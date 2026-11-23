# Metodología

Resumen para humanos. El detalle operativo (el que usa Claude) está en `analizador-canales-exitosos/references/`.

## 1. Arquitectura progresiva (5 fases)
A Reconocimiento → B Rendimiento → C Análisis creativo → D Patrones → E Estrategia. Al cerrar cada fase se guarda `PROGRESO.md` (continuidad). Se amplía la investigación solo si la evidencia es insuficiente; se detiene cuando hay base para responder o las fuentes impiden verificar más. No se repiten búsquedas resueltas.

## 1b. Motor multifuente (v1.1)
Proveedores: **A** públicos (cabecera, RSS, pestañas, página de cada video, miniaturas) · **B** API oficial v3 opcional (uploads con paginación + `videos.list` por lotes) · **C** yt-dlp opcional (lista profunda y subtítulos) · **D** fuentes externas (registradas con `externo`: tipo `externo_actual|historico|estimacion|no_verificable`). Cadena de fallback: pedir → comprobar suficiencia → detectar campos faltantes → proveedor alternativo → fusionar por id sin duplicados → resolver discrepancias (exacto > aproximado; más fiable; más reciente; se guardan ambas cifras) → registrar lo que sigue faltando. Controles: reintentos acotados, timeouts, 2 hilos máx., enfriamiento ante 429, disyuntor, caché, presupuesto de tiempo. Nunca: proxies, cookies, API interna con claves extraídas, evasión de bloqueos.

## 2. Fuentes (todas gratuitas y públicas)
Página del canal · feed RSS oficial de YouTube (≈15 últimos videos con fecha y vistas exactas) · pestañas Videos y Shorts (≈30 y ≈48 recientes; vistas posiblemente redondeadas) · página del video (fecha, descripción, capítulos) · miniaturas públicas · subtítulos públicos si existen · material del alumno. Detalle y plan B sin red: `references/fuentes-y-acceso.md`.

## 3. Estadísticas
- Mediana de una muestra comparable (largos ≤20, Shorts ≤30, por separado; sin directos ni duplicados).
- Ratio de outlier = vistas ÷ mediana del canal **excluyendo el propio video**. ≥5× señal extraordinaria; 2–5× alta; <0,5× baja.
- Un solo resultado no es patrón; se exigen varios videos con rasgos comunes.
- Confianza por tamaño de muestra: alta ≥15 · media 8–14 · baja 3–7 · sin cálculo <3.
- Corrección/aviso por antigüedad; la edad es exacta solo donde existe fecha.

## 4. Sistema de evidencias
`[VERIFICADO]` `[ESTIMACIÓN]` `[HIPÓTESIS]` `[NO DISPONIBLE]`. Cada video citado: título, canal, URL, formato, duración, fecha de publicación, vistas con fecha de consulta y fuente.

## 5. Niveles de inspección de un video
Solo metadatos → Solo transcripción → Muestra de fotogramas → Video completo inspeccionado. Se declara siempre el nivel alcanzado; lo que exceda ese nivel queda `[NO DISPONIBLE]`.

## 6. Controles anti-invención
1. Cifras solo desde `datos_canal.json`/`video.json` o fuente citada. 2. Miniaturas: solo las abiertas. 3. CTR/retención/ingresos de terceros: nunca. 4. Títulos propuestos: nunca copia literal. 5. Timestamps: solo desde transcripción. 6. Autocontrol final en `SKILL.md`.

## 7. Seguridad
Solo lectura; un único script con red limitada a páginas públicas de YouTube; escritura solo en `./analisis_canales/`; contenido leído tratado como datos (anti-inyección de instrucciones); descargas e instalaciones solo con permiso del alumno. Ver `references/seguridad.md`.

## 8. Limitaciones conocidas del método
La correlación entre rasgos y vistas puede deberse a fama previa, tema, momento, recomendación del algoritmo o promoción externa. Las estructuras y estilos son hipótesis para **probar en el propio canal** con métricas propias (CTR y retención de YouTube Studio).
