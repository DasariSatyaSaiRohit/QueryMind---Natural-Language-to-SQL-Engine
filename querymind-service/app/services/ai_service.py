"""
AI SQL generation service.

Primary:  Ollama (local, free, no API key).
Fallback: Hugging Face Inference API (free tier).
"""
import hashlib
import json
import re
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.db.redis import redis_get, redis_set

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are an expert SQL assistant. Given the schema context and the user question, generate a
single valid SELECT SQL query. Reply ONLY with a JSON object matching this structure (no markdown):
{
  "sql_query": "<SQL>",
  "rationale": "<why this query>",
  "explanation": "<plain English>",
  "tables_used": ["table1", ...],
  "chain_of_thought": ["step1", "step2", ...]
}
Rules:
- Generate SELECT queries ONLY.
- Do not use INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER/CREATE.
- Use proper table and column names from the schema.
- Add LIMIT 1000 unless the user specifies a limit.
"""


def _cache_key(question: str, session_id: str) -> str:
    digest = hashlib.sha256(f"{session_id}:{question}".encode()).hexdigest()
    return f"query_cache:{digest}"


def _build_user_prompt(question: str, schema_context: str, history: list[dict]) -> str:
    history_text = ""
    if history:
        history_text = "\nConversation history:\n"
        for h in history[-5:]:  # last 5 turns only
            history_text += f"User: {h.get('user_input', '')}\nSQL: {h.get('sql_query', '')}\n"

    return (
        f"{schema_context}\n{history_text}\nUser question: {question}\n\n"
        "Respond ONLY with the JSON object as specified."
    )


async def _call_ollama(user_prompt: str) -> dict[str, Any]:
    try:
        payload = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(settings.OLLAMA_URL, json=payload)
            
            # Handle HTTP errors with response body
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error("ollama_http_error", 
                           status_code=e.response.status_code,
                           error_body=e.response.text)
                raise
            
            # Parse JSON safely
            try:
                response_data = resp.json()
            except ValueError as json_error:
                logger.error("ollama_invalid_json", error=str(json_error))
                raise ValueError(f"Invalid JSON response from Ollama: {json_error}")
            
            # Get content (handle both chat and generate endpoints)
            content = response_data.get("message", {}).get("content", "")
            
            if not content:
                # Try generate endpoint format
                content = response_data.get("response", "")
            
            if not content:
                logger.error("ollama_empty_content", response=response_data)
                raise ValueError("Ollama returned empty content")
            
            return _parse_ai_response(content)
            
    except Exception as e:
        logger.error("ollama_call_failed", error=str(e))
        raise

async def _call_huggingface(user_prompt: str) -> dict[str, Any]:
    try:
        if not settings.HF_API_KEY:
            raise RuntimeError("HF_API_KEY not configured")

        # Use model ID in URL
        api_url = f"{settings.HF_MODEL_URL}/{settings.HF_MODEL_ID}"
        
        headers = {
            "Authorization": f"Bearer {settings.HF_API_KEY}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "inputs": f"{_SYSTEM_PROMPT}\n\n{user_prompt}",
            "parameters": {
                "max_new_tokens": 1024,
                "temperature": 0.7,
                "do_sample": True,
                "return_full_text": False,
            }
        }

        async with httpx.AsyncClient(timeout=100) as client:
            resp = await client.get("https://api-inference.huggingface.co")
            resp.raise_for_status()
            
            result = resp.json()
            
            # Handle both list and dict responses
            if isinstance(result, list) and len(result) > 0:
                content = result[0].get("generated_text", "")
            elif isinstance(result, dict):
                content = result.get("generated_text", "")
            else:
                content = str(result)
            
            if not content:
                raise ValueError("Hugging Face returned empty content")
                
            return _parse_ai_response(content)
    except Exception as e:
        print(f"Hugging Face API call failed: {e}")
        raise

def _parse_ai_response(raw: str) -> dict[str, Any]:
    """Extract JSON from AI response, tolerating markdown fences."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    # Find first { ... } block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Last-resort: return a structure with raw text as sql
    return {
        "sql_query": cleaned,
        "rationale": "Could not parse structured response",
        "explanation": "Raw model output used",
        "tables_used": [],
        "chain_of_thought": [],
    }

async def _call_gemini(user_prompt: str) -> dict[str, Any]:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not configured")
    
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent"
    
    headers = {
        "Content-Type": "application/json",
    }
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{_SYSTEM_PROMPT}\n\n{user_prompt}"}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024,
        }
    }
    
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            api_url,
            headers=headers,
            json=payload,
            params={"key": settings.GEMINI_API_KEY}
        )
        resp.raise_for_status()
        result = resp.json()
        
        content = result["candidates"][0]["content"]["parts"][0]["text"]
        
        if not content:
            raise ValueError("Gemini returned empty content")
        
        return _parse_ai_response(content)

async def generate_sql(
    question: str,
    session_id: str,
    schema_context: str,
    conversation_history: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Generate SQL for a natural-language question.
    Checks cache first, then tries Ollama → HuggingFace.
    """
    try:
        cache_key = _cache_key(question, session_id)
        cached = await redis_get(cache_key)
        if cached:
            logger.info("ai.cache_hit", session_id=session_id)
            return {**cached, "cache_hit": True}

        user_prompt = _build_user_prompt(question, schema_context, conversation_history or [])

        result: dict[str, Any] | None = None
        error: Exception | None = None

        try:
            result = await _call_gemini(user_prompt)
            logger.info("ai.gemini_success", session_id=session_id)
        except Exception as e:
            error = e
            logger.warning("ai.gemini_failed", error=str(e))

        if result is None:
            try:
                result = await _call_huggingface(user_prompt)
                logger.info("ai.hf_success", session_id=session_id)
            except Exception as e:
                logger.error("ai.hf_failed", error=str(e))
                raise RuntimeError(f"All AI providers failed. Last error: {e}") from e

        result["cache_hit"] = False
        await redis_set(cache_key, result, ttl=settings.QUERY_CACHE_TTL)
        return result
    except Exception as err:
        print(err)
        return {}
    

async def warmup_ollama() -> None:
    """Send a trivial prompt to Ollama at startup to pre-load the model."""
    if not settings.WARMUP_MODEL_ON_STARTUP:
        return
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(
                settings.OLLAMA_URL,
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [{"role": "user", "content": "SELECT 1"}],
                    "stream": False,
                },
            )
        logger.info("ai.ollama_warmup_complete")
    except Exception as e:
        logger.warning("ai.ollama_warmup_failed", error=str(e))
