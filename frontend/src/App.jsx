import React, { useState } from 'react'
import Governance from './pages/Governance'
import Grants from './pages/Grants'
import Signals from './pages/Signals'
import Health from './pages/Health'

const NAV = [
  { id: 'governance', label: 'Governance', icon: '⬡' },
  { id: 'grants', label: 'Grants', icon: '◈' },
  { id: 'signals', label: 'Signals', icon: '⊛' },
  { id: 'system', label: 'System', icon: '◉' }
]

export default function App() {
  const [page, setPage] = useState('governance')
  const Page = page === 'governance' ? Governance : page === 'grants' ? Grants : page === 'signals' ? Signals : Health

  return (
    <div className="app-root">
      <aside className="sidebar">
        <div className="brand">Base Navigator</div>
        <nav>
          {NAV.map(i => (
            <button key={i.id} onClick={() => setPage(i.id)} className={page === i.id ? 'active' : ''}>
              <span className="icon">{i.icon}</span>
              {i.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="content">
        <Page />
      </main>
      <aside className="rightpanel">
        <div className="panel-heading">System Context</div>
      </aside>
    </div>
  )
}
