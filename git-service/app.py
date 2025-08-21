from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import json
import uuid
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from jose import JWTError, jwt

from repository.mongo_client import get_mongo_client, MongoClientService
from src.prompt_examine import analyze_prompt
from src.models import SessionStartRequest, SessionStartResponse, \
    SessionEndRequest, SessionEndResponse, SessionInfo, SessionEndInfo, \
    RawLogsRequest

from src.git_examine import find_commit_messages
from src.commit_execute import execute_commits

# Load environment variables
load_dotenv()

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-this")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# Environment Variables Documentation:
# SUPABASE_URL=your_supabase_project_url
# SUPABASE_ANON_KEY=your_supabase_anon_key
# SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
# JWT_SECRET_KEY=your_jwt_secret_key
# JWT_ALGORITHM=HS256
# JWT_EXPIRE_HOURS=24

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("Missing required Supabase environment variables")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

app = FastAPI(title="Git Service API", version="1.0.0")
security = HTTPBearer()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication Models
class UserLogin(BaseModel):
    email: str
    password: str

class UserSignup(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

# Authentication Functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from Supabase
    try:
        result = supabase.auth.get_user(token)
        if result.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return result.user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to authenticate user",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Databases
mongo_client: MongoClientService = get_mongo_client()
active_sessions: Dict[str, SessionInfo] = {}

# Health check endpoint
@app.get("/health")
async def health_check(): 
    return "ok"

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Git Service API is running"}

# Authentication Endpoints
@app.post("/auth/signup", response_model=TokenResponse)
async def signup(user_data: UserSignup):
    try:
        # Create user in Supabase
        result = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "full_name": user_data.full_name
                }
            }
        })
        
        if result.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user account"
            )
        
        # Create access token
        access_token = create_access_token(data={"sub": result.user.id})
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "id": result.user.id,
                "email": result.user.email,
                "full_name": user_data.full_name
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Signup failed: {str(e)}"
        )

@app.post("/auth/login", response_model=TokenResponse)
async def login(user_credentials: UserLogin):
    try:
        # Authenticate with Supabase
        result = supabase.auth.sign_in_with_password({
            "email": user_credentials.email,
            "password": user_credentials.password
        })
        
        if result.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        # Create access token
        access_token = create_access_token(data={"sub": result.user.id})
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user={
                "id": result.user.id,
                "email": result.user.email,
                "user_metadata": result.user.user_metadata
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Login failed: {str(e)}"
        )

@app.post("/auth/logout")
async def logout(current_user = Depends(get_current_user)):
    try:
        # Sign out from Supabase
        supabase.auth.sign_out()
        return {"message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logout failed: {str(e)}"
        )

@app.get("/auth/me")
async def get_current_user_info(current_user = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "user_metadata": current_user.user_metadata,
        "created_at": current_user.created_at
    }

@app.post("/logs/raw")
async def raw_logs(request: RawLogsRequest, current_user = Depends(get_current_user)):
    print(f"[RAW LOGS] Received raw logs: {request.data}")
    mongo_client.insert_log(request.data, current_user.id)
    return {"message": "Logs received"}

# Session started endpoint - generates and sends session info, returns OK
@app.post("/session/start", response_model=SessionStartResponse)
async def start_session(request: SessionStartRequest, current_user = Depends(get_current_user)):
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
        features=features,
        cwd=request.cwd,
        user_id=current_user.id
    )
    
    # Store session info (in production, send to external service)
    active_sessions[session_id] = session_info
    
    # Log the session information being sent
    print(f"[SESSION START] Sending session info: {session_info.model_dump_json()}")
    
    # Return simple OK response
    return SessionStartResponse(message="OK", session_id=session_id)

# Session ended endpoint - sends session end info, returns OK  
@app.post("/session/end", response_model=SessionEndResponse)
async def end_session(request: SessionEndRequest, current_user = Depends(get_current_user)):
    session_id = request.session_id
    
    # Verify session exists and user owns it
    if session_id not in active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if active_sessions[session_id].user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to session"
        )
    
    # Check cwd
    if active_sessions[session_id].cwd == "None":
        active_sessions[session_id].cwd = request.cwd
    
    # Store sesionEndRequest on SessionInfo
    active_sessions[session_id].session_end_request = request
    
    # Return simple OK response
    return SessionEndResponse(message="OK")

