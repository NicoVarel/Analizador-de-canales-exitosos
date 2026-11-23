"""Proveedor A: páginas públicas de YouTube (solo lectura).

Fuentes: página del canal (cabecera), feed RSS oficial, pestañas Videos / Shorts / Streams / Playlists
(primera página) y la página pública de cada video (fecha exacta, vistas exactas, duración, descripción).
No usa la API interna de YouTube ni claves extraídas de las páginas.
"""
import re, json, time, os, hashlib
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

from . import net, fechas, registro

YT = "https://www.youtube.com"


# ---------- utilidades de parseo ----------
def _json_tras(html, marcador):
    if marcador in html:
        i = html.index(marcador) + len(marcador)
        return json.JSONDecoder().raw_decode(html[i:])[0]
    return None


def initial_data(html):
    return _json_tras(html, "ytInitialData = ") or _json_tras(html, 'ytInitialData"] = ')


def player_response(html):
    return _json_tras(html, "ytInitialPlayerResponse = ")


def find_all(o, key, out=None):
    out = [] if out is None else out
    if isinstance(o, dict):
        for k, v in o.items():
            if k == key:
                out.append(v)
            else:
                find_all(v, key, out)
    elif isinstance(o, list):
        for v in o:
            find_all(v, key, out)
    return out


def slug(s):
    s = re.sub(r"[^\w\-]+", "_", (s or "").strip(), flags=re.U).strip("_")
    return (s or "canal")[:60]


# ---------- resolución de canal ----------
def resolver_url(entrada):
    e = entrada.strip()
    if re.fullmatch(r"UC[\w-]{22}", e):
        return "%s/channel/%s" % (YT, e)
    if e.startswith("@"):
        return "%s/%s" % (YT, e)
    if not e.startswith("http"):
        e = "https://" + e
    u = urlparse(e)
    if "youtube.com" not in u.netloc and "youtu.be" not in u.netloc:
        raise ValueError("La URL no parece de YouTube: %s" % entrada)
    path = re.sub(r"/(videos|shorts|streams|featured|about|playlists|community|live)/?$", "", u.path)
    return "%s%s" % (YT, path)


def cabecera(base):
    html = net.get(base + ("&" if "?" in base else "?") + "hl=en", prov="publico_cabecera")
    d = initial_data(html)
    if not d:
        raise net.ErrorFuente("YouTube no devolvió datos legibles para %s" % base)
    meta = (find_all(d, "channelMetadataRenderer") or [{}])[0]
    blob = json.dumps(d, ensure_ascii=False)
    subs = re.search(r'"content":\s*"([\d.,]+[KMB]? subscribers?)"', blob)
    nvid = re.search(r'"content":\s*"([\d.,]+[KMB]? videos?)"', blob)
    handle = re.search(r'youtube\.com/(@[\w.\-]+)', " ".join(meta.get("ownerUrls") or []))
    return {
        "titulo": meta.get("title"), "channel_id": meta.get("externalId"), "url_canal": meta.get("channelUrl"),
        "handle": handle.group(1) if handle else None,
        "descripcion": (meta.get("description") or "")[:1500],
        "palabras_clave_canal": meta.get("keywords"),
        "suscriptores_texto": subs.group(1) if subs else None,
        "videos_texto": nvid.group(1) if nvid else None,
        "familia_segura": meta.get("isFamilySafe"),
        "avatar": ((meta.get("avatar") or {}).get("thumbnails") or [{}])[0].get("url"),
    }


# ---------- RSS ----------
def rss(channel_id):
    xml = net.get("%s/feeds/videos.xml?channel_id=%s" % (YT, channel_id), prov="rss")
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
          "m": "http://search.yahoo.com/mrss/"}
    root = ET.fromstring(xml)
    creado = root.find("a:published", ns)
    out = []
    for en in root.findall("a:entry", ns):
        vid = en.find("yt:videoId", ns).text
        link = en.find("a:link", ns).get("href")
        st = en.find("m:group/m:community/m:statistics", ns)
        desc = en.find("m:group/m:description", ns)
        out.append({"id": vid, "titulo": en.find("a:title", ns).text, "publicado": en.find("a:published", ns).text,
                    "vistas": int(st.get("views")) if st is not None and st.get("views") else None,
                    "formato": "short" if "/shorts/" in link else "largo", "url": link,
                    "descripcion": (desc.text or "")[:2500] if desc is not None else None})
    return (creado.text if creado is not None else None), out


