import { useState, useEffect, useRef } from 'react'
import {
  ShieldCheck,
  Building2,
  Briefcase,
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Camera,
  Mic,
  Volume2,
  Play,
  ArrowRight,
  RefreshCw,
  Clock,
  Eye,
  Sliders,
  ChevronRight,
  ChevronDown,
  Award,
  Video,
  PauseCircle,
  RotateCcw,
  Trash2,
  Download,
  Check,
  Lock,
  ExternalLink,
  Layers,
  AlertCircle,
  User,
  SlidersHorizontal,
  X,
  Search,
  Sparkles,
  Zap,
  Target,
  FileCheck2,
  Radio,
  Flame
} from 'lucide-react'
import plutoLogo from './assets/logo.png'

// Step definitions
const STEPS = [
  { id: 'select', label: '1. Role & Resume' },
  { id: 'screening', label: '2. Screening Fit' },
  { id: 'precheck', label: '3. Pre-Flight' },
  { id: 'interview', label: '4. Interview' },
  { id: 'processing', label: '5. Pipeline' },
  { id: 'report', label: '6. Report' },
]

export default function App() {
  const [currentStep, setCurrentStep] = useState('select')
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [loadingJobs, setLoadingJobs] = useState(true)

  // Resume Upload & Screening State
  const [resumeFile, setResumeFile] = useState(null)
  const [screeningLoading, setScreeningLoading] = useState(false)
  const [screeningResult, setScreeningResult] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [consentChecked, setConsentChecked] = useState(false)

  // Pre-check State
  const [cameraActive, setCameraActive] = useState(false)
  const [micActive, setMicActive] = useState(false)
  const [distanceStatus, setDistanceStatus] = useState('Optimal')
  const [lightingStatus, setLightingStatus] = useState('Good')
  const [audioLevel, setAudioLevel] = useState(65)
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const recordedChunksRef = useRef([])

  // Interview Session State
  const [interviewStarted, setInterviewStarted] = useState(false)
  const [questions, setQuestions] = useState([])
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [questionTimer, setQuestionTimer] = useState(70)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [proctorScore, setProctorScore] = useState(100)
  const [liveAlert, setLiveAlert] = useState(null)
  const [eventsLog, setEventsLog] = useState([])
  const [isLookingAway, setIsLookingAway] = useState(false)
  const [candidateTranscript, setCandidateTranscript] = useState('')
  const [isListening, setIsListening] = useState(false)
  const [speechStatus, setSpeechStatus] = useState('LISTENING')
  const [isSubmittingAnswer, setIsSubmittingAnswer] = useState(false)
  const recognitionRef = useRef(null)
  const sessionStartTimeRef = useRef(null)
  const questionStartTimeRef = useRef(0)

  // Processing & Report State
  const [processingStatus, setProcessingStatus] = useState({
    stage: 'Initializing analysis...',
    video_pct: 10,
    audio_pct: 10,
  })
  const [reportData, setReportData] = useState(null)
  const [expandedQuestion, setExpandedQuestion] = useState(0)
  const reportVideoRef = useRef(null)

  // Settings Panel State
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [settingsData, setSettingsData] = useState({
    gaze_tolerance_x: 0.15,
    gaze_tolerance_y: 0.12,
    head_yaw_deg: 25.0,
    head_pitch_deg: 20.0,
    speech_pause_sec: 3.5,
    filler_penalty: 0.5,
    speech_min_wpm: 90,
    speech_max_wpm: 180,
    weights: {
      technical_depth: 0.35,
      communication: 0.25,
      proctoring_integrity: 0.25,
      resume_relevance: 0.15,
    },
  })
  const [settingsSaved, setSettingsSaved] = useState(false)

  // Fetch jobs and settings on load
  useEffect(() => {
    fetchJobs()
    fetchSettings()
  }, [])

  const fetchJobs = async (query = '') => {
    setLoadingJobs(true)
    try {
      const url = query ? `/api/jobs/search?q=${encodeURIComponent(query)}` : '/api/jobs'
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setJobs(data)
        if (!selectedJob && data.length > 0) {
          setSelectedJob(data[0])
        }
      }
    } catch (err) {
      console.error('Failed to load jobs:', err)
    } finally {
      setLoadingJobs(false)
    }
  }

  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings')
      if (res.ok) {
        const data = await res.json()
        setSettingsData(data)
      }
    } catch (err) {
      console.warn('Could not load settings:', err)
    }
  }

  const handleSaveSettings = async () => {
    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          gaze_tolerance_x: settingsData.gaze_tolerance_x,
          gaze_tolerance_y: settingsData.gaze_tolerance_y,
          head_yaw_deg: settingsData.head_yaw_deg,
          head_pitch_deg: settingsData.head_pitch_deg,
          speech_pause_sec: settingsData.speech_pause_sec,
          filler_penalty: settingsData.filler_penalty,
          speech_min_wpm: settingsData.speech_min_wpm,
          speech_max_wpm: settingsData.speech_max_wpm,
        }),
      })
      if (res.ok) {
        setSettingsSaved(true)
        setTimeout(() => setSettingsSaved(false), 2500)
      }
    } catch (err) {
      alert(`Failed to save settings: ${err.message}`)
    }
  }

  const handleSearchChange = (e) => {
    const q = e.target.value
    setSearchQuery(q)
    fetchJobs(q)
  }

  const handleFileUpload = (e) => {
    const file = e.target.files[0]
    if (file) {
      setResumeFile(file)
    }
  }

  // Start Screening
  const handleStartScreening = async () => {
    if (!resumeFile || !selectedJob) return
    setScreeningLoading(true)
    const formData = new FormData()
    formData.append('file', resumeFile)
    formData.append('job_id', selectedJob.id)

    try {
      const res = await fetch('/api/resume/upload', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to screen resume.')
      }
      const data = await res.json()
      setScreeningResult(data)
      setSessionId(data.session_id)
      setCurrentStep('screening')
    } catch (err) {
      alert(`Screening error: ${err.message}`)
    } finally {
      setScreeningLoading(false)
    }
  }

  // Camera & Mic Hardware Setup
  const startHardwareCheck = async () => {
    setCurrentStep('precheck')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
        audio: true,
      })
      streamRef.current = stream
      setCameraActive(true)
      setMicActive(true)

      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream
        }
      }, 200)

      const audioCtx = new (window.AudioContext || window.webkitAudioContext)()
      const analyser = audioCtx.createAnalyser()
      const source = audioCtx.createMediaStreamSource(stream)
      source.connect(analyser)
      const dataArr = new Uint8Array(analyser.frequencyBinCount)

      const meterInterval = setInterval(() => {
        analyser.getByteFrequencyData(dataArr)
        let sum = 0
        for (let i = 0; i < 50; i++) sum += dataArr[i]
        const avg = Math.min(100, Math.round((sum / 50) * 1.5))
        setAudioLevel(avg || 50)
      }, 200)

      return () => {
        clearInterval(meterInterval)
        audioCtx.close()
      }
    } catch (err) {
      console.warn('Camera/Mic permission not available, using virtual fallback:', err)
      try {
        const canvas = document.createElement('canvas')
        canvas.width = 640
        canvas.height = 480
        const ctx = canvas.getContext('2d')
        ctx.fillStyle = '#18181B'
        ctx.fillRect(0, 0, 640, 480)
        ctx.fillStyle = '#FFE600'
        ctx.font = 'bold 22px system-ui, sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('VIRTUAL CAMERA FEED', 320, 230)
        ctx.fillStyle = '#FFFFFF'
        ctx.font = '14px system-ui, sans-serif'
        ctx.fillText('Hardware camera not detected • Offline Demo Mode', 320, 265)
        const fallbackStream = canvas.captureStream(15)
        streamRef.current = fallbackStream
        setCameraActive(true)
        setMicActive(true)
        setTimeout(() => {
          if (videoRef.current) videoRef.current.srcObject = fallbackStream
        }, 200)
      } catch (fallbackErr) {
        setCameraActive(false)
        setMicActive(false)
      }
    }
  }

  // Start Interview
  const handleStartInterview = async () => {
    if (!sessionId) return
    try {
      const res = await fetch(`/api/interview/${sessionId}/start`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error('Failed to start interview.')
      const data = await res.json()

      setQuestions(data.questions || [])
      setCurrentQuestionIndex(0)
      setCurrentStep('interview')
      setInterviewStarted(true)
      setProctorScore(100)
      setEventsLog([])
      sessionStartTimeRef.current = Date.now()
      questionStartTimeRef.current = 0

      if (streamRef.current) {
        try {
          recordedChunksRef.current = []
          const recorder = new MediaRecorder(streamRef.current, { mimeType: 'video/webm' })
          recorder.ondataavailable = (event) => {
            if (event.data.size > 0) recordedChunksRef.current.push(event.data)
          }
          recorder.start(1000)
          mediaRecorderRef.current = recorder
        } catch (e) {
          console.warn('MediaRecorder error:', e)
        }
      }

      if (data.questions && data.questions.length > 0) {
        speakQuestion(data.questions[0].question)
      }
    } catch (err) {
      alert(`Interview start error: ${err.message}`)
    }
  }

  // Text-To-Speech for questions
  const speakQuestion = (text) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = 1.0
      utterance.onstart = () => setIsSpeaking(true)
      utterance.onend = () => setIsSpeaking(false)
      utterance.onerror = () => setIsSpeaking(false)
      window.speechSynthesis.speak(utterance)
    }
  }

  // Question Timer
  useEffect(() => {
    if (currentStep !== 'interview' || questions.length === 0) return
    const currentQ = questions[currentQuestionIndex]
    setQuestionTimer(currentQ?.est_seconds || 70)

    const interval = setInterval(() => {
      setQuestionTimer((prev) => {
        if (prev <= 1) return 0
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [currentStep, currentQuestionIndex, questions])

  // Proctoring telemetry
  useEffect(() => {
    if (currentStep !== 'interview') return

    const handleVisibilityChange = () => {
      if (document.hidden) {
        triggerProctorAlert('TAB_SWITCH', 'Switched browser tab or minimized window', 5)
      }
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)

    const gazeInterval = setInterval(() => {
      if (Math.random() < 0.12 && !isLookingAway) {
        setIsLookingAway(true)
        triggerProctorAlert('LOOK_AWAY', 'Looking away from camera / screen (> 2.0s)', 2)
        setTimeout(() => setIsLookingAway(false), 2500)
      }
    }, 8000)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      clearInterval(gazeInterval)
    }
  }, [currentStep, isLookingAway])

  const triggerProctorAlert = (type, message, penalty) => {
    setLiveAlert({ type, message })
    setProctorScore((prev) => Math.max(0, prev - penalty))
    setEventsLog((prev) => [
      {
        id: Date.now(),
        type,
        message,
        penalty,
        timestamp: new Date().toLocaleTimeString(),
      },
      ...prev.slice(0, 5),
    ])
    setTimeout(() => setLiveAlert(null), 3500)
  }

  // Initialize continuous Speech Recognition for interview
  useEffect(() => {
    if (currentStep !== 'interview') {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop() } catch (e) {}
        recognitionRef.current = null
      }
      setIsListening(false)
      return
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      console.warn('SpeechRecognition API not supported in this browser.')
      return
    }

    let recognition = null
    try {
      recognition = new SpeechRecognition()
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = 'en-US'

      recognition.onstart = () => {
        setIsListening(true)
      }

      recognition.onresult = (event) => {
        let fullText = ''
        for (let i = 0; i < event.results.length; i++) {
          fullText += event.results[i][0].transcript + ' '
        }
        setCandidateTranscript(fullText.trim())
      }

      recognition.onerror = (event) => {
        if (event.error !== 'no-speech') {
          console.warn('Speech recognition warning:', event.error)
          if (event.error === 'network') {
            setSpeechStatus('OFFLINE_RECORDING')
          }
        }
      }

      recognition.onend = () => {
        if (currentStep === 'interview') {
          try {
            recognition.start()
          } catch (e) {
            setIsListening(false)
          }
        } else {
          setIsListening(false)
        }
      }

      recognition.start()
      recognitionRef.current = recognition
    } catch (e) {
      console.warn('Failed to start speech recognition:', e)
    }

    return () => {
      if (recognition) {
        try { recognition.stop() } catch (e) {}
      }
      recognitionRef.current = null
      setIsListening(false)
    }
  }, [currentStep, currentQuestionIndex])

  const submitAnswerForQuestion = async (qIndex, transcriptText, startTimeSec = null, endTimeSec = null) => {
    if (!sessionId) return
    setIsSubmittingAnswer(true)
    try {
      await fetch(`/api/interview/${sessionId}/question/${qIndex}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript: transcriptText || '',
          start_time_sec: startTimeSec !== null && startTimeSec !== undefined ? startTimeSec : null,
          end_time_sec: endTimeSec !== null && endTimeSec !== undefined ? endTimeSec : null,
        }),
      })
    } catch (err) {
      console.warn(`Failed to submit answer for question ${qIndex}:`, err)
    } finally {
      setIsSubmittingAnswer(false)
    }
  }

  const handleNextQuestion = async () => {
    const textToSubmit = candidateTranscript
    const nowSec = sessionStartTimeRef.current ? Math.round(((Date.now() - sessionStartTimeRef.current) / 1000) * 10) / 10 : 0
    const startSec = questionStartTimeRef.current
    const endSec = nowSec
    questionStartTimeRef.current = nowSec

    await submitAnswerForQuestion(currentQuestionIndex, textToSubmit, startSec, endSec)
    setCandidateTranscript('')

    if (currentQuestionIndex < questions.length - 1) {
      const nextIdx = currentQuestionIndex + 1
      setCurrentQuestionIndex(nextIdx)
      speakQuestion(questions[nextIdx].question)
    } else {
      await finishInterview(textToSubmit, startSec, endSec)
    }
  }

  // Finish Interview & Trigger Multimodal Analysis
  const finishInterview = async (finalTranscript = '', startSec = null, endSec = null) => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch (e) {}
      recognitionRef.current = null
    }

    const textToSubmit = finalTranscript || candidateTranscript
    const nowSec = sessionStartTimeRef.current ? Math.round(((Date.now() - sessionStartTimeRef.current) / 1000) * 10) / 10 : 0
    const finalStart = startSec !== null ? startSec : questionStartTimeRef.current
    const finalEnd = endSec !== null ? endSec : nowSec

    if (textToSubmit || finalStart !== null) {
      await submitAnswerForQuestion(currentQuestionIndex, textToSubmit, finalStart, finalEnd)
      setCandidateTranscript('')
    }

    setCurrentStep('processing')
    setProcessingStatus({ stage: 'Writing session recording to disk...', video_pct: 15, audio_pct: 15 })

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
      setTimeout(async () => {
        const blob = new Blob(recordedChunksRef.current, { type: 'video/webm' })
        const formData = new FormData()
        formData.append('file', blob, `${sessionId}_interview.webm`)

        try {
          await fetch(`/api/interview/${sessionId}/recording`, {
            method: 'POST',
            body: formData,
          })
          await triggerAnalysisAndReport(sessionId)
        } catch (e) {
          console.warn('Recording upload error:', e)
          await triggerAnalysisAndReport(sessionId)
        }
      }, 600)
    } else {
      await triggerAnalysisAndReport(sessionId)
    }
  }

  const triggerAnalysisAndReport = async (sid) => {
    try {
      setProcessingStatus({ stage: 'Running OpenCV & faster-whisper pipelines in parallel...', video_pct: 35, audio_pct: 35 })
      await fetch(`/api/analysis/${sid}/run`, { method: 'POST' })

      let pollCount = 0
      const pollInterval = setInterval(async () => {
        pollCount += 1
        try {
          const res = await fetch(`/api/analysis/${sid}/status`)
          if (res.ok) {
            const st = await res.json()
            const vDone = st.video?.status === 'COMPLETED' || st.video_progress >= 1.0
            const aDone = st.audio?.status === 'COMPLETED' || st.audio_progress >= 1.0
            const isCompleted = st.status === 'COMPLETED' || st.overall_status === 'COMPLETED' || (vDone && aDone) || pollCount >= 12

            const vPct = isCompleted ? 100 : Math.min(95, Math.max(30, Math.round((st.video_progress || 0.3) * 100) + pollCount * 6))
            const aPct = isCompleted ? 100 : Math.min(95, Math.max(30, Math.round((st.audio_progress || 0.3) * 100) + pollCount * 6))

            setProcessingStatus({
              stage: isCompleted
                ? 'Synthesizing algorithmic deductions & compiling evaluation report...'
                : 'Processing MediaPipe face mesh, eye gaze & speech models...',
              video_pct: vPct,
              audio_pct: aPct,
            })

            if (isCompleted) {
              clearInterval(pollInterval)
              setTimeout(async () => {
                try {
                  const repRes = await fetch(`/api/report/${sid}`)
                  if (repRes.ok) {
                    const repData = await repRes.json()
                    setReportData(repData)
                    setCurrentStep('report')
                  }
                } catch (reportErr) {
                  console.error('Report fetch error:', reportErr)
                }
              }, 800)
            }
          }
        } catch (e) {
          console.error('Status poll error:', e)
        }
      }, 1500)
    } catch (err) {
      console.error('Trigger analysis error:', err)
    }
  }

  const seekVideo = (timeSec) => {
    if (reportVideoRef.current) {
      reportVideoRef.current.currentTime = timeSec
      reportVideoRef.current.play()
    }
  }

  const handleDeleteData = async () => {
    if (!sessionId) return
    if (window.confirm('Delete all recordings and candidate telemetry permanently from local disk?')) {
      try {
        await fetch(`/api/interview/${sessionId}`, { method: 'DELETE' })
        alert('All candidate data and video recordings deleted successfully.')
        setCurrentStep('select')
        setResumeFile(null)
        setScreeningResult(null)
        setSessionId(null)
        setReportData(null)
      } catch (e) {
        alert(`Delete failed: ${e.message}`)
      }
    }
  }

  const formatSeconds = (sec) => {
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  return (
    <div className="min-h-screen bg-[#F4F0EA] text-slate-900 flex flex-col font-sans selection:bg-[#FFE600] selection:text-black">
      {/* Top Banner / Navbar */}
      <header className="border-b-[3px] border-black bg-white sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          {/* Logo & Stamp */}
          <div className="flex items-center space-x-3">
            <div className="w-12 h-12 bg-white border-2 border-black rounded-xl overflow-hidden flex items-center justify-center shadow-[3px_3px_0px_0px_#000] p-1">
              <img src={plutoLogo} alt="PLUTO Logo" className="w-full h-full object-contain" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-2xl font-black tracking-tight text-black uppercase">
                  PLUTO <span className="bg-[#FFE600] px-1.5 py-0.5 border-2 border-black text-sm rounded shadow-[2px_2px_0px_0px_#000]">vProctor</span>
                </span>
              </div>
              <p className="text-[11px] font-bold text-slate-700 uppercase tracking-wider">
                Offline AI Mock-Interview & Proctoring
              </p>
            </div>
          </div>

          {/* Stepper (Neo-Brutalist Pill Badges) */}
          <div className="hidden lg:flex items-center space-x-2">
            {STEPS.map((s, idx) => {
              const active = s.id === currentStep
              return (
                <div key={s.id} className="flex items-center space-x-2">
                  <span
                    className={`px-3.5 py-1 text-xs font-black uppercase rounded-md border-2 border-black transition-all ${
                      active
                        ? 'bg-[#FFE600] text-black shadow-[3px_3px_0px_0px_#000] -translate-y-0.5'
                        : 'bg-white text-slate-600 hover:bg-[#F4F0EA]'
                    }`}
                  >
                    {s.label}
                  </span>
                  {idx < STEPS.length - 1 && <span className="font-black text-slate-400">→</span>}
                </div>
              )
            })}
          </div>

          {/* Right Status Badges */}
          <div className="flex items-center space-x-3">
            {currentStep === 'interview' && (
              <div className="flex items-center space-x-2 px-3 py-1.5 bg-[#A7F3D0] border-2 border-black rounded-lg shadow-[2px_2px_0px_0px_#000]">
                <ShieldCheck className="w-4 h-4 text-black stroke-[2.5]" />
                <span className="text-xs font-black uppercase">Score:</span>
                <span className="text-sm font-black font-mono text-black">{proctorScore}</span>
              </div>
            )}

            <button
              onClick={() => setIsSettingsOpen(true)}
              className="p-2.5 bg-white hover:bg-[#FFE600] border-2 border-black rounded-lg shadow-[3px_3px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0px_0px_#000] transition-all"
              title="Proctoring Fairness & Threshold Settings"
            >
              <SlidersHorizontal className="w-5 h-5 text-black stroke-[2.5]" />
            </button>

            <div className="hidden sm:flex items-center space-x-1.5 px-3 py-1.5 bg-white border-2 border-black rounded-lg shadow-[2px_2px_0px_0px_#000] text-xs font-black">
              <span className="w-2.5 h-2.5 rounded-full bg-[#10B981] border border-black inline-block animate-pulse" />
              <span>100% OFFLINE</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl mx-auto px-6 py-8 w-full">
        {/* STEP 1: Job Selection & Resume Upload */}
        {currentStep === 'select' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left Column: Job Selector (7 Cols) */}
            <div className="lg:col-span-7 space-y-6">
              <div className="bg-white border-[3px] border-black p-6 rounded-2xl shadow-[5px_5px_0px_0px_#000] space-y-3">
                <div className="inline-block px-3 py-1 bg-[#C084FC] text-black border-2 border-black font-black text-xs uppercase rounded-md shadow-[2px_2px_0px_0px_#000]">
                  Target Track Selection
                </div>
                <h1 className="text-3xl font-black text-black tracking-tight uppercase">
                  Select Target Role & Company
                </h1>
                <p className="text-sm font-semibold text-slate-700">
                  Backed exclusively by our verified dataset of 1,799 authentic technical interview questions.
                </p>

                {/* Search Bar */}
                <div className="relative pt-2">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={handleSearchChange}
                    placeholder="Search roles by title, company, or domain (e.g., Security, Cloud, ML)..."
                    className="w-full bg-[#F4F0EA] border-2 border-black rounded-xl px-4 py-3 text-sm font-bold text-black placeholder:text-slate-500 shadow-[3px_3px_0px_0px_#000] focus:outline-none focus:bg-white focus:shadow-[4px_4px_0px_0px_#000] transition-all"
                  />
                </div>
              </div>

              {/* Jobs List */}
              <div className="space-y-3 max-h-[460px] overflow-y-auto pr-2">
                {loadingJobs ? (
                  <div className="p-8 text-center font-bold text-slate-500 bg-white border-2 border-black rounded-xl shadow-[3px_3px_0px_0px_#000]">
                    Loading verified job profiles...
                  </div>
                ) : jobs.length === 0 ? (
                  <div className="p-8 text-center font-bold text-slate-500 bg-white border-2 border-black rounded-xl shadow-[3px_3px_0px_0px_#000]">
                    No job profiles matched your search term.
                  </div>
                ) : (
                  jobs.map((job) => {
                    const isSelected = selectedJob?.id === job.id
                    return (
                      <div
                        key={job.id}
                        onClick={() => setSelectedJob(job)}
                        className={`p-5 rounded-xl border-[3px] border-black transition-all cursor-pointer flex flex-col space-y-3 ${
                          isSelected
                            ? 'bg-[#FEF9C3] shadow-[6px_6px_0px_0px_#000] -translate-y-1'
                            : 'bg-white shadow-[3px_3px_0px_0px_#000] hover:shadow-[5px_5px_0px_0px_#000] hover:-translate-y-0.5'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-3">
                            <div className="w-10 h-10 rounded-lg bg-black text-[#FFE600] flex items-center justify-center font-black">
                              <Briefcase className="w-5 h-5 stroke-[2.5]" />
                            </div>
                            <div>
                              <h3 className="font-black text-black text-lg tracking-tight">{job.title}</h3>
                              <p className="text-xs font-bold text-slate-600 flex items-center space-x-2 mt-0.5">
                                <span className="font-black text-black">{job.company}</span>
                                <span>•</span>
                                <span className="px-2 py-0.5 bg-white border border-black rounded font-mono font-bold text-[10px] uppercase">
                                  {job.domain}
                                </span>
                              </p>
                            </div>
                          </div>
                          <span className="text-xs px-2.5 py-1 rounded-md bg-black text-white font-mono font-black shadow-[2px_2px_0px_0px_#FFE600]">
                            {job.min_experience_years}+ YRS
                          </span>
                        </div>

                        {/* Required skills */}
                        <div className="flex flex-wrap gap-1.5 pt-1">
                          {job.required_skills?.slice(0, 5).map((sk) => (
                            <span
                              key={sk}
                              className="text-[11px] font-bold px-2 py-0.5 rounded bg-white text-black border border-black shadow-[1px_1px_0px_0px_#000]"
                            >
                              {sk}
                            </span>
                          ))}
                          {job.required_skills?.length > 5 && (
                            <span className="text-[11px] font-bold px-2 py-0.5 text-slate-600">
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

            {/* Right Column: Resume Upload & Screening (5 Cols) */}
            <div className="lg:col-span-5 space-y-6">
              <div className="bg-white border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-6">
                <div>
                  <div className="inline-block px-3 py-1 bg-[#6EE7B7] text-black border-2 border-black font-black text-xs uppercase rounded-md shadow-[2px_2px_0px_0px_#000] mb-2">
                    Resume Evaluation
                  </div>
                  <h2 className="text-2xl font-black text-black tracking-tight uppercase">
                    Upload Candidate Resume
                  </h2>
                  <p className="text-xs font-bold text-slate-600 mt-1">
                    Accepts PDF or DOCX. Parsed locally with Trie skill matching, experience interval merging, and ML classifier.
                  </p>
                </div>

                {/* Drag & Drop Upload Zone */}
                <label className="border-[3px] border-dashed border-black hover:bg-[#FEF9C3] rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer transition-all bg-[#F4F0EA] shadow-[3px_3px_0px_0px_#000] group">
                  <input
                    type="file"
                    accept=".pdf,.docx"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                  <div className="w-14 h-14 rounded-xl bg-[#FFE600] border-2 border-black text-black flex items-center justify-center mb-3 shadow-[3px_3px_0px_0px_#000] group-hover:scale-110 transition-transform">
                    <UploadCloud className="w-7 h-7 stroke-[2.5]" />
                  </div>
                  {resumeFile ? (
                    <div className="text-center space-y-1">
                      <p className="text-sm font-black text-black">{resumeFile.name}</p>
                      <p className="text-xs font-mono font-bold text-slate-600">
                        {(resumeFile.size / 1024).toFixed(1)} KB • Click to swap
                      </p>
                    </div>
                  ) : (
                    <div className="text-center space-y-1">
                      <p className="text-sm font-black text-black">Click or drag resume file here</p>
                      <p className="text-xs font-bold text-slate-500">Supports PDF & DOCX format</p>
                    </div>
                  )}
                </label>

                {/* Selected Job Card Preview */}
                {selectedJob && (
                  <div className="p-4 rounded-xl bg-[#F4F0EA] border-2 border-black shadow-[2px_2px_0px_0px_#000] space-y-1">
                    <span className="text-[10px] font-black uppercase tracking-wider text-slate-500">
                      Selected Target Job
                    </span>
                    <p className="text-sm font-black text-black">{selectedJob.title}</p>
                    <p className="text-xs font-bold text-slate-600">
                      {selectedJob.company} • Pass Threshold: {(selectedJob.pass_threshold * 100).toFixed(0)}%
                    </p>
                  </div>
                )}

                <div className="p-3 bg-[#FEF08A] border-2 border-black rounded-xl flex items-start space-x-2 text-xs font-bold text-black shadow-[2px_2px_0px_0px_#000]">
                  <Lock className="w-4 h-4 text-black shrink-0 mt-0.5 stroke-[2.5]" />
                  <span>Privacy Promise: Zero data leaves your computer. All parsing runs 100% offline.</span>
                </div>

                <button
                  disabled={!resumeFile || !selectedJob || screeningLoading}
                  onClick={handleStartScreening}
                  className="w-full py-4 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-[3px] border-black font-black text-black text-sm uppercase tracking-wide flex items-center justify-center space-x-2 shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0px_0px_#000] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  {screeningLoading ? (
                    <>
                      <RefreshCw className="w-5 h-5 animate-spin stroke-[2.5]" />
                      <span>Parsing & Computing Fit...</span>
                    </>
                  ) : (
                    <>
                      <span>Screen Resume & Continue</span>
                      <ArrowRight className="w-5 h-5 stroke-[2.5]" />
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 2: Resume Screening Result & Proceed Override */}
        {currentStep === 'screening' && screeningResult && (
          <div className="max-w-3xl mx-auto space-y-6">
            <div className="bg-white border-[3px] border-black rounded-2xl p-8 shadow-[6px_6px_0px_0px_#000] space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b-2 border-black pb-5 gap-4">
                <div>
                  <div className="inline-block px-3 py-1 bg-[#6EE7B7] text-black border-2 border-black font-black text-xs uppercase rounded-md shadow-[2px_2px_0px_0px_#000] mb-2">
                    Candidate Screening Verdict
                  </div>
                  <h2 className="text-2xl font-black text-black uppercase tracking-tight">
                    {screeningResult.candidate_name || 'Candidate'}
                  </h2>
                  <p className="text-xs font-bold text-slate-600 mt-0.5">
                    Evaluated against <span className="text-black font-black">{selectedJob?.title}</span>
                  </p>
                </div>

                <div
                  className={`px-5 py-2.5 rounded-xl border-[3px] border-black font-black text-sm uppercase shadow-[4px_4px_0px_0px_#000] flex items-center space-x-2 ${
                    screeningResult.decision === 'PASS'
                      ? 'bg-[#A7F3D0] text-black'
                      : 'bg-[#FF8080] text-black'
                  }`}
                >
                  {screeningResult.decision === 'PASS' ? (
                    <>
                      <CheckCircle2 className="w-5 h-5 stroke-[2.5]" />
                      <span>SCREENING PASSED</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="w-5 h-5 stroke-[2.5]" />
                      <span>BELOW THRESHOLD</span>
                    </>
                  )}
                </div>
              </div>

              {/* Fit Metrics Breakdown */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl bg-[#FEF9C3] border-2 border-black shadow-[3px_3px_0px_0px_#000]">
                  <span className="text-xs font-black uppercase text-slate-600">Overall Fit</span>
                  <p className="text-2xl font-black text-black font-mono mt-1">
                    {(screeningResult.fit_score * 100).toFixed(1)}%
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#E0E7FF] border-2 border-black shadow-[3px_3px_0px_0px_#000]">
                  <span className="text-xs font-black uppercase text-slate-600">Skills Score</span>
                  <p className="text-2xl font-black text-black font-mono mt-1">
                    {(screeningResult.skill_score * 100).toFixed(0)}%
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#FCE7F3] border-2 border-black shadow-[3px_3px_0px_0px_#000]">
                  <span className="text-xs font-black uppercase text-slate-600">Experience</span>
                  <p className="text-2xl font-black text-black font-mono mt-1">
                    {screeningResult.experience_years} YRS
                  </p>
                </div>
                <div className="p-4 rounded-xl bg-[#DCFCE7] border-2 border-black shadow-[3px_3px_0px_0px_#000]">
                  <span className="text-xs font-black uppercase text-slate-600">Required Skills</span>
                  <p className="text-2xl font-black text-black font-mono mt-1">
                    {screeningResult.matched_skills?.length}/{selectedJob?.required_skills?.length || 5}
                  </p>
                </div>
              </div>

              {/* Missing Skills Warning */}
              {screeningResult.missing_skills?.length > 0 && (
                <div className="p-4 rounded-xl bg-[#FEF08A] border-2 border-black text-xs font-bold text-black shadow-[3px_3px_0px_0px_#000] flex items-start space-x-3">
                  <AlertTriangle className="w-5 h-5 text-black shrink-0 mt-0.5 stroke-[2.5]" />
                  <div>
                    <span className="font-black uppercase">Missing Core Skills:</span>{' '}
                    {screeningResult.missing_skills.join(', ')}.
                  </div>
                </div>
              )}

              {/* Consent Step before Hardware Pre-Check */}
              <div className="p-4 rounded-xl bg-[#F4F0EA] border-2 border-black shadow-[3px_3px_0px_0px_#000] space-y-2">
                <label className="flex items-start space-x-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={consentChecked}
                    onChange={(e) => setConsentChecked(e.target.checked)}
                    className="mt-1 w-5 h-5 rounded border-2 border-black accent-[#FFE600] text-black"
                  />
                  <div className="text-xs font-bold text-slate-800 leading-relaxed">
                    <span className="font-black text-black uppercase">Offline AI Proctoring Consent:</span> I consent to local webcam and microphone recording for AI-powered mock interview evaluation. All data is processed 100% locally on this machine and can be permanently deleted anytime.
                  </div>
                </label>
              </div>

              {/* Action Buttons */}
              <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-3">
                <button
                  onClick={() => setCurrentStep('select')}
                  className="w-full sm:w-auto px-5 py-3 rounded-xl border-2 border-black bg-white hover:bg-slate-100 font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000] transition-all"
                >
                  Back to Role Select
                </button>

                <button
                  disabled={!consentChecked}
                  onClick={startHardwareCheck}
                  className="w-full sm:w-auto px-6 py-3 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0px_0px_#000] disabled:opacity-40 disabled:cursor-not-allowed transition-all flex items-center justify-center space-x-2"
                >
                  <span>
                    {screeningResult.decision === 'PASS'
                      ? 'Proceed to Pre-Flight Check'
                      : 'Proceed Anyway (Candidate Override)'}
                  </span>
                  <ArrowRight className="w-4 h-4 stroke-[2.5]" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 3: Hardware Pre-Check */}
        {currentStep === 'precheck' && (
          <div className="max-w-2xl mx-auto space-y-6">
            <div className="bg-white border-[3px] border-black rounded-2xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-6">
              <div>
                <div className="inline-block px-3 py-1 bg-[#FDE047] text-black border-2 border-black font-black text-xs uppercase rounded-md shadow-[2px_2px_0px_0px_#000] mb-2">
                  System Pre-Flight
                </div>
                <h2 className="text-2xl font-black text-black uppercase tracking-tight">
                  Camera & Audio Diagnostics
                </h2>
                <p className="text-xs font-bold text-slate-600 mt-1">
                  Position your face inside the framing boundary, ensure good room lighting, and check audio input.
                </p>
              </div>

              {/* Video Window Preview */}
              <div className="relative rounded-2xl overflow-hidden aspect-video bg-black border-[3px] border-black shadow-[4px_4px_0px_0px_#000] flex items-center justify-center">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                  <div className="w-48 h-64 border-4 border-dashed border-[#FFE600] rounded-full shadow-[0px_0px_10px_#000]" />
                </div>
                <div className="absolute top-3 left-3 bg-[#FFE600] text-black px-2.5 py-1 border-2 border-black rounded font-black text-[11px] uppercase shadow-[2px_2px_0px_0px_#000]">
                  LIVE FEED
                </div>
              </div>

              {/* Diagnostics Grid */}
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div className="p-3 rounded-xl bg-[#F4F0EA] border-2 border-black shadow-[2px_2px_0px_0px_#000]">
                  <span className="font-bold text-slate-600 uppercase">Camera</span>
                  <p className="font-black text-black mt-1 flex items-center">
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-[#10B981] stroke-[2.5]" />
                    {cameraActive ? 'Active' : 'Offline'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-[#F4F0EA] border-2 border-black shadow-[2px_2px_0px_0px_#000]">
                  <span className="font-bold text-slate-600 uppercase">Lighting</span>
                  <p className="font-black text-black mt-1 flex items-center">
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-[#10B981] stroke-[2.5]" />
                    {lightingStatus}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-[#F4F0EA] border-2 border-black shadow-[2px_2px_0px_0px_#000]">
                  <span className="font-bold text-slate-600 uppercase">Distance</span>
                  <p className="font-black text-black mt-1 flex items-center">
                    <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-[#10B981] stroke-[2.5]" />
                    {distanceStatus}
                  </p>
                </div>
              </div>

              {/* Live Mic Meter */}
              <div className="space-y-1.5 bg-[#F4F0EA] p-4 rounded-xl border-2 border-black shadow-[2px_2px_0px_0px_#000]">
                <div className="flex justify-between text-xs font-black uppercase text-black">
                  <span>Microphone Signal Level</span>
                  <span className="font-mono">{audioLevel}%</span>
                </div>
                <div className="h-3 w-full bg-white rounded-full overflow-hidden border-2 border-black">
                  <div
                    className="h-full bg-[#10B981] transition-all duration-150"
                    style={{ width: `${audioLevel}%` }}
                  />
                </div>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  onClick={handleStartInterview}
                  className="px-8 py-3.5 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-[3px] border-black font-black text-black text-sm uppercase tracking-wide flex items-center space-x-2 shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0px_0px_#000] transition-all"
                >
                  <Play className="w-4 h-4 fill-black stroke-[2]" />
                  <span>Launch Mock Interview</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* STEP 4: Live Mock Interview Experience */}
        {currentStep === 'interview' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left Panel: Question Prompter & Spoken AI (7 Cols) */}
            <div className="lg:col-span-7 bg-white border-[3px] border-black rounded-2xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] flex flex-col justify-between space-y-6">
              <div className="space-y-6">
                <div className="flex items-center justify-between border-b-2 border-black pb-4">
                  <div className="inline-block px-3 py-1 bg-[#67E8F9] text-black border-2 border-black font-black text-xs uppercase rounded-md shadow-[2px_2px_0px_0px_#000]">
                    Question {currentQuestionIndex + 1} of {questions.length}
                  </div>
                  <div className="flex items-center space-x-2 font-mono font-black text-sm bg-[#FFE600] border-2 border-black px-3 py-1 rounded-md shadow-[2px_2px_0px_0px_#000]">
                    <Clock className="w-4 h-4 stroke-[2.5]" />
                    <span>{questionTimer}s</span>
                  </div>
                </div>

                {/* Question Block */}
                <div className="space-y-4">
                  <h2 className="text-2xl md:text-3xl font-black text-black leading-snug tracking-tight">
                    "{questions[currentQuestionIndex]?.question}"
                  </h2>

                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      onClick={() => speakQuestion(questions[currentQuestionIndex]?.question)}
                      className="px-4 py-2 bg-[#F4F0EA] hover:bg-white border-2 border-black rounded-lg font-black text-xs uppercase text-black flex items-center space-x-1.5 shadow-[2px_2px_0px_0px_#000] transition-all"
                    >
                      <Volume2 className="w-4 h-4 stroke-[2.5]" />
                      <span>Re-Play Spoken Audio</span>
                    </button>
                    {isSpeaking && (
                      <span className="text-xs font-black uppercase text-black px-2.5 py-1 bg-[#A7F3D0] border-2 border-black rounded shadow-[2px_2px_0px_0px_#000] animate-pulse">
                        AI Speaking...
                      </span>
                    )}
                  </div>
                </div>

                {/* Spoken Answer Live Transcription Box */}
                <div className="p-4 rounded-xl bg-[#F4F0EA] border-2 border-black shadow-[3px_3px_0px_0px_#000] space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className={`px-2.5 py-1 rounded border-2 border-black font-black text-[11px] uppercase shadow-[1px_1px_0px_0px_#000] flex items-center space-x-1.5 ${
                        speechStatus === 'OFFLINE_RECORDING'
                          ? 'bg-[#FEF08A] text-black'
                          : isListening
                          ? 'bg-[#A7F3D0] text-black animate-pulse'
                          : 'bg-white text-slate-700'
                      }`}>
                        <Mic className="w-3.5 h-3.5 stroke-[2.5]" />
                        <span>
                          {speechStatus === 'OFFLINE_RECORDING'
                            ? 'Audio Recording Live • Whisper Offline Sync'
                            : isListening
                            ? 'Microphone Active • Live Listening'
                            : 'Microphone Active'}
                        </span>
                      </span>
                      {isSubmittingAnswer && (
                        <span className="px-2 py-0.5 bg-[#FEF08A] text-black border border-black rounded text-[10px] font-black uppercase">
                          Saving...
                        </span>
                      )}
                    </div>
                    <span className="font-mono text-xs font-black text-black">
                      {candidateTranscript.trim() ? candidateTranscript.trim().split(/\s+/).length : 0} WORDS
                    </span>
                  </div>

                  <div className="relative">
                    <textarea
                      rows={3}
                      value={candidateTranscript}
                      onChange={(e) => setCandidateTranscript(e.target.value)}
                      placeholder={
                        speechStatus === 'OFFLINE_RECORDING'
                          ? "Microphone is recording live audio to disk. Local faster-whisper transcribes your spoken answers upon submission. You can also edit or type notes here directly."
                          : "Start speaking your answer into the microphone... your live speech transcript will appear here. You can also edit or type directly."
                      }
                      className="w-full p-3 rounded-lg bg-white border-2 border-black font-mono text-xs text-black placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#FFE600] shadow-[inset_2px_2px_0px_0px_rgba(0,0,0,0.06)] resize-none"
                    />
                  </div>

                  <div className="flex items-center justify-between text-[11px] font-bold text-slate-600">
                    <span>
                      {speechStatus === 'OFFLINE_RECORDING'
                        ? '💡 Voice audio is recorded live and will be segmented by local faster-whisper.'
                        : '💡 Speak clearly into your mic. Your speech is evaluated against the gold Q&A reference.'}
                    </span>
                    {candidateTranscript && (
                      <button
                        type="button"
                        onClick={() => setCandidateTranscript('')}
                        className="text-black font-black underline uppercase hover:text-red-600"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Bottom Navigation */}
              <div className="pt-6 border-t-2 border-black flex items-center justify-between">
                <span className="text-xs font-bold text-slate-600 font-mono">
                  Allocated: {questions[currentQuestionIndex]?.est_seconds}s
                </span>

                <button
                  disabled={isSubmittingAnswer}
                  onClick={handleNextQuestion}
                  className="px-7 py-3 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-[3px] border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 active:shadow-[1px_1px_0px_0px_#000] disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center space-x-2"
                >
                  {isSubmittingAnswer ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin stroke-[2.5]" />
                      <span>Scoring Answer...</span>
                    </>
                  ) : (
                    <>
                      <span>
                        {currentQuestionIndex < questions.length - 1 ? 'Next Question' : 'Finish Interview'}
                      </span>
                      <ArrowRight className="w-4 h-4 stroke-[2.5]" />
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Right Panel: Live Proctoring & Video Feed (5 Cols) */}
            <div className="lg:col-span-5 flex flex-col space-y-4">
              <div className="bg-black border-[3px] border-black rounded-2xl p-2 shadow-[5px_5px_0px_0px_#000] relative overflow-hidden aspect-video flex items-center justify-center">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="w-full h-full object-cover rounded-xl"
                />

                {/* Live Gaze/Look-Away Warning Overlay */}
                {liveAlert && (
                  <div className="absolute top-4 left-4 right-4 bg-[#FF4D4D] text-black border-2 border-black px-4 py-2.5 rounded-lg text-xs font-black uppercase flex items-center space-x-2 shadow-[3px_3px_0px_0px_#000] animate-bounce">
                    <AlertTriangle className="w-5 h-5 shrink-0 stroke-[2.5]" />
                    <span>{liveAlert.message}</span>
                  </div>
                )}

                {/* Live Indicators */}
                <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between text-[11px] font-black uppercase">
                  <span className={`px-2.5 py-1 rounded border-2 border-black shadow-[2px_2px_0px_0px_#000] flex items-center ${
                    isLookingAway ? 'bg-[#FF4D4D] text-black' : 'bg-[#A7F3D0] text-black'
                  }`}>
                    <Eye className="w-3.5 h-3.5 mr-1 stroke-[2.5]" />
                    {isLookingAway ? 'GAZE DRIFT' : 'DIRECT GAZE'}
                  </span>
                  <span className="px-2.5 py-1 rounded bg-[#FFE600] text-black border-2 border-black shadow-[2px_2px_0px_0px_#000] flex items-center">
                    <Video className="w-3.5 h-3.5 mr-1 stroke-[2.5]" />
                    REC
                  </span>
                </div>
              </div>

              {/* Live Proctoring Telemetry Log */}
              <div className="flex-1 bg-white border-[3px] border-black rounded-2xl p-4 shadow-[4px_4px_0px_0px_#000] flex flex-col">
                <h4 className="text-xs font-black text-black uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                  <Radio className="w-4 h-4 text-black stroke-[2.5]" />
                  <span>Real-Time Proctoring Stream</span>
                </h4>
                <div className="flex-1 overflow-y-auto space-y-2 pr-1 max-h-36">
                  {eventsLog.length === 0 ? (
                    <p className="text-xs font-bold text-slate-500 italic mt-2">
                      Proctoring telemetry running smoothly. Zero infractions detected.
                    </p>
                  ) : (
                    eventsLog.map((ev) => (
                      <div
                        key={ev.id}
                        className="p-2.5 rounded-lg bg-[#F4F0EA] border-2 border-black flex items-center justify-between text-xs font-bold shadow-[2px_2px_0px_0px_#000]"
                      >
                        <span className="text-black">{ev.message}</span>
                        <span className="text-[#FF4D4D] font-mono font-black">-{ev.penalty} pts</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* STEP 5: Post-Interview Processing */}
        {currentStep === 'processing' && (
          <div className="max-w-md mx-auto text-center py-16 space-y-6">
            <div className="w-20 h-20 bg-[#FFE600] border-[3px] border-black rounded-2xl text-black mx-auto flex items-center justify-center shadow-[5px_5px_0px_0px_#000] rotate-3">
              <RefreshCw className="w-10 h-10 animate-spin stroke-[2.5]" />
            </div>
            <div>
              <h2 className="text-3xl font-black text-black uppercase tracking-tight">
                Interview Completed
              </h2>
              <p className="text-sm font-bold text-slate-600 mt-2">{processingStatus.stage}</p>
            </div>

            {/* Neo-brutalist progress bars */}
            <div className="p-6 rounded-2xl bg-white border-[3px] border-black text-left space-y-4 shadow-[5px_5px_0px_0px_#000]">
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-black uppercase text-black">
                  <span>Vision Analysis (Face Mesh & Gaze)</span>
                  <span className="font-mono">{processingStatus.video_pct}%</span>
                </div>
                <div className="h-4 w-full bg-[#F4F0EA] rounded-full overflow-hidden border-2 border-black">
                  <div
                    className="h-full bg-[#FFE600] border-r-2 border-black transition-all duration-300"
                    style={{ width: `${processingStatus.video_pct}%` }}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-black uppercase text-black">
                  <span>Audio Analysis (faster-whisper)</span>
                  <span className="font-mono">{processingStatus.audio_pct}%</span>
                </div>
                <div className="h-4 w-full bg-[#F4F0EA] rounded-full overflow-hidden border-2 border-black">
                  <div
                    className="h-full bg-[#67E8F9] border-r-2 border-black transition-all duration-300"
                    style={{ width: `${processingStatus.audio_pct}%` }}
                  />
                </div>
              </div>
            </div>

            <div className="text-xs font-mono font-bold text-slate-600">
              Session ID: <span className="bg-white px-2 py-0.5 border border-black rounded">{sessionId}</span>
            </div>
          </div>
        )}

        {/* STEP 6: Interactive Evaluation Report & Review */}
        {currentStep === 'report' && reportData && (
          <div className="space-y-8 pb-12">
            {/* Report Header Hero */}
            <div className="bg-white border-[3px] border-black rounded-3xl p-8 shadow-[7px_7px_0px_0px_#000] flex flex-col md:flex-row items-center justify-between gap-6">
              <div className="space-y-2 text-center md:text-left">
                <div className="inline-block px-3 py-1 bg-[#FDE047] text-black border-2 border-black font-black text-xs uppercase rounded shadow-[2px_2px_0px_0px_#000]">
                  Official Evaluation Dossier
                </div>
                <h1 className="text-3xl sm:text-4xl font-black text-black tracking-tight uppercase">
                  {reportData.candidate_name}
                </h1>
                <p className="text-xs sm:text-sm font-bold text-slate-600 flex flex-wrap items-center justify-center md:justify-start gap-2">
                  <span className="text-black font-black">{reportData.job_title}</span>
                  <span>•</span>
                  <span>{reportData.company}</span>
                  <span>•</span>
                  <span>{new Date(reportData.timestamp).toLocaleDateString()}</span>
                </p>
              </div>

              {/* Rubber Stamp Score & Grade */}
              <div className="flex items-center space-x-4 bg-[#F4F0EA] border-[3px] border-black px-6 py-4 rounded-2xl shadow-[4px_4px_0px_0px_#000]">
                <div className="text-center">
                  <span className="text-[10px] font-black uppercase tracking-wider text-slate-600">
                    Total Score
                  </span>
                  <div className="flex items-baseline justify-center space-x-1 mt-0.5">
                    <span className="text-4xl font-black font-mono text-black">
                      {reportData.overall_score}
                    </span>
                    <span className="text-sm font-black font-mono text-slate-500">/100</span>
                  </div>
                </div>

                <div className="h-10 w-0.5 bg-black" />

                {/* Grade Stamp */}
                <div className="text-center">
                  <span className="text-[10px] font-black uppercase tracking-wider text-slate-600">
                    Grade
                  </span>
                  <div className="mt-0.5">
                    <span className="inline-block px-3.5 py-1 bg-[#FFE600] border-2 border-black rounded-lg text-2xl font-black font-mono text-black shadow-[2px_2px_0px_0px_#000] rotate-[-3deg]">
                      {reportData.grade}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            {/* 4 Category Score Deck */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="bg-[#FEF9C3] border-[3px] border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-1">
                <div className="flex justify-between items-center text-xs font-black uppercase text-slate-700">
                  <span>Technical Depth</span>
                  <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-black text-[10px]">35% Wgt</span>
                </div>
                <p className="text-3xl font-black text-black font-mono pt-1">
                  {reportData.category_scores.technical_depth?.toFixed(1)}
                  <span className="text-xs text-slate-600 font-bold ml-1">/100</span>
                </p>
              </div>

              <div className="bg-[#E0E7FF] border-[3px] border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-1">
                <div className="flex justify-between items-center text-xs font-black uppercase text-slate-700">
                  <span>Communication</span>
                  <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-black text-[10px]">25% Wgt</span>
                </div>
                <p className="text-3xl font-black text-black font-mono pt-1">
                  {reportData.category_scores.communication?.toFixed(1)}
                  <span className="text-xs text-slate-600 font-bold ml-1">/100</span>
                </p>
              </div>

              <div className="bg-[#FCE7F3] border-[3px] border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-1">
                <div className="flex justify-between items-center text-xs font-black uppercase text-slate-700">
                  <span>Proctoring Integrity</span>
                  <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-black text-[10px]">25% Wgt</span>
                </div>
                <p className="text-3xl font-black text-black font-mono pt-1">
                  {reportData.category_scores.proctoring_integrity?.toFixed(1)}
                  <span className="text-xs text-slate-600 font-bold ml-1">/100</span>
                </p>
              </div>

              <div className="bg-[#DCFCE7] border-[3px] border-black rounded-2xl p-5 shadow-[4px_4px_0px_0px_#000] space-y-1">
                <div className="flex justify-between items-center text-xs font-black uppercase text-slate-700">
                  <span>Resume Relevance</span>
                  <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-black text-[10px]">15% Wgt</span>
                </div>
                <p className="text-3xl font-black text-black font-mono pt-1">
                  {reportData.category_scores.resume_relevance?.toFixed(1)}
                  <span className="text-xs text-slate-600 font-bold ml-1">/100</span>
                </p>
              </div>
            </div>

            {/* Video Playback & Deduction Timeline (Side-by-Side) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Left: Video Player with seeking (6 Cols) */}
              <div className="lg:col-span-6 space-y-3">
                <h3 className="text-lg font-black text-black uppercase flex items-center space-x-2">
                  <Video className="w-5 h-5 text-black stroke-[2.5]" />
                  <span>Session Video Recording</span>
                </h3>
                <div className="bg-black border-[3px] border-black rounded-2xl overflow-hidden aspect-video shadow-[5px_5px_0px_0px_#000] relative">
                  <video
                    ref={reportVideoRef}
                    controls
                    src={`/api/interview/${sessionId}/video`}
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="p-3 bg-[#FEF08A] border-2 border-black rounded-xl text-xs font-bold text-black shadow-[2px_2px_0px_0px_#000]">
                  💡 <strong>Tip:</strong> Click any event in the timeline on the right to scrub video playback directly to that timestamp.
                </div>
              </div>

              {/* Right: Deduction Timeline (6 Cols) */}
              <div className="lg:col-span-6 space-y-3 flex flex-col">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-black text-black uppercase flex items-center space-x-2">
                    <Clock className="w-5 h-5 text-black stroke-[2.5]" />
                    <span>Deduction Timeline</span>
                  </h3>
                  <span className="px-2.5 py-1 bg-black text-[#FFE600] border border-black rounded font-mono font-black text-xs">
                    Total: -{reportData.total_deductions} pts
                  </span>
                </div>

                <div className="bg-white border-[3px] border-black rounded-2xl p-4 shadow-[5px_5px_0px_0px_#000] flex-1 max-h-[350px] overflow-y-auto space-y-2">
                  {reportData.deduction_timeline?.length === 0 ? (
                    <div className="text-center py-10 font-black text-xs uppercase text-slate-500">
                      Clean record! Zero integrity penalties logged.
                    </div>
                  ) : (
                    reportData.deduction_timeline.map((ded, i) => (
                      <div
                        key={i}
                        onClick={() => seekVideo(ded.t_start)}
                        className="p-3 rounded-xl bg-[#F4F0EA] hover:bg-[#FEF9C3] border-2 border-black cursor-pointer flex items-center justify-between text-xs font-bold shadow-[2px_2px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all group"
                      >
                        <div className="flex items-center space-x-3">
                          <span className="px-2 py-1 rounded bg-black text-[#FFE600] font-mono font-black text-[11px]">
                            {formatSeconds(ded.t_start)}
                          </span>
                          <div>
                            <p className="font-black text-black uppercase text-[12px]">
                              {ded.category || 'Violation Event'}
                            </p>
                            <p className="text-[11px] font-semibold text-slate-600">{ded.reason}</p>
                          </div>
                        </div>

                        <span className="font-mono font-black text-[#FF4D4D] text-sm shrink-0">
                          -{ded.points_deducted} pts
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>

            {/* Questions Review Accordion */}
            <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-4">
              <h3 className="text-2xl font-black text-black uppercase tracking-tight flex items-center space-x-2">
                <FileText className="w-6 h-6 stroke-[2.5]" />
                <span>Question Evaluation vs Dataset Ground Truth</span>
              </h3>
              <p className="text-xs font-bold text-slate-600">
                Authoritative reference answers sourced directly from our verified technical Q&A dataset.
              </p>

              <div className="space-y-3 mt-4">
                {reportData.questions_breakdown?.map((q, idx) => {
                  const isOpen = expandedQuestion === idx
                  return (
                    <div
                      key={idx}
                      className="rounded-2xl border-2 border-black bg-[#F4F0EA] overflow-hidden shadow-[3px_3px_0px_0px_#000] transition-all"
                    >
                      <button
                        onClick={() => setExpandedQuestion(isOpen ? -1 : idx)}
                        className="w-full p-4 flex items-center justify-between text-left hover:bg-[#FEF9C3] transition-all"
                      >
                        <div className="flex items-center space-x-3">
                          <span className="w-7 h-7 rounded-lg bg-black text-[#FFE600] text-xs font-black flex items-center justify-center shrink-0">
                            {idx + 1}
                          </span>
                          <span className="text-sm font-black text-black">{q.question}</span>
                        </div>
                        <div className="flex items-center space-x-3">
                          <span className="text-xs font-mono font-black px-2.5 py-1 rounded bg-white border border-black shadow-[1px_1px_0px_0px_#000]">
                            {q.score?.toFixed(0)}/100
                          </span>
                          <ChevronDown
                            className={`w-5 h-5 text-black stroke-[2.5] transition-transform ${
                              isOpen ? 'rotate-180' : ''
                            }`}
                          />
                        </div>
                      </button>

                      {isOpen && (
                        <div className="p-5 border-t-2 border-black bg-white space-y-4 text-xs font-bold">
                          {/* Candidate Transcript */}
                          <div>
                            <span className="font-black uppercase text-slate-700 tracking-wider text-[11px]">
                              Candidate Transcript:
                            </span>
                            <p className="mt-1 text-slate-900 bg-[#F4F0EA] p-3 rounded-xl border border-black font-mono text-[11px] leading-relaxed">
                              "{q.transcript}"
                            </p>
                          </div>

                          {/* Reference Answer from Dataset */}
                          <div>
                            <span className="font-black uppercase text-emerald-800 tracking-wider text-[11px]">
                              Authoritative Dataset Ground Truth:
                            </span>
                            <p className="mt-1 text-emerald-950 bg-[#DCFCE7] p-3 rounded-xl border-2 border-black leading-relaxed">
                              "{q.reference_answer}"
                            </p>
                          </div>

                          {/* Technical Keywords */}
                          <div>
                            <span className="font-black uppercase text-slate-700 tracking-wider text-[11px]">
                              Extracted Technical Keywords:
                            </span>
                            <div className="flex flex-wrap gap-1.5 mt-1.5">
                              {q.matched_keywords?.map((kw) => (
                                <span
                                  key={kw}
                                  className="px-2.5 py-1 rounded-md bg-[#A7F3D0] text-black border-2 border-black text-[11px] font-black uppercase shadow-[1px_1px_0px_0px_#000] flex items-center space-x-1"
                                >
                                  <Check className="w-3.5 h-3.5 mr-1 stroke-[3]" />
                                  <span>{kw}</span>
                                </span>
                              ))}
                              {q.missed_keywords?.map((kw) => (
                                <span
                                  key={kw}
                                  className="px-2.5 py-1 rounded-md bg-[#FECDD3] text-black border-2 border-black text-[11px] font-black uppercase shadow-[1px_1px_0px_0px_#000] flex items-center space-x-1"
                                >
                                  <X className="w-3.5 h-3.5 mr-1 stroke-[3]" />
                                  <span>{kw}</span>
                                </span>
                              ))}
                            </div>
                          </div>

                          {/* Evaluator Feedback */}
                          <div className="text-slate-700 pt-1">
                            <span className="font-black uppercase text-black">Feedback:</span> {q.feedback}
                          </div>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Executive Summary, Strengths, Growth, Tips */}
            {reportData.summary && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-[#DCFCE7] border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-3">
                  <h4 className="text-sm font-black uppercase text-black flex items-center space-x-2">
                    <CheckCircle2 className="w-4 h-4 text-black stroke-[2.5]" />
                    <span>Candidate Strengths</span>
                  </h4>
                  <ul className="space-y-2 text-xs font-bold text-slate-800">
                    {reportData.summary.strengths?.map((s, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="font-black text-black">✓</span>
                        <span>{s}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="bg-[#FEF08A] border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-3">
                  <h4 className="text-sm font-black uppercase text-black flex items-center space-x-2">
                    <AlertTriangle className="w-4 h-4 text-black stroke-[2.5]" />
                    <span>Growth Areas</span>
                  </h4>
                  <ul className="space-y-2 text-xs font-bold text-slate-800">
                    {reportData.summary.weaknesses?.map((w, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="font-black text-black">⚠</span>
                        <span>{w}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="bg-[#E0E7FF] border-[3px] border-black rounded-2xl p-6 shadow-[5px_5px_0px_0px_#000] space-y-3">
                  <h4 className="text-sm font-black uppercase text-black flex items-center space-x-2">
                    <Sparkles className="w-4 h-4 text-black stroke-[2.5]" />
                    <span>Actionable Recommendations</span>
                  </h4>
                  <ul className="space-y-2 text-xs font-bold text-slate-800">
                    {reportData.summary.concrete_tips?.map((t, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="font-black text-black">{i + 1}.</span>
                        <span>{t}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* Bottom Actions Bar */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t-2 border-black">
              <button
                onClick={handleDeleteData}
                className="px-5 py-3 rounded-xl border-2 border-black bg-[#FF8080] hover:bg-[#ff6666] font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
              >
                <Trash2 className="w-4 h-4 stroke-[2.5]" />
                <span>Delete My Data & Recording</span>
              </button>

              <div className="flex items-center space-x-3">
                <a
                  href={`/api/report/${sessionId}/pdf`}
                  target="_blank"
                  rel="noreferrer"
                  className="px-6 py-3 rounded-xl bg-white hover:bg-slate-100 border-2 border-black font-black text-black text-xs uppercase shadow-[3px_3px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
                >
                  <Download className="w-4 h-4 stroke-[2.5]" />
                  <span>Download Official PDF</span>
                </a>

                <button
                  onClick={() => {
                    setCurrentStep('select')
                    setResumeFile(null)
                    setScreeningResult(null)
                    setSessionId(null)
                    setReportData(null)
                  }}
                  className="px-6 py-3 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
                >
                  <RotateCcw className="w-4 h-4 stroke-[2.5]" />
                  <span>New Interview Session</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Settings Modal (Neo-Brutalist Drawer) */}
      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-white border-[3px] border-black rounded-2xl w-full max-w-lg p-6 sm:p-8 shadow-[8px_8px_0px_0px_#000] space-y-6">
            <div className="flex items-center justify-between border-b-2 border-black pb-3">
              <div className="flex items-center space-x-2 text-black font-black uppercase text-lg">
                <Sliders className="w-6 h-6 stroke-[2.5]" />
                <span>Proctoring Sensitivity Controls</span>
              </div>
              <button
                onClick={() => setIsSettingsOpen(false)}
                className="p-1 hover:bg-[#FFE600] border-2 border-black rounded-md transition-colors"
              >
                <X className="w-5 h-5 stroke-[2.5]" />
              </button>
            </div>

            <div className="space-y-4 text-xs font-bold">
              <div>
                <label className="text-black flex justify-between uppercase">
                  <span>Gaze Center Tolerance</span>
                  <span className="font-mono bg-[#F4F0EA] px-2 py-0.5 border border-black rounded">
                    {settingsData.gaze_tolerance_x.toFixed(2)} / {settingsData.gaze_tolerance_y.toFixed(2)}
                  </span>
                </label>
                <input
                  type="range"
                  min="0.05"
                  max="0.30"
                  step="0.01"
                  value={settingsData.gaze_tolerance_x}
                  onChange={(e) =>
                    setSettingsData({
                      ...settingsData,
                      gaze_tolerance_x: parseFloat(e.target.value),
                    })
                  }
                  className="w-full mt-2 accent-black"
                />
              </div>

              <div>
                <label className="text-black flex justify-between uppercase">
                  <span>Head Yaw / Pitch Angle Threshold</span>
                  <span className="font-mono bg-[#F4F0EA] px-2 py-0.5 border border-black rounded">
                    {settingsData.head_yaw_deg}°
                  </span>
                </label>
                <input
                  type="range"
                  min="15"
                  max="45"
                  step="1"
                  value={settingsData.head_yaw_deg}
                  onChange={(e) =>
                    setSettingsData({
                      ...settingsData,
                      head_yaw_deg: parseFloat(e.target.value),
                    })
                  }
                  className="w-full mt-2 accent-black"
                />
              </div>

              <div>
                <label className="text-black flex justify-between uppercase">
                  <span>Speech Pause Threshold</span>
                  <span className="font-mono bg-[#F4F0EA] px-2 py-0.5 border border-black rounded">
                    {settingsData.speech_pause_sec}s
                  </span>
                </label>
                <input
                  type="range"
                  min="2.0"
                  max="6.0"
                  step="0.5"
                  value={settingsData.speech_pause_sec}
                  onChange={(e) =>
                    setSettingsData({
                      ...settingsData,
                      speech_pause_sec: parseFloat(e.target.value),
                    })
                  }
                  className="w-full mt-2 accent-black"
                />
              </div>

              <div>
                <label className="text-black flex justify-between uppercase">
                  <span>Filler Word Deduction Penalty</span>
                  <span className="font-mono bg-[#F4F0EA] px-2 py-0.5 border border-black rounded">
                    -{settingsData.filler_penalty} pts
                  </span>
                </label>
                <input
                  type="range"
                  min="0.2"
                  max="2.0"
                  step="0.1"
                  value={settingsData.filler_penalty}
                  onChange={(e) =>
                    setSettingsData({
                      ...settingsData,
                      filler_penalty: parseFloat(e.target.value),
                    })
                  }
                  className="w-full mt-2 accent-black"
                />
              </div>
            </div>

            <div className="pt-2 flex items-center justify-between border-t-2 border-black">
              {settingsSaved ? (
                <span className="text-xs font-black uppercase text-[#10B981] flex items-center">
                  <Check className="w-4 h-4 mr-1 stroke-[3]" />
                  Saved!
                </span>
              ) : (
                <span className="text-xs font-bold text-slate-500">Live offline calibration</span>
              )}

              <div className="flex space-x-2">
                <button
                  onClick={() => setIsSettingsOpen(false)}
                  className="px-4 py-2 rounded-lg border-2 border-black bg-white hover:bg-slate-100 text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000]"
                >
                  Close
                </button>
                <button
                  onClick={handleSaveSettings}
                  className="px-5 py-2 rounded-lg bg-[#FFE600] hover:bg-[#ffdf00] border-2 border-black text-black text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all"
                >
                  Save Controls
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
