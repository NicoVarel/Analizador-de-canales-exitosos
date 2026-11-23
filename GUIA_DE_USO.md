# Guía de uso

Escribe como hablarías con una persona. No necesitas comandos especiales (aunque `/analizador-canales-exitosos` también funciona).

## Modo 1 · Analizar un canal
- `Analiza este canal y dime por qué funciona: https://www.youtube.com/@canal`
- `Hazme un informe completo de este canal y qué puedo aprender: <URL>`

## Modo 2 · Comparar varios canales
- `Analiza estos tres canales y encuentra los patrones de éxito que tienen en común: <URL 1>, <URL 2>, <URL 3>`
- `Compara estos dos canales del mismo nicho y dime dónde hay hueco para uno nuevo: <URL 1> <URL 2>`

## Modo 3 · Videos concretos
- `Analiza este video: título, miniatura, gancho y estructura. Dime qué pudiste ver realmente: <URL del video>`
- Si tienes el archivo del video en tu ordenador: `Analiza la edición de este video (ritmo, cortes, recursos visuales): C:\ruta\mi_video.mp4`
- Si tienes la transcripción o capturas, pégalas o indica el archivo.

## Modo 4 · Estrategia para tu canal
- `Analiza este canal y ayúdame a crear una estrategia original para competir en su nicho: <URL>`
- `Quiero un canal sobre [tema] en [idioma], sin mostrar la cara, 3 horas por semana. Usa estos canales de referencia para crear mi estrategia: <URL 1> <URL 2>`

## Funciones puntuales
- `Analiza solo los títulos de este canal y dame estructuras nuevas para mi tema: <URL>`
- `Mira las miniaturas de sus 8 mejores videos y dime qué principios visuales comparten`
- `Dame 10 ideas de videos originales basadas en lo que funciona en este canal`

## Continuar más tarde
- `Continúa el análisis de [canal]` → Claude lee `analisis_canales/<canal>/PROGRESO.md` y sigue donde lo dejó.
- `Actualiza las estadísticas de [canal]` → vuelve a leer vistas y conserva el histórico con su fecha.

## Qué esperar al pedir un análisis
1. Claude ejecuta el motor (≈1–3 min por canal): lista 50–100 publicaciones por formato, lee fechas y vistas exactas, separa largos/Shorts/directos, calcula estadísticas y elige 5–10 videos.
2. Te muestra primero el **informe de cobertura**: qué se consiguió de verdad y qué no (por ejemplo "fechas exactas 100 de 115", "transcripciones 5 de 6").
3. Mira las miniaturas elegidas y lee las transcripciones disponibles.
4. Redacta el informe sin conclusiones que necesiten datos que no se pudieron obtener.
Si falta algo importante te dirá cómo completarlo (esperar un 429, instalar yt-dlp con tu permiso, pegar una transcripción…).

## Cómo leer el informe
- **[VERIFICADO]** dato observado con fuente y fecha · **[ESTIMACIÓN]** cálculo aproximado · **[HIPÓTESIS]** idea razonable sin probar · **[NO DISPONIBLE]** no se pudo obtener.
- *Ratio 3× = el video tiene el triple de vistas que la mediana del canal.* Un solo éxito no es un patrón.
- Las vistas son públicas; el **CTR, la retención y los ingresos de otros canales no lo son**: el informe no los inventa.

## Consejos
1. Cuantos más videos del canal tengan transcripción o los pegues tú, mejor el análisis narrativo.
2. Empieza por 1 canal; compara después.
3. Valida las ideas en TU canal con pruebas pequeñas (el informe propone experimentos).
