from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from cache import get_value, set_value
from fetchers.gitcoin import fetch_active_grants
from fetchers.snapshot import fetch_active_proposals
from signals.scorer import SIGNAL_THRESHOLD, build_signal
from signals.store import increment_stat, save_signal_with_result

logger = logging.getLogger(__name__)

SNAPSHOT_STATE_KEY = "state:snapshot:latest"
GITCOIN_STATE_KEY = "state:gitcoin:latest"
LAST_POLL_TIME_KEY = "stats:last_poll_time"
POLL_INTERVAL_MINUTES = 10


async def poll_ecosystem() -> list[dict[str, Any]]:
    """Fetch ecosystem state, persist it, and return prioritized signals."""
    poll_started_at = datetime.now(UTC)
    previous_poll_time = _parse_datetime(await get_value(LAST_POLL_TIME_KEY))

    proposals, grants = await asyncio.gather(fetch_active_proposals(), fetch_active_grants())
    previous_proposals = _as_list(await get_value(SNAPSHOT_STATE_KEY))
    previous_grants = _as_list(await get_value(GITCOIN_STATE_KEY))

    snapshot_events = diff_snapshot_proposals(
        previous_proposals,
        proposals,
        now=poll_started_at,
        previous_poll_time=previous_poll_time,
    )
    gitcoin_events = diff_gitcoin_grants(
        previous_grants,
        grants,
        now=poll_started_at,
        previous_poll_time=previous_poll_time,
    )
    events = [*snapshot_events, *gitcoin_events]

    await set_value(SNAPSHOT_STATE_KEY, proposals)
    await set_value(GITCOIN_STATE_KEY, grants)
    await set_value(LAST_POLL_TIME_KEY, poll_started_at.isoformat())
    signals = await process_diff_events(events, now=poll_started_at)

    if not proposals:
        logger.info("Snapshot quiet period.", extra={"proposals_found": 0})
    if not events:
        logger.info(
            "Ecosystem quiet period.",
            extra={"proposals_found": len(proposals), "grants_found": len(grants)},
        )

    logger.info(
        "Poll completed.",
        extra={
            "poll_timestamp": poll_started_at.isoformat(),
            "proposals_found": len(proposals),
            "grants_found": len(grants),
            "diffs_detected": len(events),
            "signals_generated": len(signals),
        },
    )
    return signals


