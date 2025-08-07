"""Load and parse conversation history from JSONL files."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from rich.console import Console

console = Console()


class ConversationLoader:
    """Load conversation history from JSONL files for additional context."""
    
    def __init__(self, verbose: bool = False):
        """Initialize ConversationLoader.
        
        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose
    
    def load_jsonl(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load conversation from JSONL file.
        
        Args:
            file_path: Path to JSONL file
            
        Returns:
            List of conversation entries
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Conversation file not found: {file_path}")
        
        conversations = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    entry = json.loads(line)
                    conversations.append(entry)
                    
                    if self.verbose:
                        console.print(f"[blue]Loaded entry {line_num}: {entry.get('type', 'unknown')}[/blue]")
                        
                except json.JSONDecodeError as e:
                    console.print(f"[yellow]Warning: Skipping invalid JSON at line {line_num}: {e}[/yellow]")
                    continue
        
        if self.verbose:
            console.print(f"[green]Loaded {len(conversations)} conversation entries[/green]")
        
        return conversations
    
    def format_for_prompt(self, conversations: List[Dict[str, Any]]) -> str:
        """Format conversation history for inclusion in AI prompt.
        
        Args:
            conversations: List of conversation entries
            
        Returns:
            Formatted string for prompt context
        """
        if not conversations:
            return ""
        
        formatted_parts = ["## Previous Conversation Context\n"]
        
        for entry in conversations:
            msg_type = entry.get("type", "unknown")
            content = entry.get("content", "")
            
            if msg_type == "human":
                formatted_parts.append(f"User: {content}\n")
            elif msg_type == "assistant":
                formatted_parts.append(f"Assistant: {content}\n")
            elif msg_type == "system":
                formatted_parts.append(f"System: {content}\n")
            else:
                formatted_parts.append(f"{msg_type}: {content}\n")
        
        return "\n".join(formatted_parts)
    
    def extract_relevant_context(
        self, 
        conversations: List[Dict[str, Any]], 
        keywords: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Extract relevant conversation entries based on keywords.
        
        Args:
            conversations: Full conversation history
            keywords: Optional keywords to filter by
            
        Returns:
            Filtered conversation entries
        """
        if not keywords:
            return conversations
        
        relevant = []
        keywords_lower = [k.lower() for k in keywords]
        
        for entry in conversations:
            content = entry.get("content", "").lower()
            if any(keyword in content for keyword in keywords_lower):
                relevant.append(entry)
        
        if self.verbose:
            console.print(f"[blue]Filtered to {len(relevant)} relevant entries from {len(conversations)} total[/blue]")
        
        return relevant