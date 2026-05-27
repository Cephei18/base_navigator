import type { HealthResponse, SignalFeedResponse } from '@/types/api'
import { formatDateTime, formatPercent } from '@/lib/format'

type MetricStripProps = {
  feed?: SignalFeedResponse
  health?: HealthResponse
}

export function MetricStrip({ feed, health }: MetricStripProps) {
  const capUsed = formatPercent(health?.gemini_calls_today, health?.gemini_daily_cap)
  const staleCount = health?.stale_source_warnings?.length || 0
  const metrics = [
    { label: 'Active signals', value: feed?.signals_count ?? 0, tone: feed?.quiet_period ? 'text-emerald-200' : 'text-ink-50' },
    { label: 'Critical', value: feed?.severity_summary?.critical ?? 0, tone: 'text-rose-200' },
    { label: 'High', value: feed?.severity_summary?.high ?? 0, tone: 'text-amber-200' },
    { label: 'Social', value: health?.total_social_events_generated ?? 0, tone: 'text-base-400' },
    { label: 'Scheduler', value: health?.scheduler_running ? 'Running' : 'Offline', tone: health?.scheduler_running ? 'text-emerald-200' : 'text-rose-200' },
    { label: 'Gemini cap', value: capUsed, tone: 'text-base-400' },
    { label: 'Distributed', value: health?.distributed_signals_count ?? 0, tone: 'text-cyan-200' },
    { label: 'Source warnings', value: staleCount, tone: staleCount ? 'text-amber-200' : 'text-emerald-200' }
  ]

  return (
    <section className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-8">
      {metrics.map((metric) => (
        <div key={metric.label} className="rounded-lg border border-white/10 bg-surface-900/72 px-4 py-3">
          <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">{metric.label}</div>
          <div className={`mt-2 text-xl font-semibold ${metric.tone}`}>{metric.value}</div>
        </div>
      ))}
      <div className="col-span-2 rounded-lg border border-white/10 bg-surface-900/72 px-4 py-3 sm:col-span-3 xl:col-span-8">
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">Last poll</div>
        <div className="mt-2 text-sm text-ink-100">{formatDateTime(health?.last_poll_time)}</div>
      </div>
    </section>
  )
}
