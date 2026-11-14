import { useState, useEffect, useRef } from 'react'
import { LiveGazeDetector } from './utils/liveGazeDetector'
import { InterviewFSM, INTERVIEW_STATES, saveSessionState, loadSessionState, clearSessionState } from './utils/interviewFSM'
import {
  authFetch,
  readCookie,
  refreshAccessToken,
  resolveRouteAccess,
  setAccessToken,
} from './utils/authClient'
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
import { CandidateAuthPage, AdminLoginPage } from './components/AuthPages'
import { CandidateProfilePage } from './components/CandidateProfilePage'
import { ResumeLibraryPage } from './components/ResumeLibraryPage'
import { RecommendationsPage } from './components/RecommendationsPage'
import { LearningRoadmapPage } from './components/LearningRoadmapPage'
import { AdminConsolePage } from './components/AdminConsolePage'
import { RoomJoinPage } from './components/RoomJoinPage'
import { WaitingRoom } from './components/WaitingRoom'
import { LiveInterviewRoom } from './components/LiveInterviewRoom'
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
  // Check developer fixture recording route first without conditional hooks
  if (typeof window !== 'undefined' && window.location.pathname.startsWith('/dev/record-fixture')) {
    return <RecordFixturePage />
  }
  return <MainApp />
}

function MainApp() {
  // Auth & Routing State
  const [authReady, setAuthReady] = useState(false)
  const [authEnabled, setAuthEnabled] = useState(false)
  const [currentUser, setCurrentUser] = useState(null)
  const [pathname, setPathname] = useState(() =>
    typeof window !== 'undefined' ? window.location.pathname : '/',
  )

  const navigate = (to) => {
    if (typeof window !== 'undefined' && window.location.pathname !== to) {
      window.history.pushState({}, '', to)
    }
    setPathname(to)
  }

  useEffect(() => {
    if (typeof window === 'undefined') return undefined
    const onPop = () => setPathname(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

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

  // Modals
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)
  const [isDashboardOpen, setIsDashboardOpen] = useState(false)

  // Media & Detector Refs
  const [mediaStream, setMediaStream] = useState(null)
  const mediaRecorderRef = useRef(null)
  const recordedChunksRef = useRef([])
  const liveGazeDetectorRef = useRef(new LiveGazeDetector('strict'))
  const fsmRef = useRef(new InterviewFSM(INTERVIEW_STATES.IDLE))

  // 0. Bootstrap auth flags and restore refresh session cleanly on boot
  useEffect(() => {
    let active = true
    async function initAuth() {
      let enabled = false
      try {
        const cfgRes = await fetch('/api/auth/config')
        if (cfgRes.ok) {
          const cfg = await cfgRes.json()
          enabled = Boolean(cfg.auth_enabled)
        }
      } catch {
        enabled = false
      }
      if (active) setAuthEnabled(enabled)

      if (readCookie('pluto_csrf_token')) {
        const refreshed = await refreshAccessToken()
        if (active && refreshed?.user) {
          setCurrentUser(refreshed.user)
          setCandidateName((prev) => prev || refreshed.user.full_name || '')
        }
      }
      if (active) setAuthReady(true)
    }
    initAuth()
    return () => {
      active = false
    }
  }, [])

  const routeGuard = authReady
    ? resolveRouteAccess({ pathname, authEnabled, user: currentUser })
    : { allowed: true, redirectTo: null, view: 'loading' }

  useEffect(() => {
    if (authReady && routeGuard.redirectTo && routeGuard.redirectTo !== pathname) {
      navigate(routeGuard.redirectTo)
    }
  }, [authReady, routeGuard.redirectTo, pathname])

  const handleLogout = async () => {
    const csrf = readCookie('pluto_csrf_token')
    try {
      await authFetch('/api/auth/logout', {
        method: 'POST',
        headers: csrf ? { 'X-CSRF-Token': csrf } : {},
      })
    } catch {
      // ignore network failures on logout cleanup
    }
    setAccessToken(null)
    setCurrentUser(null)
    handleResetSession()
    navigate(authEnabled ? '/login' : '/')
  }

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
      }
    }
  }, [])

  // Auto-fetch report data if entering or restored on report step without reportData
  useEffect(() => {
    if (authReady && currentStep === 'report' && !reportData && sessionId) {
      authFetch(`/api/report/${sessionId}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data) {
            setReportData(data)
          }
        })
        .catch((err) => console.warn('Auto-reload report error:', err))
    }
  }, [authReady, currentStep, reportData, sessionId])

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
      let res = await authFetch('/api/resume/screen', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok && res.status === 404) {
        // Fallback to /api/resume/upload if needed
        res = await authFetch('/api/resume/upload', {
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
      const res = await authFetch(`/api/interview/${sessionId}/start`, {
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
      await authFetch(`/api/interview/${sessionId}/question/${qIndex}/answer`, {
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
      await authFetch(`/api/interview/${sessionId}/recording`, {
        method: 'POST',
        body: formData,
      })

      // Trigger analysis pipeline
      setProcessingStatus({ stage: 'Launching parallel video and audio pipelines...', video_pct: 35, audio_pct: 35 })
      await authFetch(`/api/analysis/${sessionId}/run`, { method: 'POST' })

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
        const res = await authFetch(`/api/analysis/${sessionId}/status`)
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
      const res = await authFetch(`/api/report/${sessionId}`)
      if (res.ok) {
        const data = await res.json()
        setReportData(data)
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

  // Delete data action
  const handleDeleteData = async () => {
    if (!window.confirm('Are you sure you want to permanently delete this interview recording and all associated data?')) return
    try {
      await authFetch(`/api/interview/${sessionId}`, { method: 'DELETE' })
      alert('All session recordings and evaluation data have been permanently erased.')
      handleResetSession()
    } catch (e) {
      console.warn('Delete data error:', e)
    }
  }

  // Retry with different questions rotated from knapsack pool
  const handleRetryDifferentQuestions = async () => {
    if (!sessionId) return
    handleCalibrationComplete(calibrationData || {})
  }

  const handleStartFromSavedResume = async (resumeId, jobId) => {
    const chosenJob = jobs.find((j) => j.id === jobId) || selectedJob
    if (chosenJob) setSelectedJob(chosenJob)
    try {
      const fd = new FormData()
      fd.append('job_id', jobId)
      const res = await authFetch(`/api/resumes/${resumeId}/start-session`, {
        method: 'POST',
        body: fd,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Could not start screening from saved resume.')
      setScreeningResult(data)
      setSessionId(data.session_id)
      setCandidateName(data.candidate_name || currentUser?.full_name || '')
      setCurrentStep('screening')
      navigate('/')
    } catch (err) {
      alert(err.message || 'Failed to launch saved-resume screening.')
    }
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
          currentUser={currentUser}
          authEnabled={authEnabled}
          currentPath={pathname}
          onNavigate={navigate}
          onLogout={handleLogout}
        />

        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {!authReady && (
            <div className="py-16 text-center font-black uppercase text-sm">
              Initializing PLUTO vProctor session...
            </div>
          )}

          {authReady && (routeGuard.view === 'login' || routeGuard.view === 'register' || routeGuard.view === 'forgot-password' || routeGuard.view === 'reset-password') && (
            <CandidateAuthPage
              mode={routeGuard.view}
              onNavigate={navigate}
              onAuthSuccess={(user) => {
                setCurrentUser(user)
                setCandidateName(user.full_name || '')
                navigate(user.role === 'admin' || user.role === 'super_admin' ? '/admin' : '/')
              }}
            />
          )}

          {authReady && routeGuard.view === 'admin-login' && (
            <AdminLoginPage
              onNavigate={navigate}
              onAuthSuccess={(user) => {
                setCurrentUser(user)
                navigate('/admin')
              }}
            />
          )}

          {authReady && routeGuard.view === 'admin' && (
            <AdminConsolePage
              currentUser={currentUser}
              onOpenSettings={() => setIsSettingsOpen(true)}
            />
          )}

          {authReady && routeGuard.view === 'profile' && (
            <CandidateProfilePage
              onNavigate={navigate}
              onProfileSaved={(p) => p?.full_name && setCandidateName(p.full_name)}
            />
          )}

          {authReady && routeGuard.view === 'resumes' && (
            <ResumeLibraryPage
              jobs={jobs}
              onStartInterviewFromSaved={handleStartFromSavedResume}
            />
          )}

          {authReady && routeGuard.view === 'recommendations' && (
            <RecommendationsPage
              onNavigate={navigate}
              onSelectJobForInterview={(jobId) => {
                const matched = jobs.find((j) => j.id === jobId)
                if (matched) setSelectedJob(matched)
                setCurrentStep('select')
                navigate('/')
              }}
            />
          )}

          {authReady && routeGuard.view === 'roadmap' && (
            <LearningRoadmapPage
              onNavigate={navigate}
            />
          )}

          {authReady && routeGuard.view === 'rooms-join' && (
            <RoomJoinPage
              onJoinedRoom={(rId) => navigate(`/rooms/${rId}`)}
              onNavigate={navigate}
            />
          )}

          {authReady && routeGuard.view === 'live-room' && (
            <HostedRoomContainer
              roomId={pathname.split('/rooms/')[1]?.replace(/\/+$/, '')}
              currentUser={currentUser}
              onLeaveRoom={() => navigate('/')}
            />
          )}

          {authReady && routeGuard.view === 'practice' && (
            <>
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
            </>
          )}
        </main>

        {/* Candidate Past Sessions Drawer */}
        <CandidateDashboard
          isOpen={isDashboardOpen}
          onClose={() => setIsDashboardOpen(false)}
          currentUser={currentUser}
          authEnabled={authEnabled}
          onNavigate={navigate}
          onLoadPastReport={async (pastSid) => {
            setSessionId(pastSid)
            setCurrentStep('processing')
            navigate('/')
            try {
              const res = await authFetch(`/api/report/${pastSid}`)
              if (res.ok) {
                const data = await res.json()
                setReportData(data)
                setCurrentStep('report')
              }
            } catch (e) {
              console.warn('Failed to load past report:', e)
            }
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

function HostedRoomContainer({ roomId, currentUser, onLeaveRoom }) {
  const [snapshot, setSnapshot] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [admitted, setAdmitted] = useState(false)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const res = await authFetch(`/api/rooms/${roomId}/snapshot`)
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          setError(body.detail || 'Access to room forbidden or room not found.')
          return
        }
        const data = await res.json()
        if (active) setSnapshot(data)
      } catch {
        if (active) setError('Network error fetching room state.')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [roomId])

  if (loading) {
    return (
      <div className="p-12 text-center font-black uppercase text-sm text-gray-500 animate-pulse">
        Connecting to hosted room...
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-md mx-auto p-6 bg-[#FECDD3] border-2 border-black rounded-2xl text-center space-y-4 shadow-[4px_4px_0px_0px_#000]">
        <h2 className="text-base font-black uppercase text-red-950">Room Access Blocked</h2>
        <p className="text-xs font-bold text-red-900">{error}</p>
        <button
          type="button"
          onClick={onLeaveRoom}
          className="px-4 py-2 bg-black text-white rounded-xl text-xs font-black uppercase hover:bg-gray-800"
        >
          Return Home
        </button>
      </div>
    )
  }

  const isAdmin = currentUser?.role === 'admin' || currentUser?.role === 'super_admin'
  if (snapshot?.status === 'LOBBY' && !isAdmin && !admitted) {
    return (
      <WaitingRoom
        roomSnapshot={snapshot}
        onAdmitted={() => setAdmitted(true)}
        onLeave={onLeaveRoom}
      />
    )
  }

  return (
    <LiveInterviewRoom
      roomId={roomId}
      currentUser={currentUser}
      onLeaveRoom={onLeaveRoom}
    />
  )
}
