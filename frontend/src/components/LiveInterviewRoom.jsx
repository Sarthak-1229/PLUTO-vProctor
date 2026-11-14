import React, { useState, useEffect, useRef } from 'react'
import { Mic, MicOff, Video, VideoOff, ScreenShare, PhoneOff, Clock, User, ShieldAlert, CheckCircle2, ChevronRight, AlertTriangle } from 'lucide-react'
import { authFetch, getAccessToken } from '../utils/authClient'

export function LiveInterviewRoom({ roomId, currentUser, onLeaveRoom }) {
  const [snapshot, setSnapshot] = useState(null)
  const [occupants, setOccupants] = useState([])
  const [micEnabled, setMicEnabled] = useState(true)
  const [videoEnabled, setVideoEnabled] = useState(true)
  const [isScreenSharing, setIsScreenSharing] = useState(false)
  const [wsConnected, setWsConnected] = useState(false)
  const [webrtcConnected, setWebrtcConnected] = useState(false)
  const [timeLeft, setTimeLeft] = useState(180)
  const [connectionMessage, setConnectionMessage] = useState('Connecting to live session...')
  const [error, setError] = useState('')

  const localVideoRef = useRef(null)
  const remoteVideoRef = useRef(null)
  const localStreamRef = useRef(null)
  const screenTrackRef = useRef(null)
  const pcRef = useRef(null)
  const wsRef = useRef(null)
  const heartbeatTimerRef = useRef(null)

  const isHost = currentUser?.role === 'admin' || currentUser?.role === 'super_admin'

  // 1. Fetch initial snapshot
  useEffect(() => {
    let active = true
    async function loadSnapshot() {
      try {
        const res = await authFetch(`/api/rooms/${roomId}/snapshot`)
        if (!res.ok) {
          setError('Failed to load room snapshot or access forbidden.')
          return
        }
        const data = await res.json()
        if (active) {
          setSnapshot(data)
          if (data.current_question?.time_limit_seconds) {
            setTimeLeft(data.current_question.time_limit_seconds)
          }
        }
      } catch {
        if (active) setError('Network error fetching room state.')
      }
    }
    loadSnapshot()
    return () => {
      active = false
    }
  }, [roomId])

  // 2. Initialize WebRTC Peer Connection and Local Media Stream
  useEffect(() => {
    let active = true

    async function setupLocalMediaAndWebRTC() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 1280, height: 720 },
          audio: true,
        })
        if (!active) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        localStreamRef.current = stream
        if (localVideoRef.current) {
          localVideoRef.current.srcObject = stream
        }

        const iceServers = snapshot?.ice_servers || [{ urls: 'stun:stun.l.google.com:19302' }]
        const pc = new RTCPeerConnection({ iceServers })
        pcRef.current = pc

        // Add local tracks to peer connection
        stream.getTracks().forEach((track) => pc.addTrack(track, stream))

        // Remote track handler
        pc.ontrack = (event) => {
          if (remoteVideoRef.current && event.streams[0]) {
            remoteVideoRef.current.srcObject = event.streams[0]
            setWebrtcConnected(true)
          }
        }

        // ICE candidate handler
        pc.onicecandidate = (event) => {
          if (event.candidate && wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(
              JSON.stringify({
                type: 'webrtc.signal',
                signal_type: 'ice-candidate',
                payload: event.candidate.toJSON(),
              })
            )
          }
        }

        pc.onconnectionstatechange = () => {
          if (pc.connectionState === 'connected') {
            setWebrtcConnected(true)
            setConnectionMessage('Live peer-to-peer connection established')
          } else if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
            setWebrtcConnected(false)
            setConnectionMessage('Media stream reconnecting...')
          }
        }

        // Connect WebSocket signaling after PC is prepared
        setupWebSocket(pc)
      } catch (err) {
        if (active) {
          setError('Camera or microphone access denied. Please grant device permissions.')
        }
      }
    }

    if (snapshot && !pcRef.current) {
      setupLocalMediaAndWebRTC()
    }

    return () => {
      active = false
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current)
      if (wsRef.current) wsRef.current.close()
      if (pcRef.current) pcRef.current.close()
      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((t) => t.stop())
      }
    }
  }, [snapshot, roomId])

  // 3. WebSocket Signaling Setup
  const setupWebSocket = (pc) => {
    const token = getAccessToken()
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/rooms/${roomId}/ws?token=${token}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = async () => {
      setWsConnected(true)
      setConnectionMessage('Signaling server connected')

      // If host, initiate WebRTC offer
      if (isHost && pc) {
        try {
          const offer = await pc.createOffer()
          await pc.setLocalDescription(offer)
          ws.send(
            JSON.stringify({
              type: 'webrtc.signal',
              signal_type: 'offer',
              payload: offer,
            })
          )
        } catch (e) {
          console.warn('Failed creating initial offer:', e)
        }
      }

      // Heartbeat ping
      heartbeatTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }))
        }
      }, 15000)
    }

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data)
        const type = msg.type

        if (type === 'room.snapshot') {
          if (msg.snapshot) setSnapshot(msg.snapshot)
          if (msg.occupants) setOccupants(msg.occupants)
        } else if (type === 'participant.joined' || type === 'participant.left') {
          // Re-fetch snapshot or update occupants
          const res = await authFetch(`/api/rooms/${roomId}/snapshot`)
          if (res.ok) setSnapshot(await res.json())
        } else if (type === 'question.active') {
          setSnapshot((prev) => (prev ? { ...prev, current_question: msg.question } : prev))
          setTimeLeft(msg.question?.time_limit_seconds || 180)
        } else if (type === 'room.state_changed') {
          setSnapshot((prev) => (prev ? { ...prev, status: msg.status } : prev))
        } else if (type === 'room.ended') {
          setSnapshot((prev) => (prev ? { ...prev, status: 'COMPLETED' } : prev))
        } else if (type === 'webrtc.signal' && pc) {
          const { signal_type, payload } = msg
          if (signal_type === 'offer') {
            await pc.setRemoteDescription(new RTCSessionDescription(payload))
            const answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            ws.send(
              JSON.stringify({
                type: 'webrtc.signal',
                signal_type: 'answer',
                payload: answer,
              })
            )
          } else if (signal_type === 'answer') {
            await pc.setRemoteDescription(new RTCSessionDescription(payload))
          } else if (signal_type === 'ice-candidate') {
            await pc.addIceCandidate(new RTCIceCandidate(payload))
          }
        }
      } catch (e) {
        console.warn('Signaling parse error:', e)
      }
    }

    ws.onclose = () => {
      setWsConnected(false)
      setConnectionMessage('Signaling disconnected')
    }
  }

  // Active question countdown timer
  useEffect(() => {
    if (snapshot?.status !== 'LIVE') return undefined
    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [snapshot?.status, snapshot?.current_question?.ordinal])

  // Media Controls
  const toggleMic = () => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0]
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled
        setMicEnabled(audioTrack.enabled)
      }
    }
  }

  const toggleVideo = () => {
    if (localStreamRef.current) {
      const videoTrack = localStreamRef.current.getVideoTracks()[0]
      if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled
        setVideoEnabled(videoTrack.enabled)
      }
    }
  }

  const toggleScreenShare = async () => {
    if (!pcRef.current) return
    if (!isScreenSharing) {
      try {
        const screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true })
        const screenTrack = screenStream.getVideoTracks()[0]
        screenTrackRef.current = screenTrack

        const sender = pcRef.current.getSenders().find((s) => s.track?.kind === 'video')
        if (sender) sender.replaceTrack(screenTrack)
        if (localVideoRef.current) localVideoRef.current.srcObject = screenStream

        screenTrack.onended = () => {
          stopScreenShare()
        }
        setIsScreenSharing(true)
      } catch {
        console.warn('Screen share canceled or failed')
      }
    } else {
      stopScreenShare()
    }
  }

  const stopScreenShare = () => {
    if (screenTrackRef.current) {
      screenTrackRef.current.stop()
      screenTrackRef.current = null
    }
    if (localStreamRef.current && pcRef.current) {
      const camTrack = localStreamRef.current.getVideoTracks()[0]
      const sender = pcRef.current.getSenders().find((s) => s.track?.kind === 'video')
      if (sender && camTrack) sender.replaceTrack(camTrack)
      if (localVideoRef.current) localVideoRef.current.srcObject = localStreamRef.current
    }
    setIsScreenSharing(false)
  }

  const formatTimer = (sec) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m}:${s < 10 ? '0' : ''}${s}`
  }

  const activeQ = snapshot?.current_question

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      {/* Top Session Bar */}
      <div className="bg-white border-2 border-black rounded-2xl px-5 py-3 shadow-[3px_3px_0px_0px_#000] flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center space-x-3">
          <span
            className={`w-3 h-3 rounded-full border border-black ${
              wsConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            }`}
          />
          <div>
            <h1 className="text-base font-black uppercase text-black">{snapshot?.title || 'Hosted Interview'}</h1>
            <span className="text-[11px] font-bold text-gray-500">
              {connectionMessage} • Status: {snapshot?.status || 'CONNECTING'}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div className="px-3 py-1 bg-[#FFE600] border-2 border-black rounded-xl text-xs font-black uppercase flex items-center space-x-1.5 shadow-[2px_2px_0px_0px_#000]">
            <Clock className="w-3.5 h-3.5" />
            <span>Time: {formatTimer(timeLeft)}</span>
          </div>
          <button
            type="button"
            onClick={onLeaveRoom}
            className="px-3 py-1 bg-[#FECDD3] text-red-950 border-2 border-black rounded-xl text-xs font-black uppercase hover:bg-red-200"
          >
            Leave Room
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-[#FECDD3] border-2 border-black rounded-xl text-xs font-bold text-red-900 flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Video & Proctoring Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Videos Area (3 columns) */}
        <div className="lg:col-span-3 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Remote Peer Video Stream */}
            <div className="relative aspect-video bg-black border-2 border-black rounded-2xl overflow-hidden shadow-[4px_4px_0px_0px_#000] flex items-center justify-center">
              <video
                ref={remoteVideoRef}
                autoPlay
                playsInline
                className="w-full h-full object-cover"
              />
              {!webrtcConnected && (
                <div className="absolute inset-0 flex flex-col items-center justify-center p-4 text-center bg-gray-900/80 text-white space-y-2">
                  <User className="w-10 h-10 text-gray-400 animate-pulse" />
                  <span className="text-xs font-bold uppercase tracking-wider">
                    Waiting for peer video stream...
                  </span>
                </div>
              )}
              <div className="absolute top-2 left-2 px-2 py-0.5 bg-black/70 text-white rounded text-[10px] font-black uppercase">
                {isHost ? 'Candidate Stream' : 'Interviewer Stream'}
              </div>
            </div>

            {/* Local Video Stream */}
            <div className="relative aspect-video bg-black border-2 border-black rounded-2xl overflow-hidden shadow-[4px_4px_0px_0px_#000]">
              <video
                ref={localVideoRef}
                autoPlay
                playsInline
                muted
                className={`w-full h-full object-cover ${isScreenSharing ? '' : 'mirror'}`}
              />
              <div className="absolute top-2 left-2 px-2 py-0.5 bg-black/70 text-white rounded text-[10px] font-black uppercase">
                You ({currentUser?.full_name || 'Me'})
              </div>
            </div>
          </div>

          {/* Media Controls Toolbar */}
          <div className="p-3 bg-white border-2 border-black rounded-2xl shadow-[3px_3px_0px_0px_#000] flex items-center justify-center space-x-4">
            <button
              type="button"
              onClick={toggleMic}
              className={`p-3 rounded-xl border-2 border-black shadow-[2px_2px_0px_0px_#000] transition-colors ${
                micEnabled ? 'bg-white hover:bg-gray-100' : 'bg-red-400 text-white'
              }`}
            >
              {micEnabled ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
            </button>

            <button
              type="button"
              onClick={toggleVideo}
              className={`p-3 rounded-xl border-2 border-black shadow-[2px_2px_0px_0px_#000] transition-colors ${
                videoEnabled ? 'bg-white hover:bg-gray-100' : 'bg-red-400 text-white'
              }`}
            >
              {videoEnabled ? <Video className="w-5 h-5" /> : <VideoOff className="w-5 h-5" />}
            </button>

            <button
              type="button"
              onClick={toggleScreenShare}
              className={`p-3 rounded-xl border-2 border-black shadow-[2px_2px_0px_0px_#000] transition-colors ${
                isScreenSharing ? 'bg-[#FFE600]' : 'bg-white hover:bg-gray-100'
              }`}
            >
              <ScreenShare className="w-5 h-5" />
            </button>

            <button
              type="button"
              onClick={onLeaveRoom}
              className="p-3 rounded-xl border-2 border-black bg-red-500 text-white shadow-[2px_2px_0px_0px_#000] hover:bg-red-600"
            >
              <PhoneOff className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Live Synchronized Question & Proctoring Board (1 column) */}
        <div className="space-y-4">
          <div className="bg-white border-2 border-black rounded-2xl p-4 shadow-[4px_4px_0px_0px_#000] space-y-3">
            <span className="text-[10px] font-black uppercase text-gray-500 tracking-wider">
              Active Question {activeQ?.ordinal ? `#${activeQ.ordinal}` : ''}
            </span>

            {activeQ ? (
              <div className="space-y-2">
                <p className="text-sm font-bold text-black leading-snug">
                  {activeQ.question_text || activeQ.text || 'Preparing question...'}
                </p>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-900 border border-black text-[10px] font-bold">
                    {activeQ.domain || 'General'}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-yellow-100 text-yellow-900 border border-black text-[10px] font-bold">
                    {activeQ.difficulty || 'Intermediate'}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-xs font-semibold text-gray-500">
                Waiting for the interviewer to present the next question...
              </p>
            )}
          </div>

          {/* Proctoring Status Pill */}
          <div className="bg-[#F4F0EA] border-2 border-black rounded-2xl p-4 space-y-2">
            <div className="flex items-center space-x-2">
              <ShieldAlert className="w-4 h-4 text-indigo-700" />
              <span className="text-xs font-black uppercase text-black">Active Proctoring</span>
            </div>
            <p className="text-[11px] font-medium text-gray-700 leading-tight">
              Preset: <strong>{snapshot?.proctoring_preset || 'strict'}</strong>. Gaze tracking, posture, and speech fluency are evaluated in realtime.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

