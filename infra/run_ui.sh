#!/bin/bash
# Launch the TaxAgent chat web UI. Talks to the model serve via TAXAGENT_BASE_URL
# (default http://127.0.0.1:8011/v1 — start it with infra/serve_35b_mvp.sh first).
set -euo pipefail
cd "$(dirname "$0")/.."
HOST=${TAXAGENT_UI_HOST:-127.0.0.1}
PORT=${TAXAGENT_UI_PORT:-8055}
exec .venv/bin/python -m uvicorn taxagent.web.app:app --host "$HOST" --port "$PORT"
