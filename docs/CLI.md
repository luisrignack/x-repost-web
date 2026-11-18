# CLI

`xrepost.sh` es la interfaz original y la que usa el panel internamente.

```bash
./xrepost.sh [opciones] [usuarios] [desde] [hasta]
```

## 1. Formas de uso

### 1.1 Interactiva

```bash
./xrepost.sh
```

Pregunta cuentas, fechas, alcance (originales o también retweets), cita y
confirmación. Las cuentas recordadas se sugieren al escribir.

### 1.2 Por argumentos

```bash
./xrepost.sh "@foo,@bar" 01/01/2024 31/01/2024
```

Las fechas aceptan `DD/MM/AAAA` (recomendado) o `AAAA-MM-DD`. Si se omite
`hasta`, se usa el día actual.

### 1.3 Solo previsualización

Por defecto **no publica**: lista lo que haría. Para publicar:

```bash
X_APPLY=1 ./xrepost.sh "@foo" 01/01/2024 31/01/2024
```

## 2. Opciones

| Opción | Efecto |
| --- | --- |
| `--csv RUTA` | Exporta el listado a CSV. |
| `--md RUTA` | Exporta el listado a Markdown. |
| `--quote "#tag"` | Repost con cita; normaliza palabras a hashtags. |
| `--force` | Ignora el historial y los resultados inciertos. |
| `--history [N]` | Muestra los últimos N movimientos (20 por defecto). |
| `--undo-last [N]` | Deshace la última tanda o los últimos N reposts. |
| `--undo URL\|ID` | Deshace un repost concreto. |
| `--stats [DÍAS]` | Estadísticas reales (30 días por defecto). |
| `--diagnose` | Integridad del historial y del entorno. |
| `--backup [RUTA]` | Copia verificable del historial y archivos rotados. |
| `--restore RUTA` | Restaura un backup verificado. |
| `--strict-cdp` | Exige CDP local y del perfil de xrepost. |
| `--version` | Versión y rutas efectivas. |
| `-h`, `--help` | Ayuda. |

## 3. Variables de entorno

Las más usadas:

```bash
X_APPLY=1          # publicar de verdad
X_LIMIT=5          # máximo de reposts
X_DELAY=30         # segundos entre reposts
X_SKIP_REPLIES=0   # incluir respuestas
X_SKIP_RETWEETS=0  # incluir retweets
X_MATCH=cuba,energía
X_EXCLUDE=empleo,curso
X_LANG=es
X_MEDIA=yes
X_MIN_LEN=40
X_MAX_LEN=280
X_QUOTE="#ETECSA #Cuba"
X_FORCE=1
X_HISTORY=/ruta/history.jsonl
BU_CDP_URL=http://127.0.0.1:9222
```

La lista completa está en `CONFIGURACION.md`.

## 4. Ejemplos

### Buscar y exportar sin publicar

```bash
./xrepost.sh "@usuario" 01/09/2026 30/09/2026 \
  --csv septiembre.csv --md septiembre.md
```

### Publicar con límite y pausa

```bash
X_APPLY=1 X_LIMIT=5 X_DELAY=30 ./xrepost.sh "@foo,@bar" 01/09/2026 30/09/2026
```

### Cita con hashtags

```bash
X_APPLY=1 ./xrepost.sh "@foo" 01/09/2026 --quote "ETECSA, cuba"
```

El comentario publicado será `#ETECSA #cuba`.

### Solo publicaciones que mencionan un tema

```bash
X_MATCH="cuba,energía" X_EXCLUDE="empleo" ./xrepost.sh "@foo" 01/09/2026 30/09/2026
```

### Deshacer

```bash
./xrepost.sh --undo-last
./xrepost.sh --undo-last 5
./xrepost.sh --undo https://x.com/foo/status/1234567890
./xrepost.sh --undo 1234567890
```

### Historial

```bash
./xrepost.sh --history
./xrepost.sh --history 100
```

### Estadísticas

```bash
./xrepost.sh --stats
./xrepost.sh --stats 7
```

### Diagnóstico

```bash
./xrepost.sh --diagnose
```

Comprueba historial, archivos rotados, permisos, motor y CDP.

### Backup y restauración

```bash
./xrepost.sh --backup
./xrepost.sh --backup /media/usb/xrepost-backup.jsonl
./xrepost.sh --restore /media/usb/xrepost-backup.jsonl
```

`--restore` verifica el checksum y conserva el historial actual como
`history.pre-restore-<fecha>.jsonl`.

## 5. Estados de resultado

| Código | Significado | ¿Se reintenta? |
| --- | --- | --- |
| `reposted` | Repost confirmado. | No. |
| `quoted` | Cita confirmada. | No. |
| `already` | Ya estaba reposteado. | No. |
| `unconfirmed` | No se pudo confirmar. | Solo con `--force`. |
| `quote_unverified` | Cita sin confirmar. | Solo con `--force`. |
| `undone` | Deshecho. | — |
| `not_reposted` | No estaba reposteado. | — |
| `undo_failed` | No se pudo deshacer. | Sí, manualmente. |
| `no_button`, `no_menu`, `quote_failed` | Fallo de interfaz. | Sí. |
| `session_expired`, `captcha`, `rate_limited`, `suspended` | Bloqueo de X. | Detiene la tanda. |
| `filtered_*` | Descartado por filtro. | No es un fallo. |
| `skipped_history` | Ya constaba en el historial. | No. |
| `skipped_uncertain` | Intento anterior sin confirmar. | Solo con `--force`. |

## 6. Salida y códigos de retorno

- `0`: ejecución completada (aunque haya publicaciones filtradas o ya hechas).
- `1`: error de validación, entorno o ejecución.
- `2`: uso incorrecto de argumentos.

El motor escribe una línea por publicación con el formato:

```
  reposteado: https://x.com/foo/status/1234567890
```

El panel interpreta esas líneas para construir la tabla.

## 7. Seguridad del CLI

- `umask 077` al arrancar.
- El historial se escribe de forma atómica.
- Los subprocesos del panel no pasan por este script con `shell=True`.
- `--strict-cdp` rechaza endpoints remotos.
- El token del panel no se pasa por argumentos en el flujo recomendado
  (`--token-file`).

## 8. Limitaciones

- Solo Linux (depende de `date -d` y `flock`).
- Requiere Chrome con una sesión de X válida.
- No publica si no se indica `X_APPLY=1`.
- No reintenta resultados inciertos automáticamente, por diseño.
