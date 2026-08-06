<template>
  <div v-if="show" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content card">
      <div class="modal-header">
        <div>
          <p class="modal-kicker">对话偏好</p>
          <h2>回复风格</h2>
        </div>
        <button class="close-btn" @click="$emit('close')" title="关闭" aria-label="关闭">×</button>
      </div>
      
      <div class="modal-body">
        <p class="description">
          管理阅读对话中可复用的回复风格。选中的风格只会应用到本次发送给 AI 的最新消息。
        </p>

        <div v-if="error" class="error-message">{{ error }}</div>
        <div v-if="loading" class="loading-message">正在加载回复风格…</div>

        <div v-else class="style-list">
          <div v-for="(style, index) in styles" :key="index" class="style-item">
            <div class="style-fields">
              <input 
                v-model="style.id" 
                placeholder="style-id" 
                class="modal-input id-input"
              />
              <input 
                v-model="style.label" 
                placeholder="显示名称"
                class="modal-input label-input"
              />
              <button class="remove-btn" @click="removeStyle(index)" title="删除风格" :aria-label="`删除第 ${index + 1} 个回复风格`">×</button>
              <input
                v-model="style.description"
                placeholder="风格说明"
                class="modal-input description-input"
              />
              <textarea
                v-model="style.prompt"
                placeholder="回复风格提示词…"
                class="modal-input prompt-input"
                rows="3"
              ></textarea>
            </div>
          </div>
        </div>

        <button type="button" class="add-btn" @click="addStyle">
          <span class="icon">+</span> 添加风格
        </button>

        <div class="form-actions">
          <button type="button" class="cancel-btn" @click="$emit('close')">取消</button>
          <button type="button" class="save-btn primary-btn" :disabled="saving" @click="saveStyles">
            {{ saving ? '正在保存…' : '保存风格' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { apiClient } from '../api/client'

const props = defineProps({
  show: Boolean
})

const emit = defineEmits(['close', 'save'])

const styles = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const normalizeStyles = (rawStyles) => {
  return Array.isArray(rawStyles)
    ? rawStyles.map(style => ({
        id: style?.id || '',
        label: style?.label || '',
        description: style?.description || '',
        prompt: style?.prompt || ''
      }))
    : []
}

const loadStyles = async () => {
  loading.value = true
  error.value = ''
  try {
    const response = await apiClient.get('/settings/conversation-styles')
    styles.value = normalizeStyles(response.data)
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '回复风格加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => props.show,
  (visible) => {
    if (visible) loadStyles()
  },
  { immediate: true }
)

const addStyle = () => {
  styles.value.push({ id: '', label: '', description: '', prompt: '' })
}

const removeStyle = (index) => {
  styles.value.splice(index, 1)
}

const saveStyles = async () => {
  saving.value = true
  error.value = ''
  try {
    const payload = styles.value.map(style => ({
      id: style.id,
      label: style.label,
      description: style.description,
      prompt: style.prompt
    }))
    const response = await apiClient.put('/settings/conversation-styles', payload)
    styles.value = normalizeStyles(response.data)
    emit('save', styles.value)
    emit('close')
  } catch (err) {
    error.value = err?.response?.data?.detail || err.message || '回复风格保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  padding: 2rem;
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
  --modal-accent: #2563eb;
  --modal-accent-dark: #1d4ed8;

  background: #ffffff;
  width: min(680px, 100%);
  max-height: calc(100vh - 2rem);
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.28);
}

.modal-content,
.modal-content * {
  box-sizing: border-box;
}

.modal-header {
  padding: 1.25rem 1.45rem;
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
  margin: 0 0 0.28rem;
  color: var(--modal-muted);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.28rem;
  color: var(--modal-ink);
  line-height: 1.2;
}

.close-btn {
  width: 34px;
  height: 34px;
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
  padding: 1.35rem 1.45rem 1.45rem;
  max-height: calc(100vh - 7rem);
  overflow: auto;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}

.description {
  margin: 0 0 1.15rem;
  color: var(--modal-muted);
  font-size: 0.9rem;
  line-height: 1.5;
}

.style-list {
  max-height: 440px;
  overflow-y: auto;
  margin-bottom: 1rem;
  padding-right: 0.35rem;
}

.style-item {
  margin-bottom: 1rem;
  padding: 0.9rem;
  border: 1px solid var(--modal-line);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.72));
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.style-fields {
  display: grid;
  grid-template-columns: minmax(110px, 0.8fr) minmax(160px, 1fr) 32px;
  gap: 0.5rem;
  align-items: start;
}

.description-input,
.prompt-input {
  grid-column: 1 / -1;
}

.prompt-input {
  resize: vertical;
  min-height: 82px;
  line-height: 1.45;
}

.remove-btn {
  background: #fff;
  color: #ef4444;
  border: 1px solid #fee2e2;
  border-radius: 999px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 1.2rem;
  transition: background 0.2s;
}

.remove-btn:hover {
  background: #fef2f2;
  border-color: #fecaca;
}

.modal-input {
  padding: 0.68rem 0.76rem;
  border: 1px solid var(--modal-line);
  border-radius: 12px;
  font-size: 0.9rem;
  min-width: 0;
  color: var(--modal-ink);
  background: white;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.modal-input:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: #ffffff;
  border: 1px dashed #b8c6d1;
  color: var(--modal-muted);
  padding: 0.7rem 1rem;
  border-radius: 14px;
  cursor: pointer;
  width: 100%;
  justify-content: center;
  font-weight: 600;
  transition: all 0.2s;
}

.add-btn:hover {
  background: #f8fbff;
  border-color: #93c5fd;
  color: var(--modal-ink);
  transform: translateY(-1px);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 2rem;
}

.cancel-btn {
  padding: 0.72rem 1.15rem;
  background: white;
  border: 1px solid var(--modal-line);
  border-radius: 999px;
  cursor: pointer;
  font-weight: 700;
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
  padding: 0.72rem 1.2rem;
  background: var(--modal-accent);
  color: white;
  border: none;
  border-radius: 999px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.18);
  transition: background 0.2s, transform 0.2s, box-shadow 0.2s;
}

.primary-btn:hover:not(:disabled) {
  background: var(--modal-accent-dark);
  transform: translateY(-1px);
}

.primary-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
  box-shadow: none;
}

.error-message {
  margin-bottom: 1rem;
  color: #b91c1c;
  background: #fee2e2;
  border: 1px solid #fecaca;
  border-radius: 12px;
  padding: 0.75rem;
  font-size: 0.9rem;
}

.loading-message {
  margin-bottom: 1rem;
  color: #64748b;
  font-size: 0.9rem;
}

@media (max-width: 640px) {
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

  .style-fields {
    grid-template-columns: minmax(0, 1fr) 32px;
  }

  .id-input {
    grid-column: 1;
    grid-row: 1;
  }

  .label-input {
    grid-column: 1 / -1;
    grid-row: 2;
  }

  .remove-btn {
    grid-column: 2;
    grid-row: 1;
    justify-self: end;
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
