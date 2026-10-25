import typer

from talktodb.src.core.agent.sql_agent import sql_agent
from talktodb.src.core.artifacts.settings import settings
from talktodb.src.core.db.connectors import ConnectorError, get_connector
from talktodb.src.core.db.core.database import CORE_STATE_PATH, StateError
from talktodb.src.core.db.core.repository.connection import ConnectionRepository
from talktodb.src.core.db.vector.repository.schema import SchemaVectorRepository

app = typer.Typer(help="talktodb CLI")


def fail(message: str, code: int = 1) -> typer.Exit:
    """Print an error and return the Exit to raise. Typer bundles its own copy
    of Click, so exceptions from the `click` package would print as tracebacks."""
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    return typer.Exit(code)


def connect() -> None:
    """Connect to the database and save its schema and embeddings."""
    typer.secho("Connecting to database...", fg=typer.colors.YELLOW)
    try:
        target = get_connector(settings.DATABASE_URL)
        target.check_connection()
        schema = target.fetch_schema()
    except ConnectorError as exc:
        raise fail(f"Database connection failed: {exc}") from exc
    typer.secho("Database connected successfully.", fg=typer.colors.GREEN)

    connection = ConnectionRepository().save(settings.DATABASE_URL, schema)
    typer.secho(f"Schema saved to {CORE_STATE_PATH} ({len(schema)} tables).", fg=typer.colors.GREEN)

    typer.secho("Creating vector embeddings (first run downloads the model)...", fg=typer.colors.YELLOW)
    SchemaVectorRepository().save(connection["id"], schema)
    typer.secho(f"Vector data saved ({len(schema)} chunks).", fg=typer.colors.GREEN)


def disconnect() -> None:
    """Remove the saved connection, its schema and its embeddings."""
    connection = ConnectionRepository().get_by_url(settings.DATABASE_URL)
    if connection:
        SchemaVectorRepository().delete(connection["id"])
    if ConnectionRepository().delete(settings.DATABASE_URL):
        typer.secho("Disconnected. Connection, schema and embeddings removed.", fg=typer.colors.GREEN)
    else:
        typer.secho("No saved connection found.", fg=typer.colors.YELLOW)


def chat() -> None:
    """Continuous chat with the SQL agent (type 'exit' to quit)."""
    connection = ConnectionRepository().get_by_url(settings.DATABASE_URL)
    if not connection:
        raise fail("No schema found. Run with --connect first.")

    sql_agent.cli_app(stream=True, markdown=True, exit_on=["exit", "quit", "q"])


@app.command()
def main(
    connect_db: bool = typer.Option(
        False, "--connect", help="Connect to the database and sync its schema."
    ),
    disconnect_db: bool = typer.Option(
        False, "--disconnect", help="Remove the saved connection and its schema."
    ),
) -> None:
    """Run with --connect / --disconnect, else start the chat."""
    if connect_db and disconnect_db:
        raise fail("Use either --connect or --disconnect, not both.", code=2)
    try:
        if disconnect_db:
            disconnect()
        elif connect_db:
            connect()
        else:
            chat()
    except StateError as exc:
        raise fail(str(exc)) from exc


if __name__ == "__main__":
    app()
