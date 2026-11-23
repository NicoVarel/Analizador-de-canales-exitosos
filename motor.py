"""Orquestador multifuente con cadena de fallback.

Cadena (cada paso comprueba si el dato ya es suficiente antes de pedir otro proveedor):
 1  Cabecera del canal      público -> RSS(id) -> API -> yt-dlp
 2  Lista de publicaciones  público (1ª página + RSS) -> [API uploads | yt-dlp por pestaña] si hace falta profundidad
 3  Fechas/vistas exactas   página del video (4 hilos) -> API videos.list -> yt-dlp por video (tope 20)
 4  Estadísticas            solo desde los registros
 5  Selección (5-10)        por rendimiento relativo
 6  Miniaturas / subtítulos solo para la selección
 7  Cobertura               desde datos + observaciones registradas
"""
import os, json, time

from . import net, fechas, registro, estadisticas, prov_publico as pub, prov_ytdlp as ydl, prov_api as api
from . import miniaturas as mini, transcripciones as trans, cobertura as cob

VERSION = "1.1.0-rc1"
FORMATOS_CONOCIDOS = ("largo", "short", "directo")


class Ctx:
    def __init__(self, out, nivel, max_videos, presupuesto_s):
        self.out, self.nivel, self.max_videos = out, nivel, max_videos
        self.t0, self.presupuesto = time.time(), presupuesto_s
        self.pasos, self.notas = [], []
        self.recs = {}

    def resta(self):
        return self.presupuesto - (time.time() - self.t0)

    def paso(self, nombre, prov, estado, detalle="", n=None):
        self.pasos.append({"paso": nombre, "proveedor": prov, "estado": estado, "detalle": detalle, "n": n,
                           "t_s": round(time.time() - self.t0, 1)})

    def rec(self, vid):
        if vid not in self.recs:
            self.recs[vid] = registro.nuevo(vid)
            self.recs[vid]["url"] = "https://www.youtube.com/watch?v=" + vid
        return self.recs[vid]


# ---------- cabecera ----------
def _cabecera(c, entrada):
    base = pub.resolver_url(entrada)
    cab, err = None, []
    try:
        cab = pub.cabecera(base)
        c.paso("cabecera", "publico", "ok", cab.get("titulo"))
    except Exception as e:
        err.append("público: %s" % e)
        c.paso("cabecera", "publico", "fallo", str(e)[:100])
    cid = (cab or {}).get("channel_id")
    if not cid and entrada.strip().startswith("UC"):
        cid = entrada.strip()
    if not cid and api.configurada():
        try:
            h = entrada.strip() if entrada.strip().startswith("@") else None
            if h is None and "/@" in entrada:
                h = "@" + entrada.split("/@")[1].split("/")[0]
            a = api.canal(handle=h) if h else None
            if a:
                cid = a["channel_id"]
                cab = {"titulo": a["titulo"], "channel_id": cid, "handle": h, "descripcion": a["descripcion"]}
                c.paso("cabecera", "api", "ok", "recuperada vía API")
        except Exception as e:
            err.append("api: %s" % e)
    if not cid and ydl.disponible():
        try:
            r = ydl.listar(base + "/videos", fin=1)
            cid = r.get("canal_id")
            cab = {"titulo": r.get("titulo"), "channel_id": cid}
            c.paso("cabecera", "ytdlp", "ok", "recuperada vía yt-dlp")
        except Exception as e:
            err.append("yt-dlp: %s" % e)
    if not cid:
        raise net.ErrorFuente("No se pudo identificar el canal (%s). Revisa el enlace o usa el modo manual." % "; ".join(err)[:300])
    cab = cab or {}
    cab["channel_id"] = cid
    return cab


# ---------- listados ----------
def _aportar_tab(c, items, formato, es_directo=False):
    ahora = fechas.ahora()
    for pos, it in enumerate(items):
        r = c.rec(it["id"])
        r.setdefault("orden_lista", pos) if formato != "directo" else None
        aportar = lambda campo, valor, prec=None, extra=None: registro.aportar(r, campo, valor, "tab", prec, None, extra)
        aportar("titulo", it.get("titulo"))
        # un video presente en Videos/Shorts es un video normal aunque también salga en la pestaña de directos (estrenos/premieres)
        aportar("formato", "directo" if it.get("directo") else "en_pestana_directos" if es_directo else formato)
        v, prec = fechas.parse_views(it.get("vistas_texto"))
        if v is not None:
            aportar("vistas", v, prec, it.get("vistas_texto"))
        if it.get("duracion_s"):
            aportar("duracion_s", it["duracion_s"])
        rr = fechas.relativa_a_rango(it.get("rel"), ahora) if it.get("rel") else None
        if rr:
            aportar("publicado", rr[0], "aproximada", {"rango_dias": [rr[1], rr[2]], "texto": it["rel"]})


