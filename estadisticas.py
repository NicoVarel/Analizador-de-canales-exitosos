"""Estadísticas calculadas EXCLUSIVAMENTE desde los registros recopilados (nunca a mano).

Mantiene el sistema de v1.0 (mediana comparable, ratio con mediana que excluye al propio video, outliers >=5x,
confianza por tamaño de muestra, largos y Shorts separados, directos excluidos) y añade: comparación con
videos de antigüedad semejante, recientes vs antiguos, frecuencia, duración habitual y patrones repetidos.
"""
import re, statistics, math

from . import fechas


def conf(n):
    return "alta" if n >= 15 else "media" if n >= 8 else "baja" if n >= 3 else "ninguna"


def _clave_orden(v):
    e = v.get("edad_dias")
    return (e is None, e if e is not None else v.get("orden_lista", 9999))


def muestra(videos, formato, tope):
    m = [v for v in videos if v.get("formato") == formato and v.get("vistas") is not None and not v.get("es_directo")]
    m.sort(key=_clave_orden)
    return m[:tope]


def _med(xs):
    return statistics.median(xs) if xs else None


def _vecinos_por_edad(v, pool, k=6):
    """Videos de antigüedad semejante (los k más cercanos en edad), excluyendo al propio. Exige edad conocida."""
    if v.get("edad_dias") is None:
        return []
    cands = [o for o in pool if o["id"] != v["id"] and o.get("edad_dias") is not None]
    cands.sort(key=lambda o: abs(math.log1p(o["edad_dias"]) - math.log1p(v["edad_dias"])))
    return cands[:k]


def estadisticas(videos, formato, tope):
    m = muestra(videos, formato, tope)
    n = len(m)
    res = {"formato": formato, "n_muestra": n, "tope": tope, "confianza": conf(n)}
    if n < 3:
        res["nota"] = "Muestra insuficiente: no se calculan medianas ni outliers."
        res["confianza"] = "ninguna"
        return res
    vs = [v["vistas"] for v in m]
    res.update({"mediana_vistas": _med(vs), "media_vistas": round(statistics.mean(vs)), "max_vistas": max(vs),
                "min_vistas": min(vs), "n_vistas_exactas": sum(1 for v in m if v.get("vistas_precision") == "exacto")})
    filas = []
    for v in m:
        med = _med([x["vistas"] for x in m if x["id"] != v["id"]])
        ratio = round(v["vistas"] / med, 2) if med else None
        vec = _vecinos_por_edad(v, m)
        r_edad = None
        if len(vec) >= 4:
            md = _med([x["vistas"] for x in vec])
            r_edad = round(v["vistas"] / md, 2) if md else None
        filas.append({
            "id": v["id"], "titulo": v.get("titulo"), "vistas": v["vistas"], "ratio_vs_mediana": ratio,
            "ratio_edad_similar": r_edad, "edad_dias": v.get("edad_dias"), "edad_precision": v.get("edad_precision"),
            "duracion": v.get("duracion"),
            "senal": "outlier>=5x" if ratio and ratio >= 5 else "alto 2-5x" if ratio and ratio >= 2 else
                     "bajo <0.5x" if ratio is not None and ratio < 0.5 else "habitual"})
    for f in filas:
        f["senal_fiable"] = n >= 8
    res["outliers_fiables"] = n >= 8
    if n < 8:
        res["aviso_muestra_pequena"] = ("Muestra de %d videos: las señales de outlier NO son concluyentes y no permiten hablar de patrones." % n)
    res["videos"] = filas
    res["n_outliers_5x"] = sum(1 for f in filas if f["senal"] == "outlier>=5x")
    desconocidas = sum(1 for v in m if v.get("edad_dias") is None)
    res["n_edad_desconocida"] = desconocidas
    if desconocidas:
        res["nota_edad"] = ("%d videos de la muestra no tienen fecha: se ordenan por posición en la lista y no se "
                            "pueden comparar por antigüedad." % desconocidas)
    res["advertencia"] = ("Las vistas dependen de la antigüedad: videos recientes tienen menos vistas acumuladas. "
                          "Un ratio no prueba causalidad.")
    return res


