#!/bin/bash
# Start the MLX Embeddings Server

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Default port (can be overridden via environment variable)
export EMBEDDINGS_PORT=${EMBEDDINGS_PORT:-1234}

echo "Starting MLX Embeddings Server on port $EMBEDDINGS_PORT..."
python server.py
