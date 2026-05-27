'use client'

import Link from 'next/link'

export function Landing() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="text-4xl font-bold">Base Navigator</h1>
      <p className="mt-4 text-lg text-ink-300">Precomputed ecosystem intelligence: signals, momentum, and narratives for builders and operators.</p>

      <section className="mt-8 grid gap-6 sm:grid-cols-2">
        <div className="rounded-lg border border-white/10 p-6">
          <h3 className="font-semibold">Curated Feeds</h3>
          <p className="mt-2 text-sm text-ink-300">Priority signals across governance, grants, social momentum, and protocol risk.</p>
        </div>
        <div className="rounded-lg border border-white/10 p-6">
          <h3 className="font-semibold">Timeline Intelligence</h3>
          <p className="mt-2 text-sm text-ink-300">Temporal context to understand attention lifecycle and signal convergence.</p>
        </div>
      </section>

      <div className="mt-8 flex gap-3">
        <Link href="/">
          <a className="rounded bg-base-400 px-4 py-2 font-semibold text-ink-900">Open dashboard</a>
        </Link>
        <Link href="/">
          <a className="rounded border border-white/10 px-4 py-2 text-sm text-ink-300">Learn more</a>
        </Link>
      </div>
    </main>
  )
}
