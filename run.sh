#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${VENV_PATH:-$PROJECT_ROOT/backend/.venv}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"
OPEN_BROWSER="${OPEN_BROWSER:-1}"

[[ -x "$VENV_PATH/bin/python" ]] || {
  echo "Python environment not found at $VENV_PATH. Run ./install.sh first." >&2
  exit 1
}
[[ -f "$PROJECT_ROOT/frontend/dist/index.html" ]] || {
  echo "Frontend build not found. Run ./install.sh first." >&2
  exit 1
}

echo "Applying database migrations..."
(cd "$PROJECT_ROOT/backend" && "$VENV_PATH/bin/python" -m alembic upgrade head)

export SERVE_FRONTEND=1
export FRONTEND_DIST_DIR="$PROJECT_ROOT/frontend/dist"
export DB_MIGRATION_MODE=check

APP_URL="http://$APP_HOST:$APP_PORT"
if [[ "$APP_HOST" == "0.0.0.0" ]]; then
  APP_URL="http://localhost:$APP_PORT"
fi

echo "Math Book Translator is available at $APP_URL"
echo "Press Ctrl+C to stop."

if [[ "$OPEN_BROWSER" == "1" ]]; then
  (
    sleep 2
    if command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$APP_URL" >/dev/null 2>&1 || true
    elif command -v open >/dev/null 2>&1; then
      open "$APP_URL" >/dev/null 2>&1 || true
    fi
  ) &
fi

cd "$PROJECT_ROOT/backend"
exec "$VENV_PATH/bin/python" -m uvicorn app.main:app --host "$APP_HOST" --port "$APP_PORT"
