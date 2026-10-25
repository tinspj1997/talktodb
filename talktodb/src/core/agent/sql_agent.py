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
    "If the question is unrelated to the database, say so briefly.",
    "Always start your reply with the SQL you ran in a ```sql block. Tell the user when no rows were returned.",
]

# How the answer after the SQL is written; the chat picks one (--table selects TABLE_STYLE).
DESCRIPTIVE_STYLE = [
    "After the SQL, answer in a descriptive way: plain sentences that explain what the data "
    "shows, naming the actual values. Do not use tables.",
    "When there are many rows, describe the overall picture (totals, highest, lowest, notable "
    "patterns) and mention the most important rows by name instead of listing every row.",
    "Explain missing values in words, e.g. 'users with no organization' instead of 'NULL'.",
]
TABLE_STYLE = [
    "After the SQL, give a one-sentence answer, then all returned rows as a markdown table "
    "with the column names as headers.",
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
    instructions=INSTRUCTIONS + DESCRIPTIVE_STYLE,
    tools=[search_schema, run_query],
    # Keep the last few turns so follow-up questions have context.
    db=InMemoryDb(),
    add_history_to_context=True,
    num_history_runs=5,
    markdown=True,
)


def set_answer_style(table: bool) -> None:
    """Answer with markdown tables (table=True) or in descriptive sentences."""
    sql_agent.instructions = INSTRUCTIONS + (TABLE_STYLE if table else DESCRIPTIVE_STYLE)
