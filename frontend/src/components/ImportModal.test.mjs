import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'ImportModal.vue'), 'utf8')

assert.match(source, /preflightWarning/, 'ImportModal should render preflight warning details')
assert.match(source, /outlineReview/, 'ImportModal should render outline confirmation details')
assert.match(source, /确认章节结构/, 'ImportModal should label the outline confirmation view')
assert.match(source, /confirm-outline/, 'ImportModal should emit confirmed outline selections')
assert.match(source, /cancel-outline/, 'ImportModal should emit outline cancellation')
assert.match(source, /importDepth/, 'ImportModal should track confirmed import depth')
assert.match(source, /splitLevelById/, 'ImportModal should track per-heading split levels')
assert.match(source, /buildOutlinePlan/, 'ImportModal should emit a full outline plan')
assert.match(source, /setNodeSplitLevel/, 'ImportModal should let users change a node split level')
assert.match(source, />不切</, 'ImportModal should let users mark headings as non-split nodes')
assert.match(source, />删除</, 'ImportModal should let users delete headings from the confirmed outline')
assert.match(source, /deleted_heading_ids/, 'ImportModal should send deleted heading ids in the outline plan')
assert.match(source, /confirm-preflight/, 'ImportModal should emit a force confirmation event')
assert.match(source, /cancel-preflight/, 'ImportModal should emit a preflight cancellation event')
assert.match(source, /仍然导入/, 'ImportModal should offer a force import action for warnings')
assert.match(source, /检查导入警告/, 'ImportModal should render the import warning title in Chinese')
assert.match(source, /issue\.examples/, 'ImportModal should render issue examples separately')
assert.match(source, /chapterTypeSummary/, 'ImportModal should summarize detected chapter types')
assert.match(source, /content_type === 'exercise'/, 'ImportModal should highlight exercise chapters')
assert.match(source, /chapter-preview/, 'ImportModal should render the preflight chapter type preview')
assert.match(source, /chapter\.char_count/, 'ImportModal should show chapter character counts')
assert.match(source, /preflightWarning\?\.severity !== 'blocked'/, 'ImportModal should not offer force import for blocked preflight errors')
assert.match(source, /导入已阻止/, 'ImportModal should clearly label blocked preflight errors')
assert.match(source, /width:\s*min\(920px,\s*calc\(100vw - 2rem\)\)/, 'ImportModal should use a wider review layout')
assert.match(source, /full\.md/, 'ImportModal should explain directory imports prefer full.md')
assert.match(source, /activeTab === 'package'/, 'ImportModal should render a Package tab')
assert.match(source, /accept="\.zip,application\/zip"/, 'ImportModal package import should accept zip files')
assert.match(source, /import-package/, 'ImportModal should emit a package import event')
assert.doesNotMatch(source, /export-package|selectedExportBookId|Export Portable Package/, 'ImportModal should keep export out of the add-book flow')

console.log('ImportModal preflight warning UI ok')
