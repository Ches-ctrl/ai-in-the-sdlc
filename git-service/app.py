from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mongo_client: MongoClientService = get_mongo_client()


# Store for session information (in production, use a proper database)
active_sessions: Dict[str, SessionInfo] = {}

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

    # Analyze prompt
    features = await analyze_prompt(request.user_prompt)
    
    # Create session info to send out
    session_info = SessionInfo(
        user_prompt=request.user_prompt,
        session_id=session_id,
        timestamp=timestamp,
        git_commit_hash="mock_commit_hash",
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
            print(f"\n\n\nSession {session_id} is done")
            print(f"Session info: {active_sessions[session_id].model_dump_json()}\n\n\n")
            commit_messages = await find_commit_messages(websocket, active_sessions[session_id].features)
            print(f"Commit messages: {commit_messages.model_dump_json()}")

            if len(commit_messages.commit_messages) == 0:
                return {"status": "success", "message": "No files to commit"}
            
            # Add messages to mongo_async
            for commit_message in commit_messages.commit_messages:
                mongo_client.insert_commit(
                    commit_hash="mock_commit_hash",
                    message=commit_message.message,
                    author="AI",
                    prompt=active_sessions[session_id].user_prompt,
                    timestamp=datetime.now(),
                    files_changed=commit_message.files,
                )
                print(f"Inserted commit: {commit_message.message}")

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
                    
                    if result.get('message_type') == 'session_finished':
                        status = await start_done(result.get('session_id'))
                    
                    await websocket.send_text(json.dumps({
                        "message_type": result.get('message_type'),
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



# Commit endpoints for frontend integration
@app.get("/commits/recent")
async def get_recent_commits(limit: int = 10):
    """Get recent commits from MongoDB"""
    try:
        commits = mongo_client.get_recent_commits(limit=limit)
        return commits
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching commits: {str(e)}")

class SearchCommitsRequest(BaseModel):
    query_text: str
    limit: int = 5
    min_score: float = 0.7

@app.post("/commits/search")
async def search_commits(request: SearchCommitsRequest):
    """Search commits using semantic similarity"""
    try:
        results = mongo_client.get_commits_by_similarity(
            query_text=request.query_text,
            limit=request.limit,
            min_score=request.min_score
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/commits/{commit_hash}")
async def get_commit_by_hash(commit_hash: str):
    """Get a specific commit by hash"""
    try:
        commit = mongo_client.get_commit_by_hash(commit_hash)
        if not commit:
            raise HTTPException(status_code=404, detail="Commit not found")
        return commit
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching commit: {str(e)}")

# Helper endpoint to get session information (for debugging/monitoring)
@app.get("/sessions")
async def get_sessions():
    return {"active_sessions": list(active_sessions.keys()), "count": len(active_sessions)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
