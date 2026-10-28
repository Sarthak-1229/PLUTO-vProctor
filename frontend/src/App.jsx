import { useState, useEffect, useRef } from 'react'
import { LiveGazeDetector, PRESETS } from './utils/liveGazeDetector'
import { InterviewFSM, INTERVIEW_STATES, saveSessionState, loadSessionState, clearSessionState } from './utils/interviewFSM'
import { Navbar } from './components/Navbar'
import { BrowserSupportBanner } from './components/BrowserSupportBanner'
import { ErrorBoundary } from './components/ErrorBoundary'
import { RoleSelectStep } from './components/RoleSelectStep'
import { ScreeningStep } from './components/ScreeningStep'
import { SystemCheckStep } from './components/SystemCheckStep'
import { CalibrationStep } from './components/CalibrationStep'
import { InterviewRoom } from './components/InterviewRoom'
import { ProcessingStep } from './components/ProcessingStep'
import { ReportView } from './components/ReportView'
import { CandidateDashboard } from './components/CandidateDashboard'
import { SettingsModal } from './components/SettingsModal'
import RecordFixturePage from './RecordFixturePage'

const STEPS = [
  { id: 'select', label: '1. Role & Resume' },
  { id: 'screening', label: '2. Screening Fit' },
  { id: 'precheck', label: '3. Pre-Flight' },
  { id: 'calibration', label: '4. Calibration' },
  { id: 'interview', label: '5. Interview' },
  { id: 'processing', label: '6. Pipeline' },
  { id: 'report', label: '7. Report' },
]

