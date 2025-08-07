"""Command execution with security controls."""

import asyncio
import logging
import os
import time
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class CommandExecutor:
    """Executes commands with security controls and output management."""
    
    # Default dangerous patterns to check
    DANGEROUS_PATTERNS = [
        '../../', '..\\..\\',
        '/etc/shadow', '/etc/passwd',
        'C:\\Windows\\System32\\config',
        '> /dev/', '| dd', 'mkfs.',
        ':(){ :|:& };:'  # Fork bomb
    ]
    
    def __init__(self, config):
        """
        Initialize command executor.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.metrics = {
            'commands_executed': 0,
            'commands_failed': 0,
            'total_duration': 0,
            'last_executed': None
        }
    
    async def execute(
        self, 
        command: str, 
        timeout: Optional[int] = None,
        work_dir: Optional[str] = None, 
        args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Execute a command and return results.
        
        Args:
            command: Command to execute
            timeout: Execution timeout in seconds
            work_dir: Working directory
            args: Command arguments
            
        Returns:
            Dictionary with execution results
        """
        start_time = time.time()
        
        # Validate command
        if not self._validate_command(command):
            return self._create_error_response(
                'Command blocked by security policy',
                start_time
            )
        
        # Prepare timeout
        if timeout is None:
            timeout = self.config.get('executor', 'default_timeout')
        timeout = min(timeout, self.config.get('executor', 'max_timeout'))
        
        # Prepare working directory
        if not work_dir:
            work_dir = self.config.get('executor', 'work_dir') or os.getcwd()
        
        # Validate working directory
        if not self._validate_path(work_dir):
            return self._create_error_response(
                'Invalid working directory',
                start_time
            )
        
        try:
            # Build command
            if args:
                cmd = [command] + args
                cmd_str = ' '.join(cmd)
            else:
                cmd_str = command
            
            # Execute command
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir
            )
            
            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return self._create_error_response(
                    f'Command timed out after {timeout} seconds',
                    start_time
                )
            
            # Process output
            stdout_text = self._decode_and_limit(stdout)
            stderr_text = self._decode_and_limit(stderr)
            
            # Update metrics
            self._update_metrics(process.returncode == 0, start_time)
            
            return {
                'stdout': stdout_text,
                'stderr': stderr_text,
                'return_code': process.returncode,
                'duration_ms': int((time.time() - start_time) * 1000),
                'timestamp': int(time.time())
            }
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            self._update_metrics(False, start_time)
            
            return self._create_error_response(str(e), start_time)
    
    def _validate_command(self, command: str) -> bool:
        """
        Validate command against security policies.
        
        Args:
            command: Command to validate
            
        Returns:
            True if command is allowed
        """
        if not command:
            return False
        
        # Extract base command
        base_cmd = command.split()[0] if command else ''
        base_cmd = os.path.basename(base_cmd).lower()
        
        # Check blocked commands
        blocked = self.config.get('executor', 'blocked_commands')
        if base_cmd in [b.lower() for b in blocked]:
            logger.warning(f"Blocked command: {base_cmd}")
            return False
        
        # Check allowed commands if whitelist is configured
        allowed = self.config.get('executor', 'allowed_commands')
        if allowed and base_cmd not in [a.lower() for a in allowed]:
            logger.warning(f"Command not in allowed list: {base_cmd}")
            return False
        
        # Check for dangerous patterns
        command_lower = command.lower()
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.lower() in command_lower:
                logger.warning(f"Dangerous pattern detected: {pattern}")
                return False
        
        return True
    
    def _validate_path(self, path: str) -> bool:
        """
        Validate a file path.
        
        Args:
            path: Path to validate
            
        Returns:
            True if path is valid
        """
        try:
            # Resolve to absolute path
            abs_path = os.path.abspath(path)
            
            # Check if it exists and is a directory
            if not os.path.exists(abs_path) or not os.path.isdir(abs_path):
                return False
            
            # Check for path traversal
            if '..' in path:
                return False
            
            return True
        except Exception:
            return False
    
    def _decode_and_limit(self, data: bytes) -> str:
        """
        Decode bytes and limit output size.
        
        Args:
            data: Raw bytes output
            
        Returns:
            Decoded and limited string
        """
        if not data:
            return ''
        
        # Decode
        text = data.decode('utf-8', errors='replace')
        
        # Limit size
        max_size = self.config.get('executor', 'max_output_size')
        if len(text) > max_size:
            text = text[:max_size] + '\n[Output truncated]'
        
        return text
    
    def _create_error_response(self, error_msg: str, start_time: float) -> Dict[str, Any]:
        """
        Create an error response.
        
        Args:
            error_msg: Error message
            start_time: Command start time
            
        Returns:
            Error response dictionary
        """
        return {
            'stdout': '',
            'stderr': error_msg,
            'return_code': -1,
            'error': error_msg,
            'duration_ms': int((time.time() - start_time) * 1000),
            'timestamp': int(time.time())
        }
    
    def _update_metrics(self, success: bool, start_time: float):
        """
        Update execution metrics.
        
        Args:
            success: Whether command succeeded
            start_time: Command start time
        """
        self.metrics['commands_executed'] += 1
        if not success:
            self.metrics['commands_failed'] += 1
        
        duration = int((time.time() - start_time) * 1000)
        self.metrics['total_duration'] += duration
        self.metrics['last_executed'] = time.time()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get executor metrics."""
        return self.metrics.copy()