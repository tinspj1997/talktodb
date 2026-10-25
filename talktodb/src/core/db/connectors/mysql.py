from urllib.parse import unquote, urlsplit

import pymysql
from pymysql.cursors import DictCursor

from talktodb.src.core.db.connectors.base import (
    MAX_ROWS,
    BaseConnector,
    ConnectorError,
    Schema,
    validate_select,
)

# Every column of every table and view in the database named in the URL.
COLUMNS_QUERY = """
SELECT TABLE_NAME AS table_name,
       COLUMN_NAME AS column_name,
       COLUMN_TYPE AS data_type,
       IS_NULLABLE = 'YES' AS nullable,
       COLUMN_KEY AS column_key
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME, ORDINAL_POSITION
"""

FOREIGN_KEYS_QUERY = """
SELECT TABLE_NAME AS table_name,
       COLUMN_NAME AS column_name,
       REFERENCED_TABLE_NAME AS ref_table,
       REFERENCED_COLUMN_NAME AS ref_column
FROM information_schema.KEY_COLUMN_USAGE
WHERE TABLE_SCHEMA = DATABASE()
  AND REFERENCED_TABLE_NAME IS NOT NULL
"""


class MySQLConnector(BaseConnector):
    dialect = "MySQL"

    def _connect(self) -> pymysql.connections.Connection:
        """Open a connection from a mysql://user:pass@host:port/db URL."""
        parts = urlsplit(self.url)
        try:
            return pymysql.connect(
                host=parts.hostname or "localhost",
                port=parts.port or 3306,
                user=unquote(parts.username or ""),
                password=unquote(parts.password or ""),
                database=parts.path.lstrip("/") or None,
                cursorclass=DictCursor,
                connect_timeout=10,
            )
        except pymysql.MySQLError as exc:
            raise ConnectorError(str(exc)) from exc

    def check_connection(self) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        except pymysql.MySQLError as exc:
            raise ConnectorError(str(exc)) from exc
        finally:
            conn.close()

    def fetch_schema(self) -> Schema:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(COLUMNS_QUERY)
                columns = cur.fetchall()
                cur.execute(FOREIGN_KEYS_QUERY)
                foreign_keys = cur.fetchall()
        except pymysql.MySQLError as exc:
            raise ConnectorError(str(exc)) from exc
        finally:
            conn.close()

        schema: Schema = {}
        for row in columns:
            schema.setdefault(row["table_name"], {})[row["column_name"]] = {
                "type": row["data_type"],
                "primary_key": row["column_key"] == "PRI",
                "unique": row["column_key"] == "UNI",
                "nullable": bool(row["nullable"]),
                "foreign_key": None,
            }

        for row in foreign_keys:
            column = schema.get(row["table_name"], {}).get(row["column_name"])
            if column is not None:
                column["foreign_key"] = f"{row['ref_table']}.{row['ref_column']}"
        return schema

    def execute_query(self, sql: str) -> list[dict]:
        query = validate_select(sql)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                # the server rejects any write in this transaction
                cur.execute("START TRANSACTION READ ONLY")
                cur.execute(query)
                rows = cur.fetchmany(MAX_ROWS)
            conn.rollback()
            return list(rows)
        except pymysql.MySQLError as exc:
            raise ConnectorError(str(exc)) from exc
        finally:
            conn.close()
