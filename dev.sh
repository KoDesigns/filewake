#!/usr/bin/env bash

set -Eeuo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
host="${DEV_HOST:-127.0.0.1}"
api_port="${API_PORT:-8080}"
frontend_port="${FRONTEND_PORT:-5173}"
api_pid=""
frontend_pid=""

shutdown() {
  trap - EXIT

  if [[ -n "$api_pid" ]]; then
    kill "$api_pid" 2>/dev/null || true
  fi
  if [[ -n "$frontend_pid" ]]; then
    kill "$frontend_pid" 2>/dev/null || true
  fi

  if [[ -n "$api_pid" ]]; then
    wait "$api_pid" 2>/dev/null || true
  fi
  if [[ -n "$frontend_pid" ]]; then
    wait "$frontend_pid" 2>/dev/null || true
  fi
}

handle_signal() {
  shutdown
  exit 130
}

trap shutdown EXIT
trap handle_signal INT TERM

if [[ ! -x "$project_dir/.venv/bin/uvicorn" ]]; then
  echo "Missing Python environment. Run:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt" >&2
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  echo "Node is required. Install the version declared in frontend/package.json." >&2
  exit 1
fi

if [[ ! -x "$project_dir/frontend/node_modules/.bin/vite" ]]; then
  echo "Missing frontend dependencies. Run:" >&2
  echo "  cd frontend && npm ci" >&2
  exit 1
fi

cd "$project_dir"

"$project_dir/.venv/bin/uvicorn" backend.main:app \
  --host "$host" \
  --port "$api_port" \
  --reload &
api_pid=$!

(
  cd "$project_dir/frontend"
  export API_PORT="$api_port"
  exec "$project_dir/frontend/node_modules/.bin/vite" \
    --host "$host" \
    --port "$frontend_port" \
    --strictPort
) &
frontend_pid=$!

echo
echo "Filewake is starting:"
echo "  UI:  http://$host:$frontend_port"
echo "  API: http://$host:$api_port/api/health"
echo
echo "Press Ctrl+C to stop both servers."

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
  sleep 1
done

set +e
if ! kill -0 "$api_pid" 2>/dev/null; then
  wait "$api_pid"
  exit_status=$?
  echo "API server stopped unexpectedly (status $exit_status)." >&2
else
  wait "$frontend_pid"
  exit_status=$?
  echo "Frontend server stopped unexpectedly (status $exit_status)." >&2
fi
set -e

exit "$exit_status"
