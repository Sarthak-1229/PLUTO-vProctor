import React, { useEffect, useState } from 'react'
import { Compass, Sparkles, ArrowRight, RefreshCw } from 'lucide-react'
import { authFetch } from '../utils/authClient'

export function RecommendationsPage({ onSelectJobForInterview, onNavigate }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const loadRecommendations = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await authFetch('/api/jobs/recommendations')
      const body = await res.json()
      if (!res.ok) throw new Error(body.detail || 'Could not compute recommendations.')
      setData(body)
    } catch (err) {
      setError(err.message || 'Recommendations error.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRecommendations()
  }, [])

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-black pb-4">
          <div>
            <h1 className="text-2xl font-black uppercase text-black flex items-center space-x-2">
              <Compass className="w-6 h-6 stroke-[2.5]" />
              <span>Personalized Job Recommendations</span>
            </h1>
            <p className="text-xs font-bold text-slate-600">
              Matched immediately from your uploaded resume, manual profile skills, or both — no prior interview needed.
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => onNavigate('/profile')}
              className="px-3 py-2 rounded-xl bg-[#F4F0EA] border-2 border-black text-xs font-black uppercase"
            >
              Update Skills
            </button>
            <button
              type="button"
              onClick={loadRecommendations}
              className="px-3 py-2 rounded-xl bg-[#FFE600] border-2 border-black text-xs font-black uppercase flex items-center space-x-1 shadow-[2px_2px_0px_0px_#000]"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {loading && <div className="p-6 text-xs font-black uppercase">Computing role matches...</div>}
        {error && <div className="p-3 bg-[#FEE2E2] border-2 border-black rounded-xl text-xs font-bold">{error}</div>}

        {data && (
          <>
            <div className="flex flex-wrap items-center gap-2 text-xs font-black uppercase">
              <span className="px-3 py-1 rounded-lg bg-[#67E8F9] border-2 border-black">
                Signal Source: {data.source_type}
              </span>
              <span className="px-3 py-1 rounded-lg bg-[#DCFCE7] border-2 border-black">
                Skills Detected: {data.candidate_skills?.length || 0}
              </span>
              {!data.has_completed_interview && (
                <span className="px-3 py-1 rounded-lg bg-[#FEF08A] border-2 border-black flex items-center space-x-1">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Ready Before Your First Interview</span>
                </span>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {(data.recommendations || []).map((rec) => (
                <div
                  key={`${rec.target_type}_${rec.target_id}`}
                  className="p-5 rounded-2xl border-2 border-black bg-[#F4F0EA] shadow-[4px_4px_0px_0px_#000] flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-white border border-black">
                          {rec.company} • {rec.level}
                        </span>
                        <h3 className="font-black text-lg text-black mt-1">{rec.title}</h3>
                      </div>
                      <span className="px-2.5 py-1 rounded-xl bg-[#FFE600] border-2 border-black font-mono font-black text-sm">
                        {rec.match_score}%
                      </span>
                    </div>
                    <p className="text-xs font-bold text-slate-700">{rec.why_recommended}</p>
                    {rec.matched_skills?.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {rec.matched_skills.map((s) => (
                          <span key={s} className="px-2 py-0.5 rounded bg-[#DCFCE7] border border-black text-[10px] font-black uppercase">
                            ✓ {s}
                          </span>
                        ))}
                      </div>
                    )}
                    {rec.missing_skills?.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {rec.missing_skills.slice(0, 3).map((s) => (
                          <span key={s} className="px-2 py-0.5 rounded bg-white border border-black text-[10px] font-bold text-slate-600">
                            + {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {rec.interview_job_id && onSelectJobForInterview && (
                    <button
                      type="button"
                      onClick={() => onSelectJobForInterview(rec.interview_job_id)}
                      className="w-full py-2.5 rounded-xl bg-white hover:bg-[#FFE600] border-2 border-black font-black text-xs uppercase flex items-center justify-center space-x-1 shadow-[2px_2px_0px_0px_#000]"
                    >
                      <span>Practice Mock Interview</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

