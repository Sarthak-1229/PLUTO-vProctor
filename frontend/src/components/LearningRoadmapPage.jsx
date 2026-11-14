import React, { useState, useEffect } from 'react'
import { Compass, CheckCircle2, Clock, AlertTriangle, ArrowRight, Award, TrendingUp, Sparkles, BookOpen } from 'lucide-react'
import { authFetch } from '../utils/authClient'

export function LearningRoadmapPage({ onStartPractice, onNavigate }) {
  const [analytics, setAnalytics] = useState(null)
  const [roadmap, setRoadmap] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    async function loadRoadmapData() {
      try {
        const [aRes, rRes] = await Promise.all([
          authFetch('/api/candidate/analytics'),
          authFetch('/api/candidate/roadmap'),
        ])
        if (aRes.ok && rRes.ok) {
          const aData = await aRes.json()
          const rData = await rRes.json()
          if (active) {
            setAnalytics(aData)
            setRoadmap(rData)
          }
        } else {
          if (active) setError('Could not load learning roadmap data.')
        }
      } catch {
        if (active) setError('Network error fetching preparation roadmap.')
      } finally {
        if (active) setLoading(false)
      }
    }
    loadRoadmapData()
    return () => {
      active = false
    }
  }, [])

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto py-16 text-center font-black uppercase text-xs text-gray-500 animate-pulse">
        Synthesizing personalized learning roadmap & competency milestones...
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header Banner */}
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-black pb-4">
          <div>
            <span className="px-2.5 py-0.5 rounded-full bg-[#FFE600] border border-black text-[10px] font-black uppercase">
              Preparation & Skill Synthesis
            </span>
            <h1 className="text-2xl font-black uppercase text-black mt-1 flex items-center space-x-2">
              <Compass className="w-6 h-6 stroke-[2.5]" />
              <span>Personalized Learning Roadmap</span>
            </h1>
          </div>

          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={() => onNavigate('/')}
              className="px-4 py-2 bg-[#FFE600] border-2 border-black rounded-xl text-xs font-black uppercase shadow-[3px_3px_0px_0px_#000] hover:bg-yellow-400 flex items-center space-x-1.5"
            >
              <span>Practice Now</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {error && (
          <div className="p-3 bg-[#FECDD3] border-2 border-black rounded-xl text-xs font-bold text-red-900 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Readiness Overview Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="p-4 bg-[#FFE600] border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-1">
            <span className="text-[10px] font-black uppercase text-gray-700">Readiness Grade</span>
            <p className="text-lg font-black text-black leading-tight">
              {analytics?.readiness_grade || 'New Candidate'}
            </p>
          </div>

          <div className="p-4 bg-[#E0E7FF] border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-1">
            <span className="text-[10px] font-black uppercase text-gray-700">Average Score</span>
            <p className="text-2xl font-black text-black font-mono">
              {analytics?.average_score ? `${analytics.average_score}%` : 'N/A'}
            </p>
          </div>

          <div className="p-4 bg-[#DCFCE7] border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-1">
            <span className="text-[10px] font-black uppercase text-gray-700">Interviews Completed</span>
            <p className="text-2xl font-black text-black font-mono">
              {analytics?.completed_interviews || 0}
            </p>
          </div>

          <div className="p-4 bg-[#FCE7F3] border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-1">
            <span className="text-[10px] font-black uppercase text-gray-700">Practice Time</span>
            <p className="text-2xl font-black text-black font-mono">
              {analytics?.total_practice_minutes || 0}m
            </p>
          </div>
        </div>

        {/* Score Progression History */}
        {analytics?.score_trend && analytics.score_trend.length > 0 && (
          <div className="bg-[#F4F0EA] border-2 border-black rounded-2xl p-5 space-y-3">
            <h3 className="text-xs font-black uppercase text-black flex items-center space-x-1.5">
              <TrendingUp className="w-4 h-4" />
              <span>Historical Score Trajectory</span>
            </h3>
            <div className="flex flex-wrap items-end gap-3 pt-2">
              {analytics.score_trend.map((st, i) => (
                <div key={st.session_id || i} className="flex flex-col items-center space-y-1">
                  <span className="text-[10px] font-black font-mono">{Math.round(st.score)}%</span>
                  <div className="w-10 bg-gray-300 rounded-t-lg border-2 border-black overflow-hidden flex items-end h-24">
                    <div
                      className={`w-full ${
                        st.score >= 80 ? 'bg-green-400' : st.score >= 65 ? 'bg-yellow-400' : 'bg-red-300'
                      }`}
                      style={{ height: `${Math.max(15, Math.min(100, st.score))}%` }}
                    />
                  </div>
                  <span className="text-[9px] font-bold text-gray-600">#{st.interview_number}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Milestones Breakdown */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-black uppercase text-black">Curated Skill Milestones</h3>
            <span className="text-xs font-black px-2 py-0.5 rounded bg-black text-white">
              {roadmap?.overall_progress_pct || 0}% Completed
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {roadmap?.milestones?.map((m) => (
              <div
                key={m.id}
                className={`p-5 border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-3 ${
                  m.status === 'completed' ? 'bg-[#DCFCE7]' : 'bg-white'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    {m.status === 'completed' ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-800" />
                    ) : (
                      <Award className="w-5 h-5 text-indigo-700" />
                    )}
                    <h4 className="text-sm font-black uppercase text-black">{m.title}</h4>
                  </div>
                  <span className="text-xs font-black font-mono">
                    {Math.round(m.current_score)}% / {Math.round(m.target_score)}%
                  </span>
                </div>

                <div className="w-full h-2 bg-gray-200 border border-black rounded-full overflow-hidden">
                  <div
                    className={`h-full ${m.status === 'completed' ? 'bg-emerald-600' : 'bg-[#FFE600]'}`}
                    style={{ width: `${Math.min(100, (m.current_score / m.target_score) * 100)}%` }}
                  />
                </div>

                <ul className="space-y-1.5 text-xs font-medium text-gray-800">
                  {m.action_items.map((act, idx) => (
                    <li key={idx} className="flex items-start space-x-2">
                      <span className="text-black font-black">•</span>
                      <span>{act}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        {/* Recommended Practice Drills */}
        {roadmap?.recommended_drills && (
          <div className="p-5 bg-[#FFE600] border-2 border-black rounded-2xl space-y-3">
            <h3 className="text-xs font-black uppercase text-black flex items-center space-x-1.5">
              <Sparkles className="w-4 h-4" />
              <span>Recommended High-Impact Drills</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {roadmap.recommended_drills.map((d, i) => (
                <div key={i} className="p-4 bg-white border-2 border-black rounded-xl space-y-1 shadow-[2px_2px_0px_0px_#000]">
                  <h4 className="text-xs font-black uppercase text-black">{d.title}</h4>
                  <p className="text-[11px] font-medium text-gray-700">{d.description}</p>
                  <div className="text-[10px] font-bold text-gray-500 pt-1 flex items-center space-x-1">
                    <Clock className="w-3 h-3" />
                    <span>~{d.estimated_time_mins} minutes</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

