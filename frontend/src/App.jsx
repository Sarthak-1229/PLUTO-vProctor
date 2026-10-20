import { useState, useEffect } from 'react'
import {
  ShieldCheck,
  Cpu,
  Database,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Eye,
  Mic,
  BrainCircuit,
  FileText
} from 'lucide-react'

function App() {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchHealth = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('http://127.0.0.1:8000/health')
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setHealth(data)
    } catch (err) {
      setError(err.message || 'Failed to connect to backend')
      setHealth(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
  }, [])

  return (
    <div className="min-h-screen bg-[#0b0f17] text-slate-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-[#0f172a]/70 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                PLUTO <span className="text-cyan-400 font-normal">vProctor</span>
              </span>
              <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800/60">
                Phase 0 Setup
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <button
              onClick={fetchHealth}
              disabled={loading}
              className="flex items-center space-x-2 text-xs font-medium px-3.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 transition-all border border-slate-700 active:scale-95 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh Status</span>
            </button>
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-xs">
              <span className={`w-2 h-2 rounded-full ${health ? 'bg-emerald-400 shadow-sm shadow-emerald-400' : 'bg-rose-500 shadow-sm shadow-rose-500'}`} />
              <span className="text-slate-300 font-mono">
                {health ? 'Backend Online' : 'Backend Disconnected'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl mx-auto px-6 py-10 w-full">
        {/* Hero Section */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 text-xs font-medium mb-4">
            <Activity className="w-3.5 h-3.5" />
            <span>Local Offline AI Mock-Interview & Proctoring System</span>
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight">
            AI Interviewer & Intelligent Proctoring Engine
          </h1>
          <p className="mt-4 text-slate-400 text-base leading-relaxed">
            Running 100% locally on a Windows machine with 6 GB VRAM constraints. Powered by hand-implemented
            algorithms, local Ollama Qwen 3B, MediaPipe vision proctoring, and faster-whisper speech recognition.
          </p>
        </div>

        {/* Status Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          {/* Card 1: Backend Health */}
          <div className="bg-[#111827]/80 rounded-2xl border border-slate-800 p-6 shadow-xl backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
            <div className="absolute top-0 right-0 w-24 h-24 bg-cyan-500/5 rounded-full blur-2xl group-hover:bg-cyan-500/10 transition" />
            <div className="flex items-center justify-between mb-4">
              <div className="w-10 h-10 rounded-lg bg-cyan-500/10 flex items-center justify-center text-cyan-400 border border-cyan-500/20">
                <Cpu className="w-5 h-5" />
              </div>
              {health ? (
                <span className="flex items-center space-x-1 text-xs text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded-md font-medium">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Healthy</span>
                </span>
              ) : (
                <span className="flex items-center space-x-1 text-xs text-rose-400 bg-rose-950/60 border border-rose-800/60 px-2 py-0.5 rounded-md font-medium">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  <span>Check Server</span>
                </span>
              )}
            </div>
            <h3 className="text-base font-semibold text-white">FastAPI Core Service</h3>
            <p className="text-xs text-slate-400 mt-1 mb-4">Health endpoint and API orchestration status.</p>
            <div className="space-y-2 text-xs font-mono bg-slate-900/80 p-3 rounded-lg border border-slate-800">
              <div className="flex justify-between">
                <span className="text-slate-500">Status:</span>
                <span className={health ? 'text-emerald-400' : 'text-rose-400'}>{health ? health.status : 'offline'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Version:</span>
                <span className="text-slate-300">{health ? health.version : 'v0.1.0'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">LLM Target:</span>
                <span className="text-cyan-400">{health ? health.model : 'qwen2.5:3b'}</span>
              </div>
            </div>
          </div>

          {/* Card 2: Dataset Discipline */}
          <div className="bg-[#111827]/80 rounded-2xl border border-slate-800 p-6 shadow-xl backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
            <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 rounded-full blur-2xl group-hover:bg-blue-500/10 transition" />
            <div className="flex items-center justify-between mb-4">
              <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center text-blue-400 border border-blue-500/20">
                <Database className="w-5 h-5" />
              </div>
              <span className="flex items-center space-x-1 text-xs text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded-md font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>6 Splits Loaded</span>
              </span>
            </div>
            <h3 className="text-base font-semibold text-white">Curated Q&A Datasets</h3>
            <p className="text-xs text-slate-400 mt-1 mb-4">Verified in datasets/data and datasets/data1.</p>
            <div className="space-y-1.5 text-xs bg-slate-900/80 p-3 rounded-lg border border-slate-800 font-mono">
              <div className="flex justify-between text-slate-300">
                <span>datasets/data</span>
                <span className="text-cyan-400">train, val, test</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>datasets/data1</span>
                <span className="text-cyan-400">train, val, test</span>
              </div>
              <div className="flex justify-between text-slate-400 border-t border-slate-800 pt-1">
                <span>Rule:</span>
                <span className="text-amber-400 text-[10px]">Test split read-once</span>
              </div>
            </div>
          </div>

          {/* Card 3: Offline Hardware Constraints */}
          <div className="bg-[#111827]/80 rounded-2xl border border-slate-800 p-6 shadow-xl backdrop-blur-sm relative overflow-hidden group hover:border-slate-700 transition">
            <div className="absolute top-0 right-0 w-24 h-24 bg-purple-500/5 rounded-full blur-2xl group-hover:bg-purple-500/10 transition" />
            <div className="flex items-center justify-between mb-4">
              <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center text-purple-400 border border-purple-500/20">
                <BrainCircuit className="w-5 h-5" />
              </div>
              <span className="text-xs text-purple-300 bg-purple-950/60 border border-purple-800/60 px-2 py-0.5 rounded-md font-medium">
                6 GB VRAM Safe
              </span>
            </div>
            <h3 className="text-base font-semibold text-white">Resource Policy</h3>
            <p className="text-xs text-slate-400 mt-1 mb-4">Lock-based GPUScheduler for concurrency.</p>
            <div className="space-y-1 text-xs text-slate-300 bg-slate-900/80 p-3 rounded-lg border border-slate-800">
              <div className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                <span>Ollama Qwen 3B (GPU, 30s keep-alive)</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <span>Faster-Whisper (int8 / CPU fallback)</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <span>MiniLM & MediaPipe (CPU Only)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Multimodal Proctoring Pipeline Preview */}
        <div className="bg-[#111827]/50 rounded-2xl border border-slate-800 p-6 mb-10">
          <h3 className="text-lg font-semibold text-white mb-2 flex items-center space-x-2">
            <Activity className="w-5 h-5 text-cyan-400" />
            <span>Architecture & Feature Pipeline</span>
          </h3>
          <p className="text-xs text-slate-400 mb-6">
            Key subsystems configured in Phase 0 and implemented in subsequent phases:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <Eye className="w-5 h-5 text-cyan-400 mb-2" />
              <h4 className="text-sm font-semibold text-white">Visual Proctoring</h4>
              <p className="text-xs text-slate-400 mt-1">
                MediaPipe face mesh tracking gaze deviation, eye contact ratio, head yaw/pitch, and multi-face alerts.
              </p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <Mic className="w-5 h-5 text-blue-400 mb-2" />
              <h4 className="text-sm font-semibold text-white">Audio & Fluency</h4>
              <p className="text-xs text-slate-400 mt-1">
                Whisper int8 transcription, speech pace WPM bounds (90-180), hesitation pauses, and filler word detection.
              </p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <BrainCircuit className="w-5 h-5 text-purple-400 mb-2" />
              <h4 className="text-sm font-semibold text-white">Custom Algorithms</h4>
              <p className="text-xs text-slate-400 mt-1">
                15 hand-implemented algorithms: Trie, BM25, Knapsack interview planning, MinHash dedupe, and MMR.
              </p>
            </div>
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <FileText className="w-5 h-5 text-emerald-400 mb-2" />
              <h4 className="text-sm font-semibold text-white">Scoring & Reports</h4>
              <p className="text-xs text-slate-400 mt-1">
                mm:ss proctoring deduction timeline, rubric weighted metrics, and downloadable PDF report summary.
              </p>
            </div>
          </div>
        </div>

        {/* Phase Workflow Progress */}
        <div className="bg-[#111827]/50 rounded-2xl border border-slate-800 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-300">Development Workflow Status</h3>
            <span className="text-xs font-mono text-cyan-400">Phase 0 of 9 Active</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs font-mono">
            <div className="p-2 rounded bg-cyan-950/60 border border-cyan-800 text-cyan-300 text-center font-bold">
              0. Setup [OK]
            </div>
            <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-500 text-center">
              1. Algorithms
            </div>
            <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-500 text-center">
              2. Dataset
            </div>
            <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-500 text-center">
              3. Resume
            </div>
            <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-500 text-center">
              4. Questions
            </div>
            <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-500 text-center">
              5. Frontend
            </div>
            <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-500 text-center">
              6. Analysis
            </div>
            <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-500 text-center">
              7. Scoring
            </div>
            <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-500 text-center">
              8. Polish
            </div>
            <div className="p-2 rounded bg-slate-900 border border-slate-800 text-slate-500 text-center">
              9. Report
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
        PLUTO vProctor &bull; AIML Academic Project &bull; Fully Local & Offline Execution
      </footer>
    </div>
  )
}

export default App
