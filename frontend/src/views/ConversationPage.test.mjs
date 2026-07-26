import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const page = readFileSync(resolve(currentDir, 'ConversationPage.vue'), 'utf8')

assert.match(page, /@delete="handleDelete"/, 'conversation page should handle delete events from the dialog')
assert.match(page, /const prompt = typeof payload === 'string' \? payload : payload\?\.prompt/, 'send handler should accept structured prompt payloads')
assert.match(page, /responseStylePrompt: typeof payload === 'string' \? '' : payload\?\.responseStylePrompt/, 'send handler should pass response style prompts only to the request layer')
assert.match(page, /useBookStore/, 'conversation page should use the book store note deletion API')
assert.match(page, /await bookStore\.deleteNote\(target\.noteId\)/, 'delete handler should delete persisted notes by noteId')
assert.match(page, /window\.localStorage\.removeItem\(conversationStorageKey\(conversationId\)\)/, 'delete handler should clear the cached conversation payload')
assert.match(page, /card\.value = null/, 'delete handler should leave the page in the missing conversation state')

console.log('conversation page delete behavior ok')
