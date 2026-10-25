# talktodb

Talk to your PostgreSQL or MySQL database in plain English. talktodb reads your database
schema, finds the tables that matter for your question, asks an LLM to write the
SQL, runs it (read-only) and shows you the rows.

## How it works

```
--connect                                   chat
   │                                          │
   ├─ check the database connection           ├─ you ask a question
   ├─ read tables, columns, keys              ├─ find the closest schema chunks (ChromaDB)
   ├─ save them in talktodb_state.json        ├─ the agent calls search_schema (ChromaDB)
   ├─ embed one chunk per table (ChromaDB)    ├─ the agent writes SQL and calls run_query
   └─ write the schema graph page             └─ it fixes errors, retries and answers
```

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A PostgreSQL or MySQL/MariaDB database you can reach
- An OpenAI-compatible API key

## Setup

```bash
uv sync
cp .env.example .env     # then edit .env
```

Fill in `.env`:

| Variable | Description |
|---|---|
| `DATABASE_URL` | Database URL; the scheme picks the connector: `postgresql://user:pass@host:5432/db` or `mysql://user:pass@host:3306/db` |
| `LLM_BASE_URL` | LLM API base URL (default `https://api.openai.com/v1`) |
| `LLM_MODEL_API_KEY` | API key for the LLM |
| `LLM_MODEL_NAME` | Model name, e.g. `gpt-4o-mini-2024-07-18` |

Run every command from the project root, because `.env` is read from the current directory.

## Commands

| Command | What it does | When to use it | Example |
|---|---|---|---|
| `uv run main.py --connect` | Checks the database connection, saves the schema to `talktodb_state.json`, builds the embeddings and writes the schema graph page. | Once at the start, and again whenever the database schema changes. | `uv run main.py --connect` |
| `uv run main.py` | Starts the chat. Answers start with the SQL that was run, then explain the result in plain sentences. | To ask questions about your data. | `uv run main.py`<br>`User : which organization has the most users?` |
| `uv run main.py --table` | Starts the chat with table answers: the SQL, a one-sentence answer, then the rows as a markdown table. | When you want to see the rows themselves instead of a description. | `uv run main.py --table`<br>`User : list the latest 10 tickets` |
| `uv run main.py --show` | Rebuilds the schema graph page from the saved schema and opens it in your browser. | To explore the tables and how they are related. | `uv run main.py --show` |
| `uv run main.py --disconnect` | Removes the saved connection, its schema and its embeddings. The database itself is not touched. | To forget a database, or to start again from a clean state. | `uv run main.py --disconnect` |
| `uv run main.py --help` | Lists all options. | To check what options are available. | `uv run main.py --help` |

`--connect`, `--disconnect` and `--show` can't be combined; use one at a time. `--table` only applies to the chat.
In the chat, type `exit`, `quit` or `q` (or press Ctrl-C) to leave.

## Usage

### 1. Connect (once, and again whenever the schema changes)

```bash
uv run main.py --connect
```

This checks the connection, saves the schema and builds the embeddings. The first
run downloads a small embedding model (about 80 MB).

### 2. Chat

```bash
uv run main.py
```

```
User : how many users are there and what are their emails
Tool Calls
  • search_schema(query=users)
  • run_query(sql=SELECT ... FROM users ...)
Response
  ```sql
  SELECT email FROM users;
  ```
  There are two users: alice@example.com and bob@example.com.
```

Keep asking questions. The agent decides which tools to call, retries when a query fails, and remembers the last 5 turns, so follow-ups such
as "now show their emails" work. Type `exit`, `quit` or `q` (or press Ctrl-C) to leave.

Answers are written as descriptive text. To get the rows as a markdown table instead, start the chat with `--table`:

```bash
uv run main.py --table
```

### 3. See the tables and relationships

```bash
uv run main.py --show
```

Opens `talktodb_schema.html` in your browser: an interactive graph with one dot
per table and a line for every foreign key (dashed when it is one-to-one). The more
links a table has, the bigger its dot; colors group tables that are closely linked.

- Click a table, or search for it in the sidebar, to highlight it and its
  neighbours and list its columns (with PK / FK / UQ markers), what it references
  and what references it.
- Click a cluster in the sidebar legend to hide or show it.
- Drag tables to move them, scroll to zoom, **Fit** to see everything.
- **Tree layout** lines tables up by dependency; **Force layout** goes back.

The page is rebuilt from `talktodb_state.json` each time, so it needs no
database connection, and it shows your database URL with the password masked.
It loads the graph library from unpkg.com, so it needs internet access; offline
it still lists the tables.

### 4. Disconnect

```bash
uv run main.py --disconnect
```

Removes the saved connection, its schema and its embeddings. Your
database is not touched.

## Safety

- Only a single `SELECT` / `WITH` query is executed.
- Queries run inside a read-only transaction, so the database rejects writes.
- At most 100 rows are returned.

## Local files

| Path | Purpose |
|---|---|
| `talktodb_state.json` | JSON file with the app's state: each saved connection (keyed by database URL) with its id and the schema read on `--connect`. Open it to see exactly what was read. It includes your database URL, password included, in plain text. |
| `talktodb_schema.html` | The schema graph page written by `--connect` and `--show`. |
| `chroma_db/` | ChromaDB folder with the embedded schema chunks. |
| `.env` | Your settings and secrets. Do not commit it. |

All of these are in `.gitignore`.

## Project layout

```
main.py                              CLI (--connect, --disconnect, --show, chat, --table)
talktodb/src/core/
  agent/sql_agent.py                 Agno agent with search_schema and run_query tools
  artifacts/settings.py              Settings loaded from .env
  db/core/                           talktodb_state.json: saved connections and their schemas
  db/connectors/                     the database you connect to, one connector per engine
    base.py                          BaseConnector interface, read-only SELECT check
    postgres.py                      PostgreSQL (psycopg)
    mysql.py                         MySQL / MariaDB (PyMySQL)
  db/vector/                         ChromaDB schema embeddings
  graph/                             schema graph page (--show): schema_graph.py + HTML template
```

## Adding a database

1. Write a `BaseConnector` subclass in `talktodb/src/core/db/connectors/` that
   implements `check_connection`, `fetch_schema` and `execute_query`, sets
   `dialect`, and raises `ConnectorError` instead of driver exceptions.
2. Register its URL schemes in `CONNECTORS` in `connectors/__init__.py`.

## Troubleshooting

- **The agent can't find the right table**: use the table and column wording from your schema, or ask more specifically.
- **`No schema found. Run with --connect first.`**: run `uv run main.py --connect`.
- **Schema changed in the database**: run `--connect` again to refresh it.
