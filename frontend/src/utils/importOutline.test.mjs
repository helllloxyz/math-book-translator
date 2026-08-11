import assert from 'node:assert/strict'
import {
  filterCollapsedImportOutlineRows,
  importOutlineGroupChildCount,
  importOutlineLevelOneGroups,
  importOutlineNodeLevel
} from './importOutline.js'

const nodes = [
  { id: 'preface', level: 1, title: 'Preface' },
  { id: 'chapter-1', level: 1, title: 'Chapter 1' },
  { id: 'section-1-1', level: 2, title: 'Section 1.1' },
  { id: 'section-1-2', level: 2, title: 'Section 1.2' },
  { id: 'chapter-2', level: 1, title: 'Chapter 2' },
  { id: 'section-2-1', level: 2, title: 'Section 2.1' },
  { id: 'detail-2-1-1', level: 3, title: 'Detail 2.1.1' }
]

assert.equal(importOutlineNodeLevel(nodes[2], {}), 2)
assert.equal(importOutlineNodeLevel(nodes[2], { 'section-1-1': 1 }), 1)
assert.equal(importOutlineNodeLevel(nodes[2], { 'section-1-1': 'delete' }), 2)
assert.equal(importOutlineGroupChildCount(nodes, 1), 2)
assert.equal(importOutlineGroupChildCount(nodes, 4), 2)
assert.deepEqual(importOutlineLevelOneGroups(nodes).map((node) => node.id), ['chapter-1', 'chapter-2'])

assert.deepEqual(
  filterCollapsedImportOutlineRows(nodes, new Set(['chapter-1'])).map((node) => node.id),
  ['preface', 'chapter-1', 'chapter-2', 'section-2-1', 'detail-2-1-1'],
  'collapsing an L1 heading should hide descendants only until the next L1 heading'
)

assert.deepEqual(
  filterCollapsedImportOutlineRows(nodes, new Set(['chapter-1', 'chapter-2'])).map((node) => node.id),
  ['preface', 'chapter-1', 'chapter-2'],
  'all L1 groups should be collapsible together'
)

const changedLevels = { 'section-1-2': 1 }
assert.equal(importOutlineGroupChildCount(nodes, 1, changedLevels), 1)
assert.deepEqual(
  filterCollapsedImportOutlineRows(nodes, new Set(['chapter-1']), changedLevels).map((node) => node.id),
  ['preface', 'chapter-1', 'section-1-2', 'chapter-2', 'section-2-1', 'detail-2-1-1'],
  'confirmed split-level edits should immediately redefine L1 group boundaries'
)

console.log('import outline folding utilities ok')
