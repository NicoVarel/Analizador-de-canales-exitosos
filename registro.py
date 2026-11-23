"""Registro único por video, fusión sin duplicados y resolución de discrepancias con procedencia.

Cada dato llega como un "candidato" (valor, fuente, precisión, fecha de consulta). `resolver` elige uno
con reglas explícitas y deja constancia de: de dónde salió (procedencia) y qué fuentes discreparon.
Fiabilidad de fuentes: api > watch (página del video) > rss > ytdlp > tab (pestañas) > manual.
"""
from . import fechas

FIABILIDAD = {"api": 5, "watch": 4, "rss": 3, "ytdlp": 2, "tab": 1, "orden": 1, "inferido": 0.5, "manual": 0}
PREC_RANGO = {"exacta": 2, "exacto": 2, "aproximada": 1, "aprox": 1, "desconocida": 0, None: 0}


def nuevo(vid):
    return {"id": vid, "url": None, "_cand": {}, "origen": [], "procedencia": {}, "discrepancias": []}


def aportar(rec, campo, valor, fuente, precision=None, consulta=None, extra=None):
    if valor is None or valor == "":
        return
    c = rec["_cand"].setdefault(campo, [])
    c.append({"valor": valor, "fuente": fuente, "precision": precision,
              "consulta": consulta or fechas.iso(fechas.ahora()), "extra": extra})
    if fuente not in rec["origen"]:
        rec["origen"].append(fuente)


def _ancho(c):
    ex = c.get("extra")
    if isinstance(ex, dict) and ex.get("rango_dias"):
        return ex["rango_dias"][1] - ex["rango_dias"][0]
    return 0


def _mejor(cands):
    # 1) precisión (exacta > aproximada); 2) entre aproximadas, el rango más estrecho; 3) fiabilidad; 4) más reciente
    return sorted(cands, key=lambda c: (PREC_RANGO.get(c["precision"], 0), -_ancho(c), FIABILIDAD.get(c["fuente"], 0),
                                       c["consulta"]), reverse=True)


def resolver(rec, ref=None):
    """Convierte candidatos en campos finales. Devuelve el mismo registro."""
    ref = ref or fechas.ahora()
    cand = rec["_cand"]
    rec["discrepancias"] = []
    # campos simples: se elige el mejor candidato
    for campo in ("titulo", "descripcion", "canal", "canal_id", "formato", "palabras_clave", "categoria",
                  "miniatura_url", "es_directo", "url"):
        if campo in cand:
            m = _mejor(cand[campo])[0]
            rec[campo] = m["valor"]
            rec["procedencia"][campo] = m["fuente"]
    # formato: 'directo' explícito (texto "Streamed") manda; si el video solo aparece en la pestaña de directos es un directo;
    # si además está en Videos/Shorts es un video normal con marca de directo/estreno (p. ej. premieres)
    if "formato" in cand:
        vals = {c["valor"] for c in cand["formato"]}
        normales = [c for c in cand["formato"] if c["valor"] in ("largo", "short")]
        if "directo" in vals:
            rec["formato"] = "directo"
        elif normales:
            rec["formato"] = _mejor(normales)[0]["valor"]
            if "en_pestana_directos" in vals:
                rec["marca_directo_o_estreno"] = True
            if {"largo", "short"} <= vals:
                rec["discrepancias"].append({"campo": "formato", "valores": sorted(vals), "elegido": rec["formato"],
                                             "motivo": "mayor fiabilidad de fuente"})
        elif "en_pestana_directos" in vals:
            rec["formato"] = "estreno_o_directo"  # solo aparece en la pestaña de directos: no se puede distinguir; se excluye de las estadísticas
        rec["procedencia"]["formato"] = _mejor(cand["formato"])[0]["fuente"]
    # duración
    if "duracion_s" in cand:
        m = _mejor(cand["duracion_s"])[0]
        rec["duracion_s"] = m["valor"]
        rec["duracion"] = fechas.s_a_dur(m["valor"])
        rec["procedencia"]["duracion_s"] = m["fuente"]
    # vistas
    if "vistas" in cand:
        ordenadas = _mejor(cand["vistas"])
        m = ordenadas[0]
        rec["vistas"] = m["valor"]
        rec["vistas_precision"] = "exacto" if PREC_RANGO.get(m["precision"]) == 2 else "aprox"
        rec["vistas_fuente"] = m["fuente"]
        rec["vistas_consulta"] = m["consulta"]
        rec["procedencia"]["vistas"] = m["fuente"]
        if m.get("extra"):
            rec["vistas_texto"] = m["extra"]
        otros = [c for c in ordenadas[1:] if c["valor"] is not None]
        for c in otros:
            base = max(m["valor"], 1)
            tol = 0.08 if (c["precision"] in ("aprox", "aproximada") or m["precision"] in ("aprox", "aproximada")) else 0.02
            if abs(c["valor"] - m["valor"]) / base > tol:
                rec["discrepancias"].append({
                    "campo": "vistas", "elegido": {"valor": m["valor"], "fuente": m["fuente"], "consulta": m["consulta"]},
                    "otro": {"valor": c["valor"], "fuente": c["fuente"], "consulta": c["consulta"]},
                    "motivo": "se prefiere la cifra exacta de la fuente más fiable y más reciente"})
    # publicación
    if "publicado" in cand:
        m = _mejor(cand["publicado"])[0]
        rec["publicado"] = m["valor"]
        rec["publicado_precision"] = "exacta" if PREC_RANGO.get(m["precision"]) == 2 else "aproximada"
        rec["publicado_fuente"] = m["fuente"]
        rec["procedencia"]["publicado"] = m["fuente"]
        if m["precision"] in ("aproximada", "aprox") and m.get("extra"):
            rec["publicado_rango_dias"] = m["extra"].get("rango_dias")
            rec["publicado_relativo"] = m["extra"].get("texto")
        for c in _mejor(cand["publicado"])[1:]:
            if PREC_RANGO.get(c["precision"]) == 2 and PREC_RANGO.get(m["precision"]) == 2:
                d1, d2 = fechas.parse_iso(c["valor"]), fechas.parse_iso(m["valor"])
                if d1 and d2 and abs((d1 - d2).total_seconds()) > 86400:
                    rec["discrepancias"].append({"campo": "publicado", "elegido": m["valor"], "otro": c["valor"],
                                                 "motivo": "dos fuentes exactas difieren > 1 día; se usa la más fiable"})
        rec["edad_dias"] = fechas.edad_dias(rec["publicado"], ref)
        rec["edad_precision"] = rec["publicado_precision"]
    else:
        rec["publicado"] = None
        rec["publicado_precision"] = "desconocida"
        rec["edad_dias"] = None
        rec["edad_precision"] = "desconocida"
    rec["fuente"] = rec["origen"][0] if rec["origen"] else None
    return rec


def confianza(rec):
    pts = 0
    if rec.get("vistas_precision") == "exacto":
        pts += 2
    elif rec.get("vistas") is not None:
        pts += 1
    if rec.get("publicado_precision") == "exacta":
        pts += 2
    elif rec.get("publicado_precision") == "aproximada":
        pts += 1
    if rec.get("duracion_s") is not None or rec.get("formato") == "short":
        pts += 1
    if rec.get("formato") in ("largo", "short", "directo"):
        pts += 1
    return "alta" if pts >= 5 else "media" if pts >= 3 else "baja"


def limpio(rec):
    """Versión serializable (sin candidatos internos) con confianza calculada."""
    r = {k: v for k, v in rec.items() if k != "_cand"}
    r["confianza"] = confianza(rec)
    return r
