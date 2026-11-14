import React, { useState } from 'react'
import { Video, ArrowRight, AlertTriangle, Key } from 'lucide-react'
import { authFetch } from '../utils/authClient'

export function RoomJoinPage({ onJoinedRoom, onNavigate }) {
  const [codeOrToken, setCodeOrToken] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleJoin = async (e) => {
    e.preventDefault()
    if (!codeOrToken.trim()) {
      setError('Please enter a valid room code or invite link token.')
      return
    }
    setError('')
    setLoading(true)

    try {
      const res = await authFetch('/api/rooms/join', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token_or_code: codeOrToken.trim() }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || 'Could not join interview room. Verify the code.')
        return
      }
      if (onJoinedRoom) {
        onJoinedRoom(data.room_id)
      } else if (onNavigate) {
        onNavigate(`/rooms/${data.room_id}`)
      }
    } catch {
      setError('An error occurred connecting to the room.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-md mx-auto space-y-6">
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-6">
        <div className="text-center space-y-2">
          <div className="w-12 h-12 bg-[#FFE600] border-2 border-black rounded-2xl mx-auto flex items-center justify-center shadow-[3px_3px_0px_0px_#000]">
            <Video className="w-6 h-6 stroke-[2.5]" />
          </div>
          <h1 className="text-xl font-black uppercase text-black">Join Hosted Interview</h1>
          <p className="text-xs font-semibold text-gray-600">
            Enter the 9-character room code or paste the invitation token provided by your interviewer.
          </p>
        </div>

        {error && (
          <div className="p-3 bg-[#FECDD3] border-2 border-black rounded-xl text-xs font-bold text-red-900 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleJoin} className="space-y-4">
          <div>
            <label className="block text-xs font-black uppercase text-gray-700 mb-1">Room Code or Invite Token</label>
            <div className="relative">
              <Key className="w-4 h-4 absolute left-3 top-3 text-gray-400" />
              <input
                type="text"
                value={codeOrToken}
                onChange={(e) => setCodeOrToken(e.target.value.toUpperCase())}
                placeholder="e.g. PLUTO-A1B2-C3D4"
                className="w-full pl-9 pr-3 py-2.5 border-2 border-black rounded-xl text-xs font-mono font-bold tracking-wider uppercase focus:bg-yellow-50 outline-none"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-[#FFE600] border-2 border-black rounded-xl text-xs font-black uppercase shadow-[3px_3px_0px_0px_#000] hover:bg-yellow-400 flex items-center justify-center space-x-2 disabled:opacity-50"
          >
            <span>{loading ? 'Validating...' : 'Enter Waiting Room'}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <div className="text-center pt-2">
          <button
            type="button"
            onClick={() => onNavigate('/')}
            className="text-xs font-bold text-gray-500 hover:text-black underline"
          >
            Return to Self-Practice Mode
          </button>
        </div>
      </div>
    </div>
  )
}

