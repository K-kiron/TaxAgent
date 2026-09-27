#!/bin/bash
# Stop the TaxAgent MVP serve (the vLLM process bound to :8011).
set -uo pipefail
pids=$(pgrep -f "vllm serve /work/mingze/models/Qwen3.6-35B-A3B .*--port 8011" || true)
if [ -z "$pids" ]; then
  echo "no TaxAgent serve on :8011"
  exit 0
fi
echo "stopping serve pids: $pids"
kill $pids
sleep 3
pgrep -f "port 8011" >/dev/null && { echo "force killing"; pkill -9 -f "port 8011"; } || true
echo "done"
