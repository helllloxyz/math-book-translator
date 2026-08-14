import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'QuickInputSettingsModal.vue'), 'utf8')

assert.match(source, /<h2>快捷输入<\/h2>/, 'modal should present localized quick-input configuration')
assert.match(source, /追加到当前输入/, 'modal should explain that buttons append visible composer text')
assert.match(source, /保留在对话记录中/, 'modal should explain that inserted text remains in history')
assert.match(source, /apiClient\.get\('\/settings\/quick-inputs'\)/, 'modal should load quick inputs from the backend settings API')
assert.match(source, /apiClient\.put\('\/settings\/quick-inputs'/, 'modal should save quick inputs through the backend settings API')
assert.match(source, /v-model="quickInput\.id"/, 'modal should allow editing quick-input ids')
assert.match(source, /v-model="quickInput\.label"/, 'modal should allow editing quick-input labels')
assert.match(source, /v-model="quickInput\.prompt"/, 'modal should allow editing inserted text')

console.log('quick input modal behavior ok')
