import type { HealthResponse, SignalFeedResponse } from '@/types/api'
import { formatDateTime } from '@/lib/format'

type MetricStripProps = {
  feed?: SignalFeedResponse
  health?: HealthResponse
}

export function MetricStrip({ feed, health }: MetricStripProps) {
  const highPriority = (feed?.severity_summary?.critical ?? 0) + (feed?.severity_summary?.high ?? 0)
  const sharedSignals = feed?.signals.filter((signal) => signal.published_to_farcaster).length ?? 0
  const metrics = [
    { label: 'Priority signals', value: highPriority, tone: highPriority ? 'text-rose-200' : 'text-emerald-200' },
    { label: 'Signals in view', value: feed?.signals_count ?? 0, tone: feed?.quiet_period ? 'text-emerald-200' : 'text-ink-50' },
    { label: 'Social momentum', value: sharedSignals, tone: 'text-base-400' },
    { label: 'Feed posture', value: feed?.quiet_period ? 'Quiet' : 'Active', tone: feed?.quiet_period ? 'text-emerald-200' : 'text-ink-50' }
  ]

  return (
    <section className="grid grid-cols-2 gap-2 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div key={metric.label} className="rounded-lg border border-white/10 bg-surface-900/72 px-4 py-3">
          <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">{metric.label}</div>
          <div className={`mt-2 text-xl font-semibold ${metric.tone}`}>{metric.value}</div>
        </div>
      ))}
      <div className="col-span-2 rounded-lg border border-white/10 bg-surface-900/72 px-4 py-3 sm:col-span-2 xl:col-span-4">
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">Last refresh</div>
        <div className="mt-2 text-sm text-ink-100">{formatDateTime(health?.last_poll_time)}</div>
      </div>
    </section>
  )
}
