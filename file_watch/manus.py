#!/usr/bin/env python3
"""
Claude Code Monitor - Stream Claude conversations to external applications

This script monitors Claude Code's JSONL conversation files for changes and
streams prompts and responses to a secondary application via HTTP, WebSocket,
or file output.

Author: Generated for Claude Code monitoring
License: MIT
"""

import json
import os
import time
import logging
import argparse
import requests
import websocket
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import queue


@dataclass
class ClaudeMessage:
    """Represents a parsed Claude message"""
    type: str
    content: str
    timestamp: str
    session_id: str
    project_name: str
    file_path: str
    token_usage: Optional[Dict[str, int]] = None
    tool_name: Optional[str] = None
    tool_result: Optional[str] = None


class ClaudeFileHandler(FileSystemEventHandler):
    """Handles file system events for Claude JSONL files"""
    
    def __init__(self, message_queue: queue.Queue, claude_dir: Path):
        self.message_queue = message_queue
        self.claude_dir = claude_dir
        self.processed_files = {}  # Track file positions
        self.logger = logging.getLogger(__name__)
        
    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        if file_path.suffix == '.jsonl' and 'projects' in file_path.parts:
            self.logger.info(f"Detected change in {file_path}")
            self.process_jsonl_file(file_path)
    
    def on_created(self, event):
        """Handle file creation events"""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        if file_path.suffix == '.jsonl' and 'projects' in file_path.parts:
            self.logger.info(f"New file created: {file_path}")
            self.process_jsonl_file(file_path)
    
    def process_jsonl_file(self, file_path: Path):
        """Process a JSONL file and extract new messages"""
        try:
            # Get project name from path
            project_name = self.extract_project_name(file_path)
            
            # Track file position to only read new lines
            last_position = self.processed_files.get(str(file_path), 0)
            
            with open(file_path, 'r', encoding='utf-8') as f:
                f.seek(last_position)
                new_lines = f.readlines()
                self.processed_files[str(file_path)] = f.tell()
            
            # Parse new lines
            for line in new_lines:
                line = line.strip()
                if line:
                    try:
                        message_data = json.loads(line)
                        message = self.parse_message(message_data, project_name, file_path)
                        if message:
                            self.message_queue.put(message)
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse JSON line: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
    
    def extract_project_name(self, file_path: Path) -> str:
        """Extract project name from file path"""
        parts = file_path.parts
        try:
            projects_index = parts.index('projects')
            if projects_index + 1 < len(parts):
                return parts[projects_index + 1]
        except ValueError:
            pass
        return "unknown"
    
    def parse_message(self, data: Dict[str, Any], project_name: str, file_path: Path) -> Optional[ClaudeMessage]:
        """Parse a message from JSONL data"""
        try:
            message_type = data.get('type', 'unknown')
            content = data.get('content', '')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            session_id = data.get('session_id', 'unknown')
            
            # Handle different message types
            if message_type in ['user', 'assistant']:
                return ClaudeMessage(
                    type=message_type,
                    content=content,
                    timestamp=timestamp,
                    session_id=session_id,
                    project_name=project_name,
                    file_path=str(file_path),
                    token_usage=data.get('token_usage')
                )
            elif message_type == 'tool_use':
                return ClaudeMessage(
                    type=message_type,
                    content=f"Tool: {data.get('tool_name', 'unknown')}",
                    timestamp=timestamp,
                    session_id=session_id,
                    project_name=project_name,
                    file_path=str(file_path),
                    tool_name=data.get('tool_name'),
                    tool_result=str(data.get('parameters', {}))
                )
            elif message_type == 'tool_result':
                return ClaudeMessage(
                    type=message_type,
                    content=f"Result: {data.get('result', 'No result')}",
                    timestamp=timestamp,
                    session_id=session_id,
                    project_name=project_name,
                    file_path=str(file_path),
                    tool_name=data.get('tool_name'),
                    tool_result=data.get('result')
                )
                
        except Exception as e:
            self.logger.error(f"Error parsing message: {e}")
        
        return None