def _listar(c, cid, base):
    completo = {"largo": None, "short": None}
    # RSS (también da la fecha de creación del canal)
    creado = None
    try:
        creado, ents = pub.rss(cid)
        for e in ents:
            r = c.rec(e["id"])
            registro.aportar(r, "titulo", e["titulo"], "rss")
            registro.aportar(r, "publicado", e["publicado"], "rss", "exacta")
            registro.aportar(r, "vistas", e["vistas"], "rss", "exacto")
            registro.aportar(r, "formato", e["formato"], "rss")
            registro.aportar(r, "descripcion", e.get("descripcion"), "rss")
            r["url"] = e["url"]
        c.paso("lista", "rss", "ok", "últimos videos con fecha y vistas exactas", len(ents))
    except Exception as e:
        c.paso("lista", "rss", "fallo", str(e)[:100])
    # pestañas públicas (1ª página)
    tamano = {"videos": 30, "shorts": 48}
    for tab, fm in (("videos", "largo"), ("shorts", "short")):
        try:
            items = pub.pestana(cid, tab)
            _aportar_tab(c, items, fm)
            completo[fm] = len(items) < tamano[tab] * 0.9  # página no llena => no hay más
            c.paso("lista", "publico_tabs", "ok", "pestaña %s (1ª página)" % tab, len(items))
        except Exception as e:
            c.paso("lista", "publico_tabs", "fallo", "pestaña %s: %s" % (tab, str(e)[:90]))
    try:
        items = pub.pestana(cid, "streams")
        _aportar_tab(c, items, "directo", es_directo=True)
        c.paso("lista", "publico_tabs", "ok", "pestaña directos", len(items))
    except Exception:
        pass
    # profundidad (nivel >= 2): solo si falta y hay un proveedor permitido
    cuenta = lambda fm: sum(1 for r in c.recs.values() if _fm(r) == fm)
    necesita = c.nivel >= 2 and any(completo[f] is not True and cuenta(f) < c.max_videos for f in ("largo", "short"))
    if necesita:
        hecho = False
        if api.configurada() and not net.proveedor_cortado("api"):
            try:
                _profundidad_api(c, cid)
                hecho = True
            except Exception as e:
                c.paso("lista_profunda", "api", "fallo", api.redactar(e)[:120])
        else:
            c.paso("lista_profunda", "api", "no_configurado", "sin clave de API (opcional)")
        if not hecho and ydl.disponible() and not net.proveedor_cortado("ytdlp"):
            try:
                _profundidad_ytdlp(c, cid, base, completo)
                hecho = True
            except Exception as e:
                c.paso("lista_profunda", "ytdlp", "fallo", str(e)[:120])
        elif not hecho:
            c.paso("lista_profunda", "ytdlp", "no_disponible" if not ydl.disponible() else "cortado",
                   "yt-dlp no instalado (opcional)" if not ydl.disponible() else "")
        if not hecho:
            c.notas.append("Lista parcial: solo la primera página de cada pestaña + feed RSS (no hay API ni yt-dlp disponibles).")
    return creado, completo


def _fm(r):
    cand = r["_cand"].get("formato")
    if not cand:
        return None
    vals = {x["valor"] for x in cand}
    if "directo" in vals:
        return "directo"
    normales = [x for x in cand if x["valor"] in ("largo", "short")]
    if normales:
        return sorted(normales, key=lambda x: registro.FIABILIDAD.get(x["fuente"], 0), reverse=True)[0]["valor"]
    return "estreno_o_directo" if "en_pestana_directos" in vals else None


