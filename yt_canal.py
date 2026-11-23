#!/usr/bin/env python3
"""
yt_canal.py v1.1 - Motor de investigación de solo lectura del Analizador de Canales Exitosos.

Solo biblioteca estándar de Python 3.8+. Sin cuentas ni claves obligatorias. Solo LEE páginas públicas (y,
si el alumno lo configura, la API oficial de YouTube y la herramienta yt-dlp ya instalada). Escribe únicamente
en la carpeta de resultados (--out, por defecto ./analisis_canales/).

Comandos principales
  investigar <url|@handle|UC..> [--nivel 1|2|3] [--max-videos 100] [--presupuesto 240]
        Motor completo: reconocimiento -> lista amplia -> fechas exactas -> estadísticas -> selección ->
        miniaturas -> transcripciones -> informe de cobertura. Genera JSON estructurado.
  cobertura <carpeta_del_canal>          Recalcula el informe de cobertura (tras registrar observaciones).
  registrar <miniatura|narrativa|visual> <id> --texto "..." --canal <carpeta>
        Deja constancia de lo que Claude REALMENTE inspeccionó (para que la cobertura sea veraz).
  video <url|id>                          Ficha de un video (metadatos, miniatura, transcripción).
  frames <archivo> [--n 12] [--umbral 0.3]  Fotogramas/cortes de un video LOCAL (ffmpeg opcional).
  transcribir-local <archivo>             Transcripción local (herramienta opcional).
  externo <carpeta_del_canal> --fuente .. --dato .. --valor .. --fecha .. --tipo ..   Dato de fuente externa.
  limpiar-cache <carpeta_del_canal>       Borra solo la caché temporal del canal.
  doctor                                  Diagnóstico del entorno (Python, yt-dlp, ffmpeg, API, red, escritura).
  api-config / api-estado                 Configura/consulta la clave opcional de la API (en TU terminal).
Compatibilidad v1.0: canal, miniaturas, estado.
"""
import sys, os, json, argparse, getpass, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yt_engine import net, fechas, motor, prov_publico as pub, prov_ytdlp as ydl, prov_api as api  # noqa: E402
from yt_engine import miniaturas as mini, transcripciones as trans, visual, cobertura as cob  # noqa: E402

VERSION = motor.VERSION


def _sal(d):
    print(json.dumps(d, ensure_ascii=False))


def resumen_consola(d, ruta):
    cv = d["cobertura"]
    print("OK canal:", d["canal"].get("titulo"), "|", d["canal"].get("handle"), "|", d["canal"].get("suscriptores_texto"))
    print("Consulta:", d["fecha_consulta"], "| videos:", cv["videos_identificados"],
          "(largos %d, shorts %d, directos %d)" % (cv["largos"], cv["shorts"], cv["directos"]),
          "| %.0f s" % d["duracion_ejecucion_s"])
    for k in ("largo", "short"):
        e = d["estadisticas"][k]
        print(" -", k, "n=%d" % e["n_muestra"], "confianza=" + e["confianza"],
              ("mediana=%s outliers5x=%s" % (e.get("mediana_vistas"), e.get("n_outliers_5x"))) if e.get("mediana_vistas") is not None else e.get("nota", ""))
    print()
    print(cob.texto(cv))
    for av in d["avisos"]:
        print("AVISO:", av)
    print("Guardado:", os.path.join(ruta, "datos_canal.json"))


def cmd_investigar(a, nivel=None):
    d = motor.investigar(a.entrada, a.out, nivel=nivel or a.nivel, max_videos=a.max_videos, presupuesto_s=a.presupuesto,
                         idiomas=tuple(x.strip() for x in a.idioma.split(",") if x.strip()),
                         max_paginas=a.max_paginas, miniaturas=not a.sin_miniaturas, transcripciones=not a.sin_transcripciones,
                         max_transcripciones=a.max_transcripciones)
    ruta = d.pop("_carpeta")
    if a.json:
        _sal({"carpeta": ruta, "cobertura": d["cobertura"], "estadisticas": d["estadisticas"], "seleccion": d["seleccion"],
              "archivos": ["datos_canal.json", "videos.jsonl", "seleccion.json", "cobertura.json", "COBERTURA.txt"]})
    else:
        resumen_consola(d, ruta)


def cmd_canal(a):  # compatible con v1.0: reconocimiento rápido (nivel 1, sin miniaturas ni transcripciones)
    a.max_videos, a.sin_miniaturas, a.sin_transcripciones = 30, True, True
    cmd_investigar(a, nivel=1)


def _carpeta_canal(a, ref):
    if os.path.isdir(ref):
        return ref
    p = os.path.join(a.out, ref)
    if os.path.isdir(p):
        return p
    raise SystemExit("No existe la carpeta del canal: %s (usa la ruta que imprimió `investigar`)" % ref)


