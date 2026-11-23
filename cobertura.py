"""Informe de cobertura: cuánta información REAL se obtuvo, calculado desde los datos y las observaciones registradas.

Una miniatura cuenta como INSPECCIONADA solo si existe una observación registrada (`registrar miniatura`).
Un video cuenta como INSPECCIONADO VISUALMENTE solo si hay análisis de fotogramas Y observación registrada.
"""
import os, json

from . import fechas

PRIVADOS = ["CTR (tasa de clics)", "retención de audiencia", "impresiones", "RPM/CPM", "ingresos", "fuentes de tráfico",
            "demografía de la audiencia"]


def leer_observaciones(carpeta):
    ruta = os.path.join(carpeta, "observaciones.jsonl")
    out = []
    if os.path.exists(ruta):
        for ln in open(ruta, encoding="utf-8"):
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def registrar(carpeta, tipo, vid, texto):
    os.makedirs(carpeta, exist_ok=True)
    with open(os.path.join(carpeta, "observaciones.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"tipo": tipo, "id": vid, "texto": texto, "fecha": fechas.iso(fechas.ahora())},
                           ensure_ascii=False) + "\n")


def calcular(carpeta, canal, videos, seleccion, miniaturas, transcripciones, visuales, proveedores, listas_completas, notas):
    obs = leer_observaciones(carpeta)
    ob = lambda t: {o["id"] for o in obs if o["tipo"] == t}
    n = len(videos)
    por = lambda f: sum(1 for v in videos if f(v))
    largos = [v for v in videos if v.get("formato") == "largo"]
    shorts = [v for v in videos if v.get("formato") == "short"]
    directos = [v for v in videos if v.get("formato") == "directo"]
    estrenos = [v for v in videos if v.get("formato") == "estreno_o_directo"]
    otros = n - len(largos) - len(shorts) - len(directos) - len(estrenos)
    mini_ok = [m for m in miniaturas if m.get("valida")]
    mini_obs = [m for m in mini_ok if m["id"] in ob("miniatura")]
    tr_ok = [t for t in transcripciones if t.get("estado") == "ok"]
    tr_obs = [t for t in tr_ok if t["video_id"] in ob("narrativa")]
    vis_ok = [v for v in visuales if v.get("estado") == "ok"]
    vis_obs = [v for v in vis_ok if v.get("id_video") in ob("visual")]
    cob = {
        "canal": canal.get("titulo"), "handle": canal.get("handle"), "consulta": fechas.iso(fechas.ahora()),
        "videos_identificados": n, "largos": len(largos), "shorts": len(shorts), "directos": len(directos), "estrenos_o_directos_indistinguibles": len(estrenos),
        "formato_sin_clasificar": otros,
        "videos_con_marca_de_directo_o_estreno": por(lambda v: bool(v.get("marca_directo_o_estreno"))),
        "videos_con_visualizaciones": por(lambda v: v.get("vistas") is not None),
        "videos_con_visualizaciones_exactas": por(lambda v: v.get("vistas_precision") == "exacto"),
        "videos_con_fecha_exacta": por(lambda v: v.get("publicado_precision") == "exacta"),
        "videos_con_fecha_aproximada": por(lambda v: v.get("publicado_precision") == "aproximada"),
        "videos_sin_fecha": por(lambda v: v.get("publicado_precision") == "desconocida"),
        "videos_con_duracion": por(lambda v: v.get("duracion_s") is not None),
        "videos_seleccionados_para_analisis_profundo": len(seleccion),
        "miniaturas_descargadas_validas": len(mini_ok),
        "miniaturas_inspeccionadas": len(mini_obs),
        "transcripciones_intentadas": len(transcripciones),
        "transcripciones_conseguidas": len(tr_ok),
        "transcripciones_analizadas": len(tr_obs),
        "transcripciones_por_estado": _contar([t.get("estado") for t in transcripciones]),
        "videos_con_analisis_visual_de_fotogramas": len(vis_ok),
        "videos_inspeccionados_visualmente": len(vis_obs),
        "listas_completas_por_formato": listas_completas,
        "visibles_en_pestanas": canal.get("videos_visibles_en_pestanas"),
        "videos_totales_declarados_por_el_canal": canal.get("videos_texto"),
        "discrepancias_de_datos": por(lambda v: bool(v.get("discrepancias"))),
        "proveedores": proveedores,
        "datos_privados_no_disponibles": PRIVADOS,
        "limitaciones_de_esta_ejecucion": notas,
    }
    # veredicto por tipo de conclusión
    def nivel(ok, parcial):
        return "SUFICIENTE" if ok else "PARCIAL" if parcial else "INSUFICIENTE"
    nl, ns = len(largos), len(shorts)
    cob["veredicto"] = {
        "estadistica_largos": nivel(nl >= 15, nl >= 5),
        "estadistica_shorts": nivel(ns >= 15, ns >= 5),
        "patrones_de_titulo": nivel(n >= 30, n >= 10),
        "miniaturas": nivel(len(mini_obs) >= 5, len(mini_obs) >= 2),
        "narrativa_guion": nivel(len(tr_obs) >= 3, len(tr_ok) >= 1),
        "edicion_visual": nivel(len(vis_obs) >= 1, len(vis_ok) >= 1),
    }
    return cob


