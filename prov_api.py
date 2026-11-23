"""Proveedor B: YouTube Data API v3 oficial (OPCIONAL).

Métodos usados (los más baratos, 1 unidad de cuota cada llamada):
  channels.list  ->  playlistItems.list (lista pública de 'uploads', con paginación)  ->  videos.list (lotes de 50)
No usa search.list (100 unidades por llamada).

La CLAVE:
  - se lee SOLO de la variable de entorno YOUTUBE_API_KEY o del archivo local ~/.analizador_canales/youtube_api_key.txt
  - NUNCA se imprime, ni se guarda en informes/JSON/logs; los mensajes de error se redactan
  - NUNCA se pide pegarla en la conversación: el alumno la configura en su propia terminal (comando `api-config`)
La API es gratuita con cuota diaria (por defecto 10.000 unidades/proyecto); no es ilimitada.
"""
import os, re, json
from pathlib import Path
from urllib.parse import urlencode

from . import net, fechas

BASE_DEFECTO = "https://www.googleapis.com/youtube/v3"
ARCHIVO_CLAVE = Path.home() / ".analizador_canales" / "youtube_api_key.txt"


def _clave():
    k = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not k and ARCHIVO_CLAVE.exists():
        try:
            k = ARCHIVO_CLAVE.read_text(encoding="utf-8").strip()
        except Exception:
            k = ""
    return k or None


def configurada():
    return bool(_clave()) and "api" not in net.fallos_simulados()


def _base():
    b = os.environ.get("YT_API_BASE", "").strip()
    # el desvío solo se admite hacia localhost (pruebas con servidor simulado)
    if b and re.match(r"^http://(127\.0\.0\.1|localhost)(:\d+)?(/|$)", b):
        return b.rstrip("/")
    return BASE_DEFECTO


def redactar(s):
    k = _clave()
    s = str(s)
    if k:
        s = s.replace(k, "***")
    return re.sub(r"([?&]key=)[^&\s]+", r"\1***", s)


class Cuota:
    unidades = 0


def _llamar(recurso, **params):
    k = _clave()
    if not k:
        raise net.ErrorFuente("API no configurada")
    params["key"] = k
    url = "%s/%s?%s" % (_base(), recurso, urlencode(params))
    try:
        txt = net.get(url, prov="api", retries=1)
    except net.ErrorFuente as e:
        raise net.ErrorFuente(redactar(e))
    Cuota.unidades += 1
    try:
        d = json.loads(txt)
    except Exception:
        net.marcar("api", False, "respuesta no JSON")
        raise net.ErrorFuente("respuesta de la API no válida")
    if "error" in d:
        motivo = (d["error"].get("errors") or [{}])[0].get("reason") or d["error"].get("message", "")
        net.marcar("api", False, motivo)
        if motivo in ("quotaExceeded", "dailyLimitExceeded", "keyInvalid", "accessNotConfigured", "forbidden"):
            with net._lock:
                net._estado["api"]["cortado"] = True
        raise net.ErrorFuente("API: %s" % redactar(motivo)[:120])
    return d


def _iso8601_a_s(d):
    m = re.match(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", d or "")
    if not m:
        return None
    dd, h, mi, s = [int(x or 0) for x in m.groups()]
    return dd * 86400 + h * 3600 + mi * 60 + s


def canal(channel_id=None, handle=None):
    p = {"part": "snippet,statistics,contentDetails"}
    if channel_id:
        p["id"] = channel_id
    else:
        p["forHandle"] = handle
    d = _llamar("channels", **p)
    it = (d.get("items") or [None])[0]
    if not it:
        raise net.ErrorFuente("la API no encontró el canal")
    st = it.get("statistics", {})
    return {"channel_id": it["id"], "titulo": it["snippet"].get("title"),
            "descripcion": (it["snippet"].get("description") or "")[:1500],
            "creado_iso": it["snippet"].get("publishedAt"), "pais": it["snippet"].get("country"),
            "suscriptores": None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0) or 0),
            "suscriptores_ocultos": bool(st.get("hiddenSubscriberCount")),
            "total_videos": int(st.get("videoCount", 0) or 0), "total_vistas": int(st.get("viewCount", 0) or 0),
            "uploads": it.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")}


def uploads(playlist_id, maximo=100):
    """Recorre la lista de 'uploads' con paginación hasta 'maximo' (más recientes primero)."""
    ids, token, paginas = [], None, 0
    while len(ids) < maximo and paginas < 40:
        p = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if token:
            p["pageToken"] = token
        d = _llamar("playlistItems", **p)
        for it in d.get("items", []):
            vid = it.get("contentDetails", {}).get("videoId")
            if vid and vid not in ids:
                ids.append(vid)
        paginas += 1
        token = d.get("nextPageToken")
        if not token:
            break
    return ids[:maximo]


def videos(ids):
    """Detalles públicos por lotes de 50. Devuelve {id: dict}."""
    out = {}
    for i in range(0, len(ids), 50):
        d = _llamar("videos", part="snippet,contentDetails,statistics,liveStreamingDetails", id=",".join(ids[i:i + 50]))
        for it in d.get("items", []):
            sn, st, cd = it.get("snippet", {}), it.get("statistics", {}), it.get("contentDetails", {})
            out[it["id"]] = {
                "titulo": sn.get("title"), "descripcion": (sn.get("description") or "")[:2500],
                "publicado": sn.get("publishedAt"), "canal": sn.get("channelTitle"), "canal_id": sn.get("channelId"),
                "duracion_s": _iso8601_a_s(cd.get("duration")),
                "vistas": int(st["viewCount"]) if st.get("viewCount") is not None else None,
                "es_directo": bool(it.get("liveStreamingDetails")) or sn.get("liveBroadcastContent") in ("live", "upcoming"),
                "palabras_clave": sn.get("tags"), "consulta": fechas.iso(fechas.ahora())}
    return out
