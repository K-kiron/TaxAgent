#!/bin/bash
# Launch the TaxAgent chat web UI. Talks to the model serve via TAXAGENT_BASE_URL
# (default http://127.0.0.1:8011/v1 — start it with infra/serve_35b_mvp.sh first).
set -euo pipefail
cd "$(dirname "$0")/.."
HOST=${TAXAGENT_UI_HOST:-127.0.0.1}
PORT=${TAXAGENT_UI_PORT:-8055}
if [[ "$HOST" != "127.0.0.1" && "$HOST" != "localhost" && "${TAXAGENT_ALLOW_PUBLIC_BIND:-0}" != "1" ]]; then
  echo "Refusing to bind TaxAgent demo UI to $HOST." >&2
  echo "Use a tunnel to http://127.0.0.1:$PORT, or set TAXAGENT_ALLOW_PUBLIC_BIND=1 only if you accept the risk." >&2
  exit 2
fi
exec .venv/bin/python -m uvicorn taxagent.web.app:app --host "$HOST" --port "$PORT"
