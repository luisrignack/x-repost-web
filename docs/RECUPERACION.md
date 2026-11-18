# Recuperación ante fallos

Referencias: [`GESTION_DE_JOBS.md`](GESTION_DE_JOBS.md) ·
[`BACKUP_RESTORE.md`](BACKUP_RESTORE.md) · [`PERSISTENCIA.md`](PERSISTENCIA.md)

## 1. Principio

La recuperación es **conservadora**: nunca se repite automáticamente una
operación externa cuyo resultado no se puede verificar. Un repost, una cita o
un undo interrumpidos pueden haberse completado en X; repetirlos crearía
duplicados o desharía algo distinto.

## 2. Al arrancar el panel

1. Se abre `jobs.json`; si el JSON está corrupto, no se sobrescribe en
   silencio y se informa del problema.
2. `JobStore.recover()` marca como `INTERRUPTED` los trabajos en `CREATED`,
   `QUEUED` o `RUNNING`.
3. El mensaje persistido explica que el panel se cerró con la ejecución en
   curso y que hay que revisar X antes de repetir.
4. Los logs y los resultados parciales (`posts.csv`, `posts.md`,
   `selected.json`) se conservan.
5. No se relanza ningún proceso ni se reencola el trabajo.

## 3. Resultados inciertos

- El motor clasifica los resultados ambiguos en `UNCERTAIN_RESULTS`
  (`unconfirmed`).
- La bandeja los muestra como no confirmados y **no** los reintenta.
- `--force` es la única vía para repetir una operación incierta y debe ser una
  decisión humana.
- Un fallo de undo no borra el hecho de que el repost sigue activo; el estado
  se mantiene como corresponde.

## 4. Historial y backups

- El historial se escribe de forma atómica; un corte no deja una línea a
  medias.
- `--diagnose` detecta líneas corruptas y eventos inválidos.
- `--backup` crea una copia con checksum SHA-256 en `history-backups/`.
- `--restore RUTA` verifica el checksum antes de restaurar; `--force` permite
  restaurar una copia alterada de forma consciente.
- La restauración no toca las cuentas ni los perfiles de Chrome.

## 5. Recuperación de archivos de estado

- `xrepost_store.JsonStore` valida el JSON y usa escritura atómica
  (temporal + `fsync` + `os.replace`) con bloqueo.
- `xrepost_fs` rechaza symlinks, archivos de otro propietario y rutas fuera del
  directorio de datos.
- Un archivo corrupto se reporta; no se reemplaza por valores por defecto sin
  avisar.

## 6. Qué no se hace

- No se marca un trabajo interrumpido como `COMPLETED`.
- No se considera `FAILED` automáticamente: podría haber funcionado.
- No se borran historiales, perfiles ni cuentas para “limpiar” el estado.
- No se ejecutan reposts de recuperación.

## 7. Pruebas

- `HistoryIntegrityTest`: líneas corruptas, rotación, backup manipulado,
  restauración forzada y diagnóstico.
- `JobsTest`: recuperación de `RUNNING`/`QUEUED` como `INTERRUPTED` y poda.
- `FilesystemHardeningTest`: escritura atómica, permisos, symlinks y archivos
  de tamaño excesivo.
- `web/test_app.py`: reconstrucción de la aplicación y estado de trabajos.
