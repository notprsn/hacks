#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo
echo "📎 Clippy setup"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed."
  echo "Install it from https://www.python.org/downloads/ and run this file again."
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "Clippy needs Python 3.10 or newer."
  echo "Update Python at https://www.python.org/downloads/ and run this file again."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "1/2 · Creating Clippy's private setup…"
  python3 -m venv .venv
fi

echo "2/2 · Installing or updating Clippy…"
.venv/bin/python -m pip install --quiet --disable-pip-version-check --upgrade -r requirements.txt

echo
echo "Setup complete. Opening Clippy…"
echo "Keep this window open while you use it. Press Ctrl+C here to stop."
echo

exec .venv/bin/python clippy.py
