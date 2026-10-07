import functools
import sqlite3
from collections.abc import Callable

from talktodb.src.core.db.core.database import get_core_connection, init_core_db


def with_core_connection(func: Callable) -> Callable:
    """Open a core.db connection, pass it to `func` as the first argument
    after `self`, commit on success / roll back on error, then close it."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        conn: sqlite3.Connection = get_core_connection()
        try:
            with conn:  # commit or rollback
                init_core_db(conn)  # no-op when the tables already exist
                return func(self, conn, *args, **kwargs)
        finally:
            conn.close()

    return wrapper
