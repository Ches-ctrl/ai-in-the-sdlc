from typing import List
from pydantic import BaseModel
from src.git_examine import run_git_command
from fastapi import WebSocket
import asyncio
import re

class CommitMessage(BaseModel):
    message: List[str]
    files: List[str]


async def get_repository_url(websocket: WebSocket) -> str:
    """
    Get the remote repository URL.
    
    Args:
        websocket: WebSocket connection for command execution
        
    Returns:
        str: The repository URL (HTTP/HTTPS format)
    """
    try:
        # Get the remote URL
        remote_url = await run_git_command(['config', '--get', 'remote.origin.url'], websocket)
        if remote_url:
            remote_url = remote_url.strip()
            
            # Convert SSH URL to HTTPS if needed
            if remote_url.startswith('git@'):
                # Convert git@github.com:user/repo.git to https://github.com/user/repo
                remote_url = remote_url.replace('git@', 'https://').replace(':', '/')
                if remote_url.endswith('.git'):
                    remote_url = remote_url[:-4]
            
            return remote_url
        
        return None
    except Exception as e:
        print(f"Error getting repository URL: {e}")
        return None


async def get_commit_hash_by_ref(ref: str, websocket: WebSocket) -> str:
    """
    Get the full commit hash for a given reference (HEAD, branch name, etc.).
    
    Args:
        ref: Git reference (e.g., 'HEAD', 'main', commit hash)
        websocket: WebSocket connection for command execution
        
    Returns:
        str: The full commit hash
    """
    try:
        commit_hash = await run_git_command(['rev-parse', ref], websocket)
        return commit_hash.strip() if commit_hash else None
    except Exception as e:
        print(f"Error getting commit hash for {ref}: {e}")
        return None


async def git_add_files(files: List[str], websocket: WebSocket) -> None:
    """
    Add specific files to git staging area.
    
    Args:
        files: List of file paths to add
        repo_path: Path to the git repository
    """
    for file in files:
        await run_git_command(['add', file], websocket)


async def git_commit_message(commit_msg: str, websocket: WebSocket) -> dict:
    """
    Create a git commit with the specified message.
    
    Args:
        message: List of message strings to join
        repo_path: Path to the git repository
        
    Returns:
        dict: Contains commit_hash, commit_output, and repository_url
    """
    # Execute the commit
    commit_output = await run_git_command(['commit', '-m', f'"{commit_msg}"'], websocket)
    
    # Extract commit hash from output (format: "[branch commit_hash] message")
    commit_hash = None
    print(f"Commit output: {commit_output}")
    hash_match = re.search(r'\[.*?([a-f0-9]{7,40})\]', commit_output)
    if hash_match:
        commit_hash = hash_match.group(1)
    
    # Get the full commit hash if we only got a short one
    if commit_hash and len(commit_hash) < 40:
        full_hash_output = await run_git_command(['rev-parse', commit_hash], websocket)
        if full_hash_output.strip():
            commit_hash = full_hash_output.strip()
    
    # Get repository URL
    repo_url = await get_repository_url(websocket)
    
    return {
        "commit_hash": commit_hash,
        "commit_output": commit_output,
        "repository_url": repo_url,
        "commit_url": f"{repo_url}/commit/{commit_hash}" if repo_url and commit_hash else None
    }


async def execute_commits(commit_messages: List[CommitMessage], websocket: WebSocket) -> List[dict]:
    """
    Execute multiple commits in sequence.
    
    Args:
        commit_messages: List of CommitMessage objects to process
        repo_path: Path to the git repository
        
    Returns:
        List[dict]: List of commit results with hash, output, and URLs
    """
    results = []
    
    for commit_msg in commit_messages:
        # Add files
        await git_add_files(commit_msg.files, websocket)
        
        # Commit with message
        result = await git_commit_message(commit_msg.message, websocket)
        results.append(result)
    
    return results


# Example usage
if __name__ == "__main__":
    # Test with provided example
    commit_messages = [
        CommitMessage(
            message='Add Hi.txt and bla.txt text files with initial greetings', 
            files=['Hi.txt', 'bla.txt']
        ),
        CommitMessage(
            message='Create a FastAPI application in app.py with a root endpoint', 
            files=['app.py']
        )
    ]
    
    repo_path = "test_git"
    
    try:
        results = asyncio.run(execute_commits(commit_messages, repo_path))
        print("Commit results:")
        for i, result in enumerate(results):
            print(f"Commit {i+1}:")
            print(f"  Hash: {result['commit_hash']}")
            print(f"  URL: {result['commit_url']}")
            print(f"  Output: {result['commit_output']}")
    except Exception as e:
        print(f"Error executing commits: {e}")