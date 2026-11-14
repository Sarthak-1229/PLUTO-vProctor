/**
 * Utilities for Admin Question-Set loading, validation, normalization, and import.
 */

/**
 * Safely parse the backend question sets response shape.
 * Reconciles both direct array `[...]` and object `{ question_sets: [...] }`.
 */
export function parseQuestionSetsResponse(resData) {
  if (Array.isArray(resData)) {
    return { success: true, questionSets: resData }
  }
  if (resData && typeof resData === 'object' && Array.isArray(resData.question_sets)) {
    return { success: true, questionSets: resData.question_sets }
  }
  return {
    success: false,
    error: 'Unexpected question-sets response format. Expected an array or question_sets list.',
  }
}

/**
 * Normalize an individual question item from varied input formats.
 */
export function normalizeQuestionItem(item, index = 0) {
  if (!item || typeof item !== 'object') {
    throw new Error(`Question item at index ${index + 1} must be an object.`)
  }

  const questionText = (item.question_text || item.text || item.question || '').trim()
  if (!questionText || questionText.length < 5) {
    throw new Error(`Question ${index + 1} text must be at least 5 characters.`)
  }
  if (questionText.length > 2000) {
    throw new Error(`Question ${index + 1} text cannot exceed 2000 characters.`)
  }

  const domain = (item.domain || 'General').trim()
  const difficulty = (item.difficulty || 'Intermediate').trim()

  let targetSkills = []
  if (Array.isArray(item.target_skills)) {
    targetSkills = item.target_skills.map((s) => String(s).trim()).filter(Boolean)
  } else if (Array.isArray(item.skills)) {
    targetSkills = item.skills.map((s) => String(s).trim()).filter(Boolean)
  } else if (typeof item.target_skills === 'string') {
    targetSkills = item.target_skills.split(',').map((s) => s.trim()).filter(Boolean)
  }

  let idealCriteria = []
  if (Array.isArray(item.ideal_criteria)) {
    idealCriteria = item.ideal_criteria.map((c) => String(c).trim()).filter(Boolean)
  } else if (Array.isArray(item.criteria)) {
    idealCriteria = item.criteria.map((c) => String(c).trim()).filter(Boolean)
  } else if (typeof item.ideal_criteria === 'string') {
    idealCriteria = item.ideal_criteria.split(',').map((c) => c.trim()).filter(Boolean)
  } else if (item.answer) {
    idealCriteria = [String(item.answer).trim()]
  }

  const timeLimitSeconds = parseInt(item.time_limit_seconds || 180, 10)

  return {
    question_text: questionText,
    domain: domain || 'General',
    difficulty: difficulty || 'Intermediate',
    target_skills: targetSkills,
    ideal_criteria: idealCriteria,
    time_limit_seconds: isNaN(timeLimitSeconds) ? 180 : Math.max(30, Math.min(600, timeLimitSeconds)),
  }
}

/**
 * Validate and normalize a raw JSON string for Question Set import.
 */
export function validateAndNormalizeImportJson(jsonText, filename = '') {
  if (!jsonText || !jsonText.trim()) {
    throw new Error('Imported JSON file is empty.')
  }

  let parsed
  try {
    parsed = JSON.parse(jsonText)
  } catch (err) {
    throw new Error(`Malformed JSON syntax: ${err.message}`)
  }

  let rawItems = []
  let setName = ''
  let setDescription = ''

  if (Array.isArray(parsed)) {
    rawItems = parsed
    setName = filename
      ? filename.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ')
      : 'Imported Question Set'
    setDescription = filename ? `Imported from ${filename}` : 'Imported question collection'
  } else if (parsed && typeof parsed === 'object') {
    rawItems = parsed.items || parsed.questions || []
    setName = parsed.name || (filename ? filename.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ') : 'Imported Question Set')
    setDescription = parsed.description || (filename ? `Imported from ${filename}` : '')
  } else {
    throw new Error('JSON content must be an object or an array of question objects.')
  }

  setName = setName.trim()
  if (!setName || setName.length < 3) {
    throw new Error('Question set name must be at least 3 characters.')
  }
  if (setName.length > 255) {
    throw new Error('Question set name cannot exceed 255 characters.')
  }

  if (!Array.isArray(rawItems) || rawItems.length === 0) {
    throw new Error('Question set must contain at least 1 question.')
  }
  if (rawItems.length > 200) {
    throw new Error('Question set cannot exceed 200 questions.')
  }

  const normalizedItems = rawItems.map((item, idx) => normalizeQuestionItem(item, idx))

  return {
    name: setName,
    description: setDescription.trim() || null,
    source_filename: filename || null,
    items: normalizedItems,
  }
}