# WebSocket for command execution with session ID
@app.websocket("/ws/execute")
async def websocket_execute_command(websocket: WebSocket):
    await websocket.accept()
    
    # Authenticate user via first message
    authenticated_user = None
    try:
        # Wait for authentication message
        auth_data = await websocket.receive_text()
        auth_message = json.loads(auth_data)
        
        if auth_message.get('message_type') != 'authenticate':
            await websocket.send_text(json.dumps({"error": "First message must be authentication"}))
            await websocket.close()
            return
            
        token = auth_message.get('token')
        if not token:
            await websocket.send_text(json.dumps({"error": "Token required for authentication"}))
            await websocket.close()
            return
            
        # Verify token
        user_id = verify_token(token)
        if user_id is None:
            await websocket.send_text(json.dumps({"error": "Invalid token"}))
            await websocket.close()
            return
            
        # Get user from Supabase
        try:
            result = supabase.auth.get_user(token)
            if result.user is None:
                await websocket.send_text(json.dumps({"error": "User not found"}))
                await websocket.close()
                return
            authenticated_user = result.user
        except Exception as e:
            await websocket.send_text(json.dumps({"error": "Authentication failed"}))
            await websocket.close()
            return
            
        # Send authentication success
        await websocket.send_text(json.dumps({"message_type": "auth_success", "user_id": authenticated_user.id}))
        
    except Exception as e:
        await websocket.send_text(json.dumps({"error": f"Authentication error: {str(e)}"}))
        await websocket.close()
        return
    
    try:

        async def start_done(session_id: str):
            commit_messages = await find_commit_messages(websocket, active_sessions[session_id].features)

            if len(commit_messages.commit_messages) == 0:
                del active_sessions[session_id]
                return {"status": "success", "message": "No files to commit", "finished": True}

            results = await execute_commits(commit_messages.commit_messages, websocket)

            # Add messages to mongo_async
            for commit_message, result in zip(commit_messages.commit_messages, results):
                # Note: user_id needs to be passed from the session
                mongo_client.insert_commit(
                    user_id=active_sessions[session_id].user_id,
                    commit_hash=result["commit_hash"],
                    message=commit_message.message,
                    author="AI",
                    prompt=active_sessions[session_id].user_prompt,
                    timestamp=datetime.now(),
                    files_changed=commit_message.files,
                    cwd=active_sessions[session_id].cwd,
                    metadata=result
                )
            
            del active_sessions[session_id]
            return {"status": "success", "message": commit_messages.model_dump_json(), "finished": True}
        
        async def handle_client_messages():
            while True:
                try:
                    data = await websocket.receive_text()
                    result = json.loads(data)

                    # Verify session exists
                    session_id = result.get('session_id')
                    if session_id not in active_sessions:
                        print(f"❌ Invalid session ID: {session_id}")
                        print(f"Active sessions: {active_sessions.keys()}")
                        await websocket.send_text(json.dumps({"error": "Invalid session ID"}))
                        return
                    
                    # Verify user owns this session
                    if active_sessions[session_id].user_id != authenticated_user.id:
                        print(f"❌ User {authenticated_user.id} does not own session {session_id}")
                        await websocket.send_text(json.dumps({"error": "Access denied to session"}))
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
                except Exception as e:
                    print(f"❌ Error receiving message: {str(e)}")
                    break
        
        # Run both tasks concurrently
        await handle_client_messages()
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")



# Commit endpoints for frontend integration
@app.get("/commits/recent")
async def get_recent_commits(limit: int = 10, cwd: str = None, current_user = Depends(get_current_user)):
    """Get recent commits from MongoDB"""
    try:
        commits = mongo_client.get_recent_commits(limit=limit, user_id=current_user.id, cwd=cwd)
        return commits
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching commits: {str(e)}")

class SearchCommitsRequest(BaseModel):
    query_text: str
    limit: int = 5
    min_score: float = 0.7

@app.post("/commits/search")
async def search_commits(request: SearchCommitsRequest, current_user = Depends(get_current_user)):
    """Search commits using semantic similarity"""
    try:
        results = mongo_client.get_commits_by_similarity(
            query_text=request.query_text,
            limit=request.limit,
            min_score=request.min_score,
            user_id=current_user.id
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

@app.get("/commits/{commit_hash}")
async def get_commit_by_hash(commit_hash: str, current_user = Depends(get_current_user)):
    """Get a specific commit by hash"""
    try:
        commit = mongo_client.get_commit_by_hash(commit_hash, user_id=current_user.id)
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
