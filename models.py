from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Proposal(BaseModel):
    protocol: str
    title: str = Field(max_length=160)
    tldr: str
    voting_ends: str
    hours_remaining: int
    current_result: Literal["passing", "failing", "too close to call"]
    for_pct: float = Field(ge=0, le=100)
    impact: Literal["high", "medium", "low"] = "medium"
    source_url: str
    urgency: Literal["critical", "high", "medium", "low"]


class GovernanceResponse(BaseModel):
    as_of: str
    active_proposals: list[Proposal]
    urgent_count: int
    summary_for_agents: str


class Grant(BaseModel):
    name: str
    operator: str
    amount: str
    deadline: str | None = None
    urgency: Literal["critical", "high", "medium", "low"]
    eligibility: list[str]
    apply_url: str
    tldr: str


class GrantsResponse(BaseModel):
    as_of: str
    open_grants: list[Grant]
    urgent_deadlines: list[Grant]
    pro_tip: str


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    uptime_seconds: int
    cache_backend: str
    redis_status: Literal["connected", "unavailable", "not_configured"]
    redis_last_error: str | None = None
    rate_limit_enabled: bool
    rate_limit_backend: str
    request_id_enabled: bool
    gemini_configured: bool
    degraded_mode: bool
    degraded_reasons: list[str]
    degraded_subsystems: list[str]
    x402_enabled: bool
    total_http_requests: int
    total_rate_limited_requests: int
    total_queries_served: int
    total_usdc_earned: str
    total_usdc_earned_estimated: str
    verified_usdc_earned: str | None = None
    revenue_basis: Literal["estimated_from_queries", "verified_payments"] = "estimated_from_queries"
    last_governance_update: str | None = None
    last_grants_update: str | None = None
    total_signals_generated: int = 0
    high_severity_signals: int = 0
    ignored_events_count: int = 0
    escalated_events_count: int = 0
    signals_in_store: int = 0
    scoring_engine_health: str = "unknown"