def cmd_cobertura(a):
    carpeta = _carpeta_canal(a, a.carpeta)
    d = json.load(open(os.path.join(carpeta, "datos_canal.json"), encoding="utf-8"))
    mini_res, tr, vis = [], [], []
    ip = os.path.join(carpeta, "miniaturas", "miniaturas_indice.json")
    if os.path.exists(ip):
        mini_res = json.load(open(ip, encoding="utf-8")).get("miniaturas", [])
    td = os.path.join(carpeta, "transcripciones")
    ti = os.path.join(td, "_intentos.json")
    if os.path.exists(ti):
        tr = json.load(open(ti, encoding="utf-8"))
    elif os.path.isdir(td):
        for f in os.listdir(td):
            if f.endswith(".json") and not f.startswith("_"):
                m = json.load(open(os.path.join(td, f), encoding="utf-8"))
                m.pop("segmentos", None)
                tr.append(m)
    fd = os.path.join(carpeta, "frames")
    if os.path.isdir(fd):
        for sub in os.listdir(fd):
            fj = os.path.join(fd, sub, "frames.json")
            if os.path.exists(fj):
                j = json.load(open(fj, encoding="utf-8"))
                j["id_video"] = sub
                vis.append(j)
    cv = cob.calcular(carpeta, d["canal"], d["videos"], d.get("seleccion", []), mini_res, tr, vis, d.get("proveedores", {}),
                      d.get("cobertura", {}).get("listas_completas_por_formato", {}), d.get("avisos", []))
    json.dump(cv, open(os.path.join(carpeta, "cobertura.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(carpeta, "COBERTURA.txt"), "w", encoding="utf-8").write(cob.texto(cv) + "\n")
    print(cob.texto(cv))


def cmd_registrar(a):
    carpeta = _carpeta_canal(a, a.canal)
    if len(a.texto.strip()) < 10:
        raise SystemExit("La observación es demasiado corta: describe lo que realmente viste/leíste.")
    cob.registrar(carpeta, a.tipo, a.id, a.texto.strip())
    print("Registrado:", a.tipo, a.id)


def _id_video(e):
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([\w-]{11})", e) or re.fullmatch(r"([\w-]{11})", e.strip())
    if not m:
        raise SystemExit("No se reconoce el id del video: %s" % e)
    return m.group(1)


def cmd_video(a):
    vid = _id_video(a.entrada)
    w = pub.watch(vid, os.path.join(a.out, "_cache"))
    carpeta = os.path.join(a.out, "videos", vid)
    os.makedirs(carpeta, exist_ok=True)
    mi = mini.descargar(vid, carpeta)
    tr = trans.obtener(vid, carpeta, w["pistas_subtitulos"], w["duracion_s"], tuple(x for x in a.idioma.split(",")))
    out = {"fecha_consulta": w["consulta"], "id": vid, "url": "https://www.youtube.com/watch?v=" + vid,
           "titulo": w["titulo"], "canal": w["canal"], "channel_id": w["canal_id"], "duracion_s": w["duracion_s"],
           "vistas": w["vistas"], "vistas_precision": "exacto", "fecha_publicacion": w["publicado"],
           "fecha_publicacion_precision": "exacta" if w["publicado"] else "desconocida",
           "es_directo_o_estreno": w["es_directo"], "descripcion": w["descripcion"], "palabras_clave": w["palabras_clave"],
           "categoria": w["categoria"], "capitulos": w["capitulos"], "pistas_subtitulos": w["pistas_subtitulos"],
           "miniatura": mi, "miniatura_local": mi.get("archivo"), "transcripcion": tr,
           "estado_transcripcion": tr.get("estado"),
           "nivel_de_acceso": "transcripcion" if tr.get("estado") == "ok" else "solo_metadatos",
           "nota": "Este nivel NO implica haber visto el video. Ver SKILL.md: niveles de inspección."}
    with open(os.path.join(carpeta, "video.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("OK video:", out["titulo"], "|", out["canal"], "|", out["vistas"], "vistas |", out["fecha_publicacion"])
    print("Miniatura:", mi.get("estado"), mi.get("archivo") or "")
    print("Transcripción:", tr.get("estado"), "(%s)" % tr.get("metodo"), tr.get("detalle", ""))
    print("Nivel de acceso:", out["nivel_de_acceso"])
    print("Guardado:", os.path.join(carpeta, "video.json"))


def cmd_miniaturas(a):
    vids = [_id_video(e) for e in a.entradas]
    for r in mini.lote([{"id": v} for v in vids], os.path.join(a.out, "miniaturas")):
        print(r["id"], "->", r.get("archivo") or "NO DISPONIBLE", ("%dx%d" % (r["ancho"], r["alto"])) if r.get("valida") else "")


def cmd_frames(a):
    r = visual.analizar(a.archivo, a.out, a.n, a.umbral)
    if r.get("estado") != "ok":
        print(r.get("detalle") or r["estado"])
        sys.exit(2)
    print("OK frames: %d cambios de plano, %d fotogramas de muestra -> %s" % (r["cambios_de_plano_detectados"], r["n_fotogramas_muestra"], r["carpeta"]))


def cmd_transcribir_local(a):
    r = trans.local(a.archivo, os.path.join(a.out, "transcripciones"), a.id, a.idioma, a.modelo, a.permitir_descarga)
    print(json.dumps({k: v for k, v in r.items() if k != "segmentos"}, ensure_ascii=False, indent=1))


def cmd_externo(a):
    carpeta = _carpeta_canal(a, a.carpeta)
    ruta = os.path.join(carpeta, "fuentes_externas.json")
    lista = json.load(open(ruta, encoding="utf-8")) if os.path.exists(ruta) else []
    lista.append({"fuente": a.fuente, "dato": a.dato, "valor": a.valor, "fecha_del_dato": a.fecha, "tipo": a.tipo,
                  "registrado": fechas.iso(fechas.ahora()), "nota": "Fuente externa; no es un dato directo de YouTube."})
    json.dump(lista, open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("Registrado dato externo (%s) de %s con fecha %s" % (a.tipo, a.fuente, a.fecha))


def cmd_estado(a):
    base = a.carpeta
    if not os.path.isdir(base):
        print("No hay carpeta de resultados todavía en:", base)
        return
    from datetime import datetime
    claves = ("datos_canal.json", "video.json", "PROGRESO.md", "frames.json", "COBERTURA.txt", "cobertura.json",
              "seleccion.json", "observaciones.jsonl")
    for raiz, dirs, fs in os.walk(base):
        dirs[:] = [d for d in dirs if d != "_cache"]
        for f in sorted(fs):
            if f in claves or f.endswith("_transcripcion.txt") or (os.path.basename(raiz) == "transcripciones" and f.endswith(".json")):
                p = os.path.join(raiz, f)
                print("%s  (%s)" % (os.path.relpath(p, base), datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M")))


def cmd_limpiar_cache(a):
    """Borra SOLO la subcarpeta _cache del canal indicado (nunca otra cosa)."""
    import shutil
    carpeta = _carpeta_canal(a, a.carpeta)
    objetivo = os.path.join(carpeta, "_cache")
    if os.path.basename(objetivo) != "_cache" or not os.path.isdir(objetivo):
        print("No hay _cache en", carpeta)
        return
    n = sum(len(fs) for _, _, fs in os.walk(objetivo))
    shutil.rmtree(objetivo)
    print("Caché eliminada (%d archivos). Los resultados y el informe no se tocan." % n)


def cmd_doctor(a):
    info = {"python": sys.version.split()[0], "sistema": sys.platform,
            "codificacion_stdout": getattr(sys.stdout, "encoding", None),
            "yt_dlp": {"instalado": bool(ydl.disponible()), "version": ydl.version(), "antiguedad_dias": ydl.antiguedad_dias()},
            "ffmpeg": visual.disponible(), "api_youtube": "configurada" if api.configurada() else "no configurada (opcional)"}
    if info["yt_dlp"]["antiguedad_dias"] and info["yt_dlp"]["antiguedad_dias"] > 120:
        info["yt_dlp"]["aviso"] = "Versión antigua: YouTube cambia a menudo. Actualiza yt-dlp con tu permiso."
    try:
        os.makedirs(a.out, exist_ok=True)
        t = os.path.join(a.out, ".prueba_escritura")
        open(t, "w").write("ok")
        os.remove(t)
        info["escritura_en_carpeta_resultados"] = True
    except Exception as e:
        info["escritura_en_carpeta_resultados"] = "NO: %s" % e
    try:
        net.get("https://www.youtube.com/feeds/videos.xml?channel_id=UCHnyfMqiRRG1u-2MsSQLbXA", prov="doctor", retries=0, timeout=15)
        info["red_youtube"] = "ok"
    except Exception as e:
        info["red_youtube"] = "FALLO: %s" % str(e)[:100]
    if info["red_youtube"] != "ok":
        info["modo_recomendado"] = "sin red: modo manual (el alumno pega datos o capturas)"
    elif info["yt_dlp"]["instalado"]:
        info["modo_recomendado"] = "completo (con yt-dlp)"
    else:
        info["modo_recomendado"] = "básico gratuito (páginas públicas): lista parcial y sin transcripciones automáticas"
    print(json.dumps(info, ensure_ascii=False, indent=1))


def cmd_api_estado(a):
    print("API de YouTube:", "configurada" if api.configurada() else "NO configurada (es opcional; el análisis funciona sin ella)")


def cmd_api_config(a):
    if not sys.stdin.isatty():
        raise SystemExit("Ejecuta este comando en TU propia terminal (no dentro de la conversación): la clave nunca debe pegarse en el chat.")
    k = getpass.getpass("Pega tu clave de la API de YouTube Data v3 (no se mostrará): ").strip()
    if not k:
        raise SystemExit("Cancelado.")
    api.ARCHIVO_CLAVE.parent.mkdir(parents=True, exist_ok=True)
    api.ARCHIVO_CLAVE.write_text(k, encoding="utf-8")
    try:
        os.chmod(api.ARCHIVO_CLAVE, 0o600)
    except Exception:
        pass
    print("Clave guardada en tu carpeta de usuario (solo local). No se mostrará nunca en informes ni registros.")


def main():
    ap = argparse.ArgumentParser(description="Motor de investigación de solo lectura (v%s)" % VERSION)
    ap.add_argument("--out", default=os.path.join(os.getcwd(), "analisis_canales"), help="Carpeta de resultados")
    sp = ap.add_subparsers(dest="cmd", required=True)

    def comun(p):
        p.add_argument("--max-videos", type=int, default=100)
        p.add_argument("--presupuesto", type=int, default=240)
        p.add_argument("--max-paginas", type=int, default=80, help="Tope de cortesía de páginas de video por ejecución")
        p.add_argument("--idioma", default="es,en")
        p.add_argument("--sin-miniaturas", action="store_true")
        p.add_argument("--sin-transcripciones", action="store_true")
        p.add_argument("--max-transcripciones", type=int, default=6)
        p.add_argument("--json", action="store_true", help="Imprime un resumen JSON compacto")
    i = sp.add_parser("investigar"); i.add_argument("entrada"); i.add_argument("--nivel", type=int, default=3, choices=[1, 2, 3]); comun(i)
    c = sp.add_parser("canal"); c.add_argument("entrada"); c.add_argument("--tope-largos", type=int, default=20)
    c.add_argument("--tope-shorts", type=int, default=30); comun(c)
    k = sp.add_parser("cobertura"); k.add_argument("carpeta")
    r = sp.add_parser("registrar"); r.add_argument("tipo", choices=["miniatura", "narrativa", "visual"]); r.add_argument("id")
    r.add_argument("--texto", required=True); r.add_argument("--canal", required=True)
    v = sp.add_parser("video"); v.add_argument("entrada"); v.add_argument("--idioma", default="es,en")
    m = sp.add_parser("miniaturas"); m.add_argument("entradas", nargs="+")
    f = sp.add_parser("frames"); f.add_argument("archivo"); f.add_argument("--n", type=int, default=12); f.add_argument("--umbral", type=float, default=0.3)
    t = sp.add_parser("transcribir-local"); t.add_argument("archivo"); t.add_argument("--id", default="local"); t.add_argument("--idioma", default=None); t.add_argument("--modelo", default="base"); t.add_argument("--permitir-descarga", action="store_true")
    x = sp.add_parser("externo"); x.add_argument("carpeta"); x.add_argument("--fuente", required=True); x.add_argument("--dato", required=True)
    x.add_argument("--valor", required=True); x.add_argument("--fecha", required=True)
    x.add_argument("--tipo", required=True, choices=["externo_actual", "historico", "estimacion", "no_verificable"])
    e = sp.add_parser("estado"); e.add_argument("carpeta", nargs="?", default=os.path.join(os.getcwd(), "analisis_canales"))
    lc = sp.add_parser("limpiar-cache"); lc.add_argument("carpeta")
    sp.add_parser("doctor"); sp.add_parser("api-estado"); sp.add_parser("api-config")
    a = ap.parse_args()
    try:
        {"investigar": cmd_investigar, "canal": cmd_canal, "cobertura": cmd_cobertura, "registrar": cmd_registrar,
         "video": cmd_video, "miniaturas": cmd_miniaturas, "frames": cmd_frames, "transcribir-local": cmd_transcribir_local,
         "externo": cmd_externo, "limpiar-cache": cmd_limpiar_cache, "estado": cmd_estado, "doctor": cmd_doctor, "api-estado": cmd_api_estado,
         "api-config": cmd_api_config}[a.cmd](a)
    except SystemExit:
        raise
    except Exception as ex:
        print("ERROR:", api.redactar(ex))
        print("Sugerencia: ejecuta `doctor` para diagnosticar el entorno; si no hay red, usa el modo manual (pega datos o capturas).")
        sys.exit(1)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
