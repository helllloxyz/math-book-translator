import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'useChat.js'), 'utf8')

assert.match(source, /appendResponseStylePrompt/, 'chat requests should append style prompts in request-only history')
assert.match(source, /lastUserIndex/, 'style prompts should target only the latest user message')
assert.match(source, /responseStylePrompt: options\.responseStylePrompt/, 'card chat should pass the selected response style to history building')
assert.doesNotMatch(source, /localStorage/, 'chat request building should not read prompt macro settings from localStorage')
assert.doesNotMatch(source, /prompt_macros|loadPromptMacros|applyPromptMacros/, 'chat request building should not expand legacy prompt macros')
assert.match(source, /mode:\s*card\.type === 'quiz' \? 'quiz' : 'chat'/, 'card chat should send quiz mode only for quiz cards')
assert.match(source, /firstMessageNoteContent/, 'note creation should keep the original user message content for persistence')
assert.match(source, /appendWithTypewriter/, 'stream chunks should be flushed through the frontend typewriter layer')
assert.match(source, /const assistantIndex = messages\.push/, 'streaming should update the assistant message through the reactive messages array')
assert.match(source, /messages\[assistantIndex\] = \{/, 'stream chunks should replace the assistant array entry to trigger UI updates')
assert.match(source, /card\.type === 'quiz' && card\.questionId/, 'structured quiz cards should submit answers to the attempts endpoint')
assert.match(source, /\/quiz\/questions\/\$\{card\.questionId\}\/attempts/, 'structured quiz attempts should use the quiz attempt API')
assert.doesNotMatch(source, /assistantMessage\.content \+=/, 'streaming should not mutate a raw assistant object outside Vue reactivity')

console.log('useChat request styling and streaming behavior ok')
