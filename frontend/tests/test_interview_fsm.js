import test from 'node:test'
import assert from 'node:assert/strict'
import { InterviewFSM, INTERVIEW_STATES } from '../src/utils/interviewFSM.js'

test('InterviewFSM starts at IDLE and performs valid linear transitions', () => {
  const fsm = new InterviewFSM(INTERVIEW_STATES.IDLE)
  assert.equal(fsm.getState(), INTERVIEW_STATES.IDLE)

  // IDLE -> SYSTEM_CHECK
  assert.ok(fsm.transition(INTERVIEW_STATES.SYSTEM_CHECK))
  assert.equal(fsm.getState(), INTERVIEW_STATES.SYSTEM_CHECK)

  // SYSTEM_CHECK -> CALIBRATION
  assert.ok(fsm.transition(INTERVIEW_STATES.CALIBRATION))
  assert.equal(fsm.getState(), INTERVIEW_STATES.CALIBRATION)

  // CALIBRATION -> GREETING
  assert.ok(fsm.transition(INTERVIEW_STATES.GREETING))
  assert.equal(fsm.getState(), INTERVIEW_STATES.GREETING)

  // GREETING -> ASKING
  assert.ok(fsm.transition(INTERVIEW_STATES.ASKING))
  assert.equal(fsm.getState(), INTERVIEW_STATES.ASKING)

  // ASKING -> LISTENING
  assert.ok(fsm.transition(INTERVIEW_STATES.LISTENING))
  assert.equal(fsm.getState(), INTERVIEW_STATES.LISTENING)

  // LISTENING -> NEXT
  assert.ok(fsm.transition(INTERVIEW_STATES.NEXT))
  assert.equal(fsm.getState(), INTERVIEW_STATES.NEXT)

  // NEXT -> WRAP_UP
  assert.ok(fsm.transition(INTERVIEW_STATES.WRAP_UP))
  assert.equal(fsm.getState(), INTERVIEW_STATES.WRAP_UP)

  // WRAP_UP -> UPLOADING
  assert.ok(fsm.transition(INTERVIEW_STATES.UPLOADING))
  assert.equal(fsm.getState(), INTERVIEW_STATES.UPLOADING)

  // UPLOADING -> PROCESSING
  assert.ok(fsm.transition(INTERVIEW_STATES.PROCESSING))
  assert.equal(fsm.getState(), INTERVIEW_STATES.PROCESSING)

  // PROCESSING -> COMPLETE
  assert.ok(fsm.transition(INTERVIEW_STATES.COMPLETE))
  assert.equal(fsm.getState(), INTERVIEW_STATES.COMPLETE)
})

test('InterviewFSM blocks illegal transitions', () => {
  const fsm = new InterviewFSM(INTERVIEW_STATES.IDLE)
  // Cannot jump from IDLE to ASKING directly
  assert.equal(fsm.canTransitionTo(INTERVIEW_STATES.ASKING), false)
  const success = fsm.transition(INTERVIEW_STATES.ASKING)
  assert.equal(success, false)
  assert.equal(fsm.getState(), INTERVIEW_STATES.IDLE)
})

test('InterviewFSM supports follow-up loop', () => {
  const fsm = new InterviewFSM(INTERVIEW_STATES.LISTENING)
  assert.ok(fsm.transition(INTERVIEW_STATES.FOLLOW_UP))
  assert.equal(fsm.getState(), INTERVIEW_STATES.FOLLOW_UP)

  assert.ok(fsm.transition(INTERVIEW_STATES.ASKING))
  assert.equal(fsm.getState(), INTERVIEW_STATES.ASKING)

  assert.ok(fsm.transition(INTERVIEW_STATES.LISTENING))
  assert.equal(fsm.getState(), INTERVIEW_STATES.LISTENING)
})
