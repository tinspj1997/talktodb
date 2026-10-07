import sqlite3

from talktodb.src.core.artifacts.decorator import with_core_connection


class ConnectionRepository:
    @with_core_connection
    def get_by_url(self, conn: sqlite3.Connection, db_url: str) -> dict | None:
        row = conn.execute(
            "SELECT * FROM connections WHERE db_url = ?", (db_url,)
        ).fetchone()
        return dict(row) if row else None

    @with_core_connection
    def set_connected(
        self, conn: sqlite3.Connection, db_url: str, is_connected: bool
    ) -> None:
        """Insert the connection row if missing, then update is_connected."""
        conn.execute(
            """
            INSERT INTO connections (db_url, is_connected)
            VALUES (?, ?)
            ON CONFLICT(db_url) DO UPDATE SET is_connected = excluded.is_connected
            """,
            (db_url, int(is_connected)),
        )
