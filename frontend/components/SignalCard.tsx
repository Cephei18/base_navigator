import type { Signal } from '@/types/api'
import { formatDateTime, formatScore, labelize } from '@/lib/format'
import dynamic from 'next/dynamic'
import { useState } from 'react'

const Timeline = dynamic(() => import('./Timeline').then((m) => m.Timeline), { ssr: false })

type SignalCardProps = {
  signal: Signal
}

const severityStyles: Record<string, string> = {
  critical: 'border-l-rose-400 bg-rose-950/10 text-rose-100',
  high: 'border-l-amber-300 bg-amber-950/10 text-amber-100',
  medium: 'border-l-base-400 bg-blue-950/10 text-base-400',
  low: 'border-l-slate-400 bg-slate-900/20 text-slate-200'
}

const severityDotStyles: Record<string, string> = {
  critical: 'bg-rose-300',
  high: 'bg-amber-200',
  medium: 'bg-base-400',
  low: 'bg-slate-400'
}

export function SignalCard({ signal }: SignalCardProps) {
  const [showTimeline, setShowTimeline] = useState(false)
  const severity = String(signal.severity || 'low').toLowerCase()
  const enrichment = signal.llm_enrichment || undefined
  const title = signal.title || labelize(signal.event_type) || 'Untitled signal'
  const summary = enrichment?.ecosystem_summary || enrichment?.why_this_matters || enrichment?.potential_impact

  return (
    <article className={`rounded-lg border border-white/10 border-l-4 ${severityStyles[severity] || severityStyles.low} px-5 py-4`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${severityDotStyles[severity] || severityDotStyles.low}`} />
            <span className="font-mono text-xs uppercase tracking-[0.16em] text-ink-300">{labelize(severity)}</span>
            <span className="font-mono text-xs text-ink-500">/</span>
            <span className="font-mono text-xs uppercase tracking-[0.12em] text-ink-300">{labelize(signal.source)}</span>
            {signal.published_to_farcaster ? (
              <span className="rounded border border-cyan-200/20 bg-cyan-950/20 px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-cyan-100">
                Published
              </span>
            ) : null}
          </div>
          <h3 className="mt-3 text-lg font-semibold leading-snug text-ink-50">{title}</h3>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-300">
            <span>{signal.protocol || 'Base'}</span>
            <span className="text-ink-500">/</span>
            <span>{labelize(signal.event_type)}</span>
            <span className="text-ink-500">/</span>
            <time>{formatDateTime(signal.created_at)}</time>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:flex sm:shrink-0">
          <ScorePill label="Urgency" value={formatScore(signal.urgency_score)} />
          <ScorePill label="Importance" value={formatScore(signal.importance_score)} />
        </div>
      </div>

      {summary ? (
        <div className="mt-4 rounded-md border border-white/10 bg-black/[0.14] p-4">
          <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">Why this matters</div>
          <p className="mt-2 text-sm leading-6 text-ink-100">{String(summary)}</p>
        </div>
      ) : null}

      {enrichment?.recommended_attention ? (
        <p className="mt-3 text-sm leading-6 text-ink-300">{String(enrichment.recommended_attention)}</p>
      ) : null}

      {signal.reasons?.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {signal.reasons.slice(0, 4).map((reason) => (
            <span key={reason} className="rounded border border-white/10 bg-white/[0.04] px-2.5 py-1 font-mono text-[11px] text-ink-300">
              {reason}
            </span>
          ))}
        </div>
      ) : null}

      <div className="mt-4 flex items-center justify-between">
        <div className="text-sm text-ink-300">{signal.event_id ? `ID: ${signal.event_id}` : null}</div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setShowTimeline((s) => !s)} className="rounded px-3 py-1 text-sm border border-white/10 hover:bg-white/[0.02]">
            {showTimeline ? 'Hide timeline' : 'View timeline'}
          </button>
        </div>
      </div>

      {showTimeline && signal.event_id ? (
        <div className="mt-3 animate-fade-in">
          <Timeline eventId={signal.event_id} />
        </div>
      ) : null}
    </article>
  )
}

function ScorePill({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-[104px] rounded-md border border-white/10 bg-surface-950/70 px-3 py-2">
      <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-ink-50">{value}</div>
    </div>
  )
}
