import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from talktodb.src.core.db.connectors.base import Schema

# HTML page with the interactive table/relationship graph, written on --connect.
SCHEMA_GRAPH_PATH = "talktodb_schema.html"

TEMPLATE_PATH = Path(__file__).with_name("schema_graph.html")


def mask_password(db_url: str) -> str:
    """Replace the password in a database URL with ***."""
    parts = urlsplit(db_url)
    if not parts.password:
        return db_url
    netloc = parts.netloc.replace(f":{parts.password}@", ":***@", 1)
    return parts._replace(netloc=netloc).geturl()


def build_graph(schema: Schema) -> dict:
    """Turn the saved schema into tables (nodes) and foreign keys (edges)."""
    tables = [
        {"name": table, "columns": [{"name": name, **info} for name, info in columns.items()]}
        for table, columns in sorted(schema.items())
    ]
    relationships = []
    for table, columns in sorted(schema.items()):
        for name, info in columns.items():
            if not info["foreign_key"]:
                continue
            # "users.id" or "sales.orders.id": the column is after the last dot.
            to_table, _, to_column = info["foreign_key"].rpartition(".")
            if to_table not in schema:
                continue
            relationships.append(
                {
                    "from_table": table,
                    "from_column": name,
                    "to_table": to_table,
                    "to_column": to_column,
                    # A unique (or primary key) FK column means each row matches at most one.
                    "one_to_one": info["unique"] or info["primary_key"],
                }
            )
    return {"tables": tables, "relationships": relationships}


def render_html(db_url: str, schema: Schema) -> str:
    data = {
        "database": mask_password(db_url),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        **build_graph(schema),
    }
    # "</" would end the <script> block early if a name contained "</script>".
    payload = json.dumps(data).replace("</", "<\\/")
    return TEMPLATE_PATH.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)


def write_schema_graph(db_url: str, schema: Schema) -> Path:
    """Write the graph page and return its absolute path."""
    path = Path(SCHEMA_GRAPH_PATH).resolve()
    path.write_text(render_html(db_url, schema), encoding="utf-8")
    return path
