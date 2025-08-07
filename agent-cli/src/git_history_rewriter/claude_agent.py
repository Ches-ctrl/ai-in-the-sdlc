"""Claude SDK integration for git history rewriting."""

import json
import re
from pathlib import Path
from typing import AsyncIterator, Optional, List, Dict, Any, TYPE_CHECKING
import anyio
from rich.console import Console

from claude_code_sdk import query, ClaudeCodeOptions, Message
from claude_code_sdk.types import (
    AssistantMessage, 
    TextBlock, 
    ToolUseBlock,
    ToolResultBlock,
    ResultMessage
)

from .git import GitError

if TYPE_CHECKING:
    from .plan_schema import RewritePlan


console = Console()


class ClaudeHistoryRewriter:
    """Manages Claude SDK agent for git history rewriting."""
    
    def __init__(self, verbose: bool = False):
        """Initialize the Claude history rewriter.
        
        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose
    
    def _log(self, message: str, level: str = "info"):
        """Log message if verbose mode is enabled.
        
        Args:
            message: Message to log
            level: Log level (info, warning, error)
        """
        if self.verbose:
            if level == "error":
                console.print(f"[red]✗ {message}[/red]")
            elif level == "warning":
                console.print(f"[yellow]⚠ {message}[/yellow]")
            else:
                console.print(f"[blue]ℹ {message}[/blue]")
    
    async def rewrite_history(
        self,
        prompt: str,
        working_dir: Path,
        permission_mode: str = "acceptEdits",
        model: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Execute git history rewriting using Claude SDK.
        
        Args:
            prompt: Complete prompt with instructions for Claude
            working_dir: Repository directory to work in
            permission_mode: Permission mode for tools ('default', 'acceptEdits', 'bypassPermissions')
            model: Claude model to use (optional)
            dry_run: If True, show what would be done without executing
            
        Returns:
            Dictionary with rewrite results
            
        Raises:
            GitError: If rewriting fails
        """
        try:
            # Configure Claude SDK options
            options = ClaudeCodeOptions(
                cwd=str(working_dir),
                permission_mode=permission_mode,  # type: ignore
                allowed_tools=["Read", "Write", "Bash", "Grep", "LS"],
                system_prompt="You are an expert git user helping to rewrite repository history. "
                             "Always verify operations with git status and git log. "
                             "Create backup branches before destructive operations.",
                max_turns=10  # Allow multiple turns for complex operations
            )
            
            if model:
                options.model = model
            
            if dry_run:
                # In dry-run mode, add instructions to only show what would be done
                prompt = f"""DRY RUN MODE - DO NOT EXECUTE CHANGES

{prompt}

Instead of executing git operations, please:
1. Analyze the current git history
2. Explain what changes would be made
3. Show the git commands that would be executed
4. DO NOT actually run any git rebase, reset, or other modifying commands
"""
            
            self._log(f"Starting Claude agent in {working_dir}")
            self._log(f"Permission mode: {permission_mode}")
            
            # Track messages for result building
            messages_received = []
            tool_uses = []
            errors = []
            
            # Execute query with Claude SDK
            async for message in query(prompt=prompt, options=options):
                messages_received.append(message)
                
                if isinstance(message, AssistantMessage):
                    # Process assistant response
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if self.verbose:
                                console.print(f"[dim]Claude:[/dim] {block.text}")
                        elif isinstance(block, ToolUseBlock):
                            tool_uses.append({
                                "tool": block.name,
                                "input": block.input
                            })
                            self._log(f"Using tool: {block.name}")
                        elif isinstance(block, ToolResultBlock):
                            if block.is_error:
                                errors.append(block.content)
                                self._log(f"Tool error: {block.content}", "error")
                
                elif isinstance(message, ResultMessage):
                    # Process final result
                    result = {
                        "success": not message.is_error,
                        "duration_ms": message.duration_ms,
                        "num_turns": message.num_turns,
                        "total_cost_usd": message.total_cost_usd,
                        "tool_uses": tool_uses,
                        "errors": errors,
                        "dry_run": dry_run
                    }
                    
                    if message.is_error:
                        self._log(f"Rewrite failed: {message.result}", "error")
                    else:
                        self._log("Rewrite completed successfully")
                    
                    return result
            
            # If we get here without a ResultMessage, something went wrong
            raise GitError("Claude agent terminated without providing a result")
            
        except Exception as e:
            self._log(f"Unexpected error during rewrite: {str(e)}", "error")
            raise GitError(f"Failed to rewrite history: {str(e)}")
    
    async def generate_plan(
        self,
        prompt: str,
        working_dir: Path,
        commits: List[Dict[str, Any]],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a rewrite plan using Claude.
        
        Args:
            prompt: Complete prompt with instructions for Claude
            working_dir: Repository directory to work in
            commits: List of commits in the range
            model: Claude model to use (optional)
            
        Returns:
            Dictionary with plan operations and commands
        """
        try:
            # Create a prompt asking for structured output
            plan_prompt = f"""{prompt}

IMPORTANT: Instead of executing git commands, generate a structured plan in JSON format with:
1. A list of operations (squash, reword, drop, reorder)
2. The git commands that would be executed

Return your plan in this format:
{{
    "operations": [
        {{
            "type": "squash",
            "commits": ["sha1", "sha2"],
            "new_message": "Combined message",
            "description": "Why these are being squashed"
        }},
        {{
            "type": "reword",
            "commit": "sha",
            "old_message": "original",
            "new_message": "improved",
            "reason": "why"
        }}
    ],
    "commands": [
        "git command 1",
        "git command 2"
    ],
    "planned_commit_count": <number>
}}

Current commits in range:
{json.dumps([dict(
    sha=c['sha'][:7],
    message=c['message'],
    author=c['author']
) for c in commits], indent=2)}"""

            # Configure Claude SDK options
            options = ClaudeCodeOptions(
                cwd=str(working_dir),
                permission_mode="default",  # type: ignore
                allowed_tools=["Read", "Bash"],  # Read-only tools for plan generation
                system_prompt="You are an expert git user helping to plan repository history rewrites. "
                             "Generate a structured plan in JSON format. Do not execute any git commands that modify history.",
                max_turns=3
            )
            
            if model:
                options.model = model
            
            self._log(f"Generating plan with Claude in {working_dir}")
            
            # Collect the response
            plan_data = {
                "operations": [],
                "commands": [],
                "planned_commit_count": None
            }
            
            async for message in query(prompt=plan_prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            # Try to extract JSON from the response
                            text = block.text
                            try:
                                # Look for JSON in the response
                                import re
                                json_match = re.search(r'\{[\s\S]*\}', text)
                                if json_match:
                                    extracted_plan = json.loads(json_match.group())
                                    if "operations" in extracted_plan:
                                        plan_data["operations"] = extracted_plan["operations"]
                                    if "commands" in extracted_plan:
                                        plan_data["commands"] = extracted_plan["commands"]
                                    if "planned_commit_count" in extracted_plan:
                                        plan_data["planned_commit_count"] = extracted_plan["planned_commit_count"]
                            except json.JSONDecodeError:
                                # If we can't parse JSON, try to extract information manually
                                self._log("Could not parse JSON from response, using fallback extraction", "warning")
            
            return plan_data
            
        except Exception as e:
            self._log(f"Unexpected error during plan generation: {str(e)}", "error")
            raise GitError(f"Failed to generate plan: {str(e)}")
    
    async def apply_saved_plan(
        self,
        plan: 'RewritePlan',
        repo_path: Path,
        permission_mode: str = "acceptEdits",
        model: Optional[str] = None,
        backup_branch: str = None
    ) -> Dict[str, Any]:
        """Apply a saved rewrite plan using Claude agent.
        
        Args:
            plan: The loaded RewritePlan object
            repo_path: Path to repository
            permission_mode: Permission mode for tool use
            model: Optional Claude model to use
            backup_branch: Name of the backup branch already created
            
        Returns:
            Result dictionary with success status and details
        """
        try:
            working_dir = Path(repo_path).resolve()
            
            # Build prompt with plan details
            prompt = f"""You have a git history rewrite plan to apply. The repository is at {working_dir}.

A backup branch has already been created: {backup_branch}

Here is the plan to execute:

Repository: {plan.metadata.repository}
Commits to rewrite: {plan.metadata.initial_commit}..{plan.metadata.final_commit}
Original prompt: {plan.metadata.prompt}

Operations to perform:
{json.dumps([op.to_dict() for op in plan.operations], indent=2)}

The plan suggests these commands (but you should adapt as needed for interactive rebase):
{chr(10).join(plan.commands)}

Your task:
1. Execute the operations described in the plan
2. Use git rebase -i to rewrite the history
3. For interactive rebase, create a custom editor script or use GIT_SEQUENCE_EDITOR
4. Apply the operations:
   - "squash" operations: combine specified commits
   - "reword" operations: change commit messages
   - "drop" operations: remove commits
   - "reorder" operations: change commit order
5. Verify the rewrite was successful
6. Report what was done

Important:
- The backup branch {backup_branch} has already been created
- You have permission to modify git history
- Use appropriate git commands to implement the plan
- Handle interactive rebase programmatically (don't rely on manual editing)
"""
            
            # Configure Claude SDK options
            options = ClaudeCodeOptions(
                cwd=str(working_dir),
                permission_mode=permission_mode,  # type: ignore
                allowed_tools=["Read", "Write", "Bash"],
                system_prompt="You are an expert git user executing a git history rewrite plan. "
                             "You have permission to modify git history using rebase and other git commands.",
                max_turns=30
            )
            
            if model:
                options.model = model
            
            self._log(f"Applying saved plan in {working_dir}")
            self._log(f"Permission mode: {permission_mode}")
            
            # Track execution details
            messages_received = []
            tool_uses = []
            errors = []
            
            # Execute with Claude SDK
            async for message in query(prompt=prompt, options=options):
                messages_received.append(message)
                
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            if self.verbose:
                                console.print(f"[dim]Claude:[/dim] {block.text}")
                        elif isinstance(block, ToolUseBlock):
                            tool_uses.append({
                                "tool": block.name,
                                "input": block.input
                            })
                            self._log(f"Using tool: {block.name}")
                        elif isinstance(block, ToolResultBlock):
                            if block.is_error:
                                errors.append(block.content)
                                self._log(f"Tool error: {block.content}", "error")
                
                elif isinstance(message, ResultMessage):
                    result = {
                        "success": not message.is_error,
                        "duration_ms": message.duration_ms,
                        "num_turns": message.num_turns,
                        "total_cost_usd": message.total_cost_usd,
                        "tool_uses": tool_uses,
                        "errors": errors
                    }
                    
                    if message.is_error:
                        self._log(f"Plan application failed: {message.result}", "error")
                    else:
                        self._log("Plan applied successfully")
                    
                    return result
            
            # If we get here without a result, something went wrong
            return {
                "success": False,
                "errors": ["No result received from Claude"],
                "tool_uses": tool_uses
            }
            
        except Exception as e:
            self._log(f"Unexpected error during plan application: {str(e)}", "error")
            raise GitError(f"Failed to apply plan: {str(e)}")
    
    async def analyze_commits(
        self,
        repo_path: Path,
        initial_commit: str,
        final_commit: str
    ) -> str:
        """Analyze commits in the specified range.
        
        Args:
            repo_path: Path to repository
            initial_commit: Starting commit SHA
            final_commit: Ending commit SHA
            
        Returns:
            Analysis of the commit range
        """
        prompt = f"""Analyze the git commits between {initial_commit} and {final_commit} in the repository at {repo_path}.

Please provide:
1. Total number of commits in the range
2. Summary of changes made
3. Any patterns you notice (WIP commits, formatting commits, etc.)
4. Suggestions for how the history could be improved

Use git log and git show commands to examine the commits."""
        
        options = ClaudeCodeOptions(
            cwd=str(repo_path),
            permission_mode="default",  # type: ignore
            allowed_tools=["Bash", "Read"],
            max_turns=3
        )
        
        analysis = ""
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        analysis += block.text + "\n"
        
        return analysis.strip()