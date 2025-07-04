"""
FastAPI proxy server for OpenRouter API with Langfuse observability.
Handles /models and /chat/completions endpoints with SSE streaming support.
"""

import os
import json
import asyncio
import secrets
from typing import Dict, Any, Optional, AsyncGenerator, List, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
import httpx
from pydantic import BaseModel
from langfuse import Langfuse
from langfuse.decorators import observe
import uvicorn
from dotenv import load_dotenv

load_dotenv(override=True)

# Initialize Langfuse client
langfuse = Langfuse(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)

# Pydantic models for request/response validation
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: Optional[bool] = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    response_format: Optional[Dict[str, Any]] = None

class ModelsResponse(BaseModel):
    data: list[Dict[str, Any]]
    object: str = "list"

# Security configuration
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    print("WARNING: API_KEY environment variable is not set. Generating a random key for this session.")
    API_KEY = secrets.token_urlsafe(32)
    print(f"Generated API_KEY: {API_KEY}")

api_key_header = APIKeyHeader(name="x-api-key", auto_error=False)

async def get_api_key(api_key: str = Depends(api_key_header)):
    if not api_key or api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    yield
    # On shutdown, flush any buffered events
    print("Shutting down and flushing Langfuse events...")
    langfuse.flush()
    print("Langfuse events flushed.")


