import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  parseQuestionSetsResponse,
  normalizeQuestionItem,
  validateAndNormalizeImportJson,
} from '../src/utils/questionSetUtils.js'

test('parseQuestionSetsResponse handles direct backend array response', () => {
  const mockBackendResponse = [
    { id: 'qset_1', name: 'Set A', item_count: 5 },
    { id: 'qset_2', name: 'Set B', item_count: 3 },
  ]
  const result = parseQuestionSetsResponse(mockBackendResponse)
  assert.equal(result.success, true)
  assert.equal(result.questionSets.length, 2)
  assert.equal(result.questionSets[0].name, 'Set A')
})

test('parseQuestionSetsResponse handles object with question_sets key', () => {
  const mockWrappedResponse = {
    question_sets: [{ id: 'qset_1', name: 'Set Wrapped', item_count: 2 }],
  }
  const result = parseQuestionSetsResponse(mockWrappedResponse)
  assert.equal(result.success, true)
  assert.equal(result.questionSets.length, 1)
  assert.equal(result.questionSets[0].name, 'Set Wrapped')
})

test('parseQuestionSetsResponse handles empty array cleanly', () => {
  const result = parseQuestionSetsResponse([])
  assert.equal(result.success, true)
  assert.equal(result.questionSets.length, 0)
})

test('parseQuestionSetsResponse detects and rejects invalid response shape', () => {
  const invalidResponses = [null, undefined, 'string response', 123, { status: 'error' }]
  for (const resp of invalidResponses) {
    const result = parseQuestionSetsResponse(resp)
    assert.equal(result.success, false)
    assert.match(result.error, /Unexpected question-sets response format/)
  }
})

test('normalizeQuestionItem standardizes question fields and defaults', () => {
  const raw = {
    text: 'What is the difference between TCP and UDP?',
    domain: 'Networking',
    difficulty: 'Easy',
    skills: ['TCP', 'UDP'],
    criteria: ['Reliability', 'Handshake'],
  }
  const normalized = normalizeQuestionItem(raw, 0)
  assert.equal(normalized.question_text, 'What is the difference between TCP and UDP?')
  assert.equal(normalized.domain, 'Networking')
  assert.equal(normalized.difficulty, 'Easy')
  assert.deepEqual(normalized.target_skills, ['TCP', 'UDP'])
  assert.deepEqual(normalized.ideal_criteria, ['Reliability', 'Handshake'])
  assert.equal(normalized.time_limit_seconds, 180)
})

test('normalizeQuestionItem handles comma-separated string skills and criteria', () => {
  const raw = {
    question: 'Explain how TLS handshake works.',
    target_skills: 'Security, TLS, Cryptography',
    ideal_criteria: 'Certificates, Key exchange',
  }
  const normalized = normalizeQuestionItem(raw, 0)
  assert.equal(normalized.question_text, 'Explain how TLS handshake works.')
  assert.deepEqual(normalized.target_skills, ['Security', 'TLS', 'Cryptography'])
  assert.deepEqual(normalized.ideal_criteria, ['Certificates', 'Key exchange'])
})

test('normalizeQuestionItem rejects empty or too-short question text', () => {
  assert.throws(
    () => normalizeQuestionItem({ question_text: 'Hey' }, 2),
    /Question 3 text must be at least 5 characters/
  )
})

test('validateAndNormalizeImportJson parses valid JSON object format', () => {
  const jsonStr = JSON.stringify({
    name: 'DevOps & SRE Track',
    description: 'Site reliability engineering assessment.',
    items: [
      {
        question_text: 'How do you design an alert fatigue mitigation strategy?',
        domain: 'SRE',
        difficulty: 'Advanced',
      },
    ],
  })
  const res = validateAndNormalizeImportJson(jsonStr, 'devops.json')
  assert.equal(res.name, 'DevOps & SRE Track')
  assert.equal(res.description, 'Site reliability engineering assessment.')
  assert.equal(res.source_filename, 'devops.json')
  assert.equal(res.items.length, 1)
  assert.equal(res.items[0].domain, 'SRE')
})

test('validateAndNormalizeImportJson parses raw array format and infers name from filename', () => {
  const jsonStr = JSON.stringify([
    {
      question_text: 'Explain the principles of zero trust architecture.',
      domain: 'Security',
      difficulty: 'Advanced',
    },
  ])
  const res = validateAndNormalizeImportJson(jsonStr, 'zero_trust_security.json')
  assert.equal(res.name, 'zero trust security')
  assert.equal(res.items.length, 1)
})

test('validateAndNormalizeImportJson throws descriptive errors for malformed or invalid JSON', () => {
  // Empty
  assert.throws(() => validateAndNormalizeImportJson(''), /Imported JSON file is empty/)

  // Bad syntax
  assert.throws(() => validateAndNormalizeImportJson('{ not json }'), /Malformed JSON syntax/)

  // Empty items
  assert.throws(
    () => validateAndNormalizeImportJson(JSON.stringify({ name: 'Valid Name', items: [] })),
    /Question set must contain at least 1 question/
  )

  // Name too short
  assert.throws(
    () =>
      validateAndNormalizeImportJson(
        JSON.stringify({ name: 'ab', items: [{ question_text: 'Valid question text?' }] })
      ),
    /Question set name must be at least 3 characters/
  )
})

