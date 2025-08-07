#!/usr/bin/env python3
"""Test MongoDB connection and data retrieval."""

import os
import sys
from dotenv import load_dotenv
from repository.mongo_client import get_mongo_client

# Load environment variables
load_dotenv()

def test_mongodb_connection():
    """Test MongoDB connection and retrieve data."""
    
    print("="*60)
    print("MONGODB CONNECTION TEST")
    print("="*60)
    
    try:
        # Get MongoDB client
        print("\n1. Connecting to MongoDB...")
        mongo_client = get_mongo_client()
        print("   ✅ Connected successfully")
        
        # Check environment variables
        print("\n2. Environment variables:")
        mongo_uri = os.getenv("MONGO_URI")
        openai_key = os.getenv("OPENAI_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        
        print(f"   MONGO_URI: {'✅ Set' if mongo_uri else '❌ Not set'}")
        print(f"   OPENAI_API_KEY: {'✅ Set' if openai_key else '❌ Not set'}")
        print(f"   ANTHROPIC_API_KEY: {'✅ Set' if anthropic_key else '❌ Not set'}")
        
        # Test database connection
        print("\n3. Testing database access:")
        print(f"   Database: {mongo_client.db.name}")
        
        # List collections
        collections = mongo_client.db.list_collection_names()
        print(f"   Collections: {collections}")
        
        # Check commits collection
        print("\n4. Checking commits collection (gitstore):")
        commit_count = mongo_client.commits_collection.count_documents({})
        print(f"   Total commits in database: {commit_count}")
        
        if commit_count > 0:
            # Get sample commits
            print("\n5. Sample commits (latest 3):")
            recent_commits = mongo_client.get_recent_commits(limit=3)
            
            for i, commit in enumerate(recent_commits, 1):
                print(f"\n   Commit {i}:")
                print(f"   - Hash: {commit.get('commit_hash', 'N/A')}")
                print(f"   - Message: {commit.get('message', 'N/A')[:50]}...")
                print(f"   - Author: {commit.get('author', 'N/A')}")
                print(f"   - Files: {', '.join(commit.get('files_changed', [])[:3])}")
                if commit.get('prompt'):
                    print(f"   - Prompt: {commit.get('prompt', '')[:50]}...")
        
        # Check logs collection
        print("\n6. Checking logs collection:")
        log_count = mongo_client.logs_collection.count_documents({})
        print(f"   Total logs in database: {log_count}")
        
        # Test vector search capability
        print("\n7. Testing vector search capability:")
        if commit_count > 0:
            try:
                # Test with a simple query
                test_query = "login authentication error"
                print(f"   Searching for: '{test_query}'")
                
                similar_commits = mongo_client.get_commits_by_similarity(
                    query_text=test_query,
                    limit=3,
                    min_score=0.0  # Set to 0 to get any results
                )
                
                if similar_commits:
                    print(f"   ✅ Vector search working! Found {len(similar_commits)} similar commits")
                    for commit in similar_commits:
                        print(f"      - {commit.get('commit_hash', 'N/A')[:8]}: {commit.get('message', 'N/A')[:40]}... (score: {commit.get('score', 0):.3f})")
                else:
                    print("   ⚠️ Vector search returned no results (this is normal if commits don't match the query)")
            except Exception as e:
                print(f"   ❌ Vector search error: {str(e)}")
        else:
            print("   ⏭️ Skipping vector search (no commits in database)")
        
        # Check indexes
        print("\n8. Checking indexes:")
        try:
            indexes = list(mongo_client.commits_collection.list_search_indexes())
            if indexes:
                print(f"   Found {len(indexes)} search indexes:")
                for idx in indexes:
                    print(f"   - {idx.get('name', 'unnamed')}: {idx.get('type', 'unknown')}")
            else:
                print("   ⚠️ No search indexes found (vector search may not work)")
        except Exception as e:
            print(f"   ⚠️ Could not list indexes: {str(e)}")
        
        print("\n" + "="*60)
        print("✅ DATABASE CONNECTION TEST COMPLETE")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check that MongoDB is running")
        print("2. Verify MONGO_URI in .env file")
        print("3. Ensure database 'GitDaddy' exists")
        print("4. Check network connectivity to MongoDB")
        return False
    
    finally:
        try:
            mongo_client.close()
            print("\n✅ MongoDB connection closed")
        except:
            pass


if __name__ == "__main__":
    success = test_mongodb_connection()
    sys.exit(0 if success else 1)