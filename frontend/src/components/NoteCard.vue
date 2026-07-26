<template>
  <div class="note-card" :class="[note.type, { collapsed: isCollapsed, 'is-drawer': drawer }]" :style="drawer ? { top: `${top}px` } : {}">
    <div class="note-header" @click="toggleCollapse">
      <div class="header-left">
          <span class="collapse-icon">{{ isCollapsed ? '▶' : '▼' }}</span>
          <span class="note-title">{{ note.title || 'Conversation' }}</span>
      </div>
      <div class="header-right">
          <span class="note-date" v-if="note.created_at && !isCollapsed">{{ formatDate(note.created_at) }}</span>
          <button @click.stop="confirmDelete" class="delete-btn" title="Delete Note">×</button>
      </div>
    </div>
    
    <div class="note-body" v-show="!isCollapsed">
      <div v-if="note.selected_text" ref="selectedTextRef" class="selected-text-preview">
        "{{ note.selected_text }}"
      </div>
      
      <div ref="contentRef" class="note-content latex-content" v-html="renderedContent"></div>
      
      <div class="chat-input-area">
        <textarea 
            v-model="inputPrompt" 
            placeholder="Ask a question..." 
            @keydown.enter.exact.prevent="sendChat"
            @click.stop
            :disabled="note.loading"
        ></textarea>
        <button @click.stop="sendChat" :disabled="!inputPrompt.trim() || note.loading">
            {{ note.loading ? '...' : 'Send' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, toRefs, onMounted, nextTick, ref, watch } from 'vue'
import { deserializeMessages, renderMarkdown, renderMath as renderKatexMath } from '../utils/renderer'

const props = defineProps({
  note: {
    type: Object,
    required: true
  },
  top: {
    type: Number,
    default: 0
  },
  drawer: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['delete', 'chat', 'toggle-expand'])

const isCollapsed = ref(true)
const inputPrompt = ref('')

const toggleCollapse = () => {
    isCollapsed.value = !isCollapsed.value
    emit('toggle-expand', !isCollapsed.value)
    if (!isCollapsed.value) {
        renderMath()
    }
}

const confirmDelete = () => {
  if (confirm('Are you sure you want to delete this note?')) {
    emit('delete')
  }
}

const sendChat = () => {
    if (!inputPrompt.value.trim()) return
    emit('chat', inputPrompt.value)
    inputPrompt.value = ''
}

const renderedContent = computed(() => {
  const rawMessages = Array.isArray(props.note.messages) ? props.note.messages : (props.note.note_content || '')
  const messages = deserializeMessages(rawMessages)
  if (!messages.length) return ''
  return messages.map((message) => {
    const className = message.role === 'user' ? 'chat-user' : 'chat-ai'
    return `<div class="${className}">${renderMarkdown(message.content)}</div>`
  }).join('')
})

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString()
}

const contentRef = ref(null)
const selectedTextRef = ref(null)

const renderMath = () => {
  nextTick(() => {
    if (contentRef.value) {
      renderKatexMath(contentRef.value)
      // Auto-scroll to bottom if loading
      if (props.note.loading) {
          contentRef.value.scrollTop = contentRef.value.scrollHeight
      }
    }
    
    if (selectedTextRef.value) {
      renderKatexMath(selectedTextRef.value)
    }
  })
}

watch(() => props.note.note_content, () => {
    renderMath()
})

watch(() => props.note.messages, () => {
    renderMath()
}, { deep: true })

watch(() => props.note.selected_text, () => {
    renderMath()
})

onMounted(() => {
  renderMath()
})
</script>

<style scoped>
.note-card {
  position: relative;
  width: 100%; 
  background: #fff;
  border: 1px solid #eee;
  border-left: 3px solid #ccc;
  border-radius: 6px;
  padding: 0;
  box-shadow: 0 2px 5px rgba(0,0,0,0.05);
  font-size: 0.9rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  margin-bottom: 1rem;
  display: flex;
  flex-direction: column;
}

.note-card.is-drawer {
  position: absolute;
  right: 0;
  width: 280px;
  z-index: 10;
  margin-bottom: 0;
}

.note-card.is-drawer:not(.collapsed) {
    width: 600px;
    box-shadow: -10px 0 30px rgba(0,0,0,0.15);
    z-index: 100;
}

/* For smaller screens, don't let the drawer exceed viewport width */
@media (max-width: 1200px) {
    .note-card:not(.collapsed) {
        width: 80vw;
    }
}

/* Header */
.note-header {
  padding: 0.6rem 0.8rem;
  background: #f8f9fa;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.8rem;
  color: #555;
  cursor: pointer;
  border-top-left-radius: 6px;
  border-top-right-radius: 6px;
}

.header-left { display: flex; align-items: center; gap: 0.5rem; }
.collapse-icon { font-size: 0.6rem; color: #aaa; }
.note-title { font-weight: 600; color: #333; }
.header-right { display: flex; align-items: center; gap: 0.5rem; }
.delete-btn { background: none; border: none; font-size: 1.2rem; cursor: pointer; color: #999; line-height: 1; padding: 0; }
.delete-btn:hover { color: #f44336; }

/* Body */
.note-body {
  padding: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
}

.selected-text-preview {
  font-style: italic;
  color: #666;
  font-size: 0.8rem;
  padding: 0.5rem;
  background: #f9f9f9;
  border-left: 2px solid #ddd;
  border-radius: 2px;
}

.note-content {
  line-height: 1.6;
  color: #333;
  overflow-y: auto;
}

/* Chat Input */
.chat-input-area {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
    border-top: 1px solid #f0f0f0;
    padding-top: 0.8rem;
}

.chat-input-area textarea {
    flex: 1;
    min-height: 40px;
    padding: 0.4rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    resize: vertical;
    font-family: inherit;
    font-size: 0.85rem;
}

.chat-input-area textarea:focus {
    outline: none;
    border-color: #2196F3;
}

.chat-input-area button {
    background: #2196F3;
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0 0.8rem;
    font-weight: 600;
    cursor: pointer;
    font-size: 0.8rem;
}

.chat-input-area button:disabled {
    background: #ccc;
    cursor: not-allowed;
}

.note-footer {
  padding: 0 0.8rem 0.8rem 0.8rem;
  text-align: right;
}

.save-btn {
  background: #4CAF50;
  color: white;
  border: none;
  padding: 0.4rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 500;
}

/* Chat Styles (Global or Deep) */
:deep(.chat-user) {
    background: #e3f2fd;
    padding: 0.5rem;
    border-radius: 6px;
    margin: 0.5rem 0 0.5rem 1rem;
    font-size: 0.9em;
    border-bottom-right-radius: 0;
}

:deep(.chat-ai) {
    background: #f1f1f1;
    padding: 0.5rem;
    border-radius: 6px;
    margin: 0.5rem 1rem 0.5rem 0;
    font-size: 0.9em;
    border-bottom-left-radius: 0;
}
</style>
