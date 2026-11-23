# Historial de cambios

## 1.1.0-rc1 · 2026-11-23 — Motor de investigación multifuente
**Problema:** la v1.0 solo leía la primera página de cada pestaña (≈30 largos, 48 Shorts), tenía fechas exactas únicamente en 15 videos (feed RSS), y las transcripciones dependían de una URL que YouTube devuelve vacía (HTTP 200, 0 bytes) a un cliente simple.
**Cambios:**
- Nuevo paquete `scripts/yt_engine/` (net, fechas, registro, prov_publico, prov_api, prov_ytdlp, estadisticas, miniaturas, transcripciones, visual, cobertura, motor). `yt_canal.py` es ahora la CLI; los comandos v1.0 (`canal`, `video`, `miniaturas`, `frames`, `estado`) siguen funcionando.
- Comandos nuevos: `investigar`, `cobertura`, `registrar`, `transcribir-local`, `externo`, `doctor`, `api-config`, `api-estado`.
- Proveedores: públicos (cabecera, RSS, pestañas, página de video), API oficial v3 opcional (channels → playlistItems/uploads → videos.list; sin search.list), yt-dlp opcional (lista profunda y subtítulos; nunca videos), fuentes externas registradas con tipo y fecha.
- Fechas: exactas desde la página de video/API; aproximadas con rango (de "hace N meses" o interpoladas por el orden de la lista entre dos fechas exactas), nunca promovidas a exactas; creación del canal ≠ primer video accesible ≠ fecha de consulta.
- Fusión por id con procedencia por campo y registro de discrepancias; confianza por registro.
- Estadísticas extendidas: comparación con antigüedad semejante, recientes vs antiguos, frecuencia (90/365 días), duración habitual, patrones repetidos con n dentro/fuera; selección de 5–10 videos; aviso de muestra pequeña.
- Transcripciones por niveles con calidad registrada; local con `openai-whisper`/`faster-whisper` si ya están instalados (sin descargar modelos sin permiso).
- Miniaturas validadas (JPEG real, no marcador) y vinculadas a su video; "inspeccionada" solo con observación registrada.
- Informe de cobertura automático desde los datos y las observaciones.
- Red: 2 hilos máximo, espaciado, enfriamiento ante HTTP 429, disyuntor por proveedor, caché de resultados parseados, presupuesto de tiempo.
- Seguridad: sin cookies, sin proxies, sin API interna de YouTube; clave de API nunca impresa ni guardada en informes.
- Clasificación de formatos corregida durante las pruebas: los estrenos (premieres) aparecen también en la pestaña de directos y se marcaban como directos (106 falsos directos en un canal de prueba); ahora son videos normales con marca, y lo ambiguo se cuenta aparte (`estreno_o_directo`).
- Tope de cortesía de 80 páginas nuevas por ejecución (`--max-paginas`), `limpiar-cache`, `transcribir-local` con openai-whisper ya instalado (sin descargar modelos sin permiso).
- SKILL.md reescrito como flujo autónomo corto; nuevas referencias `motor-y-comandos.md` y `proveedores-opcionales.md`.

## 1.0.0-rc1 · 2026-11-23
Primera versión candidata.
- Skill `analizador-canales-exitosos` con 4 modos (canal, comparación, videos, estrategia propia).
- Arquitectura por fases A–E, sistema de evidencias, niveles de inspección y continuidad (`PROGRESO.md`).
- Script `scripts/yt_canal.py` (solo biblioteca estándar): `canal`, `video`, `miniaturas`, `frames`, `estado`. Respaldo opcional con yt-dlp únicamente para subtítulos.
- Referencias: estadística, títulos, miniaturas, narrativa/edición, monetización/estrategia, continuidad, seguridad, fuentes.
- Plantillas: informe, ficha de video, progreso.
- Documentación para alumnos, ejemplo con datos reales y registro de pruebas (`TESTS.md`).
- Correcciones durante las pruebas: lectura de vistas abreviadas ("16M"), fechas relativas abreviadas ("4d ago"), suscriptores/handle, Shorts sin fecha (`edad_precision: desconocida`), respaldo de subtítulos y límite 429.
