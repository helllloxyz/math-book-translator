import assert from 'node:assert/strict'
import {
  annotationStyle,
  noteCategory,
  noteCategoryCounts,
  normalizeNoteCategory,
  notesInCategory
} from './noteCategories.js'

const records = [
  { id: 1, type: 'custom_note' },
  { id: 2, type: 'selection_chat' },
  { id: 3, type: 'quiz_chat' },
  { id: 4, type: 'annotation', note_content: '{"style":"underline"}' }
]

assert.equal(noteCategory(records[0]), 'notes')
assert.equal(noteCategory(records[2]), 'quiz')
assert.equal(noteCategory(records[3]), 'marks')
assert.deepEqual(noteCategoryCounts(records), { notes: 2, quiz: 1, marks: 1 })
assert.deepEqual(notesInCategory(records, 'quiz').map(note => note.id), [3])
assert.equal(normalizeNoteCategory('unknown'), 'notes')
assert.equal(annotationStyle(records[3]), 'underline')
assert.equal(annotationStyle({ note_content: 'invalid json' }), 'highlight')

console.log('note categories and annotation metadata ok')
