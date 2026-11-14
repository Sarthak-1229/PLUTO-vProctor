import React, { useState, useEffect, useRef } from 'react'
import {
  Video,
  Plus,
  Play,
  Pause,
  FastForward,
  SkipForward,
  CheckCircle2,
  Copy,
  Clock,
  AlertTriangle,
  Layers,
  Trash2,
  Edit2,
  Upload,
  X,
  RefreshCw,
  FileText,
  Download,
} from 'lucide-react'
import { authFetch } from '../utils/authClient'
import {
  parseQuestionSetsResponse,
  normalizeQuestionItem,
  validateAndNormalizeImportJson,
} from '../utils/questionSetUtils'

export function AdminRoomManager({ users = [], onNavigate }) {
  const [rooms, setRooms] = useState([])
  const [questionSets, setQuestionSets] = useState([])
  const [selectedRoom, setSelectedRoom] = useState(null)
  const [activeTab, setActiveTab] = useState('rooms') // 'rooms' | 'create' | 'qsets'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [playingVideoSessionId, setPlayingVideoSessionId] = useState(null)

  // New room form state
  const [newTitle, setNewTitle] = useState('')
  const [assignedCandId, setAssignedCandId] = useState('')
  const [selectedQSetId, setSelectedQSetId] = useState('')
  const [preset, setPreset] = useState('strict')
  const [durationMins, setDurationMins] = useState(45)
  const [customQuestionsText, setCustomQuestionsText] = useState('')

  // New question set form state
  const [qsetName, setQsetName] = useState('')
  const [qsetDescription, setQsetDescription] = useState('')
  const [qsetMode, setQsetMode] = useState('builder') // 'builder' | 'json'
  const [qsetQuestions, setQsetQuestions] = useState([
    {
      question_text: '',
      domain: 'General',
      difficulty: 'Intermediate',
      target_skills: '',
      ideal_criteria: '',
      time_limit_seconds: 180,
    },
  ])
  const [qsetJsonText, setQsetJsonText] = useState('')

  // Edit question set state & modal
  const [editingQSet, setEditingQSet] = useState(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editQuestions, setEditQuestions] = useState([])
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState('')

  // Delete confirmation modal state
  const [deletingQSet, setDeletingQSet] = useState(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  // JSON import modal state & file ref
  const importFileRef = useRef(null)
  const [importPreview, setImportPreview] = useState(null)
  const [importLoading, setImportLoading] = useState(false)
  const [importError, setImportError] = useState('')

  const loadRoomsAndSets = async () => {
    setLoading(true)
    setError('')
    try {
      const [rRes, qRes] = await Promise.all([
        authFetch('/api/admin/rooms'),
        authFetch('/api/admin/question-sets'),
      ])
      if (rRes.ok) {
        const data = await rRes.json()
        setRooms(data.rooms || [])
      } else {
        const rErr = await rRes.json().catch(() => ({}))
        setError(rErr.detail || 'Failed to fetch rooms.')
      }
      if (qRes.ok) {
        const qData = await qRes.json()
        const parsed = parseQuestionSetsResponse(qData)
        if (parsed.success) {
          setQuestionSets(parsed.questionSets)
        } else {
          setError(parsed.error)
        }
      } else {
        const qErr = await qRes.json().catch(() => ({}))
        setError(qErr.detail || 'Failed to fetch question sets.')
      }
    } catch {
      setError('Failed to fetch rooms and question templates.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadRoomsAndSets()
  }, [])

  const handleAddQuestionToBuilder = () => {
    setQsetQuestions((prev) => [
      ...prev,
      {
        question_text: '',
        domain: 'General',
        difficulty: 'Intermediate',
        target_skills: '',
        ideal_criteria: '',
        time_limit_seconds: 180,
      },
    ])
  }

  const handleRemoveQuestionFromBuilder = (idx) => {
    setQsetQuestions((prev) => prev.filter((_, i) => i !== idx))
  }

  const handleUpdateBuilderQuestion = (idx, field, val) => {
    setQsetQuestions((prev) =>
      prev.map((q, i) => (i === idx ? { ...q, [field]: val } : q))
    )
  }

  const handleToggleMode = (newMode) => {
    if (newMode === qsetMode) return
    if (newMode === 'json') {
      const serialized = qsetQuestions.map((q) => ({
        question_text: q.question_text,
        domain: q.domain,
        difficulty: q.difficulty,
        target_skills: q.target_skills.split(',').map((s) => s.trim()).filter(Boolean),
        ideal_criteria: q.ideal_criteria.split(',').map((c) => c.trim()).filter(Boolean),
        time_limit_seconds: parseInt(q.time_limit_seconds, 10) || 180,
      }))
      setQsetJsonText(JSON.stringify(serialized, null, 2))
    } else {
      if (qsetJsonText.trim()) {
        try {
          const parsed = JSON.parse(qsetJsonText)
          const items = Array.isArray(parsed) ? parsed : (parsed.items || parsed.questions || [])
          if (items.length > 0) {
            setQsetQuestions(
              items.map((it) => ({
                question_text: it.question_text || it.text || it.question || '',
                domain: it.domain || 'General',
                difficulty: it.difficulty || 'Intermediate',
                target_skills: Array.isArray(it.target_skills)
                  ? it.target_skills.join(', ')
                  : (it.target_skills || ''),
                ideal_criteria: Array.isArray(it.ideal_criteria)
                  ? it.ideal_criteria.join(', ')
                  : (it.ideal_criteria || ''),
                time_limit_seconds: it.time_limit_seconds || 180,
              }))
            )
          }
        } catch {
          // Keep existing if JSON is invalid
        }
      }
    }
    setQsetMode(newMode)
  }

  const handleCreateRoom = async (e) => {
    e.preventDefault()
    if (!newTitle.trim()) {
      setError('Room title is required.')
      return
    }
    setError('')
    setSuccess('')

    let customQs = []
    if (customQuestionsText.trim()) {
      customQs = customQuestionsText
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => ({ question_text: line, domain: 'General' }))
    }

    try {
      const payload = {
        title: newTitle.trim(),
        assigned_candidate_id: assignedCandId || null,
        question_set_id: selectedQSetId || null,
        proctoring_preset: preset,
        duration_seconds: parseInt(durationMins, 10) * 60,
        custom_questions: customQs,
      }
      const res = await authFetch('/api/admin/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Failed to create interview room.')
        return
      }
      setSuccess(`Room created! Room code: ${data.raw_room_code}`)
      setNewTitle('')
      setCustomQuestionsText('')
      await loadRoomsAndSets()
      setActiveTab('rooms')
    } catch {
      setError('An error occurred creating room.')
    }
  }

  const handleCreateQuestionSet = async (e) => {
    e.preventDefault()
    setError('')
    setSuccess('')

    const name = qsetName.trim()
    if (!name || name.length < 3) {
      setError('Question set name must be at least 3 characters.')
      return
    }

    let items = []
    if (qsetMode === 'builder') {
      if (qsetQuestions.length === 0) {
        setError('At least one question is required.')
        return
      }
      for (let i = 0; i < qsetQuestions.length; i++) {
        const q = qsetQuestions[i]
        if (!q.question_text.trim() || q.question_text.trim().length < 5) {
          setError(`Question ${i + 1} text must be at least 5 characters.`)
          return
        }
        items.push({
          question_text: q.question_text.trim(),
          domain: q.domain.trim() || 'General',
          difficulty: q.difficulty.trim() || 'Intermediate',
          target_skills: q.target_skills.split(',').map((s) => s.trim()).filter(Boolean),
          ideal_criteria: q.ideal_criteria.split(',').map((c) => c.trim()).filter(Boolean),
          time_limit_seconds: parseInt(q.time_limit_seconds, 10) || 180,
        })
      }
    } else {
      if (!qsetJsonText.trim()) {
        setError('Please provide questions JSON.')
        return
      }
      try {
        const parsed = JSON.parse(qsetJsonText)
        const rawItems = Array.isArray(parsed) ? parsed : (parsed.items || parsed.questions || [])
        if (rawItems.length === 0) {
          setError('Question set must contain at least 1 question.')
          return
        }
        items = rawItems.map((it, idx) => normalizeQuestionItem(it, idx))
      } catch (err) {
        setError(`Invalid JSON format: ${err.message}`)
        return
      }
    }

    try {
      const res = await authFetch('/api/admin/question-sets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description: qsetDescription.trim() || null,
          items,
        }),
      })
      const d = await res.json()
      if (!res.ok) {
        setError(d.detail || 'Failed to create question set.')
        return
      }
      setSuccess(`Question set "${name}" created cleanly with ${items.length} questions.`)
      setQsetName('')
      setQsetDescription('')
      setQsetQuestions([
        {
          question_text: '',
          domain: 'General',
          difficulty: 'Intermediate',
          target_skills: '',
          ideal_criteria: '',
          time_limit_seconds: 180,
        },
      ])
      setQsetJsonText('')
      await loadRoomsAndSets()
    } catch {
      setError('An error occurred creating question set.')
    }
  }

  const handleOpenEditModal = async (qs) => {
    setEditError('')
    setEditLoading(true)
    try {
      const res = await authFetch(`/api/admin/question-sets/${qs.id}`)
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        setError(err.detail || 'Failed to fetch question set details.')
        return
      }
      const data = await res.json()
      setEditingQSet(data)
      setEditName(data.name || '')
      setEditDescription(data.description || '')
      setEditQuestions(
        (data.items || []).map((it) => ({
          question_text: it.question_text || '',
          domain: it.domain || 'General',
          difficulty: it.difficulty || 'Intermediate',
          target_skills: Array.isArray(it.target_skills) ? it.target_skills.join(', ') : '',
          ideal_criteria: Array.isArray(it.ideal_criteria) ? it.ideal_criteria.join(', ') : '',
          time_limit_seconds: it.time_limit_seconds || 180,
        }))
      )
    } catch {
      setError('Failed to load question set for editing.')
    } finally {
      setEditLoading(false)
    }
  }

  const handleAddQuestionToEdit = () => {
    setEditQuestions((prev) => [
      ...prev,
      {
        question_text: '',
        domain: 'General',
        difficulty: 'Intermediate',
        target_skills: '',
        ideal_criteria: '',
        time_limit_seconds: 180,
      },
    ])
  }

  const handleRemoveQuestionFromEdit = (idx) => {
    setEditQuestions((prev) => prev.filter((_, i) => i !== idx))
  }

  const handleUpdateEditQuestion = (idx, field, val) => {
    setEditQuestions((prev) =>
      prev.map((q, i) => (i === idx ? { ...q, [field]: val } : q))
    )
  }

  const handleSaveEdit = async (e) => {
    e.preventDefault()
    if (!editingQSet) return
    setEditError('')

    const name = editName.trim()
    if (!name || name.length < 3) {
      setEditError('Question set name must be at least 3 characters.')
      return
    }

    if (editQuestions.length === 0) {
      setEditError('Question set must have at least one question.')
      return
    }

    const items = []
    for (let i = 0; i < editQuestions.length; i++) {
      const q = editQuestions[i]
      if (!q.question_text.trim() || q.question_text.trim().length < 5) {
        setEditError(`Question ${i + 1} text must be at least 5 characters.`)
        return
      }
      items.push({
        question_text: q.question_text.trim(),
        domain: q.domain.trim() || 'General',
        difficulty: q.difficulty.trim() || 'Intermediate',
        target_skills: q.target_skills.split(',').map((s) => s.trim()).filter(Boolean),
        ideal_criteria: q.ideal_criteria.split(',').map((c) => c.trim()).filter(Boolean),
        time_limit_seconds: parseInt(q.time_limit_seconds, 10) || 180,
      })
    }

    setEditLoading(true)
    try {
      const res = await authFetch(`/api/admin/question-sets/${editingQSet.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description: editDescription.trim() || null,
          items,
        }),
      })
      const d = await res.json()
      if (!res.ok) {
        setEditError(d.detail || 'Failed to update question set.')
        return
      }
      setSuccess(`Question set "${name}" updated successfully.`)
      setEditingQSet(null)
      await loadRoomsAndSets()
    } catch {
      setEditError('An unexpected error occurred saving changes.')
    } finally {
      setEditLoading(false)
    }
  }

  const handleConfirmDelete = async () => {
    if (!deletingQSet) return
    setDeleteLoading(true)
    setError('')
    try {
      const res = await authFetch(`/api/admin/question-sets/${deletingQSet.id}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        if (res.status === 409) {
          setError(d.detail || 'Cannot delete: this question set is referenced by active interview rooms.')
        } else {
          setError(d.detail || 'Failed to delete question set.')
        }
        setDeletingQSet(null)
        return
      }
      setSuccess(`Question set "${deletingQSet.name}" deleted cleanly.`)
      setDeletingQSet(null)
      await loadRoomsAndSets()
    } catch {
      setError('An error occurred deleting question set.')
      setDeletingQSet(null)
    } finally {
      setDeleteLoading(false)
    }
  }

  const handleFileSelected = (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.toLowerCase().endsWith('.json')) {
      setError('Only .json files are supported for import.')
      if (importFileRef.current) importFileRef.current.value = ''
      return
    }

    if (file.size > 2 * 1024 * 1024) {
      setError('File exceeds 2MB limit.')
      if (importFileRef.current) importFileRef.current.value = ''
      return
    }

    const reader = new FileReader()
    reader.onload = (event) => {
      try {
        const text = event.target?.result
        const normalized = validateAndNormalizeImportJson(text, file.name)
        setImportPreview(normalized)
        setImportError('')
      } catch (err) {
        setError(`JSON import validation failed: ${err.message}`)
      } finally {
        if (importFileRef.current) importFileRef.current.value = ''
      }
    }
    reader.onerror = () => {
      setError('Failed to read the selected file.')
      if (importFileRef.current) importFileRef.current.value = ''
    }
    reader.readAsText(file)
  }

  const handleConfirmImport = async () => {
    if (!importPreview) return
    setImportLoading(true)
    setImportError('')

    try {
      const res = await authFetch('/api/admin/question-sets/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(importPreview),
      })
      const d = await res.json()
      if (!res.ok) {
        setImportError(d.detail || 'Failed to import question set.')
        return
      }
      setSuccess(`Imported question set "${importPreview.name}" with ${importPreview.items.length} questions.`)
      setImportPreview(null)
      await loadRoomsAndSets()
    } catch {
      setImportError('An unexpected error occurred during import.')
    } finally {
      setImportLoading(false)
    }
  }

  const handleRoomAction = async (roomId, action, body = {}) => {
    setError('')
    try {
      const res = await authFetch(`/api/admin/rooms/${roomId}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || `Action ${action} failed.`)
        return
      }
      setSelectedRoom(data)
      await loadRoomsAndSets()
    } catch {
      setError(`Error executing ${action}.`)
    }
  }

  const copyToClipboard = (text, label) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text)
      setSuccess(`${label} copied to clipboard!`)
      setTimeout(() => setSuccess(''), 3000)
    }
  }

  return (
    <div className="space-y-6">
      {/* Sub tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b-2 border-black pb-3">
        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => setActiveTab('rooms')}
            className={`px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1 ${
              activeTab === 'rooms' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Video className="w-3.5 h-3.5" />
            <span>Active Rooms ({rooms.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('create')}
            className={`px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1 ${
              activeTab === 'create' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Schedule Room</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('qsets')}
            className={`px-3 py-1.5 rounded-xl border-2 border-black text-xs font-black uppercase flex items-center space-x-1 ${
              activeTab === 'qsets' ? 'bg-[#FFE600]' : 'bg-[#F4F0EA]'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Question Sets ({questionSets.length})</span>
          </button>
        </div>

        <button
          type="button"
          onClick={loadRoomsAndSets}
          className="text-xs font-bold text-gray-700 hover:text-black underline"
        >
          Refresh Data
        </button>
      </div>

      {error && (
        <div className="p-3 bg-[#FECDD3] border-2 border-black rounded-xl text-xs font-bold text-red-900 flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {success && (
        <div className="p-3 bg-[#A7F3D0] border-2 border-black rounded-xl text-xs font-bold text-green-900 flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
          <span>{success}</span>
        </div>
      )}

      {/* TAB 1: ROOMS LIST & ORCHESTRATION */}
      {activeTab === 'rooms' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 space-y-3">
            <h3 className="text-sm font-black uppercase text-black tracking-wider">Scheduled Rooms</h3>
            {rooms.length === 0 ? (
              <div className="p-6 bg-[#F4F0EA] border-2 border-dashed border-black rounded-2xl text-center text-xs font-semibold text-gray-600">
                No active or scheduled interview rooms found.
              </div>
            ) : (
              rooms.map((rm) => (
                <div
                  key={rm.id}
                  onClick={() => setSelectedRoom(rm)}
                  className={`p-4 border-2 border-black rounded-2xl cursor-pointer transition-all ${
                    selectedRoom?.id === rm.id
                      ? 'bg-[#FFE600] shadow-[3px_3px_0px_0px_#000]'
                      : 'bg-white hover:bg-yellow-50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black uppercase text-black truncate max-w-[150px]">
                      {rm.title}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-black uppercase border border-black ${
                        rm.status === 'LIVE'
                          ? 'bg-red-200 text-red-900 animate-pulse'
                          : rm.status === 'COMPLETED'
                          ? 'bg-green-200 text-green-900'
                          : 'bg-blue-100 text-blue-900'
                      }`}
                    >
                      {rm.status}
                    </span>
                  </div>
                  <div className="text-[11px] font-medium text-gray-600 mt-1 flex items-center space-x-2">
                    <Clock className="w-3 h-3" />
                    <span>{Math.round(rm.duration_seconds / 60)} mins</span>
                    <span>•</span>
                    <span>{rm.question_count || rm.questions?.length || 0} questions</span>
                  </div>
                </div>
              ))
            )}
          </div>

          <div className="lg:col-span-2">
            {selectedRoom ? (
              <div className="bg-white border-2 border-black rounded-2xl p-6 shadow-[4px_4px_0px_0px_#000] space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b-2 border-black pb-3">
                  <div>
                    <h2 className="text-lg font-black uppercase text-black">{selectedRoom.title}</h2>
                    <span className="text-xs font-bold text-gray-500">Room ID: {selectedRoom.id}</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <a
                      href={`/rooms/${selectedRoom.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="px-3 py-1.5 rounded-xl bg-black text-white text-xs font-black uppercase flex items-center space-x-1.5 hover:bg-gray-800"
                    >
                      <Video className="w-3.5 h-3.5" />
                      <span>Launch Room</span>
                    </a>
                  </div>
                </div>

                {/* State Machine Control Bar */}
                <div className="p-4 bg-[#F4F0EA] border-2 border-black rounded-xl space-y-3">
                  <span className="text-xs font-black uppercase text-gray-700">Interview Flow Controls</span>
                  <div className="flex flex-wrap items-center gap-2">
                    {selectedRoom.status === 'LOBBY' && (
                      <button
                        type="button"
                        onClick={() => handleRoomAction(selectedRoom.id, 'start')}
                        className="px-3 py-1.5 rounded-lg bg-green-500 text-white border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1"
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>Start Interview</span>
                      </button>
                    )}

                    {selectedRoom.status === 'LIVE' && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleRoomAction(selectedRoom.id, 'pause', { reason: 'Admin technical pause' })}
                          className="px-3 py-1.5 rounded-lg bg-amber-400 text-black border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1"
                        >
                          <Pause className="w-3.5 h-3.5" />
                          <span>Pause</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRoomAction(selectedRoom.id, 'advance')}
                          className="px-3 py-1.5 rounded-lg bg-blue-400 text-black border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1"
                        >
                          <FastForward className="w-3.5 h-3.5" />
                          <span>Next Question</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRoomAction(selectedRoom.id, 'skip')}
                          className="px-3 py-1.5 rounded-lg bg-yellow-200 text-black border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1"
                        >
                          <SkipForward className="w-3.5 h-3.5" />
                          <span>Skip Question</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRoomAction(selectedRoom.id, 'end')}
                          className="px-3 py-1.5 rounded-lg bg-red-500 text-white border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>End & Finalize</span>
                        </button>
                      </>
                    )}

                    {selectedRoom.status === 'PAUSED' && (
                      <button
                        type="button"
                        onClick={() => handleRoomAction(selectedRoom.id, 'resume')}
                        className="px-3 py-1.5 rounded-lg bg-green-500 text-white border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] flex items-center space-x-1"
                      >
                        <Play className="w-3.5 h-3.5" />
                        <span>Resume Interview</span>
                      </button>
                    )}

                    {selectedRoom.status === 'COMPLETED' && (
                      <div className="w-full p-4 bg-white border-2 border-black rounded-xl shadow-[3px_3px_0px_0px_#000] space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-200 pb-2">
                          <div className="flex items-center space-x-2">
                            <CheckCircle2 className="w-5 h-5 text-green-600 stroke-[2.5]" />
                            <span className="text-xs font-black uppercase text-black">
                              Interview Concluded & Evaluated
                            </span>
                          </div>
                          {selectedRoom.report?.overall_score !== undefined && selectedRoom.report?.overall_score !== null && (
                            <span className="px-2.5 py-1 rounded-lg bg-[#FFE600] border-2 border-black text-xs font-black">
                              Score: {selectedRoom.report.overall_score}% ({selectedRoom.report.grade || 'N/A'})
                            </span>
                          )}
                        </div>

                        {/* Linked Candidate info */}
                        <div className="text-xs text-gray-700 flex flex-wrap items-center gap-x-4 gap-y-1">
                          <span>
                            <strong className="font-bold">Candidate:</strong>{' '}
                            {selectedRoom.assigned_candidate?.full_name || 'Assigned Candidate'} (
                            {selectedRoom.assigned_candidate?.email || 'Authenticated Account'})
                          </span>
                          {selectedRoom.ended_at && (
                            <span>
                              <strong className="font-bold">Ended:</strong>{' '}
                              {new Date(selectedRoom.ended_at).toLocaleString()}
                            </span>
                          )}
                        </div>

                        {/* Report & Recording Actions */}
                        <div className="flex flex-wrap items-center gap-2 pt-1">
                          {selectedRoom.active_session_id ? (
                            <>
                              <button
                                type="button"
                                onClick={() => {
                                  if (onNavigate) {
                                    onNavigate(`/report/${selectedRoom.active_session_id}`)
                                  } else {
                                    window.location.href = `/report/${selectedRoom.active_session_id}`
                                  }
                                }}
                                className="px-3 py-1.5 rounded-lg bg-[#FFE600] border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-yellow-400 flex items-center space-x-1"
                              >
                                <FileText className="w-3.5 h-3.5" />
                                <span>View Evaluation Report</span>
                              </button>
                              <a
                                href={`/api/report/${selectedRoom.active_session_id}/pdf`}
                                target="_blank"
                                rel="noreferrer"
                                className="px-3 py-1.5 rounded-lg bg-white border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-gray-100 flex items-center space-x-1"
                              >
                                <Download className="w-3.5 h-3.5" />
                                <span>PDF Dossier</span>
                              </a>
                            </>
                          ) : (
                            <span className="text-[11px] text-gray-500 italic">
                              Room concluded without linked evaluation session.
                            </span>
                          )}

                          {selectedRoom.has_recording && selectedRoom.active_session_id && (
                            <button
                              type="button"
                              onClick={() => setPlayingVideoSessionId(selectedRoom.active_session_id)}
                              className="px-3 py-1.5 rounded-lg bg-black text-white border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-gray-800 flex items-center space-x-1"
                            >
                              <Video className="w-3.5 h-3.5" />
                              <span>Play Recording</span>
                            </button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Candidate credentials & join links */}
                {selectedRoom.raw_room_code && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div className="p-3 bg-white border-2 border-black rounded-xl">
                      <span className="text-[10px] font-black uppercase text-gray-500">Candidate Room Code</span>
                      <div className="flex items-center justify-between mt-1">
                        <code className="text-sm font-black font-mono">{selectedRoom.raw_room_code}</code>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(selectedRoom.raw_room_code, 'Room Code')}
                          className="p-1 hover:bg-gray-100 rounded"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="p-3 bg-white border-2 border-black rounded-xl">
                      <span className="text-[10px] font-black uppercase text-gray-500">Candidate Join URL</span>
                      <div className="flex items-center justify-between mt-1">
                        <span className="text-xs truncate max-w-[180px] font-mono">
                          {window.location.origin}/rooms/{selectedRoom.id}
                        </span>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(`${window.location.origin}/rooms/${selectedRoom.id}`, 'Join URL')}
                          className="p-1 hover:bg-gray-100 rounded"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Questions List */}
                <div className="space-y-3">
                  <h3 className="text-xs font-black uppercase text-black">Questions Timeline</h3>
                  <div className="space-y-2">
                    {selectedRoom.questions?.map((q, idx) => (
                      <div
                        key={q.id || idx}
                        className={`p-3 border-2 border-black rounded-xl flex items-center justify-between ${
                          q.status === 'active'
                            ? 'bg-[#FFE600] font-black'
                            : q.status === 'completed'
                            ? 'bg-gray-100 opacity-70'
                            : 'bg-white'
                        }`}
                      >
                        <div className="flex items-center space-x-3">
                          <span className="w-6 h-6 rounded-full bg-black text-white text-xs flex items-center justify-center font-bold">
                            {q.ordinal || idx + 1}
                          </span>
                          <div>
                            <p className="text-xs font-semibold text-black">{q.question_text}</p>
                            <span className="text-[10px] text-gray-600">
                              {q.domain} • {q.difficulty}
                            </span>
                          </div>
                        </div>
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded border border-black bg-white">
                          {q.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center p-12 bg-[#F4F0EA] border-2 border-dashed border-black rounded-2xl text-xs font-bold text-gray-500">
                Select an interview room from the left list to inspect status or control live orchestration.
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: CREATE SCHEDULED ROOM */}
      {activeTab === 'create' && (
        <div className="max-w-2xl bg-white border-2 border-black rounded-2xl p-6 shadow-[4px_4px_0px_0px_#000] space-y-5">
          <h2 className="text-lg font-black uppercase text-black flex items-center space-x-2">
            <Plus className="w-5 h-5" />
            <span>Create Collaborative Interview Room</span>
          </h2>

          <form onSubmit={handleCreateRoom} className="space-y-4">
            <div>
              <label className="block text-xs font-black uppercase text-gray-700 mb-1">Room Title *</label>
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g. Senior Backend Engineer - Round 1"
                className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Assign Candidate</label>
                <select
                  value={assignedCandId}
                  onChange={(e) => setAssignedCandId(e.target.value)}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                >
                  <option value="">Any authenticated candidate</option>
                  {users
                    .filter((u) => u.role === 'candidate')
                    .map((u) => (
                      <option key={u.id} value={u.id}>
                        {u.full_name} ({u.email})
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Question Set</label>
                <select
                  value={selectedQSetId}
                  onChange={(e) => setSelectedQSetId(e.target.value)}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                >
                  <option value="">Default Catalog (Auto-select)</option>
                  {questionSets.map((qs) => (
                    <option key={qs.id} value={qs.id}>
                      {qs.name} ({qs.item_count ?? qs.items?.length ?? 0} questions)
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Proctoring Preset</label>
                <select
                  value={preset}
                  onChange={(e) => setPreset(e.target.value)}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                >
                  <option value="strict">Strict (High Sensitivity)</option>
                  <option value="balanced">Balanced (Standard)</option>
                  <option value="relaxed">Relaxed (Low Sensitivity)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Duration (minutes)</label>
                <input
                  type="number"
                  min="15"
                  max="180"
                  value={durationMins}
                  onChange={(e) => setDurationMins(e.target.value)}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-black uppercase text-gray-700 mb-1">
                Custom Questions (One per line, optional)
              </label>
              <textarea
                rows="4"
                value={customQuestionsText}
                onChange={(e) => setCustomQuestionsText(e.target.value)}
                placeholder="Explain the differences between optimistic and pessimistic locking.&#10;How does distributed consensus work in Raft?"
                className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-mono focus:bg-yellow-50 outline-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-[#FFE600] border-2 border-black rounded-xl text-xs font-black uppercase shadow-[3px_3px_0px_0px_#000] hover:bg-yellow-400"
            >
              {loading ? 'Creating...' : 'Create & Generate Invite Link'}
            </button>
          </form>
        </div>
      )}

      {/* TAB 3: QUESTION SETS */}
      {activeTab === 'qsets' && (
        <div className="space-y-6">
          {/* Top Actions Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 bg-[#F4F0EA] border-2 border-black rounded-2xl p-4">
            <div>
              <h2 className="text-sm font-black uppercase text-black flex items-center space-x-2">
                <Layers className="w-4 h-4" />
                <span>Question Collections ({questionSets.length})</span>
              </h2>
              <p className="text-[11px] font-medium text-gray-600 mt-0.5">
                Curate specialized question tracks, import assessment JSONs, and bind them to live collaborative rooms.
              </p>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="file"
                ref={importFileRef}
                accept=".json,application/json"
                onChange={handleFileSelected}
                className="hidden"
              />
              <button
                type="button"
                onClick={() => importFileRef.current?.click()}
                className="px-3 py-1.5 rounded-xl bg-white border-2 border-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-yellow-50 flex items-center space-x-1.5"
              >
                <Upload className="w-3.5 h-3.5" />
                <span>Import JSON</span>
              </button>
              <button
                type="button"
                onClick={loadRoomsAndSets}
                className="p-1.5 rounded-xl bg-white border-2 border-black hover:bg-gray-100 shadow-[2px_2px_0px_0px_#000]"
                title="Refresh question sets"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* LEFT COLUMN: CREATE QUESTION SET */}
            <div className="bg-white border-2 border-black rounded-2xl p-6 shadow-[4px_4px_0px_0px_#000] space-y-4">
              <div className="flex items-center justify-between border-b-2 border-black pb-3">
                <h3 className="text-sm font-black uppercase text-black flex items-center space-x-2">
                  <Plus className="w-4 h-4" />
                  <span>Create Question Set</span>
                </h3>
                <div className="flex items-center space-x-1 bg-[#F4F0EA] p-1 border-2 border-black rounded-xl">
                  <button
                    type="button"
                    onClick={() => handleToggleMode('builder')}
                    className={`px-2.5 py-1 text-[10px] font-black uppercase rounded-lg transition-all ${
                      qsetMode === 'builder' ? 'bg-[#FFE600] border border-black shadow-[1px_1px_0px_0px_#000]' : 'text-gray-600'
                    }`}
                  >
                    Builder
                  </button>
                  <button
                    type="button"
                    onClick={() => handleToggleMode('json')}
                    className={`px-2.5 py-1 text-[10px] font-black uppercase rounded-lg transition-all ${
                      qsetMode === 'json' ? 'bg-[#FFE600] border border-black shadow-[1px_1px_0px_0px_#000]' : 'text-gray-600'
                    }`}
                  >
                    JSON
                  </button>
                </div>
              </div>

              <form onSubmit={handleCreateQuestionSet} className="space-y-4">
                <div>
                  <label className="block text-xs font-black uppercase text-gray-700 mb-1">Set Name *</label>
                  <input
                    type="text"
                    value={qsetName}
                    onChange={(e) => setQsetName(e.target.value)}
                    placeholder="e.g. Distributed Systems Specialization"
                    className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-black uppercase text-gray-700 mb-1">Description (Optional)</label>
                  <input
                    type="text"
                    value={qsetDescription}
                    onChange={(e) => setQsetDescription(e.target.value)}
                    placeholder="e.g. Targeted questions for senior infrastructure engineers."
                    className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                  />
                </div>

                {/* MODE 1: INTERACTIVE QUESTION BUILDER */}
                {qsetMode === 'builder' && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <label className="block text-xs font-black uppercase text-gray-700">
                        Questions ({qsetQuestions.length})
                      </label>
                      <button
                        type="button"
                        onClick={handleAddQuestionToBuilder}
                        className="px-2.5 py-1 bg-[#FFE600] border-2 border-black rounded-lg text-[10px] font-black uppercase shadow-[1px_1px_0px_0px_#000] flex items-center space-x-1"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Add Question</span>
                      </button>
                    </div>

                    <div className="space-y-3 max-h-[380px] overflow-y-auto pr-1">
                      {qsetQuestions.map((q, idx) => (
                        <div key={idx} className="p-3 bg-[#F4F0EA] border-2 border-black rounded-xl space-y-2.5 relative">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-black text-white">
                              Question #{idx + 1}
                            </span>
                            {qsetQuestions.length > 1 && (
                              <button
                                type="button"
                                onClick={() => handleRemoveQuestionFromBuilder(idx)}
                                className="text-red-700 hover:text-red-900 p-1 rounded"
                                title="Remove question"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                          </div>

                          <div>
                            <textarea
                              rows="2"
                              value={q.question_text}
                              onChange={(e) => handleUpdateBuilderQuestion(idx, 'question_text', e.target.value)}
                              placeholder="Question text (min 5 characters) *"
                              className="w-full px-2.5 py-1.5 bg-white border-2 border-black rounded-lg text-xs font-medium focus:bg-yellow-50 outline-none"
                              required
                            />
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                            <div>
                              <label className="block text-[10px] font-bold text-gray-600 mb-0.5">Domain</label>
                              <select
                                value={q.domain}
                                onChange={(e) => handleUpdateBuilderQuestion(idx, 'domain', e.target.value)}
                                className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-xs outline-none"
                              >
                                <option value="General">General</option>
                                <option value="Distributed Systems">Distributed</option>
                                <option value="Backend">Backend</option>
                                <option value="Frontend">Frontend</option>
                                <option value="System Design">System Design</option>
                                <option value="Algorithms">Algorithms</option>
                                <option value="Security">Security</option>
                                <option value="DevOps">DevOps</option>
                              </select>
                            </div>

                            <div>
                              <label className="block text-[10px] font-bold text-gray-600 mb-0.5">Difficulty</label>
                              <select
                                value={q.difficulty}
                                onChange={(e) => handleUpdateBuilderQuestion(idx, 'difficulty', e.target.value)}
                                className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-xs outline-none"
                              >
                                <option value="Easy">Easy</option>
                                <option value="Intermediate">Intermediate</option>
                                <option value="Advanced">Advanced</option>
                              </select>
                            </div>

                            <div>
                              <label className="block text-[10px] font-bold text-gray-600 mb-0.5">Time Limit</label>
                              <select
                                value={q.time_limit_seconds}
                                onChange={(e) => handleUpdateBuilderQuestion(idx, 'time_limit_seconds', e.target.value)}
                                className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-xs outline-none"
                              >
                                <option value="120">2 mins</option>
                                <option value="180">3 mins</option>
                                <option value="240">4 mins</option>
                                <option value="300">5 mins</option>
                              </select>
                            </div>
                          </div>

                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            <div>
                              <input
                                type="text"
                                value={q.target_skills}
                                onChange={(e) => handleUpdateBuilderQuestion(idx, 'target_skills', e.target.value)}
                                placeholder="Target skills (e.g. Raft, Consensus)"
                                className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-[11px] outline-none"
                              />
                            </div>
                            <div>
                              <input
                                type="text"
                                value={q.ideal_criteria}
                                onChange={(e) => handleUpdateBuilderQuestion(idx, 'ideal_criteria', e.target.value)}
                                placeholder="Ideal criteria (e.g. Split brain, Quorum)"
                                className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-[11px] outline-none"
                              />
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* MODE 2: RAW JSON */}
                {qsetMode === 'json' && (
                  <div>
                    <label className="block text-xs font-black uppercase text-gray-700 mb-1">
                      Questions JSON Array format
                    </label>
                    <textarea
                      rows="8"
                      value={qsetJsonText}
                      onChange={(e) => setQsetJsonText(e.target.value)}
                      placeholder={`[\n  {\n    "question_text": "What is the CAP theorem?",\n    "domain": "Distributed Systems",\n    "difficulty": "Intermediate",\n    "target_skills": ["CAP", "Consensus"]\n  }\n]`}
                      className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-mono focus:bg-yellow-50 outline-none"
                    />
                  </div>
                )}

                <button
                  type="submit"
                  className="w-full py-2.5 bg-[#FFE600] border-2 border-black rounded-xl text-xs font-black uppercase shadow-[3px_3px_0px_0px_#000] hover:bg-yellow-400"
                >
                  Save Question Set
                </button>
              </form>
            </div>

            {/* RIGHT COLUMN: EXISTING QUESTION SETS */}
            <div className="space-y-4">
              <h3 className="text-sm font-black uppercase text-black flex items-center justify-between">
                <span>Existing Question Sets</span>
                <span className="text-[10px] font-bold text-gray-500">
                  {questionSets.length} {questionSets.length === 1 ? 'collection' : 'collections'}
                </span>
              </h3>

              {questionSets.length === 0 ? (
                <div className="p-8 bg-[#F4F0EA] border-2 border-dashed border-black rounded-2xl text-center space-y-2">
                  <Layers className="w-8 h-8 mx-auto text-gray-400" />
                  <p className="text-xs font-bold text-gray-600">No custom question sets yet.</p>
                  <p className="text-[11px] text-gray-500">
                    Create your first set using the builder on the left or import an existing JSON assessment.
                  </p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[620px] overflow-y-auto pr-1">
                  {questionSets.map((qs) => (
                    <div
                      key={qs.id}
                      className="p-4 bg-white border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] space-y-2.5"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center space-x-2 truncate">
                          <span className="text-xs font-black uppercase text-black truncate">{qs.name}</span>
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-gray-100 border border-black flex-shrink-0">
                            v{qs.version || 1}
                          </span>
                        </div>

                        <div className="flex items-center space-x-1.5 flex-shrink-0">
                          <span className="text-[10px] font-black px-2 py-0.5 rounded bg-[#FFE600] border border-black">
                            {qs.item_count ?? qs.items?.length ?? 0} questions
                          </span>
                          <button
                            type="button"
                            onClick={() => handleOpenEditModal(qs)}
                            className="p-1 rounded-lg border border-black bg-white hover:bg-yellow-100 transition-colors"
                            title="Edit question set"
                          >
                            <Edit2 className="w-3.5 h-3.5 text-black" />
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeletingQSet(qs)}
                            className="p-1 rounded-lg border border-black bg-white hover:bg-red-100 transition-colors"
                            title="Delete question set"
                          >
                            <Trash2 className="w-3.5 h-3.5 text-red-600" />
                          </button>
                        </div>
                      </div>

                      {qs.description && (
                        <p className="text-xs text-gray-600 line-clamp-2">{qs.description}</p>
                      )}

                      <div className="flex items-center justify-between text-[10px] font-medium text-gray-500 pt-1 border-t border-gray-200">
                        <span>ID: {qs.id}</span>
                        {qs.created_at && (
                          <span>Created {new Date(qs.created_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* MODAL 1: EDIT QUESTION SET MODAL */}
      {editingQSet && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border-2 border-black rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-[6px_6px_0px_0px_#000] space-y-4">
            <div className="flex items-center justify-between border-b-2 border-black pb-3">
              <div>
                <h3 className="text-base font-black uppercase text-black flex items-center space-x-2">
                  <Edit2 className="w-4 h-4" />
                  <span>Edit Question Set — {editingQSet.name}</span>
                </h3>
                <span className="text-[10px] font-bold text-gray-500">ID: {editingQSet.id}</span>
              </div>
              <button
                type="button"
                onClick={() => setEditingQSet(null)}
                className="p-1 rounded-lg border-2 border-black hover:bg-gray-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {editError && (
              <div className="p-3 bg-[#FECDD3] border-2 border-black rounded-xl text-xs font-bold text-red-900 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleSaveEdit} className="space-y-4">
              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Set Name *</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Description</label>
                <input
                  type="text"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                />
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-black uppercase text-gray-700">
                    Questions ({editQuestions.length})
                  </label>
                  <button
                    type="button"
                    onClick={handleAddQuestionToEdit}
                    className="px-2.5 py-1 bg-[#FFE600] border-2 border-black rounded-lg text-[10px] font-black uppercase shadow-[1px_1px_0px_0px_#000] flex items-center space-x-1"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Add Question</span>
                  </button>
                </div>

                <div className="space-y-3 max-h-[320px] overflow-y-auto pr-1">
                  {editQuestions.map((q, idx) => (
                    <div key={idx} className="p-3 bg-[#F4F0EA] border-2 border-black rounded-xl space-y-2 relative">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-black text-white">
                          Question #{idx + 1}
                        </span>
                        {editQuestions.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveQuestionFromEdit(idx)}
                            className="text-red-700 hover:text-red-900 p-1"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      <textarea
                        rows="2"
                        value={q.question_text}
                        onChange={(e) => handleUpdateEditQuestion(idx, 'question_text', e.target.value)}
                        placeholder="Question text *"
                        className="w-full px-2.5 py-1.5 bg-white border-2 border-black rounded-lg text-xs font-medium focus:bg-yellow-50 outline-none"
                        required
                      />

                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                        <div>
                          <label className="block text-[10px] font-bold text-gray-600 mb-0.5">Domain</label>
                          <input
                            type="text"
                            value={q.domain}
                            onChange={(e) => handleUpdateEditQuestion(idx, 'domain', e.target.value)}
                            className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-xs outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-bold text-gray-600 mb-0.5">Difficulty</label>
                          <select
                            value={q.difficulty}
                            onChange={(e) => handleUpdateEditQuestion(idx, 'difficulty', e.target.value)}
                            className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-xs outline-none"
                          >
                            <option value="Easy">Easy</option>
                            <option value="Intermediate">Intermediate</option>
                            <option value="Advanced">Advanced</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-[10px] font-bold text-gray-600 mb-0.5">Time Limit (s)</label>
                          <input
                            type="number"
                            min="30"
                            max="600"
                            value={q.time_limit_seconds}
                            onChange={(e) => handleUpdateEditQuestion(idx, 'time_limit_seconds', e.target.value)}
                            className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-xs outline-none"
                          />
                        </div>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        <div>
                          <input
                            type="text"
                            value={q.target_skills}
                            onChange={(e) => handleUpdateEditQuestion(idx, 'target_skills', e.target.value)}
                            placeholder="Target skills (comma separated)"
                            className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-[11px] outline-none"
                          />
                        </div>
                        <div>
                          <input
                            type="text"
                            value={q.ideal_criteria}
                            onChange={(e) => handleUpdateEditQuestion(idx, 'ideal_criteria', e.target.value)}
                            placeholder="Ideal criteria (comma separated)"
                            className="w-full px-2 py-1 bg-white border-2 border-black rounded-lg text-[11px] outline-none"
                          />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t-2 border-black">
                <button
                  type="button"
                  onClick={() => setEditingQSet(null)}
                  className="px-4 py-2 rounded-xl border-2 border-black bg-white text-xs font-black uppercase hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editLoading}
                  className="px-4 py-2 rounded-xl border-2 border-black bg-[#FFE600] text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-yellow-400"
                >
                  {editLoading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL 2: DELETE CONFIRMATION MODAL */}
      {deletingQSet && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border-2 border-black rounded-2xl max-w-md w-full p-6 shadow-[6px_6px_0px_0px_#000] space-y-4">
            <div className="flex items-center space-x-3 text-red-600">
              <AlertTriangle className="w-6 h-6 flex-shrink-0" />
              <h3 className="text-base font-black uppercase text-black">Delete Question Set</h3>
            </div>

            <p className="text-xs text-gray-700">
              Are you sure you want to delete question set <strong className="text-black font-black">"{deletingQSet.name}"</strong>? This action cannot be undone.
            </p>

            <div className="p-3 bg-[#F4F0EA] border border-black rounded-xl text-[11px] text-gray-600">
              Historical interview rooms and past recordings are safely preserved, but any active rooms referencing this set will block deletion.
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                type="button"
                onClick={() => setDeletingQSet(null)}
                className="px-4 py-2 rounded-xl border-2 border-black bg-white text-xs font-black uppercase hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={deleteLoading}
                className="px-4 py-2 rounded-xl border-2 border-black bg-red-600 text-white text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-red-700"
              >
                {deleteLoading ? 'Deleting...' : 'Delete Set'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 3: JSON IMPORT PREVIEW MODAL */}
      {importPreview && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border-2 border-black rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-[6px_6px_0px_0px_#000] space-y-4">
            <div className="flex items-center justify-between border-b-2 border-black pb-3">
              <div>
                <h3 className="text-base font-black uppercase text-black flex items-center space-x-2">
                  <Upload className="w-4 h-4" />
                  <span>Import Question Set Preview</span>
                </h3>
                <span className="text-[10px] font-bold text-gray-500">
                  {importPreview.source_filename} • {importPreview.items.length} questions detected
                </span>
              </div>
              <button
                type="button"
                onClick={() => setImportPreview(null)}
                className="p-1 rounded-lg border-2 border-black hover:bg-gray-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {importError && (
              <div className="p-3 bg-[#FECDD3] border-2 border-black rounded-xl text-xs font-bold text-red-900 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{importError}</span>
              </div>
            )}

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Set Name *</label>
                <input
                  type="text"
                  value={importPreview.name}
                  onChange={(e) => setImportPreview((prev) => ({ ...prev, name: e.target.value }))}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Description</label>
                <input
                  type="text"
                  value={importPreview.description || ''}
                  onChange={(e) => setImportPreview((prev) => ({ ...prev, description: e.target.value }))}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-2">
                  Questions Sample (Showing up to 5 of {importPreview.items.length})
                </label>
                <div className="space-y-2 max-h-[240px] overflow-y-auto pr-1">
                  {importPreview.items.slice(0, 5).map((q, idx) => (
                    <div key={idx} className="p-3 bg-[#F4F0EA] border-2 border-black rounded-xl space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-black uppercase px-1.5 py-0.5 rounded bg-black text-white">
                          #{idx + 1}
                        </span>
                        <div className="flex items-center space-x-1">
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-white border border-black">
                            {q.domain}
                          </span>
                          <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-white border border-black">
                            {q.difficulty}
                          </span>
                        </div>
                      </div>
                      <p className="text-xs font-semibold text-black">{q.question_text}</p>
                    </div>
                  ))}
                  {importPreview.items.length > 5 && (
                    <div className="p-2 bg-yellow-50 border border-black rounded-xl text-center text-[10px] font-bold text-gray-600">
                      + {importPreview.items.length - 5} additional questions included in this set
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-3 border-t-2 border-black">
              <button
                type="button"
                onClick={() => setImportPreview(null)}
                className="px-4 py-2 rounded-xl border-2 border-black bg-white text-xs font-black uppercase hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmImport}
                disabled={importLoading}
                className="px-4 py-2 rounded-xl border-2 border-black bg-[#FFE600] text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:bg-yellow-400"
              >
                {importLoading ? 'Importing...' : 'Confirm & Import Question Set'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* MODAL 4: VIDEO RECORDING PLAYER MODAL */}
      {playingVideoSessionId && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white border-2 border-black rounded-2xl max-w-3xl w-full p-4 shadow-[6px_6px_0px_0px_#000] space-y-3">
            <div className="flex items-center justify-between border-b-2 border-black pb-2">
              <span className="text-xs font-black uppercase text-black flex items-center space-x-2">
                <Video className="w-4 h-4" />
                <span>Session Video Recording — {playingVideoSessionId}</span>
              </span>
              <button
                type="button"
                onClick={() => setPlayingVideoSessionId(null)}
                className="p-1 rounded-lg border-2 border-black hover:bg-gray-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="aspect-video bg-black rounded-xl overflow-hidden border border-black">
              <video
                controls
                autoPlay
                src={`/api/interview/${playingVideoSessionId}/video`}
                className="w-full h-full object-contain"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

