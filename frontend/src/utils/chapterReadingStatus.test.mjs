import assert from 'node:assert/strict'
import {
  defaultChapterReadingStatus,
  getChapterReadingStatus,
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
  difficulty: 'easy',
})

assert.deepEqual(
  getChapterReadingStatus(7, 23),
  { progress: 'unread', difficulty: 'easy' },
  'chapters should default to unread and easy before user choice'
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
  { progress: 'finished', difficulty: 'easy' },
  'invalid persisted values should fall back to defaults'
)

assert.equal(memory.has('math-book-reader-status:7:23'), true)

console.log('chapter reading status persistence ok')
