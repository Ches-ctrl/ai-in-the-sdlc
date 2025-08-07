"""Simple commit summarizer agent using Claude SDK."""

import os
from typing import Dict, Any, List
from datetime import datetime
import anthropic
from dotenv import load_dotenv

from .agent_base import AgentBase

load_dotenv()


class CommitSummarizerAgent(AgentBase):
    """Simple agent that summarizes recent commits using Claude."""
    
    def __init__(self, mongo_client, verbose: bool = False):
        """Initialize the commit summarizer agent.
        
        Args:
            mongo_client: MongoDB client service instance
            verbose: Enable verbose logging
        """
        super().__init__(name="CommitSummarizer", verbose=verbose)
        self.mongo_client = mongo_client
        
        # Try to get Anthropic API key, fall back to OpenAI key if not available
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your_openai_api_key_here":
            # Use a mock response if no valid API key
            self.anthropic_client = None
            self._log("No valid API key found, will use mock response", "warning")
        else:
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
    
    async def execute(self, limit: int = 10) -> Dict[str, Any]:
        """Execute the commit summarization.
        
        Args:
            limit: Number of recent commits to summarize
            
        Returns:
            Dictionary containing the summary
        """
        try:
            self._log(f"Fetching {limit} recent commits from database")
            
            # Get recent commits from MongoDB
            recent_commits = self.mongo_client.get_recent_commits(limit=limit)
            
            if not recent_commits:
                return {
                    "summary": "No commits found in the database.",
                    "commit_count": 0
                }
            
            self._log(f"Found {len(recent_commits)} commits to summarize")
            
            # Format commits for Claude
            commits_text = self._format_commits_for_prompt(recent_commits)
            
            # Generate summary using Claude or mock
            if self.anthropic_client:
                summary = await self._generate_claude_summary(commits_text, len(recent_commits))
            else:
                summary = self._generate_mock_summary(recent_commits)
            
            return {
                "summary": summary,
                "commit_count": len(recent_commits),
                "time_range": self._get_time_range(recent_commits)
            }
            
        except Exception as e:
            self._log(f"Error during summarization: {str(e)}", "error")
            raise
    
    def _format_commits_for_prompt(self, commits: List[Dict[str, Any]]) -> str:
        """Format commits into a text prompt for Claude.
        
        Args:
            commits: List of commit dictionaries
            
        Returns:
            Formatted text string
        """
        lines = []
        for i, commit in enumerate(commits, 1):
            lines.append(f"Commit {i}:")
            lines.append(f"  Hash: {commit.get('commit_hash', 'N/A')[:8] if commit.get('commit_hash') else 'N/A'}")
            lines.append(f"  Author: {commit.get('author', 'Unknown')}")
            lines.append(f"  Date: {commit.get('timestamp', 'Unknown')}")
            lines.append(f"  Message: {commit.get('message', 'No message')}")
            
            files = commit.get('files_changed', [])
            if files:
                lines.append(f"  Files: {', '.join(files)}")
            
            prompt = commit.get('prompt', '')
            if prompt:
                lines.append(f"  Original Request: {prompt[:100]}...")
            
            lines.append("")
        
        return "\n".join(lines)
    
    async def _generate_claude_summary(self, commits_text: str, count: int) -> str:
        """Generate summary using Claude API.
        
        Args:
            commits_text: Formatted commits text
            count: Number of commits
            
        Returns:
            Summary text
        """
        try:
            prompt = f"""Please provide a concise summary of these {count} recent git commits.

{commits_text}

Provide:
1. A brief overview of what was accomplished
2. Key patterns or themes you notice
3. Types of files/components that were modified
4. Any potential concerns or observations

Keep the summary concise but informative (3-5 paragraphs)."""

            message = self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            self._log(f"Error calling Claude API: {str(e)}", "error")
            # Fall back to mock summary
            return self._generate_mock_summary([])
    
    def _generate_mock_summary(self, commits: List[Dict[str, Any]]) -> str:
        """Generate a mock summary when API is not available.
        
        Args:
            commits: List of commits
            
        Returns:
            Mock summary text
        """
        if not commits:
            commits = self.mongo_client.get_recent_commits(limit=10)
        
        # Analyze the commits
        total = len(commits)
        authors = set(c.get('author', 'Unknown') for c in commits)
        all_files = []
        for c in commits:
            all_files.extend(c.get('files_changed', []))
        
        unique_files = set(all_files)
        
        # Count file types
        file_types = {}
        for f in all_files:
            ext = f.split('.')[-1] if '.' in f else 'no_extension'
            file_types[ext] = file_types.get(ext, 0) + 1
        
        # Build summary
        summary_parts = [
            f"## Summary of {total} Recent Commits\n",
            f"**Overview:** The repository has seen {total} commits from {len(authors)} author(s). ",
            f"These commits primarily focused on {', '.join(list(unique_files)[:3])} and other files.\n",
            "\n**Key Patterns:**",
            f"- Most changes were made to {max(file_types.items(), key=lambda x: x[1])[0] if file_types else 'various'} files",
            f"- {all_files.count('README.md')} commits modified documentation (README.md)" if 'README.md' in all_files else "",
            f"- {all_files.count('app.py')} commits modified the main application file" if 'app.py' in all_files else "",
            "\n\n**Recent Activity:**"
        ]
        
        # Add recent commit messages
        for commit in commits[:3]:
            msg = commit.get('message', 'No message')
            if len(msg) > 80:
                msg = msg[:77] + "..."
            summary_parts.append(f"- {msg}")
        
        summary_parts.append(f"\n**Note:** This is a simplified summary. Configure ANTHROPIC_API_KEY for AI-powered analysis.")
        
        return "\n".join(filter(None, summary_parts))
    
    def _get_time_range(self, commits: List[Dict[str, Any]]) -> Dict[str, str]:
        """Get the time range of commits.
        
        Args:
            commits: List of commits
            
        Returns:
            Dictionary with earliest and latest timestamps
        """
        if not commits:
            return {"earliest": "N/A", "latest": "N/A"}
        
        timestamps = [c.get('timestamp') for c in commits if c.get('timestamp')]
        if not timestamps:
            return {"earliest": "N/A", "latest": "N/A"}
        
        return {
            "earliest": str(min(timestamps)),
            "latest": str(max(timestamps))
        }