# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/) y
versionado semántico (`MAYOR.MENOR.PARCHE`).

## [2.0.0] - 2026-11-18

### Añadido

- Autenticación por sesión `HttpOnly` con rotación, caducidad absoluta y por
  inactividad, revocación y bloqueo por fuerza bruta.
- CSRF obligatorio en toda escritura, con validación exacta de `Host` y
  `Origin` y cabeceras CSP/COOP/CORP.
- Validación de seguridad del endpoint CDP (loopback, puerto explícito, proceso
  y perfil dedicados) antes de operar sobre X.
- Escritura atómica, permisos `0700/0600`, bloqueos, rechazo de enlaces
  simbólicos y protección contra traversal.
- Máquina de estados por publicación (`DISCOVERED` … `UNDONE`) con transiciones
  validadas.
- Verificación real de repost, cita y undo; los resultados inciertos no se
  reintentan.
- Trabajos persistentes con recuperación como `INTERRUPTED`.
- Bandeja de revisión, perfiles de filtros, grupos de cuentas con alias y
  favoritos, programación de previsualizaciones y estadísticas con denominador.
- Exportaciones CSV (con neutralización de fórmulas), Markdown, JSON, HTML,
  PDF y backups verificables.
- Panel con ocho secciones, temas claro/oscuro, diseño adaptable y mejoras de
  accesibilidad.
- Comandos `--stats`, `--diagnose`, `--backup`, `--restore`, `--strict-cdp` y
  `--version`.
- Documentación técnica y de usuario en `docs/`.
- CI con `ruff`, `shellcheck`, `bandit`, `gitleaks`, `pip-audit`, `mypy`
  (informativo), cobertura y verificación de la copia portable.

### Cambiado

- El token ya no se imprime en el log ni permanece en la URL.
- La programación solo ejecuta previsualizaciones; nunca reposts automáticos.
- Las estadísticas separan confirmados, deshechos y desconocidos.

### Corregido

- `ruff` fallaba en CI por nombres inyectados por `browser-use` y por una
  f-string incompatible con Python 3.10.
- Un token de ejemplo real quedó en `ABRIR_LA_APLICACION.md`.

## [1.x]

Versiones anteriores sin changelog formal: CLI de repost, exportación CSV/MD e
historial JSONL.
