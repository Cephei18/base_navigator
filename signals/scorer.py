from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCORING_VERSION = "deterministic-v1"
SIGNAL_THRESHOLD = 30
HIGH_SIGNAL_THRESHOLD = 50
CRITICAL_SIGNAL_THRESHOLD = 70

Severity = Literal["low", "medium", "high", "critical"]
ScoreCategory = Literal["urgency", "importance", "relevance"]


class SignalEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    event_id: str = ""
    event_type: str
    source: str
    protocol: str = "Unknown protocol"
    title: str = "Untitled event"
    source_url: str = ""
    is_new_proposal: bool = False
    is_new_grant: bool = False
    vote_swing_pct: float = 0.0
    hours_until_deadline: int = 999_999
    estimated_treasury_impact_usd: float = 0.0
    quorum_at_risk: bool = False
    for_vs_against_swing: bool = False
    current: dict[str, Any] = Field(default_factory=dict)
    previous: dict[str, Any] | None = None


class ScoreComponent(BaseModel):
    category: ScoreCategory
    rule: str
    points: int
    reason: str


class ScoredSignal(BaseModel):
    event_id: str
    event_type: str
    source: str
    protocol: str
    title: str
    source_url: str
    severity: Severity
    urgency_score: int
    importance_score: int
    reasons: list[str]
    score_components: list[ScoreComponent]
    requires_llm_reasoning: bool
    notify_users: bool
    store_as_major_signal: bool
    dashboard_worthy: bool
    escalation_recommendation: str
    created_at: str
    scoring_version: str = SCORING_VERSION
    raw_event: dict[str, Any]


def score_event(event: dict[str, Any]) -> int:
    """Return the deterministic urgency score used for signal thresholding."""
    signal = build_signal(event)
    return signal.urgency_score


def build_signal(event: dict[str, Any], *, now: datetime | None = None) -> ScoredSignal:
    signal_event = SignalEvent.model_validate(event)
    created_at = now or datetime.now(UTC)
    components = _score_components(signal_event)
    urgency_score = sum(component.points for component in components)
    importance_score = sum(
        component.points
        for component in components
        if component.category in {"importance", "relevance"}
    )
    severity = classify_severity(urgency_score)
    event_id = signal_event.event_id or _fallback_event_id(event)

    return ScoredSignal(
        event_id=event_id,
        event_type=signal_event.event_type,
        source=signal_event.source,
        protocol=signal_event.protocol,
        title=signal_event.title,
        source_url=signal_event.source_url,
        severity=severity,
        urgency_score=urgency_score,
        importance_score=importance_score,
        reasons=[component.reason for component in components],
        score_components=components,
        requires_llm_reasoning=urgency_score >= SIGNAL_THRESHOLD,
        notify_users=urgency_score >= CRITICAL_SIGNAL_THRESHOLD,
        store_as_major_signal=urgency_score >= HIGH_SIGNAL_THRESHOLD,
        dashboard_worthy=urgency_score >= SIGNAL_THRESHOLD,
        escalation_recommendation=_escalation_recommendation(urgency_score),
        created_at=created_at.isoformat(),
        raw_event=event,
    )


def classify_severity(score: int) -> Severity:
    if score >= CRITICAL_SIGNAL_THRESHOLD:
        return "critical"
    if score >= HIGH_SIGNAL_THRESHOLD:
        return "high"
    if score >= SIGNAL_THRESHOLD:
        return "medium"
    return "low"


def _score_components(event: SignalEvent) -> list[ScoreComponent]:
    components: list[ScoreComponent] = []
    components.extend(_vote_swing_components(event))
    components.extend(_deadline_components(event))
    components.extend(_treasury_components(event))

    if event.is_new_proposal:
        components.append(
            ScoreComponent(
                category="importance",
                rule="new_governance_proposal",
                points=10,
                reason="new governance proposal detected",
            )
        )

    if event.is_new_grant:
        components.append(
            ScoreComponent(
                category="importance",
                rule="new_grant_round",
                points=8,
                reason="new grant opportunity detected",
            )
        )

    if event.quorum_at_risk:
        components.append(
            ScoreComponent(
                category="urgency",
                rule="quorum_at_risk",
                points=20,
                reason="quorum is at risk",
            )
        )

    if event.for_vs_against_swing:
        components.append(
            ScoreComponent(
                category="urgency",
                rule="result_flipped",
                points=35,
                reason="for/against result flipped since last check",
            )
        )

    if _is_base_native(event):
        components.append(
            ScoreComponent(
                category="relevance",
                rule="base_native_program",
                points=12,
                reason="Base-native ecosystem relevance",
            )
        )

    return components


def _vote_swing_components(event: SignalEvent) -> list[ScoreComponent]:
    vote_swing = event.vote_swing_pct
    if vote_swing > 20:
        return [
            ScoreComponent(
                category="urgency",
                rule="vote_swing_gt_20",
                points=30,
                reason="vote swing above 20%",
            )
        ]
    if vote_swing > 10:
        return [
            ScoreComponent(
                category="urgency",
                rule="vote_swing_gt_10",
                points=15,
                reason="vote swing above 10%",
            )
        ]
    return []


def _deadline_components(event: SignalEvent) -> list[ScoreComponent]:
    hours = event.hours_until_deadline
    if hours < 6:
        return [
            ScoreComponent(
                category="urgency",
                rule="deadline_lt_6h",
                points=25,
                reason="deadline is under 6 hours away",
            )
        ]
    if hours < 24:
        return [
            ScoreComponent(
                category="urgency",
                rule="deadline_lt_24h",
                points=15,
                reason="deadline is under 24 hours away",
            )
        ]
    if hours < 72:
        return [
            ScoreComponent(
                category="urgency",
                rule="deadline_lt_72h",
                points=8,
                reason="deadline is under 72 hours away",
            )
        ]
    return []


def _treasury_components(event: SignalEvent) -> list[ScoreComponent]:
    impact = event.estimated_treasury_impact_usd
    if impact > 1_000_000:
        return [
            ScoreComponent(
                category="importance",
                rule="treasury_impact_gt_1m",
                points=40,
                reason="treasury impact above $1M",
            )
        ]
    if impact > 100_000:
        return [
            ScoreComponent(
                category="importance",
                rule="treasury_impact_gt_100k",
                points=20,
                reason="treasury impact above $100k",
            )
        ]
    return []


def _is_base_native(event: SignalEvent) -> bool:
    haystack = f"{event.source} {event.protocol} {event.title}".lower()
    return "base" in haystack


def _escalation_recommendation(score: int) -> str:
    if score >= CRITICAL_SIGNAL_THRESHOLD:
        return "immediate_alert"
    if score >= HIGH_SIGNAL_THRESHOLD:
        return "priority_digest"
    if score >= SIGNAL_THRESHOLD:
        return "dashboard"
    return "ignore"


def _fallback_event_id(event: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(event, sort_keys=True, default=str).encode()).hexdigest()
    return f"event:{digest[:16]}"
