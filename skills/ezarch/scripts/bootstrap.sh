#!/bin/sh
set -eu
[ "$(uname -s)" = Darwin ] || { echo 'Use bootstrap.ps1 on Windows.' >&2; exit 2; }
EZARCH_SKILL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
EZARCH_NEXT_HOME=0
for EZARCH_ARG in "$@"; do
  if [ "$EZARCH_NEXT_HOME" = 1 ]; then EZARCH_HOME=$EZARCH_ARG; EZARCH_NEXT_HOME=0; fi
  if [ "$EZARCH_ARG" = --home ]; then EZARCH_NEXT_HOME=1; fi
done
EZARCH_CONFIG=${EZARCH_CONFIG:-"$HOME/Library/Application Support/EZarch/settings.json"}
if [ -z "${EZARCH_HOME:-}" ] && [ -f "$EZARCH_CONFIG" ]; then
  EZARCH_HOME=$(/usr/bin/plutil -extract home raw -o - "$EZARCH_CONFIG" 2>/dev/null || true)
fi
EZARCH_HOME=${EZARCH_HOME:-"$HOME/Library/Application Support/EZarch/runtime"}
export EZARCH_HOME
mkdir -p "$EZARCH_HOME/tools" "$EZARCH_HOME/cache" "$EZARCH_HOME/temp"
export UV_CACHE_DIR="$EZARCH_HOME/cache/uv" UV_PYTHON_INSTALL_DIR="$EZARCH_HOME/runtimes/python"
export UV_TOOL_DIR="$EZARCH_HOME/tools/uv-tools" TMPDIR="$EZARCH_HOME/temp"
if [ -x "$EZARCH_HOME/tools/uv" ]; then EZARCH_UV="$EZARCH_HOME/tools/uv"
elif command -v uv >/dev/null 2>&1; then EZARCH_UV=$(command -v uv)
else
  curl --fail --location --retry 2 --proto '=https' --tlsv1.2 https://astral.sh/uv/0.11.26/install.sh -o "$EZARCH_HOME/tools/install-uv.sh"
  UV_INSTALL_DIR="$EZARCH_HOME/tools" UV_NO_MODIFY_PATH=1 sh "$EZARCH_HOME/tools/install-uv.sh"
  EZARCH_UV="$EZARCH_HOME/tools/uv"
fi
export EZARCH_UV
exec "$EZARCH_UV" run --no-project --python 3.12 python "$EZARCH_SKILL_ROOT/scripts/bootstrap.py" "$@"
