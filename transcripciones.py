"""Transcripciones por niveles, con registro de calidad. Una transcripción vacía NUNCA cuenta como éxito.

Diagnóstico real (comprobado): la URL directa de subtítulos que aparece en la página del video devuelve
HTTP 200 con 0 bytes a un cliente HTTP simple, aunque las pistas EXISTAN. No se intenta eludir: se usa
yt-dlp (opcional) o el texto que aporte el alumno.

NIVEL 1  subtítulos públicos del video (yt-dlp, idioma ORIGINAL de la pista; manual antes que automático)
NIVEL 2  variantes de idioma si el pedido no existe (se declara el idioma real obtenido)
NIVEL 3  transcripción local de un archivo de audio/video aportado por el alumno (herramienta opcional)
NIVEL 4  sin transcripción: el análisis se limita a lo existente; no se inventa ninguna palabra ni timestamp
"""
import os, re, json, shutil, subprocess, importlib.util

from . import net, fechas, prov_ytdlp


def _validar(segs, dur_s, automatica):
    palabras = sum(len(t.split()) for _, t in segs)
    cobertura = None
    if segs and dur_s:
        cobertura = round(min(1.0, segs[-1][0] / float(dur_s)), 2)
    texto = " ".join(t for _, t in segs).lower()
    ruido = len(re.findall(r"\[(music|applause|laughter|música|aplausos)\]|>>", texto))
    errores = []
    if automatica:
        errores.append("subtítulo automático: posibles errores de reconocimiento, nombres propios y cifras")
    if ruido:
        errores.append("%d marcas de ruido/cambio de hablante ([music], >>)" % ruido)
    if cobertura is not None and cobertura < 0.6:
        errores.append("cobertura baja (%.0f%% de la duración)" % (cobertura * 100))
    if palabras < 15:
        return None, "rechazada_muy_corta", palabras, cobertura, errores
    if cobertura is not None and cobertura >= 0.8 and not automatica:
        conf = "alta"
    elif cobertura is None or cobertura >= 0.6:
        conf = "media"
    else:
        conf = "baja"
    return conf, "ok", palabras, cobertura, errores


