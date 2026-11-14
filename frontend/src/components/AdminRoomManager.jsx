import React, { useState, useEffect } from 'react'
import { Video, Plus, Play, Pause, FastForward, SkipForward, CheckCircle2, Copy, Users, Clock, AlertTriangle, Layers, Trash2 } from 'lucide-react'
import { authFetch } from '../utils/authClient'

export function AdminRoomManager({ users = [] }) {
  const [rooms, setRooms] = useState([])
  const [questionSets, setQuestionSets] = useState([])
  const [selectedRoom, setSelectedRoom] = useState(null)
  const [activeTab, setActiveTab] = useState('rooms') // 'rooms' | 'create' | 'qsets'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

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
  const [qsetJsonText, setQsetJsonText] = useState('')

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
      }
      if (qRes.ok) {
        const qData = await qRes.json()
        setQuestionSets(qData.question_sets || [])
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
    if (!qsetName.trim()) {
      setError('Question set name is required.')
      return
    }
    let items = []
    if (qsetJsonText.trim()) {
      try {
        const parsed = JSON.parse(qsetJsonText)
        items = Array.isArray(parsed) ? parsed : (parsed.questions || parsed.items || [])
      } catch {
        setError('Invalid JSON format for questions. Provide an array of question objects.')
        return
      }
    }

    try {
      const res = await authFetch('/api/admin/question-sets', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: qsetName.trim(),
          description: qsetDescription.trim() || null,
          items: items.map((it, idx) => ({
            question_text: it.question_text || it.text || it.question || `Question ${idx + 1}`,
            domain: it.domain || 'General',
            difficulty: it.difficulty || 'Intermediate',
            target_skills: it.target_skills || (it.skills ? (Array.isArray(it.skills) ? it.skills : [it.skills]) : []),
            ideal_criteria: it.ideal_criteria || (it.answer ? [it.answer] : []),
          })),
        }),
      })
      if (!res.ok) {
        const d = await res.json()
        setError(d.detail || 'Failed to create question set.')
        return
      }
      setSuccess('Question set saved cleanly.')
      setQsetName('')
      setQsetDescription('')
      setQsetJsonText('')
      await loadRoomsAndSets()
    } catch {
      setError('Failed saving question set.')
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
                      {qs.name} ({qs.items?.length || 0} questions)
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white border-2 border-black rounded-2xl p-6 shadow-[4px_4px_0px_0px_#000] space-y-4">
            <h3 className="text-sm font-black uppercase text-black">Create Question Set</h3>
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
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">Description</label>
                <input
                  type="text"
                  value={qsetDescription}
                  onChange={(e) => setQsetDescription(e.target.value)}
                  placeholder="Targeted questions for senior infrastructure engineers."
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-medium focus:bg-yellow-50 outline-none"
                />
              </div>
              <div>
                <label className="block text-xs font-black uppercase text-gray-700 mb-1">
                  Questions JSON (Array format)
                </label>
                <textarea
                  rows="6"
                  value={qsetJsonText}
                  onChange={(e) => setQsetJsonText(e.target.value)}
                  placeholder={`[\n  {\n    "question_text": "What is the CAP theorem?",\n    "domain": "Distributed",\n    "difficulty": "Intermediate"\n  }\n]`}
                  className="w-full px-3 py-2 border-2 border-black rounded-xl text-xs font-mono focus:bg-yellow-50 outline-none"
                />
              </div>
              <button
                type="submit"
                className="w-full py-2.5 bg-[#FFE600] border-2 border-black rounded-xl text-xs font-black uppercase shadow-[3px_3px_0px_0px_#000]"
              >
                Save Question Set
              </button>
            </form>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-black uppercase text-black">Existing Question Sets</h3>
            {questionSets.length === 0 ? (
              <div className="p-6 bg-[#F4F0EA] border-2 border-dashed border-black rounded-2xl text-center text-xs font-bold text-gray-500">
                No custom question sets yet. Default catalog questions are used automatically.
              </div>
            ) : (
              questionSets.map((qs) => (
                <div key={qs.id} className="p-4 bg-white border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000]">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-black uppercase text-black">{qs.name}</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-gray-100 border border-black">
                      {qs.items?.length || 0} questions
                    </span>
                  </div>
                  {qs.description && <p className="text-xs text-gray-600 mt-1">{qs.description}</p>}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

