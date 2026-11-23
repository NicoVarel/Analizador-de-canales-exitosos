"""Normalización de fechas y números.

Tres fechas distintas que NUNCA se mezclan:
  - fecha de CREACIÓN DEL CANAL  (canal.creado_iso, fuente declarada)
  - fecha de PUBLICACIÓN del video (video.publicado + publicado_precision)
  - fecha de CONSULTA de las estadísticas (consulta_iso)
Una fecha aproximada (a partir de "hace 3 años") se guarda como aproximada, con su rango, y jamás
se convierte en exacta.
"""
import re
from datetime import datetime, timezone, timedelta

_UNIDADES = {"second": 0.0, "minute": 0.0007, "hour": 0.0417, "day": 1.0, "week": 7.0, "month": 30.4375, "year": 365.25}
_ABREV = {"mo": "month", "m": "minute", "min": "minute", "s": "second", "sec": "second", "h": "hour",
          "hr": "hour", "d": "day", "w": "week", "y": "year", "yr": "year"}


def ahora():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    """Acepta '2026-11-12T09:27:13-08:00', '...Z', '2026-11-12'. Devuelve datetime UTC o None."""
    if not s:
        return None
    try:
        s = s.strip().replace("Z", "+00:00")
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s or "")
        if m:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
        return None


def relativa_a_rango(txt, ref=None):
    """'3 years ago' / '4d ago' / 'Streamed 2 weeks ago' -> (centro_iso, dias_min, dias_max) o None.
    El intervalo refleja que 'hace 3 años' significa entre 3 y <4 años."""
    if not txt:
        return None
    m = re.search(r"(\d+)\s*(seconds?|minutes?|hours?|days?|weeks?|months?|years?|mo|min|sec|yr|hr|s|m|h|d|w|y)\s+ago",
                  txt.lower())
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2)
    clave = _ABREV.get(u, u.rstrip("s"))
    paso = _UNIDADES[clave]
    dmin, dmax = n * paso, (n + 1) * paso
    ref = ref or ahora()
    centro = ref - timedelta(days=(dmin + dmax) / 2.0)
    return iso(centro), round(dmin, 2), round(dmax, 2)


def edad_dias(publicado_iso, ref=None):
    d = parse_iso(publicado_iso)
    if not d:
        return None
    return round(((ref or ahora()) - d).total_seconds() / 86400.0, 2)


def parse_views(txt):
    """'1.2M views' -> (1200000, 'aprox'); '1,234 views' -> (1234, 'exacto'); '16 million views' -> aprox."""
    if not txt:
        return None, None
    t = txt.lower().replace("\xa0", " ").strip()
    if t.startswith("no views") or t.startswith("sin visualizaciones"):
        return 0, "exacto"
    m = re.search(r"([\d][\d.,]*)\s*(k|m|b|thousand|million|billion|mil|millones)?\b", t)
    if not m:
        return None, None
    num, suf = m.group(1), m.group(2)
    if suf:
        v = float(num.replace(",", ".")) if ("," in num and "." not in num) else float(num.replace(",", ""))
        mult = {"k": 1e3, "thousand": 1e3, "mil": 1e3, "m": 1e6, "million": 1e6, "millones": 1e6,
                "b": 1e9, "billion": 1e9}[suf]
        return int(round(v * mult)), "aprox"
    return int(re.sub(r"[.,]", "", num)), "exacto"


def dur_a_s(txt):
    if txt is None:
        return None
    if isinstance(txt, (int, float)):
        return int(txt)
    p = [int(x) for x in re.findall(r"\d+", str(txt))]
    if not p:
        return None
    s = 0
    for x in p:
        s = s * 60 + x
    return s


def s_a_dur(s):
    if s is None:
        return None
    s = int(s)
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return "%d:%02d:%02d" % (h, m, sec) if h else "%d:%02d" % (m, sec)
