import json

from agno.agent import Agent
from agno.db.in_memory import InMemoryDb
from agno.models.openai import OpenAIResponses

from talktodb.src.core.artifacts.settings import settings
from talktodb.src.core.db.connectors import ConnectorError, get_connector
from talktodb.src.core.db.core.repository.connection import ConnectionRepository
from talktodb.src.core.db.vector.repository.schema import SchemaVectorRepository


def _dialect() -> str:
    """SQL dialect of the configured database, or plain "SQL" if unsupported."""
    try:
        return get_connector(settings.DATABASE_URL).dialect
    except ConnectorError:
        return "SQL"


DIALECT = _dialect()

INSTRUCTIONS = [
    f"You answer questions about a {DIALECT} database by querying it with tools.",
    "Work step by step: 1) call search_schema to find the relevant tables, "
    f"2) write a read-only {DIALECT} SELECT using only tables and columns returned "
    "by search_schema, joining through the listed foreign keys, 3) run it with "
    "run_query, 4) answer the user from the returned rows.",
    "If search_schema does not return the table you need, call it again with different "
    "wording (for example synonyms or the likely table name) before giving up.",
    "If run_query returns an error, read it, fix the query and run it again.",
    "Never invent tables, columns or data. Never write INSERT, UPDATE, DELETE, DROP or DDL.",
    "Show the SQL you ran, then a short answer and the data (as a markdown table when "
    "there are several rows). Tell the user when no rows were returned.",
    "If the question is unrelated to the database, say so briefly.",
]


_vectors = SchemaVectorRepository()


def search_schema(query: str) -> str:
    """Find the database tables most relevant to a topic.

    Args:
        query: What you are looking for, e.g. "support tickets" or "user emails".

    Returns:
        The matching tables with their columns, data types, keys and foreign keys.
    """
    connection = ConnectionRepository().get_by_url(settings.DATABASE_URL)
    if not connection:
        return "ERROR: No schema found. Run with --connect first."
    chunks = _vectors.search(connection["id"], query)
    if not chunks:
        return "No matching tables found."
    return "\n\n".join(item["chunk"] for item in chunks)


def run_query(sql: str) -> str:
    """Run one read-only SELECT query and return the rows.

    Args:
        sql: A single SELECT (or WITH ... SELECT) query.

    Returns:
        The rows as JSON (at most 100), or an error message to fix the query.
    """
    try:
        rows = get_connector(settings.DATABASE_URL).execute_query(sql)
    except ConnectorError as exc:
        return f"ERROR: {exc}"
    return json.dumps(rows, default=str)


# Created once at import time with its tools attached; everything reuses this instance.
sql_agent = Agent(
    name="SQL Agent",
    model=OpenAIResponses(
        id=settings.LLM_MODEL_NAME,
        api_key=settings.LLM_MODEL_API_KEY,
        base_url=settings.LLM_BASE_URL,
    ),
    description=f"Answers questions about a {DIALECT} database.",
    instructions=INSTRUCTIONS,
    tools=[search_schema, run_query],
    # Keep the last few turns so follow-up questions have context.
    db=InMemoryDb(),
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)
