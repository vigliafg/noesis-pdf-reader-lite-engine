#!/usr/bin/env bash
# Quick launcher for the Noesis PDF Reader Lite engine TUI wizard (`-gui`).
#
# Usage:
#   ./tui.sh                     # open the wizard (file picker)
#   ./tui.sh libro.pdf           # preload a PDF
#   ./tui.sh libro.pdf --dst en  # any CLI option is forwarded
#
# Uses the repo-local .venv when present, otherwise falls back to python3.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PY="$DIR/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
    PY="$(command -v python3 || true)"
    if [[ -z "$PY" ]]; then
        echo "error: no python3 found" >&2
        exit 1
    fi
fi

if ! "$PY" -c "import textual" >/dev/null 2>&1; then
    echo "warning: 'textual' is not installed for $PY" >&2
    echo "         -gui will fall back to the line wizard." >&2
    echo "         install it with: $PY -m pip install -e \".[tui]\"" >&2
fi

exec "$PY" "$DIR/cli.py" -gui "$@"
