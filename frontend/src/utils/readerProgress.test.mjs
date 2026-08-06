import assert from 'node:assert/strict'
import {
  getFurthestReadChapter,
  rememberFurthestReadChapter,
} from './readerProgress.js'

const memory = new Map()
globalThis.localStorage = {
  getItem: (key) => memory.get(key) ?? null,
  setItem: (key, value) => memory.set(key, value),
  removeItem: (key) => memory.delete(key),
}

const chapters = [
  {
    id: 'directory:1',
    kind: 'directory',
    title: 'Part I',
    children: [
      { id: 'chapter:11', kind: 'leaf', type: 'chapter', chapter_id: 11, title: 'Opening' },
      {
        id: 'directory:1.1',
        kind: 'directory',
        title: 'Foundations',
        children: [
          { id: 'chapter:12', kind: 'leaf', type: 'chapter', chapter_id: 12, title: 'Definitions' },
          { id: 'chapter:13', kind: 'leaf', type: 'chapter', chapter_id: 13, title: 'Theorem' },
        ]
      }
    ]
  }
]

const [first, second, third] = [
  chapters[0].children[0],
  chapters[0].children[1].children[0],
  chapters[0].children[1].children[1],
]

assert.equal(getFurthestReadChapter(7, chapters), null, 'a book without saved progress should not restore a chapter')

rememberFurthestReadChapter(7, chapters, second)
assert.equal(
  getFurthestReadChapter(7, chapters)?.id,
  second.id,
  'opening a chapter should save it as the furthest reading position'
)

rememberFurthestReadChapter(7, chapters, first)
assert.equal(
  getFurthestReadChapter(7, chapters)?.id,
  second.id,
  'opening an earlier chapter for review should not move reading progress backward'
)

rememberFurthestReadChapter(7, chapters, third)
assert.equal(
  getFurthestReadChapter(7, chapters)?.id,
  third.id,
  'opening a later chapter should advance reading progress'
)

rememberFurthestReadChapter(7, chapters, { id: 'guide:1', kind: 'leaf', type: 'guide' })
assert.equal(
  getFurthestReadChapter(7, chapters)?.id,
  third.id,
  'opening generated guides should not replace chapter reading progress'
)

assert.equal(getFurthestReadChapter(8, chapters), null, 'reading progress should be isolated by book')

memory.set('math-book-reader-progress:9', '{broken json')
assert.equal(getFurthestReadChapter(9, chapters), null, 'invalid cached progress should fail safely')

console.log('furthest reader chapter persistence ok')
