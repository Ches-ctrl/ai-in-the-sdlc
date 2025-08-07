from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import subprocess
import asyncio
import json
import uuid

from repository.mongo_client import get_mongo_client, MongoClientService
from src.prompt_examine import analyze_prompt
from src.models import SessionStartRequest, SessionStartResponse, \
    SessionEndRequest, SessionEndResponse, SessionInfo, SessionEndInfo, \
    RawLogsRequest

from src.git_examine import find_commit_messages
from src.commit_execute import execute_commits

app = FastAPI(title="Git Service API", version="1.0.0")
mongo_client: MongoClientService = get_mongo_client()


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

# Health check endpoint
@app.get("/health")
async def health_check(): 
    return {"running": True}

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Git Service API is running"}

@app.post("/logs/raw")
async def raw_logs(request: RawLogsRequest):
    print(f"[RAW LOGS] Received raw logs: {request.data}")
    mongo_client.insert_log(request.data)
    return {"message": "Logs received"}

# Session started endpoint - generates and sends session info, returns OK
@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest):
    # Generate session information
    session_id = str(uuid.uuid4())
    timestamp = datetime.now()
    git_commit_hash = get_current_git_commit()

    # Analyze prompt
    features = await analyze_prompt(request.user_prompt)
    
    # Create session info to send out
    session_info = SessionInfo(
        user_prompt=request.user_prompt,
        session_id=session_id,
        timestamp=timestamp,
        git_commit_hash=git_commit_hash,
        features=features
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
    session_id = request.session_id
    
    
    # Store sesionEndRequest on SessionInfo
    active_sessions[session_id].session_end_request = request
    
    # Return simple OK response
    return SessionEndResponse(message="OK")

# WebSocket for command execution with session ID
@app.websocket("/ws/execute")
async def websocket_execute_command(websocket: WebSocket):
    await websocket.accept()
    
    try:

        async def start_done(session_id: str):
            print(f"\n\n\nSession {session_id} is done\n\n\n")
            print(f"Session info: {active_sessions[session_id].model_dump_json()}")
            commit_messages = await find_commit_messages(websocket, active_sessions[session_id].features)
            print(f"Commit messages: {commit_messages.model_dump_json()}")

            if len(commit_messages.commit_messages) == 0:
                return {"status": "success", "message": "No files to commit"}

            results = await execute_commits(commit_messages.commit_messages, websocket)
            print(f"Results: {results}")
            
            return {"status": "success", "message": commit_messages.model_dump_json()}
        
        async def handle_client_messages():
            while True:
                try:
                    data = await websocket.receive_text()
                    result = json.loads(data)

                    # Verify session exists
                    if result.get('session_id') not in active_sessions:
                        print(f"❌ Invalid session ID: {result.get('session_id')}")
                        print(f"Active sessions: {active_sessions.keys()}")
                        await websocket.send_text(json.dumps({"error": "Invalid session ID"}))
                        return
                    
                    if result.get('message') == 'done':
                        status = await start_done(result.get('session_id'))
                    
                    await websocket.send_text(json.dumps({
                        "message": result.get('message'),
                        "status": status
                    }))
                        
                except json.JSONDecodeError:
                    print(f"❌ Invalid JSON response from client")
                except WebSocketDisconnect:
                    break
                # except Exception as e:
                #     print(f"❌ Error receiving message: {str(e)}")
                #     break
        
        # Run both tasks concurrently
        await handle_client_messages()
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")



# Helper endpoint to get session information (for debugging/monitoring)
@app.get("/sessions")
async def get_sessions():
    return {"active_sessions": list(active_sessions.keys()), "count": len(active_sessions)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
