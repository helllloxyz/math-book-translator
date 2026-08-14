import assert from 'node:assert/strict'

import { deserializeMessages, serializeMessages } from './chatMessages.js'

const messages = [
  { role: 'user', content: '问题', suggestedQuestions: ['不应保留'] },
  { role: 'assistant', content: '回答', suggestedQuestions: ['追问一？', '追问二？'] }
]

const restored = deserializeMessages(serializeMessages(messages))
assert.deepEqual(restored, [
  { role: 'user', content: '问题' },
  { role: 'assistant', content: '回答', suggestedQuestions: ['追问一？', '追问二？'] }
])

console.log('chat message suggestion persistence ok')
