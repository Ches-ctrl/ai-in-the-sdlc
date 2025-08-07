from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime

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
    session_end_request: Optional[SessionEndRequest] = None
    features: List[str]

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

class RawLogsRequest(BaseModel):
    data: Dict[str, Any]