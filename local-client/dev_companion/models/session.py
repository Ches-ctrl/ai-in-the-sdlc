"""Session-related data models."""

import platform
import os
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


class SessionStatus(Enum):
    """Session status enumeration."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GitInfo:
    """Git repository information."""
    branch: str = ""
    commit_hash: str = ""
    commit_message: str = ""
    author: str = ""
    is_dirty: bool = False


@dataclass
class EnvironmentInfo:
    """System environment information."""
    os: str = field(default_factory=lambda: platform.system())
    architecture: str = field(default_factory=lambda: platform.machine())
    hostname: str = field(default_factory=lambda: platform.node())
    username: str = field(default_factory=lambda: os.getenv('USER', ''))
    working_dir: str = field(default_factory=lambda: os.getcwd())


@dataclass
class SessionMetadata:
    """Session metadata."""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tokens_used: Dict[str, int] = field(default_factory=lambda: {"input": 0, "output": 0, "total": 0})
    error_count: int = 0
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_deleted: List[str] = field(default_factory=list)
    commands_run: List[str] = field(default_factory=list)