export default function App() {
  // Check developer fixture recording route first
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/dev/record-fixture')) {
    return <RecordFixturePage />
  }

  // Application State
  const [currentStep, setCurrentStep] = useState('select')
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)
  const [candidateName, setCandidateName] = useState('')
  const [resumeFile, setResumeFile] = useState(null)
  const [screeningResult, setScreeningResult] = useState(null)
  const [sessionId, setSessionId] = useState(null)
  const [consentChecked, setConsentChecked] = useState(false)
  const [activePreset, setActivePreset] = useState('strict')
  const [calibrationData, setCalibrationData] = useState(null)
  const [questions, setQuestions] = useState([])
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [processingStatus, setProcessingStatus] = useState({ stage: 'Starting...', video_pct: 0, audio_pct: 0 })
  const [reportData, setReportData] = useState(null)
  const [loadingScreening, setLoadingScreening] = useState(false)

  // Modals
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isDashboardOpen, setIsDashboardOpen] = useState(false)

  // Media & Detector Refs
  const [mediaStream, setMediaStream] = useState(null)
  const mediaRecorderRef = useRef(null)
  const recordedChunksRef = useRef([])
  const liveGazeDetectorRef = useRef(new LiveGazeDetector('strict'))
  const fsmRef = useRef(new InterviewFSM(INTERVIEW_STATES.IDLE))

  // 1. Fetch available jobs on mount
  useEffect(() => {
    async function fetchJobs() {
      const endpoints = ['/api/jobs', '/api/jobs/', 'http://127.0.0.1:8000/api/jobs']
      for (const ep of endpoints) {
        try {
          const res = await fetch(ep)
          if (res.ok) {
            const data = await res.json()
            if (Array.isArray(data) && data.length > 0) {
              setJobs(data)
              if (!selectedJob) {
                setSelectedJob(data[0])
              }
              break
            }
          }
        } catch (e) {
          // Fall through to next endpoint or default
        }
      }
    }
    fetchJobs()

    // Try session restore on mount
    const saved = loadSessionState()
    if (saved && saved.sessionId && saved.currentStep) {
      setSessionId(saved.sessionId)
      if (saved.candidateName) setCandidateName(saved.candidateName)
      if (saved.selectedJob) setSelectedJob(saved.selectedJob)
      if (saved.questions) setQuestions(saved.questions)
      if (saved.currentQuestionIndex !== undefined) setCurrentQuestionIndex(saved.currentQuestionIndex)
      if (saved.currentStep === 'report' || saved.currentStep === 'interview') {
        setCurrentStep(saved.currentStep)
        if (saved.currentStep === 'report' && saved.sessionId) {
          fetch(`/api/report/${saved.sessionId}`)
            .then((r) => (r.ok ? r.json() : null))
            .then((d) => d && setReportData(d))
            .catch(() => {})
        }
      }
    }
  }, [])

  // Auto-fetch report data if entering or restored on report step without reportData
  useEffect(() => {
    if (currentStep === 'report' && !reportData && sessionId) {
      fetch(`/api/report/${sessionId}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) {
            setReportData(data)
            saveToPastInterviews(data)
          }
        })
        .catch((err) => console.warn('Auto-reload report error:', err))
    }
  }, [currentStep, reportData, sessionId])

  // Persist session state on step/index changes
  useEffect(() => {
    if (sessionId) {
      saveSessionState({
        sessionId,
        currentStep,
        candidateName,
        selectedJob,
        questions,
        currentQuestionIndex,
      })
    }
  }, [sessionId, currentStep, candidateName, selectedJob, questions, currentQuestionIndex])

  // Initialize camera and microphone when entering precheck/calibration/interview
  useEffect(() => {
    let active = true
    if (['precheck', 'calibration', 'interview'].includes(currentStep)) {
      async function startMedia() {
        if (mediaStream) return
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } },
            audio: { echoCancellation: true, noiseSuppression: false, autoGainControl: false },
          })
          if (active) {
            setMediaStream(stream)
            // Initialize live gaze detector with stream
            if (liveGazeDetectorRef.current) {
              const videoEl = document.createElement('video')
              videoEl.srcObject = stream
              videoEl.muted = true
              videoEl.play().catch(() => {})
              liveGazeDetectorRef.current.start(videoEl)
            }
          }
        } catch (err) {
          console.warn('getUserMedia error:', err)
        }
      }
      startMedia()
    }

    return () => {
      active = false
    }
  }, [currentStep, mediaStream])

  // Cleanup media stream when returning to select or report
  useEffect(() => {
    if (['select', 'screening', 'report'].includes(currentStep) && mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop())
      setMediaStream(null)
      if (liveGazeDetectorRef.current) {
        liveGazeDetectorRef.current.stop()
      }
    }
  }, [currentStep])

  // Change preset
  const handleSelectPreset = (presetId) => {
    setActivePreset(presetId)
    if (liveGazeDetectorRef.current) {
      liveGazeDetectorRef.current.setPreset(presetId)
    }
  }

  // Submit resume screening
  const handleSubmitScreening = async () => {
    if (!selectedJob || !resumeFile) return
    setLoadingScreening(true)
    const formData = new FormData()
    formData.append('resume', resumeFile)
    formData.append('file', resumeFile)
    formData.append('job_id', selectedJob.id)
    if (candidateName) formData.append('candidate_name', candidateName)

    try {
      let res = await fetch('/api/resume/screen', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        // Fallback to /api/resume/upload if needed
        res = await fetch('/api/resume/upload', {
          method: 'POST',
          body: formData,
        })
      }
      if (!res.ok) {
        const errDetail = await res.text()
        throw new Error(errDetail || 'Screening request rejected by server')
      }
      const data = await res.json()
      setScreeningResult(data)
      setSessionId(data.session_id)
      setCurrentStep('screening')
    } catch (e) {
      console.error('Screening submission error:', e)
      alert(`Failed to screen resume: ${e.message || 'Please ensure the backend is running.'}`)
    } finally {
      setLoadingScreening(false)
    }
  }

  // Proceed from screening to precheck
  const handleProceedFromScreening = () => {
    setCurrentStep('precheck')
  }

  // Proceed from precheck to calibration
  const handleProceedToCalibration = () => {
    setCurrentStep('calibration')
  }

  // Finish calibration and start interview
  const handleCalibrationComplete = async (baseline) => {
    setCalibrationData(baseline)
    try {
      // Start session on backend with calibration baseline and preset
      const res = await fetch(`/api/interview/${sessionId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          calibration: baseline,
          preset_name: activePreset,
        }),
      })
      if (!res.ok) throw new Error('Failed to start interview session on server')
      const data = await res.json()
      setQuestions(data.questions || [])
      setCurrentQuestionIndex(0)

      // Start recording media
      startRecording()

      setCurrentStep('interview')
    } catch (e) {
      console.error('Start interview error:', e)
      alert('Failed to start interview. Please retry.')
    }
  }

  // Start MediaRecorder
  const startRecording = () => {
    if (!mediaStream) return
    recordedChunksRef.current = []
    let mimeType = 'video/webm;codecs=vp9,opus'
    if (!MediaRecorder.isTypeSupported(mimeType)) {
      mimeType = 'video/webm;codecs=vp8,opus'
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'video/webm'
      }
    }

    try {
      const recorder = new MediaRecorder(mediaStream, { mimeType })
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          recordedChunksRef.current.push(e.data)
        }
      }
      recorder.start(1000)
      mediaRecorderRef.current = recorder
    } catch (e) {
      console.warn('Failed to start MediaRecorder:', e)
    }
  }

  // Answer submit from InterviewRoom
  const handleNextQuestion = async ({ qIndex, transcript, startTime, endTime, ttsWindows }) => {
    if (!sessionId) return
    try {
      await fetch(`/api/interview/${sessionId}/question/${qIndex}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transcript: transcript || '',
          start_time_sec: startTime,
          end_time_sec: endTime,
          tts_windows: ttsWindows || [],
        }),
      })
    } catch (e) {
      console.warn(`Failed to submit answer for question ${qIndex}:`, e)
    }

    if (qIndex + 1 < questions.length) {
      setCurrentQuestionIndex(qIndex + 1)
    }
  }

  // Finish interview -> stop recorder -> upload recording -> trigger analysis
  const handleFinishInterview = async () => {
    setCurrentStep('processing')
    setProcessingStatus({ stage: 'Finalizing and compressing recording...', video_pct: 10, audio_pct: 10 })

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
      await new Promise((resolve) => {
        mediaRecorderRef.current.onstop = resolve
      })
    }

    // Build WebM blob
    const blob = new Blob(recordedChunksRef.current, { type: 'video/webm' })
    const formData = new FormData()
    formData.append('file', blob, `${sessionId}_interview.webm`)

    try {
      setProcessingStatus({ stage: 'Uploading session video to server...', video_pct: 25, audio_pct: 25 })
      await fetch(`/api/interview/${sessionId}/recording`, {
        method: 'POST',
        body: formData,
      })

      // Trigger analysis pipeline
      setProcessingStatus({ stage: 'Launching parallel video and audio pipelines...', video_pct: 35, audio_pct: 35 })
      await fetch(`/api/analysis/${sessionId}/run`, { method: 'POST' })

      // Poll analysis status
      pollAnalysisStatus()
    } catch (e) {
      console.error('Recording upload error:', e)
      setProcessingStatus({ stage: 'Analysis error occurred. Loading available report...', video_pct: 100, audio_pct: 100 })
      loadFinalReport()
    }
  }

  // Poll analysis status
  const pollAnalysisStatus = () => {
    let failCount = 0
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/analysis/${sessionId}/status`)
        if (res.ok) {
          failCount = 0
          const status = await res.json()
          const vPct = status.video_pct !== undefined ? status.video_pct : Math.round((status.video_progress || 0) * 100)
          const aPct = status.audio_pct !== undefined ? status.audio_pct : Math.round((status.audio_progress || 0) * 100)
          setProcessingStatus({
            stage: status.stage || 'Analyzing multimodal video & audio telemetry...',
            video_pct: vPct,
            audio_pct: aPct,
          })

          if (status.status === 'COMPLETED' || (vPct >= 100 && aPct >= 100)) {
            clearInterval(interval)
            loadFinalReport()
          }
        } else {
          failCount++
          if (failCount > 6) {
            clearInterval(interval)
            loadFinalReport()
          }
        }
      } catch (e) {
        failCount++
        if (failCount > 6) {
          clearInterval(interval)
          loadFinalReport()
        }
      }
    }, 1500)
  }

  // Load final evaluation report
  const loadFinalReport = async (retries = 3) => {
    try {
      const res = await fetch(`/api/report/${sessionId}`)
      if (res.ok) {
        const data = await res.json()
        setReportData(data)
        // Save to past sessions in localStorage
        saveToPastInterviews(data)
        setCurrentStep('report')
        return
      }
    } catch (e) {
      console.warn('Failed to load report attempt:', e)
    }

    if (retries > 1) {
      setTimeout(() => loadFinalReport(retries - 1), 2000)
    } else {
      setCurrentStep('report')
    }
  }

  // Save interview report summary to localStorage
  const saveToPastInterviews = (report) => {
    try {
      const existing = JSON.parse(localStorage.getItem('pluto_past_interviews') || '[]')
      const filtered = existing.filter((item) => item.session_id !== sessionId)
      const newItem = {
        session_id: sessionId,
        job_title: report.job_title || selectedJob?.title,
        company: report.company || selectedJob?.company,
        overall_score: report.overall_score,
        grade: report.grade,
        timestamp: Date.now(),
      }
      localStorage.setItem('pluto_past_interviews', JSON.stringify([newItem, ...filtered].slice(0, 20)))
    } catch (e) {
      console.warn('Failed to cache past interview:', e)
    }
  }

  // Delete data action
  const handleDeleteData = async () => {
    if (!window.confirm('Are you sure you want to permanently delete this interview recording and all associated data?')) return
    try {
      await fetch(`/api/interview/${sessionId}`, { method: 'DELETE' })
      alert('All session recordings and evaluation data have been permanently erased.')
      handleResetSession()
    } catch (e) {
      console.warn('Delete data error:', e)
    }
  }

  // Reset session to start over
  const handleResetSession = () => {
    clearSessionState()
    setSessionId(null)
    setResumeFile(null)
    setScreeningResult(null)
    setReportData(null)
    setQuestions([])
    setCurrentQuestionIndex(0)
    setCurrentStep('select')
  }

  // Retry with different questions rotated from knapsack pool
  const handleRetryDifferentQuestions = async () => {
    if (!sessionId) return
    handleCalibrationComplete(calibrationData || {})
  }

  return (
    <ErrorBoundary onReset={handleResetSession}>
      <div className="min-h-screen bg-[#F4F0EA] text-slate-900 flex flex-col font-sans selection:bg-[#FFE600] selection:text-black">
        <BrowserSupportBanner />

        <Navbar
          steps={STEPS}
          currentStep={currentStep}
          onStepClick={(s) => {
            if (currentStep === 'report' || currentStep === 'select') {
              setCurrentStep(s)
            }
          }}
          activePreset={activePreset}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onOpenDashboard={() => setIsDashboardOpen(true)}
        />

        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* STEP 1: Role Selection & Resume Upload */}
          {currentStep === 'select' && (
            <RoleSelectStep
              jobs={jobs}
              selectedJob={selectedJob}
              onSelectJob={setSelectedJob}
              resumeFile={resumeFile}
              onResumeChange={setResumeFile}
              candidateName={candidateName}
              onCandidateNameChange={setCandidateName}
              onSubmitScreening={handleSubmitScreening}
              loading={loadingScreening}
            />
          )}

          {/* STEP 2: Screening Fit & Consent */}
          {currentStep === 'screening' && (
            <ScreeningStep
              screeningResult={screeningResult}
              selectedJob={selectedJob}
              candidateName={candidateName}
              consentChecked={consentChecked}
              onConsentChange={setConsentChecked}
              onProceed={handleProceedFromScreening}
              onBack={() => setCurrentStep('select')}
            />
          )}

          {/* STEP 3: System Pre-Flight Check */}
          {currentStep === 'precheck' && (
            <SystemCheckStep
              stream={mediaStream}
              onProceed={handleProceedToCalibration}
              onBack={() => setCurrentStep('screening')}
            />
          )}

          {/* STEP 4: Gaze Baseline Calibration */}
          {currentStep === 'calibration' && (
            <CalibrationStep
              stream={mediaStream}
              liveDetector={liveGazeDetectorRef.current}
              onCalibrationComplete={handleCalibrationComplete}
              onBack={() => setCurrentStep('precheck')}
            />
          )}

          {/* STEP 5: Live Mock Interview Experience */}
          {currentStep === 'interview' && (
            <InterviewRoom
              sessionId={sessionId}
              candidateName={candidateName}
              jobTitle={selectedJob?.title}
              company={selectedJob?.company}
              questions={questions}
              currentQuestionIndex={currentQuestionIndex}
              onNextQuestion={handleNextQuestion}
              onFinishInterview={handleFinishInterview}
              stream={mediaStream}
              liveDetector={liveGazeDetectorRef.current}
              activePreset={activePreset}
            />
          )}

          {/* STEP 6: Pipeline Processing */}
          {currentStep === 'processing' && (
            <ProcessingStep
              processingStatus={processingStatus}
              sessionId={sessionId}
            />
          )}

          {/* STEP 7: Comprehensive Report & Scrubber */}
          {currentStep === 'report' && (
            <ReportView
              reportData={reportData}
              sessionId={sessionId}
              onDeleteData={handleDeleteData}
              onResetSession={handleResetSession}
              onRetryDifferentQuestions={handleRetryDifferentQuestions}
            />
          )}
        </main>

        {/* Candidate Past Sessions Drawer */}
        <CandidateDashboard
          isOpen={isDashboardOpen}
          onClose={() => setIsDashboardOpen(false)}
          onLoadPastReport={async (pastSid) => {
            setSessionId(pastSid)
            setCurrentStep('processing')
            try {
              const res = await fetch(`/api/report/${pastSid}`)
              if (res.ok) {
                const data = await res.json()
                setReportData(data)
                setCurrentStep('report')
              }
            } catch (e) {
              console.warn('Failed to load past report:', e)
            }
          }}
          onRetryRole={(roleJob) => {
            setSelectedJob(roleJob)
            setCurrentStep('select')
          }}
        />

        {/* Proctoring Settings Modal */}
        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          activePreset={activePreset}
          onSelectPreset={handleSelectPreset}
        />
      </div>
    </ErrorBoundary>
  )
}
