export type Severity = 'low' | 'medium' | 'high' | 'critical' | string

export type LlmEnrichment = {
  status?: string
  ecosystem_summary?: string
  why_this_matters?: string
  potential_impact?: string
  recommended_attention?: string
  confidence?: number
  risk_level?: string
  key_entities?: string[]
  follow_up_watch_items?: string[]
  [key: string]: unknown
}

export type Signal = {
  event_id?: string
  event_type?: string
  source?: string
  protocol?: string
  title?: string
  source_url?: string
  severity?: Severity
  urgency_score?: number
  importance_score?: number
  reasons?: string[]
  requires_llm_reasoning?: boolean
  notify_users?: boolean
  store_as_major_signal?: boolean
  dashboard_worthy?: boolean
  escalation_recommendation?: string
  created_at?: string
  scoring_version?: string
  llm_enrichment?: LlmEnrichment | null
  score_components?: unknown[]
  raw_event?: unknown
  published_to_farcaster?: boolean
  distribution?: Record<string, unknown> | null
}

export type SignalFeedResponse = {
  source: 'precomputed' | 'live_fallback'
  generated_at: string
  category: 'all' | 'governance' | 'grants' | 'social'
  premium: boolean
  signals_count: number
  quiet_period: boolean
  message: string
  severity_summary: Record<string, number>
  signals: Signal[]
  live_fallback?: Record<string, unknown> | null
}

export type HealthResponse = {
  status: string
  version?: string
  environment?: string
  uptime_seconds?: number
  cache_backend?: string
  redis_status?: string
  rate_limit_enabled?: boolean
  rate_limit_backend?: string
  gemini_configured?: boolean
  degraded_mode?: boolean
  degraded_reasons?: string[]
  x402_enabled?: boolean
  total_http_requests?: number
  total_queries_served?: number
  total_usdc_earned?: string
  last_poll_time?: string | null
  next_poll_time?: string | null
  scheduler_running?: boolean
  last_snapshot_checked_at?: string | null
  total_signals_generated?: number
  high_severity_signals?: number
  ignored_events_count?: number
  escalated_events_count?: number
  total_social_events_generated?: number
  momentum_signals_generated?: number
  distributed_signals_count?: number
  distribution_skips_count?: number
  distribution_cooldown_suppressions?: number
  signals_in_store?: number
  signals_in_feed?: number
  scoring_engine_health?: string
  total_gemini_enrichments?: number
  gemini_enrichments_skipped?: number
  gemini_enrichment_cache_hits?: number
  gemini_enrichment_cache_misses?: number
  gemini_failures?: number
  gemini_fallbacks?: number
  gemini_calls_today?: number
  gemini_daily_cap?: number
  average_gemini_enrichment_latency_ms?: number
  last_successful_enrichment?: string | null
  last_snapshot_success_at?: string | null
  last_snapshot_non_empty_at?: string | null
  last_snapshot_failure_at?: string | null
  last_gitcoin_success_at?: string | null
  last_gitcoin_non_empty_at?: string | null
  last_gitcoin_failure_at?: string | null
  last_farcaster_success_at?: string | null
  last_farcaster_non_empty_at?: string | null
  last_farcaster_failure_at?: string | null
  snapshot_data_stale?: boolean
  gitcoin_data_stale?: boolean
  farcaster_data_stale?: boolean
  stale_source_warnings?: string[]
}

export type FeedCategory = 'signals' | 'governance' | 'grants' | 'social'
