'use client'

export function InterestBadge({ label, onClick }: { label: string; onClick?: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-full border border-white/10 px-3 py-1 text-sm text-ink-100 hover:bg-white/[0.02]"
    >
      {label}
    </button>
  )
}
