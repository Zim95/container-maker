#!/bin/bash

# Ensure Poetry uses the virtualenv at /opt/venv (not overwritten by volume mount)
# The virtualenv is created during Docker build and persists across volume mounts
VENV_PYTHON=$(find /opt/venv -name python -type f 2>/dev/null | head -1)
if [ -n "$VENV_PYTHON" ] && [ -f "$VENV_PYTHON" ]; then
    poetry env use "$VENV_PYTHON" 2>/dev/null || true
    # Add the correct virtualenv to PATH (prioritize /opt/venv over /app/.venv)
    VENV_BIN=$(dirname "$VENV_PYTHON")
    export PATH="$VENV_BIN:$PATH"
else
    echo "Virtualenv not found. Installing dependencies..."
    poetry install --no-root
fi

# Start Jupyter notebook in the background using Poetry
poetry run jupyter notebook --ip 0.0.0.0 --no-browser --allow-root &

# Run the main application using Poetry
poetry run python app.py --use_ssl true
