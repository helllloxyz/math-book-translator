import assert from 'node:assert/strict'
import {
  defaultChapterReadingStatus,
  getChapterReadingStatus,
  getBookChapterReadingStatuses,
  setChapterReadingStatus,
} from './chapterReadingStatus.js'

const memory = new Map()
globalThis.localStorage = {
  getItem: (key) => memory.get(key) ?? null,
  setItem: (key, value) => memory.set(key, value),
  removeItem: (key) => memory.delete(key),
}

assert.deepEqual(defaultChapterReadingStatus(), {
  progress: 'unread',
  difficulty: 'unmarked',
})

assert.deepEqual(
  getChapterReadingStatus(7, 23),
  { progress: 'unread', difficulty: 'unmarked' },
  'chapters should default to unread and unmarked before user choice'
)

setChapterReadingStatus(7, 23, { progress: 'reading', difficulty: 'confused' })
assert.deepEqual(
  getChapterReadingStatus(7, 23),
  { progress: 'reading', difficulty: 'confused' },
  'chapter status should persist by book and chapter id'
)

setChapterReadingStatus(7, 23, { progress: 'finished', difficulty: 'unknown' })
assert.deepEqual(
  getChapterReadingStatus(7, 23),
  { progress: 'finished', difficulty: 'unmarked' },
  'invalid persisted values should fall back to defaults'
)

memory.set('math-book-reader-status:7:24', JSON.stringify({ progress: 'reading', difficulty: 'easy' }))
assert.deepEqual(
  getChapterReadingStatus(7, 24),
  { progress: 'reading', difficulty: 'unmarked' },
  'legacy easy values should migrate to unmarked'
)

const bookTree = [{
  kind: 'branch',
  title: 'Part I',
  children: [
    { kind: 'leaf', type: 'chapter', chapter_id: 23 },
    { kind: 'leaf', type: 'chapter', chapter_id: 24 },
  ]
}]
assert.deepEqual(getBookChapterReadingStatuses(7, bookTree), [
  { chapter_id: 23, progress: 'finished', difficulty: 'unmarked' },
  { chapter_id: 24, progress: 'reading', difficulty: 'unmarked' },
])

assert.equal(memory.has('math-book-reader-status:7:23'), true)

console.log('chapter reading status persistence ok')
