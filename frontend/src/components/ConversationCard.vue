<template>
  <article
    class="conversation-card"
    :class="{ active, loading: card.loading }"
    @click="emit('activate', card)"
  >
    <header class="card-header">
      <div class="title-group">
        <strong>{{ card.title }}</strong>
        <p>{{ subtitle }}</p>
      </div>
      <span class="type-pill">{{ typeLabel }}</span>
    </header>

    <blockquote v-if="card.selectedText" ref="selectedTextRef" class="selected-preview">
      {{ card.selectedText }}
    </blockquote>

    <div ref="contentRef" class="card-content latex-content" :class="{ empty: !messages.length }">
      <p v-if="!messages.length">Ask a question to start this conversation.</p>
      <template v-else>
        <div
          v-for="(message, index) in messages"
          :key="`${message.role}-${index}`"
          class="chat-message"
          :class="message.role === 'user' ? 'chat-user' : 'chat-ai'"
          v-html="renderMessage(message.content)"
        ></div>
      </template>
    </div>
  </article>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { deserializeMessages, renderMarkdown, renderMath as renderKatexMath } from '../utils/renderer'

const props = defineProps({
  card: {
    type: Object,
    required: true
  },
  active: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['activate'])

const contentRef = ref(null)
const selectedTextRef = ref(null)

const typeLabel = computed(() => {
  if (props.card.readerType === 'guide') return 'Guide'
  if (props.card.type === 'chapter') return 'Chapter'
  if (props.card.type === 'selection') return 'Selection'
  if (props.card.type === 'quiz') return 'Quiz'
  if (props.card.type === 'custom') return 'Custom'
  return 'Ask'
})

const subtitle = computed(() => {
  if (props.card.loading) return 'Generating response...'
  if (props.card.createdAt) return new Date(props.card.createdAt).toLocaleDateString()
  if (props.card.readerType === 'guide') return 'Current guide context'
  if (props.card.type === 'chapter') return 'Current chapter context'
  if (props.card.type === 'selection') return 'Selected text context'
  if (props.card.type === 'quiz') return 'Quiz dialogue'
  if (props.card.type === 'custom') return 'Saved note'
  return 'Conversation'
})

const messages = computed(() => {
  if (Array.isArray(props.card.messages)) return props.card.messages
  return deserializeMessages(props.card.noteContent || '')
})

const renderMessage = (messageContent) => renderMarkdown(messageContent)

const renderMath = () => {
  nextTick(() => {
    if (contentRef.value) {
      renderKatexMath(contentRef.value)
      if (props.card.loading) {
        contentRef.value.scrollTop = contentRef.value.scrollHeight
      }
    }

    if (selectedTextRef.value) {
      renderKatexMath(selectedTextRef.value)
    }
  })
}

watch(() => props.card.noteContent, renderMath)
watch(() => props.card.messages, renderMath, { deep: true })
watch(() => props.card.selectedText, renderMath)

onMounted(renderMath)
</script>

<style scoped>
.conversation-card {
  width: 100%;
  border: 1px solid #e5e7eb;
  border-left: 3px solid transparent;
  border-radius: 8px;
  background: #fff;
  padding: 0.75rem;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.conversation-card:hover {
  border-color: #cbd5e1;
}

.conversation-card.active {
  border-color: #2563eb;
  border-left-color: #2563eb;
  background: #f8fbff;
}

.conversation-card.loading {
  cursor: progress;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
}

.title-group {
  min-width: 0;
}

.title-group strong {
  display: block;
  color: #111827;
  font-size: 0.9rem;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-group p {
  margin: 0.2rem 0 0;
  color: #6b7280;
  font-size: 0.75rem;
  line-height: 1.3;
}

.type-pill {
  flex-shrink: 0;
  border: 1px solid #dbeafe;
  border-radius: 999px;
  color: #1d4ed8;
  background: #eff6ff;
  font-size: 0.7rem;
  font-weight: 600;
  line-height: 1;
  padding: 0.25rem 0.45rem;
}

.selected-preview {
  margin: 0.65rem 0 0;
  padding: 0.5rem 0.6rem;
  border-left: 2px solid #cbd5e1;
  border-radius: 4px;
  background: #f8fafc;
  color: #475569;
  font-size: 0.78rem;
  line-height: 1.5;
  max-height: 4.5rem;
  overflow: hidden;
}

.card-content {
  margin-top: 0.65rem;
  color: #1f2937;
  font-size: 0.84rem;
  line-height: 1.55;
  max-height: 18rem;
  overflow-y: auto;
}

.card-content.empty {
  color: #94a3b8;
}

.card-content :deep(p) {
  margin: 0 0 0.55rem;
}

.card-content :deep(p:last-child) {
  margin-bottom: 0;
}

.chat-message {
  padding: 0.5rem 0.6rem;
  border-radius: 6px;
  margin-bottom: 0.5rem;
}

.chat-user {
  background: #eff6ff;
  color: #1e3a8a;
}

.chat-ai {
  background: #f8fafc;
  color: #1f2937;
}
</style>
