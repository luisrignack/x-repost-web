# Backup y restauración

## 1. Qué se puede respaldar

| Modo | Contenido | Comando | Formato |
| --- | --- | --- | --- |
| Historial | `history.jsonl` + rotaciones | `./xrepost.sh --backup` | JSONL + `.sha256` |
| Estado completo | Historial, cuentas, hashtags, red, grupos, perfiles, bandeja y programación | Panel → Sistema → Backup completo / `POST /api/backup {"mode":"bundle"}` | `.tar.gz` |

El backup completo **no** incluye el perfil de Chrome ni el token del panel.

Archivos incluidos en el bundle:

```
history.jsonl
accounts.json
hashtags.json
network.json
groups.json
profiles.json
inbox.json
schedules.json
```

## 2. Backup del historial por CLI

```bash
./xrepost.sh --backup
```

Salida:

```
Backup: /home/usuario/.local/state/xrepost/backups/history-20261118T100000Z.jsonl
Eventos: 120 · 48.2 KB · sha256: abc123…
```

Con destino explícito:

```bash
./xrepost.sh --backup /media/usb/xrepost-2026-11-18.jsonl
```

Propiedades:

- Combina el historial principal y los archivos rotados en un único JSONL.
- Escribe el checksum en `<archivo>.sha256`.
- Usa escritura atómica y permisos 0600.
- Si no hay historial, falla con un mensaje claro.

## 3. Verificación

```bash
./xrepost.sh --diagnose
```

El diagnóstico del historial informa de:

- Ruta y archivos encontrados.
- Eventos totales y corruptos.
- Reposteados y deshacibles.

Para verificar un backup concreto desde Python:

```bash
python3 - <<'PY'
from xrepost_history import verify_backup
print(verify_backup("/ruta/backup.jsonl"))
PY
```

Devuelve `ok: true` solo si el checksum coincide, hay eventos y no hay líneas
corruptas.

## 4. Restauración del historial

```bash
./xrepost.sh --restore /ruta/backup.jsonl
```

Pasos:

1. Verifica el checksum y las líneas.
2. Si el historial actual existe, lo copia a
   `history.pre-restore-<fecha>.jsonl`.
3. Escribe el backup de forma atómica.
4. Devuelve el diagnóstico posterior.

Si la verificación falla, se rechaza salvo que se use `force` desde la API. El
CLI no expone `force` para evitar restauraciones accidentales.

## 5. Backup completo desde el panel

Pestaña **Sistema** → **Crear backup completo**.

La API:

```bash
TOKEN="$(cat ~/.local/state/xrepost/panel-token)"
curl -s -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"mode":"bundle"}' http://127.0.0.1:8765/api/backup
```

Los bundles se guardan en:

```
~/.local/state/xrepost/backups/state-<fecha>.tar.gz
```

El panel solo acepta restaurar backups creados por xrepost (comprueba que la
ruta esté en la lista de backups conocidos o sea el historial actual).

## 6. Restauración completa

```bash
TOKEN="$(cat ~/.local/state/xrepost/panel-token)"
curl -s -H "X-Token: $TOKEN" -H "Content-Type: application/json" \
  -d '{"path":"/home/usuario/.local/state/xrepost/backups/state-20261118T100000Z.tar.gz"}' \
  http://127.0.0.1:8765/api/restore
```

`restore_bundle()`:

- Rechaza rutas absolutas, `..` y nombres fuera de la lista permitida.
- Solo extrae archivos regulares.
- Escribe cada archivo con permisos privados.
- Devuelve `restored` y `skipped`.

## 7. Copia fuera del equipo

El backup local no protege frente a un fallo del disco. Se recomienda:

```bash
# copiar el último backup a un USB
cp ~/.local/state/xrepost/backups/history-*.jsonl /media/usb/xrepost/
cp ~/.local/state/xrepost/backups/*.sha256 /media/usb/xrepost/
```

O programar una copia periódica con `cron`:

```cron
0 3 * * * cd /ruta/x-repost-web && ./xrepost.sh --backup /media/usb/xrepost/backup-$(date +\%F).jsonl
```

Verifica los backups de vez en cuando con `verify_backup()`.

## 8. Recuperación ante corrupción

Si `diagnose()` detecta líneas corruptas:

1. No borres el archivo.
2. Haz una copia inmediata:
   ```bash
   cp history.jsonl history.corrupto-$(date +%F).jsonl
   ```
3. Restaura el último backup verificado.
4. Compara el número de eventos y revisa los que falten.

Si el JSON de estado está corrupto:

- `JsonStore` guarda `<archivo>.corrupt-<fecha>` automáticamente.
- Se devuelve el valor por defecto.
- Restaura el archivo desde el bundle si lo tienes.

## 9. Qué no se puede recuperar

- Un repost ya publicado en X: el backup restaura el registro local, no la
  acción en X.
- La sesión de Chrome: si se pierde, hay que iniciar sesión de nuevo.
- El token del panel: si se borra, `iniciar.sh` genera uno nuevo.
- Una cita publicada pero no registrada: aparecerá como no confirmada en el
  historial y requerirá revisión manual.

## 10. Lista de comprobación

Antes de una operación arriesgada:

- [ ] `./xrepost.sh --diagnose` sin errores.
- [ ] Backup reciente con checksum.
- [ ] Copia del backup fuera del equipo.
- [ ] Panel detenido o sin trabajos en curso.
- [ ] Espacio libre suficiente.

Después de restaurar:

- [ ] `./xrepost.sh --diagnose` correcto.
- [ ] El panel muestra el historial esperado.
- [ ] La bandeja y las programaciones conservan su estado.
- [ ] Los permisos son 0600/0700.
