import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'useSelectionMenu.js'), 'utf8')
const latexCopy = readFileSync(resolve(currentDir, '../utils/latexCopy.js'), 'utf8')

assert.match(source, /handleCopy/, 'reader selections should override native copy text')
assert.match(source, /copySelectionAsLatex/, 'reader copy handler should use the shared LaTeX copy helper')
assert.match(latexCopy, /clipboardData\.setData\('text\/plain'/, 'copy helper should put restored LaTeX text on the clipboard')
assert.match(latexCopy, /katex-display/, 'display math should be detected separately from inline math')
assert.match(latexCopy, /\$\$\$\{annotation\.textContent\}\$\$/, 'display math should copy with $$ delimiters')
assert.match(source, /selectedContentTarget/, 'selection menu should preserve whether the selection came from source or translated content')
assert.match(source, /event\.ctrlKey[\s\S]*event\.key !== 'q'[\s\S]*menuVisible\.value = true/, 'Ctrl+Q should pop the selection menu')
assert.doesNotMatch(source, /onAction\('chat'/, 'Ctrl+Q should not skip the menu and start chat directly')
assert.doesNotMatch(source, /addEventListener\('mouseup'/, 'reader selections should not automatically pop a menu on mouseup')

console.log('selection menu LaTeX copy behavior ok')
