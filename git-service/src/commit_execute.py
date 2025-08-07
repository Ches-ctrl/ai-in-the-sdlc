from typing import List
from pydantic import BaseModel
from git_examine import run_git_command
from fastapi import WebSocket
import asyncio

class CommitMessage(BaseModel):
    message: List[str]
    files: List[str]


async def git_add_files(files: List[str], websocket: WebSocket) -> None:
    """
    Add specific files to git staging area.
    
    Args:
        files: List of file paths to add
        repo_path: Path to the git repository
    """
    for file in files:
        await run_git_command(['add', file], websocket)


async def git_commit_message(message: List[str], websocket: WebSocket) -> str:
    """
    Create a git commit with the specified message.
    
    Args:
        message: List of message strings to join
        repo_path: Path to the git repository
        
    Returns:
        str: The output from the git commit command
    """
    commit_msg = ' '.join(message)
    return await run_git_command(['commit', '-m', commit_msg], websocket)


async def execute_commits(commit_messages: List[CommitMessage], websocket: WebSocket) -> List[str]:
    """
    Execute multiple commits in sequence.
    
    Args:
        commit_messages: List of CommitMessage objects to process
        repo_path: Path to the git repository
        
    Returns:
        List[str]: List of commit outputs
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
            message=['Add Hi.txt and bla.txt text files with initial greetings'], 
            files=['Hi.txt', 'bla.txt']
        ),
        CommitMessage(
            message=['Create a FastAPI application in app.py with a root endpoint'], 
            files=['app.py']
        )
    ]
    
    repo_path = "test_git"
    
    try:
        results = asyncio.run(execute_commits(commit_messages, repo_path))
        print("Commit results:")
        for i, result in enumerate(results):
            print(f"Commit {i+1}: {result}")
    except Exception as e:
        print(f"Error executing commits: {e}")