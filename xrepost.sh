#!/usr/bin/env bash
# xrepost — repostea posts de usuarios concretos en un rango de fechas.
#
# Uso:
#   ./xrepost.sh                          # interactivo (pregunta usuarios, fechas y alcance)
#   ./xrepost.sh <usuarios> <desde> [hasta]
#
# Fechas (modo interactivo): campo DD/MM/AAAA con avance automático (las barras
# se insertan solas y al escribir el octavo dígito se acepta). Enter acepta el
# valor entre corchetes; se valida el calendario y que desde <= hasta.
# Por argumentos se acepta DD/MM/AAAA (recomendado) o AAAA-MM-DD.
#
# Retweets: en modo interactivo se pregunta si se incluyen los retweets que las
# cuentas hayan hecho de otras cuentas. Por defecto solo se consideran las
# publicaciones originales (X_SKIP_RETWEETS=1).
#
# Cuentas: el modo interactivo sugiere las cuentas usadas antes mientras se
# escribe (↑/↓ elige, Tab completa, Enter acepta). Se guardan junto al historial.
# Citas: --quote "#ETECSA" repostea con cita y ese comentario; cada palabra se
# normaliza a hashtag y los usados quedan recordados para el panel web.
#
# Opciones:
#   --csv RUTA          exportar el listado a CSV
#   --md RUTA           exportar el listado a Markdown
#   --quote "#tag"      repost con cita: publica ese comentario (admite varios
#                       hashtags: --quote "#ETECSA #Cuba")
#   --force             ignorar el historial (repostea aunque ya conste)
#   --history [N]       ver los últimos N movimientos (20 por defecto)
#   --undo-last [N]     deshacer la última tanda (o los últimos N reposts)
#   --undo URL|ID       deshacer un repost concreto
#   --stats [DÍAS]      estadísticas reales del historial (30 días por defecto)
#   --diagnose          integridad del historial y del entorno
#   --backup [RUTA]     copia verificable del historial (y archivos rotados)
#   --restore RUTA      restaurar un backup verificado
#   --strict-cdp        exigir que CDP sea local y del perfil de xrepost
#   --version           versión y rutas efectivas
#   -h, --help          esta ayuda
#
# Variables opcionales:
#   X_APPLY=1      repostear de verdad (por defecto solo lista)
#   X_LIMIT=5      máximo de reposts por ejecución
#   X_DELAY=30     segundos entre reposts
#   X_SKIP_REPLIES=0  incluir respuestas (por defecto se ignoran)
#   X_SKIP_RETWEETS=0 incluir retweets (por defecto se ignoran)
#   X_MATCH=a,b    solo posts que contengan alguna de esas palabras
#   X_EXCLUDE=c,d  descartar posts que contengan alguna
#   X_QUOTE="#tag" repost con cita y ese comentario (igual que --quote)
#   X_ACCOUNTS=... archivo de cuentas recordadas (por defecto, junto al historial)
#   X_HASHTAGS=... archivo de hashtags recordados (por defecto, junto al historial)
#   BU_CDP_URL=... endpoint de Chrome (default http://127.0.0.1:9222)
#
# Historial: ~/.local/state/xrepost/history.jsonl (cambiable con X_HISTORY)
# Cuentas:   ~/.local/state/xrepost/accounts.json  (cambiable con X_ACCOUNTS)
# Hashtags:  ~/.local/state/xrepost/hashtags.json  (cambiable con X_HASHTAGS)

set -euo pipefail
umask 077

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
# El motor se ejecuta por stdin y no tiene `__file__`: le decimos dónde está el
# proyecto para que pueda importar xrepost_labels.py (etiquetas compartidas).
export X_SELF_DIR="$SELF_DIR"
export X_HISTORY="${X_HISTORY:-${XDG_STATE_HOME:-$HOME/.local/state}/xrepost/history.jsonl}"

usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

# --- entrada interactiva ----------------------------------------------------

