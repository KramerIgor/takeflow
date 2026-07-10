#!/usr/bin/env bash

set +e

cd "$(dirname "$0")/.."

PORT="${PORT:-7860}"
HOST="${HOST:-127.0.0.1}"

if [ ! -x ".venv/bin/python" ]; then
  printf 'Virtualenv not found at .venv/bin/python\n'
  printf 'Create it and install requirements before starting the GUI.\n'
  exit 1
fi

printf 'Starting Takeflow at http://%s:%s\n' "$HOST" "$PORT"
printf 'Press Ctrl+C to stop.\n'

exec .venv/bin/python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