def _profundidad_ytdlp(c, cid, base, completo):
    fin = c.max_videos
    for tab, fm in (("videos", "largo"), ("shorts", "short")):
        if c.resta() < 20:
            c.notas.append("Presupuesto de tiempo agotado antes de listar %s." % tab)
            break
        r = ydl.listar("%s/channel/%s/%s" % (pub.YT, cid, tab), fin=fin)
        ents = r["entradas"]
        for pos, e in enumerate(ents):
            rec = c.rec(e["id"])
            rec.setdefault("orden_lista", pos)
            registro.aportar(rec, "titulo", e["titulo"], "ytdlp")
            registro.aportar(rec, "formato", fm, "ytdlp")
            if e.get("live_status") in ("was_live", "is_live", "is_upcoming"):
                rec["marca_directo_o_estreno"] = True
            if e.get("vistas") is not None:
                registro.aportar(rec, "vistas", e["vistas"], "ytdlp", "aprox")  # la lista plana redondea cifras antiguas
            if e.get("duracion_s"):
                registro.aportar(rec, "duracion_s", int(e["duracion_s"]), "ytdlp")
        completo[fm] = len(ents) < fin
        c.paso("lista_profunda", "ytdlp", "ok", "pestaña %s hasta %d" % (tab, fin), len(ents))


def _profundidad_api(c, cid, ):
    a = api.canal(channel_id=cid)
    ids = api.uploads(a["uploads"], maximo=int(c.max_videos * 1.6))
    det = api.videos(ids)
    n = 0
    for pos, vid in enumerate(ids):
        d = det.get(vid)
        if not d:
            continue
        r = c.rec(vid)
        r.setdefault("orden_lista", pos)
        for campo in ("titulo", "descripcion", "canal", "canal_id", "palabras_clave"):
            registro.aportar(r, campo, d.get(campo), "api")
        registro.aportar(r, "publicado", d["publicado"], "api", "exacta")
        registro.aportar(r, "vistas", d["vistas"], "api", "exacto")
        registro.aportar(r, "duracion_s", d["duracion_s"], "api")
        if d["es_directo"]:
            r["marca_directo_o_estreno"] = True  # liveStreamingDetails también existe en estrenos
        if "formato" not in r["_cand"]:
            # la API no distingue Shorts: se infiere SOLO cuando es seguro; lo dudoso queda sin clasificar
            dur = d.get("duracion_s")
            if dur is not None and dur > 180:
                registro.aportar(r, "formato", "largo", "inferido")
            elif dur is not None and dur <= 60:
                registro.aportar(r, "formato", "short", "inferido")
        n += 1
    c.paso("lista_profunda", "api", "ok", "uploads + videos.list (%d unidades de cuota)" % api.Cuota.unidades, n)
    c.api_canal = a


