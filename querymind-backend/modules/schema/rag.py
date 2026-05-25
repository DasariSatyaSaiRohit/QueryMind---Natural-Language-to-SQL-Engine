"""
modules/schema/rag.py
RAG relevance scoring — selects which tables to inject into the AI prompt.
Pure Python, no async needed.
"""
from __future__ import annotations

import logging
import math
import re

logger = logging.getLogger(__name__)

STOPWORDS: frozenset[str] = frozenset(
    {"the", "a", "an", "of", "to", "in", "for", "on", "with", "by", "from"}
)


def tokenise(text: str) -> set[str]:
    """Lowercase word tokens, strip common SQL stopwords."""
    return set(re.findall(r"[a-z0-9_]+", text.lower())) - STOPWORDS


def score_table(
    question_tokens: set[str],
    table_name: str,
    row_count: int,
) -> float:
    """
    Score relevance of a table to a question.

    Scoring:
      +3.0 per exact token match between question and table name
      +1.0 per partial substring match (question token is substring of table name)
      +0.1 * log10(max(row_count, 1)) size boost (larger tables rank higher on ties)

    Returns float score. Higher = more relevant.
    """
    table_tokens = tokenise(table_name)
    score: float = 0.0

    for token in question_tokens:
        if token in table_tokens:
            score += 3.0
        elif any(token in t for t in table_tokens):
            score += 1.0

    # Size boost
    score += 0.1 * math.log10(max(row_count, 1))

    return score


def select_relevant_tables(
    question: str,
    table_list: list[dict],  # [{table_name: str, row_count_estimate: int}]
    max_tables: int,
) -> tuple[list[str], dict[str, float]]:
    """
    Score all tables and return:
      - selected_tables: top max_tables table names
      - scores: { table_name: score } for all tables

    Fallback: if all scores are 0 (no keyword overlap at all),
    return the top max_tables tables by row_count_estimate.
    """
    question_tokens = tokenise(question)

    scores: dict[str, float] = {}
    for entry in table_list:
        name = entry["table_name"]
        row_count = entry.get("row_count_estimate", 0)
        scores[name] = score_table(question_tokens, name, row_count)

    all_zero = all(s == 0.0 for s in scores.values()) or not scores

    if all_zero:
        logger.info(
            "RAG: no keyword overlap for question=%r — falling back to size ranking",
            question[:80],
        )
        sorted_tables = sorted(
            table_list,
            key=lambda e: e.get("row_count_estimate", 0),
            reverse=True,
        )
        selected = [e["table_name"] for e in sorted_tables[:max_tables]]
    else:
        sorted_tables_by_score = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        selected = [name for name, _ in sorted_tables_by_score[:max_tables]]

    return selected, scores
