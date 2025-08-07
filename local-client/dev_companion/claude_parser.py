"""Claude session file parser."""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Iterator
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClaudeMessage:
    """Represents a message in Claude session."""
    role: str
    content: str
    timestamp: str
    message_type: str
    tool_uses: List[Dict[str, Any]] = field(default_factory=list)
    uuid: str = ""
    parent_uuid: Optional[str] = None


@dataclass
class ClaudeSession:
    """Represents a Claude session."""
    session_id: str
    cwd: str
    git_branch: str
    messages: List[ClaudeMessage] = field(default_factory=list)
    tool_calls: Dict[str, int] = field(default_factory=dict)
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)
    files_read: List[str] = field(default_factory=list)
    commands_executed: List[str] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    user_prompt: str = ""
    final_output: str = ""


class ClaudeSessionParser:
    """Parser for Claude session JSONL files."""
    
    # Tool name mappings
    TOOL_MAPPINGS = {
        'Read': 'file_read',
        'Write': 'file_create',
        'Edit': 'file_modify',
        'MultiEdit': 'file_modify',
        'Bash': 'command_execute',
        'Grep': 'search',
        'Glob': 'search',
        'WebSearch': 'web_search',
        'TodoWrite': 'todo_manage'
    }
    
    def __init__(self, claude_home: str = None):
        """
        Initialize parser.
        
        Args:
            claude_home: Path to Claude home directory (default: ~/.claude)
        """
        self.claude_home = Path(claude_home or os.path.expanduser("~/.claude"))
        self.projects_dir = self.claude_home / "projects"
    
    def get_project_path(self, original_path: str) -> Path:
        """
        Convert original project path to Claude's sanitized project directory name.
        
        Args:
            original_path: Original project path
            
        Returns:
            Path to Claude project directory
        """
        # Claude replaces non-alphanumeric characters with hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9]', '-', str(Path(original_path).resolve()))
        return self.projects_dir / sanitized
    
    def find_session_files(self, project_path: str) -> List[Path]:
        """
        Find all session files for a project.
        
        Args:
            project_path: Original project path
            
        Returns:
            List of session file paths
        """
        project_dir = self.get_project_path(project_path)
        
        # Looking for Claude sessions

        if not project_dir.exists():
            logger.warning(f"Project directory not found: {project_dir}")
            # List what directories do exist
            if self.projects_dir.exists():
                existing = list(self.projects_dir.iterdir())
            return []
        
        # Find all JSONL files (session files)
        session_files = list(project_dir.glob("*.jsonl"))
        return sorted(session_files, key=lambda p: p.stat().st_mtime, reverse=True)
    
    def parse_session_file(self, file_path: Path) -> Optional[ClaudeSession]:
        """
        Parse a Claude session JSONL file.
        
        Args:
            file_path: Path to session file
            
        Returns:
            Parsed session or None if error
        """
        try:
            session_id = file_path.stem
            session = ClaudeSession(
                session_id=session_id,
                cwd="",  # Will be set from JSONL
                git_branch=""  # Will be set from JSONL
            )
            
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue
                    
                    try:
                        data = json.loads(line)
                        self._process_entry(session, data)
                    except json.JSONDecodeError as e:
                        pass  # Skip malformed JSON lines
                        continue
            
            # Set session times
            if session.messages:
                session.start_time = self._parse_timestamp(session.messages[0].timestamp)
                session.end_time = self._parse_timestamp(session.messages[-1].timestamp)
                
                # Extract first user prompt
                for msg in session.messages:
                    if msg.role == "user" and msg.content:
                        session.user_prompt = msg.content[:200]  # First 200 chars
                        break
                
                # Extract last assistant message as final output
                for msg in reversed(session.messages):
                    if msg.role == "assistant" and msg.content:
                        session.final_output = msg.content[:200]
                        break
            
            return session
            
        except Exception as e:
            logger.error(f"Error parsing session file {file_path}: {e}")
            return None
    
    def _process_entry(self, session: ClaudeSession, data: Dict[str, Any]):
        """Process a single JSONL entry."""
        # Extract basic info
        entry_type = data.get('type', '')
        
        # Set project info from first entry
        if not session.cwd and 'cwd' in data:
            session.cwd = data['cwd']
        if not session.git_branch and 'gitBranch' in data:
            session.git_branch = data['gitBranch']
        
        # Process messages
        if 'message' in data:
            msg_data = data['message']
            
            # Handle different message formats
            if isinstance(msg_data, dict):
                msg = self._parse_message(msg_data, data)
                if msg:
                    session.messages.append(msg)
                    
                    # Process tool uses
                    for tool_use in msg.tool_uses:
                        self._process_tool_use(session, tool_use)
        
        # Process tool results
        if 'toolUseResult' in data:
            self._process_tool_result(session, data['toolUseResult'])
    
    def _parse_message(self, msg_data: Dict[str, Any], entry_data: Dict[str, Any]) -> Optional[ClaudeMessage]:
        """Parse a message from entry data."""
        role = msg_data.get('role', entry_data.get('userType', ''))
        
        # Extract content
        content = ""
        tool_uses = []
        
        if 'content' in msg_data:
            if isinstance(msg_data['content'], str):
                content = msg_data['content']
            elif isinstance(msg_data['content'], list):
                for item in msg_data['content']:
                    if isinstance(item, dict):
                        if item.get('type') == 'text':
                            content += item.get('text', '')
                        elif item.get('type') == 'tool_use':
                            tool_uses.append(item)
        
        if not role:
            return None
        
        return ClaudeMessage(
            role=role,
            content=content,
            timestamp=entry_data.get('timestamp', ''),
            message_type=entry_data.get('type', ''),
            tool_uses=tool_uses,
            uuid=entry_data.get('uuid', ''),
            parent_uuid=entry_data.get('parentUuid')
        )
    
    def _process_tool_use(self, session: ClaudeSession, tool_use: Dict[str, Any]):
        """Process a tool use entry."""
        tool_name = tool_use.get('name', '')
        
        # Track tool calls
        mapped_name = self.TOOL_MAPPINGS.get(tool_name, tool_name.lower())
        session.tool_calls[mapped_name] = session.tool_calls.get(mapped_name, 0) + 1
        
        # Extract file operations and commands
        if 'input' in tool_use:
            input_data = tool_use['input']
            
            # File operations
            if tool_name in ['Read', 'Glob']:
                file_path = input_data.get('file_path') or input_data.get('pattern', '')
                if file_path:
                    session.files_read.append(file_path)
            
            elif tool_name in ['Write', 'Edit', 'MultiEdit']:
                file_path = input_data.get('file_path', '')
                if file_path:
                    if tool_name == 'Write':
                        session.files_created.append(file_path)
                    else:
                        session.files_modified.append(file_path)
            
            # Command execution
            elif tool_name == 'Bash':
                command = input_data.get('command', '')
                if command:
                    session.commands_executed.append(command)
    
    def _process_tool_result(self, session: ClaudeSession, result: Any):
        """Process a tool result."""
        if isinstance(result, dict):
            # Check for file operations in results
            if 'filePath' in result:
                file_path = result['filePath']
                if 'oldString' in result:  # Edit operation
                    if file_path not in session.files_modified:
                        session.files_modified.append(file_path)
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse ISO format timestamp."""
        try:
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        except:
            return None
    
    def get_active_session(self, project_path: str) -> Optional[ClaudeSession]:
        """
        Get the most recent active session for a project.
        
        Args:
            project_path: Original project path
            
        Returns:
            Active session or None
        """
        session_files = self.find_session_files(project_path)
        
        if not session_files:
            return None
        
        # Check the most recent file
        latest_file = session_files[0]
        
        # Check if file was modified recently (within last minute)
        import time
        file_age = time.time() - latest_file.stat().st_mtime
        
        if file_age < 60:  # Active if modified within last minute
            return self.parse_session_file(latest_file)
        
        return None
    
    def watch_session(self, project_path: str) -> Iterator[ClaudeSession]:
        """
        Watch for changes in session files.
        
        Args:
            project_path: Original project path
            
        Yields:
            Updated sessions
        """
        project_dir = self.get_project_path(project_path)
        last_mtime = {}
        
        while True:
            try:
                if project_dir.exists():
                    for session_file in project_dir.glob("*.jsonl"):
                        current_mtime = session_file.stat().st_mtime
                        
                        if session_file not in last_mtime or last_mtime[session_file] < current_mtime:
                            last_mtime[session_file] = current_mtime
                            
                            session = self.parse_session_file(session_file)
                            if session:
                                yield session
                
                # Small delay to avoid excessive CPU usage
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error watching sessions: {e}")
                import time
                time.sleep(5)