'use client'

import Link from 'next/link'

export function Landing() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-4xl font-bold text-ink-50 sm:text-5xl">Base Navigator</h1>
      <p className="mt-4 max-w-2xl text-lg leading-7 text-ink-300">A calm ecosystem intelligence product for following what deserves attention across Base.</p>

      <section className="mt-10 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-white/10 bg-surface-900/72 p-6">
          <h3 className="text-lg font-semibold text-ink-50">Curated feeds</h3>
          <p className="mt-2 text-sm leading-6 text-ink-300">Priority movement across governance, grants, social momentum, and ecosystem change.</p>
        </div>
        <div className="rounded-xl border border-white/10 bg-surface-900/72 p-6">
          <h3 className="text-lg font-semibold text-ink-50">System posture</h3>
          <p className="mt-2 text-sm leading-6 text-ink-300">Secondary operational context stays quiet unless it affects the feed.</p>
        </div>
      </section>

      <div className="mt-10 flex flex-wrap gap-3">
        <Link href="/" className="rounded-md bg-base-400 px-4 py-2 font-semibold text-ink-900 transition hover:opacity-90">
          Open dashboard
        </Link>
        <Link href="/" className="rounded-md border border-white/10 px-4 py-2 text-sm text-ink-200 transition hover:border-base-400/50 hover:text-base-400">
          View signals
        </Link>
      </div>
    </main>
  )
}
