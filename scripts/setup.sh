#!/usr/bin/env bash
# One-time local setup: virtualenv, dependencies, and a local catalogue database
# loaded from the committed snapshot. Everything lives inside this folder.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || { echo "Python 3.10+ is required"; exit 1; }

[ -d .venv ] || "$PY" -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e ".[dev]"

if [ ! -f data/catalog.db ]; then
  echo "Creating data/catalog.db from seed/catalog.jsonl.gz ..."
  python -m jainfriendly.catalog load seed/catalog.jsonl.gz
fi
python -m pytest -q
echo
echo "Done. Start the app with: scripts/run.sh   (then open http://localhost:8000)"
