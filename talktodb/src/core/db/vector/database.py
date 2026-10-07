import chromadb

# Local persistent ChromaDB that holds the embedded schema chunks.
VECTOR_DB_PATH = "chroma_db"


def get_vector_client() -> chromadb.ClientAPI:
    return chromadb.PersistentClient(path=VECTOR_DB_PATH)
