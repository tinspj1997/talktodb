import click
import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.exc import SQLAlchemyError

from talktodb.src.core.agent.sql_agent import SqlAgent
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


def print_rows(rows: list[dict]) -> None:
    """Print query results as a table."""
    if not rows:
        typer.secho("No rows returned.", fg=typer.colors.YELLOW)
        return
    table = Table(*rows[0].keys())
    for row in rows:
        table.add_row(*(str(value) for value in row.values()))
    Console().print(table)
    typer.secho(f"{len(rows)} row(s) returned.", fg=typer.colors.GREEN)


def ask(question: str, agent: SqlAgent) -> None:
    """Fetch the schema chunks closest to the question and list them."""
    connection = ConnectionRepository().get_by_url(settings.DATABASE_URL)
    if not connection or not connection["schema_created"]:
        raise click.ClickException("No schema found. Run with --connect first.")

    chunks = SchemaVectorRepository().search(connection["id"], question)
    typer.secho(f"Top {len(chunks)} matching chunks:", fg=typer.colors.CYAN)
    for rank, item in enumerate(chunks, start=1):
        typer.secho(
            f"\n[{rank}] {item['table_name']} (distance: {item['distance']:.3f})",
            fg=typer.colors.YELLOW,
        )
        typer.echo(item["chunk"])

    typer.secho("\nGenerating SQL query...", fg=typer.colors.YELLOW)
    sql = agent.generate_sql(question, chunks)
    typer.secho("Generated SQL:", fg=typer.colors.GREEN)
    typer.echo(sql)

    if sql.strip() == "CANNOT_ANSWER":
        return

    typer.secho("\nExecuting query...", fg=typer.colors.YELLOW)
    try:
        rows = TargetSchemaRepository().execute_query(sql)
    except (ValueError, SQLAlchemyError) as exc:
        raise click.ClickException(f"Query failed: {exc}") from exc
    print_rows(rows)


EXIT_WORDS = {"exit", "quit", "q"}


def chat() -> None:
    """Continuous chat: keep answering questions until the user exits."""
    agent = SqlAgent()  # one agent for the whole chat so it remembers earlier turns
    typer.secho("Type 'exit' to quit.", fg=typer.colors.BRIGHT_BLACK)
    while True:
        try:
            question = typer.prompt("\nHow can I help you?").strip()
        except (click.Abort, EOFError):  # Ctrl-C / Ctrl-D
            break
        if not question:
            continue
        if question.lower() in EXIT_WORDS:
            break
        try:
            ask(question, agent)
        except click.ClickException as exc:
            typer.secho(f"Error: {exc.message}", fg=typer.colors.RED)
    typer.secho("Goodbye!", fg=typer.colors.CYAN)


@app.command()
def main(
    connect_db: bool = typer.Option(
        False, "--connect", help="Connect to the database and sync its schema."
    ),
    disconnect_db: bool = typer.Option(
        False, "--disconnect", help="Remove the saved connection and its schema."
    ),
) -> None:
    """Run with --connect / --disconnect, else ask what to do."""
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
