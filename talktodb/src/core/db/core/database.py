import sqlite3

# Local SQLite database that holds the application's own state
# (connection status, schema sync status, ...).
CORE_DB_PATH = "core.db"

CREATE_CONNECTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS connections (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    db_url         TEXT    NOT NULL UNIQUE,
    is_connected   INTEGER NOT NULL DEFAULT 0,
    schema_created INTEGER NOT NULL DEFAULT 0
)
"""

CREATE_SCHEMAS_TABLE = """
CREATE TABLE IF NOT EXISTS schemas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id INTEGER NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    table_name    TEXT    NOT NULL,
    columns       TEXT    NOT NULL,
    UNIQUE (connection_id, table_name)
)
"""


def get_core_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(CORE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # enforce FK / ON DELETE CASCADE
    return conn


def init_core_db(conn: sqlite3.Connection) -> None:
    """Create the core tables if they do not exist."""
    conn.execute(CREATE_CONNECTIONS_TABLE)
    conn.execute(CREATE_SCHEMAS_TABLE)
