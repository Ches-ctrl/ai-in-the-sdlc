"""Git operations for repository cloning and branch management."""

import os
import shutil
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse

from git import Repo, GitCommandError, InvalidGitRepositoryError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn


console = Console()


class GitError(Exception):
    """Custom exception for git operations."""
    pass


class GitCloner:
    """Handles git repository cloning and branch operations."""
    
    def __init__(self, verbose: bool = False):
        """Initialize GitCloner.
        
        Args:
            verbose: Enable verbose output
        """
        self.verbose = verbose
        
    def validate_url(self, repo_url: str) -> bool:
        """Validate repository URL format.
        
        Args:
            repo_url: Repository URL to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check for SSH format
        if repo_url.startswith("git@"):
            parts = repo_url.split(":")
            if len(parts) != 2:
                return False
            return parts[1].endswith(".git") or "/" in parts[1]
        
        # Check for HTTPS format
        parsed = urlparse(repo_url)
        if parsed.scheme not in ["http", "https"]:
            return False
        
        # Must have a valid host and path
        return bool(parsed.netloc and parsed.path)
    
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
    
    def clone_repository(
        self,
        repo_url: str,
        target_dir: Path,
        branch: Optional[str] = None,
        depth: Optional[int] = None
    ) -> Repo:
        """Clone a git repository to the specified directory.
        
        Args:
            repo_url: URL of the repository to clone
            target_dir: Target directory for the clone
            branch: Branch to checkout after cloning
            depth: Create a shallow clone with specified depth
            
        Returns:
            GitPython Repo object
            
        Raises:
            GitError: If cloning fails
        """
        # Validate URL
        if not self.validate_url(repo_url):
            raise GitError(
                f"Invalid repository URL format: {repo_url}\n"
                f"Expected format: https://github.com/user/repo.git or git@github.com:user/repo.git"
            )
        
        # Check if target directory exists
        if target_dir.exists():
            if target_dir.is_dir() and any(target_dir.iterdir()):
                raise GitError(
                    f"Target directory already exists and is not empty: {target_dir}\n"
                    f"Please choose a different directory or remove the existing one."
                )
        
        # Create parent directories if needed
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        
        self._log(f"Validating repository URL: {repo_url}")
        self._log(f"Target directory: {target_dir}")
        
        try:
            # Clone with progress if not verbose (verbose shows git output)
            if self.verbose:
                console.print(f"[green]Cloning repository...[/green]")
                kwargs = {"progress": None}
            else:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task("Cloning repository...", total=None)
                    kwargs = {"progress": lambda op_code, cur_count, max_count, message: 
                             progress.update(task, description=f"Cloning: {message or '...'}")}
            
            # Add depth parameter if specified
            if depth:
                kwargs["depth"] = depth
                self._log(f"Using shallow clone with depth: {depth}")
            
            # Perform the clone
            repo = Repo.clone_from(repo_url, target_dir, **kwargs)
            
            console.print(f"[green]✓ Repository cloned successfully[/green]")
            self._log(f"Clone completed: {len(list(repo.iter_commits()))} commits")
            
            # Checkout branch if specified
            if branch:
                self.checkout_branch(repo, branch)
            
            return repo
            
        except GitCommandError as e:
            # Clean up partial clone if it exists
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            
            # Parse common error scenarios
            error_msg = str(e)
            if "Repository not found" in error_msg or "does not exist" in error_msg:
                raise GitError(
                    f"Repository not found: {repo_url}\n"
                    f"Please check the URL and ensure you have access to the repository."
                )
            elif "Authentication failed" in error_msg or "Permission denied" in error_msg:
                raise GitError(
                    f"Authentication failed for repository: {repo_url}\n"
                    f"For private repositories:\n"
                    f"  - Use SSH URL with configured SSH keys\n"
                    f"  - Or provide authentication token for HTTPS"
                )
            elif "Connection" in error_msg or "timeout" in error_msg:
                raise GitError(
                    f"Failed to connect to repository: {repo_url}\n"
                    f"Please check your internet connection and try again."
                )
            else:
                raise GitError(f"Failed to clone repository: {error_msg}")
        except Exception as e:
            # Clean up on any error
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            raise GitError(f"Unexpected error during clone: {str(e)}")
    
    def checkout_branch(self, repo: Repo, branch_name: str) -> None:
        """Checkout a specific branch in the repository.
        
        Args:
            repo: GitPython Repo object
            branch_name: Name of the branch to checkout
            
        Raises:
            GitError: If branch doesn't exist or checkout fails
        """
        self._log(f"Checking out branch: {branch_name}")
        
        try:
            # Fetch all remote branches first
            repo.remotes.origin.fetch()
            
            # Get list of all branches (local and remote)
            remote_branches = [ref.name for ref in repo.remotes.origin.refs]
            local_branches = [branch.name for branch in repo.branches]
            
            # Check if branch exists
            remote_branch_name = f"origin/{branch_name}"
            
            if branch_name in local_branches:
                # Branch exists locally
                repo.git.checkout(branch_name)
                console.print(f"[green]✓ Checked out branch: {branch_name}[/green]")
            elif remote_branch_name in remote_branches:
                # Branch exists remotely, create local tracking branch
                repo.git.checkout("-b", branch_name, remote_branch_name)
                console.print(f"[green]✓ Checked out branch: {branch_name}[/green]")
            else:
                # Branch doesn't exist
                available_branches = self.list_branches(repo)
                raise GitError(
                    f"Branch '{branch_name}' not found\n\n"
                    f"Available branches:\n" + 
                    "\n".join(f"  - {b}" for b in available_branches[:10]) +
                    (f"\n  ... and {len(available_branches) - 10} more" if len(available_branches) > 10 else "") +
                    f"\n\nTip: Use one of the available branches or check the branch name"
                )
                
        except GitCommandError as e:
            if "did not match any file(s) known to git" in str(e):
                available_branches = self.list_branches(repo)
                raise GitError(
                    f"Branch '{branch_name}' not found\n\n"
                    f"Available branches:\n" + 
                    "\n".join(f"  - {b}" for b in available_branches)
                )
            else:
                raise GitError(f"Failed to checkout branch: {str(e)}")
    
    def list_branches(self, repo: Repo) -> List[str]:
        """List all available branches in the repository.
        
        Args:
            repo: GitPython Repo object
            
        Returns:
            List of branch names
        """
        branches = []
        
        # Add local branches
        for branch in repo.branches:
            branches.append(branch.name)
        
        # Add remote branches (without 'origin/' prefix)
        for ref in repo.remotes.origin.refs:
            branch_name = ref.name.replace("origin/", "")
            if branch_name not in branches and branch_name != "HEAD":
                branches.append(branch_name)
        
        return sorted(branches)
    
    def get_repo_info(self, repo: Repo) -> dict:
        """Get information about the cloned repository.
        
        Args:
            repo: GitPython Repo object
            
        Returns:
            Dictionary with repository information
        """
        try:
            current_branch = repo.active_branch.name
        except TypeError:
            # Detached HEAD state
            current_branch = f"(detached HEAD at {repo.head.commit.hexsha[:7]})"
        
        commit_count = len(list(repo.iter_commits()))
        
        return {
            "url": repo.remotes.origin.url if repo.remotes else "Unknown",
            "branch": current_branch,
            "location": repo.working_dir,
            "commits": commit_count,
        }
    
    def get_commit_history(self, repo_path: Path, initial_commit: str, final_commit: str) -> List[dict]:
        """Get commit history between two commits.
        
        Args:
            repo_path: Path to the git repository
            initial_commit: Starting commit SHA (older commit)
            final_commit: Ending commit SHA (newer commit)
            
        Returns:
            List of commit information dictionaries
            
        Raises:
            GitError: If repository is invalid or commits don't exist
        """
        # Validate repository path
        if not repo_path.exists():
            raise GitError(f"Repository path does not exist: {repo_path}")
        
        try:
            repo = Repo(repo_path)
        except InvalidGitRepositoryError:
            raise GitError(f"Not a valid git repository: {repo_path}")
        
        # Validate commits exist
        try:
            initial = repo.commit(initial_commit)
            self._log(f"Initial commit found: {initial.hexsha[:8]} - {initial.summary}")
        except Exception:
            raise GitError(f"Initial commit not found: {initial_commit}")
        
        try:
            final = repo.commit(final_commit)
            self._log(f"Final commit found: {final.hexsha[:8]} - {final.summary}")
        except Exception:
            raise GitError(f"Final commit not found: {final_commit}")
        
        # Check if initial is ancestor of final
        if not repo.is_ancestor(initial, final):
            raise GitError(
                f"Initial commit {initial_commit[:8]} is not an ancestor of final commit {final_commit[:8]}\n"
                f"The initial commit must come before the final commit in the history."
            )
        
        # Get commits in range (initial..final]
        # This excludes initial and includes final
        try:
            commit_range = f"{initial_commit}..{final_commit}"
            commits = list(repo.iter_commits(commit_range))
            
            # If we want to include the initial commit, use initial^..final
            # But we'll stick with excluding initial for now as it's more standard
            
            self._log(f"Found {len(commits)} commits in range {initial_commit[:8]}..{final_commit[:8]}")
            
            # Build commit information
            commit_list = []
            for commit in reversed(commits):  # Show oldest first
                commit_info = {
                    "sha": commit.hexsha,
                    "short_sha": commit.hexsha[:8],
                    "author": str(commit.author) if hasattr(commit, 'author') else "Unknown",
                    "author_email": commit.author.email if hasattr(commit, 'author') else "unknown@example.com",
                    "date": commit.committed_datetime.isoformat(),
                    "message": commit.message.strip(),
                    "summary": commit.summary,
                    "files_changed": len(commit.stats.files) if hasattr(commit, 'stats') else 0,
                    "insertions": commit.stats.total["insertions"] if hasattr(commit, 'stats') else 0,
                    "deletions": commit.stats.total["deletions"] if hasattr(commit, 'stats') else 0,
                }
                commit_list.append(commit_info)
            
            return commit_list
            
        except GitCommandError as e:
            raise GitError(f"Failed to get commit history: {str(e)}")
        except Exception as e:
            raise GitError(f"Unexpected error getting commit history: {str(e)}")