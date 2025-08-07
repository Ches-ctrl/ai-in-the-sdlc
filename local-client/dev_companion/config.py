"""Configuration management module - uses environment variables only."""

import os
from pathlib import Path
from dotenv import load_dotenv


class Config:
    """Configuration management for Dev Companion Client using environment variables."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Load .env file
        load_dotenv()
        
        # Core settings with defaults
        self.api_base_url = os.getenv('DEV_COMPANION_API_BASE_URL', 'http://localhost:8000')
        self.api_token = os.getenv('DEV_COMPANION_API_TOKEN', '')
        self.ws_url = os.getenv('DEV_COMPANION_WS_URL', 'ws://localhost:8000/ws/execute')
        self.log_level = os.getenv('DEV_COMPANION_LOG_LEVEL', 'INFO')
        
        # Claude monitoring settings
        self.claude_home = os.path.expanduser(os.getenv('DEV_COMPANION_CLAUDE_HOME', '~/.claude'))
        
        # Parse monitored projects (comma-separated list)
        projects_env = os.getenv('DEV_COMPANION_MONITORED_PROJECTS', '')
        if projects_env:
            self.monitored_projects = [p.strip() for p in projects_env.split(',') if p.strip()]
        else:
            # Default to current working directory
            self.monitored_projects = [os.getcwd()]
        
        # Optional advanced settings (rarely needed)
        self.api_timeout = int(os.getenv('DEV_COMPANION_API_TIMEOUT', '30'))
        self.monitor_interval = int(os.getenv('DEV_COMPANION_MONITOR_INTERVAL', '5'))
        self.command_timeout = int(os.getenv('DEV_COMPANION_COMMAND_TIMEOUT', '30'))
        self.max_output_size = int(os.getenv('DEV_COMPANION_MAX_OUTPUT_SIZE', '10485760'))  # 10MB
        
        # Cache directory
        self.cache_dir = os.getenv('DEV_COMPANION_CACHE_DIR', '/tmp/dev-companion')
    
    def get(self, *path):
        """
        Get a configuration value by path (for backward compatibility).
        
        Args:
            *path: Path to configuration value
            
        Returns:
            Configuration value or default
        """
        # Map old path-based access to new flat structure
        if len(path) == 2:
            section, key = path
            
            if section == 'api':
                if key == 'base_url':
                    return self.api_base_url
                elif key == 'token':
                    return self.api_token
                elif key == 'timeout':
                    return self.api_timeout
                elif key == 'start_path':
                    return '/session/start'
                elif key == 'end_path':
                    return '/session/end'
                elif key == 'retry_count':
                    return 3
                elif key == 'retry_delay':
                    return 1
                    
            elif section == 'websocket':
                if key == 'url':
                    return self.ws_url
                elif key == 'reconnect_interval':
                    return 5
                elif key == 'max_reconnect_delay':
                    return 300
                elif key == 'ping_interval':
                    return 30
                    
            elif section == 'session':
                if key == 'monitor_interval':
                    return self.monitor_interval
                elif key == 'claude_home':
                    return self.claude_home
                elif key == 'monitored_projects':
                    return self.monitored_projects
                elif key == 'cache_dir':
                    return self.cache_dir
                elif key == 'enable_cache':
                    return True
                    
            elif section == 'executor':
                if key == 'default_timeout':
                    return self.command_timeout
                elif key == 'max_timeout':
                    return 600
                elif key == 'max_output_size':
                    return self.max_output_size
                elif key == 'blocked_commands':
                    return [
                        'rm', 'del', 'format', 'fdisk', 'dd', 'mkfs',
                        'shutdown', 'reboot', 'init', 'systemctl',
                        'passwd', 'useradd', 'userdel', 'usermod',
                        'chown', 'chmod', 'chgrp'
                    ]
                elif key == 'allowed_commands':
                    return []
                elif key == 'work_dir':
                    return ''
                    
            elif section == 'logging':
                if key == 'level':
                    return self.log_level
        
        # Default return for unknown paths
        return None