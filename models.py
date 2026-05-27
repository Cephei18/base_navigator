from __future__ import annotations

from typing import Any, Literal

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


class SignalFeedResponse(BaseModel):
    source: Literal["precomputed", "live_fallback"]
    generated_at: str
    category: Literal["all", "governance", "grants", "social"] = "all"
    premium: bool = False
    signals_count: int
    quiet_period: bool
    message: str
    severity_summary: dict[str, int]
    signals: list[dict[str, Any]]
    live_fallback: dict[str, Any] | None = None


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
    last_poll_time: str | None = None
    next_poll_time: str | None = None
    scheduler_running: bool = False
    last_snapshot_checked_at: str | None = None
    total_signals_generated: int = 0
    high_severity_signals: int = 0
    ignored_events_count: int = 0
    escalated_events_count: int = 0
    total_social_events_generated: int = 0
    momentum_signals_generated: int = 0
    distributed_signals_count: int = 0
    distribution_skips_count: int = 0
    distribution_cooldown_suppressions: int = 0
    signals_in_store: int = 0
    signals_in_feed: int = 0
    scoring_engine_health: str = "unknown"
    total_gemini_enrichments: int = 0
    gemini_enrichments_skipped: int = 0
    gemini_enrichment_cache_hits: int = 0
    gemini_enrichment_cache_misses: int = 0
    gemini_failures: int = 0
    gemini_fallbacks: int = 0
    gemini_calls_today: int = 0
    gemini_daily_cap: int = 50
    average_gemini_enrichment_latency_ms: float = 0.0
    last_successful_enrichment: str | None = None
    last_snapshot_success_at: str | None = None
    last_snapshot_non_empty_at: str | None = None
    last_snapshot_failure_at: str | None = None
    last_gitcoin_success_at: str | None = None
    last_gitcoin_non_empty_at: str | None = None
    last_gitcoin_failure_at: str | None = None
    last_farcaster_success_at: str | None = None
    last_farcaster_non_empty_at: str | None = None
    last_farcaster_failure_at: str | None = None
    snapshot_data_stale: bool = False
    gitcoin_data_stale: bool = False
    farcaster_data_stale: bool = False
    stale_source_warnings: list[str] = Field(default_factory=list)
