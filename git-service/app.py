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
    RawLogsRequest, IssueInvestigationRequest, IssueInvestigationResponse, \
    InvestigationProgress

from src.git_examine import find_commit_messages
from src.commit_execute import execute_commits
from src.services.investigation_service import InvestigationService
from src.agents.commit_summarizer import CommitSummarizerAgent

app = FastAPI(title="Git Service API", version="1.0.0")
mongo_client: MongoClientService = get_mongo_client()
investigation_service = InvestigationService(mongo_client)


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



# Helper endpoint to get session information (for debugging/monitoring)
@app.get("/sessions")
async def get_sessions():
    return {"active_sessions": list(active_sessions.keys()), "count": len(active_sessions)}


# Commit Summary Endpoint
@app.get("/summarize/commits")
async def summarize_commits(limit: int = 10):
    """Get a summary of recent commits using Claude.
    
    Args:
        limit: Number of recent commits to summarize (default: 10)
        
    Returns:
        Summary of recent commits
    """
    try:
        # Create summarizer agent
        summarizer = CommitSummarizerAgent(mongo_client, verbose=True)
        
        # Run the summarization
        result = await summarizer.run(limit=limit)
        
        if result["success"]:
            return {
                "status": "success",
                "summary": result["result"]["summary"],
                "commit_count": result["result"]["commit_count"],
                "time_range": result["result"]["time_range"],
                "execution_time": result["execution_time_seconds"]
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Summarization failed: {result.get('error', 'Unknown error')}"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Issue Investigation Endpoints
@app.post("/investigate/issue", response_model=Dict[str, str])
async def investigate_issue(request: IssueInvestigationRequest):
    """Start a new issue investigation.
    
    Args:
        request: Investigation request with issue details
        
    Returns:
        Dictionary with investigation_id and status
    """
    try:
        investigation_id = await investigation_service.start_investigation(request)
        return {
            "investigation_id": investigation_id,
            "status": "started",
            "message": "Investigation started successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/investigate/{investigation_id}")
async def get_investigation_status(investigation_id: str):
    """Get the status and results of an investigation.
    
    Args:
        investigation_id: Unique investigation identifier
        
    Returns:
        Investigation status and results if available
    """
    status = await investigation_service.get_investigation_status(investigation_id)
    
    if status is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    
    return status


@app.get("/investigate/{investigation_id}/results", response_model=IssueInvestigationResponse)
async def get_investigation_results(investigation_id: str):
    """Get the results of a completed investigation.
    
    Args:
        investigation_id: Unique investigation identifier
        
    Returns:
        Investigation results
    """
    results = await investigation_service.get_investigation_results(investigation_id)
    
    if results is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found or not yet completed"
        )
    
    return results


@app.get("/investigations")
async def list_investigations():
    """List all investigations.
    
    Returns:
        List of investigation summaries
    """
    return {
        "investigations": investigation_service.list_investigations(),
        "count": len(investigation_service.active_investigations)
    }


# WebSocket for real-time investigation updates
@app.websocket("/ws/investigate")
async def websocket_investigate(websocket: WebSocket):
    """WebSocket endpoint for real-time investigation updates."""
    await websocket.accept()
    
    try:
        # Wait for investigation request
        data = await websocket.receive_text()
        request_data = json.loads(data)
        
        # Create investigation request
        request = IssueInvestigationRequest(**request_data)
        
        # Progress callback to send updates via WebSocket
        async def progress_callback(progress: InvestigationProgress):
            await websocket.send_json({
                "type": "progress",
                "data": progress.model_dump(mode="json")
            })
        
        # Start investigation with progress callback
        investigation_id = await investigation_service.start_investigation(
            request, progress_callback
        )
        
        # Send initial response
        await websocket.send_json({
            "type": "started",
            "investigation_id": investigation_id
        })
        
        # Wait for investigation to complete
        while True:
            await asyncio.sleep(1)
            
            # Check if investigation is complete
            results = await investigation_service.get_investigation_results(investigation_id)
            if results:
                # Send final results
                await websocket.send_json({
                    "type": "completed",
                    "data": results.model_dump(mode="json")
                })
                break
            
            # Check if investigation failed
            status = await investigation_service.get_investigation_status(investigation_id)
            if status and status.get("status") == "failed":
                await websocket.send_json({
                    "type": "failed",
                    "error": status.get("results", {}).get("error", "Unknown error")
                })
                break
                
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
