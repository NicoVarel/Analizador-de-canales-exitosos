"""Análisis visual de un video LOCAL (aportado/autorizado por el alumno) con ffmpeg (opcional).

Entrega: cambios de plano detectados (aproximado), duración media de plano, y una MUESTRA de fotogramas
(cada uno con su timestamp). Nunca afirma haber visto todos los fotogramas.
"""
import os, re, json, shutil, subprocess

from . import fechas
from .prov_publico import slug


def disponible():
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def analizar(archivo, salida, n=12, umbral=0.3, video_id=None):
    if not disponible():
        return {"estado": "ffmpeg_no_disponible", "nivel_de_acceso": "ninguno",
                "detalle": "ffmpeg/ffprobe no están instalados (opcional). Sin ellos no hay análisis de fotogramas."}
    if not os.path.isfile(archivo):
        return {"estado": "archivo_no_existe", "nivel_de_acceso": "ninguno"}
    nombre = slug(video_id or os.path.splitext(os.path.basename(archivo))[0])
    carpeta = os.path.join(salida, "frames", nombre)
    os.makedirs(carpeta, exist_ok=True)
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,r_frame_rate",
                         "-of", "json", archivo], capture_output=True, text=True)
    try:
        info = json.loads(pr.stdout)
        dur = float(info["format"]["duration"])
        vs = [s for s in info.get("streams", []) if s.get("width")]
        res = "%sx%s" % (vs[0]["width"], vs[0]["height"]) if vs else None
    except Exception:
        dur, res = 0.0, None
    sc = subprocess.run(["ffmpeg", "-i", archivo, "-vf", "select='gt(scene,%s)',showinfo" % umbral, "-f", "null", "-"],
                        capture_output=True, text=True, errors="replace")
    tiempos = [float(x) for x in re.findall(r"pts_time:([\d.]+)", sc.stderr)]
    n = max(2, n)
    marcas = sorted(set(round((dur / n) * (i + 0.5), 2) for i in range(n))) if dur else []
    # añade el primer instante (gancho) para poder describir la apertura
    if dur and 0.5 not in marcas:
        marcas = [0.5] + marcas
    guardados = []
    for t in marcas:
        ruta = os.path.join(carpeta, "frame_%07.2fs.jpg" % t)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", archivo, "-frames:v", "1",
                        "-vf", "scale=640:-2", ruta], capture_output=True)
        if os.path.exists(ruta):
            guardados.append({"t_s": t, "archivo": ruta})
    planos = len(tiempos) + 1 if dur else None
    res_d = {"estado": "ok", "archivo": os.path.basename(archivo), "duracion_s": round(dur, 2), "resolucion": res,
             "umbral_escena": umbral, "cambios_de_plano_detectados": len(tiempos), "tiempos_cambio_s": tiempos[:400],
             "duracion_media_plano_s_aprox": round(dur / planos, 2) if planos else None,
             "cortes_por_minuto": round(len(tiempos) / (dur / 60.0), 2) if dur else None,
             "fotogramas_guardados": guardados, "n_fotogramas_muestra": len(guardados),
             "nivel_de_acceso": "muestra_de_fotogramas", "consulta": fechas.iso(fechas.ahora()),
             "nota": "Detección automática aproximada de cortes DUROS (no detecta bien fundidos). Solo se inspecciona "
                     "una MUESTRA de fotogramas: no afirmar que se vieron todos."}
    with open(os.path.join(carpeta, "frames.json"), "w", encoding="utf-8") as f:
        json.dump(res_d, f, ensure_ascii=False, indent=1)
    res_d["carpeta"] = carpeta
    return res_d
