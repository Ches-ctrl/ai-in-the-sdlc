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
    message: str
    session_id: str

class SessionEndRequest(BaseModel):
    session_id: str
    final_output: str
    status: str
    metadata: Optional[Dict[str, Any]] = None

class SessionEndResponse(BaseModel):
    message: str

# Internal models for session data we send out
class SessionInfo(BaseModel):
    user_prompt: str
    session_id: str
    timestamp: datetime
    git_commit_hash: str

class SessionEndInfo(BaseModel):
    session_id: str
    timestamp: datetime
    status: str

class CommandRequest(BaseModel):
    command: str

class CommandResponse(BaseModel):
    stdout: str
    stderr: str
    return_code: int

# Store for session information (in production, use a proper database)
active_sessions: Dict[str, SessionInfo] = {}

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

# Session started endpoint - generates and sends session info, returns OK
@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest):
    # Generate session information
    session_id = str(uuid.uuid4())
    timestamp = datetime.now()
    git_commit_hash = get_current_git_commit()
    
    # Create session info to send out
    session_info = SessionInfo(
        user_prompt=request.user_prompt,
        session_id=session_id,
        timestamp=timestamp,
        git_commit_hash=git_commit_hash
    )
    
    # Store session info (in production, send to external service)
    active_sessions[session_id] = session_info
    
    # Log the session information being sent
    print(f"[SESSION START] Sending session info: {session_info.model_dump_json()}")
    
    # Return simple OK response
    return SessionStartResponse(message="OK", session_id=session_id)

# Session ended endpoint - sends session end info, returns OK  
@app.post("/session/end", response_model=SessionEndResponse)
async def end_session(request: SessionEndRequest):
    # For now, we'll get the most recent session (in production, pass session_id)
    if active_sessions:
        latest_session_id = list(active_sessions.keys())[-1]
        session_info = active_sessions[latest_session_id]
        
        # Create session end info to send out
        session_end_info = SessionEndInfo(
            session_id=session_info.session_id,
            timestamp=datetime.now(),
            status="completed"
        )
        
        # Log the session end information being sent
        print(f"[SESSION END] Sending session end info: {session_end_info.model_dump_json()}")
        
        # Remove from active sessions
        del active_sessions[latest_session_id]
    else:
        print("[SESSION END] No active sessions found")
    
    # Return simple OK response
    return SessionEndResponse(message="OK")

# WebSocket for command execution
@app.websocket("/ws/execute")
async def websocket_execute_command(websocket: WebSocket):
    await websocket.accept()
    print("Client connected to WebSocket")
    
    try:
        # List of commands to send to the client
        commands_to_execute = [
            "git status",
            "ls -la",
            "pwd",
            "git log --oneline -5"
        ]
        
        # Send commands to client and receive results
        for command in commands_to_execute:
            print(f"Sending command to client: {command}")
            
            # Send command to client
            command_request = {"command": command}
            await websocket.send_text(json.dumps(command_request))
            
            # Wait for execution result from client
            try:
                result_data = await websocket.receive_text()
                result = json.loads(result_data)
                
                print(f"Received result from client:")
                print(f"  Command: {command}")
                print(f"  Return Code: {result.get('return_code', 'Unknown')}")
                print(f"  Output: {result.get('stdout', '')[:100]}...")  # First 100 chars
                
                if result.get('stderr'):
                    print(f"  Error: {result.get('stderr', '')[:100]}...")
                    
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON response from client for command: {command}")
            except Exception as e:
                print(f"❌ Error receiving result for command '{command}': {str(e)}")
                break
            
            # Small delay between commands
            await asyncio.sleep(1)
        
        print("✅ All commands sent and processed")
        
        # Keep connection alive to receive any additional messages
        while True:
            try:
                data = await websocket.receive_text()
                print(f"Additional message from client: {data}")
            except WebSocketDisconnect:
                break
                
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

# Helper endpoint to get session information (for debugging/monitoring)
@app.get("/sessions")
async def get_sessions():
    return {"active_sessions": list(active_sessions.keys()), "count": len(active_sessions)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
