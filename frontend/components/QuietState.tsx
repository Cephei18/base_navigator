type QuietStateProps = {
  message?: string
  detail?: string
}

export function QuietState({ message = 'No high-priority ecosystem signals detected.', detail }: QuietStateProps) {
  return (
    <section className="rounded-lg border border-white/10 bg-surface-900/78 px-6 py-8 shadow-terminal">
      <div className="flex items-center gap-3">
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-300 shadow-[0_0_16px_rgba(110,231,183,0.35)]" />
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-200">Quiet period</p>
      </div>
      <h2 className="mt-4 max-w-2xl text-2xl font-semibold text-ink-50">{message}</h2>
      {detail ? <p className="mt-3 max-w-2xl text-sm leading-6 text-ink-300">{detail}</p> : null}
    </section>
  )
}
