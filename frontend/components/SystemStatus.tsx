import type { HealthResponse } from '@/types/api'
import { formatDateTime, formatLatency } from '@/lib/format'

type SystemStatusProps = {
  health?: HealthResponse
  loading?: boolean
  error?: string
}

export function SystemStatus({ health, loading, error }: SystemStatusProps) {
  if (loading) {
    return <section className="h-80 animate-pulse rounded-lg border border-white/10 bg-white/[0.04]" />
  }

  if (error) {
    return (
      <section className="rounded-lg border border-rose-300/20 bg-rose-950/10 p-6">
        <h2 className="text-2xl font-semibold text-ink-50">System status</h2>
        <p className="mt-4 text-sm leading-6 text-rose-100">{error}</p>
      </section>
    )
  }

  const staleWarnings = health?.stale_source_warnings || []

  return (
    <section className="space-y-5">
      <div className="border-b border-white/10 pb-5">
        <div className="font-mono text-xs uppercase tracking-[0.18em] text-base-400">Operational status</div>
        <h2 className="mt-3 text-2xl font-semibold text-ink-50">System status</h2>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <StatusTile label="Scheduler" value={health?.scheduler_running ? 'Running' : 'Offline'} good={health?.scheduler_running} />
        <StatusTile label="Redis" value={health?.redis_status || 'Unknown'} good={health?.redis_status === 'connected'} />
        <StatusTile label="Scoring engine" value={health?.scoring_engine_health || 'Unknown'} good={health?.scoring_engine_health === 'healthy'} />
        <StatusTile label="Signals in feed" value={health?.signals_in_feed ?? 0} />
        <StatusTile label="Gemini calls today" value={`${health?.gemini_calls_today ?? 0}/${health?.gemini_daily_cap ?? 50}`} />
        <StatusTile label="Avg enrichment" value={formatLatency(health?.average_gemini_enrichment_latency_ms)} />
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <SourcePanel
          name="Snapshot"
          stale={Boolean(health?.snapshot_data_stale)}
          success={health?.last_snapshot_success_at}
          nonEmpty={health?.last_snapshot_non_empty_at}
          failure={health?.last_snapshot_failure_at}
        />
        <SourcePanel
          name="Gitcoin"
          stale={Boolean(health?.gitcoin_data_stale)}
          success={health?.last_gitcoin_success_at}
          nonEmpty={health?.last_gitcoin_non_empty_at}
          failure={health?.last_gitcoin_failure_at}
        />
      </div>

      <div className="rounded-lg border border-white/10 bg-surface-900/72 p-5">
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">Warnings</div>
        {staleWarnings.length ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {staleWarnings.map((warning) => (
              <span key={warning} className="rounded border border-amber-200/20 bg-amber-950/10 px-2.5 py-1 font-mono text-xs text-amber-100">
                {warning}
              </span>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-emerald-200">No stale source warnings.</p>
        )}
      </div>
    </section>
  )
}

function StatusTile({ label, value, good }: { label: string; value: string | number; good?: boolean }) {
  const tone = good === undefined ? 'text-ink-50' : good ? 'text-emerald-200' : 'text-rose-200'
  return (
    <div className="rounded-lg border border-white/10 bg-surface-900/72 p-4">
      <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">{label}</div>
      <div className={`mt-2 text-xl font-semibold ${tone}`}>{value}</div>
    </div>
  )
}

function SourcePanel({
  name,
  stale,
  success,
  nonEmpty,
  failure
}: {
  name: string
  stale: boolean
  success?: string | null
  nonEmpty?: string | null
  failure?: string | null
}) {
  return (
    <div className="rounded-lg border border-white/10 bg-surface-900/72 p-5">
      <div className="flex items-center justify-between gap-4">
        <h3 className="text-lg font-semibold text-ink-50">{name}</h3>
        <span className={`rounded border px-2.5 py-1 font-mono text-xs ${stale ? 'border-amber-200/20 text-amber-100' : 'border-emerald-200/20 text-emerald-200'}`}>
          {stale ? 'Stale' : 'Fresh'}
        </span>
      </div>
      <dl className="mt-4 space-y-3 text-sm">
        <Row label="Last success" value={formatDateTime(success)} />
        <Row label="Last non-empty" value={formatDateTime(nonEmpty)} />
        <Row label="Last failure" value={formatDateTime(failure)} />
      </dl>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-ink-500">{label}</dt>
      <dd className="text-right font-mono text-xs text-ink-300">{value}</dd>
    </div>
  )
}
