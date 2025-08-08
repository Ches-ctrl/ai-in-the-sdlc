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
        logger.info(f"REQUEST: {json.dumps(log_data, indent=2)[:100]}")

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
        logger.info(f"RESPONSE: {json.dumps(log_data, indent=2)[:100]}")

        with open(f"data/responses/{datetime.utcnow().isoformat()}.json", "w") as f:
            f.write(json.dumps(log_data, indent=2))

        return log_data

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
                    async for chunk in response.aiter_bytes():
                        yield chunk
                
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

@app.api_route("/completions", methods=["POST"])
async def completions(request: Request):
    """Proxy for OpenAI completions"""
    return await proxy_request(request, "completions")

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

@app.api_route("/images/generations", methods=["POST"])
async def image_generations(request: Request):
    """Proxy for OpenAI image generations"""
    return await proxy_request(request, "images/generations")

@app.api_route("/images/edits", methods=["POST"])
async def image_edits(request: Request):
    """Proxy for OpenAI image edits"""
    return await proxy_request(request, "images/edits")

@app.api_route("/images/variations", methods=["POST"])
async def image_variations(request: Request):
    """Proxy for OpenAI image variations"""
    return await proxy_request(request, "images/variations")

@app.api_route("/audio/transcriptions", methods=["POST"])
async def audio_transcriptions(request: Request):
    """Proxy for OpenAI audio transcriptions"""
    return await proxy_request(request, "audio/transcriptions")

@app.api_route("/audio/translations", methods=["POST"])
async def audio_translations(request: Request):
    """Proxy for OpenAI audio translations"""
    return await proxy_request(request, "audio/translations")

@app.api_route("/files", methods=["GET", "POST"])
async def files(request: Request):
    """Proxy for OpenAI files"""
    return await proxy_request(request, "files")

@app.api_route("/files/{file_id}", methods=["GET", "DELETE"])
async def file_operations(request: Request, file_id: str):
    """Proxy for OpenAI file operations"""
    return await proxy_request(request, f"files/{file_id}")

@app.api_route("/fine-tuning/jobs", methods=["GET", "POST"])
async def fine_tuning_jobs(request: Request):
    """Proxy for OpenAI fine-tuning jobs"""
    return await proxy_request(request, "fine-tuning/jobs")

@app.api_route("/fine-tuning/jobs/{job_id}", methods=["GET"])
async def fine_tuning_job_details(request: Request, job_id: str):
    """Proxy for OpenAI fine-tuning job details"""
    return await proxy_request(request, f"fine-tuning/jobs/{job_id}")

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
            "completions": "/completions",
            "embeddings": "/embeddings",
            "models": "/models",
            "images": "/images/*",
            "audio": "/audio/*",
            "files": "/files/*",
            "fine-tuning": "/fine-tuning/*"
        },
        "health": "/health"
    }

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"Starting OpenAI API Proxy on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

