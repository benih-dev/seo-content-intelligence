#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
pids=()
cleanup() { if ((${#pids[@]})); then kill "${pids[@]}" 2>/dev/null || true; fi; }
trap cleanup EXIT INT TERM
(cd backend && uv sync --frozen --python 3.12 && uv run alembic upgrade head)
(cd frontend && npm ci)
(cd backend && exec uv run uvicorn seoci.api.main:app --host 127.0.0.1 --port 8000) & pids+=("$!")
(cd backend && exec uv run python -m seoci.worker) & pids+=("$!")
(cd frontend && exec npm run dev) & pids+=("$!")
wait
