import React, { useEffect, useState } from 'react'
import {
  Shield,
  Users,
  Link2,
  ScrollText,
  Video,
  Activity,
  Search,
  Eye,
  Award,
  FileText,
  Download,
  X,
  Play,
  Clock,
  AlertTriangle,
  CheckCircle2,
  Briefcase,
  GraduationCap,
} from 'lucide-react'
import { authFetch } from '../utils/authClient'
import { AdminRoomManager } from './AdminRoomManager'

export function AdminConsolePage({ currentUser, onNavigate, onOpenSettings }) {
  const [tab, setTab] = useState('analytics') // 'analytics' | 'interviews' | 'rooms' | 'users' | 'legacy' | 'audit'
  const [legacySessions, setLegacySessions] = useState([])
  const [users, setUsers] = useState([])
  const [auditLogs, setAuditLogs] = useState([])
  const [overview, setOverview] = useState(null)
  const [claimMap, setClaimMap] = useState({})
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  // Users management state
  const [userSearch, setUserSearch] = useState('')
  const [userRoleFilter, setUserRoleFilter] = useState('all')
  const [loadingUsers, setLoadingUsers] = useState(false)
  const [selectedUserForDetails, setSelectedUserForDetails] = useState(null)
  const [userDetailsData, setUserDetailsData] = useState(null)
  const [loadingDetails, setLoadingDetails] = useState(false)
  const [selectedUserForHistory, setSelectedUserForHistory] = useState(null)
  const [userHistoryData, setUserHistoryData] = useState([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  // Role management modal state
  const [roleChangeTarget, setRoleChangeTarget] = useState(null)
  const [roleChangeValue, setRoleChangeValue] = useState('candidate')
  const [roleChangeReason, setRoleChangeReason] = useState('')
  const [roleChangeLoading, setRoleChangeLoading] = useState(false)
  const [roleChangeError, setRoleChangeError] = useState('')

  // Interviews browser state
  const [allInterviews, setAllInterviews] = useState([])
  const [interviewModeFilter, setInterviewModeFilter] = useState('all')
  const [interviewSearch, setInterviewSearch] = useState('')
  const [loadingInterviews, setLoadingInterviews] = useState(false)

  // Video recording player modal
  const [playingVideoSid, setPlayingVideoSid] = useState(null)

  const loadInitialData = async () => {
    try {
      const [legRes, usrRes, audRes, ovRes] = await Promise.all([
        authFetch('/api/admin/legacy-sessions'),
        authFetch('/api/admin/users'),
        authFetch('/api/admin/audit-logs?limit=50'),
        authFetch('/api/admin/analytics/overview'),
      ])
      if (legRes.ok) setLegacySessions((await legRes.json()).sessions || [])
      if (usrRes.ok) setUsers((await usrRes.json()).users || [])
      if (audRes.ok) setAuditLogs((await audRes.json()).audit_logs || [])
      if (ovRes.ok) setOverview(await ovRes.json())
    } catch {
      setError('Failed to load administrator console data.')
    }
  }

  const loadUsers = async (searchVal = userSearch, roleVal = userRoleFilter) => {
    setLoadingUsers(true)
    try {
      const q = new URLSearchParams()
      if (roleVal && roleVal !== 'all') q.set('role', roleVal)
      if (searchVal && searchVal.trim()) q.set('search', searchVal.trim())
      const res = await authFetch(`/api/admin/users?${q.toString()}`)
      if (res.ok) {
        const data = await res.json()
        setUsers(data.users || [])
      }
    } catch {
      setError('Failed to fetch candidate accounts.')
    } finally {
      setLoadingUsers(false)
    }
  }

  const loadInterviews = async (modeVal = interviewModeFilter, searchVal = interviewSearch) => {
    setLoadingInterviews(true)
    try {
      const q = new URLSearchParams()
      if (modeVal && modeVal !== 'all') q.set('mode', modeVal)
      if (searchVal && searchVal.trim()) q.set('search', searchVal.trim())
      const res = await authFetch(`/api/admin/interviews?${q.toString()}`)
      if (res.ok) {
        const data = await res.json()
        setAllInterviews(data.interviews || [])
      }
    } catch {
      setError('Failed to load interview history.')
    } finally {
      setLoadingInterviews(false)
    }
  }

  useEffect(() => {
    loadInitialData()
  }, [])

  useEffect(() => {
    if (tab === 'interviews') {
      loadInterviews()
    }
  }, [tab])

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
    await loadInitialData()
  }

  const handleOpenUserDetails = async (u) => {
    setSelectedUserForDetails(u)
    setUserDetailsData(null)
    setLoadingDetails(true)
    try {
      const res = await authFetch(`/api/admin/users/${u.id}`)
      if (res.ok) {
        const data = await res.json()
        setUserDetailsData(data)
      } else {
        setError('Failed to load user details.')
      }
    } catch {
      setError('Error fetching candidate profile.')
    } finally {
      setLoadingDetails(false)
    }
  }

  const handleOpenUserHistory = async (u) => {
    setSelectedUserForHistory(u)
    setUserHistoryData([])
    setLoadingHistory(true)
    try {
      const res = await authFetch(`/api/admin/users/${u.id}/history`)
      if (res.ok) {
        const data = await res.json()
        setUserHistoryData(data.sessions || [])
      } else {
        setError('Failed to load interview history.')
      }
    } catch {
      setError('Error fetching candidate history.')
    } finally {
      setLoadingHistory(false)
    }
  }

  const handlePromptRoleChange = (u) => {
    setRoleChangeTarget(u)
    setRoleChangeValue(u.role)
    setRoleChangeReason('')
    setRoleChangeError('')
  }

  const handleExecuteRoleChange = async (e) => {
    e.preventDefault()
    if (!roleChangeTarget) return
    if (!roleChangeReason.trim() || roleChangeReason.trim().length < 5) {
      setRoleChangeError('Reason must be at least 5 characters long.')
      return
    }
    setRoleChangeLoading(true)
    setRoleChangeError('')
    try {
      const res = await authFetch(`/api/admin/users/${roleChangeTarget.id}/role`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          role: roleChangeValue,
          reason: roleChangeReason.trim(),
        }),
      })
      const d = await res.json()
      if (!res.ok) {
        setRoleChangeError(d.detail || 'Failed to update role.')
        return
      }
      setMessage(`Role for ${roleChangeTarget.full_name} (${roleChangeTarget.email}) updated to ${roleChangeValue}.`)
      setRoleChangeTarget(null)
      await loadUsers()
    } catch {
      setRoleChangeError('An unexpected error occurred updating role.')
    } finally {
      setRoleChangeLoading(false)
    }
  }

  const handleReportNavigate = (sessionId) => {
    if (onNavigate) {
      onNavigate(`/report/${sessionId}`)
    } else {
      window.location.href = `/report/${sessionId}`
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-6">
        {/* Header Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-black pb-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="px-2 py-0.5 rounded bg-[#FECDD3] border border-black text-[10px] font-black uppercase">
                Role: {currentUser?.role}
              </span>
              <span className="text-xs font-bold text-gray-500">
                {currentUser?.email}
              </span>
            </div>
            <h1 className="text-2xl font-black uppercase text-black mt-1 flex items-center space-x-2">
              <Shield className="w-6 h-6 stroke-[2.5]" />
              <span>PLUTO Admin Console</span>
            </h1>
          </div>
          {onOpenSettings && (
            <button
              type="button"
              onClick={onOpenSettings}
              className="px-4 py-2 rounded-xl bg-[#FFE600] border-2 border-black text-xs font-black uppercase shadow-[3px_3px_0px_0px_#000] hover:bg-yellow-400"
            >
              Proctoring Thresholds
            </button>
          )}
        </div>

        {/* Tab Navigation */}
        <div className="flex flex-wrap gap-2 border-b-2 border-black pb-3">
          <button
            type="button"
            onClick={() => setTab('analytics')}
            className={`px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1.5 ${
              tab === 'analytics' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span>Analytics</span>
          </button>
          <button
            type="button"
            onClick={() => setTab('rooms')}
            className={`px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1.5 ${
              tab === 'rooms' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Video className="w-3.5 h-3.5" />
            <span>Interview Rooms</span>
          </button>
          <button
            type="button"
            onClick={() => setTab('interviews')}
            className={`px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1.5 ${
              tab === 'interviews' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Award className="w-3.5 h-3.5" />
            <span>Completed Interviews</span>
          </button>
          <button
            type="button"
            onClick={() => setTab('users')}
            className={`px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1.5 ${
              tab === 'users' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Users className="w-3.5 h-3.5" />
            <span>Candidate Accounts ({users.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setTab('legacy')}
            className={`px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1.5 ${
              tab === 'legacy' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Link2 className="w-3.5 h-3.5" />
            <span>Legacy Sessions ({legacySessions.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setTab('audit')}
            className={`px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1.5 ${
              tab === 'audit' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <ScrollText className="w-3.5 h-3.5" />
            <span>Audit Trail</span>
          </button>
        </div>

        {message && (
          <div className="p-3 bg-[#DCFCE7] border-2 border-black rounded-xl text-xs font-bold text-green-900 flex items-center justify-between">
            <span>{message}</span>
            <button type="button" onClick={() => setMessage('')} className="font-bold underline">Dismiss</button>
          </div>
        )}
        {error && (
          <div className="p-3 bg-[#FEE2E2] border-2 border-black rounded-xl text-xs font-bold text-red-900 flex items-center justify-between">
            <span>{error}</span>
            <button type="button" onClick={() => setError('')} className="font-bold underline">Dismiss</button>
          </div>
        )}

        {/* TAB 1: ANALYTICS OVERVIEW */}
        {tab === 'analytics' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="p-4 bg-[#FFE600] border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-1">
                <span className="text-[10px] font-black uppercase text-gray-700">Total Candidates</span>
                <p className="text-2xl font-black text-black font-mono">
                  {overview?.users?.total_candidates || 0}
                </p>
              </div>
              <div className="p-4 bg-[#DCFCE7] border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-1">
                <span className="text-[10px] font-black uppercase text-gray-700">Interviews Conducted</span>
                <p className="text-2xl font-black text-black font-mono">
                  {overview?.interviews?.total_sessions || 0}
                </p>
                <span className="text-[10px] text-gray-600 block">
                  {overview?.interviews?.self_practice_count || 0} practice • {overview?.interviews?.hosted_count || 0} hosted
                </span>
              </div>
              <div className="p-4 bg-[#E0E7FF] border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-1">
                <span className="text-[10px] font-black uppercase text-gray-700">Average Score</span>
                <p className="text-2xl font-black text-black font-mono">
                  {overview?.interviews?.average_overall_score ? `${overview.interviews.average_overall_score}%` : 'N/A'}
                </p>
              </div>
              <div className="p-4 bg-[#FCE7F3] border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-1">
                <span className="text-[10px] font-black uppercase text-gray-700">Active Rooms</span>
                <p className="text-2xl font-black text-black font-mono">
                  {overview?.rooms?.active_now || 0}
                </p>
              </div>
            </div>

            <div className="p-4 bg-[#F4F0EA] border-2 border-black rounded-2xl space-y-2">
              <h3 className="text-xs font-black uppercase text-black">Proctoring Telemetry Infractions Logged</h3>
              <p className="text-xl font-black font-mono">
                {overview?.proctoring?.total_infractions_detected || 0} total events
              </p>
              <p className="text-xs text-gray-600">
                Continuous gaze-tracking, posture monitoring, and Whisper acoustic flux analysis active across all sessions.
              </p>
            </div>
          </div>
        )}

        {/* TAB 2: INTERVIEW ROOMS MANAGER */}
        {tab === 'rooms' && (
          <AdminRoomManager users={users} onNavigate={onNavigate} />
        )}

        {/* TAB 3: COMPLETED INTERVIEWS BROWSER */}
        {tab === 'interviews' && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 bg-[#F4F0EA] p-3 border-2 border-black rounded-2xl">
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-500" />
                  <input
                    type="text"
                    value={interviewSearch}
                    onChange={(e) => {
                      setInterviewSearch(e.target.value)
                      loadInterviews(interviewModeFilter, e.target.value)
                    }}
                    placeholder="Search candidate, job, session ID..."
                    className="pl-8 pr-3 py-1.5 bg-white border-2 border-black rounded-xl text-xs font-medium outline-none w-56 sm:w-72"
                  />
                </div>
                <select
                  value={interviewModeFilter}
                  onChange={(e) => {
                    setInterviewModeFilter(e.target.value)
                    loadInterviews(e.target.value, interviewSearch)
                  }}
                  className="px-3 py-1.5 bg-white border-2 border-black rounded-xl text-xs font-bold outline-none"
                >
                  <option value="all">All Modes</option>
                  <option value="hosted">Hosted Rooms</option>
                  <option value="self_practice">Self-Practice</option>
                </select>
              </div>

              <button
                type="button"
                onClick={() => loadInterviews()}
                className="px-3 py-1.5 bg-white border-2 border-black rounded-xl text-xs font-black uppercase hover:bg-yellow-50"
              >
                Refresh
              </button>
            </div>

            {loadingInterviews ? (
              <div className="p-12 text-center text-xs font-bold text-gray-500">Loading interview sessions...</div>
            ) : allInterviews.length === 0 ? (
              <div className="p-8 border-2 border-dashed border-black rounded-2xl text-center text-xs font-bold text-gray-500">
                No interview sessions matched the filter criteria.
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[550px] overflow-y-auto pr-1">
                {allInterviews.map((sess) => (
                  <div
                    key={sess.session_id}
                    className="p-4 bg-white border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] flex flex-wrap items-center justify-between gap-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs font-black text-black">{sess.session_id}</span>
                        <span
                          className={`text-[9px] font-black uppercase px-2 py-0.5 rounded border border-black ${
                            sess.interview_mode === 'hosted'
                              ? 'bg-purple-100 text-purple-900'
                              : 'bg-blue-100 text-blue-900'
                          }`}
                        >
                          {sess.interview_mode}
                        </span>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-gray-100 border border-black">
                          {sess.interview_status}
                        </span>
                      </div>
                      <p className="text-xs font-bold text-black">
                        {sess.candidate_name || 'Candidate'} {sess.owner_email ? `(${sess.owner_email})` : ''} •{' '}
                        <span className="text-gray-700">{sess.job_title}</span>
                      </p>
                      <div className="text-[10px] text-gray-500 flex items-center space-x-3">
                        {sess.created_at && (
                          <span>Date: {new Date(sess.created_at).toLocaleString()}</span>
                        )}
                        {sess.overall_score !== null && sess.overall_score !== undefined && (
                          <span className="font-bold text-black">
                            Score: {sess.overall_score}% ({sess.grade || 'N/A'})
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      {sess.has_report ? (
                        <>
                          <button
                            type="button"
                            onClick={() => handleReportNavigate(sess.session_id)}
                            className="px-2.5 py-1.5 rounded-lg bg-[#FFE600] border-2 border-black text-[11px] font-black uppercase shadow-[1px_1px_0px_0px_#000] hover:bg-yellow-400 flex items-center space-x-1"
                          >
                            <FileText className="w-3 h-3" />
                            <span>Report</span>
                          </button>
                          <a
                            href={`/api/report/${sess.session_id}/pdf`}
                            target="_blank"
                            rel="noreferrer"
                            className="px-2.5 py-1.5 rounded-lg bg-white border-2 border-black text-[11px] font-black uppercase shadow-[1px_1px_0px_0px_#000] hover:bg-gray-100 flex items-center space-x-1"
                          >
                            <Download className="w-3 h-3" />
                            <span>PDF</span>
                          </a>
                        </>
                      ) : (
                        <span className="text-[10px] text-gray-400 font-bold px-2">No Report</span>
                      )}

                      {sess.has_recording && (
                        <button
                          type="button"
                          onClick={() => setPlayingVideoSid(sess.session_id)}
                          className="px-2.5 py-1.5 rounded-lg bg-black text-white border-2 border-black text-[11px] font-black uppercase shadow-[1px_1px_0px_0px_#000] hover:bg-gray-800 flex items-center space-x-1"
                        >
                          <Video className="w-3 h-3" />
                          <span>Video</span>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: CANDIDATE ACCOUNTS MANAGEMENT */}
        {tab === 'users' && (
          <div className="space-y-4">
            {/* Search and Filters */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-[#F4F0EA] p-3 border-2 border-black rounded-2xl">
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-gray-500" />
                  <input
                    type="text"
                    value={userSearch}
                    onChange={(e) => {
                      setUserSearch(e.target.value)
                      loadUsers(e.target.value, userRoleFilter)
                    }}
                    placeholder="Search candidate name, email, ID..."
                    className="pl-8 pr-3 py-1.5 bg-white border-2 border-black rounded-xl text-xs font-medium outline-none w-56 sm:w-72"
                  />
                </div>
                <select
                  value={userRoleFilter}
                  onChange={(e) => {
                    setUserRoleFilter(e.target.value)
                    loadUsers(userSearch, e.target.value)
                  }}
                  className="px-3 py-1.5 bg-white border-2 border-black rounded-xl text-xs font-bold outline-none"
                >
                  <option value="all">All Roles</option>
                  <option value="candidate">Candidates</option>
                  <option value="admin">Admins</option>
                  <option value="super_admin">Super Admins</option>
                </select>
              </div>

              <span className="text-xs font-bold text-gray-600">
                {users.length} {users.length === 1 ? 'account' : 'accounts'}
              </span>
            </div>

            {loadingUsers ? (
              <div className="p-12 text-center text-xs font-bold text-gray-500">Loading accounts...</div>
            ) : users.length === 0 ? (
              <div className="p-8 border-2 border-dashed border-black rounded-2xl text-center text-xs font-bold text-gray-500">
                No accounts found matching the search or role filter.
              </div>
            ) : (
              <div className="space-y-3 max-h-[550px] overflow-y-auto pr-1">
                {users.map((u) => (
                  <div
                    key={u.id}
                    className="p-4 bg-white border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] flex flex-wrap items-center justify-between gap-3"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="text-xs font-black uppercase text-black">{u.full_name}</span>
                        <span
                          className={`text-[9px] font-black uppercase px-2 py-0.5 rounded border border-black ${
                            u.role === 'super_admin'
                              ? 'bg-red-200 text-red-900'
                              : u.role === 'admin'
                              ? 'bg-[#FFE600] text-black'
                              : 'bg-blue-100 text-blue-900'
                          }`}
                        >
                          {u.role}
                        </span>
                        {u.email_verified && (
                          <span className="text-[9px] font-bold text-green-700 bg-green-50 border border-green-600 px-1.5 py-0.5 rounded">
                            Verified
                          </span>
                        )}
                      </div>
                      <p className="text-xs font-mono text-gray-600">{u.email} • ID: {u.id}</p>
                      <div className="text-[10px] text-gray-500 flex items-center space-x-3">
                        {u.created_at && (
                          <span>Joined {new Date(u.created_at).toLocaleDateString()}</span>
                        )}
                        <span>{u.interview_count || 0} interviews conducted</span>
                        {u.has_profile && (
                          <span className="text-green-700 font-bold">• Profile active</span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        type="button"
                        onClick={() => handleOpenUserDetails(u)}
                        className="px-2.5 py-1.5 bg-[#F4F0EA] border-2 border-black rounded-xl text-[11px] font-black uppercase hover:bg-yellow-50 flex items-center space-x-1"
                        title="View profile and resume metadata"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Profile</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleOpenUserHistory(u)}
                        className="px-2.5 py-1.5 bg-[#FFE600] border-2 border-black rounded-xl text-[11px] font-black uppercase shadow-[1px_1px_0px_0px_#000] hover:bg-yellow-400 flex items-center space-x-1"
                        title="View complete interview history"
                      >
                        <Clock className="w-3.5 h-3.5" />
                        <span>History ({u.interview_count || 0})</span>
                      </button>

                      {currentUser?.role === 'super_admin' && (
                        <button
                          type="button"
                          onClick={() => handlePromptRoleChange(u)}
                          className="px-2.5 py-1.5 bg-white border-2 border-black rounded-xl text-[11px] font-black uppercase hover:bg-gray-100"
                          title="Modify user role"
                        >
                          Role
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 5: UNCLAIMED LEGACY SESSIONS */}
        {tab === 'legacy' && (
          <div className="space-y-3">
            {legacySessions.length === 0 ? (
              <div className="p-6 border-2 border-dashed border-black rounded-2xl text-xs font-bold text-center text-slate-500">
                No unclaimed legacy sessions remaining. All historical sessions linked to candidate accounts.
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
                      className="w-full px-2.5 py-2 rounded-xl border-2 border-black bg-white font-bold text-xs outline-none"
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
                      className="w-full px-2.5 py-2 rounded-xl border-2 border-black bg-white font-bold text-xs outline-none"
                    />
                  </div>
                  <div className="lg:col-span-2 text-right">
                    <button
                      type="button"
                      onClick={() => handleClaim(s.session_id)}
                      className="w-full py-2 px-3 rounded-xl bg-[#FFE600] border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-yellow-400"
                    >
                      Link Session
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* TAB 6: AUDIT TRAIL */}
        {tab === 'audit' && (
          <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
            {auditLogs.map((log) => (
              <div
                key={log.id}
                className="p-3 rounded-xl border-2 border-black bg-[#F4F0EA] text-xs font-bold flex flex-wrap justify-between gap-2"
              >
                <div>
                  <span className="px-2 py-0.5 rounded bg-[#FFE600] border border-black font-mono font-black mr-2">
                    {log.action}
                  </span>
                  <span>
                    {log.resource_type} {log.resource_id || ''}
                  </span>
                </div>
                <div className="flex items-center space-x-2 text-[11px] text-slate-600 font-mono">
                  <span>Actor: {log.actor_role}</span>
                  <span>•</span>
                  <span>{log.created_at ? new Date(log.created_at).toLocaleString() : ''}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* MODAL 1: CANDIDATE PROFILE DETAILS MODAL */}
      {selectedUserForDetails && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border-2 border-black rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-[6px_6px_0px_0px_#000] space-y-4">
            <div className="flex items-center justify-between border-b-2 border-black pb-3">
              <div>
                <h3 className="text-base font-black uppercase text-black flex items-center space-x-2">
                  <Users className="w-5 h-5" />
                  <span>Candidate Profile — {selectedUserForDetails.full_name}</span>
                </h3>
                <span className="text-[11px] font-mono text-gray-500">
                  {selectedUserForDetails.email} • ID: {selectedUserForDetails.id}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedUserForDetails(null)}
                className="p-1 rounded-lg border-2 border-black hover:bg-gray-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {loadingDetails ? (
              <div className="p-8 text-center text-xs font-bold text-gray-500">Loading candidate profile...</div>
            ) : userDetailsData ? (
              <div className="space-y-4">
                {/* Stats cards */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="p-2.5 bg-[#F4F0EA] border border-black rounded-xl text-center">
                    <span className="text-[10px] font-bold text-gray-600 uppercase block">Interviews</span>
                    <span className="text-base font-black font-mono">{userDetailsData.stats?.total_sessions || 0}</span>
                  </div>
                  <div className="p-2.5 bg-[#F4F0EA] border border-black rounded-xl text-center">
                    <span className="text-[10px] font-bold text-gray-600 uppercase block">Completed</span>
                    <span className="text-base font-black font-mono">{userDetailsData.stats?.completed_sessions || 0}</span>
                  </div>
                  <div className="p-2.5 bg-[#F4F0EA] border border-black rounded-xl text-center">
                    <span className="text-[10px] font-bold text-gray-600 uppercase block">Avg Score</span>
                    <span className="text-base font-black font-mono">
                      {userDetailsData.stats?.average_score ? `${userDetailsData.stats.average_score}%` : 'N/A'}
                    </span>
                  </div>
                  <div className="p-2.5 bg-[#FFE600] border border-black rounded-xl text-center">
                    <span className="text-[10px] font-bold text-black uppercase block">Best Score</span>
                    <span className="text-base font-black font-mono">
                      {userDetailsData.stats?.highest_score ? `${userDetailsData.stats.highest_score}%` : 'N/A'}
                    </span>
                  </div>
                </div>

                {/* Profile Information */}
                {userDetailsData.profile ? (
                  <div className="space-y-3 bg-[#F4F0EA] p-4 border border-black rounded-xl">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-black uppercase text-black flex items-center space-x-1.5">
                        <Briefcase className="w-3.5 h-3.5" />
                        <span>Professional Summary</span>
                      </span>
                      {userDetailsData.profile.experience_years > 0 && (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-white border border-black">
                          {userDetailsData.profile.experience_years} Years Experience
                        </span>
                      )}
                    </div>

                    {userDetailsData.profile.headline && (
                      <p className="text-xs font-bold text-gray-800">{userDetailsData.profile.headline}</p>
                    )}

                    {userDetailsData.profile.location && (
                      <p className="text-[11px] text-gray-600">Location: {userDetailsData.profile.location}</p>
                    )}

                    {userDetailsData.profile.bio && (
                      <p className="text-xs text-gray-700 bg-white p-2.5 rounded-lg border border-black">
                        {userDetailsData.profile.bio}
                      </p>
                    )}

                    {userDetailsData.profile.technical_skills?.length > 0 && (
                      <div>
                        <span className="text-[10px] font-black uppercase text-gray-600 block mb-1">
                          Technical Competencies
                        </span>
                        <div className="flex flex-wrap gap-1">
                          {userDetailsData.profile.technical_skills.map((skill, i) => (
                            <span key={i} className="text-[10px] font-bold px-2 py-0.5 rounded bg-white border border-black">
                              {skill}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-4 bg-gray-50 border border-black rounded-xl text-xs text-gray-500 text-center">
                    Candidate has not created a detailed profile yet.
                  </div>
                )}

                {/* Resumes Library */}
                <div className="space-y-2">
                  <span className="text-xs font-black uppercase text-black flex items-center space-x-1.5">
                    <FileText className="w-3.5 h-3.5" />
                    <span>Uploaded Resumes ({userDetailsData.resumes?.length || 0})</span>
                  </span>
                  {userDetailsData.resumes?.length === 0 ? (
                    <p className="text-xs text-gray-500 italic">No resumes uploaded.</p>
                  ) : (
                    userDetailsData.resumes.map((r) => (
                      <div key={r.id} className="p-2.5 bg-white border border-black rounded-xl text-xs flex justify-between items-center">
                        <div>
                          <p className="font-bold text-black">{r.original_filename}</p>
                          <span className="text-[10px] text-gray-500">
                            {Math.round(r.file_size_bytes / 1024)} KB • Uploaded {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                          </span>
                        </div>
                        {r.skills?.length > 0 && (
                          <span className="text-[10px] font-bold px-2 py-0.5 bg-yellow-100 border border-black rounded">
                            {r.skills.length} skills parsed
                          </span>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : null}

            <div className="flex items-center justify-between pt-3 border-t-2 border-black">
              <button
                type="button"
                onClick={() => {
                  const target = selectedUserForDetails
                  setSelectedUserForDetails(null)
                  handleOpenUserHistory(target)
                }}
                className="px-3 py-1.5 rounded-xl border-2 border-black bg-[#FFE600] text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-yellow-400 flex items-center space-x-1"
              >
                <Clock className="w-3.5 h-3.5" />
                <span>View Complete History</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedUserForDetails(null)}
                className="px-4 py-2 rounded-xl border-2 border-black bg-white text-xs font-black uppercase hover:bg-gray-100"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: CANDIDATE INTERVIEW HISTORY MODAL */}
      {selectedUserForHistory && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border-2 border-black rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-[6px_6px_0px_0px_#000] space-y-4">
            <div className="flex items-center justify-between border-b-2 border-black pb-3">
              <div>
                <h3 className="text-base font-black uppercase text-black flex items-center space-x-2">
                  <Clock className="w-5 h-5" />
                  <span>Interview History — {selectedUserForHistory.full_name}</span>
                </h3>
                <span className="text-[11px] font-mono text-gray-500">
                  {selectedUserForHistory.email} • ID: {selectedUserForHistory.id}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedUserForHistory(null)}
                className="p-1 rounded-lg border-2 border-black hover:bg-gray-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {loadingHistory ? (
              <div className="p-8 text-center text-xs font-bold text-gray-500">Loading interview records...</div>
            ) : userHistoryData.length === 0 ? (
              <div className="p-8 border-2 border-dashed border-black rounded-2xl text-center text-xs font-bold text-gray-500">
                No interview sessions recorded for this candidate account yet.
              </div>
            ) : (
              <div className="space-y-3 max-h-[460px] overflow-y-auto pr-1">
                {userHistoryData.map((sess) => (
                  <div
                    key={sess.session_id}
                    className="p-3.5 bg-[#F4F0EA] border-2 border-black rounded-xl space-y-2"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs font-black text-black">{sess.session_id}</span>
                        <span
                          className={`text-[9px] font-black uppercase px-2 py-0.5 rounded border border-black ${
                            sess.interview_mode === 'hosted'
                              ? 'bg-purple-100 text-purple-900'
                              : 'bg-blue-100 text-blue-900'
                          }`}
                        >
                          {sess.interview_mode}
                        </span>
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-white border border-black">
                          {sess.interview_status}
                        </span>
                      </div>

                      {sess.overall_score !== null && sess.overall_score !== undefined && (
                        <span className="px-2 py-0.5 rounded bg-[#FFE600] border border-black text-xs font-black">
                          Score: {sess.overall_score}% ({sess.grade || 'N/A'})
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div>
                        <span className="font-bold text-black">{sess.job_title}</span>
                        {sess.company && <span className="text-gray-600"> • {sess.company}</span>}
                        {sess.created_at && (
                          <span className="text-[10px] text-gray-500 block">
                            Conducted {new Date(sess.created_at).toLocaleString()}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center space-x-2">
                        {sess.has_report && (
                          <>
                            <button
                              type="button"
                              onClick={() => handleReportNavigate(sess.session_id)}
                              className="px-2.5 py-1 rounded-lg bg-black text-white text-[11px] font-black uppercase hover:bg-gray-800 flex items-center space-x-1"
                            >
                              <FileText className="w-3 h-3" />
                              <span>View Dossier</span>
                            </button>
                            <a
                              href={`/api/report/${sess.session_id}/pdf`}
                              target="_blank"
                              rel="noreferrer"
                              className="px-2.5 py-1 rounded-lg bg-white border border-black text-[11px] font-black uppercase hover:bg-gray-100 flex items-center space-x-1"
                            >
                              <Download className="w-3 h-3" />
                              <span>PDF</span>
                            </a>
                          </>
                        )}

                        {sess.has_recording && (
                          <button
                            type="button"
                            onClick={() => setPlayingVideoSid(sess.session_id)}
                            className="px-2.5 py-1 rounded-lg bg-[#FFE600] border border-black text-[11px] font-black uppercase hover:bg-yellow-400 flex items-center space-x-1"
                          >
                            <Play className="w-3 h-3" />
                            <span>Watch</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-end pt-3 border-t-2 border-black">
              <button
                type="button"
                onClick={() => setSelectedUserForHistory(null)}
                className="px-4 py-2 rounded-xl border-2 border-black bg-white text-xs font-black uppercase hover:bg-gray-100"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: ROLE CHANGE CONFIRMATION MODAL */}
      {roleChangeTarget && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border-2 border-black rounded-2xl max-w-md w-full p-6 shadow-[6px_6px_0px_0px_#000] space-y-4">
            <div className="flex items-center justify-between border-b-2 border-black pb-3">
              <h3 className="text-base font-black uppercase text-black flex items-center space-x-2">
                <Shield className="w-5 h-5 text-red-600" />
                <span>Modify Platform Role</span>
              </h3>
              <button
                type="button"
                onClick={() => setRoleChangeTarget(null)}
                className="p-1 rounded-lg border-2 border-black hover:bg-gray-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-gray-700">
              Modifying the security role for{' '}
              <strong className="text-black font-black">{roleChangeTarget.full_name}</strong> ({roleChangeTarget.email}).
            </p>

            {roleChangeError && (
              <div className="p-3 bg-[#FECDD3] border-2 border-black rounded-xl text-xs font-bold text-red-900">
                {roleChangeError}
              </div>
            )}

            <form onSubmit={handleExecuteRoleChange} className="space-y-4">
              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Select New Role *</label>
                <select
                  value={roleChangeValue}
                  onChange={(e) => setRoleChangeValue(e.target.value)}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-bold outline-none"
                >
                  <option value="candidate">candidate (Standard Candidate)</option>
                  <option value="admin">admin (Full Admin Console)</option>
                  <option value="super_admin">super_admin (Complete Governance)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">
                  Reason for Role Change (Audit Required) *
                </label>
                <input
                  type="text"
                  value={roleChangeReason}
                  onChange={(e) => setRoleChangeReason(e.target.value)}
                  placeholder="e.g. Promoted to technical recruiter"
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium outline-none"
                  required
                />
              </div>

              <div className="p-3 bg-yellow-50 border border-black rounded-xl text-[11px] text-gray-700">
                Changing a user's role revokes active session tokens immediately by incrementing their token security version.
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2 border-t-2 border-black">
                <button
                  type="button"
                  onClick={() => setRoleChangeTarget(null)}
                  className="px-4 py-2 rounded-xl border-2 border-black bg-white text-xs font-black uppercase hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={roleChangeLoading}
                  className="px-4 py-2 rounded-xl border-2 border-black bg-red-600 text-white text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-red-700"
                >
                  {roleChangeLoading ? 'Updating...' : 'Confirm Role Update'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 4: VIDEO RECORDING PLAYER MODAL */}
      {playingVideoSid && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border-2 border-black rounded-2xl max-w-3xl w-full p-4 shadow-[6px_6px_0px_0px_#000] space-y-3">
            <div className="flex items-center justify-between border-b-2 border-black pb-2">
              <span className="text-xs font-black uppercase text-black flex items-center space-x-2">
                <Video className="w-4 h-4" />
                <span>Session Video Recording — {playingVideoSid}</span>
              </span>
              <button
                type="button"
                onClick={() => setPlayingVideoSid(null)}
                className="p-1 rounded-lg border-2 border-black hover:bg-gray-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="aspect-video bg-black rounded-xl overflow-hidden border border-black">
              <video
                controls
                autoPlay
                src={`/api/interview/${playingVideoSid}/video`}
                className="w-full h-full object-contain"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
