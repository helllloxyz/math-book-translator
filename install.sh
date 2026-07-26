#!/bin/bash

echo "Starting environment installation..."

# Check Python version (3.10+ required)
if command -v python3.10 > /dev/null; then
  PYTHON_BIN="python3.10"
elif command -v python3 > /dev/null; then
  PYTHON_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
  PYTHON_MAJOR=$(echo "$PYTHON_VER" | cut -d '.' -f 1)
  PYTHON_MINOR=$(echo "$PYTHON_VER" | cut -d '.' -f 2)
  if [ "$PYTHON_MAJOR" -gt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; }; then
    PYTHON_BIN="python3"
  else
    echo "Error: Python 3.10+ is required. Current python3 is $PYTHON_VER."
    echo "Please install Python 3.10+ and re-run this script."
    exit 1
  fi
else
  echo "Error: Python 3.10+ is not installed."
  exit 1
fi

# Check Node.js version
if command -v node > /dev/null; then
  NODE_VER=$(node -v | cut -d 'v' -f 2)
  NODE_MAJOR=$(echo $NODE_VER | cut -d '.' -f 1)
  if [ "$NODE_MAJOR" -lt 20 ]; then
    echo "Error: Node.js version 20.19+ or 22.12+ is required. Current version is $NODE_VER."
    exit 1
  fi
else
  echo "Error: Node.js is not installed."
  exit 1
fi

# Install backend dependencies
echo "Installing backend dependencies..."
VENV_PATH=${VENV_PATH:-"$HOME/agent"}
echo "Creating virtual environment at $VENV_PATH..."
$PYTHON_BIN -m venv "$VENV_PATH"
source "$VENV_PATH/bin/activate"
cd backend
pip install -r requirements.txt
deactivate
cd ..

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo "Environment installation complete."
