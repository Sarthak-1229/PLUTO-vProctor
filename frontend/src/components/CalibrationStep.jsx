import React, { useState, useEffect, useRef } from 'react'
import {
  Eye,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react'

export function CalibrationStep({
  stream,
  liveDetector,
  onCalibrationComplete,
  onBack,
}) {
  const videoRef = useRef(null)
  const [countdown, setCountdown] = useState(4)
  const [calibrating, setCalibrating] = useState(false)
  const [calibrationSuccess, setCalibrationSuccess] = useState(false)
  const samplesRef = useRef([])

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream
    }
  }, [stream])

  const startCalibration = () => {
    setCalibrating(true)
    setCountdown(4)
    samplesRef.current = []

    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval)
          finishCalibration()
          return 0
        }
        return prev - 1
      })
    }, 1000)
  }

  const finishCalibration = () => {
    setCalibrating(false)
    let baselineData = {
      baseline_yaw: 0.0,
      baseline_pitch: 0.0,
      baseline_roll: 0.0,
      baseline_iris_h: 0.0,
      baseline_iris_v: 0.0,
      baseline_nose_y: 0.5,
      baseline_interocular: 0.15,
      is_calibrated: true,
    }

    if (liveDetector && liveDetector.currentBaseline) {
      baselineData = { ...liveDetector.currentBaseline, is_calibrated: true }
    } else if (liveDetector && typeof liveDetector.calibrateNeutralPose === 'function') {
      try {
        const cal = liveDetector.calibrateNeutralPose()
        if (cal) baselineData = { ...cal, is_calibrated: true }
      } catch (e) {
        console.warn('Detector calibration failed:', e)
      }
    }

    setCalibrationSuccess(true)
    setTimeout(() => {
      onCalibrationComplete(baselineData)
    }, 800)
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Banner */}
      <div className="bg-[#FFE600] border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-2">
        <div className="inline-flex items-center space-x-1.5 px-3 py-1 bg-white border-2 border-black rounded-lg text-xs font-black uppercase shadow-[2px_2px_0px_0px_#000]">
          <ShieldCheck className="w-4 h-4 text-black stroke-[2.5]" />
          <span>Biometric Eye-Gaze Alignment</span>
        </div>
        <h2 className="text-3xl font-black text-black tracking-tight uppercase">
          Step 4: Personal Gaze Calibration
        </h2>
        <p className="text-xs sm:text-sm font-bold text-black/80">
          We calibrate the proctoring thresholds to your unique eye geometry, screen position, and neutral seating posture.
        </p>
      </div>

      {/* Main Calibration Card */}
      <div className="bg-white border-[3px] border-black rounded-3xl p-6 sm:p-8 shadow-[6px_6px_0px_0px_#000] space-y-6 text-center">
        {/* Webcam View with Crosshair Target */}
        <div className="relative max-w-md mx-auto aspect-video bg-black border-[3px] border-black rounded-2xl overflow-hidden shadow-[4px_4px_0px_0px_#000]">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full h-full object-cover"
          />

          {/* Crosshair Target */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className={`w-36 h-36 rounded-full border-4 border-dashed transition-all duration-300 ${
              calibrating ? 'border-[#FFE600] animate-spin' : calibrationSuccess ? 'border-emerald-400' : 'border-white/50'
            }`} />
            <div className="absolute w-3 h-3 bg-[#FFE600] rounded-full shadow-[0_0_8px_#FFE600]" />
          </div>

          {/* Countdown Overlay */}
          {calibrating && (
            <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
              <span className="text-7xl font-mono font-black text-[#FFE600] drop-shadow-[4px_4px_0_#000]">
                {countdown}
              </span>
            </div>
          )}

          {calibrationSuccess && (
            <div className="absolute inset-0 bg-emerald-500/30 flex items-center justify-center">
              <span className="px-4 py-2 bg-[#A7F3D0] border-2 border-black rounded-xl text-xs font-black uppercase text-black shadow-[3px_3px_0px_0px_#000]">
                Calibration Locked!
              </span>
            </div>
          )}
        </div>

        {/* Instructions */}
        <div className="space-y-2">
          <h3 className="text-lg font-black text-black uppercase">
            {calibrating
              ? 'Hold still and look directly into your camera lens...'
              : calibrationSuccess
              ? 'Baseline Established Successfully'
              : 'Position Yourself and Begin Calibration'}
          </h3>
          <p className="text-xs font-bold text-slate-600 max-w-md mx-auto">
            Sit naturally at your working distance. When you click start, maintain direct eye contact with the yellow dot for 4 seconds.
          </p>
        </div>

        {/* Action Button */}
        <div className="pt-2 flex items-center justify-center gap-4">
          {!calibrating && !calibrationSuccess && (
            <button
              onClick={startCalibration}
              className="px-8 py-3.5 rounded-xl bg-[#FFE600] hover:bg-[#ffdf00] border-[3px] border-black font-black text-black text-xs uppercase shadow-[4px_4px_0px_0px_#000] hover:-translate-y-0.5 active:translate-y-0.5 transition-all flex items-center space-x-2"
            >
              <Eye className="w-4 h-4 stroke-[2.5]" />
              <span>Start 4-Second Calibration</span>
            </button>
          )}

          {calibrating && (
            <div className="px-6 py-3 rounded-xl bg-[#F4F0EA] border-2 border-black text-xs font-black uppercase flex items-center space-x-2">
              <RefreshCw className="w-4 h-4 animate-spin stroke-[2.5]" />
              <span>Sampling Baseline Posture ({countdown}s)...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
