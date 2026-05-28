'use client'

import { useEffect, useMemo, useState } from 'react'
import { getFeed, getHealth } from '@/lib/api'
import type { FeedCategory, HealthResponse, SignalFeedResponse } from '@/types/api'
import { FeedView } from './FeedView'
import { MetricStrip } from './MetricStrip'
import { SystemStatus } from './SystemStatus'
import { OnboardingModal } from './OnboardingModal'

type Tab = FeedCategory | 'status'

const enableOnboarding = process.env.NEXT_PUBLIC_ENABLE_ONBOARDING === 'true'

const tabs: Array<{ id: Tab; label: string; eyebrow: string; title: string }> = [
  { id: 'signals', label: 'Signals', eyebrow: 'Global feed', title: 'Priority ecosystem signals' },
  { id: 'governance', label: 'Governance', eyebrow: 'Governance watch', title: 'Governance shifts' },
  { id: 'grants', label: 'Grants', eyebrow: 'Funding watch', title: 'Grants and opportunities' },
  { id: 'social', label: 'Social', eyebrow: 'Farcaster watch', title: 'Ecosystem attention movement' },
  { id: 'status', label: 'Status', eyebrow: 'System', title: 'System status' }
]

export function Shell() {
  const [activeTab, setActiveTab] = useState<Tab>('signals')
  const [feeds, setFeeds] = useState<Partial<Record<FeedCategory, SignalFeedResponse>>>({})
  const [health, setHealth] = useState<HealthResponse | undefined>()
  const [errors, setErrors] = useState<Partial<Record<Tab, string>>>({})
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date | undefined>()

  async function load() {
    setLoading(true)
    const nextErrors: Partial<Record<Tab, string>> = {}
    const [signals, governance, grants, social, status] = await Promise.allSettled([
      getFeed('signals'),
      getFeed('governance'),
      getFeed('grants'),
      getFeed('social'),
      getHealth()
    ])

    const nextFeeds: Partial<Record<FeedCategory, SignalFeedResponse>> = {}
    if (signals.status === 'fulfilled') nextFeeds.signals = signals.value
    else nextErrors.signals = signals.reason instanceof Error ? signals.reason.message : 'Unable to load signal feed.'
    if (governance.status === 'fulfilled') nextFeeds.governance = governance.value
    else nextErrors.governance = governance.reason instanceof Error ? governance.reason.message : 'Unable to load governance feed.'
    if (grants.status === 'fulfilled') nextFeeds.grants = grants.value
    else nextErrors.grants = grants.reason instanceof Error ? grants.reason.message : 'Unable to load grants feed.'
    if (social.status === 'fulfilled') nextFeeds.social = social.value
    else nextErrors.social = social.reason instanceof Error ? social.reason.message : 'Unable to load social feed.'
    if (status.status === 'fulfilled') setHealth(status.value)
    else nextErrors.status = status.reason instanceof Error ? status.reason.message : 'Unable to load system health.'

    setFeeds(nextFeeds)
    setErrors(nextErrors)
    setLastRefresh(new Date())
    setLoading(false)
  }

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 60000)
    return () => window.clearInterval(timer)
  }, [])

  const activeMeta = useMemo(() => tabs.find((tab) => tab.id === activeTab) || tabs[0], [activeTab])
  const activeFeed = activeTab === 'status' ? undefined : feeds[activeTab]

  return (
    <main className="min-h-screen text-ink-100">
      <div className="mx-auto flex min-h-screen w-full max-w-[1500px] flex-col px-4 py-4 lg:flex-row lg:gap-4 lg:px-5">
        <aside className="border-white/10 lg:sticky lg:top-4 lg:h-[calc(100vh-2rem)] lg:w-[236px] lg:border-r lg:pr-4">
          <div className="rounded-lg border border-white/10 bg-surface-900/78 p-4 lg:h-full">
            <div className="flex items-center justify-between gap-3 lg:block">
              <div>
                <div className="font-mono text-xs uppercase tracking-[0.18em] text-base-400">Base Navigator</div>
                <h1 className="mt-2 text-xl font-semibold text-ink-50">Intelligence terminal</h1>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void load()}
                  className="rounded-md border border-white/10 px-3 py-2 text-sm text-ink-100 transition hover:border-base-400/50 hover:text-base-400"
                >
                  Refresh
                </button>
              </div>
            </div>

            <nav className="mt-5 grid grid-cols-2 gap-2 lg:grid-cols-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveTab(tab.id)}
                  className={`rounded-md border px-3 py-3 text-left text-sm transition ${
                    activeTab === tab.id
                      ? 'border-base-400/50 bg-base-500/10 text-ink-50'
                      : 'border-white/10 bg-white/[0.03] text-ink-300 hover:border-white/20 hover:text-ink-50'
                  }`}
                >
                  <span className="block font-medium">{tab.label}</span>
                  <span className="mt-1 block font-mono text-[10px] uppercase tracking-[0.13em] text-ink-500">{tab.eyebrow}</span>
                </button>
              ))}
            </nav>

            <div className="mt-5 hidden border-t border-white/10 pt-4 lg:block">
              <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">Feed source</div>
              <p className="mt-2 text-sm leading-6 text-ink-300">Precomputed signal feed</p>
              <div className="mt-4 font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">Last refresh</div>
              <p className="mt-2 text-sm text-ink-300">{lastRefresh ? lastRefresh.toLocaleTimeString() : 'Pending'}</p>
            </div>
          </div>
        </aside>

        <section className="mt-4 min-w-0 flex-1 space-y-5 lg:mt-0">
          <MetricStrip feed={feeds.signals} health={health} />

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_330px]">
            <div className="min-w-0 rounded-lg border border-white/10 bg-surface-950/72 p-4 shadow-terminal sm:p-5">
              {activeTab === 'status' ? (
                <SystemStatus health={health} loading={loading && !health} error={errors.status} />
              ) : (
                <FeedView
                  title={activeMeta.title}
                  eyebrow={activeMeta.eyebrow}
                  feed={activeFeed}
                  loading={loading && !activeFeed}
                  error={errors[activeTab]}
                />
              )}
            </div>

            <aside className="space-y-3">
              <StatusRail health={health} feed={feeds.signals} socialFeed={feeds.social} />
            </aside>
          </div>
        </section>
      </div>
      {enableOnboarding ? <OnboardingModal onClose={() => undefined} /> : null}
    </main>
  )
}

