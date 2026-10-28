import React, { useState, useEffect } from 'react'
import {
  History,
  TrendingUp,
  Award,
  Calendar,
  X,
  ExternalLink,
  RotateCcw,
  Sparkles,
} from 'lucide-react'

export function CandidateDashboard({
  isOpen,
  onClose,
  onLoadPastReport,
  onRetryRole,
}) {
  const [pastSessions, setPastSessions] = useState([])

  useEffect(() => {
    try {
      const stored = localStorage.getItem('pluto_past_interviews')
      if (stored) {
        setPastSessions(JSON.parse(stored))
      }
    } catch (e) {
      console.warn('Failed to load past sessions:', e)
    }
  }, [isOpen])

  if (!isOpen) return null

  // Calculate score average
  const avgScore =
    pastSessions.length > 0
      ? (
          pastSessions.reduce((acc, s) => acc + (s.overall_score || 0), 0) /
          pastSessions.length
        ).toFixed(1)
      : 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-white border-[3px] border-black rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col shadow-[8px_8px_0px_0px_#000]">
        {/* Header */}
        <div className="p-6 border-b-2 border-black flex items-center justify-between bg-[#F4F0EA]">
          <div className="flex items-center space-x-2">
            <History className="w-5 h-5 text-black stroke-[2.5]" />
            <h2 className="text-lg font-black text-black uppercase">Candidate History & Trends</h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-slate-200 rounded-lg text-black transition-colors"
          >
            <X className="w-5 h-5 stroke-[2.5]" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Summary Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-[#FFE600] border-2 border-black p-4 rounded-xl shadow-[3px_3px_0px_0px_#000]">
              <span className="text-[10px] font-black uppercase text-slate-700">Completed Sessions</span>
              <p className="text-2xl font-black font-mono text-black mt-1">{pastSessions.length}</p>
            </div>
            <div className="bg-[#A7F3D0] border-2 border-black p-4 rounded-xl shadow-[3px_3px_0px_0px_#000]">
              <span className="text-[10px] font-black uppercase text-slate-700">Average Score</span>
              <p className="text-2xl font-black font-mono text-black mt-1">{avgScore}/100</p>
            </div>
            <div className="bg-[#67E8F9] border-2 border-black p-4 rounded-xl shadow-[3px_3px_0px_0px_#000]">
              <span className="text-[10px] font-black uppercase text-slate-700">Highest Score</span>
              <p className="text-2xl font-black font-mono text-black mt-1">
                {pastSessions.length > 0
                  ? Math.max(...pastSessions.map((s) => s.overall_score || 0))
                  : 0}
                /100
              </p>
            </div>
          </div>

          {/* Past Sessions List */}
          <div className="space-y-3">
            <h3 className="text-xs font-black uppercase text-slate-700 tracking-wider">
              Recorded Interviews
            </h3>
            {pastSessions.length === 0 ? (
              <div className="text-center py-10 border-2 border-dashed border-black rounded-xl font-bold text-xs uppercase text-slate-500">
                No previous interviews saved yet. Complete your first session to see your performance timeline!
              </div>
            ) : (
              pastSessions.map((s, idx) => (
                <div
                  key={s.session_id || idx}
                  className="p-4 rounded-xl bg-[#F4F0EA] border-2 border-black flex flex-wrap items-center justify-between gap-4 shadow-[2px_2px_0px_0px_#000] hover:-translate-y-0.5 transition-all"
                >
                  <div className="space-y-0.5">
                    <h4 className="font-black text-sm text-black">{s.job_title || 'Software Engineer'}</h4>
                    <p className="text-xs font-bold text-slate-600 flex items-center space-x-2">
                      <span>{s.company || 'Tech Corp'}</span>
                      <span>•</span>
                      <span>{new Date(s.timestamp || Date.now()).toLocaleDateString()}</span>
                    </p>
                  </div>

                  <div className="flex items-center space-x-3">
                    <div className="text-right">
                      <span className="font-mono font-black text-lg text-black">{s.overall_score || 85}</span>
                      <span className="text-xs text-slate-500 font-bold">/100</span>
                      <span className="ml-2 px-2 py-0.5 rounded bg-[#FFE600] border border-black font-mono font-black text-xs">
                        {s.grade || 'A'}
                      </span>
                    </div>

                    {s.session_id && (
                      <button
                        onClick={() => {
                          onLoadPastReport(s.session_id)
                          onClose()
                        }}
                        className="px-3 py-1.5 rounded-lg bg-white hover:bg-slate-100 border border-black text-xs font-black uppercase shadow-[1px_1px_0px_0px_#000]"
                      >
                        View Report
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t-2 border-black bg-[#F4F0EA] flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-white hover:bg-slate-100 border-2 border-black font-black text-xs uppercase shadow-[2px_2px_0px_0px_#000]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
