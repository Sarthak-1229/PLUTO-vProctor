import React, { useState } from 'react'
import {
  Briefcase,
  Building2,
  UploadCloud,
  FileText,
  Search,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  User,
  Zap,
} from 'lucide-react'

export function RoleSelectStep({
  jobs,
  selectedJob,
  onSelectJob,
  resumeFile,
  onResumeChange,
  candidateName,
  onCandidateNameChange,
  onSubmitScreening,
  loading,
}) {
  const [searchQuery, setSearchQuery] = useState('')
  const [isDragging, setIsDragging] = useState(false)

  const filteredJobs = jobs.filter((job) => {
    const q = searchQuery.toLowerCase().trim()
    if (!q) return true
    return (
      job.title?.toLowerCase().includes(q) ||
      job.company?.toLowerCase().includes(q) ||
      job.question_domains?.some((d) => d.toLowerCase().includes(q)) ||
      job.required_skills?.some((s) => s.toLowerCase().includes(q))
    )
  })

  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onResumeChange(e.dataTransfer.files[0])
    }
  }

  return (
    <div className="space-y-8">
      {/* Hero Banner */}
      <div className="bg-[#FFE600] border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-3">
        <div className="inline-flex items-center space-x-1.5 px-3 py-1 bg-white border-2 border-black rounded-lg text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000]">
          <Sparkles className="w-4 h-4 text-black stroke-[2.5]" />
          <span>Intelligent Automated Interviewing</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-black text-black tracking-tight uppercase">
          Step 1: Choose Role & Upload Resume
        </h1>
        <p className="text-sm font-bold text-black/80 max-w-2xl">
          Select your target role and company, enter your candidate details, and upload your resume.
          Our AI parser evaluates your profile alignment and extracts personalized questions for your interview.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: Job Selection (7 Cols) */}
        <div className="lg:col-span-7 bg-white border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b-2 border-black pb-4">
            <div className="flex items-center space-x-2">
              <Briefcase className="w-5 h-5 text-black stroke-[2.5]" />
              <h2 className="text-lg font-black text-black uppercase">Available Positions ({jobs.length})</h2>
            </div>
            {/* Search Input */}
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 stroke-[2.5]" />
              <input
                type="text"
                placeholder="Search roles, skills..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-1.5 bg-[#F4F0EA] border-2 border-black rounded-lg text-xs font-bold text-black placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-[#FFE600] w-full sm:w-56"
              />
            </div>
          </div>

          {/* Job List */}
          <div className="space-y-3 max-h-[460px] overflow-y-auto pr-1">
            {filteredJobs.length === 0 ? (
              <div className="text-center py-10 font-bold text-xs uppercase text-slate-500">
                No matching positions found. Try a different query.
              </div>
            ) : (
              filteredJobs.map((job) => {
                const isSelected = selectedJob?.id === job.id
                return (
                  <div
                    key={job.id}
                    onClick={() => onSelectJob(job)}
                    className={`p-4 rounded-xl border-2 border-black cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-[#FEF9C3] shadow-[4px_4px_0px_0px_#000] -translate-y-0.5'
                        : 'bg-[#F4F0EA] hover:bg-white shadow-[2px_2px_0px_0px_#000] hover:-translate-y-0.5'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-black text-sm text-black flex items-center space-x-1.5">
                          <span>{job.title}</span>
                          {isSelected && <CheckCircle2 className="w-4 h-4 text-black stroke-[3]" />}
                        </h3>
                        <p className="text-xs font-bold text-slate-600 flex items-center space-x-1 mt-0.5">
                          <Building2 className="w-3.5 h-3.5 stroke-[2]" />
                          <span>{job.company}</span>
                          <span>•</span>
                          <span>Exp: {job.min_experience_years}+ yrs</span>
                        </p>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-black text-[#FFE600] text-[10px] font-mono font-black">
                        Pass {job.pass_threshold}%
                      </span>
                    </div>

                    {/* Skill Badges */}
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {job.required_skills?.slice(0, 5).map((skill) => (
                        <span
                          key={skill}
                          className="px-2 py-0.5 bg-white border border-black rounded text-[10px] font-black uppercase text-black"
                        >
                          {skill}
                        </span>
                      ))}
                      {job.required_skills?.length > 5 && (
                        <span className="text-[10px] font-bold text-slate-500 self-center">
                          +{job.required_skills.length - 5} more
                        </span>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Right Column: Candidate Info & Resume Upload (5 Cols) */}
        <div className="lg:col-span-5 bg-white border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div className="flex items-center space-x-2 border-b-2 border-black pb-3">
              <UploadCloud className="w-5 h-5 text-black stroke-[2.5]" />
              <h2 className="text-lg font-black text-black uppercase">Candidate Profile</h2>
            </div>

            {/* Candidate Name Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-black uppercase text-slate-700 flex items-center space-x-1">
                <User className="w-3.5 h-3.5 stroke-[2.5]" />
                <span>Full Name</span>
              </label>
              <input
                type="text"
                value={candidateName}
                onChange={(e) => onCandidateNameChange(e.target.value)}
                placeholder="e.g. Alex Morgan"
                className="w-full p-2.5 bg-[#F4F0EA] border-2 border-black rounded-lg text-xs font-bold text-black placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#FFE600]"
              />
            </div>

            {/* Resume Upload Drag & Drop Area */}
            <div className="space-y-1.5">
              <label className="text-xs font-black uppercase text-slate-700">Resume Document</label>
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed border-black rounded-xl p-6 text-center cursor-pointer transition-colors ${
                  isDragging
                    ? 'bg-[#FEF9C3]'
                    : resumeFile
                    ? 'bg-[#DCFCE7]'
                    : 'bg-[#F4F0EA] hover:bg-slate-50'
                }`}
                onClick={() => document.getElementById('resume-file-input').click()}
              >
                <input
                  id="resume-file-input"
                  type="file"
                  accept=".pdf,.docx,.txt"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files?.[0]) onResumeChange(e.target.files[0])
                  }}
                />
                <FileText className="w-10 h-10 mx-auto text-black stroke-[2] mb-2" />
                {resumeFile ? (
                  <div className="space-y-1">
                    <p className="text-xs font-black text-black break-all">{resumeFile.name}</p>
                    <p className="text-[10px] font-bold text-slate-600">
                      {(resumeFile.size / 1024).toFixed(1)} KB • Click to replace
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <p className="text-xs font-black text-black uppercase">
                      Drop your resume here, or <span className="underline">browse</span>
                    </p>
                    <p className="text-[10px] font-bold text-slate-500">Supports PDF, DOCX, TXT up to 10 MB</p>
                  </div>
                )}
              </div>
            </div>

            {/* Selected Role Summary */}
            {selectedJob && (
              <div className="p-3 bg-[#F4F0EA] border-2 border-black rounded-xl text-xs space-y-1">
                <span className="font-black text-black uppercase text-[11px]">Selected Role:</span>
                <p className="font-bold text-black">
                  {selectedJob.title} at {selectedJob.company}
                </p>
              </div>
            )}
          </div>

          {/* Submit Button */}
          <button
            disabled={!selectedJob || !resumeFile || loading}
            onClick={onSubmitScreening}
            className="w-full py-3.5 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-[3px] border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0px_0px_#000] disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center space-x-2"
          >
            {loading ? (
              <span>Analyzing Profile & Skills...</span>
            ) : (
              <>
                <span>Run Resume Screening Fit</span>
                <ArrowRight className="w-4 h-4 stroke-[2.5]" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

