import { useState, useEffect } from 'react'
import { AlertCircle, CheckCircle2, X } from 'lucide-react'

export function BrowserSupportBanner() {
  const [warning, setWarning] = useState(null)
  const [dismissed, setDismissed] = useState(false)

  useEffect(() => {
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
      navigator.userAgent
    )
    const hasMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia)
    const hasRecorder = typeof window.MediaRecorder !== 'undefined'
    const hasAudioCtx = typeof (window.AudioContext || window.webkitAudioContext) !== 'undefined'

    if (!hasMedia || !hasRecorder) {
      setWarning('Your browser does not support video/audio recording APIs. Please switch to Google Chrome or Microsoft Edge.')
    } else if (isMobile) {
      setWarning('Mobile device detected. For optimal proctoring and camera framing, desktop Google Chrome is strongly recommended.')
    }
  }, [])

  if (!warning || dismissed) return null

  return (
    <div className="bg-[#FFE600] border-b-2 border-black px-4 py-2.5 flex items-center justify-between text-xs font-bold text-black shadow-[0_2px_0_0_#000]">
      <div className="flex items-center space-x-2">
        <AlertCircle className="w-4 h-4 stroke-[2.5] shrink-0" />
        <span>{warning}</span>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="p-1 hover:bg-black/10 rounded transition-colors text-black"
        title="Dismiss"
      >
        <X className="w-4 h-4 stroke-[2.5]" />
      </button>
    </div>
  )
}
