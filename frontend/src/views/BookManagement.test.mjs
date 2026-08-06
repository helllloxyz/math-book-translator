import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'BookManagement.vue'), 'utf8')
const learningSource = readFileSync(resolve(currentDir, 'BookLearning.vue'), 'utf8')
const storeSource = readFileSync(resolve(currentDir, '../stores/bookStore.js'), 'utf8')
const routerSource = readFileSync(resolve(currentDir, '../router/index.js'), 'utf8')

assert.match(routerSource, /name:\s*'book-management'/, 'router should expose the book management page')
assert.match(source, /aria-label="内容状态与维护"/, 'management page should retain an accessible content-maintenance section')
assert.match(source, /章节概览/, 'management page should include chapter-level state')
assert.doesNotMatch(source, /id="quiz"|id="profile"/, 'content status page should not retain learning sections')
assert.match(learningSource, /id="quiz"/, 'learning page should include quiz evaluation')
assert.match(learningSource, /id="profile"/, 'learning page should include the learning profile')
assert.match(routerSource, /name:\s*'book-learning'/, 'router should expose the learning workspace')
assert.match(source, /chapter_guides_stale/, 'management page should distinguish stale guides')
assert.match(source, /requestChapterRetranslation/, 'management page should confirm chapter retranslation')
assert.match(source, /target="_blank"/, 'chapter reader links should open in a new tab')
assert.match(source, /generateChapterGuide/, 'management page should offer chapter-level guide generation')
assert.match(source, /重新生成全书导读/, 'management page should contain full-book guide regeneration')
assert.match(source, /消耗较多 Token/, 'full-book regeneration should warn about model cost before starting')
assert.match(source, /confirmation\.kind === 'guides'/, 'full-book regeneration should require an explicit confirmation')
assert.match(source, /Loading|正在加载/, 'management page should provide a loading state')
assert.match(source, /management-error/, 'management page should provide an error state')
assert.match(source, /filteredChapters\.length/, 'management page should provide a filtered empty state')
assert.match(storeSource, /async fetchBookManagement\(id\)/, 'book store should fetch the management snapshot')
assert.match(storeSource, /async retranslateChapter\(bookId, chapterId\)/, 'book store should expose chapter retranslation')
assert.match(storeSource, /async generateChapterGuide\(bookId, chapterId\)/, 'book store should expose chapter guide generation')
assert.match(learningSource, /selectBookQuizTarget/, 'learning page should start a full-book quiz')
assert.match(learningSource, /analyzeLearningProfile/, 'learning page should update the learning profile')
assert.match(learningSource, /v-html="profileHtml"/, 'learning page should render the profile document')

console.log('Book management page wiring ok')
