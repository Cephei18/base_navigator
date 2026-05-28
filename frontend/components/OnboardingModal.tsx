'use client'

export function OnboardingModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="min-w-[320px] max-w-[560px] rounded-lg border border-white/10 bg-surface-900/90 p-6 shadow-lg">
        <h2 className="text-xl font-semibold text-ink-50">Welcome to Base Navigator</h2>
        <p className="mt-2 text-sm leading-6 text-ink-300">
          A calm view of what deserves attention across the Base ecosystem. The feed is ready; no setup is required.
        </p>

        <div className="mt-6 flex justify-end">
          <button type="button" onClick={onClose} className="rounded-md border border-white/10 px-3 py-2 text-sm text-ink-100 transition hover:border-base-400/50 hover:text-base-400">
            Continue
          </button>
        </div>
      </div>
    </div>
  )
}
