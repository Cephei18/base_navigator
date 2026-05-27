'use client'

import { useEffect, useState } from 'react'

const INTERESTS = [
  'Governance',
  'Grants & Funding',
  'Ecosystem Launches',
  'Builder Opportunities',
  'Social Momentum',
  'DeFi',
  'Infrastructure'
]

export function OnboardingModal({ onClose }: { onClose: () => void }) {
  const [selected, setSelected] = useState<string[]>([])

  useEffect(() => {
    const raw = localStorage.getItem('bn:interests')
    if (raw) setSelected(JSON.parse(raw))
  }, [])

  function toggle(interest: string) {
    setSelected((s) => (s.includes(interest) ? s.filter((x) => x !== interest) : [...s, interest]))
  }

  function save() {
    localStorage.setItem('bn:interests', JSON.stringify(selected))
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="min-w-[320px] max-w-[720px] rounded-lg bg-surface-900/80 p-6 shadow-lg">
        <h2 className="text-xl font-semibold">Welcome to Base Navigator</h2>
        <p className="mt-2 text-sm text-ink-300">Track what matters across the Base ecosystem. Pick a few interests to get started.</p>

        <div className="mt-4 grid grid-cols-2 gap-2">
          {INTERESTS.map((i) => (
            <button
              key={i}
              type="button"
              onClick={() => toggle(i)}
              className={`rounded-md border px-3 py-2 text-left text-sm transition ${selected.includes(i) ? 'border-base-400 bg-base-500/10' : 'border-white/10 bg-white/[0.02]'}`}
            >
              {i}
            </button>
          ))}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded px-3 py-2 text-sm text-ink-300">Continue as guest</button>
          <button type="button" onClick={save} className="rounded bg-base-400 px-3 py-2 text-sm text-ink-900">Start</button>
        </div>
      </div>
    </div>
  )
}
