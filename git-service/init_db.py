from pymongo.operations import SearchIndexModel
from pymongo import MongoClient
import os
import openai
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")


client = MongoClient(MONGO_URI)
db = client.get_database("GitDaddy")
collection = db.get_collection("gitstore")

# Create your index model, then create the search index
search_index_model = SearchIndexModel(
  definition = {
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

print(collection.create_search_index(model=search_index_model))



# Create a function to embed a text
def embed_text(text: str) -> list[float]:
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        encoding_format="float"
    )
    return response.data[0].embedding

# Create a function to insert a document into the collection
def insert_document(text: str) -> None:
    embedding = embed_text(text)
    collection.insert_one({"text": text, "embedding": embedding, "delete_me": True})



if __name__ == "__main__":
    
    # Add some documents to the collection
    insert_document("Hello, world! 1")
    insert_document("Hello, world! 2")
    insert_document("Hello, world! 3")
    insert_document("Hello, world! 4")
    insert_document("Hello, world! 5")
    



    # Generate embedding for the search query
    query_embedding = embed_text("Hello, world!")
    # Sample vector search pipeline
    pipeline = [
    {
        "$vectorSearch": {
                "index": "vector_index",
                "queryVector": query_embedding,
                "path": "embedding",
                "exact": True,
                "limit": 5
        }
    }, 
    {
        "$project": {
            "_id": 0, 
            "text": 1,
            "score": {
                "$meta": "vectorSearchScore"
            }
        }
    }
    ]
    # Execute the search
    results = collection.aggregate(pipeline)
    # Print results
    for i in results:
        print(i)

    # Delete the collection
    collection.delete_many({"delete_me": True})