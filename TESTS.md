# Registro de pruebas · v1.1.0-rc1 · 2026-11-23

Estados: ✅ superada · 🟡 parcial · ⏳ pendiente · ❌ fallida. Cada prueba indica qué se ejecutó de verdad. Las pruebas **sin red real** o contra el servidor **simulado** de la API están rotuladas como tales y no sustituyen a las reales.

## Hallazgo importante del entorno de pruebas: límite de peticiones (HTTP 429)
Tras ejecutar varias veces el motor completo (≈100 páginas de video por ejecución) YouTube respondió **429** a las páginas de video y, además, **bloqueo anti-bot** a yt-dlp para los subtítulos, durante ≈30 minutos cada vez. No se eludió: el motor esperó, redujo el ritmo, usó la caché y registró el hecho. Consecuencias aplicadas: ritmo de 2 hilos y 0,4 s de espaciado, tope de cortesía de 80 páginas **nuevas** por ejecución, caché de resultados, aviso explícito en la cobertura. Esto también es una limitación real para los alumnos (ver "Limitaciones").

## Causas de los fallos de la v1.0 (comprobadas con datos reales)
| Fallo v1.0 | Causa comprobada | Corrección v1.1 |
|---|---|---|
| ≈30 largos / 48 Shorts | solo se leía la 1ª página de cada pestaña | lista profunda con yt-dlp (hasta 100+) o API oficial; la API interna de YouTube **no** se usó (bloqueado por seguridad y descartado) |
| Fechas exactas solo en 15 videos | únicamente el feed RSS las daba | fecha y vistas exactas desde la página de cada video (hasta el tope de cortesía), API, caché; aproximadas con rango y marcadas |
| Vistas redondeadas ("1,3 M") | las pestañas/lista plana redondean | cifra exacta de la página del video; la lista plana se marca `aprox` |
| Transcripciones vacías | la URL directa de subtítulos devuelve HTTP 200 con 0 bytes aunque las pistas existen | yt-dlp (idioma hablado primero); si falla, estado explícito; nunca se acepta vacío |
| Transcripción "intermitente" | además, límite 429/anti-bot de YouTube tras muchas peticiones | enfriamiento, caché, mensaje claro `bloqueo anti-bot… NO se elude` |
| "Unknown skill" en la 1ª invocación | la lista de skills de la sesión se refresca entre turnos; la estructura era correcta (nombre = carpeta, SKILL.md válido) | documentado (`/reload-skills`); en esta sesión la Skill actualizada **sí** aparece y se invocó con éxito (prueba J) |

## Pruebas automáticas (offline) — `_herramientas/pruebas/pruebas_offline.py`
**15 pruebas, todas ✅.** Cubren: vistas abreviadas ("16M", "377 thousand", "No views"), fechas relativas con rango, aproximada ≠ exacta, exacta gana a aproximada y se registran discrepancias, mediana que excluye al propio video, no mezclar formatos, directos excluidos, muestra pequeña sin medianas, confianza por tamaño, patrones solo con n≥5, selección de 5–10 sin duplicados. Y contra un **servidor de API SIMULADO** (no equivale a una clave real): paginación de *uploads* en 3 páginas, lotes de `videos.list`, ausencia de `search.list`, clasificación segura de formatos, cuota agotada → proveedor cortado, **la clave nunca aparece en ningún archivo de salida**, redacción de la clave en errores, desvío de URL solo a localhost.

## A · Canal completo (MinutePhysics, real) — ✅
- **Procedimiento:** `investigar @minutephysics` (nivel 3) con el motor v1.1; después flujo de la Skill (miniaturas, observaciones, cobertura).
- **Resultado:** 115 videos (100 largos, 14 Shorts, 1 directo); 114 con vistas **exactas** y fecha **exacta**; creación del canal 2011-06-20 ≠ primer video visible 2011-06-26; 305 largos visibles de los que se analizaron 100; mediana 753 644 (n=100); 6 outliers ≥5×; 12 miniaturas válidas (4 vistas y registradas en esa ejecución); 4 transcripciones de 6 (las otras 2 coincidieron con el 429). Informe de cobertura generado automáticamente. Demostración: `EJEMPLO_DE_RESULTADO.md`.
- **Reutilización:** segunda ejecución del mismo canal con caché: **18 s** (vs 133 s) y medianas idénticas, incluso con las páginas de video limitadas.

