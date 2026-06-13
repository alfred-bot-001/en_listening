#!/usr/bin/env bash
#
# One-shot dev launcher for ListenFlow.
#
#   ./dev.sh          # set up (if needed) and start API + Web together
#   ./dev.sh setup    # only install deps, start db/redis, run migrations
#   ./dev.sh api      # only start the backend (http://localhost:8000)
#   ./dev.sh web      # only start the frontend (http://localhost:3000)
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$ROOT/apps/api"
WEB_DIR="$ROOT/apps/web"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

check_tools() {
  command -v ffmpeg  >/dev/null || die "ffmpeg not found. Install it (macOS: brew install ffmpeg)."
  command -v uv      >/dev/null || die "uv not found. Install it: https://docs.astral.sh/uv/"
  command -v npm     >/dev/null || die "npm not found. Install Node.js."
  command -v docker  >/dev/null || die "docker not found. Install Docker Desktop."
}

setup() {
  check_tools

  if [ ! -f "$API_DIR/.env" ]; then
    info "Creating apps/api/.env from .env.example"
    cp "$ROOT/.env.example" "$API_DIR/.env"
  fi

  info "Starting PostgreSQL + Redis (docker compose)"
  (cd "$ROOT" && docker compose up -d postgres redis)

  info "Installing backend dependencies (uv sync)"
  (cd "$API_DIR" && uv sync --extra dev)

  info "Waiting for PostgreSQL to accept connections"
  for _ in $(seq 1 30); do
    if (cd "$ROOT" && docker compose exec -T postgres pg_isready -U listenflow >/dev/null 2>&1); then
      break
    fi
    sleep 1
  done

  info "Running database migrations (alembic upgrade head)"
  (cd "$API_DIR" && uv run alembic upgrade head)

  if [ ! -d "$WEB_DIR/node_modules" ]; then
    info "Installing frontend dependencies (npm install)"
    (cd "$WEB_DIR" && npm install)
  fi

  info "Setup complete."
}

run_api() {
  info "API → http://localhost:8000  (docs at /docs)"
  cd "$API_DIR" && exec uv run uvicorn listenflow.main:app --reload
}

run_web() {
  info "Web → http://localhost:3000"
  cd "$WEB_DIR" && exec npm run dev
}

run_both() {
  setup
  info "Starting API + Web (Ctrl-C to stop both)"
  (run_api) &
  API_PID=$!
  (run_web) &
  WEB_PID=$!
  trap 'kill "$API_PID" "$WEB_PID" 2>/dev/null || true' INT TERM EXIT
  wait
}

case "${1:-all}" in
  setup) setup ;;
  api)   run_api ;;
  web)   run_web ;;
  all)   run_both ;;
  *)     die "Unknown command: $1 (use: setup | api | web | all)" ;;
esac
