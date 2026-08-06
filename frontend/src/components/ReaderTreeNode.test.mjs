import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const component = readFileSync(resolve(currentDir, 'ReaderTreeNode.vue'), 'utf8')

assert.match(component, /class="leaf-marker"/, 'leaf rows should render a marker before article titles for alignment')
assert.doesNotMatch(component, /class="leaf-marker"[^>]*>-</, 'leaf rows should not use a dash marker before article titles')
assert.match(component, /visibleLabel/, 'tree nodes should compute whether the label is worth showing')
assert.match(component, /titleText/, 'tree nodes should compare labels against plain title text')
assert.match(component, /renderedDisplayTitle/, 'tree nodes should render the numeric label and title as one title run')
assert.doesNotMatch(component, /class="item-label"/, 'tree rows should not style numeric labels separately from titles')
assert.match(component, /const expanded = ref\(false\)/, 'directory rows should start collapsed after import/load')
assert.match(component, /containsCurrentItem/, 'tree nodes should detect whether they contain the active chapter')
assert.match(component, /if \(containsCurrent\) expanded\.value = true/, 'the active chapter directory path should expand automatically')
assert.match(component, /scrollIntoView/, 'the restored chapter should be brought into the visible table of contents')
assert.doesNotMatch(component, /\.directory-row\s*\{[^}]*font-weight:\s*700/, 'directory rows should not be bold by default')
assert.match(component, /\.disclosure\s*\{[^}]*font-size:\s*1\.1rem/, 'directory disclosure marker should be visually larger')

console.log('reader tree label cleanup ok')
