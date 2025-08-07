"""Session monitoring functionality - monitors Claude JSONL files only."""

import asyncio
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from dataclasses import asdict
from typing import Optional, Dict, Any, Set, List

from ..models import SessionStatus, GitInfo, EnvironmentInfo, SessionMetadata
from ..claude_parser import ClaudeSessionParser, ClaudeSession

logger = logging.getLogger(__name__)


class SessionMonitor:
    """Monitors Claude sessions by watching JSONL files."""
    
    def __init__(self, config, api_client):
        """
        Initialize session monitor.
        
        Args:
            config: Configuration object
            api_client: API client instance
        """
        self.config = config
        self.api_client = api_client
        self.running = False
        self.ws_client = None  # Will be set by WebSocketClient
        
        # Claude session tracking
        claude_home = config.get('session', 'claude_home')
        self.claude_parser = ClaudeSessionParser(claude_home)
        self.monitored_projects: List[str] = []
        self.active_sessions: Dict[str, ClaudeSession] = {}
        self.server_session_ids: Dict[str, str] = {}  # Map Claude session ID -> Server session ID
        self.sent_sessions: Set[str] = set()  # Track sessions we've already sent start for
        self.session_last_modified: Dict[str, float] = {}  # Track file modification times
    
    async def start(self):
        """Start monitoring Claude sessions."""
        self.running = True
        
        # Get monitored projects from config or use current directory
        self.monitored_projects = self.config.get('session', 'monitored_projects') or [os.getcwd()]
        
        # Also check if specific project paths are provided
        if self.config.get('session', 'project_path'):
            self.monitored_projects.append(self.config.get('session', 'project_path'))
        
        logger.info(f"Monitoring Claude sessions in: {self.claude_parser.claude_home}")
        
        # Start monitoring Claude files
        await self._monitor_claude_files()
    
    def stop(self):
        """Stop monitoring sessions."""
        self.running = False
        
        # End any active sessions
        for session_id, session in self.active_sessions.items():
            if session_id in self.sent_sessions:
                asyncio.create_task(self._end_claude_session(session, 'shutdown'))
    
    async def _monitor_claude_files(self):
        """Monitor Claude JSONL session files."""
        monitor_interval = self.config.get('session', 'monitor_interval') or 0.5
        seen_files = {}  # Track files we've already seen with their initial mtime
        startup_time = time.time()  # Record when monitoring started
        
        # On startup, check existing files but DON'T send starts yet
        # We'll send starts when they actually get modified
        logger.info(f"Checking existing sessions on startup...")
        for project_path in self.monitored_projects:
            existing_files = self.claude_parser.find_session_files(project_path)
            for session_file in existing_files:
                mtime = session_file.stat().st_mtime
                seen_files[session_file] = mtime
                
                # Log what we found
                file_age = time.time() - mtime
                logger.info(f"  Found {session_file.name} (age: {file_age:.0f}s)")
                
                # Don't pre-load sessions - let them be detected when modified
        
        # Start monitoring for changes
        
        while self.running:
            try:
                for project_path in self.monitored_projects:
                    # Find all session files for this project
                    session_files = self.claude_parser.find_session_files(project_path)
                    
                    for session_file in session_files:
                        current_mtime = session_file.stat().st_mtime
                        file_age = time.time() - current_mtime
                        session_id = session_file.stem
                        
                        # Track this session's file modification time
                        self.session_last_modified[session_id] = current_mtime
                        
                        # Check if this is a NEW file (not seen before or modified after we saw it)
                        is_new_file = session_file not in seen_files
                        is_modified = session_file in seen_files and current_mtime > seen_files[session_file]
                        
                        if is_new_file:
                            logger.info(f"New session file detected: {session_file.name}")
                            seen_files[session_file] = current_mtime
                        elif is_modified:
                            seen_files[session_file] = current_mtime
                        
                        # Process if it's new/modified (regardless of age for modified files)
                        # For new files, only process if recently created
                        should_process = is_modified or (is_new_file and file_age < 120)
                        
                        if should_process:
                            # Parse the session
                            claude_session = self.claude_parser.parse_session_file(session_file)
                            
                            if claude_session:
                                session_id = claude_session.session_id
                                
                                # Check if this is a new session to track
                                if session_id not in self.active_sessions:
                                    logger.info(f"Tracking new session: {session_id[:8]}...")
                                    self.active_sessions[session_id] = claude_session
                                    
                                    # Send session start if not already sent
                                    if session_id not in self.sent_sessions:
                                        await self._start_claude_session(claude_session)
                                        self.sent_sessions.add(session_id)
                                else:
                                    # Update existing session
                                    old_message_count = len(self.active_sessions[session_id].messages) if session_id in self.active_sessions else 0
                                    self.active_sessions[session_id] = claude_session
                                    
                                    # If this session wasn't sent yet (file existed but wasn't active), send start now
                                    if session_id not in self.sent_sessions:
                                        logger.info(f"Session {session_id[:8]}... became active, sending start")
                                        await self._start_claude_session(claude_session)
                                        self.sent_sessions.add(session_id)
                                    elif len(claude_session.messages) > old_message_count:
                                        # New messages added
                                        ...

                # Check ALL tracked sessions for inactivity based on file modification time
                current_time = time.time()
                inactive_timeout = 5
                sessions_to_end = []
                
                for session_id in list(self.active_sessions.keys()):
                    if session_id in self.session_last_modified:
                        # Check how long since the file was last modified
                        time_since_modified = current_time - self.session_last_modified[session_id]
                        if time_since_modified > inactive_timeout and session_id in self.sent_sessions:
                            sessions_to_end.append(session_id)
                
                # End inactive sessions
                for session_id in sessions_to_end:
                    logger.info(f"Ending inactive session: {session_id[:8]}... (inactive for {(current_time - self.session_last_modified[session_id]):.0f}s)")
                    
                    # Get server session ID before calling _end_claude_session (which deletes it)
                    server_session_id = self.server_session_ids.get(session_id)
                    
                    await self._end_claude_session(self.active_sessions[session_id], 'inactive')
                    
                    # Notify WebSocket client if connected
                    logger.info("Before Sending session finished notification to WebSocket client")
                    if self.ws_client and server_session_id:
                        logger.info(f"Sending session finished notification to WebSocket client for server session: {server_session_id}")
                        await self.ws_client.send_session_finished(server_session_id)
                    
                    del self.active_sessions[session_id]
                    if session_id in self.session_last_modified:
                        del self.session_last_modified[session_id]
                    self.sent_sessions.discard(session_id)
                
                await asyncio.sleep(monitor_interval)
                
            except Exception as e:
                logger.error(f"Claude file monitor error: {e}", exc_info=True)
                await asyncio.sleep(monitor_interval or 0.5)
    
    async def _start_claude_session(self, claude_session: ClaudeSession):
        """Send session start event for a Claude session."""
        logger.info(f"Session started: {claude_session.session_id[:8]}...")
        
        # Get git info from the session's working directory
        git_info = self._get_git_info(claude_session.cwd)
        
        # According to OpenAPI spec, only user_prompt is required for session/start
        request_data = {
            'user_prompt': claude_session.user_prompt or "Claude Code session"
        }
        
        try:
            response = await self.api_client.send_session_start(request_data)
            if response and 'session_id' in response:
                # Store the server's session ID mapped to Claude's session ID
                server_session_id = response['session_id']
                self.server_session_ids[claude_session.session_id] = server_session_id
                # Session start successful
            else:
                logger.error(f"No session_id in response for Claude session: {claude_session.session_id}")
            
            # Cache session if enabled
            if self.config.get('session', 'enable_cache'):
                request_data['session_id'] = claude_session.session_id
                self._cache_session(request_data)
                
        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            logger.error(f"Failed to send session start: {e}")
    
    async def _end_claude_session(self, claude_session: ClaudeSession, reason: str = 'completed'):
        """Send session end event for a Claude session."""
        # Only send session end if we have a server session ID (meaning we sent session start)
        if claude_session.session_id not in self.server_session_ids:
            return
            
        server_session_id = self.server_session_ids[claude_session.session_id]
        logger.info(f"Sending session end for {claude_session.session_id[:8]}... (reason: {reason})")
        
        # Create metadata from Claude session (optional per OpenAPI spec)
        metadata = {
            'tool_calls': [{'name': name, 'count': count} for name, count in claude_session.tool_calls.items()],
            'files_modified': claude_session.files_modified,
            'files_created': claude_session.files_created,
            'commands_run': claude_session.commands_executed
        }
        
        # According to OpenAPI spec: session_id, final_output, and status are required
        request_data = {
            'session_id': server_session_id,  # Use SERVER's session ID
            'final_output': claude_session.final_output or "Session completed",
            'status': self._map_reason_to_status(reason),
            'metadata': metadata if any(metadata.values()) else None  # Only include if has data
        }
        
        try:
            await self.api_client.send_session_end(request_data)
            # Clean up the mapping
            del self.server_session_ids[claude_session.session_id]
        except Exception as e:
            logger.error(f"Failed to send session end: {e}")
    
    def _get_git_info(self, working_dir: Optional[str] = None) -> GitInfo:
        """Get git repository information."""
        git_info = GitInfo()
        
        # Use provided working directory or current
        cwd = working_dir or os.getcwd()
        
        try:
            # Get branch
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                capture_output=True, text=True, timeout=5, cwd=cwd
            )
            if result.returncode == 0:
                git_info.branch = result.stdout.strip()
            
            # Get commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True, text=True, timeout=5, cwd=cwd
            )
            if result.returncode == 0:
                git_info.commit_hash = result.stdout.strip()
            
            # Get commit message
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%B'],
                capture_output=True, text=True, timeout=5, cwd=cwd
            )
            if result.returncode == 0:
                git_info.commit_message = result.stdout.strip()
            
            # Get author
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%an'],
                capture_output=True, text=True, timeout=5, cwd=cwd
            )
            if result.returncode == 0:
                git_info.author = result.stdout.strip()
            
            # Check if dirty
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True, text=True, timeout=5, cwd=cwd
            )
            if result.returncode == 0:
                git_info.is_dirty = len(result.stdout.strip()) > 0
                
        except Exception:
            pass  # Silently handle git errors
        
        return git_info
    
    def _map_reason_to_status(self, reason: str) -> str:
        """Map termination reason to session status."""
        mapping = {
            'completed': SessionStatus.COMPLETED.value,
            'inactive': SessionStatus.COMPLETED.value,
            'failed': SessionStatus.FAILED.value,
            'error': SessionStatus.FAILED.value,
            'cancelled': SessionStatus.CANCELLED.value,
            'shutdown': SessionStatus.CANCELLED.value
        }
        return mapping.get(reason, SessionStatus.COMPLETED.value)
    
    def _cache_session(self, session_data: Dict[str, Any]):
        """Cache session data to disk."""
        cache_dir = Path(self.config.get('session', 'cache_dir'))
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        cache_file = cache_dir / f"{session_data['session_id']}.json"
        try:
            import json
            cache_file.write_text(json.dumps(session_data, indent=2))
        except Exception:
            pass  # Silently handle cache errors
    
    # Methods for WebSocket client to record metrics
    def record_command(self, command: str):
        """Record a command execution from WebSocket."""
        # Find the most recent active session
        if self.active_sessions:
            latest_session = list(self.active_sessions.values())[-1]
            if command not in latest_session.commands_executed:
                latest_session.commands_executed.append(command)
    
    def record_error(self):
        """Record an error from WebSocket."""
        # This could be implemented if needed
        pass