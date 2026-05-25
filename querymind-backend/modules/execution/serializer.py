"""
modules/execution/serializer.py
Convert SQLAlchemy row results to JSON-safe Python types.
"""
from __future__ import annotations

import base64
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID


def serialise_value(value: Any) -> Any:
    """
    Convert a single value to a JSON-safe type.

    Conversions:
      datetime / date / time → ISO 8601 string
      Decimal               → float
      UUID                  → str
      bytes / bytearray     → base64-encoded string
      timedelta             → total_seconds() as float
      None                  → None
      Everything else       → str() as last resort if not natively serialisable
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, time):
        return value.isoformat()

    if isinstance(value, timedelta):
        return value.total_seconds()

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, UUID):
        return str(value)

    if isinstance(value, (bytes, bytearray)):
        return base64.b64encode(value).decode("ascii")

    # Native JSON-safe types — return as-is
    if isinstance(value, (int, float, bool, str)):
        return value

    # Lists and dicts (e.g. JSONB columns already parsed by psycopg2)
    if isinstance(value, (list, dict)):
        return value

    # Last resort: stringify
    return str(value)


def _infer_type(value: Any) -> str:
    """
    Infer a human-readable column type from a sample value.
    Used when SQLAlchemy cursor description is unavailable.
    """
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, Decimal):
        return "numeric"
    if isinstance(value, datetime):
        return "timestamp"
    if isinstance(value, date):
        return "date"
    if isinstance(value, time):
        return "time"
    if isinstance(value, timedelta):
        return "interval"
    if isinstance(value, UUID):
        return "uuid"
    if isinstance(value, (bytes, bytearray)):
        return "bytes"
    if isinstance(value, dict):
        return "json"
    if isinstance(value, list):
        return "array"
    return "text"


def serialise_rows(
    rows: list,
    column_names: list[str],
) -> tuple[list[dict], list[list]]:
    """
    Serialise a list of SQLAlchemy row objects into JSON-safe structures.

    Returns:
      columns : list of { name: str, type: str }
                type inferred from the first non-None value in each column
      rows    : list of lists — each inner list has serialised values in column order
    """
    if not rows:
        columns = [{"name": name, "type": "unknown"} for name in column_names]
        return columns, []

    # Serialise all rows first (needed for type inference too)
    serialised: list[list] = []
    for row in rows:
        row_values = list(row) if not isinstance(row, (list, tuple)) else list(row)
        serialised.append([serialise_value(v) for v in row_values])

    # Infer column types from first non-None value per column
    col_types: list[str] = ["unknown"] * len(column_names)
    for row in rows:
        row_values = list(row) if not isinstance(row, (list, tuple)) else list(row)
        for idx, value in enumerate(row_values):
            if value is not None and col_types[idx] == "unknown":
                col_types[idx] = _infer_type(value)
        if all(t != "unknown" for t in col_types):
            break

    columns = [
        {"name": name, "type": col_types[i]}
        for i, name in enumerate(column_names)
    ]

    return columns, serialised
