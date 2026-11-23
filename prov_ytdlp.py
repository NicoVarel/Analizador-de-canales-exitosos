"""Proveedor C: yt-dlp (OPCIONAL). Solo metadatos públicos y subtítulos. Nunca descarga videos aquí.

- Se comprueba que esté instalado; NUNCA se instala ni se actualiza automáticamente.
- Se invoca sin shell, con lista de argumentos, y con timeouts.
- Si el proveedor falla repetidamente (disyuntor de net.py), el motor lo deja de usar.
"""
import os, re, json, shutil, subprocess, time
from datetime import datetime, timezone

from . import net, fechas


def disponible():
    if "ytdlp" in net.fallos_simulados():
        return None
    return shutil.which("yt-dlp")


def version():
    exe = disponible()
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except Exception:
        return None


def antiguedad_dias():
    v = version()
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", v or "")
    if not m:
        return None
    d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
    return (fechas.ahora() - d).days


def _run(args, timeout):
    exe = disponible()
    if not exe:
        raise net.ErrorFuente("yt-dlp no está instalado")
    if net.proveedor_cortado("ytdlp"):
        raise net.ErrorFuente("yt-dlp cortado tras fallos repetidos")
    try:
        r = subprocess.run([exe] + args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        net.marcar("ytdlp", False, "timeout")
        raise net.ErrorFuente("yt-dlp: tiempo agotado")
    return r


def listar(url_tab, fin=100, timeout=150):
    """Lista plana de una pestaña (videos|shorts|streams): id, título, duración, vistas, estado de directo.
    NO trae fechas (la lista plana no las incluye): se completan con la página del video o la API."""
    r = _run(["--flat-playlist", "-J", "--playlist-end", str(fin), "--no-warnings", url_tab], timeout)
    if r.returncode != 0 and not r.stdout.strip():
        net.marcar("ytdlp", False, (r.stderr or "")[-200:])
        raise net.ErrorFuente("yt-dlp no pudo listar: %s" % (r.stderr or "")[-160:])
    try:
        d = json.loads(r.stdout)
    except Exception:
        net.marcar("ytdlp", False, "json inválido")
        raise net.ErrorFuente("yt-dlp devolvió JSON inválido")
    if not isinstance(d, dict):
        net.marcar("ytdlp", False, "sin datos (¿sin red?)")
        raise net.ErrorFuente("yt-dlp no devolvió datos (posible falta de red)")
    net.marcar("ytdlp", True)
    out = []
    for e in d.get("entries") or []:
        if not e or not e.get("id"):
            continue
        out.append({"id": e["id"], "titulo": e.get("title"), "duracion_s": e.get("duration"),
                    "vistas": e.get("view_count"), "live_status": e.get("live_status")})
    return {"canal_id": d.get("channel_id") or d.get("uploader_id"), "suscriptores": d.get("channel_follower_count"),
            "titulo": d.get("title"), "entradas": out}


def video_json(vid, timeout=90):
    """Metadatos públicos de UN video vía yt-dlp (respaldo cuando falla la página del video). Lento: usar con tope."""
    r = _run(["-J", "--skip-download", "--no-playlist", "--no-warnings", "https://www.youtube.com/watch?v=" + vid], timeout)
    try:
        d = json.loads(r.stdout)
    except Exception:
        net.marcar("ytdlp", False, "json inválido")
        raise net.ErrorFuente("yt-dlp sin datos para %s" % vid)
    if not isinstance(d, dict):
        net.marcar("ytdlp", False, "sin datos")
        raise net.ErrorFuente("yt-dlp sin datos para %s" % vid)
    net.marcar("ytdlp", True)
    ts = d.get("timestamp") or d.get("release_timestamp")
    pub = None
    if ts:
        pub = fechas.iso(datetime.fromtimestamp(ts, tz=timezone.utc))
        precision = "exacta"
    elif d.get("upload_date"):
        pub = fechas.parse_iso(d["upload_date"])
        pub = fechas.iso(pub) if pub else None
        precision = "exacta"  # fecha (día) exacta, sin hora
    else:
        precision = None
    return {"id": vid, "titulo": d.get("title"), "publicado": pub, "publicado_precision": precision,
            "vistas": d.get("view_count"), "duracion_s": d.get("duration"), "descripcion": (d.get("description") or "")[:2500],
            "es_directo": bool(d.get("was_live") or d.get("is_live")), "canal": d.get("channel"),
            "canal_id": d.get("channel_id"), "consulta": fechas.iso(fechas.ahora())}


def _vtt_a_segmentos(texto):
    import html as _h
    segs, ultimo, t = [], None, 0.0
    for ln in texto.splitlines():
        ln = ln.strip()
        m = re.match(r"(\d+):(\d+):(\d+)\.(\d+) -->", ln)
        if m:
            t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) + int(m.group(4)) / 1000.0
            continue
        if not ln or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or "-->" in ln:
            continue
        ln = _h.unescape(re.sub(r"<[^>]+>", "", ln)).strip()
        if ln and ln != ultimo:
            segs.append((round(t, 1), ln))
            ultimo = ln
    return segs


