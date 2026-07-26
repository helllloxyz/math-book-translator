#!/bin/bash
echo "Starting Math Book Translator..."

# Start backend
echo "Starting backend server..."
cd backend
VENV_PATH=${VENV_PATH:-"$HOME/agent"}
source "$VENV_PATH/bin/activate"

RUN_DB_MIGRATIONS=${RUN_DB_MIGRATIONS:-1}
if [ "$RUN_DB_MIGRATIONS" = "1" ]; then
  echo "Applying database migrations..."
  alembic upgrade head || exit 1
else
  echo "Skipping database migrations (RUN_DB_MIGRATIONS=$RUN_DB_MIGRATIONS)"
fi

DB_MIGRATION_MODE=${DB_MIGRATION_MODE:-off}
export DB_MIGRATION_MODE
uvicorn app.main:app &
BACKEND_PID=$!
cd ..

# Start frontend
echo "Starting frontend development server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Cleanup function to kill background processes
cleanup() {
  echo ""
  echo "Stopping servers..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  exit
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

echo "Waiting for servers to start..."
sleep 5 # Give servers some time to spin up

# Open in browser
FRONTEND_URL="http://localhost:5173"
echo "Opening application in browser: $FRONTEND_URL"
# Detect OS and open browser accordingly
if command -v xdg-open > /dev/null; then
  xdg-open $FRONTEND_URL
elif command -v open > /dev/null; then
  open $FRONTEND_URL
elif command -v start > /dev/null; then
  start $FRONTEND_URL
else
  echo "Could not automatically open browser. Please navigate to $FRONTEND_URL manually."
fi

echo "Math Book Translator is running. Press Ctrl+C to stop servers."

# Keep the script running until manually stopped, to keep child processes alive
wait $BACKEND_PID $FRONTEND_PID
