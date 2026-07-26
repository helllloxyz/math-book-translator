import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'Library.vue'), 'utf8')
const storeSource = readFileSync(resolve(currentDir, '../stores/bookStore.js'), 'utf8')

assert.match(source, />\s*Response Styles\s*</, 'Library toolbar should expose response styles, not macros')
assert.match(source, /title="Response Styles"/, 'Library response style button should have the correct title')
assert.doesNotMatch(source, /Macros saved|Prompt Macros|>\s*Macros\s*</, 'Library should not present legacy prompt macro language')
assert.match(source, /preflightWarning/, 'Library should track import preflight warnings')
assert.match(source, /outlineReview/, 'Library should track import outline confirmation')
assert.match(source, /confirmOutlineImport/, 'Library should confirm user-selected outline split points')
assert.match(source, /outlinePlan/, 'Library should preserve the confirmed outline plan across preflight confirmation')
assert.match(storeSource, /outline_plan/, 'Book store should send outline plans to the backend')
assert.match(source, /confirmPreflightImport/, 'Library should provide a force-import confirmation handler')
assert.match(source, /force:\s*true/, 'Library should retry imports with force after confirmation')
assert.match(source, /Analyze Learning Profile/, 'Library should expose learning profile analysis')
assert.match(source, /View Learning Profile/, 'Library should expose a learning profile viewer for each book')
assert.match(source, /@click="openLearningProfile\(book\)"/, 'Profile viewer button should open the selected book profile')
assert.match(source, /showProfileModal/, 'Library should keep modal state for the learning profile')
assert.match(source, /Loading learning profile\.\.\./, 'Learning profile modal should include a loading state')
assert.match(source, /profileError/, 'Learning profile modal should include an error state')
assert.match(source, /v-html="profileHtml"/, 'Learning profile modal should render markdown content')
assert.match(source, /fetchLearningProfile\(book\.id\)/, 'Library should fetch profile markdown when opening the viewer')
assert.match(source, /profile_markdown/, 'Analyze should make updated profile markdown available after analysis')
assert.match(storeSource, /async fetchLearningProfile\(bookId\)/, 'Book store should expose learning profile fetch action')
assert.match(storeSource, /`\/books\/\$\{bookId\}\/quiz\/profile`/, 'Book store should call the profile markdown endpoint')
assert.match(source, /Book Quiz/, 'Library should expose Book Quiz')
assert.match(source, /你最近有新的笔记和 Quiz 记录，可以分析生成学习画像。/, 'Library should show the learning profile hint')
assert.match(source, /selectBookQuizTarget/, 'Book Quiz should call the target selection API')

console.log('Library response style entry point ok')
