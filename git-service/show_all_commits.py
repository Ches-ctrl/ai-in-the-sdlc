#!/usr/bin/env python3
"""Show all commits stored in MongoDB."""

from dotenv import load_dotenv
from repository.mongo_client import get_mongo_client
from datetime import datetime

# Load environment variables
load_dotenv()

def show_all_commits():
    """Display all commits in the database."""
    
    print("="*80)
    print("ALL COMMITS IN DATABASE")
    print("="*80)
    
    try:
        # Get MongoDB client
        mongo_client = get_mongo_client()
        
        # Get all commits (not just recent ones)
        all_commits = list(mongo_client.commits_collection.find({}).sort("timestamp", -1))
        
        print(f"\nTotal commits: {len(all_commits)}\n")
        
        for i, commit in enumerate(all_commits, 1):
            print(f"{'='*80}")
            print(f"COMMIT #{i}")
            print(f"{'='*80}")
            
            # Basic info
            print(f"Hash:      {commit.get('commit_hash', 'N/A')}")
            print(f"Author:    {commit.get('author', 'N/A')}")
            print(f"Timestamp: {commit.get('timestamp', 'N/A')}")
            print(f"Created:   {commit.get('created_at', 'N/A')}")
            
            # Message
            message = commit.get('message', 'N/A')
            print(f"\nMessage:")
            print(f"  {message}")
            
            # Original prompt that triggered this commit
            prompt = commit.get('prompt', 'N/A')
            print(f"\nOriginal Prompt:")
            if prompt and prompt != 'N/A':
                # Show first 200 chars of prompt
                if len(prompt) > 200:
                    print(f"  {prompt[:200]}...")
                else:
                    print(f"  {prompt}")
            else:
                print("  N/A")
            
            # Files changed
            files = commit.get('files_changed', [])
            if files:
                print(f"\nFiles Changed ({len(files)}):")
                for file in files:
                    print(f"  - {file}")
            else:
                print("\nFiles Changed: None")
            
            # Embedding info
            if 'embedding' in commit:
                print(f"\nEmbedding: ✅ Present (dimension: {len(commit['embedding'])})")
                if 'embed_text' in commit:
                    print(f"Embed Text: {commit['embed_text'][:100]}...")
            else:
                print("\nEmbedding: ❌ Not present")
            
            # Any additional metadata
            exclude_keys = ['_id', 'commit_hash', 'message', 'author', 'timestamp', 
                          'created_at', 'prompt', 'files_changed', 'embedding', 'embed_text']
            extra_fields = {k: v for k, v in commit.items() if k not in exclude_keys}
            if extra_fields:
                print("\nAdditional Fields:")
                for key, value in extra_fields.items():
                    print(f"  {key}: {value}")
            
            print()
        
        # Summary statistics
        print("="*80)
        print("SUMMARY STATISTICS")
        print("="*80)
        
        # Count by author
        authors = {}
        for commit in all_commits:
            author = commit.get('author', 'Unknown')
            authors[author] = authors.get(author, 0) + 1
        
        print("\nCommits by Author:")
        for author, count in sorted(authors.items(), key=lambda x: x[1], reverse=True):
            print(f"  {author}: {count}")
        
        # Files most frequently changed
        file_counts = {}
        for commit in all_commits:
            for file in commit.get('files_changed', []):
                file_counts[file] = file_counts.get(file, 0) + 1
        
        if file_counts:
            print("\nMost Frequently Changed Files:")
            for file, count in sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {file}: {count} times")
        
        # Commits with embeddings
        with_embeddings = sum(1 for c in all_commits if 'embedding' in c)
        print(f"\nCommits with Embeddings: {with_embeddings}/{len(all_commits)}")
        
        # Date range
        if all_commits:
            timestamps = [c.get('timestamp') for c in all_commits if c.get('timestamp')]
            if timestamps:
                earliest = min(timestamps)
                latest = max(timestamps)
                print(f"\nDate Range:")
                print(f"  Earliest: {earliest}")
                print(f"  Latest:   {latest}")
        
        mongo_client.close()
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    show_all_commits()