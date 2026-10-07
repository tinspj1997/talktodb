from agno.agent import Agent
from agno.models.openai import OpenAIChat

from talktodb.src.core.artifacts.settings import settings

INSTRUCTIONS = [
    "Write one PostgreSQL query that answers the user's question using ONLY the "
    "tables and columns described in the schema chunks.",
    "Return only the SQL query, with no explanation and no markdown fences.",
    "Write read-only queries (SELECT). Never write INSERT, UPDATE, DELETE, DROP or DDL.",
    "Use foreign keys listed in the chunks to join tables.",
    "Always give your best-effort query using the closest matching tables, even if the "
    "question's wording does not match the table names exactly (for example 'documents' "
    "may mean a files or resources table).",
    "Return exactly CANNOT_ANSWER only if none of the chunks relate to the question.",
]


class SqlAgent:
    """Agno agent that turns a question plus schema chunks into a SQL query."""

    def __init__(self) -> None:
        self.agent = Agent(
            name="SQL Agent",
            model=OpenAIChat(
                id=settings.LLM_MODEL_NAME,
                api_key=settings.LLM_MODEL_API_KEY,
                base_url=settings.LLM_BASE_URL,
                temperature=0,
            ),
            description="PostgreSQL expert that writes SQL from schema chunks.",
            instructions=INSTRUCTIONS,
        )

    def generate_sql(self, question: str, chunks: list[dict]) -> str:
        schema = "\n\n".join(item["chunk"] for item in chunks)
        response = self.agent.run(f"Schema chunks:\n{schema}\n\nQuestion: {question}")
        return response.content
