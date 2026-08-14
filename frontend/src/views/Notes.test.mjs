import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'Notes.vue'), 'utf8')
const noteCard = readFileSync(resolve(currentDir, '../components/NoteCard.vue'), 'utf8')
const annotationCard = readFileSync(resolve(currentDir, '../components/AnnotationCard.vue'), 'utf8')

assert.match(source, /name: 'reader'/, 'Notes should provide a direct route back to the reader')
assert.match(source, /note_id: note\.id/, 'Notes should deep-link the selected note into the reader')
assert.match(source, /window\.open\(sourceRoute\.href, '_blank', 'noopener,noreferrer'\)/, 'source links should open safely in a new tab')
assert.match(source, /pendingDeleteNote/, 'Notes should use an in-app delete confirmation')
assert.match(source, /NOTE_CATEGORIES/, 'Notes should render separate categories for notes, Quiz, and marks')
assert.match(source, /notesInCategory/, 'Notes should filter records by the active category')
assert.match(source, /route\.query\.tab/, 'Notes should preserve the selected category in the URL')
assert.match(source, /note\.type === 'annotation'/, 'Reader annotations should use their dedicated card')
assert.match(noteCard, /emit\('open-source'\)/, 'Note cards should expose a return-to-source action')
assert.match(noteCard, /v-if="note\.created_at"/, 'Note cards should show their date while collapsed')
assert.doesNotMatch(noteCard, /note\.created_at && !isCollapsed/, 'collapsed notes should not hide their date')
assert.match(noteCard, /aria-label="在新标签页打开原文"/, 'note source icon should have an accessible label')
assert.match(annotationCard, /aria-label="在新标签页打开原文"/, 'annotation source icon should have an accessible label')
assert.doesNotMatch(noteCard, />返回原文<\/button>/, 'note source action should use an icon instead of visible text')
assert.doesNotMatch(annotationCard, />返回原文<\/button>/, 'annotation source action should use an icon instead of visible text')
assert.doesNotMatch(source, /\b(?:alert|confirm)\s*\(/, 'Notes should not use blocking browser dialogs')
assert.doesNotMatch(noteCard, /\bconfirm\s*\(/, 'Note cards should delegate confirmation to the page dialog')

console.log('notes source navigation and inline feedback ok')
