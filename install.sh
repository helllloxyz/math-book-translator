#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${VENV_PATH:-$PROJECT_ROOT/backend/.venv}"

fail() {
  echo "Error: $*" >&2
  exit 1
}

echo "Installing Math Book Translator dependencies..."

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done
[[ -n "$PYTHON_BIN" ]] || fail "Python 3.10 or newer is required."

command -v node >/dev/null 2>&1 || fail "Node.js 22.12 or newer is required."
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major > 22 || (major === 22 && minor >= 12) ? 0 : 1)' \
  || fail "Node.js 22.12 or newer is required; found $(node --version)."
command -v npm >/dev/null 2>&1 || fail "npm is required."

echo "Using $($PYTHON_BIN --version) and Node.js $(node --version)."
echo "Creating Python virtual environment at $VENV_PATH..."
"$PYTHON_BIN" -m venv "$VENV_PATH"
"$VENV_PATH/bin/python" -m pip install --upgrade pip
"$VENV_PATH/bin/python" -m pip install -r "$PROJECT_ROOT/backend/requirements.txt"

echo "Installing locked frontend dependencies..."
npm --prefix "$PROJECT_ROOT/frontend" ci

echo "Building the frontend..."
npm --prefix "$PROJECT_ROOT/frontend" run build

echo "Installation complete. Run ./run.sh to start the local application."
