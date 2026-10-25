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
   └─ embed one chunk per table (ChromaDB)    ├─ the agent writes SQL and calls run_query
                                              └─ it fixes errors, retries and answers
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
  There are two users: ...
```

Keep asking questions. The agent decides which tools to call, retries when a query fails, and remembers the last 5 turns, so follow-ups such
as "now show their emails" work. Type `exit`, `quit` or `q` (or press Ctrl-C) to leave.

### 3. Disconnect

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
| `chroma_db/` | ChromaDB folder with the embedded schema chunks. |
| `.env` | Your settings and secrets. Do not commit it. |

All three are in `.gitignore`.

## Project layout

```
main.py                              CLI (--connect, --disconnect, chat)
talktodb/src/core/
  agent/sql_agent.py                 Agno agent with search_schema and run_query tools
  artifacts/settings.py              Settings loaded from .env
  db/core/                           talktodb_state.json: saved connections and their schemas
  db/connectors/                     the database you connect to, one connector per engine
    base.py                          BaseConnector interface, read-only SELECT check
    postgres.py                      PostgreSQL (psycopg)
    mysql.py                         MySQL / MariaDB (PyMySQL)
  db/vector/                         ChromaDB schema embeddings
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