# ---------- fechas y vistas exactas ----------
def _enriquecer(c, cache_dir, max_paginas=80):
    # el objetivo: los videos que entrarán en las estadísticas (hasta max_videos por formato)
    por_fm = {}
    for fm in ("largo", "short"):
        rs = [r for r in c.recs.values() if _fm(r) == fm]
        rs.sort(key=lambda r: (_edad_aprox(r), r.get("orden_lista", 9999)))
        por_fm[fm] = rs[:c.max_videos]
    obj = []  # se intercalan formatos: los más recientes de cada uno primero
    for i in range(max(len(v) for v in por_fm.values()) if por_fm else 0):
        for fm in ("largo", "short"):
            if i < len(por_fm[fm]):
                obj.append(por_fm[fm][i])
    necesita_ = lambda r: (not any(x["precision"] in ("exacta", "exacto") and x["fuente"] in ("api", "watch", "rss", "ytdlp")
                                   for x in r["_cand"].get("publicado", []))
                           or not any(x["precision"] == "exacto" and x["fuente"] != "ytdlp" for x in r["_cand"].get("vistas", [])))
    pend_todos = [r["id"] for r in obj if necesita_(r)]
    # lo que ya está en caché no cuenta contra el tope de cortesía
    en_cache = [v for v in pend_todos if pub.watch_cache(v, cache_dir)]
    nuevos = [v for v in pend_todos if v not in en_cache]
    pend = en_cache + nuevos[:max_paginas]
    omitidos = len(nuevos) - len(nuevos[:max_paginas])
    if omitidos > 0:
        c.notas.append("Límite de cortesía: %d páginas de video por ejecución (para no saturar YouTube). %d videos quedan con fecha/vista "
                       "aproximada; vuelve a ejecutar `investigar` para completarlos: la caché conserva lo ya obtenido." % (max_paginas, omitidos))
    if c.nivel == 1:
        pend = pend[:30]
    if not pend:
        c.paso("fechas_exactas", "-", "ok", "no hay nada pendiente")
        return {}
    watch_res, fallos = pub.watch_lote(pend, cache_dir, hilos=2, presupuesto_s=max(15, min(150, c.resta() - 20)))
    for vid, w in watch_res.items():
        r = c.rec(vid)
        registro.aportar(r, "publicado", w["publicado"], "watch", "exacta")
        registro.aportar(r, "vistas", w["vistas"], "watch", "exacto", w["consulta"])
        registro.aportar(r, "duracion_s", w["duracion_s"], "watch")
        registro.aportar(r, "titulo", w["titulo"], "watch")
        registro.aportar(r, "descripcion", w["descripcion"], "watch")
        registro.aportar(r, "palabras_clave", w["palabras_clave"], "watch")
        registro.aportar(r, "categoria", w["categoria"], "watch")
        registro.aportar(r, "canal", w["canal"], "watch")
        if w["es_directo"]:
            r["marca_directo_o_estreno"] = True  # isLiveContent también es cierto en estrenos (premieres)
        r["pistas_subtitulos"] = w["pistas_subtitulos"]
        r["capitulos"] = w["capitulos"]
    ult = getattr(pub.watch_lote, "ultimo", {})
    if (ult.get("enfriamientos") or net.proveedor_cortado("watch")) and len(watch_res) < len(pend):
        c.notas.append("La página de video no estuvo disponible (HTTP 429 o bloqueo): el motor esperó, redujo el ritmo y no insistió. "
                       "%d de %d fechas/vistas exactas quedaron pendientes. Reintenta en unos minutos: `_cache/` conserva lo ya obtenido." % (len(pend) - len(watch_res), len(pend)))
    c.paso("fechas_exactas", "watch", "ok" if len(watch_res) == len(pend) else "parcial" if watch_res else "fallo",
           "%d de %d páginas leídas%s" % (len(watch_res), len(pend),
                                          ("; %d enfriamientos por HTTP 429" % ult["enfriamientos"]) if ult.get("enfriamientos") else ""),
           len(watch_res))
    restantes = [v for v in pend if v not in watch_res]
    # caché de ejecuciones anteriores: la FECHA de publicación no cambia; las vistas conservan su fecha de consulta
    usados = 0
    for vid in list(restantes):
        cc = pub.watch_cache(vid, cache_dir)
        if cc:
            w = cc[0]
            r = c.rec(vid)
            registro.aportar(r, "publicado", w["publicado"], "watch", "exacta", w["consulta"])
            registro.aportar(r, "vistas", w["vistas"], "watch", "exacto", w["consulta"])
            registro.aportar(r, "duracion_s", w["duracion_s"], "watch", None, w["consulta"])
            r["pistas_subtitulos"] = w.get("pistas_subtitulos")
            restantes.remove(vid)
            usados += 1
    if usados:
        c.paso("fechas_exactas", "cache", "ok", "reutilizados %d registros de ejecuciones anteriores (con su fecha de consulta)" % usados, usados)
    if restantes and api.configurada() and not net.proveedor_cortado("api"):
        try:
            det = api.videos(restantes[:200])
            for vid, d in det.items():
                r = c.rec(vid)
                registro.aportar(r, "publicado", d["publicado"], "api", "exacta")
                registro.aportar(r, "vistas", d["vistas"], "api", "exacto")
                registro.aportar(r, "duracion_s", d["duracion_s"], "api")
            restantes = [v for v in restantes if v not in det]
            c.paso("fechas_exactas", "api", "ok", "videos.list por lotes", len(det))
        except Exception as e:
            c.paso("fechas_exactas", "api", "fallo", api.redactar(e)[:100])
    if restantes and ydl.disponible() and not net.proveedor_cortado("ytdlp"):
        hechos = 0
        for vid in restantes[:20]:
            if c.resta() < 25:
                break
            try:
                d = ydl.video_json(vid)
                r = c.rec(vid)
                if d.get("publicado"):
                    registro.aportar(r, "publicado", d["publicado"], "ytdlp", "exacta")
                registro.aportar(r, "vistas", d.get("vistas"), "ytdlp", "exacto")
                registro.aportar(r, "duracion_s", d.get("duracion_s"), "ytdlp")
                hechos += 1
            except Exception:
                break
        c.paso("fechas_exactas", "ytdlp", "ok" if hechos else "fallo", "respaldo por video (tope 20)", hechos)
    _interpolar(c)
    sin = len([v for v in pend if not any(x["precision"] in ("exacta",) for x in c.rec(v)["_cand"].get("publicado", []))])
    if sin:
        c.notas.append("%d videos del análisis sin fecha exacta (se conserva la aproximada de la lista, marcada como tal)." % sin)
    return watch_res


