"""Prompt builder for Claude agent git operations."""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime


class PromptBuilder:
    """Builds structured prompts for Claude agent."""
    
    # Base template for git history rewriting
    REWRITE_TEMPLATE = """You are in a git repository at: {repo_path}

## Current Git Status
The repository has been prepared for history rewriting. You have full access to git commands.

## Commit Range to Rewrite
Initial commit (start): {initial_commit}
Final commit (end): {final_commit}

## Commit History
{commit_history}

## User Instructions
{user_instructions}

## Git Rewriting Guidelines

1. **Safety First**:
   - Create a backup branch before any destructive operations: `git branch backup-{timestamp}`
   - Verify current branch and status with `git status` before starting
   - Use `git reflog` if you need to recover from mistakes

2. **Common Git Commands for History Rewriting**:
   - `git rebase -i <commit>^` - Interactive rebase from a commit
   - `git commit --amend` - Modify the last commit
   - `git reset --soft <commit>` - Move HEAD but keep changes staged
   - `git reset --mixed <commit>` - Move HEAD and unstage changes
   - `git cherry-pick <commit>` - Apply specific commits
   - `git revert <commit>` - Create a new commit that undoes changes

3. **Interactive Rebase Commands**:
   - `pick` - Keep commit as is
   - `reword` - Keep commit but edit message
   - `edit` - Stop for amending
   - `squash` - Combine with previous commit
   - `fixup` - Like squash but discard this commit's message
   - `drop` - Remove commit

4. **Verification**:
   - After rewriting, verify with: `git log --oneline -n 20`
   - Check file changes with: `git diff <initial_commit>..HEAD`
   - Ensure the working tree is clean: `git status`

5. **Best Practices**:
   - Group related commits logically
   - Write clear, descriptive commit messages
   - Follow conventional commit format if detected
   - Preserve authorship unless instructed otherwise
   - Keep commits atomic (one logical change per commit)

## Your Task
Execute the git operations needed to rewrite the history according to the user's instructions.
Start by creating a backup branch, then proceed with the rewriting operations.
"""
    
    def __init__(self, verbose: bool = False):
        """Initialize the prompt builder.
        
        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose
    
    def build_rewrite_prompt(
        self,
        repo_path: Path,
        initial_commit: str,
        final_commit: str,
        user_instructions: str,
        commit_history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Build a complete prompt for history rewriting.
        
        Args:
            repo_path: Path to the repository
            initial_commit: Starting commit SHA
            final_commit: Ending commit SHA
            user_instructions: User's instructions for rewriting
            commit_history: Optional list of commits in the range
            
        Returns:
            Complete prompt for Claude agent
        """
        # Format commit history if provided
        if commit_history:
            history_text = self._format_commit_history(commit_history)
        else:
            history_text = "Run `git log --oneline {}..{}` to see the commits.".format(
                initial_commit, final_commit
            )
        
        # Generate timestamp for backup branch
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # Build the prompt
        prompt = self.REWRITE_TEMPLATE.format(
            repo_path=repo_path,
            initial_commit=initial_commit,
            final_commit=final_commit,
            commit_history=history_text,
            user_instructions=user_instructions,
            timestamp=timestamp
        )
        
        return prompt
    
    def build_analyze_prompt(
        self,
        repo_path: Path,
        initial_commit: str,
        final_commit: str
    ) -> str:
        """Build a prompt for analyzing commits.
        
        Args:
            repo_path: Path to the repository
            initial_commit: Starting commit SHA
            final_commit: Ending commit SHA
            
        Returns:
            Prompt for commit analysis
        """
        return f"""Analyze the git repository at: {repo_path}

Please examine the commits between {initial_commit} and {final_commit}.

Use these commands:
1. `git log --oneline {initial_commit}..{final_commit}` - List commits
2. `git log --stat {initial_commit}..{final_commit}` - Show commit statistics
3. `git diff {initial_commit}..{final_commit} --stat` - Overall changes

Provide:
1. Total number of commits
2. Summary of changes (files modified, lines added/removed)
3. Patterns in commit messages (WIP, fixes, features, etc.)
4. Suggestions for improving the commit history
"""
    
    def build_verify_prompt(
        self,
        repo_path: Path,
        expected_state: str
    ) -> str:
        """Build a prompt for verifying rewrite results.
        
        Args:
            repo_path: Path to the repository
            expected_state: Expected final state description
            
        Returns:
            Prompt for verification
        """
        return f"""Verify the git rewrite results at: {repo_path}

Expected state: {expected_state}

Please verify:
1. Check current branch: `git branch --show-current`
2. Show recent commits: `git log --oneline -n 10`
3. Check working tree status: `git status`
4. Verify no uncommitted changes: `git diff`

Report whether the rewrite was successful and matches expectations.
"""
    
    def _format_commit_history(self, commits: List[Dict[str, Any]]) -> str:
        """Format commit history for inclusion in prompt.
        
        Args:
            commits: List of commit dictionaries
            
        Returns:
            Formatted commit history text
        """
        if not commits:
            return "No commits found in the specified range."
        
        lines = [f"Found {len(commits)} commits in the range:\n"]
        
        for commit in commits:
            # Format each commit
            sha = commit.get("short_sha", commit.get("sha", "unknown")[:8])
            author = commit.get("author", "Unknown")
            message = commit.get("summary", commit.get("message", "No message"))
            
            # Add file statistics if available
            files_changed = commit.get("files_changed", 0)
            insertions = commit.get("insertions", 0)
            deletions = commit.get("deletions", 0)
            
            line = f"- {sha} - {message} ({author})"
            if files_changed:
                line += f" [{files_changed} files, +{insertions}, -{deletions}]"
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def build_custom_prompt(self, template: str, **kwargs) -> str:
        """Build a prompt from a custom template.
        
        Args:
            template: Custom prompt template with {placeholders}
            **kwargs: Values to substitute in the template
            
        Returns:
            Formatted prompt
        """
        return template.format(**kwargs)