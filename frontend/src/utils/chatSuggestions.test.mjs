import assert from 'node:assert/strict'

import {
  SUGGESTED_QUESTIONS_MARKER,
  extractSuggestedQuestions
} from './chatSuggestions.js'

const parsed = extractSuggestedQuestions([
  '先解释正文。',
  '',
  SUGGESTED_QUESTIONS_MARKER,
  '- 第一个问题？',
  '- 第二个问题？',
  '- 第三个问题？'
].join('\n'))

assert.equal(parsed.content, '先解释正文。')
assert.deepEqual(parsed.suggestedQuestions, [
  '第一个问题？',
  '第二个问题？',
  '第三个问题？'
])

const unchanged = extractSuggestedQuestions('普通 Markdown\n\n- 正文列表项')
assert.equal(unchanged.content, '普通 Markdown\n\n- 正文列表项')
assert.deepEqual(unchanged.suggestedQuestions, [])

const malformed = extractSuggestedQuestions(`正文仍需保留\n\n${SUGGESTED_QUESTIONS_MARKER}\n不是列表`)
assert.equal(malformed.content, '正文仍需保留')
assert.deepEqual(malformed.suggestedQuestions, [])

console.log('chat suggestion extraction ok')
