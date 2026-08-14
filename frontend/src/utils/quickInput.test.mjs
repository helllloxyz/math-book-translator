import assert from 'node:assert/strict'
import { appendQuickInputText } from './quickInput.js'

assert.equal(
  appendQuickInputText('请解释这个证明', '请先给结论。'),
  '请解释这个证明\n\n请先给结论。',
  'a quick input should be appended after the current prompt'
)
assert.equal(
  appendQuickInputText('', '请先给结论。'),
  '请先给结论。',
  'an empty composer should receive only the quick input text'
)
assert.equal(
  appendQuickInputText('原内容  ', '  补充内容  '),
  '原内容\n\n补充内容',
  'quick input insertion should use one clean paragraph break'
)

console.log('quick input behavior ok')
