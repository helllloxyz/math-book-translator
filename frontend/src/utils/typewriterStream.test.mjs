import assert from 'node:assert/strict'
import { appendWithTypewriter, createTypewriterQueue } from './typewriterStream.js'

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

const streamedAppended = []
const streamedWaits = []
await appendWithTypewriter(
  'token',
  (chunk) => streamedAppended.push(chunk),
  {
    chunkSize: 6,
    intervalMs: 7,
    delayAfterLast: true,
    delay: async (ms) => streamedWaits.push(ms)
  }
)

assert.deepEqual(streamedAppended, ['token'], 'a short streamed chunk should still be displayed')
assert.deepEqual(streamedWaits, [7], 'streamed chunks should yield after their final visible update so Vue can paint it')

const queuedAppended = []
const queue = createTypewriterQueue(
  (chunk) => queuedAppended.push(chunk),
  {
    chunkSize: 2,
    intervalMs: 1,
    delay: async () => {}
  }
)
queue.enqueue('abc')
queue.enqueue('def')
await queue.flush()

assert.equal(queuedAppended.join(''), 'abcdef', 'queued stream chunks should retain all response text')
assert.deepEqual(queuedAppended, ['ab', 'cd', 'ef'], 'queued stream chunks should animate as one response instead of independently flushing each network chunk')

const emptyAppended = []
await appendWithTypewriter('', (chunk) => emptyAppended.push(chunk), {
  delay: async () => {
    throw new Error('empty content should not wait')
  }
})

assert.deepEqual(emptyAppended, [], 'empty chunks should not trigger UI updates')

console.log('typewriter stream behavior ok')
