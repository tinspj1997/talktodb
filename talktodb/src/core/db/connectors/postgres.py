import psycopg
from psycopg.rows import dict_row

from talktodb.src.core.db.connectors.base import (
    MAX_ROWS,
    BaseConnector,
    ConnectorError,
    Schema,
    validate_select,
)

# Every column of every table, view and materialized view outside the system schemas.
COLUMNS_QUERY = """
SELECT n.nspname AS schema_name,
       c.relname AS table_name,
       a.attname AS column_name,
       format_type(a.atttypid, a.atttypmod) AS data_type,
       NOT a.attnotnull AS nullable
FROM pg_attribute a
JOIN pg_class c ON c.oid = a.attrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r', 'p', 'v', 'm', 'f')
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
ORDER BY n.nspname, c.relname, a.attnum
"""

# One row per column of every primary key, unique and foreign key constraint.
CONSTRAINTS_QUERY = """
SELECT con.contype AS kind,
       n.nspname AS schema_name,
       c.relname AS table_name,
       a.attname AS column_name,
       cardinality(con.conkey) AS column_count,
       fn.nspname AS ref_schema,
       fc.relname AS ref_table,
       fa.attname AS ref_column
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN LATERAL unnest(con.conkey, con.confkey) AS k(attnum, ref_attnum)
JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
LEFT JOIN pg_class fc ON fc.oid = con.confrelid
LEFT JOIN pg_namespace fn ON fn.oid = fc.relnamespace
LEFT JOIN pg_attribute fa ON fa.attrelid = con.confrelid AND fa.attnum = k.ref_attnum
WHERE con.contype IN ('p', 'u', 'f')
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
"""


def _table_name(schema_name: str, table_name: str) -> str:
    """Tables in `public` keep their bare name; others are schema-qualified."""
    return table_name if schema_name == "public" else f"{schema_name}.{table_name}"


class PostgresConnector(BaseConnector):
    dialect = "PostgreSQL"

    def _connect(self) -> psycopg.Connection:
        try:
            return psycopg.connect(self.url, row_factory=dict_row, connect_timeout=10)
        except psycopg.Error as exc:
            raise ConnectorError(str(exc)) from exc

    def check_connection(self) -> None:
        with self._connect() as conn:
            try:
                conn.execute("SELECT 1")
            except psycopg.Error as exc:
                raise ConnectorError(str(exc)) from exc

    def fetch_schema(self) -> Schema:
        with self._connect() as conn:
            try:
                columns = conn.execute(COLUMNS_QUERY).fetchall()
                constraints = conn.execute(CONSTRAINTS_QUERY).fetchall()
            except psycopg.Error as exc:
                raise ConnectorError(str(exc)) from exc

        schema: Schema = {}
        for row in columns:
            table = _table_name(row["schema_name"], row["table_name"])
            schema.setdefault(table, {})[row["column_name"]] = {
                "type": row["data_type"],
                "primary_key": False,
                "unique": False,
                "nullable": row["nullable"],
                "foreign_key": None,
            }

        for row in constraints:
            table = _table_name(row["schema_name"], row["table_name"])
            column = schema.get(table, {}).get(row["column_name"])
            if column is None:
                continue
            if row["kind"] == "p":
                column["primary_key"] = True
            elif row["kind"] == "u" and row["column_count"] == 1:
                column["unique"] = True
            elif row["kind"] == "f":
                ref_table = _table_name(row["ref_schema"], row["ref_table"])
                column["foreign_key"] = f"{ref_table}.{row['ref_column']}"
        return schema

    def execute_query(self, sql: str) -> list[dict]:
        query = validate_select(sql)
        with self._connect() as conn:
            conn.read_only = True  # the server rejects any write in this transaction
            try:
                with conn.cursor() as cur:
                    cur.execute(query)
                    return cur.fetchmany(MAX_ROWS)
            except psycopg.Error as exc:
                raise ConnectorError(str(exc)) from exc