# ---------- extendidas ----------
def _features(titulo, dur_s):
    t = titulo or ""
    f = {}
    f["titulo_con_numero"] = bool(re.search(r"\d", t))
    f["titulo_pregunta"] = ("?" in t) or bool(re.match(r"^(why|how|what|when|who|is|are|can|does|do|por qu|c[oó]mo|qu[eé]|cu[aá]l)\b", t.lower()))
    f["titulo_largo_>60"] = len(t) > 60
    f["titulo_con_puntos_susp"] = ("..." in t) or ("…" in t)
    f["titulo_con_dos_puntos_o_guion"] = (":" in t) or (" - " in t) or (" — " in t)
    if dur_s:
        f["duracion_>=30min"] = dur_s >= 1800
        f["duracion_<15min"] = dur_s < 900
    return f


def extendidas(videos, formato, tope=100):
    m = muestra(videos, formato, tope)
    n = len(m)
    out = {"formato": formato, "n_muestra": n, "confianza": conf(n)}
    if n < 3:
        out["nota"] = "Muestra insuficiente para estadísticas extendidas."
        return out
    base = estadisticas(videos, formato, tope)
    rat = {f["id"]: f["ratio_vs_mediana"] for f in base["videos"]}
    out["mediana_vistas"] = base["mediana_vistas"]
    out["media_vistas"] = base["media_vistas"]
    out["n_outliers_5x"] = base["n_outliers_5x"]
    out["n_alto_2_5x"] = sum(1 for f in base["videos"] if f["senal"] == "alto 2-5x")
    out["n_bajo_<0.5x"] = sum(1 for f in base["videos"] if f["senal"] == "bajo <0.5x")
    out["n_con_fecha_exacta"] = sum(1 for v in m if v.get("publicado_precision") == "exacta")
    # duración habitual
    ds = [v["duracion_s"] for v in m if v.get("duracion_s")]
    if ds:
        out["duracion_mediana_s"] = _med(ds)
        out["duracion_mediana"] = fechas.s_a_dur(_med(ds))
        out["duracion_min_max"] = [fechas.s_a_dur(min(ds)), fechas.s_a_dur(max(ds))]
    # recientes vs antiguos (solo con fechas)
    fechados = [v for v in m if v.get("edad_dias") is not None]
    if len(fechados) >= 10:
        fechados.sort(key=lambda v: v["edad_dias"])
        mitad = len(fechados) // 2
        rec, ant = fechados[:mitad], fechados[mitad:]
        mr, ma = _med([v["vistas"] for v in rec]), _med([v["vistas"] for v in ant])
        out["recientes_vs_antiguos"] = {
            "n_recientes": len(rec), "n_antiguos": len(ant), "mediana_recientes": mr, "mediana_antiguos": ma,
            "cociente": round(mr / ma, 2) if ma else None,
            "edad_corte_dias": round(ant[0]["edad_dias"], 1),
            "aviso": "Los recientes aún acumulan vistas: un cociente <1 NO indica por sí mismo pérdida de interés."}
    else:
        out["recientes_vs_antiguos"] = {"nota": "Menos de 10 videos con fecha: no se compara."}
    # frecuencia (fechas exactas)
    ex = sorted([fechas.parse_iso(v["publicado"]) for v in m if v.get("publicado_precision") == "exacta" and v.get("publicado")])
    if len(ex) >= 4:
        gaps = [(b - a).total_seconds() / 86400.0 for a, b in zip(ex, ex[1:])]
        span = (ex[-1] - ex[0]).total_seconds() / 86400.0
        out["frecuencia"] = {"videos_con_fecha_exacta": len(ex), "dias_cubiertos": round(span, 1),
                             "videos_por_semana": round((len(ex) - 1) / span * 7, 2) if span > 0 else None,
                             "mediana_dias_entre_publicaciones": round(_med(gaps), 2),
                             "ultimo_publicado": fechas.iso(ex[-1])}
        ahora_ = fechas.ahora()
        for dias in (90, 365):
            k = sum(1 for d in ex if (ahora_ - d).days <= dias)
            out["frecuencia"]["ultimos_%d_dias" % dias] = {"publicaciones": k, "por_semana": round(k / (dias / 7.0), 2),
                                                           "cobertura_completa": (ahora_ - ex[0]).days >= dias}
    else:
        out["frecuencia"] = {"nota": "Menos de 4 fechas exactas: no se calcula frecuencia."}
    # patrones repetidos: comparación de ratios dentro vs fuera del grupo
    feats = {v["id"]: _features(v.get("titulo"), v.get("duracion_s")) for v in m}
    nombres = sorted({k for f in feats.values() for k in f})
    pats = []
    for nm in nombres:
        g = [rat[i] for i, f in feats.items() if f.get(nm) is True and rat.get(i) is not None]
        r = [rat[i] for i, f in feats.items() if f.get(nm) is False and rat.get(i) is not None]
        if not g or not r:
            continue
        mg, mr_ = _med(g), _med(r)
        suficiente = len(g) >= 5 and len(r) >= 5
        pats.append({"rasgo": nm, "n_con": len(g), "n_sin": len(r), "mediana_ratio_con": round(mg, 2),
                     "mediana_ratio_sin": round(mr_, 2), "diferencia": round(mg - mr_, 2),
                     "estado": ("diferencia_notable_(correlacion)" if suficiente and abs(mg - mr_) >= 0.3
                                else "sin_diferencia_clara" if suficiente else "hipotesis_(n<5)")})
    out["patrones_repetidos"] = sorted(pats, key=lambda p: -abs(p["diferencia"]))
    out["nota_patrones"] = ("Son correlaciones entre rasgos del título/duración y vistas relativas; no prueban causalidad "
                            "(influyen tema, antigüedad, miniatura, fama del canal y recomendación).")
    return out