# ---------- pestañas ----------
def _largos(d, ref):
    items = []
    for lk in find_all(d, "lockupViewModel"):
        vid = lk.get("contentId")
        if not vid or lk.get("contentType") not in (None, "LOCKUP_CONTENT_TYPE_VIDEO"):
            continue
        md = lk.get("metadata", {}).get("lockupMetadataViewModel", {})
        partes = []
        for row in find_all(md, "metadataParts"):
            for p in row:
                c = (p.get("text") or {}).get("content")
                if c:
                    partes.append((c, p.get("accessibilityLabel") or c))
        dur = None
        for b in find_all(lk, "thumbnailBadgeViewModel"):
            if b.get("text") and re.match(r"^\d+(:\d+)+$", b["text"]):
                dur = b["text"]
        vtxt = next((lab for c, lab in partes if re.search(r"view", lab, re.I)), None)
        rel = next((c for c, lab in partes if re.search(r"ago", c, re.I)), None)
        items.append({"id": vid, "titulo": (md.get("title") or {}).get("content"), "vistas_texto": vtxt,
                      "rel": rel, "duracion_s": fechas.dur_a_s(dur),
                      "directo": bool(rel and re.search(r"stream", rel, re.I))})
    return items


def _shorts(d):
    items = []
    for lk in find_all(d, "shortsLockupViewModel"):
        txt = lk.get("accessibilityText", "")
        vid = (lk.get("entityId", "") or "").replace("shorts-shelf-item-", "") or None
        if not vid:
            continue
        titulo = txt.rsplit(",", 1)[0] if "," in txt else txt
        vt = None
        m = re.search(r",\s*([\d.,]+\s*(?:thousand|million|billion)?)\s*views", txt, re.I)
        if m:
            vt = m.group(1) + " views"
        om = find_all(lk, "overlayMetadata")
        if om:
            sec = (om[0].get("secondaryText") or {}).get("content")
            if sec:
                vt = sec
        items.append({"id": vid, "titulo": titulo, "vistas_texto": vt})
    return items


def pestana(cid, tab):
    """Devuelve lista de items de la primera página de la pestaña (videos|shorts|streams)."""
    html = net.get("%s/channel/%s/%s?hl=en" % (YT, cid, tab), prov="publico_tabs")
    d = initial_data(html)
    if not d:
        raise net.ErrorFuente("pestaña %s vacía o ilegible" % tab)
    return _shorts(d) if tab == "shorts" else _largos(d, None)


def playlists(cid):
    try:
        html = net.get("%s/channel/%s/playlists?hl=en" % (YT, cid), prov="publico_tabs")
        d = initial_data(html) or {}
        out = []
        for lk in find_all(d, "lockupViewModel"):
            md = lk.get("metadata", {}).get("lockupMetadataViewModel", {})
            t = (md.get("title") or {}).get("content")
            if t and lk.get("contentId"):
                out.append({"id": lk["contentId"], "titulo": t, "url": "%s/playlist?list=%s" % (YT, lk["contentId"])})
        return out
    except net.ErrorFuente:
        return []


# ---------- página de un video ----------
def watch_cache(vid, cache_dir):
    """Resultado cacheado de un video (de cualquier antigüedad) o None. La fecha de publicación no cambia."""
    cf = os.path.join(cache_dir, "watch_%s.json" % vid) if cache_dir else None
    if cf and os.path.exists(cf):
        try:
            return json.load(open(cf, encoding="utf-8")), (time.time() - os.path.getmtime(cf)) / 3600.0
        except Exception:
            return None
    return None