# Valida una fecha AAAA-MM-DD real (incluye meses y días del calendario).
valid_date() {
  local d="$1" y m day
  [[ "$d" =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})$ ]] || return 1
  y="${BASH_REMATCH[1]}"
  m="${BASH_REMATCH[2]}"
  day="${BASH_REMATCH[3]}"
  (( 10#$y >= 2006 && 10#$y <= 2100 )) || return 1
  (( 10#$m >= 1 && 10#$m <= 12 )) || return 1
  (( 10#$day >= 1 && 10#$day <= 31 )) || return 1
  [ "$(date -d "$d" +%F 2>/dev/null)" = "$d" ]
}

# Acepta DD/MM/AAAA (lo que ve el usuario) o AAAA-MM-DD y devuelve ISO.
# El resto del programa (búsqueda en X, historial, panel web) trabaja en ISO.
to_iso() {
  local v="$1" d m y
  if [[ "$v" =~ ^([0-9]{2})/([0-9]{2})/([0-9]{4})$ ]]; then
    d="${BASH_REMATCH[1]}"; m="${BASH_REMATCH[2]}"; y="${BASH_REMATCH[3]}"
  elif [[ "$v" =~ ^([0-9]{4})-([0-9]{2})-([0-9]{2})$ ]]; then
    y="${BASH_REMATCH[1]}"; m="${BASH_REMATCH[2]}"; d="${BASH_REMATCH[3]}"
  else
    return 1
  fi
  local iso="$y-$m-$d"
  valid_date "$iso" || return 1
  printf '%s' "$iso"
}

# ISO -> DD/MM/AAAA, solo para mensajes al usuario.
to_dmy() {
  printf '%s/%s/%s' "${1:8:2}" "${1:5:2}" "${1:0:4}"
}

# Máscara DD/MM/AAAA para dibujar el campo mientras se escribe.
format_mask() {
  local d="$1" day="${1:0:2}" mon="${1:2:2}" y="${1:4:4}"
  while [ ${#day} -lt 2 ]; do day+="_"; done
  while [ ${#mon} -lt 2 ]; do mon+="_"; done
  while [ ${#y} -lt 4 ]; do y+="_"; done
  printf '%s/%s/%s' "$day" "$mon" "$y"
}

# Campo de fecha con avance automático. $1 = etiqueta, $2 = valor por defecto.
# Los guiones se insertan solos; al completar 8 dígitos se valida y se acepta.
# Enter acepta el valor por defecto (si lo hay) o confirma una fecha completa.
# Deja el resultado en READ_DATE; devuelve 1 si no hay entrada (EOF).
read_date() {
  local label="$1" def="${2:-}" digits="" ch msg="" tty=0 drain=0 skip_def=0
  if [ -t 0 ] && [ -t 1 ]; then tty=1; fi

  if [ "$tty" = 0 ]; then
    printf '  %s' "$label"
    if [ -n "$def" ]; then printf ' [%s]' "$def"; fi
    printf ': '
  fi

  while :; do
    if [ "$tty" = 1 ]; then
      printf '\r\033[K  %s' "$label"
      if [ -n "$def" ]; then printf ' [%s]' "$def"; fi
      printf ': %s' "$(format_mask "$digits")"
      if [ -n "$msg" ]; then printf '  (%s)' "$msg"; fi
    elif [ -n "$msg" ]; then
      printf '\n  (%s)\n  %s' "$msg" "$label"
      if [ -n "$def" ]; then printf ' [%s]' "$def"; fi
      printf ': '
    fi
    msg=""

    if ! IFS= read -rsn1 ch; then
      printf '\n'
      return 1
    fi

    case "$ch" in
      "")
        if [ "$skip_def" = "1" ]; then
          skip_def=0
          msg="escribe la fecha"
          continue
        fi
        if [ -z "$digits" ] && [ -n "$def" ]; then
          digits="${def//[^0-9]/}"
          break
        fi
        if [ ${#digits} -eq 8 ] && to_iso "$(format_mask "$digits")" >/dev/null; then
          break
        fi
        msg="fecha incompleta: faltan dígitos"
        ;;
      [0-9])
        skip_def=0
        digits+="$ch"
        ;;
      -|/|' '|:|.)
        ;;
      $'\x7f'|$'\b')
        digits="${digits%?}"
        ;;
      *)
        msg="solo se admiten números"
        ;;
    esac

    if [ ${#digits} -eq 8 ]; then
      if to_iso "$(format_mask "$digits")" >/dev/null; then
        drain=1
        break
      fi
      digits=""
      skip_def=1
      msg="fecha no válida; vuelve a escribirla"
    fi
  done

  READ_DATE="$(format_mask "$digits")"
  if [ "$tty" = 1 ]; then
    printf '\r\033[K  %s' "$label"
    if [ -n "$def" ]; then printf ' [%s]' "$def"; fi
    printf ': %s\n' "$READ_DATE"
  else
    printf '%s\n' "$READ_DATE"
  fi
  # Si el usuario pulsó Enter después del octavo dígito, descartarlo para que
  # no lo consuma el siguiente campo. Tras un Enter explícito no hay nada que
  # descartar: ese salto de línea ya lo consumió la lectura.
  if [ "$drain" = "1" ]; then
    IFS= read -rsn1 -t 0.15 _ 2>/dev/null || true
  fi
}

# Pregunta el alcance: solo publicaciones originales o también retweets.
ask_scope() {
  local ans
  cat <<'TXT'

Alcance de las publicaciones
  Indique qué publicaciones de las cuentas seleccionadas desea considerar:

    1) Solo publicaciones originales (recomendado)
       Se excluyen los retweets que esas cuentas hayan hecho de otras cuentas.

    2) Publicaciones originales y retweets de otras cuentas
       Se incluyen también esos retweets; al repostear, se repostea la
       publicación original, no el retweet.

TXT
  while :; do
    printf '  Seleccione una opción [1/2] (Enter = 1): '
    read -r ans || ans=""
    case "${ans:-1}" in
      1) X_SKIP_RETWEETS=1; break ;;
      2) X_SKIP_RETWEETS=0; break ;;
      *) echo "  Opción no válida: escriba 1 o 2." ;;
    esac
  done
  if [ "$X_SKIP_RETWEETS" = "1" ]; then
    echo "  → Alcance: solo publicaciones originales (retweets omitidos)."
  else
    echo "  → Alcance: publicaciones originales y retweets de otras cuentas."
  fi
}

MODE="repost"
UNDO_TARGET=""
UNDO_N=""
HISTORY_N=""
STATS_DAYS="30"
BACKUP_DEST=""
RESTORE_PATH=""
STRICT_CDP=0
CSV=""
MD=""
QUOTE="${X_QUOTE:-}"
FORCE=0
POS=()

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage; exit 0 ;;
    --version)
      printf 'xrepost 2.0\nproyecto: %s\nhistorial: %s\n' "$SELF_DIR" "$X_HISTORY"
      exit 0 ;;
    --stats)
      MODE="stats"; shift
      if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then STATS_DAYS="$1"; shift; fi ;;
    --diagnose)
      MODE="diagnose"; shift ;;
    --backup)
      MODE="backup"; shift
      if [ $# -gt 0 ] && [[ "$1" != -* ]]; then BACKUP_DEST="$1"; shift; fi ;;
    --restore)
      [ $# -ge 2 ] || { echo "Falta la ruta de --restore" >&2; exit 1; }
      MODE="restore"; RESTORE_PATH="$2"; shift 2 ;;
    --strict-cdp)
      STRICT_CDP=1; shift ;;
    --csv)
      [ $# -ge 2 ] || { echo "Falta la ruta de --csv" >&2; exit 1; }
      CSV="$2"; shift 2 ;;
    --md)
      [ $# -ge 2 ] || { echo "Falta la ruta de --md" >&2; exit 1; }
      MD="$2"; shift 2 ;;
    --quote)
      [ $# -ge 2 ] || { echo "Falta el texto de --quote" >&2; exit 1; }
      QUOTE="$2"; shift 2 ;;
    --force)
      FORCE=1; shift ;;
    --history)
      MODE="history"; shift
      if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then HISTORY_N="$1"; shift; fi ;;
    --undo-last)
      MODE="undo_last"; shift
      if [ $# -gt 0 ] && [[ "$1" =~ ^[0-9]+$ ]]; then UNDO_N="$1"; shift; fi ;;
    --undo)
      [ $# -ge 2 ] || { echo "Falta la URL o el ID de --undo" >&2; exit 1; }
      MODE="undo"; UNDO_TARGET="$2"; shift 2 ;;
    --)
      shift; POS+=("$@"); break ;;
    -*)
      echo "Opción desconocida: $1 (usa --help)" >&2; exit 1 ;;
    *)
      POS+=("$1"); shift ;;
  esac
