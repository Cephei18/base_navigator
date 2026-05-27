'use client'

import { useEffect, useState } from 'react'

export function DiagnosticsPanel({ onClose }: { onClose: () => void }) {
  const [info, setInfo] = useState<Record<string, any>>({})

  useEffect(() => {
    const payload: Record<string, any> = {
      ua: navigator.userAgent,
      locale: navigator.language,
      storage: { local: Boolean(localStorage), keys: Object.keys(localStorage).slice(0, 20) }
    }
    setInfo(payload)
  }, [])

  return (
    <div className="fixed right-4 top-4 z-50 w-[420px] rounded-lg border border-white/10 bg-surface-900/88 p-4">
      <div className="flex items-center justify-between">
        <div className="font-mono text-xs uppercase tracking-[0.12em] text-ink-500">Diagnostics</div>
        <button type="button" onClick={onClose} className="text-sm text-ink-300">Close</button>
      </div>
      <pre className="mt-3 max-h-64 overflow-auto text-xs text-ink-300">{JSON.stringify(info, null, 2)}</pre>
    </div>
  )
}
