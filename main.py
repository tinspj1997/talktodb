import click
import typer
from sqlalchemy.exc import SQLAlchemyError

from talktodb.src.core.artifacts.settings import settings
from talktodb.src.core.db.core.repository.connection import ConnectionRepository
from talktodb.src.core.db.core.repository.schema import SchemaRepository
from talktodb.src.core.db.target.repository.schema import TargetSchemaRepository

app = typer.Typer(help="talktodb CLI")


@app.command()
def main() -> None:
    """Connect to the database and report the status."""
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


if __name__ == "__main__":
    app()
