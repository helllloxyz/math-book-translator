import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'useChat.js'), 'utf8')

assert.match(source, /const buildHistory = \(messages\) => messages\.map/, 'chat history should use the visible persisted messages directly')
assert.match(source, /mode:\s*card\.type === 'quiz' \? 'quiz' : 'chat'/, 'card chat should send quiz mode only for quiz cards')
assert.match(source, /firstMessageNoteContent/, 'note creation should keep the original user message content for persistence')
assert.match(source, /createTypewriterQueue/, 'stream chunks should flow through a response-level frontend typewriter queue')
assert.match(source, /consumeStreamWithTypewriter/, 'both chat paths should read the response independently from their visible typewriter pace')
assert.match(source, /extractSuggestedQuestions/, 'completed chat streams should extract model-generated follow-up questions')
assert.match(source, /finalizeAssistantResponse/, 'suggested questions should be stored separately from the visible answer')
assert.match(source, /const assistantIndex = messages\.push/, 'streaming should update the assistant message through the reactive messages array')
assert.match(source, /messages\[assistantIndex\] = \{/, 'stream chunks should replace the assistant array entry to trigger UI updates')
assert.match(source, /card\.type === 'quiz' && card\.questionId/, 'structured quiz cards should submit answers to the attempts endpoint')
assert.match(source, /\/quiz\/questions\/\$\{card\.questionId\}\/attempts/, 'structured quiz attempts should use the quiz attempt API')
assert.doesNotMatch(source, /assistantMessage\.content \+=/, 'streaming should not mutate a raw assistant object outside Vue reactivity')

console.log('useChat history and streaming behavior ok')
