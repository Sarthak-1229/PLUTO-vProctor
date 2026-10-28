import React from 'react'
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  ArrowRight,
  RotateCcw,
  ShieldCheck,
  Check,
  X,
  FileCheck2,
} from 'lucide-react'

export function ScreeningStep({
  screeningResult,
  selectedJob,
  candidateName,
  consentChecked,
  onConsentChange,
  onProceed,
  onBack,
}) {
  if (!screeningResult) return null

  const { fit_score, status, gaps, parsed_profile } = screeningResult
  const isPassed = status === 'PASSED' || fit_score >= (selectedJob?.pass_threshold || 60)

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Screening Verdict Card */}
      <div
        className={`border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] flex flex-col sm:flex-row items-center justify-between gap-6 ${
          isPassed ? 'bg-[#DCFCE7]' : 'bg-[#FEE2E2]'
        }`}
      >
        <div className="space-y-2 text-center sm:text-left">
          <div className="inline-flex items-center space-x-1.5 px-3 py-1 bg-white border-2 border-black rounded-lg text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000]">
            <FileCheck2 className="w-4 h-4 text-black stroke-[2.5]" />
            <span>Screening Assessment</span>
          </div>
          <h2 className="text-3xl font-black text-black tracking-tight uppercase">
            {isPassed ? 'Screening Passed' : 'Potential Experience Gap Detected'}
          </h2>
          <p className="text-xs sm:text-sm font-bold text-black/80 max-w-xl">
            {isPassed
              ? `Congratulations ${candidateName || 'Candidate'}! Your background demonstrates strong alignment with the ${selectedJob?.title} requirements.`
              : `Your profile scored below the standard benchmark (${selectedJob?.pass_threshold}%). You may still choose to override and Proceed Anyway to demonstrate your capabilities in the live interview.`}
          </p>
        </div>

        {/* Score Stamp */}
        <div className="bg-white border-[3px] border-black px-6 py-4 rounded-2xl shadow-[4px_4px_0px_0px_#000] text-center shrink-0">
          <span className="text-[10px] font-black uppercase text-slate-500 tracking-wider">
            Resume Match Fit
          </span>
          <div className="flex items-baseline justify-center space-x-1 mt-0.5">
            <span className="text-4xl font-black font-mono text-black">{fit_score}</span>
            <span className="text-sm font-black font-mono text-slate-500">/100</span>
          </div>
          <span
            className={`inline-block mt-2 px-2.5 py-0.5 rounded text-[10px] font-black uppercase border border-black ${
              isPassed ? 'bg-[#A7F3D0] text-black' : 'bg-[#FF8080] text-black'
            }`}
          >
            {isPassed ? 'APPROVED' : 'BELOW THRESHOLD'}
          </span>
        </div>
      </div>

      {/* Breakdown Deck */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Matched Skills */}
        <div className="bg-white border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-4">
          <div className="flex items-center space-x-2 text-black">
            <CheckCircle2 className="w-5 h-5 text-emerald-600 stroke-[2.5]" />
            <h3 className="font-black text-sm uppercase">Demonstrated Skills & Strengths</h3>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {parsed_profile?.skills?.length > 0 ? (
              parsed_profile.skills.map((s) => (
                <span
                  key={s}
                  className="px-2.5 py-1 bg-[#DCFCE7] border border-black rounded-lg text-xs font-black uppercase text-black flex items-center space-x-1"
                >
                  <Check className="w-3.5 h-3.5 stroke-[3]" />
                  <span>{s}</span>
                </span>
              ))
            ) : (
              <span className="text-xs font-bold text-slate-500">No explicit matching skills found.</span>
            )}
          </div>
          <div className="pt-2 border-t border-black text-xs font-bold text-slate-600">
            Detected Experience: <span className="text-black font-black">{parsed_profile?.experience_years || 0} Years</span>
          </div>
        </div>

        {/* Missing Skills / Gaps */}
        <div className="bg-white border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-4">
          <div className="flex items-center space-x-2 text-black">
            <AlertTriangle className="w-5 h-5 text-amber-500 stroke-[2.5]" />
            <h3 className="font-black text-sm uppercase">Identified Skill Gaps</h3>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {gaps?.missing_skills?.length > 0 ? (
              gaps.missing_skills.map((s) => (
                <span
                  key={s}
                  className="px-2.5 py-1 bg-[#FEE2E2] border border-black rounded-lg text-xs font-black uppercase text-black flex items-center space-x-1"
                >
                  <X className="w-3.5 h-3.5 stroke-[3]" />
                  <span>{s}</span>
                </span>
              ))
            ) : (
              <span className="text-xs font-bold text-emerald-600">All required skills are covered!</span>
            )}
          </div>
          <div className="pt-2 border-t border-black text-xs font-bold text-slate-600">
            Target Experience: <span className="text-black font-black">{selectedJob?.min_experience_years || 0}+ Years</span>
          </div>
        </div>
      </div>

      {/* Instructions & Consent Box */}
      <div className="bg-white border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-4">
        <div className="flex items-center space-x-2 text-black">
          <ShieldCheck className="w-5 h-5 stroke-[2.5]" />
          <h3 className="font-black text-sm uppercase">Candidate Consent & Instructions</h3>
        </div>
        <ul className="text-xs font-bold text-slate-700 space-y-2 list-disc pl-5">
          <li>The interview consists of technical questions spoken by our AI interviewer with on-screen text.</li>
          <li>Your webcam video and microphone audio are analyzed concurrently in real-time.</li>
          <li>Continuous eye-contact tracking will monitor for screen divergence and notes reading.</li>
          <li>Please remain in a quiet, well-lit environment and look directly into your camera while answering.</li>
        </ul>

        <div className="pt-3 border-t border-black">
          <label className="flex items-center space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={consentChecked}
              onChange={(e) => onConsentChange(e.target.checked)}
              className="w-4 h-4 rounded border-2 border-black accent-[#FFE600] cursor-pointer"
            />
            <span className="text-xs font-black uppercase text-black">
              I consent to automated video, audio and attention proctoring for this interview.
            </span>
          </label>
        </div>
      </div>

      {/* Navigation Buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        <button
          onClick={onBack}
          className="w-full sm:w-auto px-5 py-3 rounded-xl bg-white hover:bg-slate-100 border-2 border-black font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000] flex items-center justify-center space-x-2"
        >
          <RotateCcw className="w-4 h-4 stroke-[2.5]" />
          <span>Choose Another Role</span>
        </button>

        <button
          disabled={!consentChecked}
          onClick={() => onProceed(isPassed ? false : true)}
          className={`w-full sm:w-auto px-8 py-3.5 rounded-xl border-[3px] border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center space-x-2 ${
            isPassed ? 'bg-[#FFE600] hover:bg-[#ffdf00]' : 'bg-[#FF8080] hover:bg-[#ff6666]'
          }`}
        >
          <span>{isPassed ? 'Continue to Pre-Flight Check' : 'Proceed Anyway (Override)'}</span>
          <ArrowRight className="w-4 h-4 stroke-[2.5]" />
        </button>
      </div>
    </div>
  )
}

