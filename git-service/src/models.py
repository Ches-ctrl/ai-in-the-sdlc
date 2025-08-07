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


# Issue Investigation Models
class DateRange(BaseModel):
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class IssueInvestigationRequest(BaseModel):
    issue_description: str
    repository_context: Optional[str] = None
    time_range: Optional[DateRange] = None
    affected_files: Optional[List[str]] = None
    error_messages: Optional[List[str]] = None
    severity: Optional[str] = "medium"
    max_commits_to_analyze: Optional[int] = 50
    investigation_depth: Optional[str] = "thorough"  # quick/thorough/exhaustive


class CommitSummary(BaseModel):
    commit_hash: str
    message: str
    author: str
    timestamp: datetime
    files_changed: List[str]
    similarity_score: Optional[float] = None


class CommitAnalysis(BaseModel):
    commit_hash: str
    likelihood_score: float
    reasoning: str
    matching_indicators: List[str]
    message: str
    author: str
    timestamp: datetime
    files_changed: List[str]
    original_prompt: Optional[str] = None
    risk_factors: List[str]
    blast_radius: str  # low/medium/high/critical


class IssueInvestigationResponse(BaseModel):
    investigation_id: str
    status: str  # "completed", "in_progress", "failed"
    root_cause_commits: List[CommitAnalysis]
    confidence_score: float
    related_commits: List[CommitSummary]
    pattern_analysis: str
    suggested_fixes: List[str]
    affected_components: List[str]
    total_commits_analyzed: int
    search_strategy_used: str
    processing_time_ms: int
    error: Optional[str] = None


class InvestigationProgress(BaseModel):
    investigation_id: str
    stage: str  # "initializing", "searching", "analyzing", "ranking", "complete"
    progress_percentage: int
    current_action: str
    commits_found: int
    eta_seconds: Optional[int] = None
    timestamp: datetime