## B · Canal con muchos Shorts (@ZachKing, real) — ✅
`investigar @ZachKing --max-paginas 50 --max-transcripciones 3` con la Skill instalada: 201 videos (100 largos + 100 Shorts; visibles en pestañas 424 largos y 456 Shorts; el canal declara 881), formatos separados; Shorts mediana 5 771 741 (n=30, confianza alta, 3 outliers ≥5×) y largos 1 534 710 (n=20); vistas y fechas exactas en 65 videos (50 páginas + 15 del RSS) y **declaradas como pendientes** para los 135 restantes por el tope de cortesía (no inventadas); 12 miniaturas válidas; subtítulos de 2 de 3 intentos (el tercero con bloqueo declarado). La cobertura lo explica y dice cómo completarlo.

## C · Canal nuevo / historial pequeño — 🟡
Se ejecutó sobre *Tech Plus AI* (canal real, 40 K suscriptores; pestaña de largos con 17 entradas, 12 de ellas directos). Con 5 largos válidos el motor declaró **confianza baja** y (v1.1) añade `aviso_muestra_pequena` y `senal_fiable: false`: no concluye patrones. El caso "menos de 3 videos" (sin medianas) está cubierto por prueba automática, no por un canal real.

## D · Varios canales del mismo nicho (MinutePhysics vs Veritasium, real) — ✅ (datos) / 🟡 (redacción)
Los datos de MinutePhysics se **reutilizaron de la caché** (18 s, sin nuevas páginas) y Veritasium se ejecutó con tope de 40 páginas (37 s). Tabla generada desde los JSON: largos MinutePhysics n=100, mediana 753 644, duración mediana 4:59, 0,25 publ./semana (365 d), 6 outliers ≥5×; Veritasium n=100, mediana 10 629 286, duración 29:31, 0,42 publ./semana (calculada solo con las 55 fechas exactas), 2 outliers ≥5×. Ningún rasgo de título alcanzó n≥5 en ambos lados con diferencia notable en ninguno de los dos. Queda 🟡 la prueba de que **Claude redacta** la comparación (Modo 2) sin 3 informes enormes.

## E · Transcripciones — ✅
- **Con subtítulos (✅ real):** 4 transcripciones obtenidas por yt-dlp con metadatos (idioma, método, automática/manual, cobertura 0,96–0,99, confianza); una era una pista manual en español de un video cuyo idioma hablado puede ser otro (se detecta y marca `es_traduccion`).
- **Local (✅ real, video propio del usuario):** `transcribir-local` con `openai-whisper` (modelo `base` ya presente en caché; no se descargó nada) sobre un video de 25 s: 78 palabras, cobertura 0,67, confianza media, errores de reconocimiento visibles ("verdos", "prom").
- **Fallo/bloqueo (✅ real):** con el límite activo, 6 de 6 intentos terminaron en `fallo_extraccion` con causa legible (`bloqueo anti-bot… NO se elude`) y el análisis continuó sin inventar texto.
- **Subtítulos ausentes (✅ real):** un Short de @ZachKing sin pistas (`6UxNhdhTIZA`): estado `sin_subtitulos`, nivel de acceso `solo_metadatos`, sin inventar texto.

## F · Miniaturas — ✅ (parcial en volumen)
Se abrieron y describieron 6 miniaturas distintas de 2 ejecuciones (todas coincidieron con su video: se verificó imagen↔título). Validación de archivo: se rechaza un JPEG diminuto o el marcador de "sin miniatura"; un id inexistente devuelve `NO DISPONIBLE`. La cobertura cuenta como inspeccionada **solo** la que tiene observación registrada.