# ---------- selección de videos para análisis profundo ----------
def seleccionar(videos, formato, n=8):
    m = muestra(videos, formato, 100)
    if len(m) < 3:
        return []
    base = estadisticas(videos, formato, 100)
    filas = {f["id"]: f for f in base["videos"]}
    por_id = {v["id"]: v for v in m}
    elegidos, razones = [], {}

    def tomar(ids, razon, k):
        c = 0
        for i in ids:
            if i not in razones and c < k:
                razones[i] = razon
                elegidos.append(i)
                c += 1
    def clave(i):
        f = filas[i]
        return f["ratio_edad_similar"] if f["ratio_edad_similar"] is not None else (f["ratio_vs_mediana"] or 0)
    orden_desc = sorted(filas, key=clave, reverse=True)
    tomar(orden_desc, "mejor rendimiento relativo", max(1, round(n * 0.375)))
    habituales = sorted(filas, key=lambda i: abs((filas[i]["ratio_vs_mediana"] or 1) - 1))
    tomar(habituales, "rendimiento habitual", max(1, round(n * 0.25)))
    maduros = [i for i in sorted(filas, key=clave) if (por_id[i].get("edad_dias") or 0) >= 30]
    tomar(maduros, "bajo rendimiento (con ≥30 días, no por ser reciente)", max(1, round(n * 0.125)))
    recientes = sorted(por_id, key=lambda i: por_id[i].get("edad_dias") if por_id[i].get("edad_dias") is not None else 9e9)
    tomar(recientes, "reciente", max(1, round(n * 0.125)))
    tomar([i for i in orden_desc], "representativo del formato", n - len(elegidos))
    return [{"id": i, "titulo": por_id[i].get("titulo"), "formato": formato, "motivo": razones[i],
             "vistas": por_id[i]["vistas"], "ratio_vs_mediana": filas[i]["ratio_vs_mediana"],
             "ratio_edad_similar": filas[i]["ratio_edad_similar"], "url": por_id[i].get("url")} for i in elegidos[:n]]
