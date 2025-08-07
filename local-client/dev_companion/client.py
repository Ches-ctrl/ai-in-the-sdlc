"""Main client application."""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional, List

from .config import Config
from .api import APIClient
from .session import SessionMonitor
from .websocket import WebSocketClient

logger = logging.getLogger(__name__)


class DevCompanionClient:
    """Main application class for Dev Companion Client."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize Dev Companion Client.
        
        Args:
            config: Optional Config object
        """
        # Load configuration
        self.config = config or Config()
        
        # Setup logging
        self._setup_logging()
        
        # Initialize components
        self.api_client: Optional[APIClient] = None
        self.session_monitor: Optional[SessionMonitor] = None
        self.ws_client: Optional[WebSocketClient] = None
        self.tasks: List[asyncio.Task] = []
        self.shutdown_event = asyncio.Event()
    
    def _setup_logging(self):
        """Configure logging based on configuration."""
        log_level = getattr(logging, self.config.get('logging', 'level'), logging.INFO)
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Set level for our loggers
        logging.getLogger('dev_companion').setLevel(log_level)
    
    async def start(self):
        """Start the client application."""
        logger.info("Starting Dev Companion Client")
        logger.info(f"API: {self.config.get('api', 'base_url')}")
        logger.info(f"WebSocket: {self.config.get('websocket', 'url')}")
        
        # Initialize components
        self.api_client = APIClient(self.config)
        self.session_monitor = SessionMonitor(self.config, self.api_client)
        self.ws_client = WebSocketClient(self.config, self.session_monitor)
        
        # Create tasks
        self.tasks = [
            asyncio.create_task(self.session_monitor.start(), name="session_monitor"),
            asyncio.create_task(self.ws_client.start(), name="websocket_client"),
            asyncio.create_task(self._wait_for_shutdown(), name="shutdown_waiter")
        ]
        
        try:
            # Wait for all tasks
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass  # Tasks cancelled
        finally:
            await self._cleanup()
    
    async def _wait_for_shutdown(self):
        """Wait for shutdown signal."""
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        
        def signal_handler():
            pass  # Received shutdown signal
            self.shutdown_event.set()
        
        # Register signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)
        
        # Wait for shutdown event
        await self.shutdown_event.wait()
        
        # Trigger shutdown
        await self.shutdown()
    
    async def shutdown(self):
        """Shutdown the client gracefully."""
        # Initiating graceful shutdown
        
        # Stop components
        if self.session_monitor:
            self.session_monitor.stop()
        if self.ws_client:
            self.ws_client.stop()
        
        # Cancel remaining tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
    
    async def _cleanup(self):
        """Cleanup resources."""
        # Close API client session
        if self.api_client:
            await self.api_client.close()
        
        logger.info("Dev Companion Client stopped")
    
    def run(self):
        """Run the client (synchronous entry point)."""
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            pass  # Interrupted by user
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)