class MessageStreamer:
    """Handles streaming messages to external applications"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.output_methods = []
        
        # Initialize output methods based on config
        if config.get('http_endpoint'):
            self.output_methods.append(self.send_http)
        if config.get('websocket_url'):
            self.output_methods.append(self.send_websocket)
        if config.get('output_file'):
            self.output_methods.append(self.write_file)
        if config.get('console_output', True):
            self.output_methods.append(self.print_console)
    
    def stream_message(self, message: ClaudeMessage):
        """Stream a message using all configured methods"""
        for method in self.output_methods:
            try:
                method(message)
            except Exception as e:
                self.logger.error(f"Error in output method {method.__name__}: {e}")
    
    def send_http(self, message: ClaudeMessage):
        """Send message via HTTP POST"""
        endpoint = self.config['http_endpoint']
        headers = {'Content-Type': 'application/json'}
        data = asdict(message)
        
        response = requests.post(endpoint, json=data, headers=headers, timeout=5)
        response.raise_for_status()
        self.logger.debug(f"Sent message to HTTP endpoint: {response.status_code}")
    
    def send_websocket(self, message: ClaudeMessage):
        """Send message via WebSocket"""
        # Note: This is a simplified implementation
        # In production, you'd want to maintain a persistent connection
        ws_url = self.config['websocket_url']
        ws = websocket.create_connection(ws_url)
        ws.send(json.dumps(asdict(message)))
        ws.close()
        self.logger.debug("Sent message via WebSocket")
    
    def write_file(self, message: ClaudeMessage):
        """Write message to output file"""
        output_file = self.config['output_file']
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(asdict(message)) + '\n')
        self.logger.debug(f"Wrote message to {output_file}")
    
    def print_console(self, message: ClaudeMessage):
        """Print message to console"""
        timestamp = datetime.fromisoformat(message.timestamp.replace('Z', '+00:00'))
        print(f"\n[{timestamp.strftime('%H:%M:%S')}] {message.project_name}/{message.session_id}")
        print(f"Type: {message.type}")
        if message.type == 'user':
            print(f"Prompt: {message.content[:200]}{'...' if len(message.content) > 200 else ''}")
        elif message.type == 'assistant':
            print(f"Response: {message.content[:200]}{'...' if len(message.content) > 200 else ''}")
            if message.token_usage:
                print(f"Tokens: {message.token_usage}")
        elif message.type in ['tool_use', 'tool_result']:
            print(f"Tool: {message.tool_name} - {message.content[:100]}{'...' if len(message.content) > 100 else ''}")
        print("-" * 50)


class ClaudeMonitor:
    """Main monitor class that coordinates file watching and message streaming"""
    
    def __init__(self, claude_dir: str, config: Dict[str, Any]):
        self.claude_dir = Path(claude_dir).expanduser()
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.message_queue = queue.Queue()
        self.streamer = MessageStreamer(config)
        self.observer = None
        self.running = False
        
    def start(self):
        """Start monitoring Claude files"""
        if not self.claude_dir.exists():
            raise FileNotFoundError(f"Claude directory not found: {self.claude_dir}")
        
        projects_dir = self.claude_dir / 'projects'
        if not projects_dir.exists():
            raise FileNotFoundError(f"Projects directory not found: {projects_dir}")
        
        self.logger.info(f"Starting Claude monitor on {projects_dir}")
        
        # Process existing files first
        self.process_existing_files()
        
        # Set up file watcher
        event_handler = ClaudeFileHandler(self.message_queue, self.claude_dir)
        self.observer = Observer()
        self.observer.schedule(event_handler, str(projects_dir), recursive=True)
        
        # Start message processing thread
        self.running = True
        message_thread = threading.Thread(target=self.process_messages, daemon=True)
        message_thread.start()
        
        # Start file observer
        self.observer.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop monitoring"""
        self.logger.info("Stopping Claude monitor...")
        self.running = False
        if self.observer:
            self.observer.stop()
            self.observer.join()
    
    def process_existing_files(self):
        """Process existing JSONL files on startup"""
        projects_dir = self.claude_dir / 'projects'
        for jsonl_file in projects_dir.rglob('*.jsonl'):
            self.logger.info(f"Processing existing file: {jsonl_file}")
            handler = ClaudeFileHandler(self.message_queue, self.claude_dir)
            handler.process_jsonl_file(jsonl_file)
    
    def process_messages(self):
        """Process messages from the queue"""
        while self.running:
            try:
                message = self.message_queue.get(timeout=1)
                self.streamer.stream_message(message)
                self.message_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")


def setup_logging(level: str = 'INFO'):
    """Set up logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('claude_monitor.log')
        ]
    )


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Monitor Claude Code conversations')
    parser.add_argument('--claude-dir', default='~/.claude', 
                       help='Path to Claude directory (default: ~/.claude)')
    parser.add_argument('--http-endpoint', 
                       help='HTTP endpoint to send messages to')
    parser.add_argument('--websocket-url', 
                       help='WebSocket URL to send messages to')
    parser.add_argument('--output-file', 
                       help='File to write messages to')
    parser.add_argument('--no-console', action='store_true',
                       help='Disable console output')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    
    # Configuration
    config = {
        'http_endpoint': args.http_endpoint,
        'websocket_url': args.websocket_url,
        'output_file': args.output_file,
        'console_output': not args.no_console
    }
    
    # Start monitor
    monitor = ClaudeMonitor(args.claude_dir, config)
    
    try:
        monitor.start()
    except Exception as e:
        logging.error(f"Failed to start monitor: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())

