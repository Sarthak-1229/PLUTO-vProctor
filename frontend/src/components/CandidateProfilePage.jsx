import React, { useEffect, useState } from 'react'
import {
  Save,
  UserCheck,
  Briefcase,
  GraduationCap,
  Sparkles,
  Upload,
  FileText,
  CheckCircle2,
  ArrowRight,
  RefreshCw,
  Compass,
} from 'lucide-react'
import { authFetch } from '../utils/authClient'

export function CandidateProfilePage({ onProfileSaved, onNavigate, onSelectJobForInterview }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  // Resume Upload State
  const [uploadingResume, setUploadingResume] = useState(false)
  const [uploadedResumeInfo, setUploadedResumeInfo] = useState(null)
  const [resumeNotice, setResumeNotice] = useState('')

  // Job Recommendations State
  const [recommendationsData, setRecommendationsData] = useState(null)
  const [loadingRecs, setLoadingRecs] = useState(false)

  const [form, setForm] = useState({
    full_name: '',
    headline: '',
    phone: '',
    location: '',
    education_level: 'Bachelor',
    experience_years: 0,
    skillsText: '',
    preferredRolesText: '',
    githubUrl: '',
    linkedinUrl: '',
    bio: '',
  })

  const loadRecommendations = async () => {
    setLoadingRecs(true)
    try {
      const res = await authFetch('/api/jobs/recommendations')
      if (res.ok) {
        const body = await res.json()
        setRecommendationsData(body)
      }
    } catch (err) {
      console.warn('Failed to fetch recommendations:', err)
    } finally {
      setLoadingRecs(false)
    }
  }

  useEffect(() => {
    let active = true
    authFetch('/api/candidate/profile')
      .then((res) => res.json())
      .then((data) => {
        if (!active || !data.profile) return
        const p = data.profile
        setForm({
          full_name: p.full_name || '',
          headline: p.headline || '',
          phone: p.phone || '',
          location: p.location || '',
          education_level: p.education_level || 'Bachelor',
          experience_years: Number(p.experience_years || 0),
          skillsText: (p.technical_skills || []).join(', '),
          preferredRolesText: (p.preferred_roles || []).join(', '),
          githubUrl: p.portfolio_links?.github || '',
          linkedinUrl: p.portfolio_links?.linkedin || '',
          bio: p.bio || '',
        })
      })
      .catch(() => setError('Unable to load candidate profile.'))
      .finally(() => {
        if (active) setLoading(false)
      })

    // Fetch latest recommendations on initial load
    loadRecommendations()

    return () => {
      active = false
    }
  }, [])

  const handleResumeUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingResume(true)
    setResumeNotice('')
    setError('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await authFetch('/api/resumes/upload', {
        method: 'POST',
        body: fd,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Resume upload failed.')

      const eff = data.resume_profile?.effective_data || {}
      const extractedSkills = eff.skills || []
      const extractedExp = Number(eff.experience_years || 0)
      const extractedDegree = eff.education?.degree || ''
      const candidateName = eff.candidate_name || ''

      // Auto-populate form fields from parsed resume
      setForm((prev) => {
        const existingSkills = prev.skillsText
          ? prev.skillsText.split(',').map((s) => s.trim()).filter(Boolean)
          : []
        const mergedSkills = Array.from(new Set([...existingSkills, ...extractedSkills]))

        return {
          ...prev,
          full_name: prev.full_name || candidateName,
          skillsText: mergedSkills.join(', '),
          experience_years: prev.experience_years > 0 ? prev.experience_years : extractedExp,
          education_level: extractedDegree && extractedDegree !== 'None' ? extractedDegree : prev.education_level,
        }
      })

      setUploadedResumeInfo({
        filename: file.name,
        skillsCount: extractedSkills.length,
        experienceYears: extractedExp,
        degree: extractedDegree,
      })

      setResumeNotice(
        `Resume "${file.name}" uploaded and parsed cleanly. Extracted ${extractedSkills.length} skills, education level, and experience into your profile.`
      )

      // Refresh job recommendations immediately reflecting parsed resume
      await loadRecommendations()
    } catch (err) {
      setError(err.message || 'Resume upload failed.')
    } finally {
      setUploadingResume(false)
      // reset file input
      e.target.value = ''
    }
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const payload = {
        full_name: form.full_name,
        headline: form.headline,
        phone: form.phone,
        location: form.location,
        education_level: form.education_level,
        experience_years: Number(form.experience_years || 0),
        technical_skills: form.skillsText.split(',').map((s) => s.trim()).filter(Boolean),
        preferred_roles: form.preferredRolesText.split(',').map((s) => s.trim()).filter(Boolean),
        portfolio_links: {
          ...(form.githubUrl ? { github: form.githubUrl } : {}),
          ...(form.linkedinUrl ? { linkedin: form.linkedinUrl } : {}),
        },
        bio: form.bio,
      }
      const res = await authFetch('/api/candidate/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Save failed.')
      setMessage('Profile saved to database cleanly. Your job recommendations reflect these skills immediately.')
      if (onProfileSaved) onProfileSaved(data.profile)

      // Refresh recommendations to reflect updated skills
      await loadRecommendations()
    } catch (err) {
      setError(err.message || 'Save error.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <div className="p-8 font-black uppercase text-sm">Loading candidate profile...</div>
  }

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* 1. Header & Navigation */}
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000]">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-black pb-4 mb-6">
          <div>
            <h1 className="text-2xl font-black uppercase text-black flex items-center space-x-2">
              <UserCheck className="w-6 h-6 stroke-[2.5]" />
              <span>Candidate Profile & Suitable Job Roles</span>
            </h1>
            <p className="text-xs font-bold text-slate-600 mt-1">
              Upload your resume and complete your profile. Our system analyzes your skills to recommend tailored job roles and practice interviews.
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => onNavigate('/resumes')}
              className="px-3.5 py-2 rounded-xl bg-[#F4F0EA] hover:bg-[#FFE600] border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1.5"
            >
              <FileText className="w-4 h-4" />
              <span>Resume Library</span>
            </button>
            <button
              type="button"
              onClick={() => onNavigate('/recommendations')}
              className="px-3.5 py-2 rounded-xl bg-[#A7F3D0] hover:bg-[#6EE7B7] border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1.5"
            >
              <Compass className="w-4 h-4" />
              <span>Full Recommendations</span>
            </button>
          </div>
        </div>

        {message && <div className="mb-4 p-3 bg-[#DCFCE7] border-2 border-black rounded-xl text-xs font-bold text-black">{message}</div>}
        {resumeNotice && <div className="mb-4 p-3 bg-[#DCFCE7] border-2 border-black rounded-xl text-xs font-bold text-black flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-700 shrink-0 stroke-[2.5]" />
          <span>{resumeNotice}</span>
        </div>}
        {error && <div className="mb-4 p-3 bg-[#FEE2E2] border-2 border-black rounded-xl text-xs font-bold text-black">{error}</div>}

        {/* 2. Upload Resume Section */}
        <div className="mb-8 p-5 bg-[#F4F0EA] border-2 border-black rounded-2xl shadow-[4px_4px_0px_0px_#000] space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <Upload className="w-5 h-5 text-black stroke-[2.5]" />
              <h3 className="font-black text-sm uppercase text-black">Upload Resume to Auto-Fill Profile & Recommendations</h3>
            </div>
            <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-white border border-black">
              PDF, DOCX, TXT (Max 5MB)
            </span>
          </div>
          <p className="text-xs font-bold text-slate-700">
            Our multithreaded parser extracts your technical skills, experience intervals, and education to automatically recommend matching job roles.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <label className={`px-4 py-2.5 rounded-xl border-2 border-black font-black text-xs uppercase cursor-pointer shadow-[2px_2px_0px_0px_#000] inline-flex items-center space-x-2 ${
              uploadingResume ? 'bg-slate-300 cursor-not-allowed' : 'bg-[#67E8F9] hover:bg-[#22D3EE]'
            }`}>
              <Upload className="w-4 h-4 stroke-[2.5]" />
              <span>{uploadingResume ? 'Analyzing Resume...' : 'Choose Resume File'}</span>
              <input
                type="file"
                accept=".pdf,.docx,.txt"
                disabled={uploadingResume}
                onChange={handleResumeUpload}
                className="hidden"
              />
            </label>

            {uploadedResumeInfo && (
              <div className="flex flex-wrap items-center gap-2 text-xs font-black">
                <span className="px-2.5 py-1 bg-white border border-black rounded-lg">
                  {uploadedResumeInfo.filename}
                </span>
                <span className="px-2.5 py-1 bg-[#DCFCE7] border border-black rounded-lg text-emerald-800">
                  {uploadedResumeInfo.skillsCount} Skills Parsed
                </span>
                {uploadedResumeInfo.degree && (
                  <span className="px-2.5 py-1 bg-[#FEF08A] border border-black rounded-lg text-amber-900">
                    {uploadedResumeInfo.degree}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* 3. Candidate Details Form */}
        <form onSubmit={handleSave} className="space-y-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase">Full Name</span>
              <input
                type="text"
                required
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase">Headline</span>
              <input
                type="text"
                placeholder="e.g., Information Security Analyst & Cloud Specialist"
                value={form.headline}
                onChange={(e) => setForm({ ...form, headline: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase">Location</span>
              <input
                type="text"
                placeholder="e.g., Pune, India / Remote"
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase">Phone</span>
              <input
                type="text"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase flex items-center space-x-1">
                <GraduationCap className="w-3.5 h-3.5" />
                <span>Highest Education</span>
              </span>
              <select
                value={form.education_level}
                onChange={(e) => setForm({ ...form, education_level: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              >
                <option value="Diploma">Diploma</option>
                <option value="Bachelor">Bachelor</option>
                <option value="Master">Master</option>
                <option value="PhD">PhD</option>
                <option value="None">Self-Taught / Bootcamp</option>
              </select>
            </label>

            <label className="block space-y-1">
              <span className="text-xs font-black uppercase flex items-center space-x-1">
                <Briefcase className="w-3.5 h-3.5" />
                <span>Experience Years</span>
              </span>
              <input
                type="number"
                min={0}
                max={60}
                step={0.5}
                value={form.experience_years}
                onChange={(e) => setForm({ ...form, experience_years: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-xs font-black uppercase">Technical Skills (comma-separated)</span>
            <input
              type="text"
              placeholder="e.g., Python, Network Security, Docker, Linux, SQL, AWS, Cryptography"
              value={form.skillsText}
              onChange={(e) => setForm({ ...form, skillsText: e.target.value })}
              className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-xs font-black uppercase">Target / Preferred Roles (comma-separated)</span>
            <input
              type="text"
              placeholder="e.g., Information Security Analyst, Backend Developer, Cloud Engineer"
              value={form.preferredRolesText}
              onChange={(e) => setForm({ ...form, preferredRolesText: e.target.value })}
              className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
            />
          </label>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase">GitHub URL</span>
              <input
                type="url"
                value={form.githubUrl}
                onChange={(e) => setForm({ ...form, githubUrl: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase">LinkedIn URL</span>
              <input
                type="url"
                value={form.linkedinUrl}
                onChange={(e) => setForm({ ...form, linkedinUrl: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
          </div>

          <label className="block space-y-1">
            <span className="text-xs font-black uppercase">Summary / Bio</span>
            <textarea
              rows={3}
              value={form.bio}
              onChange={(e) => setForm({ ...form, bio: e.target.value })}
              className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
            />
          </label>

          <button
            type="submit"
            disabled={saving}
            className="px-6 py-3 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black font-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] flex items-center space-x-2"
          >
            <Save className="w-4 h-4 stroke-[2.5]" />
            <span>{saving ? 'Saving Profile...' : 'Save Profile & Recalculate Job Matches'}</span>
          </button>
        </form>
      </div>

      {/* 4. Integrated Suitable Job Roles Section */}
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-black pb-4">
          <div>
            <div className="flex items-center space-x-2">
              <Compass className="w-6 h-6 stroke-[2.5] text-black" />
              <h2 className="text-xl font-black uppercase text-black">
                Suitable Job Roles Recommended For You
              </h2>
            </div>
            <p className="text-xs font-bold text-slate-600 mt-1">
              Computed in real time from your uploaded resume skills and candidate profile. Practice with targeted mock interviews.
            </p>
          </div>
          <button
            type="button"
            onClick={loadRecommendations}
            disabled={loadingRecs}
            className="px-3.5 py-1.5 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black font-black text-xs uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loadingRecs ? 'animate-spin' : ''}`} />
            <span>{loadingRecs ? 'Calculating...' : 'Refresh Matches'}</span>
          </button>
        </div>

        {loadingRecs && (
          <div className="py-8 text-center text-xs font-black uppercase tracking-wider text-slate-600">
            Evaluating skill alignments across 12 target roles...
          </div>
        )}

        {!loadingRecs && recommendationsData && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2 text-xs font-black uppercase">
              <span className="px-3 py-1 rounded-lg bg-[#67E8F9] border-2 border-black">
                Source: {recommendationsData.source_type}
              </span>
              <span className="px-3 py-1 rounded-lg bg-[#DCFCE7] border-2 border-black text-emerald-900">
                Skills Analyzed: {recommendationsData.candidate_skills?.length || 0}
              </span>
              <span className="px-3 py-1 rounded-lg bg-[#FEF08A] border-2 border-black text-amber-900 flex items-center space-x-1">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Ready Before First Interview</span>
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              {(recommendationsData.recommendations || []).slice(0, 6).map((rec) => (
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
                        <h3 className="font-black text-base text-black mt-1 leading-snug">{rec.title}</h3>
                      </div>
                      <span className="px-2.5 py-1 rounded-xl bg-[#FFE600] border-2 border-black font-mono font-black text-sm shrink-0">
                        {rec.match_score}%
                      </span>
                    </div>

                    <p className="text-xs font-bold text-slate-700">{rec.why_recommended}</p>

                    {rec.matched_skills?.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {rec.matched_skills.slice(0, 4).map((s) => (
                          <span key={s} className="px-2 py-0.5 rounded bg-[#DCFCE7] border border-black text-[10px] font-black uppercase text-emerald-900">
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
                      className="w-full py-2.5 rounded-xl bg-white hover:bg-[#FFE600] border-2 border-black font-black text-xs uppercase flex items-center justify-center space-x-1.5 shadow-[2px_2px_0px_0px_#000] transition-colors"
                    >
                      <span>Practice Mock Interview</span>
                      <ArrowRight className="w-3.5 h-3.5 stroke-[2.5]" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
