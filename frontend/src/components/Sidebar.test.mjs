import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const sidebar = readFileSync(resolve(currentDir, 'Sidebar.vue'), 'utf8')
const reader = readFileSync(resolve(currentDir, '../views/Reader.vue'), 'utf8')

assert.match(sidebar, /\.sidebar\s*\{[\s\S]*?width:\s*320px;/, 'sidebar component should be wider')
assert.match(reader, /\.reader-sidebar\s*\{[\s\S]*?width:\s*340px;/, 'reader layout should allocate more width to the tree')
assert.match(reader, /@media \(max-width: 1180px\)[\s\S]*?width:\s*300px;/, 'medium viewport sidebar should remain wider than before')

console.log('sidebar width ok')