function StatusRail({ health, feed, socialFeed }: { health?: HealthResponse; feed?: SignalFeedResponse; socialFeed?: SignalFeedResponse }) {
  const warnings = health?.stale_source_warnings || []
  const currentStatus = health?.degraded_mode ? 'Needs attention' : health?.status || 'Monitoring'
  return (
    <>
      <section className="rounded-lg border border-white/10 bg-surface-900/72 p-4">
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">Attention queue</div>
        <div className="mt-3 grid grid-cols-3 gap-2">
          <RailNumber label="Priority" value={(feed?.severity_summary?.critical ?? 0) + (feed?.severity_summary?.high ?? 0)} tone="text-rose-200" />
          <RailNumber label="Signals" value={feed?.signals_count ?? 0} tone="text-ink-50" />
          <RailNumber label="Shared" value={socialFeed?.signals_count ?? 0} tone="text-base-400" />
        </div>
      </section>

      <section className="rounded-lg border border-white/10 bg-surface-900/72 p-4">
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">System posture</div>
        <div className="mt-4 space-y-3 text-sm">
          <RailRow label="Status" value={currentStatus} tone={health?.degraded_mode ? 'text-amber-200' : 'text-emerald-200'} />
          <RailRow label="Freshness" value={warnings.length ? `${warnings.length} source warning${warnings.length === 1 ? '' : 's'}` : 'All sources current'} tone={warnings.length ? 'text-amber-200' : 'text-emerald-200'} />
          <RailRow label="Last update" value={health?.last_poll_time ? new Date(health.last_poll_time).toLocaleString() : 'Pending'} />
          <RailRow label="Next update" value={health?.next_poll_time ? new Date(health.next_poll_time).toLocaleString() : 'Pending'} />
          <RailRow label="Signals in feed" value={health?.signals_in_feed ?? 0} />
        </div>
      </section>

      <section className="rounded-lg border border-white/10 bg-surface-900/72 p-4">
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-500">Source freshness</div>
        {warnings.length ? (
          <div className="mt-3 space-y-2">
            {warnings.map((warning) => (
              <div key={warning} className="rounded border border-amber-200/20 bg-amber-950/10 px-3 py-2 font-mono text-xs text-amber-100">
                {warning}
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-3 text-sm text-emerald-200">Sources fresh</p>
        )}
      </section>
    </>
  )
}

function RailNumber({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-md border border-white/10 bg-surface-950/70 p-3">
      <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-500">{label}</div>
      <div className={`mt-2 text-2xl font-semibold ${tone}`}>{value}</div>
    </div>
  )
}

function RailRow({ label, value, tone = 'text-ink-100' }: { label: string; value: string | number; tone?: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-ink-500">{label}</span>
      <span className={`font-mono text-xs ${tone}`}>{value}</span>
    </div>
  )
}
