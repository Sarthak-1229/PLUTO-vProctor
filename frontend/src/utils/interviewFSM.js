/**
 * Finite State Machine (FSM) for PLUTO vProctor AI Interview.
 *
 * States:
 * IDLE -> SYSTEM_CHECK -> CALIBRATION -> GREETING -> ASKING -> LISTENING -> (FOLLOW_UP) -> NEXT -> WRAP_UP -> UPLOADING -> PROCESSING -> COMPLETE
 */

export const INTERVIEW_STATES = {
  IDLE: 'IDLE',
  SYSTEM_CHECK: 'SYSTEM_CHECK',
  CALIBRATION: 'CALIBRATION',
  GREETING: 'GREETING',
  ASKING: 'ASKING',
  LISTENING: 'LISTENING',
  FOLLOW_UP: 'FOLLOW_UP',
  NEXT: 'NEXT',
  WRAP_UP: 'WRAP_UP',
  UPLOADING: 'UPLOADING',
  PROCESSING: 'PROCESSING',
  COMPLETE: 'COMPLETE',
  ERROR: 'ERROR',
}

const VALID_TRANSITIONS = {
  [INTERVIEW_STATES.IDLE]: [INTERVIEW_STATES.SYSTEM_CHECK, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.SYSTEM_CHECK]: [INTERVIEW_STATES.CALIBRATION, INTERVIEW_STATES.IDLE, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.CALIBRATION]: [INTERVIEW_STATES.GREETING, INTERVIEW_STATES.SYSTEM_CHECK, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.GREETING]: [INTERVIEW_STATES.ASKING, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.ASKING]: [INTERVIEW_STATES.LISTENING, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.LISTENING]: [INTERVIEW_STATES.FOLLOW_UP, INTERVIEW_STATES.NEXT, INTERVIEW_STATES.WRAP_UP, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.FOLLOW_UP]: [INTERVIEW_STATES.ASKING, INTERVIEW_STATES.NEXT, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.NEXT]: [INTERVIEW_STATES.ASKING, INTERVIEW_STATES.WRAP_UP, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.WRAP_UP]: [INTERVIEW_STATES.UPLOADING, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.UPLOADING]: [INTERVIEW_STATES.PROCESSING, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.PROCESSING]: [INTERVIEW_STATES.COMPLETE, INTERVIEW_STATES.ERROR],
  [INTERVIEW_STATES.COMPLETE]: [INTERVIEW_STATES.IDLE],
  [INTERVIEW_STATES.ERROR]: [INTERVIEW_STATES.IDLE, INTERVIEW_STATES.SYSTEM_CHECK],
}

export class InterviewFSM {
  constructor(initialState = INTERVIEW_STATES.IDLE, onStateChange = null) {
    this.state = initialState
    this.onStateChange = onStateChange
    this.history = [initialState]
  }

  canTransitionTo(nextState) {
    const allowed = VALID_TRANSITIONS[this.state] || []
    return allowed.includes(nextState)
  }

  transition(nextState, context = {}) {
    if (!this.canTransitionTo(nextState)) {
      console.warn(`[FSM] Invalid state transition from ${this.state} to ${nextState}`)
      return false
    }
    const prevState = this.state
    this.state = nextState
    this.history.push(nextState)
    if (this.onStateChange) {
      this.onStateChange(nextState, prevState, context)
    }
    return true
  }

  getState() {
    return this.state
  }
}

/**
 * Session persistence helper for resuming across page refreshes.
 */
export const SESSION_STORAGE_KEY = 'pluto_interview_session'

export function saveSessionState(sessionData) {
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
      ...sessionData,
      savedAt: Date.now(),
    }))
  } catch (e) {
    console.warn('Failed to save session state:', e)
  }
}

export function loadSessionState() {
  try {
    const raw = sessionStorage.getItem(SESSION_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    // Expire session after 3 hours
    if (Date.now() - (parsed.savedAt || 0) > 3 * 3600 * 1000) {
      sessionStorage.removeItem(SESSION_STORAGE_KEY)
      return null
    }
    return parsed
  } catch (e) {
    return null
  }
}

export function clearSessionState() {
  try {
    sessionStorage.removeItem(SESSION_STORAGE_KEY)
  } catch (e) {}
}

