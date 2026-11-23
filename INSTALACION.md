# Instalación (para alumnos, sin programar)

## La forma más fácil: que Claude lo instale por ti
1. Descarga el ZIP desde Skool y **descomprímelo** (clic derecho → Extraer todo).
2. Abre Claude Code en la carpeta descomprimida.
3. Copia y pega el contenido de `PROMPT_INSTALACION_ASISTIDA.md`.
4. Claude revisará el paquete, comprobará que no sobrescribe nada tuyo y te pedirá confirmación antes de copiar.
5. Cierra y abre Claude Code (o escribe `/skills`) y comprueba que aparece **analizador-canales-exitosos**.

## Instalación manual (alternativa)
La Skill es una carpeta llamada `analizador-canales-exitosos`. Debe quedar dentro de la carpeta personal de Skills de Claude Code.

**Windows (PowerShell), desde la carpeta descomprimida:**
```powershell
if (Test-Path "$env:USERPROFILE\.claude\skills\analizador-canales-exitosos") { "YA EXISTE: no se copia (ver sección Actualizar)" } else { New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null; Copy-Item -Recurse ".\analizador-canales-exitosos" "$env:USERPROFILE\.claude\skills\"; "Instalada" }
```
**Mac / Linux:**
```bash
[ -e ~/.claude/skills/analizador-canales-exitosos ] && echo "YA EXISTE: no se copia" || (mkdir -p ~/.claude/skills && cp -r ./analizador-canales-exitosos ~/.claude/skills/ && echo "Instalada")
```
Solo para un proyecto concreto: copia la carpeta a `.claude/skills/` dentro de ese proyecto.

## Comprobar que funciona
En Claude Code escribe `/skills`: debe aparecer *analizador-canales-exitosos*. Si no aparece, escribe `/reload-skills` o reinicia Claude Code (las skills se descubren al abrir la sesión y al cambiar la carpeta; una skill recién copiada puede tardar un turno en aparecer o requerir `/reload-skills`). Primer uso de prueba:

> Analiza este canal y dime por qué funciona: https://www.youtube.com/@veritasium

## Actualizar a una versión nueva
No borres a ciegas. Pide a Claude: *"Actualiza la Skill analizador-canales-exitosos con la carpeta nueva; guarda antes una copia de la versión instalada en `analizador-canales-exitosos_copia_AAAA-MM-DD` fuera de la carpeta de skills."* Solo se reemplaza esa carpeta; tus análisis (`analisis_canales/` en tus proyectos) no se tocan.

## Desinstalar
Se elimina únicamente la carpeta de esta Skill (no afecta a otras):
```powershell
Remove-Item -Recurse "$env:USERPROFILE\.claude\skills\analizador-canales-exitosos"
```
```bash
rm -r ~/.claude/skills/analizador-canales-exitosos
```

## Mejoras opcionales (gratis; solo con tu permiso)
La Skill funciona sin nada de esto (modo básico: lista de ~30 largos y ~48 Shorts por pestaña, sin transcripciones automáticas). Para análisis más profundo:
- **yt-dlp** → lista de hasta 100 publicaciones por formato y subtítulos. Pídele a Claude: *"Instala yt-dlp desde PyPI y dime la versión"*. Para actualizar: *"Actualiza yt-dlp"* (YouTube cambia a menudo).
- **API de YouTube (clave gratuita con cuota diaria)** → historial profundo, fechas exactas y fecha de creación del canal. Crea una clave en Google Cloud (YouTube Data API v3) y guárdala **en tu propia terminal**, nunca en el chat: `python "<carpeta de la skill>/scripts/yt_canal.py" api-config`.
- **Diagnóstico:** escribe «ejecuta doctor de la skill» o `python "<carpeta de la skill>/scripts/yt_canal.py" doctor`: muestra qué tienes disponible.

## Si YouTube responde "demasiadas peticiones" (HTTP 429)
Es un límite temporal. La Skill espera, baja el ritmo y no insiste; guarda en caché lo ya obtenido. Espera unos minutos y repite el análisis: continuará sin repetir lo hecho.

## Preguntas frecuentes
- **¿Necesito Python?** No es obligatorio. Con Python la recopilación de datos es automática. Comprueba con `python --version` (en Windows también `py --version`).
- **¿Dónde se guardan mis análisis?** En `analisis_canales/` dentro del proyecto donde trabajes. Nada sale de tu ordenador.
- **¿Pide contraseñas?** Nunca. Si algo te las pide, no es esta Skill: no las des.
- **¿Qué hace el script?** Solo lee páginas públicas de YouTube (y, si tú lo configuras, la API oficial o yt-dlp) y escribe en `analisis_canales/`. Puedes leer `scripts/yt_canal.py` y la carpeta `scripts/yt_engine/` (código Python sin dependencias).
