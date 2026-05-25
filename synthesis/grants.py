from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from models import GrantsResponse
from synthesis.common import call_gemini_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are Base Navigator, an AI intelligence service for builders in the Base ecosystem.
You receive a JSON object with current_utc and raw grants data in data.
Use current_utc exactly as the as_of value.
If data is empty, return empty open_grants and urgent_deadlines arrays.
Return ONLY a valid JSON object.
No markdown, no explanation, no text outside JSON.

Always return exactly this structure:
{
  "as_of": "<ISO timestamp>",
  "open_grants": [
    {
      "name": "<grant or round name>",
      "operator": "<organization running it>",
      "amount": "<funding amount, or 'Not specified'>",
      "deadline": "<ISO timestamp or null>",
      "urgency": "critical" | "high" | "medium" | "low",
      "eligibility": ["<short criterion>", "..."],
      "apply_url": "<URL>",
      "tldr": "<1 sentence plain English explanation>"
    }
  ],
  "urgent_deadlines": [<same Grant objects for deadlines under 7 days>],
  "pro_tip": "<1 concise action recommendation for a Base builder>"
}
"""


async def synthesize_grants(grants: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        model_output = await call_gemini_json(SYSTEM_PROMPT, grants)
        return GrantsResponse.model_validate(model_output).model_dump(mode="json")
    except Exception as exc:
        logger.warning(
            "Using deterministic grants fallback.",
            extra={"error": f"{type(exc).__name__}: {exc}", "grant_count": len(grants)},
        )
        return _fallback_grants(grants)


def _fallback_grants(grants: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(UTC)
    items = [_grant_summary(grant, now) for grant in grants[:20]]
    urgent = [item for item in items if item["urgency"] in {"critical", "high"}]
    pro_tip = (
        "Prioritize grants with live application windows and prepare a concise builder "
        "traction summary."
        if items
        else "No open Base grants were found, so check Base channels and Farcaster for new rounds."
    )
    payload = {
        "as_of": now.isoformat(),
        "open_grants": items,
        "urgent_deadlines": urgent,
        "pro_tip": pro_tip,
    }
    return GrantsResponse.model_validate(payload).model_dump(mode="json")


def _grant_summary(grant: dict[str, Any], now: datetime) -> dict[str, Any]:
    metadata = _metadata(grant.get("roundMetadata")) or grant
    name = (
        metadata.get("name")
        or metadata.get("title")
        or grant.get("name")
        or "Base ecosystem grant opportunity"
    )
    description = (
        metadata.get("description")
        or grant.get("description")
        or "Funding opportunity for Base ecosystem builders."
    )
    deadline = (
        grant.get("applicationsEndTime")
        or grant.get("donationsEndTime")
        or grant.get("deadline")
    )
    deadline_iso, hours_remaining = _deadline(deadline, now)
    apply_url = (
        metadata.get("applicationUrl")
        or metadata.get("applyUrl")
        or grant.get("apply_url")
        or "https://explorer.gitcoin.co"
    )
    amount = grant.get("matchingFundsAvailable") or grant.get("amount") or "Not specified"
    operator = (
        metadata.get("support", {}).get("info")
        if isinstance(metadata.get("support"), dict)
        else None
    )

    return {
        "name": _clean_text(str(name), 120),
        "operator": operator or grant.get("operator") or "Gitcoin/Base ecosystem",
        "amount": str(amount),
        "deadline": deadline_iso,
        "urgency": _urgency(hours_remaining),
        "eligibility": _eligibility(metadata),
        "apply_url": str(apply_url),
        "tldr": _clean_text(str(description), 180),
    }


def _metadata(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _deadline(value: Any, now: datetime) -> tuple[str | None, int | None]:
    if not value:
        return None, None
    if isinstance(value, (int, float)):
        end = datetime.fromtimestamp(value, UTC)
    else:
        text = str(value).replace("Z", "+00:00")
        try:
            end = datetime.fromisoformat(text)
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)
        except ValueError:
            return str(value), None
    return end.isoformat(), max(0, int((end - now).total_seconds() // 3600))


def _urgency(hours_remaining: int | None) -> str:
    if hours_remaining is None:
        return "low"
    if hours_remaining <= 24:
        return "critical"
    if hours_remaining <= 168:
        return "high"
    if hours_remaining <= 720:
        return "medium"
    return "low"


def _eligibility(metadata: dict[str, Any]) -> list[str]:
    eligibility = metadata.get("eligibility") or metadata.get("eligibilityRequirements")
    if isinstance(eligibility, list):
        return [_clean_text(str(item), 100) for item in eligibility[:5]]
    if isinstance(eligibility, str):
        return [_clean_text(eligibility, 140)]
    return ["Builds in or benefits the Base ecosystem"]


def _clean_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
