from abc import ABC, abstractmethod

# Most rows a query returns to the agent.
MAX_ROWS = 100

# {table_name: {column_name: {type, primary_key, unique, nullable, foreign_key}}}
Schema = dict[str, dict[str, dict]]


class ConnectorError(Exception):
    """Any connection or query failure, whatever the driver behind it."""


def validate_select(sql: str) -> str:
    """Return the query without a trailing ';' if it is a single SELECT / WITH,
    else raise ConnectorError."""
    query = sql.strip().rstrip(";").strip()
    if ";" in query:
        raise ConnectorError("Only a single statement is allowed.")
    first_word = query.split(None, 1)[0].lower() if query else ""
    if first_word not in ("select", "with"):
        raise ConnectorError("Only SELECT (or WITH ... SELECT) queries are allowed.")
    return query


class BaseConnector(ABC):
    """A database the user talks to. Each subclass wraps one driver and
    raises ConnectorError instead of the driver's own exceptions."""

    # SQL dialect name the agent is told to write, e.g. "PostgreSQL".
    dialect: str = "SQL"

    def __init__(self, url: str) -> None:
        self.url = url

    @abstractmethod
    def check_connection(self) -> None:
        """Open a connection and run a trivial query."""

    @abstractmethod
    def fetch_schema(self) -> Schema:
        """Read every table with its columns, types, keys and foreign keys."""

    @abstractmethod
    def execute_query(self, sql: str) -> list[dict]:
        """Run one SELECT in a read-only transaction, return at most MAX_ROWS rows."""
