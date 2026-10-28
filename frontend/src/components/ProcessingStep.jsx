import React from 'react'
import { RefreshCw, Sparkles, Layers } from 'lucide-react'

export function ProcessingStep({ processingStatus, sessionId }) {
  return (
    <div className="max-w-md mx-auto text-center py-16 space-y-6">
      <div className="w-20 h-20 bg-[#FFE600] border-[3px] border-black rounded-2xl text-black mx-auto flex items-center justify-center shadow-[5px_5px_0px_0px_#000] rotate-3">
        <RefreshCw className="w-10 h-10 animate-spin stroke-[2.5]" />
      </div>

      <div>
        <h2 className="text-3xl font-black text-black uppercase tracking-tight">
          Analyzing Interview Performance
        </h2>
        <p className="text-xs sm:text-sm font-bold text-slate-600 mt-2">
          {processingStatus?.stage || 'Running deep multimodal analysis pipelines...'}
        </p>
      </div>

      {/* Progress Bars Deck */}
      <div className="p-6 rounded-2xl bg-white border-[3px] border-black text-left space-y-4 shadow-[5px_5px_0px_0px_#000]">
        {/* Vision Progress */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs font-black uppercase text-black">
            <span>Vision & Gaze (MediaPipe 478 Mesh)</span>
            <span className="font-mono">{processingStatus?.video_pct || 0}%</span>
          </div>
          <div className="h-4 w-full bg-[#F4F0EA] rounded-full overflow-hidden border-2 border-black">
            <div
              className="h-full bg-[#FFE600] border-r-2 border-black transition-all duration-300"
              style={{ width: `${processingStatus?.video_pct || 0}%` }}
            />
          </div>
        </div>

        {/* Audio Progress */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs font-black uppercase text-black">
            <span>Acoustics & Whisper Speech ASR</span>
            <span className="font-mono">{processingStatus?.audio_pct || 0}%</span>
          </div>
          <div className="h-4 w-full bg-[#F4F0EA] rounded-full overflow-hidden border-2 border-black">
            <div
              className="h-full bg-[#67E8F9] border-r-2 border-black transition-all duration-300"
              style={{ width: `${processingStatus?.audio_pct || 0}%` }}
            />
          </div>
        </div>
      </div>

      <div className="text-xs font-mono font-bold text-slate-600">
        Session Reference: <span className="bg-white px-2.5 py-1 border border-black rounded shadow-[1px_1px_0px_0px_#000]">{sessionId}</span>
      </div>
    </div>
  )
}
