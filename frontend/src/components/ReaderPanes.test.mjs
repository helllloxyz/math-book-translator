import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const component = readFileSync(resolve(currentDir, 'ReaderPanes.vue'), 'utf8')

assert.doesNotMatch(component, /English Source/, 'dual source pane should not show a visible English Source label')
assert.doesNotMatch(component, /Chinese Translation/, 'dual target pane should not show a visible Chinese Translation label')
assert.doesNotMatch(component, /Reading Mode/, 'single pane should not show a visible Reading Mode label')
assert.match(component, /previousItem/, 'reader panes should accept previous item navigation data')
assert.match(component, /nextItem/, 'reader panes should accept next item navigation data')
assert.match(component, /go-previous/, 'reader panes should emit previous navigation')
assert.match(component, /go-next/, 'reader panes should emit next navigation')
assert.match(component, /const translatedOrSourceHtml = computed/, 'reader panes should centralize translated-or-source fallback')
assert.match(component, /const isSelectedGuideDual = computed/, 'guide dual should distinguish a selected guide from a selected chapter')
assert.match(component, /\['guide', 'learning'\]\.includes\(props\.currentItem\?\.type\)/, 'guide dual should treat selected learning like selected guide content')
assert.match(component, /isSelectedGuideDual\.value \? props\.renderedSource : translatedOrSourceHtml\.value/, 'selected guide dual left pane should show chapter content')
assert.match(component, /isSelectedGuideDual\.value \? translatedOrSourceHtml\.value : props\.renderedGuide/, 'selected guide dual right pane should show the selected guide content')

console.log('reader panes navigation chrome ok')
