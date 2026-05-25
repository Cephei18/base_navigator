import React, { useEffect, useState } from 'react'

const apiBase = import.meta.env.VITE_API_BASE_URL || ''

export default function Health(){
  const [health,setHealth] = useState(null)

  useEffect(()=>{
    let mounted = true
    fetch(`${apiBase}/health`).then(r=>r.json()).then(d=>{ if(mounted) setHealth(d) }).catch(()=>{})
    return ()=>{ mounted=false }
  },[])

  return (
    <div>
      <div className="section-title">System Health</div>
      <div className="card">
        {health ? <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(health,null,2)}</pre> : <div className="skeleton" style={{height:80}}/>}
      </div>
    </div>
  )
}
