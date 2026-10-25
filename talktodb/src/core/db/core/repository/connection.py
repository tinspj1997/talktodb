from talktodb.src.core.db.connectors.base import Schema
from talktodb.src.core.db.core.database import load_state, save_state


class ConnectionRepository:
    """Saved connections in the JSON state file, keyed by database URL."""

    def get_by_url(self, db_url: str) -> dict | None:
        """Return {"id": ..., "schema": {...}} or None if nothing is saved."""
        return load_state()["connections"].get(db_url)

    def save(self, db_url: str, schema: Schema) -> dict:
        """Save the schema for a connection, keeping its id if it already exists."""
        state = load_state()
        connections = state["connections"]
        existing = connections.get(db_url)
        if existing:
            connection_id = existing["id"]
        else:
            connection_id = max((c["id"] for c in connections.values()), default=0) + 1
        connections[db_url] = {"id": connection_id, "schema": schema}
        save_state(state)
        return connections[db_url]

    def delete(self, db_url: str) -> bool:
        """Delete the saved connection. True if it existed."""
        state = load_state()
        if state["connections"].pop(db_url, None) is None:
            return False
        save_state(state)
        return True
