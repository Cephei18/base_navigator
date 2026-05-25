import React, { useState } from 'react'

const apiBase = import.meta.env.VITE_API_BASE_URL || ''

export default function Governance(){
  const [query,setQuery] = useState('')
  const [loading,setLoading] = useState(false)
  const [result,setResult] = useState(null)
  const [error,setError] = useState(null)

  async function handleSubmit(e){
    e.preventDefault()
    setLoading(true); setError(null); setResult(null)
    try{
      const res = await fetch(`${apiBase}/api/governance`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ prompt: query })
      })
      if(res.status === 402){
        setError('Payment required to access this endpoint. See docs to disable x402 for local dev.')
        setLoading(false)
        return
      }
      if(!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setResult(data)
    }catch(err){
      setError(String(err))
    }finally{ setLoading(false) }
  }

  return (
    <div>
      <div className="section-title">Governance Intelligence</div>
      <div className="card">
        <form onSubmit={handleSubmit}>
          <textarea value={query} onChange={e=>setQuery(e.target.value)} placeholder="Enter a governance question or snapshot" style={{width:'100%',minHeight:120,marginBottom:10,background:'transparent',color:'inherit',border:'1px solid var(--border)',padding:10}} />
          <div style={{display:'flex',gap:8}}>
            <button className="btn" disabled={loading}>{loading? 'Working...' : 'Analyze'}</button>
            <button type="button" onClick={()=>{setQuery(''); setResult(null); setError(null)}} style={{background:'transparent',border:'1px solid var(--border2)',color:'var(--text2)',padding:'8px 12px',borderRadius:8}}>Clear</button>
          </div>
        </form>
      </div>
      <div className="card">
        <div className="section-title">Result</div>
        {error && <div style={{color:'#ffb3a7'}}>{error}</div>}
        {loading && <div className="skeleton" style={{height:80}} />}
        {result && <pre style={{whiteSpace:'pre-wrap',fontSize:13,color:'var(--text2)'}}>{JSON.stringify(result,null,2)}</pre>}
      </div>
    </div>
  )
}
