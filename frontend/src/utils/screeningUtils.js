/**
 * Normalize a job pass threshold that may be expressed as 0..1 fraction (0.65)
 * or 0..100 percentage (65) into an integer-rounded 0..100 percentage.
 */
export function normalizePassThresholdPct(passThreshold) {
  if (typeof passThreshold !== 'number' || Number.isNaN(passThreshold)) {
    return 65
  }
  if (passThreshold <= 0) {
    return 0
  }
  if (passThreshold <= 1.0) {
    return Math.round(passThreshold * 100)
  }
  return Math.min(100, Math.round(passThreshold))
}

/**
 * Determine whether resume screening passed using normalized threshold scales.
 */
export function isScreeningApproved({ status, fit_score, passThreshold }) {
  if (status === 'PASSED') return true
  if (status === 'REJECTED') return false
  const thresholdPct = normalizePassThresholdPct(passThreshold)
  const numericScore = typeof fit_score === 'number' && !Number.isNaN(fit_score) ? fit_score : 0
  return numericScore >= thresholdPct
}

