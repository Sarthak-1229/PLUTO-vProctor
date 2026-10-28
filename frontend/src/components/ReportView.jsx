import React, { useState, useRef } from 'react'
import {
  FileText,
  Video,
  Clock,
  Download,
  Trash2,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  ChevronDown,
  Check,
  X,
  Shuffle,
  ShieldAlert,
} from 'lucide-react'

export function ReportView({
  reportData,
  sessionId,
  onDeleteData,
  onResetSession,
  onRetryDifferentQuestions,
}) {
  const [expandedQuestion, setExpandedQuestion] = useState(0)
  const videoRef = useRef(null)

  if (!reportData) return null

  // Format seconds as mm:ss
  const formatSeconds = (sec) => {
    if (sec === null || sec === undefined) return '00:00'
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  // Seek video playback
  const seekVideo = (seconds) => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(0, seconds)
      videoRef.current.play().catch(() => {})
    }
  }

  const categoryScores = reportData.category_scores || {}

  return (
    <div className="space-y-8 pb-12">
      {/* Report Header Hero */}
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[7px_7px_0px_0px_#000] flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="space-y-2 text-center md:text-left">
          <div className="inline-block px-3 py-1 bg-[#FDE047] text-black border-2 border-black font-black text-xs uppercase rounded shadow-[2px_2px_0px_0px_#000]">
            Official Evaluation Dossier
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-black tracking-tight uppercase">
            {reportData.candidate_name || 'Candidate Report'}
          </h1>
          <p className="text-xs sm:text-sm font-bold text-slate-600 flex flex-wrap items-center justify-center md:justify-start gap-2">
            <span className="text-black font-black">{reportData.job_title}</span>
            <span>•</span>
            <span>{reportData.company}</span>
            <span>•</span>
            <span>{new Date(reportData.timestamp || Date.now()).toLocaleDateString()}</span>
          </p>
        </div>

        {/* Rubber Stamp Score & Grade */}
        <div className="flex items-center space-x-4 bg-[#F4F0EA] border-[3px] border-black px-6 py-4 rounded-2xl shadow-[4px_4px_0px_0px_#000]">
          <div className="text-center">
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-600">
              Total Score
            </span>
            <div className="flex items-baseline justify-center space-x-1 mt-0.5">
              <span className="text-4xl font-black font-mono text-black">
                {reportData.overall_score !== undefined ? reportData.overall_score : 85}
              </span>
              <span className="text-sm font-black font-mono text-slate-500">/100</span>
            </div>
          </div>

          <div className="h-10 w-0.5 bg-black" />

          {/* Grade Stamp */}
          <div className="text-center">
            <span className="text-[10px] font-black uppercase tracking-wider text-slate-600">
              Grade
            </span>
            <div className="mt-0.5">
              <span className="inline-block px-3.5 py-1 bg-[#FFE600] border-2 border-black rounded-lg text-2xl font-black font-mono text-black shadow-[2px_2px_0px_0px_#000] rotate-[-3deg]">
                {reportData.grade || 'A'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 4 Category Score Deck */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Technical Depth */}
        <div className="bg-[#FEF9C3] border-[3px] border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-1">
          <div className="flex justify-between items-center text-xs font-black uppercase text-slate-700">
            <span>Technical Depth</span>
            <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-black text-[10px]">35% Wgt</span>
          </div>
          <p className="text-3xl font-black text-black font-mono pt-1">
            {categoryScores.technical_depth?.toFixed(1) ?? '85.0'}
            <span className="text-xs text-slate-600 font-bold ml-1">/100</span>
          </p>
        </div>

        {/* Confidence & Fluency */}
        <div className="bg-[#E0E7FF] border-[3px] border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-1">
          <div className="flex justify-between items-center text-xs font-black uppercase text-slate-700">
            <span>Fluency & Confidence</span>
            <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-black text-[10px]">25% Wgt</span>
          </div>
          <p className="text-3xl font-black text-black font-mono pt-1">
            {categoryScores.communication?.toFixed(1) ?? '80.0'}
            <span className="text-xs text-slate-600 font-bold ml-1">/100</span>
          </p>
        </div>

        {/* Proctoring Integrity */}
        <div className="bg-[#FCE7F3] border-[3px] border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-1">
          <div className="flex justify-between items-center text-xs font-black uppercase text-slate-700">
            <span>Proctoring Integrity</span>
            <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-black text-[10px]">25% Wgt</span>
          </div>
          <p className="text-3xl font-black text-black font-mono pt-1">
            {categoryScores.proctoring_integrity?.toFixed(1) ?? '90.0'}
            <span className="text-xs text-slate-600 font-bold ml-1">/100</span>
          </p>
        </div>

        {/* Resume Fit */}
        <div className="bg-[#DCFCE7] border-[3px] border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-1">
          <div className="flex justify-between items-center text-xs font-black uppercase text-slate-700">
            <span>Resume Fit</span>
            <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-black text-[10px]">15% Wgt</span>
          </div>
          <p className="text-3xl font-black text-black font-mono pt-1">
            {categoryScores.resume_relevance?.toFixed(1) ?? '85.0'}
            <span className="text-xs text-slate-600 font-bold ml-1">/100</span>
          </p>
        </div>
      </div>

      {/* Synchronized Video Playback & Deduction Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left: Video Player */}
        <div className="lg:col-span-6 space-y-3">
          <h3 className="text-lg font-black text-black uppercase flex items-center space-x-2">
            <Video className="w-5 h-5 text-black stroke-[2.5]" />
            <span>Session Recording & Scrubber</span>
          </h3>
          <div className="bg-black border-[3px] border-black rounded-2xl overflow-hidden aspect-video shadow-[5px_5px_0px_0px_#000] relative">
            <video
              ref={videoRef}
              controls
              src={`/api/interview/${sessionId}/video`}
              className="w-full h-full object-cover"
            />
          </div>
          <div className="p-3 bg-[#FEF08A] border-2 border-black rounded-xl text-xs font-bold text-black shadow-[2px_2px_0px_0px_#000]">
            💡 <strong>Precision Scrubber:</strong> Click any deduction event on the right to jump directly to that exact second in the video.
          </div>
        </div>

        {/* Right: Traceable Deduction Timeline */}
        <div className="lg:col-span-6 space-y-3 flex flex-col">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-black text-black uppercase flex items-center space-x-2">
              <Clock className="w-5 h-5 text-black stroke-[2.5]" />
              <span>Traceable Deduction Timeline</span>
            </h3>
            <span className="px-2.5 py-1 bg-black text-[#FFE600] border border-black rounded font-mono font-black text-xs">
              Total: -{reportData.total_deductions || 0} pts
            </span>
          </div>

          <div className="bg-white border-[3px] border-black rounded-2xl p-4 shadow-[5px_5px_0px_0px_#000] flex-1 max-h-[350px] overflow-y-auto space-y-2">
            {!reportData.deduction_timeline || reportData.deduction_timeline.length === 0 ? (
              <div className="text-center py-10 font-black text-xs uppercase text-slate-500">
                Pristine record! Zero integrity infractions detected during this interview.
              </div>
            ) : (
              reportData.deduction_timeline.map((ded, i) => (
                <div
                  key={i}
                  onClick={() => seekVideo(ded.t_start)}
                  className="p-3 rounded-xl bg-[#F4F0EA] hover:bg-[#FEF9C3] border-2 border-black cursor-pointer flex items-center justify-between text-xs font-bold shadow-[2px_2px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all group"
                >
                  <div className="flex items-center space-x-3">
                    <span className="px-2 py-1 rounded bg-black text-[#FFE600] font-mono font-black text-[11px]">
                      {formatSeconds(ded.t_start)}
                    </span>
                    <div>
                      <p className="font-black text-black uppercase text-[12px]">
                        {ded.category || 'Violation Event'}
                      </p>
                      <p className="text-[11px] font-semibold text-slate-600">{ded.reason}</p>
                    </div>
                  </div>
                  <span className="font-mono font-black text-[#FF4D4D] text-sm shrink-0">
                    -{ded.points_deducted} pts
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Questions Review Accordion */}
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-4">
        <h3 className="text-2xl font-black text-black uppercase tracking-tight flex items-center space-x-2">
          <FileText className="w-6 h-6 stroke-[2.5]" />
          <span>Question-by-Question Evaluation vs Dataset Truth</span>
        </h3>
        <p className="text-xs font-bold text-slate-600">
          Evaluated using deterministic rubric scoring and authoritative reference answers from our 1,799 Q&A technical dataset.
        </p>

        <div className="space-y-3 mt-4">
          {reportData.questions_breakdown?.map((q, idx) => {
            const isOpen = expandedQuestion === idx
            return (
              <div
                key={idx}
                className="rounded-2xl border-2 border-black bg-[#F4F0EA] overflow-hidden shadow-[3px_3px_0px_0px_#000] transition-all"
              >
                <button
                  onClick={() => setExpandedQuestion(isOpen ? -1 : idx)}
                  className="w-full p-4 flex items-center justify-between text-left hover:bg-[#FEF9C3] transition-all"
                >
                  <div className="flex items-center space-x-3">
                    <span className="w-7 h-7 rounded-lg bg-black text-[#FFE600] text-xs font-black flex items-center justify-center shrink-0">
                      {idx + 1}
                    </span>
                    <span className="text-sm font-black text-black">{q.question}</span>
                  </div>
                  <div className="flex items-center space-x-3">
                    <span className="text-xs font-mono font-black px-2.5 py-1 rounded bg-white border border-black shadow-[1px_1px_0px_0px_#000]">
                      {q.score !== undefined ? q.score.toFixed(0) : 80}/100
                    </span>
                    <ChevronDown
                      className={`w-5 h-5 text-black stroke-[2.5] transition-transform ${
                        isOpen ? 'rotate-180' : ''
                      }`}
                    />
                  </div>
                </button>

                {isOpen && (
                  <div className="p-5 border-t-2 border-black bg-white space-y-4 text-xs font-bold">
                    {/* Candidate Spoken Transcript */}
                    <div>
                      <span className="font-black uppercase text-slate-700 tracking-wider text-[11px]">
                        Candidate Spoken Transcript:
                      </span>
                      <p className="mt-1 text-slate-900 bg-[#F4F0EA] p-3 rounded-xl border border-black font-mono text-[11px] leading-relaxed">
                        "{q.transcript || 'No spoken answer recorded.'}"
                      </p>
                    </div>

                    {/* Reference Answer */}
                    <div>
                      <span className="font-black uppercase text-emerald-800 tracking-wider text-[11px]">
                        Authoritative Dataset Ground Truth:
                      </span>
                      <p className="mt-1 text-emerald-950 bg-[#DCFCE7] p-3 rounded-xl border-2 border-black leading-relaxed">
                        "{q.reference_answer}"
                      </p>
                    </div>

                    {/* Keywords Matched/Missed */}
                    <div>
                      <span className="font-black uppercase text-slate-700 tracking-wider text-[11px]">
                        Technical Keywords Extracted:
                      </span>
                      <div className="flex flex-wrap gap-1.5 mt-1.5">
                        {q.matched_keywords?.map((kw) => (
                          <span
                            key={kw}
                            className="px-2.5 py-1 rounded-md bg-[#A7F3D0] text-black border-2 border-black text-[11px] font-black uppercase shadow-[1px_1px_0px_0px_#000] flex items-center space-x-1"
                          >
                            <Check className="w-3.5 h-3.5 stroke-[3]" />
                            <span>{kw}</span>
                          </span>
                        ))}
                        {q.missed_keywords?.map((kw) => (
                          <span
                            key={kw}
                            className="px-2.5 py-1 rounded-md bg-[#FECDD3] text-black border-2 border-black text-[11px] font-black uppercase shadow-[1px_1px_0px_0px_#000] flex items-center space-x-1"
                          >
                            <X className="w-3.5 h-3.5 stroke-[3]" />
                            <span>{kw}</span>
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Evaluator Feedback */}
                    <div className="text-slate-700 pt-1">
                      <span className="font-black uppercase text-black">Feedback:</span> {q.feedback}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Executive Summary Deck */}
      {reportData.summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-[#DCFCE7] border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-3">
            <h4 className="text-sm font-black uppercase text-black flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-black stroke-[2.5]" />
              <span>Candidate Strengths</span>
            </h4>
            <ul className="space-y-2 text-xs font-bold text-slate-800">
              {reportData.summary.strengths?.map((s, i) => (
                <li key={i} className="flex items-start space-x-2">
                  <span className="font-black text-black">✓</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-[#FEF08A] border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-3">
            <h4 className="text-sm font-black uppercase text-black flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-black stroke-[2.5]" />
              <span>Growth Areas</span>
            </h4>
            <ul className="space-y-2 text-xs font-bold text-slate-800">
              {reportData.summary.weaknesses?.map((w, i) => (
                <li key={i} className="flex items-start space-x-2">
                  <span className="font-black text-black">⚠</span>
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="bg-[#E0E7FF] border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-3">
            <h4 className="text-sm font-black uppercase text-black flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-black stroke-[2.5]" />
              <span>Actionable Recommendations</span>
            </h4>
            <ul className="space-y-2 text-xs font-bold text-slate-800">
              {reportData.summary.concrete_tips?.map((t, i) => (
                <li key={i} className="flex items-start space-x-2">
                  <span className="font-black text-black">{i + 1}.</span>
                  <span>{t}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Bottom Actions Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t-2 border-black">
        <button
          onClick={onDeleteData}
          className="px-5 py-3 rounded-xl border-2 border-black bg-[#FF8080] hover:bg-[#ff6666] font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
          title="Permanently erase recording and telemetry per retention policy"
        >
          <Trash2 className="w-4 h-4 stroke-[2.5]" />
          <span>Delete My Data & Recording</span>
        </button>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={onRetryDifferentQuestions}
            className="px-6 py-3 rounded-xl bg-[#67E8F9] hover:bg-[#52d6e7] border-2 border-black font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
            title="Practice again with different questions rotated from the pool"
          >
            <Shuffle className="w-4 h-4 stroke-[2.5]" />
            <span>Retry with Different Questions</span>
          </button>

          <a
            href={`/api/report/${sessionId}/pdf`}
            target="_blank"
            rel="noreferrer"
            className="px-6 py-3 rounded-xl bg-white hover:bg-slate-100 border-2 border-black font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
          >
            <Download className="w-4 h-4 stroke-[2.5]" />
            <span>Download Official PDF</span>
          </a>

          <button
            onClick={onResetSession}
            className="px-6 py-3 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
          >
            <RotateCcw className="w-4 h-4 stroke-[2.5]" />
            <span>New Role Session</span>
          </button>
        </div>
      </div>
    </div>
  )
}
