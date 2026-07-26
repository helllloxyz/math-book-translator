import assert from 'node:assert/strict'
import { appendWithTypewriter } from './typewriterStream.js'

const appended = []
const waits = []

await appendWithTypewriter(
  'abcdefghi',
  (chunk) => appended.push(chunk),
  {
    chunkSize: 3,
    intervalMs: 7,
    delay: async (ms) => waits.push(ms)
  }
)

assert.deepEqual(appended, ['abc', 'def', 'ghi'], 'large chunks should be split into small UI updates')
assert.equal(appended.join(''), 'abcdefghi', 'typewriter updates should preserve the full response')
assert.deepEqual(waits, [7, 7], 'typewriter should pause between visible updates but not after the last one')

const emptyAppended = []
await appendWithTypewriter('', (chunk) => emptyAppended.push(chunk), {
  delay: async () => {
    throw new Error('empty content should not wait')
  }
})

assert.deepEqual(emptyAppended, [], 'empty chunks should not trigger UI updates')

console.log('typewriter stream behavior ok')
