import json
import sqlite3

from talktodb.src.core.artifacts.decorator import with_core_connection


class SchemaRepository:
    @with_core_connection
    def save(self, conn: sqlite3.Connection, db_url: str, schema: dict) -> None:
        """Replace the saved tables of a connection (one record per table)
        and mark its schema as created."""
        row = conn.execute(
            "SELECT id FROM connections WHERE db_url = ?", (db_url,)
        ).fetchone()
        if row is None:
            raise ValueError(f"No connection saved for {db_url!r}")
        connection_id = row["id"]

        conn.execute("DELETE FROM schemas WHERE connection_id = ?", (connection_id,))
        conn.executemany(
            "INSERT INTO schemas (connection_id, table_name, columns) VALUES (?, ?, ?)",
            [
                (connection_id, table, json.dumps(columns))
                for table, columns in schema.items()
            ],
        )
        conn.execute(
            "UPDATE connections SET schema_created = 1 WHERE id = ?", (connection_id,)
        )

    @with_core_connection
    def get(self, conn: sqlite3.Connection, db_url: str) -> dict | None:
        """Return {table_name: {column: details}} or None if nothing saved."""
        rows = conn.execute(
            """
            SELECT s.table_name, s.columns
            FROM schemas s JOIN connections c ON c.id = s.connection_id
            WHERE c.db_url = ?
            """,
            (db_url,),
        ).fetchall()
        return {r["table_name"]: json.loads(r["columns"]) for r in rows} or None
