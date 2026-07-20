#!/usr/bin/env bash
#
# SystemIQ dev launcher — starts the backend (FastAPI) and frontend (Vite)
# together. Press Ctrl+C once to stop both.
#
# Prerequisites (one-time setup, see README):
#   backend/.venv  must exist  (uv venv --python 3.12  &&  uv pip install -r requirements.txt)
#   Node.js installed          (npm)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

BACKEND_PID=""

cleanup() {
  echo
  echo "Shutting down SystemIQ..."
  if [[ -n "$BACKEND_PID" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
  fi
  echo "Stopped."
}
trap cleanup EXIT INT TERM

# ---------- Backend ----------
cd "$BACKEND"
if [[ ! -d .venv ]]; then
  echo "ERROR: backend/.venv not found."
  echo "Create it first:"
  echo "  cd backend && uv venv --python 3.12 && source .venv/bin/activate && uv pip install -r requirements.txt"
  exit 1
fi
# shellcheck disable=SC1091
source .venv/bin/activate
[[ -f .env ]] || cp .env.example .env

echo "==> Applying database migrations..."
alembic upgrade head

echo "==> Starting backend at http://localhost:8000 (docs: /docs)"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# ---------- Frontend ----------
cd "$FRONTEND"
[[ -f .env ]] || cp .env.example .env
if [[ ! -d node_modules ]]; then
  echo "==> Installing frontend dependencies (first run only)..."
  npm install
fi

echo "==> Starting frontend at http://localhost:5173"
echo "    Login: admin / admin123"
echo "    (Press Ctrl+C to stop both servers)"
npm run dev
