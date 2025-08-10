import os
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

# Create logs directory if it doesn't exist
os.makedirs("data/requests", exist_ok=True)
os.makedirs("data/responses", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('openai_proxy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OpenAI API Proxy",
    description="A proxy server for OpenAI API calls with logging and monitoring",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY environment variable is not set")
    raise ValueError("OPENAI_API_KEY environment variable is required")

class RequestLogger:
    """Class to handle request/response logging"""
    
    @staticmethod
    def log_request(endpoint: str, method: str, headers: dict, body: Any, client_ip: str):
        """Log incoming request details"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "request",
            "endpoint": endpoint,
            "method": method,
            "client_ip": client_ip,
            "headers": dict(headers),
            "body": body
        }
        # logger.info(f"REQUEST: {json.dumps(log_data, indent=2)[:100]}")

        with open(f"data/requests/{datetime.utcnow().isoformat()}.json", "w") as f:
            f.write(json.dumps(log_data, indent=2))

        return log_data
    
    @staticmethod
    def log_response(request_log: dict, status_code: int, response_body: Any, response_time: float):
        """Log response details"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "response",
            "request_id": request_log.get("timestamp"),
            "status_code": status_code,
            "response_time_ms": round(response_time * 1000, 2),
            "response_body": response_body
        }
        # logger.info(f"RESPONSE: {json.dumps(log_data, indent=2)[:100]}")

        with open(f"data/responses/{datetime.utcnow().isoformat()}.json", "w") as f:
            f.write(json.dumps(log_data, indent=2))

        return log_data
    
    @staticmethod
    def log_stream_response(response_body: Any, timestamp: str):
        """Log streaming response details"""

        try:
            data = json.loads(response_body.strip("data: ").strip())
            if "choices" in data and data["choices"]:
                if data["choices"][0]["finish_reason"]:
                    print(f"\n\nFINISH REASON: {data['choices'][0]['finish_reason']}\n\n")
        except json.JSONDecodeError:
            pass

        # Write raw SSE data without JSON wrapping to preserve streaming format
        with open(f"data/responses/{timestamp}.stream", "a") as f:
            f.write(response_body + "\n\n")
        return response_body

request_logger = RequestLogger()

async def get_client_ip(request: Request) -> str:
    """Extract client IP address"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

async def proxy_request(request: Request, endpoint_path: str):
    """Generic proxy function for OpenAI API requests"""
    start_time = time.time()
    client_ip = await get_client_ip(request)
    
    # Read request body
    body = await request.body()
    request_data = None
    if body:
        try:
            request_data = json.loads(body.decode())
        except json.JSONDecodeError:
            request_data = body.decode()

        if "max_tokens" in request_data:
            request_data["max_completion_tokens"] = request_data["max_tokens"]
            del request_data["max_tokens"]

        if "model" in request_data:
            request_data["model"] = "gpt-4.1-mini"


        ## Detect user query
        if "messages" in request_data:
            def find_user_query(message: str):
                if "<user_query>" in message:
                    return message.split("<user_query>")[1].split("</user_query>")[0]
                return None
            
            latest_user_message = [
                find_user_query(i["content"]) for i in request_data["messages"] 
                if i["role"] == "user" and find_user_query(i["content"])
            ]

            if latest_user_message:
                latest_user_message_str = latest_user_message[-1].strip()
                print(f"\n\nLATEST USER MESSAGE: {latest_user_message_str}\n\n")

    
    # Encode the changed request data
    body = json.dumps(request_data).encode()
    
    # Log the incoming request
    request_log = request_logger.log_request(
        endpoint=endpoint_path,
        method=request.method,
        headers=request.headers,
        body=request_data,
        client_ip=client_ip
    )
    
    # Prepare headers for OpenAI API
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": request.headers.get("Content-Type", "application/json"),
        "User-Agent": request.headers.get("User-Agent", "OpenAI-Proxy/1.0")
    }
    
    # Forward request to OpenAI
    url = f"{OPENAI_API_BASE}/{endpoint_path}"
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=request.query_params
            )
            
            response_time = time.time() - start_time
            
            # Handle streaming responses
            if response.headers.get("content-type", "").startswith("text/event-stream"):
                async def stream_response():
                    timestamp = datetime.utcnow().isoformat()
                    async for chunk in response.aiter_bytes():
                    
                        for line in chunk.decode("utf-8").split("\n\n"):
                            request_logger.log_stream_response(
                                response_body=line,
                                timestamp=timestamp
                            )
                            # Yield the raw chunk to maintain SSE format
                            yield line.encode("utf-8") + b"\n\n"
                
                # Log streaming response start
                request_logger.log_response(
                    request_log=request_log,
                    status_code=response.status_code,
                    response_body="[STREAMING_RESPONSE]",
                    response_time=response_time
                )
                
                return StreamingResponse(
                    stream_response(),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.headers.get("content-type")
                )
            
            # Handle regular JSON responses
            response_data = response.json() if response.content else None
            
            # Log the response
            request_logger.log_response(
                request_log=request_log,
                status_code=response.status_code,
                response_body=response_data,
                response_time=response_time
            )
            
            return JSONResponse(
                content=response_data,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
    except httpx.RequestError as e:
        error_time = time.time() - start_time
        error_msg = f"Request failed: {str(e)}"
        logger.error(error_msg)
        
        request_logger.log_response(
            request_log=request_log,
            status_code=500,
            response_body={"error": error_msg},
            response_time=error_time
        )
        
        raise HTTPException(status_code=500, detail=error_msg)

# OpenAI API endpoints
@app.api_route("/chat/completions", methods=["POST"])
async def chat_completions(request: Request):
    """Proxy for OpenAI chat completions"""
    return await proxy_request(request, "chat/completions")


@app.api_route("/embeddings", methods=["POST"])
async def embeddings(request: Request):
    """Proxy for OpenAI embeddings"""
    return await proxy_request(request, "embeddings")

@app.api_route("/models", methods=["GET"])
async def models(request: Request):
    """Proxy for OpenAI models list"""
    return await proxy_request(request, "models")

@app.api_route("/models/{model_id}", methods=["GET"])
async def model_details(request: Request, model_id: str):
    """Proxy for OpenAI model details"""
    return await proxy_request(request, f"models/{model_id}")

# Health check and status endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "OpenAI API Proxy",
        "version": "1.0.0",
        "description": "A proxy server for OpenAI API calls with logging and monitoring",
        "endpoints": {
            "chat": "/chat/completions",
            "embeddings": "/embeddings",
            "models": "/models",
        },
        "health": "/health",
        "made_by": "Made by AI"
    }

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8001))
    
    logger.info(f"Starting OpenAI API Proxy on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

