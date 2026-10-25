from urllib.parse import urlsplit

from talktodb.src.core.db.connectors.base import BaseConnector, ConnectorError
from talktodb.src.core.db.connectors.mysql import MySQLConnector
from talktodb.src.core.db.connectors.postgres import PostgresConnector

# URL scheme -> connector. Add a new database by writing a BaseConnector
# subclass and registering its schemes here.
CONNECTORS: dict[str, type[BaseConnector]] = {
    "postgres": PostgresConnector,
    "postgresql": PostgresConnector,
    "mysql": MySQLConnector,
    "mariadb": MySQLConnector,
}


def get_connector(url: str) -> BaseConnector:
    """Pick the connector from the URL scheme, e.g. postgresql:// or mysql://.
    A SQLAlchemy-style driver suffix (postgresql+psycopg://) is dropped."""
    full_scheme = urlsplit(url).scheme
    scheme = full_scheme.partition("+")[0]
    connector = CONNECTORS.get(scheme)
    if connector is None:
        supported = ", ".join(sorted(CONNECTORS))
        raise ConnectorError(f"Unsupported database {scheme!r}. Supported: {supported}")
    return connector(scheme + url[len(full_scheme):])


__all__ = ["BaseConnector", "ConnectorError", "get_connector"]
