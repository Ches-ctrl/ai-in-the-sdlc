from typing import List
from pydantic import BaseModel
from git_examine import run_git_command


class CommitMessage(BaseModel):
    message: List[str]
    files: List[str]


def git_add_files(files: List[str], repo_path: str) -> None:
    """
    Add specific files to git staging area.
    
    Args:
        files: List of file paths to add
        repo_path: Path to the git repository
    """
    for file in files:
        run_git_command(['add', file], repo_path)


def git_commit_message(message: List[str], repo_path: str) -> str:
    """
    Create a git commit with the specified message.
    
    Args:
        message: List of message strings to join
        repo_path: Path to the git repository
        
    Returns:
        str: The output from the git commit command
    """
    commit_msg = ' '.join(message)
    return run_git_command(['commit', '-m', commit_msg], repo_path)


def execute_commits(commit_messages: List[CommitMessage], repo_path: str) -> List[str]:
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
        git_add_files(commit_msg.files, repo_path)
        
        # Commit with message
        result = git_commit_message(commit_msg.message, repo_path)
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
        results = execute_commits(commit_messages, repo_path)
        print("Commit results:")
        for i, result in enumerate(results):
            print(f"Commit {i+1}: {result}")
    except Exception as e:
        print(f"Error executing commits: {e}")