def _guardar(vid, carpeta, meta, segs):
    os.makedirs(carpeta, exist_ok=True)
    txt = os.path.join(carpeta, "%s.txt" % vid)
    with open(txt, "w", encoding="utf-8") as f:
        f.write("# video=%s idioma=%s metodo=%s automatica=%s confianza=%s\n" % (
            vid, meta.get("idioma"), meta.get("metodo"), meta.get("automatica"), meta.get("confianza")))
        for s, t in segs:
            f.write("[%02d:%02d] %s\n" % (int(s) // 60, int(s) % 60, t))
    meta = dict(meta)
    meta["archivo_texto"] = txt
    with open(os.path.join(carpeta, "%s.json" % vid), "w", encoding="utf-8") as f:
        json.dump(dict(meta, segmentos=[{"t": s, "texto": t} for s, t in segs]), f, ensure_ascii=False)
    return meta


def obtener(vid, carpeta, pistas=None, dur_s=None, preferencia=("es", "en")):
    """Devuelve SIEMPRE un dict de estado (nunca lanza): exito/fracaso con motivo claro."""
    base = {"video_id": vid, "consulta": fechas.iso(fechas.ahora()), "pistas_disponibles": pistas or [],
            "idioma_solicitado": list(preferencia)}
    if pistas is not None and len(pistas) == 0:
        return dict(base, estado="sin_subtitulos", metodo="pagina_video", nivel=4,
                    detalle="El video no publica pistas de subtítulos; no hay texto que analizar.",
                    con_timestamps=False, confianza="ninguna")
    if not prov_ytdlp.disponible():
        return dict(base, estado="pistas_existen_sin_herramienta" if pistas else "sin_herramienta", nivel=4,
                    metodo=None, con_timestamps=False, confianza="ninguna",
                    detalle=("Hay subtítulos pero YouTube no los entrega a un cliente HTTP simple. Opciones: instalar yt-dlp "
                             "(con tu permiso) o pegar la transcripción."))
    try:
        r = prov_ytdlp.subtitulos(vid, carpeta, pistas, preferencia)
    except net.ErrorFuente as e:
        return dict(base, estado="fallo_extraccion", metodo="yt-dlp", nivel=4, con_timestamps=False,
                    confianza="ninguna", detalle=str(e)[:200])
    conf, estado, palabras, cobertura, errores = _validar(r["segmentos"], dur_s, r["automatica"])
    if estado != "ok":
        return dict(base, estado=estado, metodo="yt-dlp", nivel=1, con_timestamps=True, confianza="ninguna",
                    palabras=palabras, errores_posibles=errores, detalle="Texto demasiado corto: no se acepta como transcripción.")
    nivel = 1 if (r["idioma"] or "")[:2] in [p[:2] for p in preferencia[:1]] else 2
    hablado = next(((p.get("idioma") or "")[:2] for p in (pistas or []) if p.get("automatica")), None)
    traduccion = bool(hablado and (r["idioma"] or "")[:2] != hablado)
    errores = errores + (["la pista obtenida (%s) no es el idioma hablado (%s): puede ser una traducción" % (r["idioma"], hablado)] if traduccion else [])
    meta = {**base, "estado": "ok", "nivel": nivel, "idioma_hablado": hablado, "es_traduccion": traduccion, "metodo": r["metodo"], "idioma": r["idioma"],
            "automatica": r["automatica"], "con_timestamps": True, "palabras": palabras,
            "cobertura": cobertura, "primer_segmento_s": r["segmentos"][0][0], "ultimo_segmento_s": r["segmentos"][-1][0],
            "duracion_video_s": dur_s, "errores_posibles": errores, "confianza": conf}
    return _guardar(vid, carpeta, meta, r["segmentos"])


def _modelo_en_cache(nombre):
    return os.path.exists(os.path.join(os.path.expanduser("~"), ".cache", "whisper", nombre + ".pt"))


def local(archivo, carpeta, vid="local", idioma=None, modelo="base", permitir_descarga=False):
    """Nivel 3: transcribe un archivo de audio/video que el alumno aporta (suyo o legalmente descargado).
    Requiere una herramienta OPCIONAL ya instalada (faster-whisper u openai-whisper). Nunca descarga modelos sin permiso."""
    if not os.path.isfile(archivo):
        return {"estado": "archivo_no_existe", "nivel": 4}
    segs, dur, metodo, idi = None, None, None, idioma
    if importlib.util.find_spec("faster_whisper"):
        from faster_whisper import WhisperModel
        m = WhisperModel(modelo, device="cpu", compute_type="int8")
        it, info = m.transcribe(archivo, language=idioma)
        segs = [(round(s.start, 1), s.text.strip()) for s in it if s.text.strip()]
        dur, metodo, idi = getattr(info, "duration", None), "faster-whisper (local, modelo %s)" % modelo, getattr(info, "language", idioma)
    elif importlib.util.find_spec("whisper"):
        if not _modelo_en_cache(modelo) and not permitir_descarga:
            return {"estado": "modelo_no_descargado", "nivel": 4, "con_timestamps": False, "confianza": "ninguna",
                    "detalle": ("El modelo '%s' no está en la caché local y descargarlo requiere permiso del alumno "
                                "(usa --permitir-descarga si lo autoriza)." % modelo)}
        import whisper
        m = whisper.load_model(modelo)
        r = m.transcribe(archivo, language=idioma, fp16=False)
        segs = [(round(x["start"], 1), x["text"].strip()) for x in r.get("segments", []) if x["text"].strip()]
        dur = r["segments"][-1]["end"] if r.get("segments") else None
        metodo, idi = "openai-whisper (local, modelo %s)" % modelo, r.get("language", idioma)
    else:
        return {"estado": "herramienta_no_disponible", "nivel": 4, "con_timestamps": False, "confianza": "ninguna",
                "detalle": ("Para transcribir localmente hace falta una herramienta opcional (faster-whisper u openai-whisper). "
                            "No se instala sin tu permiso. Alternativa: pega la transcripción.")}
    conf, estado, palabras, cob, errores = _validar(segs, dur, True)
    meta = {"video_id": vid, "estado": estado, "nivel": 3, "metodo": metodo, "idioma": idi, "automatica": True,
            "con_timestamps": True, "palabras": palabras, "cobertura": cob,
            "errores_posibles": errores + ["reconocimiento automático local: revisar nombres y cifras"],
            "confianza": conf or "ninguna", "consulta": fechas.iso(fechas.ahora())}
    return _guardar(vid, carpeta, meta, segs) if estado == "ok" else meta
