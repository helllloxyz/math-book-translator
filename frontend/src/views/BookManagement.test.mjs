import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'BookManagement.vue'), 'utf8')
const storeSource = readFileSync(resolve(currentDir, '../stores/bookStore.js'), 'utf8')
const routerSource = readFileSync(resolve(currentDir, '../router/index.js'), 'utf8')

assert.match(routerSource, /name:\s*'book-management'/, 'router should expose the book management page')
assert.match(source, /aria-label="内容状态与维护"/, 'management page should retain an accessible content-maintenance section')
assert.match(source, /章节概览/, 'management page should include chapter-level state')
assert.match(source, /Quiz 评估/, 'management page should include quiz evaluation')
assert.match(source, /学习画像/, 'management page should include the learning profile')
assert.match(source, /chapter_guides_stale/, 'management page should distinguish stale guides')
assert.match(source, /requestChapterRetranslation/, 'management page should confirm chapter retranslation')
assert.match(source, /target="_blank"/, 'chapter reader links should open in a new tab')
assert.match(source, /generateChapterGuide/, 'management page should offer chapter-level guide generation')
assert.match(source, /Loading|正在加载/, 'management page should provide a loading state')
assert.match(source, /management-error/, 'management page should provide an error state')
assert.match(source, /filteredChapters\.length/, 'management page should provide a filtered empty state')
assert.match(storeSource, /async fetchBookManagement\(id\)/, 'book store should fetch the management snapshot')
assert.match(storeSource, /async retranslateChapter\(bookId, chapterId\)/, 'book store should expose chapter retranslation')
assert.match(storeSource, /async generateChapterGuide\(bookId, chapterId\)/, 'book store should expose chapter guide generation')

console.log('Book management page wiring ok')
