# OpenRouter Proxy Server with Langfuse Observability

A FastAPI-based proxy server that forwards requests to OpenRouter API while providing comprehensive observability through Langfuse integration.

## Features

- **OpenRouter API Proxy**: Forwards `/models` and `/chat/completions` requests to OpenRouter
- **Langfuse Integration**: Automatic logging and tracing of all LLM interactions
- **Streaming Support**: Full SSE (Server-Sent Events) streaming support for real-time responses
- **Session Tracking**: Extract session IDs from request metadata for better tracing
- **CORS Support**: Configurable CORS for cross-origin requests
- **Health Checks**: Built-in health check endpoint
- **API Key Authentication**: Secure access control with customizable API key

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and configure your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your actual API keys:

```env
# OpenRouter API Configuration
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Langfuse Configuration
LANGFUSE_SECRET_KEY=your_langfuse_secret_key_here
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key_here
LANGFUSE_HOST=https://cloud.langfuse.com

# Server Configuration
PORT=8000
HTTP_REFERER=http://localhost:8000
X_TITLE=Graphiti Proxy Server

# Security
API_KEY=your_custom_api_key_for_access_control
```

### 3. Get API Keys

#### OpenRouter API Key
1. Visit [OpenRouter](https://openrouter.ai/)
2. Sign up/login and get your API key
3. Add it to your `.env` file

#### Langfuse API Keys
1. Visit [Langfuse](https://cloud.langfuse.com/) or your self-hosted instance
2. Create a new project
3. Get your Public Key and Secret Key from the project settings
4. Add them to your `.env` file

## Running the Server

### Development Mode (with auto-reload)

```bash
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### Production Mode

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### Using Python directly

```bash
python server.py
```

## Security

The server requires API key authentication for all endpoints except the root `/` endpoint. This prevents unauthorized use of your proxy.

### API Key Setup

1. Set a secure API key in your `.env` file using the `API_KEY` variable
2. If not set, the server will generate a random key at startup and display it in console logs
3. Include the API key in your requests using the `x-api-key` header

### API Key with n8n

When configuring n8n to use this proxy:

1. Create a custom OpenAI credential in n8n
2. Set the Base URL to your proxy's URL
3. Set the API Key to any value (this will be ignored by our proxy)
4. Configure n8n to add a custom HTTP header named `x-api-key` with your API key value

## API Endpoints

### GET /
Root endpoint with service information

### GET /models
Returns available models information

### POST /chat/completions
Main chat completions endpoint that proxies to OpenRouter
- Supports both streaming and non-streaming requests
- Automatically logs all interactions to Langfuse
- Extracts session IDs from `response_format.type` field for tracking

### GET /health
Health check endpoint

## Usage Examples

### Non-streaming Request

```bash
curl -X POST "http://localhost:8000/chat/completions" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your_api_key_here" \
  -d '{
    "model": "openai/gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Hello, world!"}
    ],
    "response_format": {"type": "session_123"}
  }'
```

### Streaming Request

```bash
curl -X POST "http://localhost:8000/chat/completions" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your_api_key_here" \
  -d '{
    "model": "openai/gpt-3.5-turbo",
    "messages": [
      {"role": "user", "content": "Hello, world!"}
    ],
    "stream": true,
    "response_format": {"type": "session_123"}
  }'
```

## Session Tracking

The server extracts session IDs from the `response_format.type` field in requests. This allows for better tracing and grouping of related requests in Langfuse.

## Observability

All requests are automatically logged to Langfuse with:
- Input messages and parameters
- Output responses
- Token usage (when available)
- Session IDs for tracking
- Model information
- Request metadata

## Development

### Project Structure

```
observability_proxy_server/
├── server.py           # Main FastAPI application
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
└── README.md          # This file
```

### Adding New Features

The server is built with FastAPI and follows standard patterns:
- Add new endpoints as FastAPI route functions
- Use the `@observe` decorator for Langfuse tracing
- Handle both sync and async operations appropriately

## Troubleshooting

### Common Issues

1. **Missing API Keys**: Ensure all required environment variables are set
2. **CORS Issues**: Check CORS configuration in the FastAPI middleware
3. **Streaming Problems**: Verify that the client properly handles SSE streams
4. **Langfuse Connection**: Check your Langfuse host URL and API keys

### Logs

The server provides detailed logging for debugging:
- Request/response logging
- Error handling with stack traces
- Langfuse integration status

## License

This project follows the same license as the parent Graphiti project.