def _primer_video(c, cid):
    """Recorre las pestañas completas con yt-dlp (lista plana, barata) para contar lo visible y hallar el video MÁS ANTIGUO
    accesible. No equivale a la fecha de creación del canal."""
    if c.nivel < 2 or not ydl.disponible() or net.proveedor_cortado("ytdlp") or c.resta() < 45:
        return None
    visibles, candidatos = {}, []
    for tab, fm in (("videos", "largo"), ("shorts", "short")):
        try:
            r = ydl.listar("%s/channel/%s/%s" % (pub.YT, cid, tab), fin=3000, timeout=240)
        except Exception as e:
            c.paso("primer_video", "ytdlp", "fallo", "%s: %s" % (tab, str(e)[:80]))
            continue
        ents = r["entradas"]
        visibles[fm] = len(ents)
        if ents:
            candidatos.append(ents[-1]["id"])
    fechados = []
    if candidatos:
        res, _ = pub.watch_lote(candidatos, os.path.join(c.out, "_cache"), hilos=2, presupuesto_s=30)
        for vid, w in res.items():
            if w.get("publicado"):
                fechados.append({"id": vid, "titulo": w["titulo"], "publicado": w["publicado"], "formato_pestana": None})
    c.paso("primer_video", "ytdlp+watch", "ok" if fechados else "fallo", "visibles %s" % visibles)
    return {"visibles": visibles, "mas_antiguo": min(fechados, key=lambda f: f["publicado"]) if fechados else None}


def _interpolar(c):
    """Fechas APROXIMADAS para videos sin fecha exacta, acotadas por el orden cronológico de la lista (más reciente primero)
    entre dos videos vecinos con fecha exacta. Siempre queda marcada 'aproximada' con su rango; jamás se presenta como exacta."""
    n = 0
    for fm in ("largo", "short"):
        rs = sorted([r for r in c.recs.values() if _fm(r) == fm and "orden_lista" in r], key=lambda r: r["orden_lista"])
        def exacta(r):
            for x in r["_cand"].get("publicado", []):
                if x["precision"] == "exacta":
                    return fechas.parse_iso(x["valor"])
            return None
        anclas = [(i, exacta(r)) for i, r in enumerate(rs) if exacta(r)]
        for (i1, d1), (i2, d2) in zip(anclas, anclas[1:]):
            if d1 < d2:  # orden no cronológico (p. ej. estreno programado): no se interpola
                continue
            for k in range(i1 + 1, i2):
                r = rs[k]
                if exacta(r):
                    continue
                centro = d2 + (d1 - d2) * ((i2 - k) / float(i2 - i1))
                ahora = fechas.ahora()
                rango = [round((ahora - d1).total_seconds() / 86400.0, 2), round((ahora - d2).total_seconds() / 86400.0, 2)]
                registro.aportar(r, "publicado", fechas.iso(centro), "orden", "aproximada",
                                 {"rango_dias": rango, "texto": "interpolada por el orden de la lista entre dos fechas exactas"})
                n += 1
    if n:
        c.paso("fechas_aproximadas", "orden_de_lista", "ok", "%d fechas aproximadas acotadas por vecinos exactos" % n, n)


def _edad_aprox(r):
    best = None
    for x in r["_cand"].get("publicado", []):
        d = fechas.edad_dias(x["valor"])
        if d is not None:
            best = d if best is None else min(best, d)
    return best if best is not None else 1e9