# FastAPI app initialization
app = FastAPI(
    title="OpenRouter Proxy with Langfuse",
    description="Proxy server for OpenRouter API with Langfuse observability",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Consider restricting in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# @app.get("/models", dependencies=[Depends(get_api_key)])
@app.get("/models")
async def get_models():
    """Handle requests to /models endpoint."""
    print("Handling /models request")
    return {"message": "Success: /models path hit"}

def normalize_model_name(model_id: str) -> str:
    """
    Normalizes the model name to the OpenRouter standard.
    - Adds provider prefix (e.g., 'anthropic/', 'openai/').
    - Simplifies model names (e.g., 'claude-3-haiku-20240307' -> 'claude-3-haiku').
    """
    if "/" in model_id:
        # Already has a provider, assume it's correct
        return model_id

    # Handle Anthropic models
    if "claude" in model_id:
        parts = model_id.split('-')
        if len(parts) > 3:
            # e.g., claude-3-haiku-20240307 -> claude-3-haiku
            simplified_name = "-".join(parts[:3])
            return f"anthropic/{simplified_name}"
        return f"anthropic/{model_id}"

    # Handle OpenAI models
    if "gpt" in model_id:
        return f"openai/{model_id}"

    # Return original if no specific rule matches
    return model_id


async def proxy_chat_completion(
    request_data: Dict[str, Any],
    session_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Proxy chat completion request to OpenRouter with Langfuse observability.
    """
    # Normalize model name before processing
    original_model = None
    if "model" in request_data:
        original_model = request_data["model"]
        normalized_model = normalize_model_name(original_model)
        request_data["model"] = normalized_model
        print(f"Normalized model name from '{original_model}' to '{normalized_model}'")

    trace = langfuse.trace(
        name="chat-completion-proxy",
        session_id=session_id,
        metadata={
            "streaming": request_data.get("stream", False),
            "model": request_data.get("model"),
            "original_model": original_model,
        }
    )
    generation = trace.generation(
        name="openrouter-generation",
        model=request_data.get("model", "unknown"),
        input=request_data.get("messages", []),
        metadata=request_data,
    )

    try:
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if not openrouter_api_key:
            raise ValueError("Server configuration error: Missing OPENROUTER_API_KEY")

        headers = {
            "Authorization": f"Bearer {openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("HTTP_REFERER", "http://localhost:8000"),
            "X-Title": os.getenv("X_TITLE", "Graphiti Proxy Server")
        }
        if session_id:
            headers["X-Session-Id"] = session_id

        filtered_request = {k: v for k, v in request_data.items() if k != "response_format"}
        print(f"Proxying request to OpenRouter: {json.dumps(filtered_request, indent=2)}")

        output_content = ""
        async with httpx.AsyncClient(timeout=60.0) as client:
            if filtered_request.get("stream", False):
                async with client.stream("POST", "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=filtered_request) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise HTTPException(status_code=response.status_code, detail=f"OpenRouter API Error: {error_text.decode()}")
                    
                    async for chunk in response.aiter_lines():
                        if chunk:
                            yield chunk + "\\n\\n"
                            if chunk.startswith("data: "):
                                data_part = chunk[6:]
                                if data_part.strip() == "[DONE]":
                                    break
                                try:
                                    chunk_data = json.loads(data_part)
                                    if "choices" in chunk_data and chunk_data["choices"]:
                                        delta = chunk_data["choices"][0].get("delta", {})
                                        if "content" in delta and delta["content"] is not None:
                                            output_content += delta["content"]
                                except json.JSONDecodeError:
                                    continue
                generation.update(output=output_content)
            else:
                response = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=filtered_request)
                if response.status_code != 200:
                    raise HTTPException(status_code=response.status_code, detail=f"OpenRouter API Error: {response.text}")
                
                response_data = response.json()
                if "choices" in response_data and response_data["choices"]:
                    message = response_data["choices"][0].get("message", {})
                    output_content = message.get("content", "")
                
                generation.update(output=output_content, usage=response_data.get("usage"))
                yield json.dumps(response_data)

    except Exception as e:
        generation.update(level="ERROR", status_message=str(e))
        print(f"Error in proxy_chat_completion: {e}")
        # Re-raise as HTTPException to be handled by FastAPI
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

# @app.post("/chat/completions", dependencies=[Depends(get_api_key)])
@app.post("/chat/completions")
async def chat_completions(request: Request):
    """Handle requests to /chat/completions endpoint."""
    print("Handling /chat/completions request")
    
    try:
        request_data = await request.json()
        print(f"Original received payload: {json.dumps(request_data, indent=2)}")
        
        # Extract session ID from response_format.type if present
        session_id = None
        if "response_format" in request_data and isinstance(request_data["response_format"], dict):
            session_id = request_data["response_format"].get("type")
            if session_id:
                print(f"Extracted session ID: {session_id}")
        
        is_streaming = request_data.get("stream", False)
        
        if is_streaming:
            print("Streaming request detected. Initiating SSE response.")
            
            async def generate_stream():
                async for chunk in proxy_chat_completion(request_data, session_id):
                    yield chunk
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        else:
            print("Non-streaming request detected. Sending full JSON response.")
            
            response_content = ""
            async for chunk in proxy_chat_completion(request_data, session_id):
                response_content = chunk  # For non-streaming, there's only one chunk
                break
            
            return Response(
                content=response_content,
                media_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
            
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        print(f"Error in chat_completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/messages")
async def messages(request: Request):
    """Handle requests to Anthropic-compatible /v1/messages endpoint."""
    print("Handling /v1/messages request for Anthropic compatibility")
    
    try:
        request_data = await request.json()
        print(f"Original received payload for /v1/messages: {json.dumps(request_data, indent=2)}")
        
        # For Anthropic, session_id might be in metadata if the client supports it.
        # n8n often passes a user_id here, which we can use for session tracking.
        session_id = request_data.get("metadata", {}).get("user_id")
        if session_id:
            print(f"Extracted session ID from metadata: {session_id}")
        
        is_streaming = request_data.get("stream", False)
        
        if is_streaming:
            print("Streaming request detected. Initiating SSE response.")
            
            async def generate_stream():
                async for chunk in proxy_chat_completion(request_data, session_id):
                    yield chunk
            
            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                }
            )
        else:
            print("Non-streaming request detected. Sending full JSON response.")
            
            response_content = ""
            async for chunk in proxy_chat_completion(request_data, session_id):
                response_content = chunk  # For non-streaming, there's only one chunk
                break
            
            return Response(
                content=response_content,
                media_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )
            
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in request body")
    except Exception as e:
        print(f"Error in /v1/messages endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# @app.get("/health", dependencies=[Depends(get_api_key)])
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "openrouter-proxy"}

@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "OpenRouter Proxy with Langfuse",
        "version": "1.0.0",
        "endpoints": ["/models", "/chat/completions", "/health"],
        "authentication": "Required (x-api-key header)"
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )