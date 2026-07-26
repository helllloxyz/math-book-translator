import assert from 'node:assert/strict'
import {
  findAdjacentReaderLeaves,
  findChapterGuideLeaf,
  findReaderLeaf,
  findReaderLeafBySource,
  flattenReaderLeaves
} from './readerTree.js'

const tree = [
  {
    id: 'dir:1',
    kind: 'directory',
    title: 'Chapter 1',
    children: [
      {
        id: 'chapter:1',
        kind: 'leaf',
        type: 'chapter',
        title: 'Chapter 1 content',
        source_type: 'chapter_content',
        source_id: 'chapter:1'
      },
      {
        id: 'dir:1.1',
        kind: 'directory',
        title: 'c 1.1',
        children: [
          {
            id: 'guide:directory-1_1-overview.md',
            kind: 'leaf',
            type: 'guide',
            title: 'Directory guide for c 1.1',
            scope_type: 'directory',
            scope_id: '1.1',
            source_type: 'directory_guide',
            source_id: 'guide:directory:1.1:overview'
          },
          {
            id: 'guide:chapter-1_1-map.md',
            kind: 'leaf',
            type: 'guide',
            title: 'Guide for c 1.1',
            scope_type: 'chapter',
            scope_id: '1.1',
            source_type: 'chapter_guide',
            source_id: 'guide:chapter:1.1:map'
          },
          {
            id: 'learning:2',
            kind: 'leaf',
            type: 'learning',
            title: 'c 1.1',
            source_type: 'chapter_learning',
            source_id: 'learning:2'
          }
        ]
      }
    ]
  }
]

const leaves = flattenReaderLeaves(tree)

assert.equal(leaves.length, 4)
assert.deepEqual(
  leaves.map((leaf) => ({ id: leaf.id, depth: leaf.depth, parentTitles: leaf.parentTitles })),
  [
    { id: 'chapter:1', depth: 1, parentTitles: ['Chapter 1'] },
    { id: 'guide:directory-1_1-overview.md', depth: 2, parentTitles: ['Chapter 1', 'c 1.1'] },
    { id: 'guide:chapter-1_1-map.md', depth: 2, parentTitles: ['Chapter 1', 'c 1.1'] },
    { id: 'learning:2', depth: 2, parentTitles: ['Chapter 1', 'c 1.1'] }
  ]
)

assert.equal(findReaderLeaf(tree, 'learning:2')?.source_id, 'learning:2')
assert.equal(findReaderLeafBySource(tree, 'chapter_learning', 'learning:2')?.id, 'learning:2')
assert.equal(findChapterGuideLeaf(tree, '1.1')?.id, 'guide:chapter-1_1-map.md')
assert.equal(findChapterGuideLeaf(tree, '1.2'), null)
assert.equal(
  findChapterGuideLeaf([{ ...tree[0], children: [tree[0].children[0], { ...tree[0].children[1], children: [tree[0].children[1].children[0]] }] }], '1.1')?.id,
  'guide:directory-1_1-overview.md',
  'directory guide should be the fallback when a chapter guide is not present'
)
assert.equal(
  findChapterGuideLeaf([
    {
      id: 'dir:1.2',
      kind: 'directory',
      title: 'c 1.2',
      children: [
        {
          id: 'learning:3',
          kind: 'leaf',
          type: 'learning',
          title: 'c 1.2',
          chapter_id: 3,
          chapter_index: '1.2',
          source_type: 'chapter_learning',
          source_id: 'learning:3'
        }
      ]
    }
  ], '1.2')?.id,
  'learning:3',
  'chapter learning should be the fallback when no generated guide is present'
)
assert.equal(findReaderLeaf(tree, 'missing'), null)
assert.equal(findReaderLeafBySource(tree, 'chapter_learning', 'missing'), null)
assert.deepEqual(
  findAdjacentReaderLeaves(tree, 'chapter:1'),
  { previous: null, next: leaves[1] },
  'first leaf should link forward only'
)
assert.deepEqual(
  findAdjacentReaderLeaves(tree, 'learning:2'),
  { previous: leaves[2], next: null },
  'last leaf should link backward only'
)
assert.deepEqual(
  findAdjacentReaderLeaves(tree, 'missing'),
  { previous: null, next: null },
  'missing current item should not produce navigation'
)

console.log('readerTree utilities ok')
