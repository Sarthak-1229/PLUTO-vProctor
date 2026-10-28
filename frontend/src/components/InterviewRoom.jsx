import React, { useState, useEffect, useRef } from 'react'
import {
  Mic,
  Volume2,
  Clock,
  Eye,
  AlertTriangle,
  ArrowRight,
  RotateCcw,
  Sparkles,
  Radio,
  Video,
  CheckCircle2,
  RefreshCw,
  HelpCircle,
  MessageSquare,
} from 'lucide-react'

export function InterviewRoom({
  sessionId,
  candidateName,
  jobTitle,
  company,
  questions,
  currentQuestionIndex,
  onNextQuestion,
  onFinishInterview,
  stream,
  liveDetector,
  activePreset,
}) {
  // Local sub-states within interview room: 'GREETING' | 'ASKING' | 'LISTENING' | 'FOLLOW_UP' | 'THINKING' | 'WRAP_UP'
  const [subState, setSubState] = useState('GREETING')
  const [overallSeconds, setOverallSeconds] = useState(0)
  const [questionSeconds, setQuestionSeconds] = useState(0)
  const [isAiSpeaking, setIsAiSpeaking] = useState(false)
  const [candidateTranscript, setCandidateTranscript] = useState('')
  const [liveAlert, setLiveAlert] = useState(null)
  const [isLookingAway, setIsLookingAway] = useState(false)
  const [followUpQuestion, setFollowUpQuestion] = useState(null)
  const [followUpCount, setFollowUpCount] = useState(0)
  const [closingNotes, setClosingNotes] = useState('')
  const [rating, setRating] = useState(5)
  const [silenceCounter, setSilenceCounter] = useState(0)
  const [proctoringEvents, setProctoringEvents] = useState([])

  const videoRef = useRef(null)
  const speechSynthRef = useRef(window.speechSynthesis)
  const recognitionRef = useRef(null)
  const questionStartTimeRef = useRef(0)
  const silenceTimerRef = useRef(null)
  const ttsWindowsRef = useRef([])

  // Attach webcam stream to video element
  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream
    }
  }, [stream])

  // Overall session timer
  useEffect(() => {
    const timer = setInterval(() => {
      setOverallSeconds((s) => s + 1)
      if (subState === 'LISTENING') {
        setQuestionSeconds((qs) => qs + 1)
      }
    }, 1000)
    return () => clearInterval(timer)
  }, [subState])

  // Live detector listener
  useEffect(() => {
    if (!liveDetector) return

    const handleGazeUpdate = (stats) => {
      setIsLookingAway(!stats.isDirect)
      if (!stats.isDirect && stats.lookAwayType) {
        setLiveAlert({
          message: `Eye Contact Divergence: ${stats.lookAwayType.replace('_', ' ')}`,
          type: stats.lookAwayType,
        })
      } else {
        setLiveAlert(null)
      }
    }

    if (typeof liveDetector.onGazeUpdate === 'function') {
      liveDetector.onGazeUpdate = handleGazeUpdate
    }

    // Proctoring tab switch / blur listener
    const handleBlur = () => {
      const event = {
        id: Date.now(),
        message: 'Window blur / Tab switch detected',
        penalty: 5,
        time: formatSeconds(overallSeconds),
      }
      setProctoringEvents((prev) => [event, ...prev.slice(0, 10)])
      setLiveAlert({ message: 'Tab Switch / Unfocused Window Detected', type: 'TAB_BLUR' })
    }

    window.addEventListener('blur', handleBlur)
    return () => {
      window.removeEventListener('blur', handleBlur)
    }
  }, [liveDetector, overallSeconds])

  // Format seconds as mm:ss
  const formatSeconds = (sec) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  // Text to speech helper
  const speakText = (text, onEndCallback = null) => {
    if (!speechSynthRef.current) {
      if (onEndCallback) onEndCallback()
      return
    }

    speechSynthRef.current.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 1.0
    utterance.pitch = 1.0

    const tStart = overallSeconds
    utterance.onstart = () => {
      setIsAiSpeaking(true)
    }

    utterance.onend = () => {
      setIsAiSpeaking(false)
      const tEnd = overallSeconds
      ttsWindowsRef.current.push([tStart, tEnd])
      if (onEndCallback) onEndCallback()
    }

    utterance.onerror = () => {
      setIsAiSpeaking(false)
      if (onEndCallback) onEndCallback()
    }

    speechSynthRef.current.speak(utterance)
  }

  // Greeting speech upon mounting
  useEffect(() => {
    if (subState === 'GREETING') {
      const greetingMsg = `Hello ${candidateName || 'there'}! Welcome to your technical interview for the ${jobTitle || 'selected'} position at ${company || 'the team'}. I am Pluto, your AI interviewer. I will present questions one at a time and listen to your spoken answers. Take a breath, and when you are ready, let's start.`
      speakText(greetingMsg)
    }
  }, [])

  // Start the first question after greeting
  const handleStartQuestions = () => {
    if (speechSynthRef.current) speechSynthRef.current.cancel()
    setSubState('ASKING')
    startQuestion(0)
  }

  // Deliver a question
  const startQuestion = (idx) => {
    const q = questions[idx]
    if (!q) {
      setSubState('WRAP_UP')
      return
    }

    setCandidateTranscript('')
    setQuestionSeconds(0)
    questionStartTimeRef.current = overallSeconds
    setFollowUpQuestion(null)

    // Speak question text
    speakText(q.question, () => {
      setSubState('LISTENING')
      startSpeechRecognition()
    })
  }

  // Browser speech recognition
  const startSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return

    try {
      const recognition = new SpeechRecognition()
      recognition.continuous = true
      recognition.interimResults = true
      recognition.lang = 'en-US'

      recognition.onresult = (event) => {
        let finalTrans = ''
        for (let i = 0; i < event.results.length; i++) {
          finalTrans += event.results[i][0].transcript + ' '
        }
        setCandidateTranscript(finalTrans)
        // Reset silence counter when candidate speaks
        setSilenceCounter(0)
      }

      recognition.onerror = (e) => {
        console.warn('Speech recognition warning:', e.error)
      }

      recognition.start()
      recognitionRef.current = recognition
    } catch (e) {
      console.warn('Recognition start error:', e)
    }
  }

  const stopSpeechRecognition = () => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch (e) {}
      recognitionRef.current = null
    }
  }

  // Handle "I'm Done / Next Question"
  const handleAnswerSubmit = async () => {
    stopSpeechRecognition()
    if (speechSynthRef.current) speechSynthRef.current.cancel()

    const qEndTime = overallSeconds
    const qStartTime = questionStartTimeRef.current
    const transcriptText = candidateTranscript.trim()
    const wordCount = transcriptText ? transcriptText.split(/\s+/).length : 0

    // Adaptive follow-up check: if answer was short (< 15 words) and we haven't asked 2 follow-ups
    if (wordCount > 0 && wordCount < 15 && followUpCount < 2 && !followUpQuestion) {
      setSubState('THINKING')
      try {
        const currentQ = questions[currentQuestionIndex]
        const res = await fetch(`/api/interview/${sessionId}/followup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question_id: currentQ.question_id || 'q_default',
            transcript: transcriptText,
          }),
        })
        const data = await res.json()
        if (data && data.is_follow_up && data.follow_up_question) {
          setFollowUpQuestion(data.follow_up_question)
          setFollowUpCount((c) => c + 1)
          setSubState('FOLLOW_UP')
          speakText(data.follow_up_question, () => {
            setSubState('LISTENING')
            startSpeechRecognition()
          })
          return
        }
      } catch (e) {
        console.warn('Follow-up check error:', e)
      }
    }

    // Submit answer to parent and move to next question or wrap-up
    setSubState('THINKING')
    await onNextQuestion({
      qIndex: currentQuestionIndex,
      transcript: transcriptText,
      startTime: qStartTime,
      endTime: qEndTime,
      ttsWindows: ttsWindowsRef.current,
    })

    ttsWindowsRef.current = []

    if (currentQuestionIndex + 1 < questions.length) {
      setSubState('ASKING')
      startQuestion(currentQuestionIndex + 1)
    } else {
      setSubState('WRAP_UP')
      speakText('Thank you for sharing your responses. Do you have any questions or concluding remarks before we finalize your assessment?')
    }
  }

  // Repeat current question
  const handleRepeatQuestion = () => {
    const q = questions[currentQuestionIndex]
    if (q) {
      speakText(followUpQuestion || q.question)
    }
  }

  const currentQ = questions[currentQuestionIndex]

  return (
    <div className="space-y-6">
      {/* Top Banner: Status, Timer, Question Indicator */}
      <div className="bg-white border-[3px] border-black rounded-2xl p-4 sm:p-5 shadow-[5px_5px_0px_0px_#000] flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="px-3 py-1 bg-[#67E8F9] text-black border-2 border-black font-black text-xs uppercase rounded-md shadow-[2px_2px_0px_0px_#000]">
            {subState === 'GREETING'
              ? 'Onboarding & Greeting'
              : subState === 'WRAP_UP'
              ? 'Closing Wrap-Up'
              : `Question ${currentQuestionIndex + 1} of ${questions.length}`}
          </div>
          <div className="flex items-center space-x-1.5 px-3 py-1 bg-[#A7F3D0] border-2 border-black rounded-md text-xs font-black uppercase text-black shadow-[2px_2px_0px_0px_#000]">
            <Radio className="w-3.5 h-3.5 stroke-[2.5] animate-pulse" />
            <span>AI Interview Session Live</span>
          </div>
        </div>

        <div className="flex items-center space-x-4 font-mono font-black text-sm">
          <div className="flex items-center space-x-1.5 bg-[#FFE600] border-2 border-black px-3 py-1 rounded-md shadow-[2px_2px_0px_0px_#000]">
            <Clock className="w-4 h-4 stroke-[2.5]" />
            <span>Session: {formatSeconds(overallSeconds)}</span>
          </div>
          {subState === 'LISTENING' && (
            <div className="flex items-center space-x-1.5 bg-[#F4F0EA] border-2 border-black px-3 py-1 rounded-md shadow-[2px_2px_0px_0px_#000]">
              <span>Answer: {formatSeconds(questionSeconds)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Grid: AI Prompter & Candidate Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Column: AI Interviewer Prompter (7 Cols) */}
        <div className="lg:col-span-7 bg-white border-[3px] border-black rounded-2xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] flex flex-col justify-between space-y-6">
          <div className="space-y-6">
            {/* AI Avatar & Animated Waveform */}
            <div className="flex items-center space-x-4 border-b-2 border-black pb-4">
              <div className="w-12 h-12 rounded-2xl bg-[#FFE600] border-2 border-black flex items-center justify-center shadow-[3px_3px_0px_0px_#000] rotate-[-2deg]">
                <Sparkles className="w-6 h-6 text-black stroke-[2.5]" />
              </div>
              <div className="flex-1">
                <div className="flex items-center justify-between">
                  <h3 className="font-black text-sm uppercase text-black">Pluto AI Interviewer</h3>
                  <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded border border-black ${
                    isAiSpeaking ? 'bg-[#A7F3D0] animate-pulse' : 'bg-[#F4F0EA]'
                  }`}>
                    {isAiSpeaking ? 'Speaking' : subState === 'LISTENING' ? 'Listening' : 'Ready'}
                  </span>
                </div>
                {/* Simulated reactive audio waveform */}
                <div className="flex items-center space-x-1 mt-1.5 h-4">
                  {[40, 70, 90, 50, 80, 100, 60, 85, 45, 95, 65, 30].map((h, i) => (
                    <div
                      key={i}
                      className={`w-1 rounded-full transition-all duration-150 ${
                        isAiSpeaking ? 'bg-black' : 'bg-slate-300'
                      }`}
                      style={{ height: isAiSpeaking ? `${Math.max(20, (h * (i % 2 === 0 ? 0.9 : 1.2)) % 100)}%` : '20%' }}
                    />
                  ))}
                </div>
              </div>
            </div>

            {/* Sub-State: GREETING */}
            {subState === 'GREETING' && (
              <div className="space-y-4">
                <h2 className="text-2xl font-black text-black">
                  Welcome, {candidateName || 'Candidate'}!
                </h2>
                <p className="text-xs sm:text-sm font-bold text-slate-700 leading-relaxed bg-[#F4F0EA] p-4 rounded-xl border-2 border-black shadow-[2px_2px_0px_0px_#000]">
                  I will be asking you technical questions designed for the <strong>{jobTitle}</strong> position at <strong>{company}</strong>.
                  Speak clearly into your microphone. Maintain natural eye contact with your camera.
                  When you have completed an answer, click <strong>"I'm Done / Next"</strong>.
                </p>
                <button
                  onClick={handleStartQuestions}
                  className="px-6 py-3 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-[3px] border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
                >
                  <span>Begin First Question</span>
                  <ArrowRight className="w-4 h-4 stroke-[2.5]" />
                </button>
              </div>
            )}

            {/* Sub-State: ASKING / LISTENING / FOLLOW_UP / THINKING */}
            {(subState === 'ASKING' || subState === 'LISTENING' || subState === 'FOLLOW_UP' || subState === 'THINKING') && (
              <div className="space-y-4">
                {/* Follow-up Alert Banner */}
                {followUpQuestion && (
                  <div className="p-3 bg-[#FEF08A] border-2 border-black rounded-xl text-xs font-black uppercase text-black flex items-center space-x-2 shadow-[2px_2px_0px_0px_#000]">
                    <Sparkles className="w-4 h-4 stroke-[2.5] text-amber-700" />
                    <span>Follow-Up Probe: Please elaborate further on this point</span>
                  </div>
                )}

                {/* Question Text Prompter */}
                <h2 className="text-2xl sm:text-3xl font-black text-black leading-snug tracking-tight">
                  "{followUpQuestion || currentQ?.question}"
                </h2>

                {/* Voice Controls */}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <button
                    onClick={handleRepeatQuestion}
                    className="px-3.5 py-1.5 bg-[#F4F0EA] hover:bg-white border-2 border-black rounded-lg font-black text-xs uppercase text-black flex items-center space-x-1.5 shadow-[2px_2px_0px_0px_#000] transition-all"
                  >
                    <Volume2 className="w-3.5 h-3.5 stroke-[2.5]" />
                    <span>Repeat Question</span>
                  </button>
                  {isAiSpeaking && (
                    <span className="text-[11px] font-black uppercase text-black px-2.5 py-1 bg-[#A7F3D0] border-2 border-black rounded shadow-[2px_2px_0px_0px_#000] animate-pulse">
                      Speaking...
                    </span>
                  )}
                </div>

                {/* Candidate Spoken Live Transcription Box */}
                <div className="p-4 rounded-xl bg-[#F4F0EA] border-2 border-black shadow-[3px_3px_0px_0px_#000] space-y-3">
                  <div className="flex items-center justify-between">
                    <span className={`px-2.5 py-1 rounded border-2 border-black font-black text-[11px] uppercase shadow-[1px_1px_0px_0px_#000] flex items-center space-x-1.5 ${
                      subState === 'LISTENING' ? 'bg-[#A7F3D0] text-black animate-pulse' : 'bg-white text-slate-700'
                    }`}>
                      <Mic className="w-3.5 h-3.5 stroke-[2.5]" />
                      <span>{subState === 'LISTENING' ? 'Listening to your speech...' : 'Microphone Ready'}</span>
                    </span>
                    <span className="font-mono text-xs font-black text-black">
                      {candidateTranscript.trim() ? candidateTranscript.trim().split(/\s+/).length : 0} WORDS
                    </span>
                  </div>

                  <textarea
                    rows={3}
                    value={candidateTranscript}
                    onChange={(e) => setCandidateTranscript(e.target.value)}
                    placeholder="Speak your answer clearly... your live speech will appear here. You can also edit or add key notes directly."
                    className="w-full p-3 rounded-lg bg-white border-2 border-black font-mono text-xs text-black placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#FFE600] resize-none"
                  />
                  <div className="flex items-center justify-between text-[10px] font-bold text-slate-500">
                    <span>💡 Speak naturally. Filler words and pauses are evaluated with high precision.</span>
                    {candidateTranscript && (
                      <button
                        onClick={() => setCandidateTranscript('')}
                        className="text-black font-black underline uppercase hover:text-red-600"
                      >
                        Clear
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Sub-State: WRAP_UP */}
            {subState === 'WRAP_UP' && (
              <div className="space-y-4">
                <h2 className="text-2xl font-black text-black uppercase">
                  Do you have any questions for me?
                </h2>
                <p className="text-xs font-bold text-slate-600">
                  You have completed all technical questions. If you have closing remarks or questions regarding the role, type them below.
                </p>
                <textarea
                  rows={3}
                  value={closingNotes}
                  onChange={(e) => setClosingNotes(e.target.value)}
                  placeholder="e.g. Can you tell me more about the engineering team's current deployment workflow?"
                  className="w-full p-3 rounded-lg bg-[#F4F0EA] border-2 border-black font-mono text-xs text-black focus:outline-none focus:ring-2 focus:ring-[#FFE600] resize-none"
                />
                {/* Candidate Experience Rating */}
                <div className="space-y-1.5 pt-2">
                  <label className="text-xs font-black uppercase text-slate-700">How was your interview experience?</label>
                  <div className="flex items-center space-x-2">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        onClick={() => setRating(star)}
                        className={`w-9 h-9 rounded-lg border-2 border-black font-black text-sm flex items-center justify-center transition-all ${
                          rating >= star ? 'bg-[#FFE600] shadow-[2px_2px_0px_0px_#000]' : 'bg-white'
                        }`}
                      >
                        ★
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Bottom Action Bar */}
          <div className="pt-6 border-t-2 border-black flex items-center justify-between">
            <span className="text-xs font-mono font-bold text-slate-600">
              {currentQ ? `Allocated: ${currentQ.est_seconds || 120}s` : 'PLUTO AI Engine'}
            </span>

            {subState === 'WRAP_UP' ? (
              <button
                onClick={onFinishInterview}
                className="px-8 py-3.5 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-[3px] border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
              >
                <CheckCircle2 className="w-4 h-4 stroke-[2.5]" />
                <span>Submit & Generate Dossier</span>
              </button>
            ) : subState !== 'GREETING' && (
              <button
                onClick={handleAnswerSubmit}
                disabled={subState === 'THINKING'}
                className="px-8 py-3.5 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-[3px] border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 disabled:opacity-50 transition-all flex items-center space-x-2"
              >
                {subState === 'THINKING' ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin stroke-[2.5]" />
                    <span>Processing Answer...</span>
                  </>
                ) : (
                  <>
                    <span>{currentQuestionIndex + 1 < questions.length ? "I'm Done / Next Question" : 'Complete Interview'}</span>
                    <ArrowRight className="w-4 h-4 stroke-[2.5]" />
                  </>
                )}
              </button>
            )}
          </div>
        </div>

        {/* Right Column: Candidate Webcam & Proctoring Telemetry (5 Cols) */}
        <div className="lg:col-span-5 flex flex-col space-y-4">
          {/* Webcam Box */}
          <div className="bg-black border-[3px] border-black rounded-2xl p-2 shadow-[5px_5px_0px_0px_#000] relative overflow-hidden aspect-video flex items-center justify-center">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover rounded-xl"
            />

            {/* Live Indicators Overlay */}
            <div className="absolute top-3 right-3 flex items-center space-x-1.5 text-[10px] font-mono font-black z-10 pointer-events-none">
              <span className="px-2 py-0.5 rounded bg-black/75 text-[#67E8F9] border border-white/20">
                15+ FPS
              </span>
              <span className="px-2 py-0.5 rounded bg-[#FFE600] text-black border border-black flex items-center">
                <Video className="w-3 h-3 mr-1 stroke-[2.5]" />
                REC
              </span>
            </div>

            {/* Live Alert Banner */}
            {liveAlert && (
              <div className="absolute top-4 left-4 right-4 bg-[#FF4D4D] text-black border-2 border-black px-4 py-2 rounded-lg text-xs font-black uppercase flex items-center space-x-2 shadow-[3px_3px_0px_0px_#000] animate-bounce z-20">
                <AlertTriangle className="w-4 h-4 shrink-0 stroke-[2.5]" />
                <span>{liveAlert.message}</span>
              </div>
            )}

            {/* Gaze Status Pill */}
            <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between text-[11px] font-black uppercase">
              <span className={`px-2.5 py-1 rounded border-2 border-black shadow-[2px_2px_0px_0px_#000] flex items-center ${
                isLookingAway ? 'bg-[#FF4D4D] text-black' : 'bg-[#A7F3D0] text-black'
              }`}>
                <Eye className="w-3.5 h-3.5 mr-1 stroke-[2.5]" />
                {isLookingAway ? 'GAZE DRIFT' : 'DIRECT GAZE'}
              </span>
              <span className="px-2 py-0.5 rounded bg-white text-black border border-black font-mono text-[10px]">
                Preset: {activePreset}
              </span>
            </div>
          </div>

          {/* Live Proctoring Log */}
          <div className="bg-white border-[3px] border-black rounded-2xl p-4 shadow-[4px_4px_0px_0px_#000] flex-1 flex flex-col">
            <h4 className="text-xs font-black text-black uppercase tracking-wider mb-2 flex items-center space-x-1.5">
              <Radio className="w-4 h-4 text-black stroke-[2.5]" />
              <span>Real-Time Proctoring Stream</span>
            </h4>
            <div className="flex-1 overflow-y-auto space-y-2 pr-1 max-h-36">
              {proctoringEvents.length === 0 ? (
                <p className="text-xs font-bold text-slate-500 italic mt-2">
                  Proctoring telemetry active. Zero integrity infractions logged.
                </p>
              ) : (
                proctoringEvents.map((ev) => (
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
    </div>
  )
}
