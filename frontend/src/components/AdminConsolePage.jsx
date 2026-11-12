import React, { useEffect, useState } from 'react'
import { Shield, Users, Link2, ScrollText } from 'lucide-react'
import { authFetch } from '../utils/authClient'

export function AdminConsolePage({ currentUser, onOpenSettings }) {
  const [tab, setTab] = useState('legacy')
  const [legacySessions, setLegacySessions] = useState([])
  const [users, setUsers] = useState([])
  const [auditLogs, setAuditLogs] = useState([])
  const [claimMap, setClaimMap] = useState({})
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadData = async () => {
    try {
      const [legRes, usrRes, audRes] = await Promise.all([
        authFetch('/api/admin/legacy-sessions'),
        authFetch('/api/admin/users'),
        authFetch('/api/admin/audit-logs?limit=50'),
      ])
      if (legRes.ok) setLegacySessions((await legRes.json()).sessions || [])
      if (usrRes.ok) setUsers((await usrRes.json()).users || [])
      if (audRes.ok) setAuditLogs((await audRes.json()).audit_logs || [])
    } catch {
      setError('Failed to load administrator console data.')
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleClaim = async (sessionId) => {
    const entry = claimMap[sessionId] || {}
    if (!entry.target_user_id || !entry.reason || entry.reason.trim().length < 5) {
      setError('Select a target candidate account and provide a reason (at least 5 characters).')
      return
    }
    setError('')
    setMessage('')
    const res = await authFetch(`/api/admin/sessions/${sessionId}/claim`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_user_id: entry.target_user_id,
        reason: entry.reason.trim(),
      }),
    })
    const body = await res.json()
    if (!res.ok) {
      setError(body.detail || 'Claim failed.')
      return
    }
    setMessage(`Session ${sessionId} linked cleanly and recorded in audit logs.`)
    await loadData()
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-black pb-4">
          <div>
            <span className="px-2 py-0.5 rounded bg-[#FECDD3] border border-black text-[10px] font-black uppercase">
              Role: {currentUser?.role}
            </span>
            <h1 className="text-2xl font-black uppercase text-black mt-1 flex items-center space-x-2">
              <Shield className="w-6 h-6 stroke-[2.5]" />
              <span>PLUTO Admin Console</span>
            </h1>
          </div>
          {onOpenSettings && (
            <button
              type="button"
              onClick={onOpenSettings}
              className="px-4 py-2 rounded-xl bg-[#FFE600] border-2 border-black text-xs font-black uppercase shadow-[3px_3px_0px_0px_#000]"
            >
              Proctoring Thresholds
            </button>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setTab('legacy')}
            className={`px-4 py-2 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1.5 ${
              tab === 'legacy' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Link2 className="w-3.5 h-3.5" />
            <span>Unclaimed Legacy Sessions ({legacySessions.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setTab('users')}
            className={`px-4 py-2 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1.5 ${
              tab === 'users' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Accounts ({users.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setTab('audit')}
            className={`px-4 py-2 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1.5 ${
              tab === 'audit' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <ScrollText className="w-3.5 h-3.5" />
            <span>Audit Trail ({auditLogs.length})</span>
          </button>
        </div>

        {message && <div className="p-3 bg-[#DCFCE7] border-2 border-black rounded-xl text-xs font-bold">{message}</div>}
        {error && <div className="p-3 bg-[#FEE2E2] border-2 border-black rounded-xl text-xs font-bold">{error}</div>}

        {tab === 'legacy' && (
          <div className="space-y-3">
            {legacySessions.length === 0 ? (
              <div className="p-6 border-2 border-dashed border-black rounded-2xl text-xs font-bold text-center text-slate-500">
                No unclaimed legacy sessions remaining.
              </div>
            ) : (
              legacySessions.map((s) => (
                <div
                  key={s.session_id}
                  className="p-4 rounded-2xl border-2 border-black bg-[#F4F0EA] grid grid-cols-1 lg:grid-cols-12 gap-3 items-center"
                >
                  <div className="lg:col-span-5">
                    <p className="font-mono font-black text-xs text-black">{s.session_id}</p>
                    <p className="font-black text-sm text-black">
                      {s.candidate_name} — {s.job_title}
                    </p>
                    <p className="text-[11px] font-bold text-slate-600">
                      Status: {s.interview_status} {s.overall_score !== null ? `• Score ${s.overall_score}/100` : ''}
                    </p>
                  </div>
                  <div className="lg:col-span-3">
                    <select
                      value={claimMap[s.session_id]?.target_user_id || ''}
                      onChange={(e) =>
                        setClaimMap({
                          ...claimMap,
                          [s.session_id]: { ...claimMap[s.session_id], target_user_id: e.target.value },
                        })
                      }
                      className="w-full px-2.5 py-2 rounded-xl border-2 border-black bg-white font-bold text-xs"
                    >
                      <option value="">Select Verified Account...</option>
                      {users.map((u) => (
                        <option key={u.id} value={u.id}>
                          {u.full_name} ({u.email})
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="lg:col-span-2">
                    <input
                      type="text"
                      placeholder="Claim reason..."
                      value={claimMap[s.session_id]?.reason || ''}
                      onChange={(e) =>
                        setClaimMap({
                          ...claimMap,
                          [s.session_id]: { ...claimMap[s.session_id], reason: e.target.value },
                        })
                      }
                      className="w-full px-2.5 py-2 rounded-xl border-2 border-black bg-white font-bold text-xs"
                    />
                  </div>
                  <div className="lg:col-span-2 text-right">
                    <button
                      type="button"
                      onClick={() => handleClaim(s.session_id)}
                      className="w-full py-2 px-3 rounded-xl bg-[#FFE600] border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000]"
                    >
                      Link Session
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {tab === 'users' && (
          <div className="space-y-2">
            {users.map((u) => (
              <div key={u.id} className="p-3 rounded-xl border-2 border-black bg-[#F4F0EA] flex flex-wrap justify-between gap-2 text-xs font-bold">
                <span>
                  <strong className="font-black">{u.full_name}</strong> ({u.email})
                </span>
                <span className="px-2 py-0.5 rounded bg-white border border-black uppercase font-black">{u.role}</span>
              </div>
            ))}
          </div>
        )}

        {tab === 'audit' && (
          <div className="space-y-2 max-h-[420px] overflow-y-auto">
            {auditLogs.map((log) => (
              <div key={log.id} className="p-3 rounded-xl border-2 border-black bg-[#F4F0EA] text-xs font-bold flex flex-wrap justify-between gap-2">
                <div>
                  <span className="px-2 py-0.5 rounded bg-[#FFE600] border border-black font-mono font-black mr-2">
                    {log.action}
                  </span>
                  <span>
                    {log.resource_type} {log.resource_id || ''}
                  </span>
                </div>
                <span className="font-mono text-[11px] text-slate-600">{log.created_at}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