## G · Análisis audiovisual — 🟡
Video **real y propio** del usuario (`Empieza_Aqui_AI_Content_Academy.mp4`, 24,9 s): 11 fotogramas de muestra guardados (2 abiertos y descritos), 0 cortes duros detectados (umbral 0,15), transcripción local real. No es un video de un canal ajeno ni se descargó nada de YouTube. El detector de cortes se validó además con un video **sintético** de cortes conocidos (2,0 s y 5,0 s → detectados exactamente): rotulado como sintético.

## H · Sin API — ✅
Todas las ejecuciones reales de esta versión se hicieron **sin clave de API** (`youtube_data_api: no_configurada_opcional`), completando el análisis con fuentes públicas y yt-dlp. La API solo se probó contra el servidor simulado.

## I · Fuente bloqueada — ✅
- *Natural (real):* páginas de video con 429 → enfriamiento, disyuntor, caché, respaldo por yt-dlp (hasta 20) y cobertura que declara los pendientes.
- *Simulada (`YT_ENGINE_FALLAR`):* pestañas + página de video bloqueadas → 54 videos desde yt-dlp (35 con fecha exacta); además yt-dlp bloqueado → 15 videos del RSS con aviso "Lista parcial". En ambos casos la cobertura documenta la pérdida.

## J · Ejecución viva en Claude Code — 🟡
- **Hecho:** con la Skill v1.1 ya instalada, se invocó con la herramienta *Skill* (`/analizador-canales-exitosos @minutephysics`). Claude Code la reconoció (la descripción actualizada aparece en la lista de skills de la sesión), expandió `${CLAUDE_SKILL_DIR}` a la ruta instalada y se siguió el flujo: investigar con `--json`, leer cobertura, abrir 2 miniaturas, registrarlas, recalcular cobertura y escribir un informe corto (no inventó transcripciones: 0 de 6 por el bloqueo anti-bot).
- **No se pudo (⏳):** una **sesión nueva** (`claude -p`) para comprobar el descubrimiento al arrancar: falla con *OAuth session expired*; no se tocaron credenciales. Tampoco se pudo observar si Claude Code pide permisos por la regla `allowed-tools` en Windows (esta sesión no los pedía; no es evidencia).
- **Cómo repetir:** abre una sesión nueva de Claude Code en cualquier carpeta de proyecto, escribe `/skills` (debe listar *analizador-canales-exitosos*) y luego `/analizador-canales-exitosos https://www.youtube.com/@minutephysics`; anota si aparece algún aviso de permiso.

## Regresión (v1.0 → v1.1) — ✅
Desde la **copia instalada**: `miniaturas` (válida e id inexistente), `frames` (2 cortes exactos), `estado`, `canal`, lectura de vistas abreviadas, fechas relativas, separación Shorts/largos, medianas sin el propio video, muestra pequeña sin medianas, continuidad (`PROGRESO.md`/`estado`/caché), privacidad (el empaquetador bloquea rutas personales, correos y claves plantadas), ZIP. Sin red (proxy inválido): error claro, exit 1, sin crear archivos.

## Corrección durante las pruebas (clasificación de formatos)
En Veritasium aparecieron 106 "directos" y en Kurzgesagt 75: eran **estrenos (premieres)**, que salen también en la pestaña de directos. Corregido: un video presente en Videos/Shorts es normal (con `marca_directo_o_estreno`); los que solo salen en la pestaña de directos son `estreno_o_directo` (fuera de las estadísticas, contados aparte). Prueba automática añadida (16 pruebas ✅). Tras la corrección: Kurzgesagt 100 largos + 100 Shorts + 54 sin distinguir.

## Pruebas pendientes
- **J en sesión nueva** (arranque y `/skills`), con la observación de permisos de `allowed-tools` en Windows: pasos en la prueba J.
- **API real:** el proveedor solo se probó contra un servidor simulado; falta una prueba con una clave real del propietario del canal de pruebas (se configura con `api-config` en su terminal).
- **Redacción de informes por Claude** en Modos 2 y 4 de principio a fin y continuidad guiada por el modelo (`Continúa el análisis…`).
- Probar la instalación en un Windows limpio **sin Python**.
