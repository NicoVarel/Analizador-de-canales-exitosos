# Prompt de instalación asistida

Abre Claude Code **en la carpeta donde descomprimiste el ZIP** y pega esto:

```
Instala la Skill "analizador-canales-exitosos" que está en la subcarpeta analizador-canales-exitosos de esta carpeta, de forma segura. Sigue estos pasos y no te saltes ninguno:

1. REVISA el paquete antes de copiar nada: lista todos sus archivos y lee SKILL.md y scripts/yt_canal.py. Dime en 5 líneas qué hace. Avísame si ves algo que no sea de solo lectura (borrar archivos, enviar datos fuera, pedir credenciales, instalar programas).
2. COMPRUEBA que existe SKILL.md con "name: analizador-canales-exitosos" en su cabecera.
3. MIRA si ya existe la carpeta ~/.claude/skills/analizador-canales-exitosos (en Windows: %USERPROFILE%\.claude\skills\analizador-canales-exitosos). Si existe, NO la sobrescribas: dime qué versión hay, y pregúntame si quiero actualizar (guardando antes una copia fuera de la carpeta de skills).
4. NO toques ninguna otra Skill ni configuración. Solo se añade esa carpeta.
5. Pídeme confirmación y, cuando te diga que sí, copia la carpeta a ~/.claude/skills/.
6. VERIFICA que quedó SKILL.md en su sitio y dime que escriba /skills (o /reload-skills) para comprobar que aparece.
7. Termina mostrándome un primer ejemplo de uso.
```

## Para actualizar
```
Actualiza la Skill analizador-canales-exitosos con la subcarpeta nueva de esta carpeta. Primero copia la versión instalada a una carpeta de respaldo fuera de ~/.claude/skills, enséñame qué cambia (versión y archivos) y pide mi confirmación antes de reemplazar. No toques otras Skills.
```

## Para desinstalar
```
Desinstala solo la Skill analizador-canales-exitosos (carpeta ~/.claude/skills/analizador-canales-exitosos). Muéstrame lo que vas a borrar y espera mi confirmación. No borres mis carpetas analisis_canales ni ninguna otra Skill.
```
