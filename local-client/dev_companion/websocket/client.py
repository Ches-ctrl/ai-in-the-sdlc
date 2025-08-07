"""WebSocket client for receiving and executing commands."""

import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional

import websockets

from ..executor import CommandExecutor

logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client for receiving commands from server."""
    
    def __init__(self, config, session_monitor):
        """
        Initialize WebSocket client.
        
        Args:
            config: Configuration object
            session_monitor: Session monitor instance
        """
        self.config = config
        self.session_monitor = session_monitor
        self.session_monitor.ws_client = self  # Set reference for session finished notifications
        self.executor = CommandExecutor(config)
        self.running = False
        self.reconnect_delay = config.get('websocket', 'reconnect_interval')
        self.max_reconnect_delay = config.get('websocket', 'max_reconnect_delay')
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.metrics = {
            'commands_received': 0,
            'commands_executed': 0,
            'commands_failed': 0,
            'reconnect_attempts': 0,
            'connected_since': None
        }
    
    async def start(self):
        """Start WebSocket client."""
        self.running = True
        
        while self.running:
            try:
                await self._connect_and_listen()
            except websockets.exceptions.InvalidURI:
                logger.error(f"Invalid WebSocket URL: {self.config.get('websocket', 'url')}")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)
                    self._update_reconnect_delay()
    
    def stop(self):
        """Stop WebSocket client."""
        self.running = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())
    
    async def _connect_and_listen(self):
        """Connect to WebSocket server and listen for commands."""
        url = self.config.get('websocket', 'url')
        
        logger.info(f"Connecting to: {url}")
        
        # Prepare headers
        headers = {}
        token = self.config.get('api', 'token')
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        # Connect to server
        async with websockets.connect(url) as websocket:
            self.websocket = websocket
            logger.info("WebSocket connected")
            self._reset_reconnect_delay()
            self.metrics['connected_since'] = time.time()
            
            # Send initial connection message if there's an active session
            await self._send_active_sessions()
            
            # Create ping task
            ping_task = asyncio.create_task(self._ping_loop())
            
            try:
                while self.running:
                    try:
                        # Receive message with timeout
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=self.config.get('websocket', 'ping_interval') * 2
                        )
                        
                        # Process message
                        await self._handle_message(message)
                        
                    except asyncio.TimeoutError:
                        # No message received, continue
                        continue
                        
                    except websockets.exceptions.ConnectionClosed:
                        break  # Server closed connection
                        
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
            
            finally:
                ping_task.cancel()
                self.websocket = None
                self.metrics['connected_since'] = None
    
    async def _handle_message(self, message: str):
        """
        Handle incoming message from server.
        
        Args:
            message: Raw message from server
        """
        # Process incoming message
        
        try:
            data = json.loads(message)
            message_type = data.get('message_type', '')
            
            if message_type == 'execute_command':
                await self._handle_execute_command(data)
            elif message_type == "session_finished":
                ...
            else:
                logger.warning(message)
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    async def _handle_execute_command(self, data: Dict[str, Any]):
        """
        Handle execute_command message from server.
        
        Args:
            data: Parsed message data
        """
        command = data.get('command', '')
        
        if not command:
            logger.error("No command provided in execute_command message")
            return
        
        self.metrics['commands_received'] += 1
        
        # Extract optional parameters
        timeout = data.get('timeout')
        work_dir = data.get('work_dir')
        args = data.get('args', [])
        
        # Execute command
        result = await self.executor.execute(command, timeout, work_dir, args)
        
        # Update metrics
        self.metrics['commands_executed'] += 1
        if result['return_code'] != 0:
            self.metrics['commands_failed'] += 1
            self.session_monitor.record_error()
        
        # Record in session monitor
        self.session_monitor.record_command(command)
        
        # Send response to server
        response = {
            'message_type': 'command_executed',
            'output': result['stdout']
        }
        
        if 'error' in result:
            response['output']['error'] = result['error']
        
        await self.websocket.send(json.dumps(response))
        # Command response sent
    
    async def _send_active_sessions(self):
        """Send information about any active Claude sessions."""
        # Check if there are active sessions to report
        if hasattr(self.session_monitor, 'active_sessions'):
            for session_id in self.session_monitor.active_sessions:
                if session_id in self.session_monitor.sent_sessions:
                    # Session is active and has been sent to API
                    message = {
                        'message_type': 'session_active',
                        'session_id': session_id
                    }
                    await self.websocket.send(json.dumps(message))
                    pass  # Notified server of active session
    
    async def send_session_finished(self, server_session_id: str):
        """
        Send session_finished message to server.
        
        Args:
            server_session_id: The server's session ID to notify as finished
        """
        if self.websocket:
            message = {
                'message_type': 'session_finished',
                'session_id': server_session_id
            }
            try:
                await self.websocket.send(json.dumps(message))
                logger.info(f"Sent session_finished for server session: {server_session_id}")
            except Exception as e:
                logger.error(f"Failed to send session_finished: {e}")
    
    async def _ping_loop(self):
        """Send periodic pings to keep connection alive."""
        ping_interval = self.config.get('websocket', 'ping_interval')
        
        while self.running and self.websocket:
            try:
                await asyncio.sleep(ping_interval)
                if self.websocket:
                    await self.websocket.ping()
                    pass  # Ping sent
            except Exception:
                pass  # Ping failed
                break
    
    def _update_reconnect_delay(self):
        """Update reconnection delay with exponential backoff."""
        self.reconnect_delay = min(
            self.reconnect_delay * 1.5,
            self.max_reconnect_delay
        )
        self.metrics['reconnect_attempts'] += 1
    
    def _reset_reconnect_delay(self):
        """Reset reconnection delay to initial value."""
        self.reconnect_delay = self.config.get('websocket', 'reconnect_interval')
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get WebSocket client metrics."""
        return self.metrics.copy()