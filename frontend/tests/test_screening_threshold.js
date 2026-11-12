import test from 'node:test'
import assert from 'node:assert/strict'
import {
  normalizePassThresholdPct,
  isScreeningApproved,
} from '../src/utils/screeningUtils.js'

test('normalizePassThresholdPct normalizes decimal 0..1 thresholds to 0..100 percentages', () => {
  assert.equal(normalizePassThresholdPct(0.65), 65)
  assert.equal(normalizePassThresholdPct(0.7), 70)
  assert.equal(normalizePassThresholdPct(1.0), 100)
  assert.equal(normalizePassThresholdPct(65), 65)
  assert.equal(normalizePassThresholdPct(0), 0)
  assert.equal(normalizePassThresholdPct(-5), 0)
  assert.equal(normalizePassThresholdPct(null), 65)
  assert.equal(normalizePassThresholdPct(undefined), 65)
})

test('isScreeningApproved never marks REJECTED fit_score < thresholdPct as approved', () => {
  // Reproduces real bug where fit_score=45.0 >= pass_threshold=0.65 evaluated true
  assert.equal(
    isScreeningApproved({ status: 'REJECTED', fit_score: 45.0, passThreshold: 0.65 }),
    false
  )
  assert.equal(
    isScreeningApproved({ status: 'PASSED', fit_score: 72.0, passThreshold: 0.65 }),
    true
  )
  assert.equal(
    isScreeningApproved({ status: undefined, fit_score: 58.0, passThreshold: 0.65 }),
    false
  )
  assert.equal(
    isScreeningApproved({ status: undefined, fit_score: 65.0, passThreshold: 0.65 }),
    true
  )
})

