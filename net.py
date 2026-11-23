"""Red: peticiones de SOLO LECTURA con reintentos limitados, timeouts, espaciado y disyuntor.

Reglas de diseño (seguridad):
- Solo GET a páginas públicas. Sin cookies de sesión del usuario (solo el aviso de consentimiento).
- Sin proxies rotativos ni técnicas de evasión. Si un proveedor falla repetidamente, se corta (disyuntor)
  y el motor cambia de estrategia.
- Cada llamada registra el proveedor, para el informe de cobertura.
"""
import os, re, time, threading, random
import urllib.request, urllib.error

UA = "Mozilla/5.0 (compatible; AnalizadorCanalesAcademy/1.1)"
HDRS = {"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9",
        "Cookie": "CONSENT=YES+1; SOCS=CAI"}  # solo el aviso de consentimiento; ninguna sesión

_lock = threading.Lock()
_ultimo = {}          # host -> última petición (espaciado)
_estado = {}          # proveedor -> contadores
UMBRAL_DISYUNTOR = 5  # fallos consecutivos para cortar un proveedor
UMBRALES = {"watch": 14}  # la página de video gestiona su propio enfriamiento ante 429


class ErrorFuente(RuntimeError):
    pass


def fallos_simulados():
    """Gancho de PRUEBAS: YT_ENGINE_FALLAR=publico_tabs,watch,rss,ytdlp,api"""
    return {x.strip() for x in os.environ.get("YT_ENGINE_FALLAR", "").split(",") if x.strip()}


def estado_proveedores():
    with _lock:
        return {k: dict(v) for k, v in _estado.items()}


def _reg(prov):
    with _lock:
        return _estado.setdefault(prov, {"intentos": 0, "ok": 0, "errores": 0, "consecutivos": 0,
                                         "ultimo_error": None, "cortado": False})


def proveedor_cortado(prov):
    return _reg(prov)["cortado"]


def marcar(prov, ok, error=None):
    with _lock:
        e = _estado.setdefault(prov, {"intentos": 0, "ok": 0, "errores": 0, "consecutivos": 0,
                                      "ultimo_error": None, "cortado": False})
        e["intentos"] += 1
        if ok:
            e["ok"] += 1
            e["consecutivos"] = 0
        else:
            e["errores"] += 1
            e["consecutivos"] += 1
            e["ultimo_error"] = str(error)[:200] if error else None
            if e["consecutivos"] >= UMBRALES.get(prov, UMBRAL_DISYUNTOR):
                e["cortado"] = True


def _espaciar(host, minimo):
    with _lock:
        t = time.time()
        prev = _ultimo.get(host, 0)
        espera = max(0.0, prev + minimo - t)
        _ultimo[host] = t + espera
    if espera:
        time.sleep(espera)


def get(url, prov="publico", binary=False, timeout=25, retries=2, espaciado=0.12, headers=None):
    """GET con reintentos limitados. Lanza ErrorFuente si no se logra. Respeta Retry-After (máx. 10 s)."""
    if prov in fallos_simulados():
        marcar(prov, False, "fallo simulado (prueba)")
        raise ErrorFuente("[simulado] proveedor %s bloqueado" % prov)
    if proveedor_cortado(prov):
        raise ErrorFuente("proveedor %s cortado tras fallos repetidos" % prov)
    host = re.sub(r"^https?://([^/]+).*$", r"\1", url)
    ultimo = None
    for i in range(retries + 1):
        try:
            _espaciar(host, espaciado)
            h = dict(HDRS)
            if headers:
                h.update(headers)
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
            data = r.read()
            marcar(prov, True)
            return data if binary else data.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            ultimo = e
            if e.code in (404, 410, 403):
                break  # no tiene sentido reintentar
            if e.code == 429 and retries == 0:
                break  # el llamador gestiona el enfriamiento
            if e.code == 429:
                ra = e.headers.get("Retry-After")
                time.sleep(min(10.0, float(ra)) if ra and ra.isdigit() else 3.0 * (i + 1))
                continue
        except Exception as e:
            ultimo = e
        time.sleep(0.8 * (i + 1) + random.random() * 0.3)
    marcar(prov, False, ultimo)
    raise ErrorFuente("No se pudo leer %s (%s)" % (re.sub(r"[?&]key=[^&]+", "", url)[:140], ultimo))
