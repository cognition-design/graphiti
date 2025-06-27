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

# FastAPI app initialization
app = FastAPI(
    title="OpenRouter Proxy with Langfuse",
    description="Proxy server for OpenRouter API with Langfuse observability",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Consider restricting in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/models", dependencies=[Depends(get_api_key)])
async def get_models():
    """Handle requests to /models endpoint."""
    print("Handling /models request")
    return {"message": "Success: /models path hit"}

@observe(name="chat_completion_proxy")
async def proxy_chat_completion(
    request_data: Dict[str, Any],
    session_id: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Proxy chat completion request to OpenRouter with Langfuse observability.
    """
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: Missing OPENROUTER_API_KEY environment variable"
        )

    # Prepare headers for OpenRouter API
    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("HTTP_REFERER", "http://localhost:8000"),
        "X-Title": os.getenv("X_TITLE", "Graphiti Proxy Server")
    }

    # Add session tracking if available
    if session_id:
        headers["X-Session-Id"] = session_id

    # Remove response_format from the request body as it was used for session tracking
    filtered_request = {k: v for k, v in request_data.items() if k != "response_format"}
    
    print(f"Proxying request to OpenRouter: {json.dumps(filtered_request, indent=2)}")
    
    # Log to Langfuse
    langfuse.generation(
        name="openrouter_chat_completion",
        model=filtered_request.get("model", "unknown"),
        input=filtered_request.get("messages", []),
        metadata={
            "session_id": session_id,
            "stream": filtered_request.get("stream", False),
            "temperature": filtered_request.get("temperature"),
            "max_tokens": filtered_request.get("max_tokens"),
        }
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            if filtered_request.get("stream", False):
                # Handle streaming response
                async with client.stream(
                    "POST",
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=filtered_request
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        print(f"OpenRouter API Error: {response.status_code} - {error_text}")
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"OpenRouter API Error: {error_text.decode()}"
                        )
                    
                    full_response = ""
                    async for chunk in response.aiter_lines():
                        if chunk:
                            chunk_str = chunk.decode('utf-8')
                            if chunk_str.startswith("data: "):
                                data_part = chunk_str[6:]  # Remove "data: " prefix
                                if data_part.strip() == "[DONE]":
                                    yield "data: [DONE]\n\n"
                                    break
                                else:
                                    try:
                                        chunk_data = json.loads(data_part)
                                        if "choices" in chunk_data and chunk_data["choices"]:
                                            delta = chunk_data["choices"][0].get("delta", {})
                                            if "content" in delta:
                                                full_response += delta["content"]
                                        yield f"data: {data_part}\n\n"
                                    except json.JSONDecodeError:
                                        continue
                    
                    # Log the complete response to Langfuse
                    langfuse.generation(
                        name="openrouter_chat_completion_complete",
                        model=filtered_request.get("model", "unknown"),
                        input=filtered_request.get("messages", []),
                        output=full_response,
                        metadata={"session_id": session_id, "stream": True}
                    )
            else:
                # Handle non-streaming response
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=filtered_request
                )
                
                if response.status_code != 200:
                    print(f"OpenRouter API Error: {response.status_code} - {response.text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"OpenRouter API Error: {response.text}"
                    )
                
                response_data = response.json()
                print(f"OpenRouter API response: {json.dumps(response_data, indent=2)}")
                
                # Extract response content for logging
                output_content = ""
                if "choices" in response_data and response_data["choices"]:
                    message = response_data["choices"][0].get("message", {})
                    output_content = message.get("content", "")
                
                # Log to Langfuse
                langfuse.generation(
                    name="openrouter_chat_completion_complete",
                    model=filtered_request.get("model", "unknown"),
                    input=filtered_request.get("messages", []),
                    output=output_content,
                    usage=response_data.get("usage", {}),
                    metadata={"session_id": session_id, "stream": False}
                )
                
                yield json.dumps(response_data)
                
        except httpx.RequestError as e:
            print(f"Request error: {e}")
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
        except Exception as e:
            print(f"Unexpected error: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/chat/completions", dependencies=[Depends(get_api_key)])
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

@app.get("/health", dependencies=[Depends(get_api_key)])
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