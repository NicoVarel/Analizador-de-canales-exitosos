# Analizador de Canales Exitosos
**AI Content Academy · Recurso 02** · versión 1.1.0-rc1 (motor de investigación multifuente)

Una Skill de Claude Code que estudia canales y videos de YouTube con evidencias y los convierte en una **estrategia original** para tu canal. Tú pegas un enlace; Claude se encarga de reunir datos, calcular, analizar y recomendar.

> No copia videos, miniaturas, guiones ni identidades. Extrae **principios** que funcionan.

## Qué hace
- **Modo 1 · Un canal:** perfil, rendimiento, videos destacados, títulos, miniaturas, narrativa, edición, patrones, monetización, oportunidades, 10 ideas y plan de acción.
- **Modo 2 · 2–5 canales:** patrones comunes, diferencias, formatos prometedores, huecos de diferenciación y lo que depende del creador.
- **Modo 3 · Videos concretos:** título, miniatura, gancho, estructura, ritmo, edición… declarando exactamente **qué pudo inspeccionar** (metadatos, transcripción, fotogramas o video).
- **Modo 4 · Tu propio canal:** posicionamiento, formato, títulos, miniaturas, 10 ideas, plan de 4 semanas y experimentos de validación.

## Qué cambió en la v1.1 (motor de datos)
- Recopila **50–100 publicaciones por formato** (antes ~30 largos / 48 Shorts) y obtiene **fechas y vistas exactas** de cada una, separando largos, Shorts y directos.
- **Motor multifuente con fallback:** páginas públicas (gratis, siempre) → API oficial de YouTube (opcional) → yt-dlp (opcional) → fuentes externas. Si una falla, usa otra y lo registra.
- **Informe de cobertura** real antes de redactar: cuántos videos, fechas exactas, miniaturas *inspeccionadas*, transcripciones conseguidas, qué falta y por qué.
- **Transcripciones** con calidad registrada (idioma, método, automática/manual, cobertura, confianza); una transcripción vacía nunca cuenta como éxito.
- **Resultados estructurados** (`datos_canal.json`, `videos.jsonl`…): las estadísticas salen de los datos, no de texto escrito a mano.

## Qué NO hace (a propósito)
No inventa cifras. No conoce el CTR, la retención ni los ingresos de canales ajenos (son privados) y nunca los declara. No afirma haber visto un video que no vio. No publica, no paga, no pide contraseñas.

## Sistema de evidencias
`[VERIFICADO]` observado con fuente y fecha · `[ESTIMACIÓN]` cálculo o aproximación declarada · `[HIPÓTESIS]` interpretación no probada · `[NO DISPONIBLE]` no se pudo obtener.

## Contenido de la carpeta
| Archivo | Para qué |
|---|---|
| `analizador-canales-exitosos/` | **La Skill instalable** (`SKILL.md`, `references/`, `templates/`, `scripts/`) |
| `INSTALACION.md` | Instalar, actualizar y desinstalar |
| `PROMPT_INSTALACION_ASISTIDA.md` | Texto para que Claude instale el paquete de forma segura |
| `GUIA_DE_USO.md` | Ejemplos de lo que puedes escribir y qué esperar |
| `METODOLOGIA.md` | Métricas, investigación y controles |
| `EJEMPLO_DE_RESULTADO.md` | Demostración con datos reales |
| `TESTS.md` | Registro de pruebas (lo ejecutado y lo pendiente) |
| `CHANGELOG.md` | Historial de cambios |
| `_herramientas/construir_zip.py` | Genera el ZIP para Skool |

## Requisitos
- Claude Code actualizado.
- Recomendado: Python 3.8+ (comprueba con `python --version`). Sin Python, la Skill funciona igual pero con menos automatización (usa búsqueda web y datos que pegues).
- Opcional (más profundidad, siempre gratis): `yt-dlp` (lista larga y subtítulos) y una clave gratuita de la API de YouTube. Ninguna es obligatoria; se instalan solo con tu permiso.
- Opcional: `ffmpeg` solo para analizar la edición de un video **que tú tengas en tu ordenador**.
- Sin servicios de pago, sin cuentas, sin claves.

## Se combina con el Recurso 01
Es independiente del *Investigador de Nichos Ganadores*. Usados juntos: 1) el Investigador encuentra oportunidades, 2) este Analizador estudia los mejores canales de ese nicho, 3) tú creas ideas, guiones y videos originales.
