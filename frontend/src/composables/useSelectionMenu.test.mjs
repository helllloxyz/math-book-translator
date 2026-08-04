import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'useSelectionMenu.js'), 'utf8')
const latexCopy = readFileSync(resolve(currentDir, '../utils/latexCopy.js'), 'utf8')
const contextMenu = readFileSync(resolve(currentDir, '../components/ContextMenu.vue'), 'utf8')

assert.match(source, /handleCopy/, 'reader selections should override native copy text')
assert.match(source, /copySelectionAsLatex/, 'reader copy handler should use the shared LaTeX copy helper')
assert.match(latexCopy, /clipboardData\.setData\('text\/plain'/, 'copy helper should put restored LaTeX text on the clipboard')
assert.match(latexCopy, /katex-display/, 'display math should be detected separately from inline math')
assert.match(latexCopy, /\$\$\$\{annotation\.textContent\}\$\$/, 'display math should copy with $$ delimiters')
assert.match(latexCopy, /range\.cloneRange\(\)/, 'copy extraction should not mutate the visible browser selection')
assert.match(latexCopy, /closest\?\.\('\.katex'\)/, 'copy extraction should detect a selection endpoint inside rendered KaTeX')
assert.match(latexCopy, /copyRange\.setStartBefore\(startTarget\)/, 'copy extraction should include the full formula when selection starts inside KaTeX')
assert.match(latexCopy, /copyRange\.setEndAfter\(endTarget\)/, 'copy extraction should include the full formula when selection ends inside KaTeX')
assert.match(source, /selectedContentTarget/, 'selection menu should preserve whether the selection came from source or translated content')
assert.match(source, /event\.ctrlKey[\s\S]*event\.key !== 'q'[\s\S]*menuVisible\.value = true/, 'Ctrl+Q should pop the selection menu')
assert.doesNotMatch(source, /onAction\('chat'/, 'Ctrl+Q should not skip the menu and start chat directly')
assert.doesNotMatch(source, /addEventListener\('(mouse|pointer)up'/, 'reader selections should not automatically pop a menu when the pointer is released')
assert.doesNotMatch(source, /addEventListener\('selectionchange'/, 'selection changes should wait for the explicit Ctrl+Q command')
assert.match(source, /selectionAnchorForRoot/, 'selection menu should capture a stable text offset for persisted annotations')
assert.match(source, /data-reader-annotation-id/, 'clicking an existing annotation should reopen its management action')
assert.match(source, /below \+ 52 <= window\.innerHeight/, 'selection menu should flip above selections near the viewport bottom')
assert.match(source, /closest\('\.mermaid, svg'\)/, 'SVG diagram text should not be wrapped in HTML annotation marks')
assert.match(source, /onAction\('chapter-note', '', \{ contentTarget: 'translated' \}\)/, 'Ctrl+Q without a selection should open a whole-chapter question')
assert.match(contextMenu, /handleAction\('chapter-note'\).*章节提问/, 'selection menu should offer a whole-chapter question mode')
assert.match(contextMenu, /handleAction\('selection-note'\).*选中提问/, 'selection menu should offer a selection-only question mode')
assert.match(contextMenu, /handleAction\('annotation-highlight'\)/, 'selection menu should offer a yellow highlight action')
assert.match(contextMenu, /handleAction\('annotation-underline'\)/, 'selection menu should offer an underline action')
assert.match(contextMenu, /handleAction\('annotation-remove'\)/, 'existing annotations should be removable from the same menu')
assert.match(contextMenu, /handleAction\('annotation-note'\)/, 'existing annotations should be usable as the source for a written note')

console.log('selection menu LaTeX copy behavior ok')
