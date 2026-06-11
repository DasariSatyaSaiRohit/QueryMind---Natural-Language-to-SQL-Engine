"""
Query endpoints.

POST /query/ask            – Generate + execute SQL (non-blocking history via RabbitMQ).
POST /query/schema/refresh – Force schema re-introspection for a session.
GET  /query/history/{session_id} – Retrieve query history for a session.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import decrypt
from app.db.session import get_db
from app.db.redis import redis_get
from app.models.query_history import QueryHistory
from app.schemas.query import QueryAskRequest, SchemaIntrospectRequest
from app.services.ai_service import generate_sql
from app.services.query_service import validate_sql, execute_query
from app.services.schema_service import (
    get_cached_schema,
    introspect_and_cache,
    build_rag_schema_context,
)
from app.services.connection_service import get_connection_by_id, get_decrypted_connection_string
from app.workers.rabbitmq_client import rabbitmq_client

router = APIRouter(prefix="/query", tags=["query"])
logger = get_logger(__name__)

_SESSION_CONN_KEY = "session:{session_id}"
_SESSION_HISTORY_KEY = "session:{session_id}:history"

@router.post("/ask")
async def ask_query(
    body: QueryAskRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        request_id = getattr(request.state, "request_id", None)

        # 1. Resolve connection string for this session
        connection_string = await _get_connection_string_for_session(body.session_id, db)

        # 2. Get (or build) schema from cache
        schema = await get_cached_schema(body.session_id)
        if schema is None:
            logger.info("query.schema_miss", session_id=body.session_id)
            schema = await introspect_and_cache(body.session_id, connection_string)

        # 3. Build RAG context
        schema_context = build_rag_schema_context(schema, body.question)

        # 4. Fetch recent conversation history from Redis
        history_key = _SESSION_HISTORY_KEY.format(session_id=body.session_id)
        raw_history = await redis_get(history_key) or []

        # 5. Generate SQL via AI (Ollama → HuggingFace)
        generation = await generate_sql(
            question=body.question,
            session_id=body.session_id,
            schema_context=schema_context,
            conversation_history=raw_history,
        )
        sql = generation.get("sql_query", "")
        sql = sql.strip().rstrip(';')
        if not sql:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI provider returned an empty SQL query.",
            )

        # 6. Validate SQL
        validation = validate_sql(sql, schema)
        if not validation["passed"]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Generated SQL failed validation.",
                    "validation_info": validation,
                    "sql": sql,
                },
            )
        # 7. Execute query with pagination
        execution = await execute_query(
            connection_string=connection_string,
            sql=sql,
            page=body.page,
            page_size=body.page_size,
        )

        # 8. Build response payload (DO NOT include raw rows in the DB history)
        response_data = {
            "question": body.question,
            "sql": sql,
            "rationale": generation.get("rationale", ""),
            "explanation": generation.get("explanation", ""),
            "tables_used": generation.get("tables_used", []),
            "chain_of_thought": generation.get("chain_of_thought", []),
            "columns": execution["columns"],
            "rows": execution["rows"],
            "row_count": execution["row_count"],
            "execution_time_ms": execution["execution_time_ms"],
            "pagination": execution["pagination"],
            "truncated": execution["truncated"],
            "truncation_warning": execution.get("truncation_warning"),
            "validation_info": validation,
            "cache_hit": generation.get("cache_hit", False),
        }

        # 9. Publish to RabbitMQ (non-blocking) – metadata only, no rows
        history_record = {
            "user_input": body.question,
            "sql_query": sql,
            "chain_of_thought": generation.get("chain_of_thought", []),
            "execution_time_ms": execution["execution_time_ms"],
            "cache_hit": generation.get("cache_hit", False),
            "correlation_id": request_id,
        }
        await rabbitmq_client.publish_history(
            session_id=body.session_id,
            record=history_record,
            correlation_id=request_id,
        )

        return {
            "success": True,
            "data": response_data,
            "correlation_id": request_id,
            "history_persisted": "async",
        }
    except Exception as e:
        print("Error in /query/ask:", str(e))
        return {
            "success": False,
            "error": str(e),}
        

async def _get_connection_string_for_session(
    session_id: str, db: AsyncSession
) -> str:
    """
    Resolve connection string for a session.
    Checks Redis cache first (key: session:{session_id}:conn),
    then falls back to DB lookup by connection_id stored in session metadata.
    """
    cache_key = _SESSION_CONN_KEY.format(session_id=session_id)
    cached = await redis_get(cache_key)
    if cached['connection_string']:
        # Stored encrypted; decrypt before use
        try:
            return decrypt(cached['connection_string'])
        except Exception:
            return cached['connection_string']  # already plaintext (dev mode)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No active session found for session_id={session_id}. "
               "Please establish a session first.",
    )

@router.post("/schema/refresh")
async def refresh_schema(
    body: SchemaIntrospectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    request_id = getattr(request.state, "request_id", None)
    connection_string = await _get_connection_string_for_session(body.session_id, db)

    schema = await introspect_and_cache(
        session_id=body.session_id,
        connection_string=connection_string,
        force_refresh=True,
    )
    return {
        "success": True,
        "data": {
            "tables": list(schema.keys()),
            "table_count": len(schema),
        },
        "correlation_id": request_id,
    }


@router.get("/history/{session_id}")
async def get_history(
    session_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(QueryHistory)
        .where(QueryHistory.session_id == session_id)
        .order_by(QueryHistory.created_at.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    return {
        "success": True,
        "data": [
            {
                "history_id": r.history_id,
                "user_input": r.user_input,
                "sql_query": r.sql_query,
                "execution_time_ms": r.execution_time_ms,
                "cache_hit": r.cache_hit,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
        "total": len(records),
    }