def subtitulos(vid, carpeta, pistas=None, preferencia=("es", "en"), intentos=3):
    """Obtiene subtítulos de UNA pista concreta (idioma original primero). Devuelve dict o lanza ErrorFuente.
    pistas: lista de {'idioma','automatica'} leída de la página del video (evita pedir traducciones → 429)."""
    os.makedirs(carpeta, exist_ok=True)
    cand = []
    if pistas:
        pref = {p: i for i, p in enumerate(preferencia)}
        # la pista automática (asr) está en el idioma HABLADO del video: ese es el original; las demás pueden ser traducciones
        hablado = next(((p["idioma"] or "")[:2] for p in pistas if p.get("automatica")), None)
        orden = sorted(pistas, key=lambda p: (hablado is not None and (p["idioma"] or "")[:2] != hablado,
                                              p.get("automatica", False), pref.get((p["idioma"] or "")[:2], 99)))
        for p in orden:
            code = p["idioma"]
            cand.append((code if not p.get("automatica") else code + "-orig", bool(p.get("automatica")), code))
        # manual primero dentro del mismo idioma ya está ordenado por 'automatica'
    else:
        cand = [(c, c.endswith("-orig"), c.replace("-orig", "")) for c in ("es", "es-orig", "en", "en-orig")]
    ultimo_error = "sin intentos"
    for code, auto, idioma in cand[:3]:
        for n in range(intentos):
            prefijo = os.path.join(carpeta, "_tmp_" + vid)
            for f in os.listdir(carpeta):
                if f.startswith("_tmp_" + vid):
                    try:
                        os.remove(os.path.join(carpeta, f))
                    except OSError:
                        pass
            args = ["--skip-download", "--write-auto-subs" if auto else "--write-subs", "--sub-langs", code,
                    "--sub-format", "vtt", "--no-playlist", "--no-warnings", "--sleep-requests", "1",
                    "-o", prefijo, "https://www.youtube.com/watch?v=" + vid]
            r = _run(args, 120)
            vtts = [f for f in os.listdir(carpeta) if f.startswith("_tmp_" + vid) and f.endswith(".vtt")]
            if vtts:
                txt = open(os.path.join(carpeta, vtts[0]), encoding="utf-8", errors="replace").read()
                for f in vtts:
                    try:
                        os.remove(os.path.join(carpeta, f))
                    except OSError:
                        pass
                segs = _vtt_a_segmentos(txt)
                if segs:
                    net.marcar("ytdlp", True)
                    return {"segmentos": segs, "idioma": idioma, "automatica": auto, "metodo": "yt-dlp"}
                ultimo_error = "subtítulo descargado pero vacío (%s)" % code
                break
            err = (r.stderr or "")
            ultimo_error = ("bloqueo anti-bot de YouTube (pide iniciar sesión): NO se elude; se continúa sin este recurso"
                            if ("confirm you" in err or "cookies" in err.lower()) else
                            "HTTP 429 (límite de peticiones)" if "429" in err else
                            "sin subtítulos para %s" % code if "no subtitles" in err.lower() or not err else err[-120:])
            if "429" in err and n < intentos - 1:
                time.sleep(6 * (n + 1))
                continue
            break
    net.marcar("ytdlp", False, ultimo_error)
    raise net.ErrorFuente(ultimo_error)
