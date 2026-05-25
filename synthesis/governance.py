from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any, cast

from models import GovernanceResponse
from synthesis.common import call_gemini_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are Base Navigator, an AI intelligence service for the Base blockchain ecosystem.
You receive a JSON object with current_utc and raw governance proposal data in data.
Use current_utc exactly as the as_of value.
If data is empty, return an empty active_proposals array and urgent_count 0.
Return ONLY a valid JSON object.
No markdown, no explanation, no text outside JSON.

Always return exactly this structure:
{
  "as_of": "<ISO timestamp>",
  "active_proposals": [
    {
      "protocol": "<DAO name>",
      "title": "<proposal title, max 80 chars>",
      "tldr": "<1 sentence plain English explanation of what this vote decides>",
      "voting_ends": "<ISO timestamp>",
      "hours_remaining": <integer>,
      "current_result": "passing" | "failing" | "too close to call",
      "for_pct": <float 0-100>,
      "impact": "high" | "medium" | "low",
      "source_url": "<snapshot URL>",
      "urgency": "critical" | "high" | "medium" | "low"
    }
  ],
  "urgent_count": <int>,
  "summary_for_agents": "<2 sentence summary of what's happening this week in Base governance>"
}
"""


async def synthesize_governance(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        model_output = await call_gemini_json(SYSTEM_PROMPT, proposals)
        return GovernanceResponse.model_validate(model_output).model_dump(mode="json")
    except Exception as exc:
        logger.warning(
            "Using deterministic governance fallback.",
            extra={"error": f"{type(exc).__name__}: {exc}", "proposal_count": len(proposals)},
        )
        return _fallback_governance(proposals)


def _fallback_governance(proposals: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(UTC)
    items = [_proposal_summary(proposal, now) for proposal in proposals[:20]]
    urgent_count = sum(1 for item in items if item["hours_remaining"] <= 24)
    if items:
        summary = (
            f"{len(items)} active Base ecosystem governance proposal(s) are being monitored. "
            f"{urgent_count} proposal(s) end within 24 hours."
        )
    else:
        summary = "No active monitored Base ecosystem governance proposals were found."
    return GovernanceResponse(
        as_of=now.isoformat(),
        active_proposals=cast(list, items),
        urgent_count=urgent_count,
        summary_for_agents=summary,
    ).model_dump(mode="json")


def _proposal_summary(proposal: dict[str, Any], now: datetime) -> dict[str, Any]:
    end_ts = int(proposal.get("end") or 0)
    voting_ends = datetime.fromtimestamp(end_ts, UTC) if end_ts else now
    hours_remaining = max(0, int((voting_ends - now).total_seconds() // 3600))
    scores = proposal.get("scores") if isinstance(proposal.get("scores"), list) else []
    total = float(
        proposal.get("scores_total")
        or sum(float(score or 0) for score in (scores or []))
        or 0
    )
    for_pct = round((float(scores[0]) / total) * 100, 2) if scores and total else 0.0
    current_result = "too close to call"
    if for_pct >= 55:
        current_result = "passing"
    elif total and for_pct <= 45:
        current_result = "failing"

    space = proposal.get("space") or {}
    protocol = space.get("name") or space.get("id") or "Unknown protocol"
    source_url = f"https://snapshot.box/#/s:{space.get('id', '')}/proposal/{proposal.get('id', '')}"
    title = _clean_text(proposal.get("title") or "Untitled proposal", 160)
    body = _clean_text(proposal.get("body") or "", 220)
    tldr = body or "Review the linked Snapshot proposal for details."

    return {
        "protocol": protocol,
        "title": title,
        "tldr": tldr,
        "voting_ends": voting_ends.isoformat(),
        "hours_remaining": hours_remaining,
        "current_result": current_result,
        "for_pct": for_pct,
        "impact": "medium",
        "source_url": source_url,
        "urgency": _urgency(hours_remaining),
    }


def _urgency(hours_remaining: int) -> str:
    if hours_remaining <= 6:
        return "critical"
    if hours_remaining <= 24:
        return "high"
    if hours_remaining <= 72:
        return "medium"
    return "low"


def _clean_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
