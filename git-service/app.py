from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import subprocess
import asyncio
import json
import uuid

app = FastAPI(title="Git Service API", version="1.0.0")

# Minimalistic Models
class SessionStartRequest(BaseModel):
    user_prompt: str

class SessionStartResponse(BaseModel):
    session_id: str
    user_prompt: str
    timestamp: datetime
    git_commit_hash: str

class SessionEndRequest(BaseModel):
    session_id: str
    final_output: str
    status: str  # "success" or "failed"
    metadata: Optional[Dict[str, Any]] = None

class SessionEndResponse(BaseModel):
    session_id: str
    final_output: str
    status: str
    metadata: Optional[Dict[str, Any]]
    timestamp: datetime

class CommandRequest(BaseModel):
    command: str

class CommandResponse(BaseModel):
    stdout: str
    stderr: str
    return_code: int

# Helper function to get current git commit hash
def get_current_git_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd="."
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return "No git repository found"
    except Exception as e:
        return f"Error getting git commit: {str(e)}"

# Session started endpoint
@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest):
    session_id = str(uuid.uuid4())
    timestamp = datetime.now()
    git_commit_hash = get_current_git_commit()
    
    return SessionStartResponse(
        session_id=session_id,
        user_prompt=request.user_prompt,
        timestamp=timestamp,
        git_commit_hash=git_commit_hash
    )

# Session ended endpoint
@app.post("/session/end", response_model=SessionEndResponse)
async def end_session(request: SessionEndRequest):
    timestamp = datetime.now()
    
    return SessionEndResponse(
        session_id=request.session_id,
        final_output=request.final_output,
        status=request.status,
        metadata=request.metadata,
        timestamp=timestamp
    )

# WebSocket for command execution
@app.websocket("/ws/execute")
async def websocket_execute_command(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # Receive command from client
            data = await websocket.receive_text()
            try:
                command_data = json.loads(data)
                command = command_data.get("command", "")
                
                if not command:
                    await websocket.send_text(json.dumps({
                        "error": "No command provided"
                    }))
                    continue
                
                # Execute command
                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=30  # 30 second timeout
                    )
                    
                    response = CommandResponse(
                        stdout=result.stdout,
                        stderr=result.stderr,
                        return_code=result.returncode
                    )
                    
                    await websocket.send_text(response.model_dump_json())
                    
                except subprocess.TimeoutExpired:
                    await websocket.send_text(json.dumps({
                        "error": "Command timed out after 30 seconds"
                    }))
                except Exception as e:
                    await websocket.send_text(json.dumps({
                        "error": f"Command execution error: {str(e)}"
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "error": "Invalid JSON format"
                }))
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "error": f"Unexpected error: {str(e)}"
                }))
                
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")

@app.get("/")
async def root():
    return {"message": "Git Service API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
