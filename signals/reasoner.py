from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from cache import get_counter, get_value, increment_counter, increment_counter_capped, set_value
from signals.scorer import HIGH_SIGNAL_THRESHOLD
from synthesis.common import call_gemini_json

logger = logging.getLogger(__name__)

REASONING_VERSION = "gemini-enrichment-v1"
DAILY_GEMINI_CAP = 50
MAX_REASONING_ATTEMPTS = 2

SYSTEM_PROMPT = """
You are Base Navigator's ecosystem intelligence enrichment engine.
You receive ONE already-scored signal from the Base blockchain ecosystem.

The deterministic scoring engine has already decided importance.
Do not change severity, urgency score, or whether the event matters.
Your job is to add concise operational context for builders, holders, and ecosystem operators.

Return ONLY a JSON object with exactly these fields:
{
  "ecosystem_summary": "1 sentence describing what happened",
  "why_this_matters": "1-2 sentences explaining concrete ecosystem significance",
  "potential_impact": "1 sentence describing treasury, governance, funding, or coordination impact",
  "recommended_attention": "1 sentence stating who should pay attention and why",
  "confidence": 0.0,
  "risk_level": "critical" | "high" | "medium" | "low",
  "key_entities": ["short protocol/entity names"],
  "follow_up_watch_items": ["specific items to monitor next"]
}

Be analytical and operational, not conversational.
Reference actual protocol names, scores, deadlines, treasury amounts, and vote movement
when available.
Avoid generic phrases like "could impact the ecosystem" unless immediately followed
by concrete details.
Do not include markdown, commentary, or fields outside the JSON object.
"""

RiskLevel = Literal["critical", "high", "medium", "low"]
EnrichmentStatus = Literal["analyzed", "skipped", "failed"]


class GeminiReasoning(BaseModel):
    ecosystem_summary: str = Field(min_length=1, max_length=500)
    why_this_matters: str = Field(min_length=1, max_length=900)
    potential_impact: str = Field(min_length=1, max_length=700)
    recommended_attention: str = Field(min_length=1, max_length=700)
    confidence: float = Field(ge=0, le=1)
    risk_level: RiskLevel
    key_entities: list[str] = Field(default_factory=list)
    follow_up_watch_items: list[str] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, value: Any) -> float:
        numeric = float(value)
        if numeric > 1 and numeric <= 100:
            return numeric / 100
        return numeric


class SignalEnrichment(BaseModel):
    status: EnrichmentStatus
    provider: str = "gemini"
    model_version: str = REASONING_VERSION
    generated_at: str
    cache_hit: bool = False
    fallback_reason: str | None = None
    ecosystem_summary: str | None = None
    why_this_matters: str | None = None
    potential_impact: str | None = None
    recommended_attention: str | None = None
    confidence: float | None = None
    risk_level: RiskLevel | None = None
    key_entities: list[str] = Field(default_factory=list)
    follow_up_watch_items: list[str] = Field(default_factory=list)


class GeminiDailyCapReached(RuntimeError):
    pass


