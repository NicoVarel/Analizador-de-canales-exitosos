"""Miniaturas: descarga pública, validación (no vacía, no corrupta, no marcador de 'sin miniatura') y vínculo video↔imagen.

El script NO "analiza" la imagen: deja archivos válidos y un índice. Quien las inspecciona es Claude con la
herramienta Read (visión). Una miniatura solo cuenta como INSPECCIONADA cuando se registra una observación
(`registrar miniatura <id> --texto ...`).
"""
import os, json, struct
from concurrent.futures import ThreadPoolExecutor

from . import net, fechas

CALIDADES = ("maxresdefault", "sddefault", "hqdefault")


def _dim_jpeg(b):
    """Ancho y alto leyendo el marcador SOF del JPEG. None si no es un JPEG válido."""
    if len(b) < 4 or b[0:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        mk = b[i + 1]
        if mk in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        if mk in (0xD8, 0x01) or 0xD0 <= mk <= 0xD7:
            i += 2
            continue
        ln = struct.unpack(">H", b[i + 2:i + 4])[0]
        i += 2 + ln
    return None


def descargar(vid, carpeta, url_extra=None):
    os.makedirs(carpeta, exist_ok=True)
    urls = ([url_extra] if url_extra else []) + ["https://i.ytimg.com/vi/%s/%s.jpg" % (vid, q) for q in CALIDADES]
    errores = []
    for u in urls:
        try:
            data = net.get(u, prov="miniaturas", binary=True, retries=0, timeout=20)
        except net.ErrorFuente as e:
            errores.append(str(e)[:80])
            continue
        dim = _dim_jpeg(data)
        if not dim or len(data) < 5000 or dim[0] <= 120:
            errores.append("imagen inválida o marcador de 'sin miniatura' (%s bytes)" % len(data))
            continue
        nombre = "%s.jpg" % vid
        ruta = os.path.join(carpeta, nombre)
        with open(ruta, "wb") as f:
            f.write(data)
        return {"id": vid, "archivo": ruta, "url": u, "ancho": dim[0], "alto": dim[1], "bytes": len(data),
                "valida": True, "estado": "descargada_valida", "consulta": fechas.iso(fechas.ahora())}
    return {"id": vid, "archivo": None, "valida": False, "estado": "no_disponible", "errores": errores[:3]}


def lote(videos_sel, carpeta, hilos=4):
    """videos_sel: lista de dicts con 'id' (y opcional 'miniatura_url', 'titulo')."""
    def uno(v):
        r = descargar(v["id"], carpeta, v.get("miniatura_url"))
        r["titulo"] = v.get("titulo")
        return r
    with ThreadPoolExecutor(max_workers=max(1, min(hilos, 4))) as ex:
        res = list(ex.map(uno, videos_sel))
    idx = os.path.join(carpeta, "miniaturas_indice.json")
    with open(idx, "w", encoding="utf-8") as f:
        json.dump({"nota": "Para describir una miniatura, ábrela con Read. Registra lo observado con "
                           "`registrar miniatura <id> --texto ...`.", "miniaturas": res}, f, ensure_ascii=False, indent=1)
    return res
