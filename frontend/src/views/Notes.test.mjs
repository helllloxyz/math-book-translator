import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'Notes.vue'), 'utf8')
const noteCard = readFileSync(resolve(currentDir, '../components/NoteCard.vue'), 'utf8')

assert.match(source, /name: 'reader'/, 'Notes should provide a direct route back to the reader')
assert.match(source, /note_id: note\.id/, 'Notes should deep-link the selected note into the reader')
assert.match(source, /pendingDeleteNote/, 'Notes should use an in-app delete confirmation')
assert.match(noteCard, /emit\('open-source'\)/, 'Note cards should expose a return-to-source action')
assert.doesNotMatch(source, /\b(?:alert|confirm)\s*\(/, 'Notes should not use blocking browser dialogs')
assert.doesNotMatch(noteCard, /\bconfirm\s*\(/, 'Note cards should delegate confirmation to the page dialog')

console.log('notes source navigation and inline feedback ok')