def watch(vid, cache_dir=None, ttl_h=24, espaciado=0.4):
    """Datos exactos de un video desde su página pública. Cachea el resultado PARSEADO (no la página)."""
    cf = None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cf = os.path.join(cache_dir, "watch_%s.json" % vid)
        c = watch_cache(vid, cache_dir)
        if c and c[1] < ttl_h:
            return c[0]
    html = net.get("%s/watch?v=%s&hl=en" % (YT, vid), prov="watch", retries=0, timeout=25, espaciado=espaciado)
    pr = player_response(html) or {}
    vd = pr.get("videoDetails", {})
    if not vd.get("videoId"):
        net.marcar("watch", False, "página sin datos de video")
        raise net.ErrorFuente("página de %s sin datos" % vid)
    mf = (pr.get("microformat") or {}).get("playerMicroformatRenderer", {})
    tracks = []
    for t in (pr.get("captions", {}).get("playerCaptionsTracklistRenderer", {}) or {}).get("captionTracks", []) or []:
        tracks.append({"idioma": t.get("languageCode"), "automatica": t.get("kind") == "asr",
                       "nombre": ((t.get("name") or {}).get("simpleText"))})
    d = initial_data(html) or {}
    caps = [{"titulo": (c.get("title") or {}).get("simpleText"), "inicio_s": c.get("timeRangeStartMillis", 0) // 1000}
            for c in find_all(d, "chapterRenderer")]
    res = {
        "id": vid, "titulo": vd.get("title"), "canal": vd.get("author"), "canal_id": vd.get("channelId"),
        "duracion_s": int(vd["lengthSeconds"]) if vd.get("lengthSeconds") else None,
        "vistas": int(vd["viewCount"]) if vd.get("viewCount") else None,
        "publicado": mf.get("publishDate") or mf.get("uploadDate"),
        "es_directo": bool(vd.get("isLiveContent")), "descripcion": (vd.get("shortDescription") or "")[:2500],
        "palabras_clave": vd.get("keywords"), "categoria": mf.get("category"), "capitulos": caps,
        "pistas_subtitulos": tracks, "disponibilidad": (pr.get("playabilityStatus") or {}).get("status"),
        "consulta": fechas.iso(fechas.ahora()),
    }
    if cf:
        try:
            json.dump(res, open(cf, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception:
            pass
    return res


def watch_lote(ids, cache_dir=None, hilos=2, presupuesto_s=90, espaciado=0.4):
    """Lee páginas de video con concurrencia LIMITADA (2 hilos), espaciado y enfriamiento ante HTTP 429.
    Ante 429: pausa de 25 s (hasta 3 veces) y un solo hilo. No intenta eludir el límite: si persiste, cede el paso a otros
    proveedores y a la caché. Devuelve (resultados, fallos)."""
    import threading
    t0 = time.time()
    res, fallos = {}, {}
    estado = {"pausa_hasta": 0.0, "enfriamientos": 0, "modo_lento": False}
    lk = threading.Lock()
    sem = threading.Semaphore(max(1, min(hilos, 2)))

    def esperar_pausa():
        while True:
            with lk:
                r = estado["pausa_hasta"] - time.time()
            if r <= 0:
                return
            time.sleep(min(r, 2.0))

    def uno(i):
        if time.time() - t0 > presupuesto_s:
            return i, None, "presupuesto de tiempo agotado"
        if net.proveedor_cortado("watch"):
            return i, None, "proveedor cortado"
        for intento in range(2):
            esperar_pausa()
            with sem:
                try:
                    return i, watch(i, cache_dir, espaciado=espaciado * (3 if estado["modo_lento"] else 1)), None
                except net.ErrorFuente as e:
                    msg = str(e)
                    if "429" in msg:
                        with lk:
                            if estado["enfriamientos"] < 3 and estado["pausa_hasta"] < time.time():
                                estado["enfriamientos"] += 1
                                estado["modo_lento"] = True
                                estado["pausa_hasta"] = time.time() + 25
                        if estado["enfriamientos"] >= 3 and intento == 1:
                            return i, None, "HTTP 429 persistente"
                        continue
                    return i, None, msg[:120]
        return i, None, "HTTP 429 tras enfriamiento"
    with ThreadPoolExecutor(max_workers=max(1, min(hilos, 2))) as ex:
        for i, r, err in ex.map(uno, ids):
            if r:
                res[i] = r
            else:
                fallos[i] = err
    res["_meta"] = None
    res.pop("_meta")
    watch_lote.ultimo = {"enfriamientos": estado["enfriamientos"], "fallos": len(fallos)}
    return res, fallos