def _contar(xs):
    d = {}
    for x in xs:
        d[x] = d.get(x, 0) + 1
    return d


def texto(c):
    L = []
    L.append("INFORME DE COBERTURA (calculado con los datos reales de esta ejecución)")
    L.append("CANAL ANALIZADO: %s %s" % (c["canal"], ("(" + c["handle"] + ")") if c.get("handle") else ""))
    L.append("CONSULTA: %s" % c["consulta"])
    L.append("VIDEOS IDENTIFICADOS: %d  (largos %d · shorts %d · directos %d · estrenos/directos sin distinguir %d · sin clasificar %d; los directos y los 'sin distinguir' quedan fuera de las estadísticas). Con marca de directo/estreno pero listados como video normal: %d" % (
        c["videos_identificados"], c["largos"], c["shorts"], c["directos"], c["estrenos_o_directos_indistinguibles"], c["formato_sin_clasificar"], c.get("videos_con_marca_de_directo_o_estreno", 0)))
    if c.get("visibles_en_pestanas"):
        L.append("VISIBLES EN LAS PESTAÑAS DEL CANAL: %s (el canal declara %s) → analizados: largos %d, shorts %d" % (
            c["visibles_en_pestanas"], c.get("videos_totales_declarados_por_el_canal"), c["largos"], c["shorts"]))
    L.append("¿LO ANALIZADO CUBRE TODO LO VISIBLE?: " + ", ".join("%s=%s" % (k, {True: "sí", False: "no (parcial)", None: "no se sabe"}[v])
                                                      for k, v in c["listas_completas_por_formato"].items()))
    L.append("VIDEOS CON VISUALIZACIONES: %d (exactas: %d)" % (c["videos_con_visualizaciones"], c["videos_con_visualizaciones_exactas"]))
    L.append("VIDEOS CON FECHA EXACTA: %d · aproximada: %d · sin fecha: %d" % (
        c["videos_con_fecha_exacta"], c["videos_con_fecha_aproximada"], c["videos_sin_fecha"]))
    L.append("MINIATURAS: %d descargadas y válidas · %d INSPECCIONADAS (con observación registrada)" % (
        c["miniaturas_descargadas_validas"], c["miniaturas_inspeccionadas"]))
    L.append("TRANSCRIPCIONES: %d conseguidas de %d intentadas · %d analizadas %s" % (
        c["transcripciones_conseguidas"], c["transcripciones_intentadas"], c["transcripciones_analizadas"],
        c["transcripciones_por_estado"]))
    L.append("VIDEOS INSPECCIONADOS VISUALMENTE: %d (fotogramas analizados: %d)" % (
        c["videos_inspeccionados_visualmente"], c["videos_con_analisis_visual_de_fotogramas"]))
    L.append("DISCREPANCIAS ENTRE FUENTES: %d videos" % c["discrepancias_de_datos"])
    L.append("PROVEEDORES: " + "; ".join("%s=%s" % (k, v.get("estado")) for k, v in c["proveedores"].items()))
    L.append("DATOS PRIVADOS NO DISPONIBLES: " + ", ".join(c["datos_privados_no_disponibles"]) + ".")
    L.append("VEREDICTO POR TIPO DE CONCLUSIÓN: " + " · ".join("%s: %s" % (k, v) for k, v in c["veredicto"].items()))
    if c["limitaciones_de_esta_ejecucion"]:
        L.append("LIMITACIONES: " + " | ".join(c["limitaciones_de_esta_ejecucion"]))
    return "\n".join(L)