done

export X_MODE="$MODE" X_UNDO_TARGET="$UNDO_TARGET" X_UNDO_N="$UNDO_N"

if [ "$MODE" = "history" ]; then
  python3 - "$X_HISTORY" "${HISTORY_N:-20}" "$SELF_DIR" <<'PY'
import json, sys

sys.path.append(sys.argv[3])
from xrepost_labels import LABELS

path, n = sys.argv[1], max(0, int(sys.argv[2] or 20))
try:
    with open(path, encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]
except FileNotFoundError:
    print(f"Sin historial todavía: {path}")
    raise SystemExit(0)
except OSError as e:
    print(f"No se pudo leer el historial ({path}): {e}")
    raise SystemExit(0)
sel = lines[-n:] if n else []
print(f"Historial: {path} ({len(lines)} eventos); mostrando {len(sel)}\n")
for line in sel:
    try:
        e = json.loads(line)
    except ValueError:
        continue
    handle = ("@" + e["handle"]) if e.get("handle") else ""
    result = e.get("result", "")
    ts = e.get("ts", "")
    disp = f"{ts[8:10]}/{ts[5:7]}/{ts[0:4]} {ts[11:16]}" if len(ts) >= 16 else ts
    print(f"{disp}  {e.get('action', ''):6} "
          f"{LABELS.get(result, result):24} {handle:18} {e.get('url', '')}")
