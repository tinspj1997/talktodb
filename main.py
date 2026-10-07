import click
import typer
from sqlalchemy.exc import SQLAlchemyError

from talktodb.src.core.agent.sql_agent import sql_agent
from talktodb.src.core.artifacts.settings import settings
from talktodb.src.core.db.core.repository.connection import ConnectionRepository
from talktodb.src.core.db.core.repository.schema import SchemaRepository
from talktodb.src.core.db.target.repository.schema import TargetSchemaRepository
from talktodb.src.core.db.vector.repository.schema import SchemaVectorRepository

app = typer.Typer(help="talktodb CLI")


def connect() -> None:
    """Connect to the database, save the status and the schema."""
    target = TargetSchemaRepository()

    typer.secho("Connecting to database...", fg=typer.colors.YELLOW)
    try:
        target.check_connection()
    except SQLAlchemyError as exc:
        raise click.ClickException(f"Database connection failed: {exc}") from exc
    typer.secho("Database connected successfully.", fg=typer.colors.GREEN)

    ConnectionRepository().set_connected(settings.DATABASE_URL, True)
    typer.secho("Connection status saved.", fg=typer.colors.GREEN)

    schema = target.fetch_schema()
    SchemaRepository().save(settings.DATABASE_URL, schema)
    typer.secho(f"Schema saved ({len(schema)} tables).", fg=typer.colors.GREEN)

    typer.secho("Creating vector embeddings (first run downloads the model)...", fg=typer.colors.YELLOW)
    connection = ConnectionRepository().get_by_url(settings.DATABASE_URL)
    SchemaVectorRepository().save(connection["id"], schema)
    typer.secho(f"Vector data saved ({len(schema)} chunks).", fg=typer.colors.GREEN)


def disconnect() -> None:
    """Remove the saved connection and its schema records."""
    connection = ConnectionRepository().get_by_url(settings.DATABASE_URL)
    if connection:
        SchemaVectorRepository().delete(connection["id"])
    if ConnectionRepository().delete(settings.DATABASE_URL):
        typer.secho("Disconnected. Connection and schema records removed.", fg=typer.colors.GREEN)
    else:
        typer.secho("No saved connection found.", fg=typer.colors.YELLOW)


def chat() -> None:
    """Continuous chat with the SQL agent (type 'exit' to quit)."""
    connection = ConnectionRepository().get_by_url(settings.DATABASE_URL)
    if not connection or not connection["schema_created"]:
        raise click.ClickException("No schema found. Run with --connect first.")

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
        raise click.UsageError("Use either --connect or --disconnect, not both.")
    if disconnect_db:
        disconnect()
        return
    if connect_db:
        connect()
        return

    chat()


if __name__ == "__main__":
    app()
