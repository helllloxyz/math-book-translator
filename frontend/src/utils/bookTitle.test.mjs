import assert from 'node:assert/strict'
import { formatLibraryBookTitle } from './bookTitle.js'

assert.equal(
  formatLibraryBookTitle('MinerU_markdown_202604301644866.md'),
  'MinerU Markdown',
  'generated filenames should read like book titles'
)
assert.equal(
  formatLibraryBookTitle('manifold — part 1'),
  'manifold — part 1',
  'intentional book title punctuation and casing should be preserved'
)
assert.equal(
  formatLibraryBookTitle('流形_导论_20260802123000'),
  '流形 导论',
  'generated timestamps and underscores should be removed from Chinese titles'
)
assert.equal(formatLibraryBookTitle(''), '未命名图书', 'empty titles should have a stable fallback')

console.log('Library book title formatting ok')
