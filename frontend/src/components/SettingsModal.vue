<template>
  <div v-if="show" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content card">
      <div class="modal-header">
        <div>
          <p class="modal-kicker">Workspace</p>
          <h2>Application Settings</h2>
        </div>
        <button class="close-btn" @click="$emit('close')" title="Close">×</button>
      </div>
      
      <div class="modal-body">
        <form @submit.prevent="saveSettings" class="settings-form">
          <section class="storage-strip">
            <div class="field-heading">
              <label>Default Storage Path</label>
              <small>Server-side book, translation, learning, and guide files.</small>
            </div>
            <input
              type="text"
              v-model="settings.storagePath"
              placeholder="e.g. ./storage"
              class="modal-input"
            />
          </section>

          <section class="settings-grid">
            <aside class="task-panel">
              <div class="section-label">Model Provider</div>
              <button
                v-for="provider in providerNavigation"
                :key="provider.id"
                type="button"
                class="task-button"
                :class="{ active: activeSection === 'providers' && activeProviderEntryId === provider.id }"
                @click="selectProviderEntry(provider.id)"
              >
                <span>{{ provider.label }}</span>
                <span class="mini-state" :class="{ configured: provider.configured }">
                  {{ provider.configured ? 'set' : 'none' }}
                </span>
              </button>

              <div class="sidebar-divider"></div>

              <button
                type="button"
                class="task-button default-options-button"
                :class="{ active: activeSection === 'defaults' }"
                @click="activeSection = 'defaults'"
              >
                <span>Default Options</span>
                <span class="mini-state configured">map</span>
              </button>
            </aside>

            <div class="settings-stack">
            <div v-if="activeSection === 'providers'" class="provider-panel">
              <div class="panel-title-row">
                <div>
                  <div class="section-label">Provider Profile</div>
                  <p>{{ providerPanelDescription }}</p>
                </div>
                <span class="status-pill" :class="{ configured: credentialForProvider }">
                  {{ selectedProvider ? (credentialForProvider ? 'Configured' : 'Needs Key') : 'Select Provider' }}
                </span>
              </div>

              <div class="compact-fields">
                <div v-if="isCompatiblePanel" class="form-group">
                  <label>LLM Provider</label>
                  <select v-model="selectedProviderId" class="modal-input">
                    <option value="" disabled>Select compatible provider</option>
                    <option v-for="provider in compatibleProviders" :key="provider.provider_id" :value="provider.provider_id">
                      {{ provider.label }}
                    </option>
                  </select>
                </div>

                <div v-if="!selectedProvider" class="form-group field-wide empty-provider-state">
                  Select a provider from the left panel or choose one OpenAI-compatible provider above.
                </div>

                <div v-if="selectedProvider" class="form-group">
                  <label>API Key</label>
                  <input
                    type="password"
                    v-model="apiKey"
                    :placeholder="credentialForProvider ? '已配置，留空则不修改' : 'Enter API key'"
                    class="modal-input"
                  />
                  <small v-if="credentialForProvider">Credential: {{ credentialForProvider.credential_id }}</small>
                </div>

                <div v-if="selectedProvider?.requires_base_url" class="form-group field-wide">
                  <label>Base URL</label>
                  <input
                    type="text"
                    v-model="baseUrl"
                    :placeholder="selectedProvider.default_base_url"
                    class="modal-input"
                  />
                </div>

                <div v-if="selectedProvider" class="form-group field-wide">
                  <label>Model Name</label>
                  <div v-if="availableModels.length > 0" class="model-selection">
                    <select v-model="selectedModel" class="modal-input">
                      <option v-for="m in availableModels" :key="m" :value="m">{{ m }}</option>
                      <option v-if="selectedProvider?.allow_custom_model" value="__custom">-- Custom Model --</option>
                    </select>
                    <input
                      v-if="selectedModel === '__custom'"
                      type="text"
                      v-model="customModelName"
                      placeholder="Enter custom model name"
                      class="modal-input mt-2"
                    />
                  </div>
                  <input
                    v-else
                    type="text"
                    v-model="customModelName"
                    :placeholder="selectedProvider?.default_model"
                    class="modal-input"
                  />
                </div>
              </div>
            </div>

            <div v-else class="provider-panel defaults-panel">
              <div class="panel-title-row">
                <div>
                  <div class="section-label">Default Options</div>
                  <p>Each group uses one model configuration for all listed usages. Groups set to Use Default inherit the fallback model.</p>
                </div>
              </div>

              <div class="default-option-row default-row">
                <div>
                  <label>{{ defaultProfileOption.label }}</label>
                  <small>{{ defaultProfileOption.description }}</small>
                </div>
                <select v-model="taskProfileSelections.default" class="modal-input">
                  <option value="" disabled>Select default model</option>
                  <option v-for="profile in configuredModelProfiles" :key="profile.key" :value="profile.key">
                    {{ profile.label }}
                  </option>
                </select>
              </div>

              <div
                v-for="group in defaultOptionGroups"
                :key="group.title"
                class="option-group"
              >
                <div class="option-group-title">{{ group.title }}</div>
                <div class="default-option-row">
                  <div>
                    <label>{{ group.label }}</label>
                    <small>{{ group.description }}</small>
                    <div class="usage-list">
                      {{ group.items.map((task) => task.label).join(' / ') }}
                    </div>
                  </div>
                  <select v-model="taskProfileSelections[group.id]" class="modal-input">
                    <option value="__default">Use Default</option>
                    <option v-for="profile in configuredModelProfiles" :key="profile.key" :value="profile.key">
                      {{ profile.label }}
                    </option>
                  </select>
                </div>
              </div>
            </div>
            </div>
          </section>

          <p v-if="formError" class="settings-form-error" role="alert">{{ formError }}</p>
          <div class="form-actions">
            <button type="button" class="cancel-btn" :disabled="isSaving" @click="$emit('close')">取消</button>
            <button type="submit" class="save-btn primary-btn" :disabled="isSaving">
              {{ isSaving ? '正在保存…' : '保存设置' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { apiClient } from '../api/client'

const props = defineProps({
  show: Boolean
})

const emit = defineEmits(['close', 'save'])

const settings = ref({
  storagePath: ''
})

const providerCatalog = ref([])
const credentials = ref([])
const taskProfiles = ref({})
const credentialDrafts = ref({})
const taskProfileSelections = ref({})
const defaultProfileOption = ref({
  label: 'Default',
  description: 'Fallback for every task without its own model.'
})
const defaultOptionGroups = ref([])
const activeSection = ref('providers')
const activeProviderEntryId = ref('')
const selectedProviderId = ref('')
const selectedModel = ref('')
const customModelName = ref('')
const apiKey = ref('')
const baseUrl = ref('')
const formError = ref('')
const isSaving = ref(false)

const COMPATIBLE_ENTRY_ID = 'openai-compatible'
const FIXED_PROVIDER_IDS = ['openai', 'deepseek', 'gemini', 'anthropic']
const COMPATIBLE_PROVIDER_IDS = ['kimi', 'qwen', 'glm', 'minimax', 'openrouter']

const fixedProviders = computed(() => {
  const providersById = new Map(providerCatalog.value.map((provider) => [provider.provider_id, provider]))
  return FIXED_PROVIDER_IDS.map((providerId) => providersById.get(providerId)).filter(Boolean)
})

const compatibleProviders = computed(() => {
  const compatibleIds = new Set(COMPATIBLE_PROVIDER_IDS)
  return providerCatalog.value.filter((provider) => compatibleIds.has(provider.provider_id))
})

const providerNavigation = computed(() => {
  const fixedEntries = fixedProviders.value.map((provider) => ({
    id: provider.provider_id,
    label: provider.label,
    configured: Boolean(credentialForProviderId(provider.provider_id))
  }))
  if (!compatibleProviders.value.length) return fixedEntries
  return [
    ...fixedEntries,
    {
      id: COMPATIBLE_ENTRY_ID,
      label: 'OpenAI Compatible',
      configured: compatibleProviders.value.some((provider) => credentialForProviderId(provider.provider_id))
    }
  ]
})

const isCompatibleProviderId = (providerId) => {
  return COMPATIBLE_PROVIDER_IDS.includes(providerId)
}

const entryIdForProviderId = (providerId) => {
  if (!providerId) return ''
  return isCompatibleProviderId(providerId) ? COMPATIBLE_ENTRY_ID : providerId
}

const isCompatiblePanel = computed(() => activeProviderEntryId.value === COMPATIBLE_ENTRY_ID)

const providerPanelDescription = computed(() => {
  if (isCompatiblePanel.value) {
    return 'Choose an OpenAI-compatible provider, then configure its credentials and default model list.'
  }
  return selectedProvider.value
    ? `Configure credentials and the default model list for ${selectedProvider.value.label}.`
    : 'Choose a provider to configure credentials and the default model list.'
})

const availableModels = computed(() => {
  if (!selectedProvider.value) return []
  const credential = credentialForProvider.value
  return Array.from(new Set([
    selectedProvider.value.default_model,
    credential?.default_model,
    ...(selectedProvider.value.models || []),
    ...(credential?.models || [])
  ].filter(Boolean)))
})

const selectedProvider = computed(() => {
  return providerCatalog.value.find((provider) => provider.provider_id === selectedProviderId.value) || null
})

const credentialForProvider = computed(() => {
  return credentials.value.find((credential) => credential.provider_id === selectedProviderId.value) || null
})

const configuredModelProfiles = computed(() => {
  const draftByProvider = credentialDrafts.value || {}
  const credentialByProvider = new Map(credentials.value.map((credential) => [credential.provider_id, credential]))
  const configuredProviderIds = new Set([
    ...credentials.value.map((credential) => credential.provider_id || credential.credential_id),
    ...Object.values(draftByProvider)
      .filter((draft) => draft?.api_key || credentialByProvider.has(draft?.provider_id))
      .map((draft) => draft.provider_id)
  ].filter(Boolean))
  const profiles = []
  const seen = new Set()

  providerCatalog.value.forEach((provider) => {
    if (!configuredProviderIds.has(provider.provider_id)) return
    const draft = draftByProvider[provider.provider_id]
    const credential = credentialByProvider.get(provider.provider_id)
    const credentialId = draft?.credential_id || credential?.credential_id || provider.provider_id
    const providerType = draft?.provider_type || credential?.provider_type || provider.provider_type
    const baseUrl = draft?.base_url ?? credential?.base_url ?? provider.default_base_url ?? null
    const models = Array.from(new Set([
      draft?.default_model,
      credential?.default_model,
      provider.default_model,
      provider.provider_id === selectedProviderId.value ? resolvedModel.value : '',
      ...(draft?.models || []),
      ...(credential?.models || []),
      ...(provider.models || [])
    ].filter(Boolean)))

    models.forEach((model) => {
      const key = modelProfileKey(provider.provider_id, model)
      if (seen.has(key)) return
      seen.add(key)
      profiles.push({
        key,
        label: `${provider.label} / ${model}`,
        provider_id: provider.provider_id,
        provider_type: providerType,
        credential_id: credentialId,
        base_url: baseUrl,
        model
      })
    })
  })

  return profiles
})

const resolvedModel = computed(() => {
  if (selectedModel.value === '__custom') return customModelName.value.trim()
  return selectedModel.value || customModelName.value.trim()
})

const modelProfileKey = (providerId, model) => `${providerId}::${model}`

const profileToKey = (profile) => {
  if (!profile?.provider_id || !profile?.model) return ''
  return modelProfileKey(profile.provider_id, profile.model)
}

const profileFromKey = (key) => {
  return configuredModelProfiles.value.find((profile) => profile.key === key) || null
}

const selectionToProfilePayload = (key) => {
  const profile = profileFromKey(key)
  if (!profile) return null
  return {
    provider_id: profile.provider_id,
    provider_type: profile.provider_type,
    credential_id: profile.credential_id,
    model: profile.model
  }
}

const credentialForProviderId = (providerId) => {
  return credentials.value.find((credential) => {
    return credential.provider_id === providerId || credential.credential_id === providerId
  }) || null
}

const upsertCredentialSummary = (items, summary) => {
  if (!summary?.credential_id) return items
  const nextItems = items.filter((item) => item.credential_id !== summary.credential_id)
  nextItems.push(summary)
  return nextItems
}

const providerForId = (providerId) => {
  return providerCatalog.value.find((provider) => provider.provider_id === providerId) || null
}

const providerIdFromCredential = (credential) => {
  if (!credential) return ''
  return providerForId(credential.provider_id)?.provider_id || providerForId(credential.credential_id)?.provider_id || ''
}

const selectProviderEntry = (entryId) => {
  activeSection.value = 'providers'
  activeProviderEntryId.value = entryId
  if (entryId === COMPATIBLE_ENTRY_ID) {
    if (!isCompatibleProviderId(selectedProviderId.value)) {
      selectedProviderId.value = ''
    }
    return
  }
  selectedProviderId.value = entryId
}

const ensureTaskProfileSelections = () => {
  const selections = { ...taskProfileSelections.value }
  const firstProfileKey = configuredModelProfiles.value[0]?.key || ''
  const availableProfileKeys = new Set(configuredModelProfiles.value.map((profile) => profile.key))
  if (!selections.default || !availableProfileKeys.has(selections.default)) {
    const savedDefaultKey = profileToKey(taskProfiles.value.default)
    selections.default = availableProfileKeys.has(savedDefaultKey) ? savedDefaultKey : firstProfileKey
  }
  defaultOptionGroups.value.forEach((group) => {
    if (!selections[group.id] || (selections[group.id] !== '__default' && !availableProfileKeys.has(selections[group.id]))) {
      const explicitKeys = Array.from(new Set(
        group.items
          .map((task) => profileToKey(taskProfiles.value[task.id]))
          .filter((key) => availableProfileKeys.has(key))
          .filter(Boolean)
      ))
      selections[group.id] = explicitKeys.length === 1 ? explicitKeys[0] : '__default'
    }
  })
  taskProfileSelections.value = selections
}

const hydrateTaskProfileSelections = (profiles) => {
  const selections = {}
  selections.default = profileToKey(profiles.default)
  defaultOptionGroups.value.forEach((group) => {
    const explicitKeys = Array.from(new Set(
      group.items
        .map((task) => profileToKey(profiles[task.id]))
        .filter(Boolean)
    ))
    selections[group.id] = explicitKeys.length === 1 ? explicitKeys[0] : '__default'
  })
  taskProfileSelections.value = selections
  ensureTaskProfileSelections()
}

const buildTaskProfilesFromSelections = () => {
  ensureTaskProfileSelections()
  const nextProfiles = {}
  const defaultProfile = profileFromKey(taskProfileSelections.value.default)
  if (!defaultProfile) return nextProfiles

  nextProfiles.default = selectionToProfilePayload(taskProfileSelections.value.default)

  defaultOptionGroups.value.forEach((group) => {
    const selectedKey = taskProfileSelections.value[group.id]
    if (!selectedKey || selectedKey === '__default') return
    const profilePayload = selectionToProfilePayload(selectedKey)
    if (!profilePayload) return
    group.items.forEach((task) => {
      nextProfiles[task.id] = { ...profilePayload }
    })
  })

  return nextProfiles
}

const updateCredentialDraftFromForm = (providerId = selectedProviderId.value) => {
  const provider = providerForId(providerId)
  if (!provider) return
  const existing = credentialForProviderId(providerId)
  const model = resolvedModel.value || existing?.default_model || provider.default_model
  credentialDrafts.value = {
    ...credentialDrafts.value,
    [providerId]: {
      credential_id: existing?.credential_id || provider.provider_id,
      provider_type: provider.provider_type,
      provider_id: provider.provider_id,
      base_url: provider.requires_base_url ? (baseUrl.value || provider.default_base_url || '') : null,
      default_model: model,
      models: model ? Array.from(new Set([model, ...(provider.models || [])])) : provider.models || [],
      headers: {},
      ...(apiKey.value ? { api_key: apiKey.value } : {})
    }
  }
}

const selectModel = (model) => {
  const provider = selectedProvider.value
  if (!provider) return
  const models = availableModels.value
  const candidate = model || provider.default_model || models[0] || ''
  if (candidate && models.includes(candidate)) {
    selectedModel.value = candidate
    customModelName.value = ''
  } else if (candidate) {
    selectedModel.value = provider.allow_custom_model ? '__custom' : (models[0] || '')
    customModelName.value = provider.allow_custom_model ? candidate : ''
  } else {
    selectedModel.value = ''
    customModelName.value = ''
  }
}

const hydrateProviderForm = (profile = null) => {
  const provider = selectedProvider.value
  if (!provider) {
    apiKey.value = ''
    baseUrl.value = ''
    selectedModel.value = ''
    customModelName.value = ''
    return
  }
  const credential = credentialForProvider.value
  apiKey.value = ''
  baseUrl.value = credential?.base_url || provider.default_base_url || ''
  const profileMatchesProvider = !profile?.provider_id || profile.provider_id === provider.provider_id
  selectModel((profileMatchesProvider && profile?.model) || credential?.default_model || provider.default_model)
}

watch(selectedProviderId, (_nextProviderId, previousProviderId) => {
  if (previousProviderId) {
    updateCredentialDraftFromForm(previousProviderId)
  }
  hydrateProviderForm()
})

onMounted(async () => {
  // Load settings from API
  try {
    const [settingsResponse, providerOptionsResponse, credentialsResponse] = await Promise.all([
      apiClient.get('/settings'),
      apiClient.get('/provider-options'),
      apiClient.get('/credentials')
    ])
    const data = settingsResponse.data
    const profiles = data.llm_profiles && Object.keys(data.llm_profiles).length
      ? data.llm_profiles
      : (data.llm_profile ? { default: data.llm_profile } : {})
    providerCatalog.value = providerOptionsResponse.data.provider_catalog || []
    defaultProfileOption.value = providerOptionsResponse.data.llm_task_group_options?.default_profile || defaultProfileOption.value
    defaultOptionGroups.value = providerOptionsResponse.data.llm_task_group_options?.groups || []
    credentials.value = credentialsResponse.data.credentials || []
    taskProfiles.value = profiles
    settings.value = {
      storagePath: data.storage_path || 'storage'
    }
    const defaultProviderId = profiles.default?.provider_id
    selectedProviderId.value = credentialForProviderId(defaultProviderId) ? defaultProviderId : providerIdFromCredential(credentials.value[0]) || defaultProviderId || ''
    activeProviderEntryId.value = entryIdForProviderId(selectedProviderId.value)
    if (selectedProviderId.value) {
      hydrateProviderForm(profiles.default)
    }
    hydrateTaskProfileSelections(profiles)
  } catch (e) {
    console.error("Failed to fetch settings:", e)
    formError.value = `服务器设置加载失败，当前显示本地缓存：${e.message}`
    // Fallback to localStorage
    const saved = localStorage.getItem('app_settings')
    if (saved) {
      const parsed = JSON.parse(saved)
      settings.value.storagePath = parsed.storagePath
    }
  }
})

const saveSettings = async () => {
  formError.value = ''
  isSaving.value = true
  try {
    const provider = selectedProvider.value
    if (!provider) {
      formError.value = '请先选择一个 LLM 服务商。'
      return
    }
    const model = resolvedModel.value
    if (!model) {
      formError.value = '请选择或输入模型名称。'
      return
    }
    updateCredentialDraftFromForm()
    const nextTaskProfiles = buildTaskProfilesFromSelections()
    if (!nextTaskProfiles.default) {
      formError.value = '请先为默认任务选择一个模型。'
      return
    }

    for (const draft of Object.values(credentialDrafts.value)) {
      const existing = credentialForProviderId(draft.provider_id)
      let response
      if (existing) {
        response = await apiClient.put(`/credentials/${existing.credential_id}`, draft)
      } else {
        if (!draft.api_key) {
          formError.value = `${draft.provider_id} 需要填写 API Key。`
          return
        }
        response = await apiClient.post('/credentials', draft)
      }
      credentials.value = upsertCredentialSummary(credentials.value, response.data.credential)
    }

    await apiClient.post('/settings', {
      storage_path: settings.value.storagePath,
      llm_profiles: nextTaskProfiles
    })
    taskProfiles.value = nextTaskProfiles
    
    localStorage.setItem('app_settings', JSON.stringify({
      storagePath: settings.value.storagePath
    }))
    emit('save', settings.value)
    emit('close')
  } catch (e) {
    formError.value = `设置保存失败：${e.response?.data?.detail || e.message}`
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped>
.mt-2 {
  margin-top: 0.5rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  padding: 1.25rem;
  background: rgba(15, 23, 42, 0.52);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(8px);
}

.modal-content {
  --modal-ink: #14213d;
  --modal-muted: #64748b;
  --modal-line: #dbe3ea;
  --modal-panel: #f6f8fb;
  --modal-accent: #2563eb;
  --modal-accent-dark: #1d4ed8;

  background: #ffffff;
  width: min(860px, 100%);
  max-height: calc(100vh - 2rem);
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 22px;
  overflow: hidden;
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.28);
}

.modal-content,
.modal-content * {
  box-sizing: border-box;
}

.modal-header {
  padding: 1rem 1.2rem;
  border-bottom: 1px solid rgba(219, 227, 234, 0.95);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.1), transparent 38%),
    linear-gradient(135deg, #ffffff 0%, #f7faf9 100%);
}

.modal-kicker {
  margin: 0 0 0.18rem;
  color: var(--modal-muted);
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.modal-header h2 {
  margin: 0;
  color: var(--modal-ink);
  font-size: 1.12rem;
  line-height: 1.2;
}

.close-btn {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--modal-line);
  border-radius: 999px;
  font-size: 1.35rem;
  line-height: 1;
  cursor: pointer;
  color: #64748b;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #ffffff;
  border-color: #b8c6d1;
  color: var(--modal-ink);
  transform: translateY(-1px);
}

.modal-body {
  padding: 1rem 1.2rem 1.1rem;
  max-height: calc(100vh - 7rem);
  overflow: auto;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}

.settings-form {
  display: grid;
  gap: 0.9rem;
}

.storage-strip {
  display: grid;
  grid-template-columns: minmax(180px, 0.78fr) minmax(260px, 1.22fr);
  align-items: center;
  gap: 1rem;
  padding: 0.85rem;
  border: 1px solid rgba(219, 227, 234, 0.95);
  border-radius: 16px;
  background: var(--modal-panel);
}

.field-heading label,
.form-group label {
  display: block;
  font-weight: 800;
  margin-bottom: 0.38rem;
  color: var(--modal-ink);
  font-size: 0.78rem;
  letter-spacing: 0.01em;
}

.field-heading small,
.form-group small,
.panel-title-row p {
  display: block;
  color: var(--modal-muted);
  margin: 0;
  font-size: 0.72rem;
  line-height: 1.45;
}

.settings-grid {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 0.9rem;
  align-items: start;
}

.task-panel,
.provider-panel {
  border: 1px solid rgba(219, 227, 234, 0.95);
  border-radius: 16px;
  background: var(--modal-panel);
}

.task-panel {
  padding: 0.65rem;
  display: grid;
  gap: 0.35rem;
}

.section-label {
  color: #526174;
  font-size: 0.66rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.task-panel .section-label {
  padding: 0.2rem 0.35rem 0.35rem;
}

.task-button {
  width: 100%;
  min-height: 32px;
  padding: 0.38rem 0.52rem;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: #475569;
  text-align: left;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  transition: background 0.18s, border-color 0.18s, color 0.18s;
}

.task-button:hover {
  background: rgba(255, 255, 255, 0.75);
  color: var(--modal-ink);
}

.task-button.active {
  border-color: rgba(37, 99, 235, 0.22);
  background: #ffffff;
  color: var(--modal-accent);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06);
}

.sidebar-divider {
  margin: 0.35rem 0;
  border-top: 1px solid rgba(219, 227, 234, 0.95);
}

.default-options-button {
  min-height: 36px;
}

.mini-state {
  flex: 0 0 auto;
  padding: 0.08rem 0.3rem;
  border-radius: 6px;
  background: #e2e8f0;
  color: #94a3b8;
  font-size: 0.56rem;
  font-weight: 900;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.mini-state.configured {
  background: rgba(37, 99, 235, 0.1);
  color: var(--modal-accent);
}

.settings-stack {
  display: grid;
  gap: 0.9rem;
}

.provider-panel {
  padding: 0.85rem;
}

.panel-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid rgba(219, 227, 234, 0.9);
}

.panel-title-row p {
  margin-top: 0.25rem;
}

.status-pill {
  flex: 0 0 auto;
  padding: 0.22rem 0.5rem;
  border-radius: 999px;
  background: #e2e8f0;
  color: #64748b;
  font-size: 0.62rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.status-pill.configured {
  background: rgba(37, 99, 235, 0.1);
  color: var(--modal-accent);
}

.compact-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
  padding-top: 0.85rem;
}

.field-wide {
  grid-column: 1 / -1;
}

.empty-provider-state {
  padding: 0.75rem;
  border: 1px dashed rgba(148, 163, 184, 0.7);
  border-radius: 12px;
  color: var(--modal-muted);
  font-size: 0.76rem;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.58);
}

.defaults-panel {
  display: grid;
  gap: 0.8rem;
}

.default-option-row {
  display: grid;
  grid-template-columns: minmax(180px, 0.8fr) minmax(220px, 1fr);
  align-items: center;
  gap: 0.8rem;
  padding: 0.58rem 0;
  border-top: 1px solid rgba(219, 227, 234, 0.72);
}

.default-option-row:first-of-type {
  border-top: 0;
}

.default-row {
  padding: 0.75rem;
  border: 1px solid rgba(37, 99, 235, 0.14);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.66);
}

