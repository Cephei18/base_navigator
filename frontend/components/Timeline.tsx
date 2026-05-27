'use client'

import { useEffect, useState } from 'react'

export function Timeline({ eventId }: { eventId: string }) {
  const [ticks, setTicks] = useState<Array<{ ts: string; note: string }>>([])

  useEffect(() => {
    try {
      const raw = localStorage.getItem(`bn:timeline:${eventId}`)
      if (raw) setTicks(JSON.parse(raw))
      else setTicks([])
    } catch (e) {
      setTicks([])
    }
  }, [eventId])

  if (!ticks.length) return <div className="mt-3 text-sm text-ink-500">No timeline available.</div>

  return (
    <div className="mt-3 space-y-2">
      {ticks.map((t, i) => (
        <div key={i} className="flex items-start gap-3">
          <div className="h-2 w-2 rounded-full bg-base-400 mt-1" />
          <div>
            <div className="font-mono text-xs text-ink-500">{new Date(t.ts).toLocaleString()}</div>
            <div className="text-sm text-ink-100">{t.note}</div>
          </div>
        </div>
      ))}
    </div>
  )
}