# ---------- principal ----------
def investigar(entrada, out, nivel=3, max_videos=100, max_paginas=80, presupuesto_s=240, idiomas=("es", "en"),
               miniaturas=True, transcripciones=True, max_transcripciones=6, n_largos=8, n_shorts=4, silencioso=False):
    c = Ctx(out, nivel, max_videos, presupuesto_s)
    cab = _cabecera(c, entrada)
    cid = cab["channel_id"]
    base = "%s/channel/%s" % (pub.YT, cid)
    carpeta = os.path.join(out, pub.slug(cab.get("handle") or cab.get("titulo") or cid))
    os.makedirs(carpeta, exist_ok=True)
    cache = os.path.join(carpeta, "_cache")
    creado, completo = _listar(c, cid, base)
    _enriquecer(c, cache, max_paginas)
    pv = _primer_video(c, cid)
    # resolver y limpiar
    ahora = fechas.ahora()
    for r in c.recs.values():
        registro.resolver(r, ahora)
        if not r.get("formato"):
            r["formato"] = "desconocido"
        r["consulta"] = fechas.iso(ahora)
        r["miniatura_url_publica"] = "https://i.ytimg.com/vi/%s/hqdefault.jpg" % r["id"]
        r["estado_transcripcion"] = "no_intentada"
        r["estado_analisis_visual"] = "no_inspeccionado"
        r["canal"] = r.get("canal") or cab.get("titulo")
    videos = sorted([registro.limpio(r) for r in c.recs.values()], key=lambda v: (v["edad_dias"] is None, v["edad_dias"] if v["edad_dias"] is not None else v.get("orden_lista", 9999)))
    # fecha del primer video accesible (distinta de la creación del canal)
    fechados = [v for v in videos if v.get("publicado") and v["publicado_precision"] == "exacta" and v["formato"] in ("largo", "short")]
    primero = min(fechados, key=lambda v: v["publicado"]) if fechados else None
    canal = dict(cab)
    if hasattr(c, "api_canal"):
        canal["creado_iso"] = c.api_canal.get("creado_iso")
        canal["creado_fuente"] = "api"
        canal["pais"] = c.api_canal.get("pais")
        canal["total_videos_api"] = c.api_canal.get("total_videos")
    elif creado:
        canal["creado_iso"] = creado
        canal["creado_fuente"] = "feed RSS del canal (campo published)"
    canal["primer_video_accesible"] = ({"id": primero["id"], "titulo": primero["titulo"], "publicado": primero["publicado"],
                                        "fuente": "registros recopilados (muestra)"} if primero else None)
    if pv:
        canal["videos_visibles_en_pestanas"] = pv["visibles"]
        if pv["mas_antiguo"]:
            canal["primer_video_accesible"] = dict(pv["mas_antiguo"], fuente="pestañas completas (lista plana) + página del video",
                                                   nota="el video público más antiguo que muestran las pestañas; no es la creación del canal")
            cuenta_ = lambda fm: sum(1 for r in c.recs.values() if _fm(r) == fm)
            for fm_, vis_ in pv["visibles"].items():
                completo[fm_] = cuenta_(fm_) >= vis_
    canal["aviso_fechas"] = ("La fecha de creación del canal NO es la del primer video. El 'primer video accesible' solo es el más "
                             "antiguo de los registros recopilados%s." % (" (la lista es completa para este formato)" if all(v is True for v in completo.values() if v is not None) and any(v is True for v in completo.values()) else "; la lista es PARCIAL, el canal puede tener videos más antiguos"))
    canal["playlists_publicas"] = pub.playlists(cid)[:20]
    est = {"largo": estadisticas.estadisticas(videos, "largo", 20), "short": estadisticas.estadisticas(videos, "short", 30)}
    ext = {"largo": estadisticas.extendidas(videos, "largo", max_videos), "short": estadisticas.extendidas(videos, "short", max_videos)}
    sel = []
    if nivel >= 2:
        sel = estadisticas.seleccionar(videos, "largo", n_largos) + estadisticas.seleccionar(videos, "short", n_shorts)
    miniaturas_res, trans_res, vis_res = [], [], []
    por_id = {v["id"]: v for v in videos}
    if nivel >= 3 and miniaturas and sel and c.resta() > 15:
        miniaturas_res = mini.lote([{"id": s["id"], "titulo": s["titulo"]} for s in sel], os.path.join(carpeta, "miniaturas"))
        for m in miniaturas_res:
            por_id[m["id"]]["miniatura"] = {k: m.get(k) for k in ("archivo", "estado", "ancho", "alto")}
        c.paso("miniaturas", "miniaturas", "ok", "%d válidas de %d" % (sum(1 for m in miniaturas_res if m.get("valida")), len(miniaturas_res)))
    if nivel >= 3 and transcripciones and sel:
        orden = [s for s in sel if s["motivo"].startswith("mejor")] + [s for s in sel if not s["motivo"].startswith("mejor")]
        for s in orden[:max_transcripciones]:
            if c.resta() < 20:
                c.notas.append("Presupuesto de tiempo agotado: transcripciones limitadas.")
                break
            v = por_id[s["id"]]
            t = trans.obtener(s["id"], os.path.join(carpeta, "transcripciones"), c.recs[s["id"]].get("pistas_subtitulos"),
                              v.get("duracion_s"), idiomas)
            trans_res.append(t)
            v["estado_transcripcion"] = t.get("estado")
            v["transcripcion"] = {k: t.get(k) for k in ("estado", "metodo", "idioma", "idioma_hablado", "es_traduccion", "automatica", "cobertura", "confianza", "con_timestamps", "archivo_texto", "detalle")}
        os.makedirs(os.path.join(carpeta, "transcripciones"), exist_ok=True)
        with open(os.path.join(carpeta, "transcripciones", "_intentos.json"), "w", encoding="utf-8") as f:
            json.dump(trans_res, f, ensure_ascii=False, indent=1)
        c.paso("transcripciones", "ytdlp" if ydl.disponible() else "-", "ok" if any(t.get("estado") == "ok" for t in trans_res) else "sin_resultados",
               "%d conseguidas de %d intentadas" % (sum(1 for t in trans_res if t.get("estado") == "ok"), len(trans_res)))
    provs = _estado_proveedores()
    coverage = cob.calcular(carpeta, canal, videos, sel, miniaturas_res, trans_res, vis_res, provs,
                            {"largos": completo["largo"], "shorts": completo["short"]}, c.notas)
    cadencia = ext["largo"].get("frecuencia") if ext["largo"].get("frecuencia", {}).get("videos_por_semana") is not None else None
    datos = {
        "version_script": VERSION, "fecha_consulta": fechas.iso(ahora), "nivel": nivel, "canal": canal,
        "cadencia_ultimos_rss": cadencia, "estadisticas": est, "estadisticas_extendidas": ext, "seleccion": sel,
        "videos": videos, "cobertura": coverage, "proveedores": provs, "pasos": c.pasos,
        "avisos": c.notas,
        "limitaciones": ["CTR, retención, impresiones, ingresos y RPM del canal ajeno NO son observables.",
                         "Una cifra de vistas es la observada en la fecha de consulta; cambia cada día.",
                         "Las fechas aproximadas (de 'hace N meses') están marcadas como tales y nunca se tratan como exactas."],
        "duracion_ejecucion_s": round(time.time() - c.t0, 1)}
    with open(os.path.join(carpeta, "datos_canal.json"), "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    with open(os.path.join(carpeta, "videos.jsonl"), "w", encoding="utf-8") as f:
        for v in videos:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    with open(os.path.join(carpeta, "seleccion.json"), "w", encoding="utf-8") as f:
        json.dump(sel, f, ensure_ascii=False, indent=1)
    with open(os.path.join(carpeta, "cobertura.json"), "w", encoding="utf-8") as f:
        json.dump(coverage, f, ensure_ascii=False, indent=1)
    with open(os.path.join(carpeta, "COBERTURA.txt"), "w", encoding="utf-8") as f:
        f.write(cob.texto(coverage) + "\n")
    datos["_carpeta"] = carpeta
    return datos


def _estado_proveedores():
    st = net.estado_proveedores()
    out = {}
    nombres = {"publico_cabecera": "youtube_publico", "publico_tabs": "youtube_publico_pestanas", "rss": "rss",
               "watch": "pagina_de_video", "ytdlp": "yt-dlp", "api": "youtube_data_api", "miniaturas": "miniaturas"}
    for k, v in st.items():
        estado = "cortado_por_fallos" if v["cortado"] else "ok" if v["ok"] and not v["errores"] else \
            "degradado" if v["ok"] else "fallo"
        out[nombres.get(k, k)] = {"estado": estado, "intentos": v["intentos"], "errores": v["errores"],
                                  "ultimo_error": v["ultimo_error"]}
    out.setdefault("yt-dlp", {"estado": ("disponible_sin_uso" if ydl.disponible() else "no_instalado"), "intentos": 0, "errores": 0,
                              "ultimo_error": None, "version": ydl.version()})
    out.setdefault("youtube_data_api", {"estado": "configurada_sin_uso" if api.configurada() else "no_configurada_opcional",
                                        "intentos": 0, "errores": 0, "ultimo_error": None})
    if "youtube_data_api" in out and api.Cuota.unidades:
        out["youtube_data_api"]["unidades_de_cuota_usadas"] = api.Cuota.unidades
    return out
