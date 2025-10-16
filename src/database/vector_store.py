from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from langchain_openai import OpenAIEmbeddings
from ..config import settings

from qdrant_client.http.models import Distance, VectorParams

qdrant_client = QdrantClient(
    url=settings.qdrant_url,
    api_key=settings.qdrant_api_key,
    check_compatibility=False
)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

try:
    collections_response = qdrant_client.get_collections()
    existing_collections = {c.name for c in collections_response.collections}
    
    if settings.qdrant_collection_name not in existing_collections:
        print(f"Collection '{settings.qdrant_collection_name}' not found. Creating it now...")
        vector_size = 1536 
        qdrant_client.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        print(f"Collection '{settings.qdrant_collection_name}' created successfully.")
    else:
        print(f"Collection '{settings.qdrant_collection_name}' already exists. Skipping creation.")

except Exception as e:
    print(f"An error occurred while checking/creating Qdrant collection: {e}")
    

vector_store = QdrantVectorStore(
    client=qdrant_client,
    collection_name=settings.qdrant_collection_name,
    embedding=embeddings,
)
