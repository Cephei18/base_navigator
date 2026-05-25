import React, { useState } from 'react'

const apiBase = import.meta.env.VITE_API_BASE_URL || ''

export default function Grants(){
  const [q,setQ] = useState('')
  const [loading,setLoading] = useState(false)
  const [resData,setResData] = useState(null)
  const [err,setErr] = useState(null)

  async function run(){
    setLoading(true); setErr(null); setResData(null)
    try{
      const r = await fetch(`${apiBase}/api/grants`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:q})})
      if(r.status===402){ setErr('Payment required. Configure backend for dev or set INTERNAL_KEY.'); setLoading(false); return }
      if(!r.ok) throw new Error(await r.text())
      setResData(await r.json())
    }catch(e){ setErr(String(e)) }finally{ setLoading(false) }
  }

  return (
    <div>
      <div className="section-title">Grants Assistant</div>
      <div className="card">
        <textarea value={q} onChange={e=>setQ(e.target.value)} placeholder="Describe grant criteria or ask for recommendations" style={{width:'100%',minHeight:100,background:'transparent',color:'inherit',border:'1px solid var(--border)',padding:10}} />
        <div style={{marginTop:10}}>
          <button className="btn" onClick={run} disabled={loading}>{loading? 'Working...' : 'Suggest Grants'}</button>
        </div>
      </div>
      <div className="card">
        {err && <div style={{color:'#ffb3a7'}}>{err}</div>}
        {resData && <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(resData,null,2)}</pre>}
      </div>
    </div>
  )
}