PY
  exit 0
fi

if [ "$MODE" = "stats" ] || [ "$MODE" = "diagnose" ] || [ "$MODE" = "backup" ] || [ "$MODE" = "restore" ]; then
  python3 - "$MODE" "$X_HISTORY" "$SELF_DIR" "$STATS_DAYS" "$BACKUP_DEST" "$RESTORE_PATH" <<'PY'
import json, sys

mode, history, self_dir, days, backup_dest, restore_path = sys.argv[1:7]
sys.path.insert(0, self_dir)
import xrepost_history
import xrepost_stats

if mode == "stats":
    data = xrepost_stats.compute(history, days=max(1, min(int(days or 30), 365)))
    print(f"Historial: {history}")
    print(f"Eventos: {data['total_events']} | confirmados: {data['confirmed_total']} | "
          f"deshechos: {data['undone']} | fallos: {data['failed']} | sin confirmar: {data['unknown']}")
    print(f"Tasa de confirmación: {data['confirmation_rate']}% "
          f"({data['confirmed_total']}/{data['rate_denominator']})")
    print(f"Trabajos: {data['jobs']}")
    for item in data["by_account"][:10]:
        print(f"  @{item['handle']}: reposts={item['reposts']} citas={item['quotes']} "
              f"deshechos={item['undone']} fallos={item['failed']} último={item['last']}")
elif mode == "diagnose":
    report = xrepost_history.diagnose(history)
    print(json.dumps(report, ensure_ascii=False, indent=2))
elif mode == "backup":
    dest = backup_dest or None
    report = xrepost_history.backup(history, dest=dest)
    print("Backup creado:")
    print(json.dumps(report, ensure_ascii=False, indent=2))
elif mode == "restore":
    if not restore_path:
        print("Falta la ruta del backup", file=sys.stderr)
        raise SystemExit(2)
    report = xrepost_history.restore(history, restore_path)
    print("Restauración completada:")
    print(json.dumps(report, ensure_ascii=False, indent=2))
PY
  exit $?
fi

