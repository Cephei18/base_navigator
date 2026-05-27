import type { SignalFeedResponse } from '@/types/api'
import { formatDateTime, labelize } from '@/lib/format'
import { QuietState } from './QuietState'
import { SignalCard } from './SignalCard'

type FeedViewProps = {
  title: string
  eyebrow: string
  feed?: SignalFeedResponse
  loading?: boolean
  error?: string
}

export function FeedView({ title, eyebrow, feed, loading, error }: FeedViewProps) {
  if (loading) {
    return (
      <section className="rounded-lg border border-white/10 bg-surface-900/72 p-6">
        <div className="font-mono text-xs uppercase tracking-[0.18em] text-ink-500">{eyebrow}</div>
        <h2 className="mt-3 text-2xl font-semibold text-ink-50">{title}</h2>
        <div className="mt-6 space-y-3">
          {[0, 1, 2].map((item) => (
            <div key={item} className="h-28 animate-pulse rounded-lg border border-white/10 bg-white/[0.04]" />
          ))}
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="rounded-lg border border-rose-300/20 bg-rose-950/10 p-6">
        <div className="font-mono text-xs uppercase tracking-[0.18em] text-rose-200">{eyebrow}</div>
        <h2 className="mt-3 text-2xl font-semibold text-ink-50">{title}</h2>
        <p className="mt-4 text-sm leading-6 text-rose-100">{error}</p>
      </section>
    )
  }

  if (!feed || feed.quiet_period || feed.signals.length === 0) {
    return <QuietState message={feed?.message} detail={`${labelize(feed?.category || 'all')} feed is reporting no major signals.`} />
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 border-b border-white/10 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="font-mono text-xs uppercase tracking-[0.18em] text-base-400">{eyebrow}</div>
          <h2 className="mt-3 text-2xl font-semibold text-ink-50">{title}</h2>
        </div>
        <div className="font-mono text-xs uppercase tracking-[0.14em] text-ink-500">
          {feed.signals_count} signals / {feed.source} / {formatDateTime(feed.generated_at)}
        </div>
      </div>
      <div className="space-y-3">
        {feed.signals.map((signal, index) => (
          <SignalCard key={signal.event_id || `${signal.event_type}-${index}`} signal={signal} />
        ))}
      </div>
    </section>
  )
}
