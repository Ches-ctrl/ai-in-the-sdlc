from pymongo import MongoClient
from pymongo.operations import SearchIndexModel
import os
import openai
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class MongoClientService:
    """
    MongoDB client service for handling logs and git commits with vector embeddings.
    """
    
    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.mongo_uri:
            raise ValueError("MONGO_URI environment variable is required")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
            
        # Initialize OpenAI client
        openai.api_key = self.openai_api_key
        
        # Initialize MongoDB client
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client.get_database("GitDaddy")
        
        # Collections
        self.logs_collection = self.db.get_collection("logs")
        self.commits_collection = self.db.get_collection("gitstore")
        
        # Ensure vector search index exists for commits
        self._ensure_vector_index()
    
    def _ensure_vector_index(self):
        """Ensure vector search index exists for commits collection."""
        try:
            # Check if index already exists
            existing_indexes = list(self.commits_collection.list_search_indexes())
            vector_index_exists = any(idx.get('name') == 'vector_index' for idx in existing_indexes)
            
            if not vector_index_exists:
                search_index_model = SearchIndexModel(
                    definition={
                        "fields": [
                            {
                                "type": "vector",
                                "path": "embedding",
                                "similarity": "dotProduct",
                                "numDimensions": 1536
                            }
                        ]
                    },
                    name="vector_index",
                    type="vectorSearch"
                )
                self.commits_collection.create_search_index(model=search_index_model)
                logger.info("Vector search index created successfully")
        except Exception as e:
            logger.warning(f"Could not create/verify vector index: {e}")
    
    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI's text-embedding-3-small model."""
        try:
            response = openai.embeddings.create(
                model="text-embedding-3-small",
                input=text,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    # LOG METHODS
    def insert_log(self, data: Dict[str, Any]) -> str:
        """
        Insert a log entry into the logs collection.
        
        Args:
            level: Log level (e.g., 'INFO', 'ERROR', 'DEBUG')
            message: Log message
            metadata: Optional additional metadata
            
        Returns:
            Inserted document ID as string
        """
        try:
            log_entry = {
                "timestamp": datetime.utcnow(),
                **data
            }
            
            result = self.logs_collection.insert_one(log_entry)
            logger.info(f"Log inserted with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error inserting log: {e}")
            raise
    
    def get_logs(self, 
                 level: Optional[str] = None, 
                 limit: int = 100, 
                 start_date: Optional[datetime] = None,
                 end_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Retrieve logs from the collection.
        
        Args:
            level: Filter by log level (optional)
            limit: Maximum number of logs to return
            start_date: Filter logs after this date (optional)
            end_date: Filter logs before this date (optional)
            
        Returns:
            List of log documents
        """
        try:
            # Build query
            query = {}
            
            if start_date or end_date:
                query["timestamp"] = {}
                if start_date:
                    query["timestamp"]["$gte"] = start_date
                if end_date:
                    query["timestamp"]["$lte"] = end_date
            
            # Execute query with sorting (newest first)
            cursor = self.logs_collection.find(query).sort("timestamp", -1).limit(limit)
            logs = list(cursor)
            
            # Convert ObjectId to string for JSON serialization
            for log in logs:
                log["_id"] = str(log["_id"])
            
            logger.info(f"Retrieved {len(logs)} logs")
            return logs
        except Exception as e:
            logger.error(f"Error retrieving logs: {e}")
            raise
    
    # COMMIT METHODS
    def insert_commit(self, 
                     commit_hash: str, 
                     message: str, 
                     author: str,
                     prompt: str,
                     timestamp: datetime,
                     files_changed: Optional[List[str]] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Insert a git commit with vector embedding.
        
        Args:
            commit_hash: Git commit hash
            message: Commit message
            author: Commit author
            timestamp: Commit timestamp
            diff: Git diff content (optional)
            files_changed: List of changed files (optional)
            metadata: Additional metadata (optional)
            
        Returns:
            Inserted document ID as string
        """
        try:
            # Create text to embed (combine relevant information)
            embed_text = f"Commit: {message}"
            if files_changed:
                embed_text += f"\nFiles: {', '.join(files_changed)}"
            
            # Generate embedding
            embedding = self._embed_text(embed_text)
            
            commit_doc = {
                "commit_hash": commit_hash,
                "message": message,
                "prompt": prompt,
                "author": author,
                "timestamp": timestamp,
                "files_changed": files_changed or [],
                "embedding": embedding,
                "embed_text": embed_text,
                "created_at": datetime.utcnow()
            }
            
            result = self.commits_collection.insert_one(commit_doc)
            logger.info(f"Commit inserted with ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error inserting commit: {e}")
            raise
    
    def get_commit_by_hash(self, commit_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a commit by its hash.
        
        Args:
            commit_hash: Git commit hash
            
        Returns:
            Commit document or None if not found
        """
        try:
            commit = self.commits_collection.find_one({"commit_hash": commit_hash})
            if commit:
                commit["_id"] = str(commit["_id"])
            return commit
        except Exception as e:
            logger.error(f"Error retrieving commit by hash: {e}")
            raise
    
    def get_commits_by_similarity(self, 
                                 query_text: str, 
                                 limit: int = 5, 
                                 min_score: float = 0.7) -> List[Dict[str, Any]]:
        """
        Retrieve commits similar to the query text using vector search.
        
        Args:
            query_text: Text to search for similar commits
            limit: Maximum number of results
            min_score: Minimum similarity score threshold
            
        Returns:
            List of similar commit documents with similarity scores
        """
        try:
            # Generate embedding for query
            query_embedding = self._embed_text(query_text)
            
            # Vector search pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "queryVector": query_embedding,
                        "path": "embedding",
                        "exact": True,
                        "limit": limit
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "commit_hash": 1,
                        "message": 1,
                        "author": 1,
                        "timestamp": 1,
                        "files_changed": 1,
                        "metadata": 1,
                        "score": {
                            "$meta": "vectorSearchScore"
                        }
                    }
                },
                {
                    "$match": {
                        "score": {"$gte": min_score}
                    }
                }
            ]
            
            # Execute search
            results = list(self.commits_collection.aggregate(pipeline))
            
            # Convert ObjectId to string
            for result in results:
                result["_id"] = str(result["_id"])
            
            logger.info(f"Found {len(results)} similar commits for query: {query_text}")
            return results
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            raise
    
    def get_recent_commits(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent commits.
        
        Args:
            limit: Maximum number of commits to return
            
        Returns:
            List of recent commit documents
        """
        try:
            cursor = self.commits_collection.find({}).sort("timestamp", -1).limit(limit)
            commits = list(cursor)
            
            # Convert ObjectId to string
            for commit in commits:
                commit["_id"] = str(commit["_id"])
                # Remove embedding from response to reduce size
                commit.pop("embedding", None)
            
            logger.info(f"Retrieved {len(commits)} recent commits")
            return commits
        except Exception as e:
            logger.error(f"Error retrieving recent commits: {e}")
            raise
    
    def close(self):
        """Close the MongoDB connection."""
        self.client.close()
        logger.info("MongoDB connection closed")

# Singleton instance
_mongo_client = None

def get_mongo_client() -> MongoClientService:
    """Get singleton MongoDB client instance."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClientService()
    return _mongo_client
