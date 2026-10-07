from talktodb.src.core.db.vector.database import get_vector_client


def _collection_name(connection_id: int) -> str:
    return f"schema_{connection_id}"


def build_chunk(table_name: str, columns: dict[str, dict]) -> str:
    """Build the text chunk that gets embedded for one table."""
    lines = [f"table_name: {table_name}", "columns:"]
    for name, info in columns.items():
        details = [info["type"]]
        if info["primary_key"]:
            details.append("primary key")
        if info["unique"]:
            details.append("unique")
        details.append("nullable" if info["nullable"] else "not null")
        if info["foreign_key"]:
            details.append(f"foreign key -> {info['foreign_key']}")
        lines.append(f"- {name} ({', '.join(details)})")
    return "\n".join(lines)


class SchemaVectorRepository:
    """Embedded schema chunks (one per table) in ChromaDB."""

    def save(self, connection_id: int, schema: dict[str, dict[str, dict]]) -> None:
        """Replace the connection's collection with one chunk per table."""
        self.delete(connection_id)
        collection = get_vector_client().create_collection(_collection_name(connection_id))
        if not schema:
            return
        collection.add(
            ids=[f"{connection_id}:{table}" for table in schema],
            documents=[build_chunk(table, cols) for table, cols in schema.items()],
            metadatas=[
                {"connection_id": connection_id, "table_name": table} for table in schema
            ],
        )

    def delete(self, connection_id: int) -> None:
        client = get_vector_client()
        name = _collection_name(connection_id)
        if name in {c.name for c in client.list_collections()}:
            client.delete_collection(name)

    def search(self, connection_id: int, question: str, n_results: int = 3) -> list[dict]:
        """Return the chunks closest to the question, best match first."""
        client = get_vector_client()
        name = _collection_name(connection_id)
        if name not in {c.name for c in client.list_collections()}:
            return []
        collection = client.get_collection(name)
        result = collection.query(
            query_texts=[question], n_results=min(n_results, collection.count())
        )
        return [
            {"table_name": meta["table_name"], "chunk": doc, "distance": dist}
            for doc, meta, dist in zip(
                result["documents"][0], result["metadatas"][0], result["distances"][0]
            )
        ]
