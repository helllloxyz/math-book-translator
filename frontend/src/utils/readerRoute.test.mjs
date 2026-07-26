import assert from 'node:assert/strict'
import { buildReaderItemQuery, findReaderLeafByRouteQuery } from './readerRoute.js'

const bookTree = [
  {
    id: 'dir:book',
    kind: 'directory',
    title: 'Book',
    children: [
      {
        id: 'chapter:42',
        kind: 'leaf',
        type: 'chapter',
        title: 'Orientations and Atlases',
        chapter_id: 42,
        chapter_index: '21.5',
        source_type: 'chapter_content',
        source_id: 'chapter:42'
      }
    ]
  }
]

const guideTree = [
  {
    id: 'dir:guide',
    kind: 'directory',
    title: 'Guides',
    children: [
      {
        id: 'guide:book:reading-path',
        kind: 'leaf',
        type: 'guide',
        title: 'Top-down reading path',
        filename: '01-reading-path.md',
        scope_type: 'book',
        scope_id: 'book',
        source_type: 'book_guide',
        source_id: 'guide:book:reading-path'
      },
      {
        id: 'learning:42',
        kind: 'leaf',
        type: 'learning',
        title: 'Orientations and Atlases',
        chapter_id: 42,
        chapter_index: '21.5',
        source_type: 'chapter_learning',
        source_id: 'learning:42'
      }
    ]
  }
]

assert.deepEqual(
  buildReaderItemQuery(bookTree[0].children[0]),
  {
    reader_type: 'chapter',
    chapter_id: '42'
  },
  'chapter reader URLs should include enough identity to distinguish book content'
)

assert.deepEqual(
  buildReaderItemQuery(guideTree[0].children[0]),
  {
    reader_type: 'guide',
    guide_id: 'guide:book:reading-path'
  },
  'guide reader URLs should use the guide id instead of the storage filename'
)

assert.equal(
  findReaderLeafByRouteQuery(bookTree, guideTree, {
    reader_type: 'guide',
    guide_id: 'guide:book:reading-path'
  })?.id,
  'guide:book:reading-path',
  'route query should resolve guide items by explicit guide id'
)

assert.equal(
  findReaderLeafByRouteQuery(bookTree, guideTree, {
    reader_type: 'learning',
    chapter_id: '42'
  })?.id,
  'learning:42',
  'route query should resolve learning items by reader type and chapter id'
)

console.log('reader route query behavior ok')
