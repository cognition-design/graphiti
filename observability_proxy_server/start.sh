#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check if required environment variables are set
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "Error: OPENROUTER_API_KEY is not set. Please check your .env file."
    exit 1
fi

if [ -z "$LANGFUSE_SECRET_KEY" ] || [ -z "$LANGFUSE_PUBLIC_KEY" ]; then
    echo "Error: Langfuse API keys are not set. Please check your .env file."
    exit 1
fi

# Set default port if not specified
PORT=${PORT:-8000}

echo "Starting OpenRouter Proxy Server with Langfuse observability..."
echo "Server will be available at: http://localhost:$PORT"
echo "Health check: http://localhost:$PORT/health"

# Start the server
uvicorn server:app --host 0.0.0.0 --port $PORT --reload
