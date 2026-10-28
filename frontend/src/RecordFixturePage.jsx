import { useState, useEffect, useRef } from 'react'
import { Video, Mic, StopCircle, Play, Download, CheckCircle, Tag, RotateCcw } from 'lucide-react'
import plutoLogo from './assets/logo.png'

export default function RecordFixturePage() {
  const [isRecording, setIsRecording] = useState(false)
  const [fixtureId, setFixtureId] = useState('fixture_001')
  const [referenceTranscript, setReferenceTranscript] = useState('')
  const [events, setEvents] = useState([])
  const [elapsedSec, setElapsedSec] = useState(0)
  const [isLookingAway, setIsLookingAway] = useState(false)
  const [isPausing, setIsPausing] = useState(false)
  const [cameraActive, setCameraActive] = useState(false)

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const recordedChunksRef = useRef([])
  const recordingStartTimeRef = useRef(null)
  const timerIntervalRef = useRef(null)
  const lookAwayStartRef = useRef(null)
  const pauseStartRef = useRef(null)

  // Start Camera & Mic on mount
  useEffect(() => {
    async function initMedia() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480, frameRate: 30 },
          audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: false },
        })
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
        setCameraActive(true)
      } catch (err) {
        console.error('Failed to get media devices:', err)
        alert('Could not access camera/mic: ' + err.message)
      }
    }
    initMedia()

    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
      }
      clearInterval(timerIntervalRef.current)
    }
  }, [])

  // Keyboard hotkey handler
  useEffect(() => {
    function handleKeyDown(e) {
      if (!isRecording) return
      // Don't trigger hotkeys if typing in textarea
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

      const now = (Date.now() - recordingStartTimeRef.current) / 1000.0

      if (e.key === 'l' || e.key === 'L') {
        e.preventDefault()
        if (!isLookingAway) {
          lookAwayStartRef.current = now
          setIsLookingAway(true)
        } else {
          const tStart = lookAwayStartRef.current
          const tEnd = now
          setEvents((prev) => [
            ...prev,
            { type: 'LOOK_AWAY', start: round2(tStart), end: round2(tEnd), duration: round2(tEnd - tStart) },
          ])
          setIsLookingAway(false)
          lookAwayStartRef.current = null
        }
      } else if (e.key === 'f' || e.key === 'F') {
        e.preventDefault()
        const tStart = Math.max(0, now - 0.4)
        const tEnd = now + 0.2
        setEvents((prev) => [
          ...prev,
          { type: 'FILLER', start: round2(tStart), end: round2(tEnd), text: 'spoken filler' },
        ])
      } else if (e.key === 'p' || e.key === 'P') {
        e.preventDefault()
        if (!isPausing) {
          pauseStartRef.current = now
          setIsPausing(true)
        } else {
          const tStart = pauseStartRef.current
          const tEnd = now
          setEvents((prev) => [
            ...prev,
            { type: 'PAUSE', start: round2(tStart), end: round2(tEnd), duration: round2(tEnd - tStart) },
          ])
          setIsPausing(false)
          pauseStartRef.current = null
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isRecording, isLookingAway, isPausing])

  const round2 = (num) => Math.round(num * 100) / 100

  const startRecording = () => {
    if (!streamRef.current) return
    recordedChunksRef.current = []
    setEvents([])
    setElapsedSec(0)
    setIsLookingAway(false)
    setIsPausing(false)

    try {
      const recorder = new MediaRecorder(streamRef.current, { mimeType: 'video/webm' })
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) recordedChunksRef.current.push(e.data)
      }
      recorder.start(500)
      mediaRecorderRef.current = recorder

      recordingStartTimeRef.current = Date.now()
      setIsRecording(true)

      timerIntervalRef.current = setInterval(() => {
        if (recordingStartTimeRef.current) {
          const sec = (Date.now() - recordingStartTimeRef.current) / 1000.0
          setElapsedSec(sec)
        }
      }, 100)
    } catch (err) {
      alert('MediaRecorder error: ' + err.message)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    clearInterval(timerIntervalRef.current)
    setIsRecording(false)

    // Close any active toggles
    const finalSec = (Date.now() - recordingStartTimeRef.current) / 1000.0
    if (isLookingAway && lookAwayStartRef.current !== null) {
      setEvents((prev) => [
        ...prev,
        { type: 'LOOK_AWAY', start: round2(lookAwayStartRef.current), end: round2(finalSec), duration: round2(finalSec - lookAwayStartRef.current) },
      ])
      setIsLookingAway(false)
    }
    if (isPausing && pauseStartRef.current !== null) {
      setEvents((prev) => [
        ...prev,
        { type: 'PAUSE', start: round2(pauseStartRef.current), end: round2(finalSec), duration: round2(finalSec - pauseStartRef.current) },
      ])
      setIsPausing(false)
    }
  }

  const handleDownloadAndSave = async () => {
    if (recordedChunksRef.current.length === 0) {
      alert('No recorded chunks available!')
      return
    }

    const videoBlob = new Blob(recordedChunksRef.current, { type: 'video/webm' })
    const labelsData = {
      fixture_id: fixtureId,
      created_at: new Date().toISOString(),
      duration_sec: round2(elapsedSec),
      reference_transcript: referenceTranscript.trim(),
      labels: events,
    }
    const jsonBlob = new Blob([JSON.stringify(labelsData, null, 2)], { type: 'application/json' })

    // Trigger local downloads
    const vUrl = URL.createObjectURL(videoBlob)
    const vLink = document.createElement('a')
    vLink.href = vUrl
    vLink.download = `${fixtureId}.webm`
    vLink.click()

    const jUrl = URL.createObjectURL(jsonBlob)
    const jLink = document.createElement('a')
    jLink.href = jUrl
    jLink.download = `${fixtureId}.labels.json`
    jLink.click()

    // Upload to backend fixtures folder
    try {
      const formData = new FormData()
      formData.append('fixture_id', fixtureId)
      formData.append('video_file', videoBlob, `${fixtureId}.webm`)
      formData.append('labels_json', JSON.stringify(labelsData))

      const res = await fetch('/api/fixtures/save', {
        method: 'POST',
        body: formData,
      })
      if (res.ok) {
        alert(`Saved ${fixtureId} directly to backend fixtures directory!`)
      }
    } catch (e) {
      console.warn('Backend fixture save endpoint skipped or failed:', e)
    }
  }

  return (
    <div className="min-h-screen bg-[#F4F0EA] text-slate-900 p-6 font-sans">
      <header className="max-w-5xl mx-auto flex items-center justify-between border-b-[3px] border-black pb-4 mb-6">
        <div className="flex items-center space-x-3">
          <img src={plutoLogo} alt="Logo" className="w-10 h-10 object-contain border-2 border-black rounded-lg bg-white p-1" />
          <div>
            <h1 className="text-xl font-black uppercase tracking-tight">PLUTO Ground-Truth Fixture Recorder</h1>
            <p className="text-xs font-bold text-slate-600">Dev Tool: Real-time Hotkey Annotation for Benchmark Fixtures</p>
          </div>
        </div>
        <a
          href="/"
          className="px-4 py-2 border-2 border-black rounded-xl bg-white font-black text-xs uppercase shadow-[2px_2px_0px_0px_#000]"
        >
          Return to App
        </a>
      </header>

      <main className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left Column: Video Window & Hotkey Controls */}
        <div className="space-y-4">
          <div className="relative rounded-2xl overflow-hidden aspect-video bg-black border-[3px] border-black shadow-[5px_5px_0px_0px_#000]">
            <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover mirror" />

            {/* Live Status Overlay */}
            <div className="absolute top-3 left-3 flex items-center space-x-2">
              <span className={`px-2.5 py-1 text-xs font-black uppercase rounded border-2 border-black ${isRecording ? 'bg-red-500 text-white animate-pulse' : 'bg-white text-black'}`}>
                {isRecording ? 'REC' : 'STANDBY'}
              </span>
              <span className="px-2.5 py-1 text-xs font-mono font-black rounded border-2 border-black bg-yellow-300">
                {elapsedSec.toFixed(1)}s
              </span>
            </div>

            {/* Active Toggles Indicators */}
            <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between pointer-events-none">
              <span className={`px-3 py-1 text-xs font-black rounded border-2 border-black ${isLookingAway ? 'bg-orange-500 text-white animate-bounce' : 'bg-slate-800 text-slate-400'}`}>
                {isLookingAway ? 'EYES: LOOKING AWAY (L)' : 'EYES: DIRECT'}
              </span>
              <span className={`px-3 py-1 text-xs font-black rounded border-2 border-black ${isPausing ? 'bg-purple-600 text-white animate-bounce' : 'bg-slate-800 text-slate-400'}`}>
                {isPausing ? 'PAUSE ACTIVE (P)' : 'SPEAKING'}
              </span>
            </div>
          </div>

          {/* Controls */}
          <div className="flex items-center space-x-3">
            {!isRecording ? (
              <button
                onClick={startRecording}
                disabled={!cameraActive}
                className="flex-1 py-3 bg-[#A7F3D0] hover:bg-[#86efac] border-[3px] border-black rounded-xl font-black uppercase text-sm shadow-[4px_4px_0px_0px_#000] flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                <Play className="w-5 h-5 fill-current" />
                <span>Start Recording</span>
              </button>
            ) : (
              <button
                onClick={stopRecording}
                className="flex-1 py-3 bg-[#FF8080] hover:bg-[#f87171] border-[3px] border-black rounded-xl font-black uppercase text-sm shadow-[4px_4px_0px_0px_#000] flex items-center justify-center space-x-2 text-white"
              >
                <StopCircle className="w-5 h-5 fill-current" />
                <span>Stop Recording</span>
              </button>
            )}
          </div>

          {/* Hotkey Instructions */}
          <div className="bg-white border-2 border-black rounded-xl p-4 shadow-[3px_3px_0px_0px_#000] space-y-2 text-xs">
            <h3 className="font-black uppercase tracking-wide flex items-center space-x-1">
              <Tag className="w-4 h-4" />
              <span>Keyboard Annotation Hotkeys (Press while recording):</span>
            </h3>
            <ul className="space-y-1 font-mono font-bold text-slate-700">
              <li><span className="px-1.5 py-0.5 bg-yellow-200 border border-black rounded text-black font-black">L</span> : Toggle Looking Away (start / stop look-away window)</li>
              <li><span className="px-1.5 py-0.5 bg-yellow-200 border border-black rounded text-black font-black">F</span> : Log Spoken Filler (instant timestamp for "umm", "uh", "like")</li>
              <li><span className="px-1.5 py-0.5 bg-yellow-200 border border-black rounded text-black font-black">P</span> : Toggle Deliberate Pause (start / stop hesitation window)</li>
            </ul>
          </div>
        </div>

        {/* Right Column: Metadata, Typed Reference Transcript & Event Stream */}
        <div className="space-y-4">
          <div className="bg-white border-[3px] border-black rounded-2xl p-5 shadow-[5px_5px_0px_0px_#000] space-y-4">
            <div>
              <label className="block text-xs font-black uppercase text-slate-600 mb-1">Fixture Identifier</label>
              <input
                type="text"
                value={fixtureId}
                onChange={(e) => setFixtureId(e.target.value)}
                className="w-full bg-[#F4F0EA] border-2 border-black rounded-xl px-3 py-2 text-sm font-bold font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-black uppercase text-slate-600 mb-1">
                Typed Reference Transcript (Ground Truth for WER)
              </label>
              <textarea
                rows={3}
                value={referenceTranscript}
                onChange={(e) => setReferenceTranscript(e.target.value)}
                placeholder="Type exactly what was spoken in this recording (including umms, uhs, and full sentences)..."
                className="w-full bg-[#F4F0EA] border-2 border-black rounded-xl p-3 text-xs font-mono font-medium focus:outline-none focus:bg-white"
              />
            </div>

            {/* Event Stream */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-black uppercase text-slate-600">Logged Events ({events.length})</span>
                {events.length > 0 && (
                  <button onClick={() => setEvents([])} className="text-[10px] font-bold text-red-600 hover:underline">
                    Clear Events
                  </button>
                )}
              </div>
              <div className="max-h-48 overflow-y-auto space-y-1.5 border-2 border-black rounded-xl p-2 bg-[#F4F0EA]">
                {events.length === 0 ? (
                  <p className="text-xs font-bold text-slate-400 text-center py-4">No events logged yet. Press L, F, or P while recording.</p>
                ) : (
                  events.map((ev, i) => (
                    <div key={i} className="flex items-center justify-between text-xs font-mono font-bold bg-white px-2 py-1 border border-black rounded shadow-[1px_1px_0px_0px_#000]">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-black ${ev.type === 'LOOK_AWAY' ? 'bg-orange-200 text-orange-900' : ev.type === 'FILLER' ? 'bg-blue-200 text-blue-900' : 'bg-purple-200 text-purple-900'}`}>
                        {ev.type}
                      </span>
                      <span>{ev.start}s - {ev.end}s</span>
                      <span className="text-slate-500">{ev.duration ? `${ev.duration}s` : ev.text || ''}</span>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Save & Download */}
            <button
              onClick={handleDownloadAndSave}
              disabled={recordedChunksRef.current.length === 0}
              className="w-full py-3 bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black rounded-xl font-black uppercase text-xs shadow-[3px_3px_0px_0px_#000] flex items-center justify-center space-x-2 disabled:opacity-40"
            >
              <Download className="w-4 h-4" />
              <span>Save & Download Fixture (.webm + .json)</span>
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}

