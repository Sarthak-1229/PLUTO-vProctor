import React, { useState, useEffect, useRef } from 'react'
import { Camera, Mic, Wifi, CheckCircle2, AlertTriangle, Clock, ShieldCheck, Play } from 'lucide-react'
import { authFetch } from '../utils/authClient'

export function WaitingRoom({ roomSnapshot, onAdmitted, onLeave }) {
  const [cameraOk, setCameraOk] = useState(false)
  const [micOk, setMicOk] = useState(false)
  const [latencyMs, setLatencyMs] = useState(null)
  const [checking, setChecking] = useState(true)
  const [error, setError] = useState('')
  const videoRef = useRef(null)
  const streamRef = useRef(null)

  useEffect(() => {
    let active = true

    async function runPreflight() {
      setChecking(true)
      try {
        // 1. Camera & Mic Check
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480 },
          audio: true,
        })
        if (!active) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
        setCameraOk(true)
        setMicOk(true)

        // 2. Latency Ping Check
        const t0 = performance.now()
        const pingRes = await fetch('/api/health')
        const t1 = performance.now()
        const measured = Math.round(t1 - t0)
        setLatencyMs(measured)

        // 3. Post device check status to backend
        if (roomSnapshot?.id) {
          await authFetch(`/api/rooms/${roomSnapshot.id}/device-check`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              camera_ok: true,
              mic_ok: true,
              latency_ms: measured,
              browser: navigator.userAgent,
            }),
          })
        }
      } catch (err) {
        if (active) {
          setError('Could not access camera or microphone. Please verify device permissions in your browser.')
        }
      } finally {
        if (active) setChecking(false)
      }
    }

    runPreflight()

    return () => {
      active = false
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
    }
  }, [roomSnapshot?.id])

  const allChecksPassed = cameraOk && micOk && latencyMs !== null

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b-2 border-black pb-4">
          <div>
            <span className="px-2.5 py-0.5 rounded-full bg-[#FFE600] border border-black text-[10px] font-black uppercase">
              Waiting Room & Pre-flight
            </span>
            <h1 className="text-2xl font-black uppercase text-black mt-1">
              {roomSnapshot?.title || 'Hosted Technical Interview'}
            </h1>
          </div>
          <div className="flex items-center space-x-2 text-xs font-bold text-gray-600">
            <Clock className="w-4 h-4" />
            <span>Duration: {Math.round((roomSnapshot?.duration_seconds || 2700) / 60)} mins</span>
          </div>
        </div>

        {error && (
          <div className="p-4 bg-[#FECDD3] border-2 border-black rounded-xl text-xs font-bold text-red-900 flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Video Preview & Preflight checklist */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
          <div className="relative aspect-video bg-black border-2 border-black rounded-2xl overflow-hidden shadow-[3px_3px_0px_0px_#000]">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover mirror"
            />
            <div className="absolute top-2 left-2 px-2 py-0.5 bg-black/70 text-white rounded text-[10px] font-black uppercase">
              Camera Feed Preview
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-xs font-black uppercase text-black tracking-wider">Device Preflight Status</h3>

            <div className="p-3 bg-[#F4F0EA] border-2 border-black rounded-xl flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Camera className="w-4 h-4" />
                <span className="text-xs font-bold">Webcam Video Stream</span>
              </div>
              {cameraOk ? (
                <span className="flex items-center text-green-700 text-xs font-black">
                  <CheckCircle2 className="w-4 h-4 mr-1" /> Ready
                </span>
              ) : (
                <span className="text-amber-700 text-xs font-black">Testing...</span>
              )}
            </div>

            <div className="p-3 bg-[#F4F0EA] border-2 border-black rounded-xl flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Mic className="w-4 h-4" />
                <span className="text-xs font-bold">Microphone Audio</span>
              </div>
              {micOk ? (
                <span className="flex items-center text-green-700 text-xs font-black">
                  <CheckCircle2 className="w-4 h-4 mr-1" /> Ready
                </span>
              ) : (
                <span className="text-amber-700 text-xs font-black">Testing...</span>
              )}
            </div>

            <div className="p-3 bg-[#F4F0EA] border-2 border-black rounded-xl flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Wifi className="w-4 h-4" />
                <span className="text-xs font-bold">Network Round-Trip Latency</span>
              </div>
              {latencyMs !== null ? (
                <span className="flex items-center text-green-700 text-xs font-black">
                  <CheckCircle2 className="w-4 h-4 mr-1" /> {latencyMs} ms
                </span>
              ) : (
                <span className="text-amber-700 text-xs font-black">Measuring...</span>
              )}
            </div>

            <div className="p-3 bg-[#E0E7FF] border-2 border-black rounded-xl flex items-center space-x-2 text-xs font-bold text-indigo-900">
              <ShieldCheck className="w-4 h-4 flex-shrink-0" />
              <span>
                Proctoring preset: <strong>{roomSnapshot?.proctoring_preset || 'strict'}</strong>. Gaze and motion monitoring will activate upon interview start.
              </span>
            </div>
          </div>
        </div>

        {/* Status Callout */}
        <div className="p-4 bg-[#FFE600] border-2 border-black rounded-2xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <h4 className="text-sm font-black uppercase text-black">
              {roomSnapshot?.status === 'LIVE'
                ? 'The interview has started!'
                : 'Waiting for Host to Start Interview'}
            </h4>
            <p className="text-xs font-semibold text-gray-800 mt-0.5">
              {roomSnapshot?.status === 'LIVE'
                ? 'Your interviewer is ready. Click enter room to connect live.'
                : 'Your equipment is verified. You will automatically be admitted when the interviewer begins.'}
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={onLeave}
              className="px-4 py-2 border-2 border-black rounded-xl text-xs font-black uppercase bg-white hover:bg-gray-100"
            >
              Exit
            </button>
            <button
              type="button"
              disabled={!allChecksPassed || roomSnapshot?.status !== 'LIVE'}
              onClick={onAdmitted}
              className="px-5 py-2.5 bg-black text-white rounded-xl text-xs font-black uppercase border-2 border-black shadow-[2px_2px_0px_0px_#FFE600] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-800 flex items-center space-x-1.5"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Enter Live Room</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

