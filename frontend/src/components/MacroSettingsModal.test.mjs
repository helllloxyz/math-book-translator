import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'MacroSettingsModal.vue'), 'utf8')

assert.match(source, /Response Styles/, 'modal should present response style configuration')
assert.match(source, /apiClient\.get\('\/settings\/conversation-styles'\)/, 'modal should load styles from the backend settings API')
assert.match(source, /apiClient\.put\('\/settings\/conversation-styles'/, 'modal should save styles through the backend settings API')
assert.match(source, /v-model="style\.id"/, 'modal should allow editing style ids')
assert.match(source, /v-model="style\.label"/, 'modal should allow editing style labels')
assert.match(source, /v-model="style\.description"/, 'modal should allow editing style descriptions')
assert.match(source, /v-model="style\.prompt"/, 'modal should allow editing style prompts')
assert.doesNotMatch(source, /localStorage|prompt_macros|Prompt Macros|Add Macro|Save Macros/, 'modal should not use legacy prompt macro behavior')

console.log('response style modal behavior ok')
