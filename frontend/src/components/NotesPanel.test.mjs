import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const component = readFileSync(resolve(currentDir, 'NotesPanel.vue'), 'utf8')

assert.match(component, /class="note-symbol"/, 'notes should use a leading symbol to distinguish note types')
assert.match(component, /noteTypeSymbol/, 'notes should compute a symbol for chapter vs selection notes')
assert.doesNotMatch(component, /scope-label/, 'notes should only show symbol plus summary, without type label text')
assert.doesNotMatch(component, /noteTypeLabel/, 'notes should not compute visible type labels')
assert.doesNotMatch(component, /class="bookmark-strip"/, 'notes should not use a top strip inside each bookmark')
assert.doesNotMatch(component, /class="source-title"/, 'notes should not repeat the current chapter/source title')
assert.doesNotMatch(component, /background:\s*var\(--bookmark-fill\)/, 'note text should not be placed inside a nested inner chip')
assert.match(component, /background:\s*var\(--bookmark-active-bg\)/, 'whole bookmark card should carry the note type color')
assert.match(component, /\.note-index-card\.active\s*\{[\s\S]*?background:\s*var\(--bookmark-accent\);/, 'selected note button should use the stronger accent background')
assert.match(component, /\.note-index-card\.active strong\s*\{[\s\S]*?color:\s*#ffffff;/, 'selected note text should have high contrast')
assert.match(component, /gap:\s*10px;/, 'bookmark spacing should separate notes without nested decoration')
assert.match(component, /\.note-index-card strong\s*\{[\s\S]*?font-size:\s*14px;/, 'note summaries should use a larger font')
assert.doesNotMatch(component, /-webkit-line-clamp/, 'note card height should follow the actual summary line count')
assert.doesNotMatch(component, /min-height:\s*56px/, 'note cards should not force a fixed minimum height')

console.log('notes panel simplified style ok')
