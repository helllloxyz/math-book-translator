import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(resolve(currentDir, 'SettingsModal.vue'), 'utf8')
const providerOptions = JSON.parse(
  readFileSync(resolve(currentDir, '../../../config/llm_provider_options.json'), 'utf8')
)

assert.match(source, /FIXED_PROVIDER_IDS = \['openai', 'deepseek', 'gemini', 'anthropic'\]/, 'fixed provider entries should stay outside the folded group')
assert.match(source, /COMPATIBLE_PROVIDER_IDS = \['kimi', 'qwen', 'glm', 'minimax', 'openrouter'\]/, 'folded provider entries should be limited to OpenAI-compatible extras')
assert.match(source, /label: 'OpenAI Compatible'/, 'sidebar should expose one folded OpenAI-compatible entry')
assert.match(source, /v-for="provider in providerNavigation"/, 'sidebar should render provider navigation entries instead of the raw catalog')
assert.match(source, /v-if="isCompatiblePanel" class="form-group"/, 'provider dropdown should only render inside the folded panel')
assert.match(source, /v-for="provider in compatibleProviders"/, 'folded panel dropdown should only render compatible providers')
assert.doesNotMatch(source, /providerCatalog\.value\[0\]\?\.provider_id/, 'empty settings should not auto-select the first catalog provider')
assert.match(source, /const configuredProviderIds = new Set/, 'default model options should be built from configured credentials and drafts only')
assert.match(source, /if \(!configuredProviderIds\.has\(provider\.provider_id\)\) return/, 'unconfigured provider catalog models should not be selectable defaults')
assert.match(source, /availableProfileKeys\.has\(selections\.default\)/, 'stale default profile selections should reset when the configured provider changes')
assert.match(source, /credentials\.value = upsertCredentialSummary/, 'saving a credential should immediately update configured provider state')
assert.match(source, /const defaultProviderId = profiles\.default\?\.provider_id/, 'loading settings should validate the saved default provider before selecting it')
assert.match(source, /credentialForProviderId\(defaultProviderId\) \? defaultProviderId : providerIdFromCredential/, 'stale defaults should fall back to the first configured credential in the provider form')

const catalog = providerOptions.provider_catalog
const byId = new Map(catalog.map((provider) => [provider.provider_id, provider]))
const foldedIds = ['kimi', 'qwen', 'glm', 'minimax', 'openrouter']

assert.deepEqual(
  ['openai', 'deepseek', 'gemini', 'anthropic'].map((providerId) => byId.get(providerId)?.label),
  ['OpenAI', 'DeepSeek', 'Google Gemini', 'Anthropic'],
  'catalog should include the four fixed provider labels'
)
assert.deepEqual(
  foldedIds.map((providerId) => byId.get(providerId)?.label),
  ['Moonshot Kimi', 'Aliyun Qwen', 'Zhipu GLM', 'MiniMax', 'OpenRouter'],
  'catalog should include exactly the intended folded provider labels'
)
assert.equal(foldedIds.includes('openai'), false, 'OpenAI should not be folded')
assert.equal(foldedIds.includes('deepseek'), false, 'DeepSeek should not be folded')

console.log('settings modal provider folding ok')
