"""
modules/ai/prompt_builder.py
Builds the Claude system prompt and user message.
"""
from __future__ import annotations

import json

SYSTEM_PROMPT_TEMPLATE = """
You are an expert SQL query generator. Your task is to convert a natural
language question into a valid, safe, read-only PostgreSQL SQL query.

<schema>
{schema_json}
</schema>

## Instructions — follow these steps in order (Chain-of-Thought):

Step 1 — Identify relevant tables
List the tables from the schema relevant to the question. Explain why each is needed.

Step 2 — Reason about relationships
Identify JOIN conditions. Use foreign key relationships from the schema.

Step 3 — Write the SQL
Rules:
- Only SELECT statements. Never INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, GRANT, REVOKE.
- Only reference tables and columns that exist in the provided schema.
- Use explicit column names, not SELECT *.
- Use table aliases for readability.
- Add LIMIT 100 unless the user explicitly asks for all rows.
- Use appropriate GROUP BY, ORDER BY as needed.

Step 4 — Explain the query
Plain-English explanation of what the query does and what results to expect.

## Output format
Respond ONLY with a valid JSON object — no markdown, no code fences:
{{
  "sql": "<complete SQL query>",
  "rationale": "<step-by-step reasoning from steps 1–2>",
  "explanation": "<plain English from step 4>",
  "tables_used": ["<table1>", "<table2>"]
}}
"""


def build_system_prompt(schema: dict) -> str:
    """Inject schema JSON into the template."""
    schema_json = json.dumps(schema, indent=2, default=str)
    return SYSTEM_PROMPT_TEMPLATE.format(schema_json=schema_json)


def build_user_message(question: str) -> str:
    """Return: 'Question: {question}'"""
    return f"Question: {question}"
