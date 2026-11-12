import React, { useEffect, useState } from 'react'
import { Save, UserCheck, Briefcase, GraduationCap, Sparkles } from 'lucide-react'
import { authFetch } from '../utils/authClient'

export function CandidateProfilePage({ onProfileSaved, onNavigate }) {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

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
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

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
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000]">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-black pb-4 mb-6">
          <div>
            <h1 className="text-2xl font-black uppercase text-black flex items-center space-x-2">
              <UserCheck className="w-6 h-6 stroke-[2.5]" />
              <span>Candidate Profile & Skills</span>
            </h1>
            <p className="text-xs font-bold text-slate-600">
              Complete your profile manually even if you do not upload a resume — recommendations work from both.
            </p>
          </div>
          <button
            type="button"
            onClick={() => onNavigate('/recommendations')}
            className="px-4 py-2 rounded-xl bg-[#A7F3D0] border-2 border-black text-xs font-black uppercase shadow-[3px_3px_0px_0px_#000] flex items-center space-x-1.5"
          >
            <Sparkles className="w-4 h-4" />
            <span>View Recommendations</span>
          </button>
        </div>

        {message && <div className="mb-4 p-3 bg-[#DCFCE7] border-2 border-black rounded-xl text-xs font-bold">{message}</div>}
        {error && <div className="mb-4 p-3 bg-[#FEE2E2] border-2 border-black rounded-xl text-xs font-bold">{error}</div>}

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
                placeholder="e.g., Full Stack & Cloud Graduate"
                value={form.headline}
                onChange={(e) => setForm({ ...form, headline: e.target.value })}
                className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
              />
            </label>
            <label className="block space-y-1">
              <span className="text-xs font-black uppercase">Location</span>
              <input
                type="text"
                placeholder="Pune, India"
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
              placeholder="Python, SQL, React, Docker, AWS"
              value={form.skillsText}
              onChange={(e) => setForm({ ...form, skillsText: e.target.value })}
              className="w-full px-3 py-2 rounded-xl border-2 border-black bg-[#F4F0EA] font-bold text-sm"
            />
          </label>

          <label className="block space-y-1">
            <span className="text-xs font-black uppercase">Target Roles (comma-separated)</span>
            <input
              type="text"
              placeholder="Backend Developer, Cloud Engineer, Cybersecurity Analyst"
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
            <span>{saving ? 'Saving Profile...' : 'Save Profile'}</span>
          </button>
        </form>
      </div>
    </div>
  )
}

