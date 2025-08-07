import subprocess
import os
from pydantic import BaseModel, Field
import re
from typing import Dict, List, Optional, Tuple, Literal
import openai
from dotenv import load_dotenv

load_dotenv()

client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class Diffs(BaseModel):
    file_path: str
    diff_idx: int

class Feature(BaseModel):
    feature: str
    files: List[Diffs]
    feature_idx: int

class Response(BaseModel):
    features: List[Feature]

def run_git_command(command: List[str], repo_path: str) -> str:
    """
    Run a git command in a specified repository path and return stdout.
    
    Args:
        command: List of git command arguments (e.g., ['status', '--porcelain'])
        repo_path: Path to the git repository
        
    Returns:
        str: The stdout output from the git command
        
    Raises:
        subprocess.CalledProcessError: If the git command fails
        FileNotFoundError: If the repository path doesn't exist
    """
    if not os.path.exists(repo_path):
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
    
    # Construct the full git command
    full_command = ['git'] + command
    
    try:
        print(f"Running command: {' '.join(full_command)} in {repo_path}")
        result = subprocess.run(
            full_command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise subprocess.CalledProcessError(
            e.returncode, 
            e.cmd, 
            f"Git command failed: {e.stderr}"
        )


def git_commit(repo_path: str, message: str, add_all: bool = False) -> str:
    """
    Create a git commit with the specified message.
    
    Args:
        repo_path: Path to the git repository
        message: Commit message
        add_all: Whether to add all changed files before committing
        
    Returns:
        str: The output from the git commit command
    """
    if add_all:
        # Add all changes first
        run_git_command(['add', '.'], repo_path)
    
    # Create the commit
    commit_output = run_git_command(['commit', '-m', message], repo_path)
    return commit_output



def get_untracked_files(repo_path: str) -> List[str]:
    """
    Get a list of untracked files in the repository.
    
    Args:
        repo_path: Path to the git repository
        
    Returns:
        List[str]: List of untracked file paths
    """
    status_output = run_git_command(['status', '--porcelain'], repo_path)
    untracked_files = []
    
    for line in status_output.strip().split('\n'):
        if line.startswith('??'):
            # Remove the '?? ' prefix and get the filename
            filename = line[3:]
            untracked_files.append(filename)
    
    return untracked_files


def examine_untracked_files(repo_path: str) -> Dict[str, Dict[str, str]]:
    """
    Examine untracked files by temporarily adding them, checking the diff, then removing them.
    This allows you to see what the diff would look like for untracked files without permanently adding them.
    
    Args:
        repo_path: Path to the git repository
        
    Returns:
        Dict[str, Dict[str, str]]: Dictionary with file paths as keys and diff info as values
        Format: {
            'file_path': {
                'status': 'added',
                'diff': 'full diff content',
                'additions': '10',
                'deletions': '0'
            }
        }
    """
    untracked_files = get_untracked_files(repo_path)
    all_diffs = {}
    
    if not untracked_files:
        print("No untracked files found.")
        return all_diffs
    
    print(f"Found {len(untracked_files)} untracked files to examine:")
    for file in untracked_files:
        print(f"  - {file}")
    
    for file_path in untracked_files:
        try:
            # git add file_path
            run_git_command(['add', file_path], repo_path)
            # git diff --cached
            output = run_git_command(['diff', '--cached', file_path], repo_path)
            all_diffs[file_path] = output
            # git rm --cached file_path
            run_git_command(['rm', '--cached', file_path], repo_path)
            
        except subprocess.CalledProcessError as e:
            print(f"  Error examining {file_path}: {e}")
            continue
    
    return all_diffs


def analyze_diff(diffs: dict[str, str], features: list[str]) -> str:
    """Examine each diff and assign  to features"""
    SYSTEM_PROMPT = """You are a helpful assistant that analyzes git diffs and assigns features to them.

## Features
{features}

## Diffs
{diff}

You will return a JSON object with the following fields:
- feature: str
- files: List[Diffs]
- feature_idx: int

each diff will have a file_path, diff_file.

    """

    diff_list = "- " + "\n- ".join([f"**file_path:** {file_path}\n**diff_file:** {diff_file}\ndiff_idx: {diff_idx}\n\n" for diff_idx, (file_path, diff_file) in enumerate(diffs.items())])
    features_list = "\n".join([f"**feature:** {feature}\n**feature_idx:** {feature_idx}\n\n" for feature, feature_idx in enumerate(features)])

    SYSTEM_PROMPT = SYSTEM_PROMPT.format(features=features_list, diff=diff_list)
    response = client.beta.chat.completions.parse(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ""}
        ],
        response_format=Response
    )

    return response.choices[0].message.parsed


# You will recieve the following:
# features=[Feature(feature='Writing text files', files=[Diffs(file_path='Hi.txt', diff_idx=0), Diffs(file_path='bla.txt', diff_idx=2)], feature_idx=0), Feature(feature='greating Flask app', files=[Diffs(file_path='app.py', diff_idx=1)], feature_idx=1)]
# Create git commit message based on the features and diffs.

def create_commit_message(response: Response, diffs: Dict[str, str]) -> str:
    """Examine each diff and assign  to features"""
    SYSTEM_PROMPT = """You are a helpful assistant that analyzes diffs and creates a git commit message.

Task: The user will provide a list of features and corresponding diffs. For each feature, you will create a git commit message that describes the feature and the diffs that are associated with it.

Guidelines:
- The commit message should be a single sentence that describes the feature and the diffs that are associated with it.
- The commit message should be in the present tense.
- The commit message should be in the active voice.
- The commit message should be in the present tense.

## Diffs
{diffs_list}
    """
    
    class CommitMessage(BaseModel):
        message: List[str]
        files: List[str]
    
    class CommitMessages(BaseModel):
        commit_messages: List[CommitMessage]

    diff_list = "- " + "\n- ".join([f"**file_path:** {file_path}\n**diff_file:** {diff_file}\ndiff_idx: {diff_idx}\n\n" for diff_idx, (file_path, diff_file) in enumerate(diffs.items())])
    SYSTEM_PROMPT = SYSTEM_PROMPT.format(diffs_list=diff_list)

    response = client.beta.chat.completions.parse(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Here are the features we identified and the corresponding diffs:\n{response.model_dump_json()}"}
        ],
        response_format=CommitMessages
    )

    return response.choices[0].message.parsed

# Example usage and testing functions
if __name__ == "__main__":
    # Example usage
    repo_path = "test_git"
    
    try:
        # Test git status --> '--porcelain'
        status = run_git_command(['status'], repo_path)
        print("Git Status:")
        print(status)
        
        print("EXAMINING UNTRACKED FILES")
        print("="*50)
        untracked_diffs = examine_untracked_files(repo_path)
        
        import pprint
        pprint.pprint(untracked_diffs)

    except Exception as e:
        print(f"Error: {e}")


    features1 = "Writing text files"
    features2 = "greating Flask app"
    features = [features1, features2]
    response = analyze_diff(untracked_diffs, features)
    print(response)

    commit_message = create_commit_message(response, untracked_diffs)

    for commit in commit_message:
        print(commit, '\n')