async def enrich_signal(signal: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Attach Gemini reasoning only when the scored signal is high-value."""
    current_time = now or datetime.now(UTC)
    enriched = dict(signal)
    event_id = str(signal.get("event_id") or "")

    if not should_enrich_signal(signal):
        await increment_counter("stats:gemini_enrichments_skipped")
        logger.info(
            "Gemini enrichment skipped.",
            extra={
                "event_id": event_id,
                "score": signal.get("urgency_score"),
                "severity": signal.get("severity"),
                "reason": "not_high_value",
            },
        )
        return enriched

    cache_key = reasoning_cache_key(event_id)
    cached = await get_value(cache_key)
    if isinstance(cached, dict):
        try:
            enrichment = SignalEnrichment.model_validate({**cached, "cache_hit": True})
        except ValidationError as exc:
            logger.warning(
                "Malformed Gemini enrichment cache ignored.",
                extra={"event_id": event_id, "error": str(exc)},
            )
        else:
            await increment_counter("stats:gemini_enrichment_cache_hits")
            enriched["llm_enrichment"] = enrichment.model_dump(mode="json")
            logger.info("Gemini enrichment cache hit.", extra={"event_id": event_id})
            return enriched

    await increment_counter("stats:gemini_enrichment_cache_misses")
    logger.info(
        "Gemini enrichment started.",
        extra={"event_id": event_id, "score": signal.get("urgency_score")},
    )
    started_at = time.perf_counter()
    try:
        reasoning = await _call_gemini_with_retries(signal, current_time)
    except GeminiDailyCapReached:
        latency_ms = _latency_ms(started_at)
        await increment_counter("stats:gemini_enrichments_skipped")
        await increment_counter("stats:gemini_fallbacks")
        enrichment = _fallback_enrichment(
            signal,
            current_time,
            status="skipped",
            reason="daily_cap_reached",
        )
        enriched["llm_enrichment"] = enrichment.model_dump(mode="json")
        logger.info(
            "Daily cap reached.",
            extra={
                "event_id": event_id,
                "daily_cap": DAILY_GEMINI_CAP,
                "score": signal.get("urgency_score"),
                "latency_ms": latency_ms,
            },
        )
        return enriched
    except Exception as exc:
        latency_ms = _latency_ms(started_at)
        await _record_latency(latency_ms)
        await increment_counter("stats:gemini_failures")
        await increment_counter("stats:gemini_fallbacks")
        enrichment = _fallback_enrichment(
            signal,
            current_time,
            status="failed",
            reason=f"{type(exc).__name__}: {exc}",
        )
        enriched["llm_enrichment"] = enrichment.model_dump(mode="json")
        logger.warning(
            "Gemini enrichment fallback used.",
            extra={
                "event_id": event_id,
                "score": signal.get("urgency_score"),
                "latency_ms": latency_ms,
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        return enriched

    latency_ms = _latency_ms(started_at)
    await _record_latency(latency_ms)
    await increment_counter("stats:gemini_enrichments")
    await set_value("stats:last_gemini_enrichment_at", current_time.isoformat())

    enrichment = SignalEnrichment(
        status="analyzed",
        generated_at=current_time.isoformat(),
        ecosystem_summary=reasoning.ecosystem_summary,
        why_this_matters=reasoning.why_this_matters,
        potential_impact=reasoning.potential_impact,
        recommended_attention=reasoning.recommended_attention,
        confidence=reasoning.confidence,
        risk_level=reasoning.risk_level,
        key_entities=reasoning.key_entities,
        follow_up_watch_items=reasoning.follow_up_watch_items,
    )
    payload = enrichment.model_dump(mode="json")
    await set_value(cache_key, payload)
    enriched["llm_enrichment"] = payload
    logger.info(
        "Gemini enrichment completed.",
        extra={
            "event_id": event_id,
            "score": signal.get("urgency_score"),
            "latency_ms": latency_ms,
        },
    )
    return enriched


async def reason_about_signal(event: dict[str, Any], score: int) -> dict[str, Any]:
    """Compatibility wrapper for callers that enrich an event directly."""
    signal = {
        **event,
        "urgency_score": score,
        "severity": event.get("severity") or ("critical" if score >= 70 else "high"),
        "requires_llm_reasoning": True,
    }
    enriched = await enrich_signal(signal)
    enrichment = enriched.get("llm_enrichment")
    return enrichment if isinstance(enrichment, dict) else {}


def should_enrich_signal(signal: dict[str, Any]) -> bool:
    severity = str(signal.get("severity") or "").lower()
    score = int(signal.get("urgency_score") or 0)
    return bool(
        signal.get("requires_llm_reasoning")
        and (
            severity in {"high", "critical"}
            or signal.get("notify_users") is True
            or signal.get("escalation_recommendation") in {"priority_digest", "immediate_alert"}
            or score >= HIGH_SIGNAL_THRESHOLD
        )
    )


def reasoning_cache_key(event_id: str) -> str:
    return f"reasoning:{event_id}"


async def average_enrichment_latency_ms() -> float:
    total = await get_counter("stats:gemini_enrichment_latency_total_ms")
    count = await get_counter("stats:gemini_enrichment_latency_count")
    return round(total / count, 2) if count else 0.0


async def _call_gemini_with_retries(
    signal: dict[str, Any],
    now: datetime,
) -> GeminiReasoning:
    last_error: Exception | None = None
    for attempt in range(1, MAX_REASONING_ATTEMPTS + 1):
        try:
            allowed, call_count = await _reserve_gemini_call(now)
            if not allowed:
                raise GeminiDailyCapReached("Gemini daily cap reached.")
            logger.info(
                "Gemini call reserved.",
                extra={
                    "event_id": signal.get("event_id"),
                    "attempt": attempt,
                    "gemini_calls_today": call_count,
                    "daily_cap": DAILY_GEMINI_CAP,
                },
            )
            model_output = await call_gemini_json(
                SYSTEM_PROMPT,
                _reasoning_payload(signal),
                max_tokens=900,
            )
            return GeminiReasoning.model_validate(model_output)
        except ValidationError as exc:
            logger.warning(
                "Gemini enrichment returned malformed output.",
                extra={
                    "event_id": signal.get("event_id"),
                    "attempt": attempt,
                    "error": str(exc),
                },
            )
            last_error = exc
        except GeminiDailyCapReached:
            raise
        except Exception as exc:
            logger.warning(
                "Gemini enrichment attempt failed.",
                extra={
                    "event_id": signal.get("event_id"),
                    "attempt": attempt,
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            last_error = exc

    raise RuntimeError("Gemini enrichment failed after retries.") from last_error


def _reasoning_payload(signal: dict[str, Any]) -> dict[str, Any]:
    raw_event = signal.get("raw_event") if isinstance(signal.get("raw_event"), dict) else {}
    current = raw_event.get("current") if isinstance(raw_event.get("current"), dict) else {}
    previous = raw_event.get("previous") if isinstance(raw_event.get("previous"), dict) else {}
    return {
        "event_id": signal.get("event_id"),
        "event_type": signal.get("event_type"),
        "source": signal.get("source"),
        "protocol": signal.get("protocol"),
        "title": signal.get("title"),
        "source_url": signal.get("source_url"),
        "severity": signal.get("severity"),
        "urgency_score": signal.get("urgency_score"),
        "importance_score": signal.get("importance_score"),
        "scoring_reasons": signal.get("reasons", []),
        "score_components": signal.get("score_components", []),
        "deterministic_flags": {
            "requires_llm_reasoning": signal.get("requires_llm_reasoning"),
            "notify_users": signal.get("notify_users"),
            "store_as_major_signal": signal.get("store_as_major_signal"),
            "escalation_recommendation": signal.get("escalation_recommendation"),
        },
        "current_state_summary": current,
        "previous_state_summary": previous,
    }


def _fallback_enrichment(
    signal: dict[str, Any],
    now: datetime,
    *,
    status: EnrichmentStatus,
    reason: str,
) -> SignalEnrichment:
    protocol = signal.get("protocol") or "Unknown protocol"
    title = signal.get("title") or "Untitled signal"
    return SignalEnrichment(
        status=status,
        generated_at=now.isoformat(),
        fallback_reason=reason,
        ecosystem_summary=f"{protocol}: {title}",
        why_this_matters=(
            "Deterministic scoring preserved this signal, but Gemini enrichment is unavailable."
        ),
        potential_impact="Use the deterministic score, severity, and scoring reasons for triage.",
        recommended_attention="Review the source signal before taking action.",
        confidence=0,
        risk_level=_risk_from_severity(signal.get("severity")),
        key_entities=[str(protocol)],
        follow_up_watch_items=["Retry enrichment when Gemini is available."],
    )


def _risk_from_severity(value: Any) -> RiskLevel:
    severity = str(value or "").lower()
    if severity in {"critical", "high", "medium", "low"}:
        return severity  # type: ignore[return-value]
    return "medium"


def _daily_gemini_counter_key(now: datetime) -> str:
    return f"stats:gemini_calls:{now.date().isoformat()}"


async def _reserve_gemini_call(now: datetime) -> tuple[bool, int]:
    return await increment_counter_capped(_daily_gemini_counter_key(now), DAILY_GEMINI_CAP)


async def _record_latency(latency_ms: int) -> None:
    await increment_counter("stats:gemini_enrichment_latency_total_ms", latency_ms)
    await increment_counter("stats:gemini_enrichment_latency_count")


def _latency_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))
