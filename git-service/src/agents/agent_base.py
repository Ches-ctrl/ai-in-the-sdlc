"""Base class for AI agents in the git-service."""

import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from datetime import datetime
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentBase(ABC):
    """Base class for all AI agents in the system."""
    
    def __init__(self, name: str, verbose: bool = False):
        """Initialize the agent.
        
        Args:
            name: Name of the agent
            verbose: Enable verbose logging
        """
        self.name = name
        self.verbose = verbose
        self.start_time = None
        self.metadata = {}
        
    def _log(self, message: str, level: str = "info"):
        """Log a message with the agent's name.
        
        Args:
            message: Message to log
            level: Log level (info, warning, error, debug)
        """
        formatted_message = f"[{self.name}] {message}"
        
        if level == "error":
            logger.error(formatted_message)
        elif level == "warning":
            logger.warning(formatted_message)
        elif level == "debug":
            logger.debug(formatted_message)
        else:
            logger.info(formatted_message)
            
        if self.verbose:
            print(f"{datetime.now().isoformat()} - {formatted_message}")
    
    def start_timer(self):
        """Start timing the agent's execution."""
        self.start_time = datetime.now()
        self._log(f"Starting execution at {self.start_time.isoformat()}")
    
    def get_elapsed_time(self) -> Optional[float]:
        """Get elapsed time in seconds since start_timer was called.
        
        Returns:
            Elapsed time in seconds or None if timer not started
        """
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            return elapsed
        return None
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to the agent's execution.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        self.metadata[key] = value
        self._log(f"Added metadata: {key}={value}", "debug")
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the agent's main task.
        
        This method must be implemented by all subclasses.
        
        Returns:
            Dictionary containing the execution results
        """
        pass
    
    async def run(self, **kwargs) -> Dict[str, Any]:
        """Run the agent with timing and error handling.
        
        Returns:
            Dictionary containing results and metadata
        """
        try:
            self.start_timer()
            self._log("Agent execution started")
            
            # Execute the main task
            result = await self.execute(**kwargs)
            
            # Add execution metadata
            elapsed_time = self.get_elapsed_time()
            
            return {
                "success": True,
                "agent": self.name,
                "result": result,
                "metadata": self.metadata,
                "execution_time_seconds": elapsed_time,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self._log(f"Agent execution failed: {str(e)}", "error")
            elapsed_time = self.get_elapsed_time()
            
            return {
                "success": False,
                "agent": self.name,
                "error": str(e),
                "metadata": self.metadata,
                "execution_time_seconds": elapsed_time,
                "timestamp": datetime.now().isoformat()
            }


class ProgressReporter:
    """Helper class for reporting agent progress."""
    
    def __init__(self, total_steps: int, callback=None):
        """Initialize the progress reporter.
        
        Args:
            total_steps: Total number of steps in the process
            callback: Optional async callback for progress updates
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.callback = callback
        self.messages = []
        
    async def update(self, step: int, message: str, details: Optional[Dict[str, Any]] = None):
        """Update progress.
        
        Args:
            step: Current step number
            message: Progress message
            details: Optional additional details
        """
        self.current_step = step
        progress_percentage = int((step / self.total_steps) * 100)
        
        update_data = {
            "step": step,
            "total_steps": self.total_steps,
            "percentage": progress_percentage,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.messages.append(update_data)
        
        if self.callback:
            await self.callback(update_data)
        
        return update_data
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress status.
        
        Returns:
            Dictionary with progress information
        """
        return {
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "percentage": int((self.current_step / self.total_steps) * 100),
            "messages": self.messages
        }