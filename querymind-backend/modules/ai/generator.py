"""
modules/ai/generator.py
Claude API integration.
Synchronous generate_sql_sync + async wrapper + async streaming.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from typing import Awaitable, Callable

import anthropic

from core.config import get_settings
from core.exceptions import SQLValidationError
from modules.ai.prompt_builder import build_system_prompt, build_user_message
from modules.ai.safety import run_validation

logger = logging.getLogger(__name__)


def make_cache_key(session_id: str, question: str) -> str:
    """SHA256 of '{session_id}:{question.strip().lower()}'"""
    raw = f"{session_id}:{question.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def parse_claude_response(content: str) -> dict:
    """
    Parse JSON from Claude response.
    Strip markdown code fences if present (```json ... ```).
    Raise ValueError if JSON is invalid or sql field is empty.
    """
    # Strip markdown fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned non-JSON response: {exc}") from exc

    sql = parsed.get("sql", "").strip()
    if not sql:
        raise ValueError("Claude response missing or empty 'sql' field.")

    return parsed


def _get_anthropic_client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def generate_sql_sync(question: str, schema: dict) -> dict:
    """
    Synchronous Claude call. Called via run_in_executor from generate_sql().

    Steps:
      1. build_system_prompt(schema) + build_user_message(question)
      2. client.messages.create(model, max_tokens, system, messages)
      3. parse_claude_response(response.content[0].text)
      4. run_validation(sql, question, schema)
      5. If validation fails: raise SQLValidationError
      6. Return GenerationResult dict
    """
    settings = get_settings()
    client = _get_anthropic_client()

    system_prompt = build_system_prompt(schema)
    user_message = build_user_message(question)

    start = time.monotonic()
    response = client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=settings.CLAUDE_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    raw_text = response.content[0].text
    tokens_used = response.usage.input_tokens + response.usage.output_tokens

    try:
        parsed = parse_claude_response(raw_text)
    except ValueError as exc:
        raise SQLValidationError(str(exc)) from exc

    sql = parsed["sql"]
    validation = run_validation(sql, question, schema)

    if not validation["passed"]:
        logger.warning(
            "SQL validation failed: pass=%s reason=%s",
            validation["failed_pass"],
            validation["reason"],
        )
        raise SQLValidationError(
            validation["reason"] or "SQL validation failed."
        )

    return {
        "sql": sql,
        "rationale": parsed.get("rationale", ""),
        "explanation": parsed.get("explanation", ""),
        "tables_used": parsed.get("tables_used", []),
        "tokens_used": tokens_used,
        "latency_ms": latency_ms,
        "validation": validation,
    }


async def generate_sql(question: str, schema: dict) -> dict:
    """Async wrapper — runs generate_sql_sync in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, generate_sql_sync, question, schema)


async def stream_sql_tokens(
    question: str,
    schema: dict,
    on_token: Callable[[str], Awaitable[None]],
    on_complete: Callable[[dict], Awaitable[None]],
    on_error: Callable[[str], Awaitable[None]],
) -> None:
    """
    Stream SQL generation from Claude.

    Steps:
      1. Build prompt (synchronous — fast, no executor needed).
      2. Open client.messages.stream() in a thread via run_in_executor.
         For each text chunk: call await on_token(chunk).
      3. After stream completes: parse full text, run validation.
      4. If validation passes: call await on_complete(result_dict).
      5. If validation fails or any exception: call await on_error(reason).

    Retries up to 2 times on anthropic.RateLimitError with exponential backoff.
    """
    settings = get_settings()
    system_prompt = build_system_prompt(schema)
    user_message = build_user_message(question)

    max_retries = 2
    attempt = 0

    while attempt <= max_retries:
        try:
            full_text = ""
            start = time.monotonic()
            tokens_used = 0

            client = _get_anthropic_client()

            # Run stream in executor so we don't block the event loop
            loop = asyncio.get_event_loop()

            # Collect chunks via a thread-safe queue
            chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()

            def _stream_worker() -> tuple[str, int]:
                """Run in thread pool. Puts chunks onto async queue."""
                nonlocal tokens_used
                collected = ""
                with client.messages.stream(
                    model=settings.CLAUDE_MODEL,
                    max_tokens=settings.CLAUDE_MAX_TOKENS,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                ) as stream:
                    for chunk in stream.text_stream:
                        collected += chunk
                        # Thread-safe put into asyncio queue
                        loop.call_soon_threadsafe(chunk_queue.put_nowait, chunk)

                    final_msg = stream.get_final_message()
                    tokens_used = (
                        final_msg.usage.input_tokens + final_msg.usage.output_tokens
                    )

                loop.call_soon_threadsafe(chunk_queue.put_nowait, None)  # sentinel
                return collected, tokens_used

            # Run streamer in thread
            stream_future = loop.run_in_executor(None, _stream_worker)

            # Consume chunks as they arrive
            while True:
                chunk = await chunk_queue.get()
                if chunk is None:
                    break
                full_text += chunk
                try:
                    await on_token(chunk)
                except Exception:  # noqa: BLE001
                    # Client disconnected — cancel streaming thread and exit
                    logger.warning("stream_sql_tokens: on_token raised; client disconnected")
                    return

            # Await thread completion to get final token count
            _, tokens_used = await stream_future
            latency_ms = int((time.monotonic() - start) * 1000)

            # Parse and validate
            try:
                parsed = parse_claude_response(full_text)
            except ValueError as exc:
                await on_error(str(exc))
                return

            sql = parsed["sql"]
            validation = run_validation(sql, question, schema)

            if not validation["passed"]:
                await on_error(
                    validation["reason"] or "SQL validation failed."
                )
                return

            result_dict = {
                "sql": sql,
                "rationale": parsed.get("rationale", ""),
                "explanation": parsed.get("explanation", ""),
                "tables_used": parsed.get("tables_used", []),
                "tokens_used": tokens_used,
                "latency_ms": latency_ms,
                "validation": validation,
            }

            await on_complete(result_dict)
            return  # Success

        except anthropic.RateLimitError:
            attempt += 1
            if attempt > max_retries:
                logger.error("Claude rate limit exhausted after %d retries", max_retries)
                await on_error("claude_rate_limited")
                return
            backoff = 2 ** (attempt - 1)  # 1s, 2s
            logger.warning(
                "Claude rate limited, retry %d/%d in %ds", attempt, max_retries, backoff
            )
            await asyncio.sleep(backoff)

        except Exception as exc:  # noqa: BLE001
            logger.exception("stream_sql_tokens unexpected error: %s", exc)
            await on_error(str(exc))
            return
