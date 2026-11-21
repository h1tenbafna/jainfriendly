#!/usr/bin/env bash
# Start the API + web app on http://localhost:8000 (catalogue at /, checker at /check, API docs at /docs).
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
exec uvicorn jainfriendly.api:app --reload --port "${PORT:-8000}" "$@"
