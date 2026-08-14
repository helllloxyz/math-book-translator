import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const page = readFileSync(resolve(currentDir, 'ConversationPage.vue'), 'utf8')

assert.match(page, /@delete="handleDelete"/, 'conversation page should handle delete events from the dialog')
assert.match(page, /@regenerate="handleRegenerateQuiz"/, 'conversation page should handle explicit Quiz regeneration')
assert.match(page, /@select-question="handleSelectQuizQuestion"/, 'conversation page should let the learner choose a candidate before answering')
assert.match(page, /fetchQuizCandidates/, 'the opened conversation page should request a small candidate pool')
assert.match(page, /candidateCount/, 'the displayed candidate count should be configurable instead of fixed in the page')
assert.match(page, /generationCount/, 'the bank generation batch should be configurable separately from display count')
assert.match(page, /previousQuestions/, 'new candidate requests should carry prior questions for deduplication')
assert.match(page, /generateQuizQuestion\(\{ forceGenerate: true \}\)/, 'explicit regeneration should grow the persisted Quiz bank')
assert.match(page, /forceGenerate/, 'Quiz candidate requests should distinguish normal bank reads from explicit regeneration')
assert.match(page, /appendWithTypewriter/, 'generated Quiz questions should be revealed with a typewriter transition')
assert.match(page, /card\.value\.quizGenerationError/, 'Quiz generation failures should remain visible and retryable in the opened page')
assert.match(page, /quizRequest: quizRequest\.value/, 'Quiz request options should survive page persistence so regeneration keeps working after reload')
assert.match(page, /card\.value\.noteId = null/, 'starting a new pool after answering should preserve the old persisted conversation as a separate note')
assert.match(page, /const handleSend = async \(prompt\) =>/, 'send handler should receive the visible composer prompt directly')
assert.match(page, /useBookStore/, 'conversation page should use the book store note deletion API')
assert.match(page, /await bookStore\.deleteNote\(target\.noteId\)/, 'delete handler should delete persisted notes by noteId')
assert.match(page, /window\.localStorage\.removeItem\(conversationStorageKey\(conversationId\)\)/, 'delete handler should clear the cached conversation payload')
assert.match(page, /card\.value = null/, 'delete handler should leave the page in the missing conversation state')

console.log('conversation page delete behavior ok')
