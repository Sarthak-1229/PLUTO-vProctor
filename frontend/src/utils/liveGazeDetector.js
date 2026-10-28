/**
 * Live MediaPipe FaceLandmarker and 1€ Gaze Tracking Utility.
 *
 * Runs real-time landmark, iris, and head-pose tracking in the browser at >= 15 FPS.
 * Uses One Euro adaptive filtering to eliminate jitter without phase lag.
 */

class LowPassFilter {
  constructor(alpha = 0.5) {
    this.alpha = alpha
    this.s = null
  }

  filter(value, alpha = null) {
    if (alpha !== null) this.alpha = alpha
    if (this.s === null) {
      this.s = value
    } else {
      this.s = this.alpha * value + (1.0 - this.alpha) * this.s
    }
    return this.s
  }

  reset() {
    this.s = null
  }
}

export class OneEuroFilter {
  constructor(minCutoff = 1.0, beta = 0.007, dCutoff = 1.0) {
    this.minCutoff = minCutoff
    this.beta = beta
    this.dCutoff = dCutoff
    this.xFilt = new LowPassFilter()
    this.dxFilt = new LowPassFilter()
    this.tPrev = null
  }

  _alpha(rate, cutoff) {
    const tau = 1.0 / (2.0 * Math.PI * cutoff)
    const te = 1.0 / Math.max(1e-6, rate)
    return 1.0 / (1.0 + tau / te)
  }

  filter(x, timestamp = performance.now() / 1000) {
    if (this.tPrev === null) {
      this.tPrev = timestamp
      return this.xFilt.filter(x)
    }

    const te = Math.max(1e-4, timestamp - this.tPrev)
    this.tPrev = timestamp
    const rate = 1.0 / te

    const prevX = this.xFilt.s !== null ? this.xFilt.s : x
    const dx = (x - prevX) * rate
    const edx = this.dxFilt.filter(dx, this._alpha(rate, this.dCutoff))

    const cutoff = this.minCutoff + this.beta * Math.abs(edx)
    return this.xFilt.filter(x, this._alpha(rate, cutoff))
  }

  reset() {
    this.xFilt.reset()
    this.dxFilt.reset()
    this.tPrev = null
  }
}

export const PRESETS = {
  strict: {
    name: 'Strict (Assessment Mode)',
    maxYaw: 15.0,
    maxPitchDown: 12.0,
    maxPitchUp: 14.0,
    maxIrisH: 0.18,
    maxIrisV: 0.16,
    alertDelaySec: 0.8,
    exitRatio: 0.75,
  },
  normal: {
    name: 'Normal (Standard Interview)',
    maxYaw: 20.0,
    maxPitchDown: 16.0,
    maxPitchUp: 18.0,
    maxIrisH: 0.22,
    maxIrisV: 0.20,
    alertDelaySec: 1.2,
    exitRatio: 0.75,
  },
  relaxed: {
    name: 'Relaxed (Practice Mode)',
    maxYaw: 25.0,
    maxPitchDown: 20.0,
    maxPitchUp: 22.0,
    maxIrisH: 0.26,
    maxIrisV: 0.24,
    alertDelaySec: 1.5,
    exitRatio: 0.75,
  },
}

export class LiveGazeDetector {
  constructor(presetKey = 'strict') {
    this.presetKey = presetKey
    this.preset = PRESETS[presetKey] || PRESETS.strict
    this.landmarker = null
    this.isReady = false

    // One Euro filters for yaw, pitch, roll, irisH, irisV
    this.filterYaw = new OneEuroFilter(1.0, 0.007)
    this.filterPitch = new OneEuroFilter(1.0, 0.007)
    this.filterRoll = new OneEuroFilter(1.0, 0.007)
    this.filterIrisH = new OneEuroFilter(1.0, 0.007)
    this.filterIrisV = new OneEuroFilter(1.0, 0.007)

    // Calibration offsets
    this.calibration = {
      baseline_yaw: 0.0,
      baseline_pitch: 0.0,
      baseline_roll: 0.0,
      baseline_iris_h: 0.0,
      baseline_iris_v: 0.0,
      baseline_nose_y: 0.5,
      baseline_interocular: 0.15,
      is_calibrated: false,
    }

    // State tracking for debounce and hysteresis
    this.inLookaway = false
    this.lookawayStartTime = null
    this.lastFrameTime = performance.now()
    this.fps = 0
    this.frameCount = 0
    this.fpsTimer = performance.now()
  }