if [ "$MODE" = "repost" ]; then
  if [ ${#POS[@]} -ge 2 ]; then
    export X_USERS="${POS[0]}"
    export X_FROM="${POS[1]}"
    export X_TO="${POS[2]:-${POS[1]}}"
  elif [ ${#POS[@]} -eq 1 ]; then
    echo "Faltan la fecha (o usa --help)." >&2
    exit 1
  elif [ -n "${X_USERS:-}" ] && [ -n "${X_FROM:-}" ]; then
    export X_USERS X_FROM
    export X_TO="${X_TO:-$X_FROM}"
  else
    echo "=== xrepost ==="
    if [ -t 0 ] && [ -t 1 ]; then
      if ! X_USERS="$(python3 "$SELF_DIR/xrepost_accounts.py" prompt)"; then
        echo "Entrada cancelada." >&2
        exit 1
      fi
    else
      read -r -p "Usuarios (separados por coma, @ opcional): " X_USERS || X_USERS=""
    fi
    if [ -z "${X_USERS// /}" ]; then
      echo "Debes indicar al menos un usuario." >&2
      exit 1
    fi

    _today="$(date +%d/%m/%Y)"
    echo
    echo "Fechas (DD/MM/AAAA): escribe los 8 dígitos seguidos; las barras se añaden solas."
    echo "Enter acepta el valor entre corchetes."
    while :; do
      if ! read_date "Fecha desde" "$_today"; then
        echo "Entrada cancelada." >&2
        exit 1
      fi
      X_FROM="$(to_iso "$READ_DATE")"

      if ! read_date "Fecha hasta (Enter = la misma)" "$READ_DATE"; then
        echo "Entrada cancelada." >&2
        exit 1
      fi
      X_TO="$(to_iso "$READ_DATE")"

      if [[ "$X_FROM" > "$X_TO" ]]; then
        echo "  La fecha inicial ($(to_dmy "$X_FROM")) es posterior a la final ($(to_dmy "$X_TO")). Inténtalo de nuevo."
        continue
      fi
      break
    done

    if [ -n "${X_SKIP_RETWEETS:-}" ]; then
      if [ "$X_SKIP_RETWEETS" = "0" ]; then
        echo
        echo "  Alcance (X_SKIP_RETWEETS=0): se incluyen retweets de otras cuentas."
      else
        echo
        echo "  Alcance (X_SKIP_RETWEETS=1): solo publicaciones originales."
      fi
    else
      ask_scope
    fi

    export X_USERS X_FROM X_TO
  fi

  if [ -z "${X_USERS:-}" ] || [ -z "${X_FROM:-}" ]; then
    echo "Faltan usuarios o fecha." >&2
    exit 1
  fi

  for _var in X_FROM X_TO; do
    _raw="${!_var}"
    if ! _iso="$(to_iso "$_raw")"; then
      echo "Fecha no válida: '$_raw'. Formato esperado: DD/MM/AAAA." >&2
      exit 1
    fi
    printf -v "$_var" '%s' "$_iso"
  done
  if [[ "$X_FROM" > "$X_TO" ]]; then
    echo "La fecha inicial ($(to_dmy "$X_FROM")) es posterior a la final ($(to_dmy "$X_TO"))." >&2
    exit 1
  fi

  if [ -n "$QUOTE" ]; then
    _clean="$(python3 "$SELF_DIR/xrepost_hashtags.py" clean "$QUOTE" 2>/dev/null || true)"
    if [ -z "$_clean" ]; then
      echo "El comentario de la cita debe contener al menos un hashtag, por ejemplo #ETECSA." >&2
      exit 1
    fi
    if [ "${#_clean}" -gt 280 ]; then
      echo "El comentario de la cita es demasiado largo (máximo 280 caracteres)." >&2
      exit 1
    fi
    QUOTE="$_clean"
  fi
fi

export X_APPLY="${X_APPLY:-0}"
export X_LIMIT="${X_LIMIT:-10}"
export X_DELAY="${X_DELAY:-20}"
export X_SKIP_REPLIES="${X_SKIP_REPLIES:-1}"
export X_SKIP_RETWEETS="${X_SKIP_RETWEETS:-1}"
export X_MATCH="${X_MATCH:-}"
export X_EXCLUDE="${X_EXCLUDE:-}"
export X_EXACT="${X_EXACT:-}"
export X_INCLUDE_REGEX="${X_INCLUDE_REGEX:-}"
export X_EXCLUDE_REGEX="${X_EXCLUDE_REGEX:-}"
export X_LANG="${X_LANG:-}"
export X_HASHTAGS_FILTER="${X_HASHTAGS_FILTER:-}"
export X_MIN_LEN="${X_MIN_LEN:-}"
export X_MAX_LEN="${X_MAX_LEN:-}"
export X_MEDIA="${X_MEDIA:-}"
export X_VIDEO="${X_VIDEO:-}"
export X_KIND="${X_KIND:-}"
export X_QUOTE="$QUOTE"
export X_FORCE="$FORCE"
export X_CSV="$CSV"
export X_MD="$MD"
export BU_CDP_URL="${BU_CDP_URL:-http://127.0.0.1:9222}"

if [ "$STRICT_CDP" = "1" ] && [ "$MODE" != "history" ]; then
  if ! python3 "$SELF_DIR/xrepost_cdp.py" --url "$BU_CDP_URL"; then
    echo "CDP no cumple las condiciones de seguridad; no se ejecuta." >&2
    exit 1
  fi
fi

# Una sola ejecución a la vez: el CLI y el panel comparten Chrome y el
# historial, y dos tandas simultáneas podrían repostear lo mismo dos veces.
if [ "$MODE" != "history" ] && command -v flock >/dev/null 2>&1; then
  _lock="${X_HISTORY}.lock"
  mkdir -p "$(dirname "$_lock")" 2>/dev/null || true
  exec 9>"$_lock"
  if ! flock -n 9; then
    echo "Hay otra ejecución de xrepost en curso ($_lock). Espera a que termine." >&2
    exit 1
  fi
fi

# Recordar las cuentas y los hashtags para las próximas sugerencias (CLI y panel).
if [ "$MODE" = "repost" ] && [ -n "${X_USERS:-}" ]; then
  python3 "$SELF_DIR/xrepost_accounts.py" add "$X_USERS" >/dev/null 2>&1 || true
fi
if [ "$MODE" = "repost" ] && [ -n "${X_QUOTE:-}" ]; then
  python3 "$SELF_DIR/xrepost_hashtags.py" add "$X_QUOTE" >/dev/null 2>&1 || true
fi

if [ "$MODE" = "repost" ] && [ "$X_APPLY" != "1" ]; then
  echo
  echo "AVISO: modo DRY-RUN. Para repostear de verdad: X_APPLY=1 $0 ..."
  echo
fi

exec browser-use < "$SELF_DIR/xrepost.py"