.default-option-row label {
  display: block;
  margin-bottom: 0.18rem;
  color: var(--modal-ink);
  font-size: 0.78rem;
  font-weight: 800;
}

.default-option-row small {
  display: block;
  color: var(--modal-muted);
  font-size: 0.68rem;
  line-height: 1.35;
}

.usage-list {
  margin-top: 0.36rem;
  color: #526174;
  font-size: 0.66rem;
  font-weight: 800;
  line-height: 1.35;
}

.option-group {
  display: grid;
  gap: 0;
}

.option-group-title {
  padding: 0.2rem 0 0.25rem;
  color: #526174;
  font-size: 0.66rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.form-group {
  margin: 0;
}

.modal-input {
  width: 100%;
  min-height: 38px;
  padding: 0.52rem 0.68rem;
  border: 1px solid var(--modal-line);
  border-radius: 10px;
  font-size: 0.84rem;
  color: var(--modal-ink);
  background: white;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.modal-input:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
  margin-top: 0.1rem;
  padding-top: 0.85rem;
  border-top: 1px solid rgba(219, 227, 234, 0.95);
}

.cancel-btn {
  padding: 0.56rem 0.98rem;
  background: white;
  border: 1px solid var(--modal-line);
  border-radius: 999px;
  cursor: pointer;
  font-weight: 700;
  font-size: 0.82rem;
  color: #475569;
  transition: all 0.2s;
}

.cancel-btn:hover {
  background: #f8fafc;
  border-color: #b8c6d1;
  color: var(--modal-ink);
}

.primary-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.56rem 1.05rem;
  background: var(--modal-accent);
  color: white;
  border: none;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.82rem;
  cursor: pointer;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.18);
  transition: background 0.2s, transform 0.2s, box-shadow 0.2s;
}

.primary-btn:hover {
  background: var(--modal-accent-dark);
  transform: translateY(-1px);
}

@media (max-width: 760px) {
  .modal-overlay {
    padding: 0.75rem;
    align-items: flex-start;
  }

  .modal-content {
    width: 100%;
    max-height: calc(100vh - 1rem);
    border-radius: 20px;
  }

  .modal-header,
  .modal-body {
    padding: 1rem;
  }

  .storage-strip,
  .settings-grid,
  .compact-fields,
  .default-option-row {
    grid-template-columns: 1fr;
  }

  .task-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .task-panel .section-label {
    grid-column: 1 / -1;
  }

  .form-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .cancel-btn,
  .primary-btn {
    width: 100%;
  }
}
</style>
