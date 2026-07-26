import assert from 'node:assert/strict'
import {
  extractImportPreflight,
  formatImportErrorMessage,
} from './importPreflight.js'

const blockedError = {
  response: {
    data: {
      detail: {
        message: 'Import blocked by preflight.',
        preflight: {
          severity: 'blocked',
          recommendation: '导入前请先拆分超长章节。',
          issues: [
            {
              code: 'chapter_too_large',
              message: 'Chapter 2 (Linear Maps) has 80001 characters, which exceeds the 80000 character limit.',
            },
          ],
        },
      },
    },
  },
}

assert.equal(
  extractImportPreflight(blockedError)?.issues?.[0]?.code,
  'chapter_too_large',
  'structured preflight details should be recoverable from HTTP errors',
)

const message = formatImportErrorMessage(blockedError)

assert.match(message, /导入前请先拆分超长章节。/, 'message should include the preflight recommendation')
assert.match(message, /Chapter 2 \(Linear Maps\)/, 'message should name the oversized chapter')
assert.match(message, /80001 characters/, 'message should include the oversized chapter length')

console.log('import preflight error formatting ok')