async def process_diff_events(
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    generated_signals: list[dict[str, Any]] = []
    severity_counts: Counter[str] = Counter()
    discarded_count = 0
    duplicate_count = 0

    await increment_stat("scoring_engine_runs")
    await set_value("stats:scoring_engine_health", "ok")

    for event in events:
        try:
            signal = build_signal(event, now=now)
        except Exception as exc:
            discarded_count += 1
            await increment_stat("signals_ignored")
            await set_value("stats:scoring_engine_health", "degraded")
            logger.exception(
                "Signal scoring failed.",
                extra={
                    "event_id": event.get("event_id"),
                    "event_type": event.get("event_type"),
                    "error": f"{type(exc).__name__}: {exc}",
                },
            )
            continue
        payload = signal.model_dump(mode="json")

        if signal.urgency_score < SIGNAL_THRESHOLD:
            discarded_count += 1
            await increment_stat("signals_ignored")
            logger.info(
                "Signal discarded.",
                extra={
                    "event_id": signal.event_id,
                    "score": signal.urgency_score,
                    "reason": "below_threshold",
                    "scoring_reasons": signal.reasons,
                },
            )
            continue

        logger.info(
            "Signal scored above threshold.",
            extra={
                "event_id": signal.event_id,
                "score": signal.urgency_score,
                "severity": signal.severity,
                "scoring_reasons": signal.reasons,
            },
        )
        result = await save_signal_with_result(payload, now=now)
        if not result.saved:
            duplicate_count += 1
            logger.info(
                "Signal discarded.",
                extra={
                    "event_id": signal.event_id,
                    "score": signal.urgency_score,
                    "reason": result.reason,
                },
            )
            continue

        generated_signals.append(payload)
        severity_counts[signal.severity] += 1

        if signal.notify_users:
            logger.info(
                "Signal escalation recommended.",
                extra={
                    "event_id": signal.event_id,
                    "score": signal.urgency_score,
                    "severity": signal.severity,
                    "recommendation": signal.escalation_recommendation,
                },
            )

    logger.info(
        "Signal scoring completed.",
        extra={
            "events_scored": len(events),
            "signals_generated": len(generated_signals),
            "events_discarded": discarded_count,
            "duplicates_suppressed": duplicate_count,
            "severity_distribution": dict(severity_counts),
        },
    )
    return generated_signals


def diff_snapshot_proposals(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    previous_poll_time: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    previous_by_id = _index_by_id(previous)
    events: list[dict[str, Any]] = []

    for proposal in current:
        proposal_id = _item_id(proposal)
        if not proposal_id:
            continue
        previous_proposal = previous_by_id.get(proposal_id)
        current_summary = _proposal_summary(proposal, now)

        if previous_proposal is None:
            events.append(
                _snapshot_event(
                    "proposal_new",
                    proposal_id,
                    proposal,
                    current_summary,
                    previous_summary=None,
                    is_new_proposal=True,
                )
            )
            continue

        previous_summary = _proposal_summary(previous_proposal, now)
        vote_swing_pct = abs(current_summary["for_pct"] - previous_summary["for_pct"])
        result_flipped = _result_flipped(
            previous_summary["current_result"],
            current_summary["current_result"],
        )
        quorum_risk_changed = (
            current_summary["quorum_at_risk"] and not previous_summary["quorum_at_risk"]
        )

        if vote_swing_pct >= 10 or result_flipped or quorum_risk_changed:
            events.append(
                _snapshot_event(
                    "proposal_changed",
                    proposal_id,
                    proposal,
                    current_summary,
                    previous_summary=previous_summary,
                    vote_swing_pct=round(vote_swing_pct, 2),
                    for_vs_against_swing=result_flipped,
                )
            )

        if previous_poll_time and _deadline_threshold_crossed(
            _proposal_deadline(proposal),
            previous_poll_time,
            now,
        ):
            events.append(
                _snapshot_event(
                    "proposal_deadline_approaching",
                    proposal_id,
                    proposal,
                    current_summary,
                    previous_summary=previous_summary,
                )
            )

    return events


def diff_gitcoin_grants(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    previous_poll_time: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    previous_by_id = _index_by_id(previous)
    events: list[dict[str, Any]] = []

    for grant in current:
        grant_id = _item_id(grant)
        if not grant_id:
            continue
        current_summary = _grant_summary(grant, now)
        previous_grant = previous_by_id.get(grant_id)

        if previous_grant is None:
            events.append(
                _gitcoin_event(
                    "grant_new",
                    grant_id,
                    grant,
                    current_summary,
                    previous_summary=None,
                )
            )
            continue

        previous_summary = _grant_summary(previous_grant, now)
        deadline_changed = current_summary["deadline"] != previous_summary["deadline"]
        funding_changed = (
            current_summary["estimated_treasury_impact_usd"]
            != previous_summary["estimated_treasury_impact_usd"]
        )
        title_changed = current_summary["title"] != previous_summary["title"]

        if deadline_changed or funding_changed or title_changed:
            events.append(
                _gitcoin_event(
                    "grant_changed",
                    grant_id,
                    grant,
                    current_summary,
                    previous_summary=previous_summary,
                )
            )

        deadline = _parse_datetime(current_summary["deadline"])
        if previous_poll_time and _deadline_threshold_crossed(deadline, previous_poll_time, now):
            events.append(
                _gitcoin_event(
                    "grant_deadline_approaching",
                    grant_id,
                    grant,
                    current_summary,
                    previous_summary=previous_summary,
                )
            )

    return events


def start_polling_scheduler() -> Any | None:
    """Start the APScheduler polling loop and return the scheduler instance."""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:
        logger.exception("APScheduler is not installed; polling scheduler was not started.")
        return None

    scheduler = AsyncIOScheduler(timezone=UTC)
    scheduler.add_job(
        poll_ecosystem,
        trigger="interval",
        minutes=POLL_INTERVAL_MINUTES,
        id="base-navigator-poller",
        name="Base Navigator ecosystem poller",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        next_run_time=datetime.now(UTC),
    )
    scheduler.start()
    logger.info("Polling scheduler started.", extra={"interval_minutes": POLL_INTERVAL_MINUTES})
    return scheduler


def stop_polling_scheduler(scheduler: Any | None) -> None:
    if scheduler is None:
        return
    scheduler.shutdown(wait=False)
    logger.info("Polling scheduler stopped.")


def _snapshot_event(
    event_type: str,
    proposal_id: str,
    proposal: dict[str, Any],
    summary: dict[str, Any],
    *,
    previous_summary: dict[str, Any] | None,
    is_new_proposal: bool = False,
    vote_swing_pct: float = 0.0,
    for_vs_against_swing: bool = False,
) -> dict[str, Any]:
    space = proposal.get("space") if isinstance(proposal.get("space"), dict) else {}
    protocol = space.get("name") or space.get("id") or "Unknown protocol"
    payload = {
        "source": "snapshot",
        "event_type": event_type,
        "proposal_id": proposal_id,
        "title": proposal.get("title") or "Untitled proposal",
        "for_pct": summary["for_pct"],
        "votes": summary["votes"],
        "scores_total": summary["scores_total"],
        "hours_until_deadline": summary["hours_until_deadline"],
        "current_result": summary["current_result"],
        "previous_result": previous_summary.get("current_result") if previous_summary else None,
    }
    return {
        "event_id": _event_id("snapshot", proposal_id, event_type, payload),
        "source": "snapshot",
        "event_type": event_type,
        "protocol": protocol,
        "title": proposal.get("title") or "Untitled proposal",
        "source_url": f"https://snapshot.box/#/s:{space.get('id', '')}/proposal/{proposal_id}",
        "is_new_proposal": is_new_proposal,
        "vote_swing_pct": vote_swing_pct,
        "hours_until_deadline": summary["hours_until_deadline"],
        "estimated_treasury_impact_usd": summary["estimated_treasury_impact_usd"],
        "quorum_at_risk": summary["quorum_at_risk"],
        "for_vs_against_swing": for_vs_against_swing,
        "current": summary,
        "previous": previous_summary,
    }


def _gitcoin_event(
    event_type: str,
    grant_id: str,
    grant: dict[str, Any],
    summary: dict[str, Any],
    *,
    previous_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = {
        "source": summary["source"],
        "event_type": event_type,
        "grant_id": grant_id,
        "title": summary["title"],
        "deadline": summary["deadline"],
        "estimated_treasury_impact_usd": summary["estimated_treasury_impact_usd"],
    }
    return {
        "event_id": _event_id("gitcoin", grant_id, event_type, payload),
        "source": summary["source"],
        "event_type": event_type,
        "protocol": summary["operator"],
        "title": summary["title"],
        "source_url": summary["apply_url"],
        "is_new_proposal": False,
        "is_new_grant": event_type == "grant_new",
        "vote_swing_pct": 0.0,
        "hours_until_deadline": summary["hours_until_deadline"],
        "estimated_treasury_impact_usd": summary["estimated_treasury_impact_usd"],
        "quorum_at_risk": False,
        "for_vs_against_swing": False,
        "current": summary,
        "previous": previous_summary,
    }


def _proposal_summary(proposal: dict[str, Any], now: datetime) -> dict[str, Any]:
    scores = proposal.get("scores") if isinstance(proposal.get("scores"), list) else []
    scores_total = float(
        proposal.get("scores_total")
        or sum(_float(score) for score in scores)
        or 0
    )
    for_pct = round((_float(scores[0]) / scores_total) * 100, 2) if scores and scores_total else 0.0
    quorum = _float(proposal.get("quorum"))
    deadline = _proposal_deadline(proposal)
    title = str(proposal.get("title") or "Untitled proposal")
    body = str(proposal.get("body") or "")
    return {
        "id": proposal.get("id"),
        "title": title,
        "for_pct": for_pct,
        "votes": int(_float(proposal.get("votes"))),
        "scores_total": scores_total,
        "quorum": quorum,
        "quorum_at_risk": bool(quorum and scores_total < quorum * 0.5),
        "current_result": _proposal_result(for_pct, scores_total),
        "deadline": deadline.isoformat() if deadline else None,
        "hours_until_deadline": _hours_until(deadline, now),
        "estimated_treasury_impact_usd": _estimate_usd_from_text(f"{title} {body}"),
    }


def _grant_summary(grant: dict[str, Any], now: datetime) -> dict[str, Any]:
    metadata = _round_metadata(grant.get("roundMetadata"))
    title = (
        metadata.get("name")
        or metadata.get("title")
        or grant.get("name")
        or grant.get("title")
        or "Untitled grant round"
    )
    deadline = _first_datetime(
        grant.get("applicationsEndTime"),
        grant.get("donationsEndTime"),
        grant.get("deadline"),
    )
    amount = _first_present(
        grant.get("matchingFundsAvailable"),
        grant.get("matchingCap"),
        grant.get("amount"),
    )
    return {
        "id": _item_id(grant),
        "source": grant.get("source") or "gitcoin",
        "title": str(title),
        "operator": str(grant.get("operator") or "Gitcoin"),
        "deadline": deadline.isoformat() if deadline else None,
        "hours_until_deadline": _hours_until(deadline, now),
        "estimated_treasury_impact_usd": _estimate_usd_from_value(amount),
        "apply_url": str(grant.get("apply_url") or grant.get("url") or ""),
    }


def _index_by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item_id: item for item in items if (item_id := _item_id(item))}


def _item_id(item: dict[str, Any]) -> str | None:
    value = (
        item.get("id")
        or item.get("roundId")
        or item.get("apply_url")
        or item.get("url")
        or item.get("title")
        or item.get("name")
    )
    return str(value) if value else None


def _event_id(source: str, entity_id: str, event_type: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return f"{source}:{_slug(entity_id)}:{event_type}:{digest[:12]}"


def _proposal_result(for_pct: float, total: float) -> str:
    if total <= 0:
        return "too close to call"
    if for_pct >= 55:
        return "passing"
    if for_pct <= 45:
        return "failing"
    return "too close to call"


def _result_flipped(previous: str, current: str) -> bool:
    decisive = {"passing", "failing"}
    return previous in decisive and current in decisive and previous != current


def _proposal_deadline(proposal: dict[str, Any]) -> datetime | None:
    end = proposal.get("end")
    if end in (None, ""):
        return None
    return datetime.fromtimestamp(int(_float(end)), UTC)


def _deadline_threshold_crossed(
    deadline: datetime | None,
    previous_poll_time: datetime,
    now: datetime,
) -> bool:
    previous_hours = _hours_until(deadline, previous_poll_time)
    current_hours = _hours_until(deadline, now)
    return any(previous_hours > threshold >= current_hours for threshold in (72, 24, 6))


def _hours_until(deadline: datetime | None, now: datetime) -> int:
    if deadline is None:
        return 999_999
    return max(0, int((deadline - now).total_seconds() // 3600))


def _round_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _first_datetime(*values: Any) -> datetime | None:
    for value in values:
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, UTC)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _estimate_usd_from_value(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return _estimate_usd_from_text(str(value))


def _estimate_usd_from_text(text: str) -> float:
    matches = re.finditer(
        r"(?:\$|USD\s*|USDC\s*)?(\d[\d,]*(?:\.\d+)?)\s*(million|m|thousand|k|usd|usdc)?",
        text,
        flags=re.IGNORECASE,
    )
    best = 0.0
    for match in matches:
        amount = _float(match.group(1).replace(",", ""))
        unit = (match.group(2) or "").lower()
        if unit in {"million", "m"}:
            amount *= 1_000_000
        elif unit in {"thousand", "k"}:
            amount *= 1_000
        best = max(best, amount)
    return best


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-")[:80] or "unknown"


def _as_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