  async initialize() {
    if (this.isReady && this.landmarker) return true
    try {
      const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision')
      const fileset = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
      )
      this.landmarker = await FaceLandmarker.createFromOptions(fileset, {
        baseOptions: {
          modelAssetPath: '/models/face_landmarker.task',
          delegate: 'GPU',
        },
        outputFaceBlendshapes: true,
        outputFacialTransformationMatrixes: true,
        runningMode: 'VIDEO',
        numFaces: 1,
      })
      this.isReady = true
      return true
    } catch (err) {
      console.warn('GPU FaceLandmarker init failed, falling back to CPU:', err)
      try {
        const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision')
        const fileset = await FilesetResolver.forVisionTasks(
          'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
        )
        this.landmarker = await FaceLandmarker.createFromOptions(fileset, {
          baseOptions: {
            modelAssetPath: '/models/face_landmarker.task',
            delegate: 'CPU',
          },
          outputFaceBlendshapes: true,
          outputFacialTransformationMatrixes: true,
          runningMode: 'VIDEO',
          numFaces: 1,
        })
        this.isReady = true
        return true
      } catch (cpuErr) {
        console.warn('FaceLandmarker load failed:', cpuErr)
        this.isReady = false
        return false
      }
    }
  }

  setPreset(key) {
    if (PRESETS[key]) {
      this.presetKey = key
      this.preset = PRESETS[key]
    }
  }

  setCalibration(calib) {
    this.calibration = { ...this.calibration, ...calib, is_calibrated: true }
  }

  processVideoFrame(videoElement, timestampMs = performance.now()) {
    if (!this.isReady || !this.landmarker || !videoElement || videoElement.readyState < 2) {
      return null
    }

    // Measure FPS
    this.frameCount++
    if (timestampMs - this.fpsTimer >= 1000) {
      this.fps = Math.round((this.frameCount * 1000) / (timestampMs - this.fpsTimer))
      this.frameCount = 0
      this.fpsTimer = timestampMs
    }

    const tSec = timestampMs / 1000.0
    let result = null
    try {
      result = this.landmarker.detectForVideo(videoElement, timestampMs)
    } catch (e) {
      return null
    }

    if (!result || !result.faceLandmarks || result.faceLandmarks.length === 0) {
      return {
        faceDetected: false,
        isLookingDirect: false,
        lookAwayType: 'FACE_MISSING',
        attentionScore: 0,
        fps: this.fps,
      }
    }

    const lm = result.faceLandmarks[0]

    // 1. Iris Displacement Ratios
    // Left eye outer: 33, inner: 133, iris: 468
    const leftOuter = lm[33]
    const leftInner = lm[133]
    const leftIris = lm[468]
    const leftW = Math.max(1e-4, Math.abs(leftInner.x - leftOuter.x))
    const leftHRatio = (leftIris.x - Math.min(leftOuter.x, leftInner.x)) / leftW - 0.5

    // Right eye inner: 362, outer: 263, iris: 473
    const rightInner = lm[362]
    const rightOuter = lm[263]
    const rightIris = lm[473]
    const rightW = Math.max(1e-4, Math.abs(rightOuter.x - rightInner.x))
    const rightHRatio = (rightIris.x - Math.min(rightInner.x, rightOuter.x)) / rightW - 0.5

    const rawIrisH = (leftHRatio + rightHRatio) / 2.0

    // Vertical iris offset
    const leftTop = lm[159].y
    const leftBottom = lm[145].y
    const leftVRatio = (leftIris.y - leftTop) / Math.max(1e-4, leftBottom - leftTop) - 0.5

    const rightTop = lm[386].y
    const rightBottom = lm[374].y
    const rightVRatio = (rightIris.y - rightTop) / Math.max(1e-4, rightBottom - rightTop) - 0.5

    const rawIrisV = (leftVRatio + rightVRatio) / 2.0

    // 2. Head Pose Euler Angles from Matrix
    let rawYaw = 0.0
    let rawPitch = 0.0
    let rawRoll = 0.0

    if (result.facialTransformationMatrixes && result.facialTransformationMatrixes.length > 0) {
      const mat = result.facialTransformationMatrixes[0].data
      // mat is column-major or row-major 4x4
      // Decompose R32, R33, R31
      rawPitch = Math.atan2(mat[6], mat[10]) * (180.0 / Math.PI)
      rawYaw = Math.atan2(-mat[2], Math.sqrt(mat[6] * mat[6] + mat[10] * mat[10])) * (180.0 / Math.PI)
      rawRoll = Math.atan2(mat[1], mat[0]) * (180.0 / Math.PI)
    }

    // 3. One Euro Filter
    const filtYaw = this.filterYaw.filter(rawYaw, tSec)
    const filtPitch = this.filterPitch.filter(rawPitch, tSec)
    const filtRoll = this.filterRoll.filter(rawRoll, tSec)
    const filtIrisH = this.filterIrisH.filter(rawIrisH, tSec)
    const filtIrisV = this.filterIrisV.filter(rawIrisV, tSec)

    // 4. Subtract Calibration Baseline
    const netYaw = filtYaw - this.calibration.baseline_yaw
    const netPitch = filtPitch - this.calibration.baseline_pitch
    const netRoll = filtRoll - this.calibration.baseline_roll
    const netIrisH = filtIrisH - this.calibration.baseline_iris_h
    const netIrisV = filtIrisV - this.calibration.baseline_iris_v

    // Blendshapes for blinks and look down
    let lookDownScore = 0.0
    let blinkScore = 0.0
    if (result.faceBlendshapes && result.faceBlendshapes.length > 0) {
      for (const cat of result.faceBlendshapes[0].categories) {
        if (cat.categoryName === 'eyeLookDownLeft' || cat.categoryName === 'eyeLookDownRight') {
          lookDownScore += cat.score * 0.5
        } else if (cat.categoryName === 'eyeBlinkLeft' || cat.categoryName === 'eyeBlinkRight') {
          blinkScore += cat.score * 0.5
        }
      }
    }

    // 5. Look-Away Detection with Hysteresis
    const { maxYaw, maxPitchDown, maxPitchUp, maxIrisH, maxIrisV, alertDelaySec, exitRatio } = this.preset

    const curYawLim = this.inLookaway ? maxYaw * exitRatio : maxYaw
    const curPitchDownLim = this.inLookaway ? maxPitchDown * exitRatio : maxPitchDown
    const curPitchUpLim = this.inLookaway ? maxPitchUp * exitRatio : maxPitchUp
    const curIrisHLim = this.inLookaway ? maxIrisH * exitRatio : maxIrisH
    const curIrisVLim = this.inLookaway ? maxIrisV * exitRatio : maxIrisV

    const isDown = netPitch < -curPitchDownLim || netIrisV > curIrisVLim || lookDownScore > 0.45
    const isSide = Math.abs(netYaw) > curYawLim || Math.abs(netIrisH) > curIrisHLim
    const isUp = netPitch > curPitchUpLim

    let lookAwayType = null
    if (isDown) lookAwayType = 'LOOK_DOWN'
    else if (isSide) lookAwayType = 'LOOK_SIDE'
    else if (isUp) lookAwayType = 'LOOK_UP'

    const isDeflected = lookAwayType !== null && blinkScore < 0.70

    // Time-based alert hysteresis (0.8s)
    let shouldAlert = false
    if (isDeflected) {
      if (this.lookawayStartTime === null) {
        this.lookawayStartTime = tSec
      } else if (tSec - this.lookawayStartTime >= alertDelaySec) {
        this.inLookaway = true
        shouldAlert = true
      }
    } else {
      this.lookawayStartTime = null
      this.inLookaway = false
    }

    // Attention Score (0-100)
    const yawPen = Math.min(40, (Math.abs(netYaw) / maxYaw) * 30)
    const pitchPen = Math.min(40, (Math.abs(netPitch) / maxPitchDown) * 30)
    const irisPen = Math.min(40, (Math.abs(netIrisH) / maxIrisH) * 20)
    const attentionScore = Math.max(0, Math.round(100 - (yawPen + pitchPen + irisPen)))

    return {
      faceDetected: true,
      isLookingDirect: !this.inLookaway,
      shouldAlert,
      lookAwayType: this.inLookaway ? lookAwayType : null,
      attentionScore,
      netYaw: Math.round(netYaw * 10) / 10,
      netPitch: Math.round(netPitch * 10) / 10,
      netRoll: Math.round(netRoll * 10) / 10,
      netIrisH: Math.round(netIrisH * 1000) / 1000,
      netIrisV: Math.round(netIrisV * 1000) / 1000,
      fps: this.fps,
      faceCenter: { x: lm[NOSE_TIP].x, y: lm[NOSE_TIP].y },
      interocular: Math.hypot(lm[263].x - lm[33].x, lm[263].y - lm[33].y),
    }
  }
}
