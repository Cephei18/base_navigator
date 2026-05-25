from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


def extract_json(text: str) -> Any:
    decoder = json.JSONDecoder()
    start_positions = [pos for pos in (text.find("{"), text.find("[")) if pos >= 0]
    if not start_positions:
        raise ValueError("No JSON object found in model response.")
    start = min(start_positions)
    value, _ = decoder.raw_decode(text[start:])
    return value


async def call_gemini_json(
    system_prompt: str,
    payload: Any,
    *,
    max_tokens: int = 1800,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    user_content = json.dumps(
        {
            "current_utc": datetime.now(UTC).isoformat(),
            "data": payload,
        },
        ensure_ascii=True,
        default=str,
    )
    model = settings.gemini_model.removeprefix("models/")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    request_body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_content}]}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    url,
                    headers={"x-goog-api-key": settings.gemini_api_key},
                    json=request_body,
                )
            response.raise_for_status()
            text = _gemini_text(response.json())
            parsed = extract_json(text)
            if not isinstance(parsed, dict):
                raise ValueError("Gemini returned JSON, but not an object.")
            return parsed
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {429, 500, 502, 503, 504} and attempt == 0:
                delay = 10 if status_code == 429 else 2
                logger.warning(
                    "Gemini synthesis retryable failure.",
                    extra={"status_code": status_code, "retry_delay_seconds": delay},
                )
                await asyncio.sleep(delay)
                continue
            logger.warning(
                "Gemini synthesis failed.",
                extra={"status_code": status_code, "error": f"{type(exc).__name__}: {exc}"},
            )
            raise
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            logger.warning(
                "Gemini synthesis failed.",
                extra={"error": f"{type(exc).__name__}: {exc}"},
            )
            raise

    raise RuntimeError("Gemini synthesis failed after retry.")


def _gemini_text(response: dict[str, Any]) -> str:
    parts = [
        part.get("text", "")
        for candidate in response.get("candidates", [])
        for part in candidate.get("content", {}).get("parts", [])
        if isinstance(part, dict)
    ]
    text = "".join(parts)
    if not text:
        raise ValueError(
            "Gemini response did not include text content: "
            f"{json.dumps(response.get('promptFeedback') or {}, ensure_ascii=True)}"
        )
    return text
