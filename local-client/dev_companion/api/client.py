"""API client for session management."""

import asyncio
import logging
from typing import Dict, Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class APIClient:
    """Handles API communication with the server."""
    
    def __init__(self, config):
        """
        Initialize API client.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.metrics = {
            'requests_sent': 0,
            'requests_failed': 0
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def ensure_session(self):
        """Ensure HTTP session is created."""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def send_session_start(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send session start event to API.
        
        Args:
            data: Session start data
            
        Returns:
            Response data including server session_id
        """
        url = self.config.get('api', 'base_url') + self.config.get('api', 'start_path')
        return await self._send_request('POST', url, data)
    
    async def send_session_end(self, data: Dict[str, Any]):
        """
        Send session end event to API.
        
        Args:
            data: Session end data
        """
        url = self.config.get('api', 'base_url') + self.config.get('api', 'end_path')
        await self._send_request('POST', url, data)
    
    async def _send_request(self, method: str, url: str, data: Dict[str, Any]):
        """
        Send HTTP request with retries.
        
        Args:
            method: HTTP method
            url: Request URL
            data: Request data
        """
        await self.ensure_session()
        
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'dev-companion/1.0'
        }
        
        token = self.config.get('api', 'token')
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        retry_count = self.config.get('api', 'retry_count')
        retry_delay = self.config.get('api', 'retry_delay')
        timeout = aiohttp.ClientTimeout(total=self.config.get('api', 'timeout'))
        
        for attempt in range(retry_count + 1):
            try:
                async with self.session.request(
                    method, url, 
                    json=data, 
                    headers=headers,
                    timeout=timeout
                ) as response:
                    if response.status < 300:
                        logger.debug(f"API request successful: {url}")
                        self.metrics['requests_sent'] += 1
                        # Return JSON response if available
                        try:
                            return await response.json()
                        except:
                            return None
                    
                    # Retry on server errors or rate limiting
                    if response.status >= 500 or response.status == 429:
                        if attempt < retry_count:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                    
                    text = await response.text()
                    raise Exception(f"API error {response.status}: {text}")
                    
            except asyncio.TimeoutError:
                logger.warning(f"API request timeout (attempt {attempt + 1}/{retry_count + 1})")
                if attempt < retry_count:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                self.metrics['requests_failed'] += 1
                raise
                
            except Exception as e:
                if attempt < retry_count:
                    logger.debug(f"API request failed (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                logger.error(f"API request failed: {e}")
                self.metrics['requests_failed'] += 1
                raise