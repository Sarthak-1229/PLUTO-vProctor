import React, { useEffect, useState } from 'react'
import { FileText, Upload, CheckCircle2, Trash2, Play, Save } from 'lucide-react'
import { authFetch } from '../utils/authClient'

export function ResumeLibraryPage({ jobs = [], onStartInterviewFromSaved }) {
  const [resumes, setResumes] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [selectedJobId, setSelectedJobId] = useState(jobs[0]?.id || 'job_sec_analyst')
  const [uploading, setUploading] = useState(false)
  const [savingEdit, setSavingEdit] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const [error, setError] = useState('')

  const [editFields, setEditFields] = useState({
    candidate_name: '',
    skillsText: '',
    experience_years: 0,
    degree: 'Bachelor',
  })

  const loadResumes = async () => {
    try {
      const res = await authFetch('/api/resumes')
      const data = await res.json()
      const list = data.resumes || []
      setResumes(list)
      if (list.length > 0 && !selectedId) {
        selectResume(list[0])
      }
    } catch {
      setError('Failed to fetch resume library.')
    }
  }

  const selectResume = (bundle) => {
    setSelectedId(bundle.resume.id)
    const eff = bundle.resume_profile?.effective_data || {}
    setEditFields({
      candidate_name: eff.candidate_name || '',
      skillsText: (eff.skills || []).join(', '),
      experience_years: Number(eff.experience_years || 0),
      degree: eff.education?.degree || 'Bachelor',
    })
  }

  useEffect(() => {
    loadResumes()
  }, [])

  useEffect(() => {
    if (jobs.length > 0 && !selectedJobId) {
      setSelectedJobId(jobs[0].id)
    }
  }, [jobs, selectedJobId])

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError('')
    setStatusMsg('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await authFetch('/api/resumes/upload', { method: 'POST', body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Upload rejected.')
      setStatusMsg('Resume uploaded and parsed. Review extracted fields below before confirming.')
      await loadResumes()
      selectResume(data)
    } catch (err) {
      setError(err.message || 'Upload error.')
    } finally {
      setUploading(false)
    }
  }

  const handleSaveEdits = async () => {
    if (!selectedId) return
    setSavingEdit(true)
    setError('')
    try {
      const res = await authFetch(`/api/resumes/${selectedId}/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_name: editFields.candidate_name,
          skills: editFields.skillsText.split(',').map((s) => s.trim()).filter(Boolean),
          experience_years: Number(editFields.experience_years || 0),
          education: { degree: editFields.degree },
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Update failed.')
      setStatusMsg('Edited resume fields saved cleanly.')
      await loadResumes()
      selectResume(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingEdit(false)
    }
  }

  const handleConfirm = async () => {
    if (!selectedId) return
    const res = await authFetch(`/api/resumes/${selectedId}/confirm`, { method: 'POST' })
    const data = await res.json()
    if (res.ok) {
      setStatusMsg('Resume profile confirmed and ready for job matching.')
      await loadResumes()
      selectResume(data)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Permanently delete this resume and stored file?')) return
    const res = await authFetch(`/api/resumes/${id}`, { method: 'DELETE' })
    if (res.ok) {
      setSelectedId(null)
      setStatusMsg('Resume and stored artifact deleted.')
      await loadResumes()
    }
  }

  const selectedBundle = resumes.find((b) => b.resume.id === selectedId) || null

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-black pb-4">
          <div>
            <h1 className="text-2xl font-black uppercase text-black flex items-center space-x-2">
              <FileText className="w-6 h-6 stroke-[2.5]" />
              <span>Resume Library & Field Review</span>
            </h1>
            <p className="text-xs font-bold text-slate-600">
              Stored privately outside web root. Inspect extracted skills, correct any parser gaps, and confirm accuracy.
            </p>
          </div>
          <label className="px-4 py-2.5 rounded-xl bg-[#FFE600] border-2 border-black text-xs font-black uppercase cursor-pointer shadow-[3px_3px_0px_0px_#000] flex items-center space-x-2">
            <Upload className="w-4 h-4 stroke-[2.5]" />
            <span>{uploading ? 'Uploading...' : 'Upload PDF / DOCX / TXT'}</span>
            <input type="file" accept=".pdf,.docx,.txt" onChange={handleUpload} className="hidden" />
          </label>
        </div>

        {statusMsg && <div className="p-3 bg-[#DCFCE7] border-2 border-black rounded-xl text-xs font-bold">{statusMsg}</div>}
        {error && <div className="p-3 bg-[#FEE2E2] border-2 border-black rounded-xl text-xs font-bold">{error}</div>}

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-5 space-y-3">
            <h2 className="text-xs font-black uppercase text-slate-600">Uploaded Resumes ({resumes.length})</h2>
            {resumes.length === 0 ? (
              <div className="p-6 border-2 border-dashed border-black rounded-2xl text-xs font-bold text-slate-500 text-center">
                No resumes uploaded yet. Upload a file or fill your Candidate Profile manually.
              </div>
            ) : (
              resumes.map((b) => (
                <div
                  key={b.resume.id}
                  onClick={() => selectResume(b)}
                  className={`p-4 rounded-2xl border-2 border-black cursor-pointer transition-all ${
                    selectedId === b.resume.id ? 'bg-[#FEF08A] shadow-[4px_4px_0px_0px_#000]' : 'bg-[#F4F0EA]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-black text-sm text-black break-all">{b.resume.original_filename}</p>
                      <p className="text-[11px] font-bold text-slate-600">
                        {Math.max(1, Math.round(b.resume.file_size_bytes / 1024))} KB •{' '}
                        {b.resume_profile?.confirmed_by_user ? 'Confirmed' : 'Pending Review'}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={(ev) => {
                        ev.stopPropagation()
                        handleDelete(b.resume.id)
                      }}
                      className="p-1.5 rounded-lg bg-white border border-black hover:bg-[#FEE2E2]"
                      title="Delete resume"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="lg:col-span-7">
            {selectedBundle ? (
              <div className="p-5 rounded-2xl border-2 border-black bg-[#F4F0EA] space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-black uppercase">Review & Edit Extracted Profile</span>
                  {selectedBundle.resume_profile?.confirmed_by_user && (
                    <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-[#A7F3D0] border border-black text-[10px] font-black uppercase">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>Confirmed</span>
                    </span>
                  )}
                </div>

                <label className="block space-y-1">
                  <span className="text-xs font-black uppercase">Candidate Name</span>
                  <input
                    type="text"
                    value={editFields.candidate_name}
                    onChange={(e) => setEditFields({ ...editFields, candidate_name: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border-2 border-black bg-white font-bold text-sm"
                  />
                </label>

                <label className="block space-y-1">
                  <span className="text-xs font-black uppercase">Skills (comma-separated)</span>
                  <input
                    type="text"
                    value={editFields.skillsText}
                    onChange={(e) => setEditFields({ ...editFields, skillsText: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl border-2 border-black bg-white font-bold text-sm"
                  />
                </label>

                <div className="grid grid-cols-2 gap-3">
                  <label className="block space-y-1">
                    <span className="text-xs font-black uppercase">Experience Years</span>
                    <input
                      type="number"
                      min={0}
                      step={0.5}
                      value={editFields.experience_years}
                      onChange={(e) => setEditFields({ ...editFields, experience_years: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl border-2 border-black bg-white font-bold text-sm"
                    />
                  </label>
                  <label className="block space-y-1">
                    <span className="text-xs font-black uppercase">Degree Level</span>
                    <select
                      value={editFields.degree}
                      onChange={(e) => setEditFields({ ...editFields, degree: e.target.value })}
                      className="w-full px-3 py-2 rounded-xl border-2 border-black bg-white font-bold text-sm"
                    >
                      <option value="Diploma">Diploma</option>
                      <option value="Bachelor">Bachelor</option>
                      <option value="Master">Master</option>
                      <option value="PhD">PhD</option>
                      <option value="None">None</option>
                    </select>
                  </label>
                </div>

                <div className="flex flex-wrap gap-2 pt-2">
                  <button
                    type="button"
                    disabled={savingEdit}
                    onClick={handleSaveEdits}
                    className="px-4 py-2 rounded-xl bg-white border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1"
                  >
                    <Save className="w-3.5 h-3.5" />
                    <span>Save Edits</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirm}
                    className="px-4 py-2 rounded-xl bg-[#A7F3D0] border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Confirm Accuracy</span>
                  </button>
                </div>

                {jobs.length > 0 && onStartInterviewFromSaved && (
                  <div className="pt-4 border-t-2 border-black space-y-2">
                    <span className="text-xs font-black uppercase">Launch Screening With This Resume</span>
                    <div className="flex flex-wrap gap-2">
                      <select
                        value={selectedJobId}
                        onChange={(e) => setSelectedJobId(e.target.value)}
                        className="flex-1 px-3 py-2 rounded-xl border-2 border-black bg-white font-bold text-xs"
                      >
                        {jobs.map((j) => (
                          <option key={j.id} value={j.id}>
                            {j.title} ({j.company})
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => onStartInterviewFromSaved(selectedBundle.resume.id, selectedJobId)}
                        className="px-4 py-2 rounded-xl bg-[#FFE600] border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1"
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>Screen & Start</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 border-2 border-dashed border-black rounded-2xl text-xs font-bold text-slate-500 text-center">
                Select an uploaded resume on the left to inspect or edit extracted fields.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

