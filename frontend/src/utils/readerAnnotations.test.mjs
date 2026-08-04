import assert from 'node:assert/strict'
import { findClosestTextIndex, parseReaderAnnotation } from './readerAnnotations.js'

const repeatedText = '定义一在这里。中间内容。定义一在这里。'
assert.equal(
  findClosestTextIndex(repeatedText, '定义一', 12),
  12,
  'saved offsets should distinguish repeated phrases'
)
assert.equal(
  findClosestTextIndex(repeatedText, '定义一', 10),
  12,
  'a shifted offset should fall back to the nearest matching phrase'
)
assert.equal(findClosestTextIndex(repeatedText, '不存在', 0), -1)

assert.deepEqual(
  parseReaderAnnotation({
    id: 8,
    selected_text: '紧致性',
    start_index: 27,
    note_content: JSON.stringify({ style: 'underline', content_target: 'raw' })
  }),
  {
    id: 8,
    selectedText: '紧致性',
    startIndex: 27,
    style: 'underline',
    contentTarget: 'raw'
  }
)

console.log('reader annotation persistence helpers ok')
