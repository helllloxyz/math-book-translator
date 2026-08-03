<template>
  <aside
    v-if="card"
    ref="dialogRef"
    class="conversation-dialog"
    :class="[modeClass, { standalone }]"
    role="dialog"
    aria-modal="false"
    :aria-label="dialogTitle"
  >
      <aside v-if="!standalone" class="dialog-context-sidebar" aria-label="Source context">
        <section v-if="metadataFields.length" class="metadata-grid" aria-label="Conversation metadata">
          <div v-for="field in metadataFields" :key="field.label">
            <span>{{ field.label }}</span>
            <strong>{{ field.value }}</strong>
          </div>
        </section>

        <button
          v-if="canGoSource"
          type="button"
          class="source-button"
          @click="emit('go-source', card)"
        >
          Go to source
        </button>

        <button
          v-if="canDelete"
          type="button"
          class="delete-conversation-button"
          @click="emit('delete', card)"
        >
          Delete
        </button>

        <section v-if="isChapterNote && displayedChapterSummary" class="chapter-context">
          <h3>Chapter context</h3>
          <div ref="chapterSummaryRef" class="latex-content" v-html="renderMessage(displayedChapterSummary)"></div>
        </section>

      </aside>

      <div class="dialog-panel">
        <header class="dialog-header">
          <div class="header-primary-row">
            <span class="dialog-status-dot" aria-hidden="true"></span>
            <div class="header-copy">
              <div class="header-title-row">
                <span class="mode-label">{{ dialogTitle }}</span>
                <strong>{{ card.questionSummary || card.title || fallbackTitle }}</strong>
              </div>
            </div>
            <p v-if="!standalone" class="header-meta">{{ modelLabel }} · {{ sourceCount }} {{ sourceCount === 1 ? 'source' : 'sources' }}</p>
            <div v-if="standalone" class="standalone-actions" aria-label="Conversation actions">
              <button
                v-if="canGoSource"
                type="button"
                class="source-button"
                @click="emit('go-source', card)"
              >
                Go to source
              </button>

              <details class="standalone-details">
                <summary>
                  <span>详细信息</span>
                  <small>{{ metadataFields.length + 2 }}</small>
                </summary>
                <dl class="standalone-details-grid">
                  <div v-for="field in metadataFields" :key="field.label">
                    <dt>{{ field.label }}</dt>
                    <dd>{{ field.value }}</dd>
                  </div>
                  <div>
                    <dt>Model</dt>
                    <dd>{{ modelLabel }}</dd>
                  </div>
                  <div>
                    <dt>Sources</dt>
                    <dd>{{ sourceCount }}</dd>
                  </div>
                </dl>
              </details>

              <button
                v-if="canDelete"
                type="button"
                class="delete-conversation-button"
                @click="emit('delete', card)"
              >
                Delete
              </button>
            </div>
            <button v-if="!standalone" type="button" class="close-button" aria-label="Close conversation" @click="emit('close')">
              ×
            </button>
          </div>
        </header>

        <div class="dialog-content">
          <section ref="messagesRef" class="message-list latex-content" :class="{ empty: !messages.length && !selectedText }">
            <section v-if="standalone && isChapterNote && displayedChapterSummary" class="chapter-context standalone-context-card">
              <h3>Chapter context</h3>
              <div ref="chapterSummaryRef" class="latex-content" v-html="renderMessage(displayedChapterSummary)"></div>
            </section>

            <details
              v-if="isSelectionNote && selectedText"
              ref="selectedTextRef"
              class="question-block latex-content question-context-details"
              open
            >
              <summary>Question context</summary>
              <p>{{ selectedText }}</p>
            </details>
            <p v-if="showEmptyMessage" class="empty-message">{{ emptyMessage }}</p>
            <template v-else>
              <article
                v-for="(message, index) in displayMessages"
                :key="`${message.role}-${index}`"
                class="chat-message"
                :class="message.role === 'user' ? 'chat-user question-block' : 'chat-ai answer-block'"
              >
                <template v-if="message.role === 'user'">
                  <span>{{ isQuiz ? 'Answer' : 'Question' }}</span>
                  <div v-html="renderMessage(message.content)"></div>
                </template>
                <template v-else>
                  <div class="answer-prose" v-html="renderMessage(message.content)"></div>
                  <section v-if="message.suggestedQuestions.length" class="suggested-questions-section" aria-label="Suggested questions">
                    <span>Suggested questions</span>
                    <div class="suggested-question-tags">
                      <button
                        v-for="question in message.suggestedQuestions"
                        :key="question"
                        type="button"
                        @click="draft = question"
                      >
                        {{ question }}
                      </button>
                    </div>
                  </section>
                </template>
              </article>
              <div v-if="isWaitingForFirstToken" class="thinking-indicator" role="status" aria-live="polite">
                <span class="loading-spinner" aria-hidden="true"></span>
                <span>{{ loadingLabel }}</span>
              </div>
            </template>
          </section>

          <form class="dialog-input" @submit.prevent="submitPrompt">
            <div class="dialog-toolbar" aria-label="Response style">
              <button
                v-for="style in responseStyles"
                :key="style.id"
                type="button"
                :class="{ active: selectedResponseStyleId === style.id }"
                :title="style.description || style.prompt"
                @click="toggleResponseStyle(style.id)"
              >
                {{ style.label }}
              </button>
            </div>
            <div class="input-row">
              <textarea
                v-model="draft"
                :placeholder="placeholder"
                :disabled="card.loading"
                rows="2"
                @keydown.enter.exact.prevent="submitPrompt"
              ></textarea>
              <button type="submit" :disabled="card.loading || !draft.trim()" :aria-label="card.loading ? loadingLabel : 'Send'">
                <svg width="13" height="13" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path d="M2 8L14 2L9.3 8L14 14L2 8Z" fill="currentColor"/>
                </svg>
              </button>
            </div>
          </form>
        </div>
      </div>
  </aside>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { buildApiUrl } from '../api/client'
import { copySelectionAsLatex } from '../utils/latexCopy'
import { deserializeMessages, renderMarkdown, renderMath as renderKatexMath } from '../utils/renderer'

const DEFAULT_RESPONSE_STYLES = [
  {
    id: 'cite',
    label: 'Cite mode',
    description: 'Answer with concise references to the selected text or current source.',
    prompt: 'Response style: Cite mode. Anchor the answer in the provided context, quote only short phrases when useful, and point out which part of the source supports each key claim.'
  },
  {
    id: 'summary',
    label: 'Summary',
    description: 'Give a compact summary first, then the minimum needed detail.',
    prompt: 'Response style: Summary. Start with a concise Chinese summary, then add only the essential mathematical details and definitions needed to understand it.'
  },
  {
    id: 'export',
    label: 'Export',
    description: 'Format the answer as reusable notes.',
    prompt: 'Response style: Export. Format the answer as clean reusable study notes in Markdown, with headings, formulas preserved, and no chatty filler.'
  }
]

const props = defineProps({
  mode: {
    type: String,
    default: 'note',
    validator: (value) => ['note', 'quiz'].includes(value)
  },
  card: {
    type: Object,
    default: null
  },
  chapterSummary: {
    type: String,
    default: ''
  },
  metadataInfo: {
    type: Object,
    default: null
  },
  standalone: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'send', 'go-source', 'delete'])

const draft = ref('')
const dialogRef = ref(null)
const messagesRef = ref(null)
const selectedTextRef = ref(null)
const chapterSummaryRef = ref(null)
const responseStyles = ref(DEFAULT_RESPONSE_STYLES)
const selectedResponseStyleId = ref('')

const isQuiz = computed(() => props.mode === 'quiz' || props.card?.type === 'quiz')
const isSelectionNote = computed(() => !isQuiz.value && props.card?.type === 'selection')
const isChapterNote = computed(() => !isQuiz.value && props.card?.type === 'chapter')
const canGoSource = computed(() => Boolean(props.metadataInfo?.bookId || props.card?.bookId || isSelectionNote.value))
const canDelete = computed(() => Boolean(props.card?.noteId))

const selectedText = computed(() => props.card?.selectedText || props.card?.selected_text || '')
const displayedChapterSummary = computed(() => props.card?.chapterSummary || props.card?.chapter_summary || props.chapterSummary)

const messages = computed(() => {
  if (!props.card) return []
  if (Array.isArray(props.card.messages)) return props.card.messages
  return deserializeMessages(props.card.noteContent || props.card.note_content || '')
})

const dialogTitle = computed(() => isQuiz.value ? 'Quiz' : 'Note')
const modeClass = computed(() => isQuiz.value ? 'quiz-mode' : 'note-mode')
const fallbackTitle = computed(() => isQuiz.value ? 'Quiz dialogue' : 'Conversation')

const metadata = computed(() => {
  const parts = [props.card?.scopeLabel, props.card?.sourceTitle || props.metadataInfo?.sourceTitle].filter(Boolean)
  return parts.join(' · ')
})

const modelLabel = computed(() => props.card?.model || props.card?.modelName || 'Reader AI')

const sourceCount = computed(() => {
  return [
    props.card?.sourceTitle || props.metadataInfo?.sourceTitle,
    selectedText.value,
    displayedChapterSummary.value
  ].filter(Boolean).length
})

const suggestedQuestionsFor = (message) => {
  if (message.role !== 'assistant') return []
  const sourceTitle = props.card?.sourceTitle || props.metadataInfo?.sourceTitle || '这一节'
  if (isQuiz.value) {
    return ['我的答案缺了哪一步？', '能给一个更短的解法吗？', '这题考察哪个定义？']
  }
  if (isSelectionNote.value) {
    return ['这段话的关键假设是什么？', '能用一个例子说明吗？', '它和前面的定义如何连接？']
  }
  return [`${sourceTitle} 的核心结论是什么？`, '这里最容易误解的点是什么？', '后续证明会用到哪一步？']
}

const displayMessages = computed(() => {
  return messages.value.map((message) => ({
    ...message,
    suggestedQuestions: String(message.content || '').trim()
      ? suggestedQuestionsFor(message)
      : []
  }))
})

const selectedResponseStyle = computed(() => (
  responseStyles.value.find((style) => style.id === selectedResponseStyleId.value) || null
))

const isWaitingForFirstToken = computed(() => {
  if (!props.card?.loading) return false
  const lastAssistant = [...messages.value].reverse().find((message) => message.role === 'assistant')
  return !String(lastAssistant?.content || '').trim()
})

const metadataFields = computed(() => {
  const info = props.metadataInfo || {}
  return [
    ['Book', info.bookTitle],
    ['Type', info.readerType],
    ['Chapter', info.chapterIndex || info.chapterId],
    ['Source', info.sourceTitle],
    ['Guide', info.guideId]
  ]
    .filter(([, value]) => value)
    .map(([label, value]) => ({ label, value }))
})

const placeholder = computed(() => {
  if (isQuiz.value) return 'Type your answer...'
  if (isChapterNote.value) return 'Ask about this chapter...'
  return 'Ask about this note...'
})

const emptyMessage = computed(() => {
  return 'Ask a question to continue this note.'
})

const showEmptyMessage = computed(() => !messages.value.length && !isQuiz.value)

const loadingLabel = computed(() => isQuiz.value ? 'Checking...' : 'Sending...')

const renderMessage = (messageContent) => renderMarkdown(messageContent)

const renderMath = () => {
  nextTick(() => {
    ;[messagesRef.value, selectedTextRef.value, chapterSummaryRef.value]
      .filter(Boolean)
      .forEach((element) => renderKatexMath(element))

    if (messagesRef.value && props.card?.loading) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

const handleLatexCopy = (event) => {
  copySelectionAsLatex(event, dialogRef.value)
}

const submitPrompt = () => {
  const prompt = draft.value.trim()
  if (!prompt || props.card?.loading) return
  emit('send', {
    prompt,
    responseStyleId: selectedResponseStyle.value?.id || '',
    responseStylePrompt: selectedResponseStyle.value?.prompt || ''
  })
  draft.value = ''
}

const normalizeResponseStyles = (rawStyles) => {
  if (!Array.isArray(rawStyles)) return DEFAULT_RESPONSE_STYLES
  return rawStyles
    .map((style) => ({
      id: String(style?.id || '').trim(),
      label: String(style?.label || '').trim(),
      description: String(style?.description || '').trim(),
      prompt: String(style?.prompt || '').trim()
    }))
    .filter((style) => style.id && style.label && style.prompt)
}

const loadResponseStyles = async () => {
  try {
    const response = await fetch(buildApiUrl('/config/conversation-styles.json'), { cache: 'no-store' })
    if (!response.ok) throw new Error('Failed to load response styles')
    responseStyles.value = normalizeResponseStyles(await response.json())
  } catch (_error) {
    responseStyles.value = DEFAULT_RESPONSE_STYLES
  }
}

const toggleResponseStyle = (styleId) => {
  selectedResponseStyleId.value = selectedResponseStyleId.value === styleId ? '' : styleId
}

watch(() => props.card?.id, () => {
  draft.value = ''
  renderMath()
})
watch(() => props.card?.noteContent, renderMath)
watch(() => props.card?.note_content, renderMath)
watch(() => props.card?.messages, renderMath, { deep: true })
watch(() => props.card?.selectedText, renderMath)
watch(() => props.card?.selected_text, renderMath)
watch(displayedChapterSummary, renderMath)

onMounted(() => {
  renderMath()
  loadResponseStyles()
  document.addEventListener('copy', handleLatexCopy)
})

onUnmounted(() => {
  document.removeEventListener('copy', handleLatexCopy)
})
</script>

<style scoped>
.conversation-dialog {
  position: fixed;
  top: 92px;
  left: 58%;
  z-index: 80;
  box-sizing: border-box;
  width: min(860px, calc(100vw - 2rem));
  height: min(680px, calc(100vh - 136px));
  border: 0.5px solid #d9d9d9;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.16);
  color: #1f2933;
  display: flex;
  flex-direction: row;
  overflow: hidden;
  transform: translateX(-50%);
  --dialog-bg-secondary: #f6f7f8;
  --dialog-border: #d9d9d9;
  --dialog-border-secondary: #b9bec5;
  --dialog-text-secondary: #5f6873;
  --dialog-text-tertiary: #8a929c;
  --dialog-blue: #185fa5;
  --dialog-blue-50: #e6f1fb;
  --dialog-blue-200: #b5d4f4;
  --dialog-blue-800: #0c447c;
}

.conversation-dialog.standalone {
  position: relative;
  top: auto;
  left: auto;
  width: 100%;
  height: 100vh;
  min-height: 100vh;
  margin: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
  transform: none;
}

.conversation-dialog *,
.conversation-dialog *::before,
.conversation-dialog *::after {
  box-sizing: border-box;
}

.dialog-header {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0;
  min-height: 40px;
  padding: 8px 14px;
  border-bottom: 0.5px solid var(--dialog-border);
  background: var(--dialog-bg-secondary);
}

.header-primary-row {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.conversation-dialog.standalone .dialog-header {
  width: min(780px, calc(100% - 48px));
  min-height: auto;
  margin: 0 auto;
  padding: 18px 20px 12px;
  border-bottom-color: rgba(102, 84, 66, 0.16);
  background: transparent;
}

.conversation-dialog.standalone .header-primary-row {
  align-items: flex-start;
}

.conversation-dialog.standalone .dialog-status-dot {
  margin-top: 0.42rem;
}

.header-copy {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.conversation-dialog.standalone .header-copy {
  flex: 1;
}

.header-title-row {
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.dialog-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--dialog-border-secondary);
  flex: 0 0 auto;
}

.mode-label {
  color: var(--dialog-text-tertiary);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  line-height: 1.2;
  text-transform: uppercase;
  white-space: nowrap;
}

.dialog-header strong {
  color: #20252b;
  font-size: 14px;
  font-weight: 500;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 15rem;
}

.conversation-dialog.standalone .dialog-header strong {
  display: -webkit-box;
  max-width: 100%;
  overflow: hidden;
  color: #25201a;
  font-size: 16px;
  white-space: normal;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.conversation-dialog.standalone .header-title-row {
  align-items: flex-start;
  flex-direction: column;
  gap: 4px;
}

.standalone-details {
  position: static;
  width: auto;
  margin: 0;
  padding: 0;
  border: 0;
}

.standalone-details summary {
  min-height: 30px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0.42rem 0.72rem;
  border: 0.5px solid rgba(102, 84, 66, 0.18);
  border-radius: 8px;
  background: rgba(255, 253, 249, 0.72);
  color: #75695d;
  cursor: pointer;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.3;
  list-style: none;
  transition: border-color 180ms ease, background-color 180ms ease, color 180ms ease;
}

.standalone-details summary::-webkit-details-marker {
  display: none;
}

.standalone-details summary::after {
  content: '⌄';
  color: #998a7b;
  font-size: 12px;
  transform: translateY(-1px);
  transition: transform 180ms ease;
}

.standalone-details[open] summary::after {
  transform: rotate(180deg) translateY(-1px);
}

.standalone-details summary:hover,
.standalone-details[open] summary {
  border-color: rgba(102, 84, 66, 0.32);
  background: #ffffff;
  color: #29231d;
}

.standalone-details summary small {
  color: #a09284;
  font: inherit;
  font-size: 10px;
}

.standalone-details-grid {
  position: absolute;
  top: calc(100% + 9px);
  right: 0;
  z-index: 30;
  width: min(34rem, calc(100vw - 3rem));
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px 24px;
  margin: 0;
  padding: 16px;
  border: 0.5px solid rgba(102, 84, 66, 0.2);
  border-radius: 12px;
  background: rgba(255, 253, 249, 0.98);
  box-shadow: 0 18px 44px rgba(45, 35, 24, 0.14);
  backdrop-filter: blur(16px);
}

.standalone-details-grid div {
  min-width: 0;
  display: grid;
  align-content: start;
  justify-items: start;
  gap: 4px;
  text-align: left;
}

.standalone-details-grid dt {
  width: 100%;
  margin: 0;
  color: #998a7b;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.08em;
  line-height: 1.2;
  text-align: left;
  text-transform: uppercase;
}

.standalone-details-grid dd {
  width: 100%;
  margin: 0;
  color: #554b42;
  font-size: 11px;
  line-height: 1.35;
  overflow-wrap: anywhere;
  text-align: left;
}

.standalone-actions {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.header-meta {
  margin: 0 0 0 auto;
  color: var(--dialog-text-tertiary);
  font-size: 11px;
  line-height: 1.2;
  white-space: nowrap;
}

.close-button {
  flex: 0 0 24px;
  width: 24px;
  height: 24px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--dialog-text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 1.1rem;
  line-height: 1;
}

.close-button:hover {
  border-color: var(--dialog-border);
  background: #ffffff;
  color: #20252b;
}

.dialog-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.conversation-dialog.standalone .dialog-content {
  background: transparent;
}

.dialog-context-sidebar {
  flex: 0 0 210px;
  min-width: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border-right: 0.5px solid var(--dialog-border);
  background: var(--dialog-bg-secondary);
}

.dialog-panel {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #ffffff;
}

.conversation-dialog.standalone .dialog-panel {
  background: transparent;
}

.metadata-grid {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 0.5px solid var(--dialog-border);
  border-radius: 8px;
  background: #ffffff;
  padding: 0.35rem 0.55rem;
}

.metadata-grid div {
  min-width: 0;
  padding: 0.42rem 0;
  border-bottom: 0.5px solid var(--dialog-border);
}

.metadata-grid div:last-child {
  border-bottom: 0;
}

.metadata-grid span {
  display: block;
  color: var(--dialog-text-tertiary);
  font-size: 0.68rem;
  font-weight: 500;
  line-height: 1.2;
  text-transform: uppercase;
}

.metadata-grid strong {
  display: block;
  margin-top: 0.2rem;
  color: #20252b;
  font-size: 0.82rem;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.question-block {
  margin: 0;
  border-left: 2px solid var(--dialog-border-secondary);
  border-radius: 0 8px 8px 0;
  background: var(--dialog-bg-secondary);
  color: #20252b;
  font-size: 14px;
  line-height: 1.5;
  padding: 8px 12px;
}

.question-block > span {
  display: block;
  margin-bottom: 4px;
  color: var(--dialog-text-tertiary);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  line-height: 1;
  text-transform: uppercase;
}

.question-context-details summary {
  display: block;
  margin-bottom: 4px;
  color: var(--dialog-text-tertiary);
  cursor: pointer;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  line-height: 1;
  list-style: none;
  text-transform: uppercase;
}

.question-context-details summary::-webkit-details-marker {
  display: none;
}

.question-context-details summary::after {
  content: 'Hide';
  margin-left: 8px;
  color: var(--dialog-text-secondary);
  font-size: 10px;
  font-weight: 400;
  letter-spacing: 0;
  text-transform: none;
}

.question-context-details:not([open]) summary {
  margin-bottom: 0;
}

.question-context-details:not([open]) summary::after {
  content: 'Show';
}

.question-block p,
.question-block :deep(p) {
  margin: 0;
}

.source-button {
  width: 100%;
  min-height: 24px;
  border: 0.5px solid var(--dialog-border);
  border-radius: 999px;
  background: var(--dialog-bg-secondary);
  color: var(--dialog-text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1;
  padding: 0.35rem 0.65rem;
}

.standalone-actions .source-button,
.standalone-actions .delete-conversation-button {
  width: auto;
  min-height: 30px;
  border-color: rgba(102, 84, 66, 0.18);
  background: rgba(255, 253, 249, 0.72);
  color: #5f554a;
  padding: 0.42rem 0.78rem;
}

.standalone-actions .source-button:hover,
.standalone-actions .delete-conversation-button:hover {
  border-color: rgba(102, 84, 66, 0.32);
  background: #ffffff;
  color: #29231d;
}

.source-button:hover {
  border-color: var(--dialog-border-secondary);
  background: #ffffff;
}

.delete-conversation-button {
  width: 100%;
  min-height: 24px;
  border: 0.5px solid var(--dialog-border);
  border-radius: 999px;
  background: var(--dialog-bg-secondary);
  color: var(--dialog-text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 500;
  line-height: 1;
  padding: 0.35rem 0.65rem;
}

.delete-conversation-button:hover {
  border-color: var(--dialog-border-secondary);
  background: #ffffff;
  color: #20252b;
}

.chapter-context {
  border: 0.5px solid var(--dialog-border);
  border-radius: 8px;
  background: var(--dialog-bg-secondary);
  padding: 0.65rem 0.7rem;
  color: #20252b;
}

.chapter-context h3 {
  margin: 0 0 0.35rem;
  color: var(--dialog-text-tertiary);
  font-size: 0.7rem;
  font-weight: 500;
  line-height: 1;
  text-transform: uppercase;
}

.chapter-context .latex-content {
  max-height: 7.5rem;
  overflow-y: auto;
  font-size: 0.88rem;
  line-height: 1.55;
}

.quiz-context {
  display: flex;
  flex-direction: column;
  gap: 0.22rem;
  border: 0.5px solid #9fe1cb;
  border-radius: 8px;
  background: #e1f5ee;
  padding: 0.62rem 0.7rem;
}

.quiz-context span {
  color: #085041;
  font-size: 0.7rem;
  font-weight: 500;
  line-height: 1;
  text-transform: uppercase;
}

.quiz-context strong {
  color: #04342c;
  font-size: 0.86rem;
  line-height: 1.35;
}

.message-list {
  flex: 1;
  min-height: 10rem;
  min-height: 0;
  overflow-y: auto;
  margin: 0.8rem 1rem;
  padding-right: 0.12rem;
  color: #20252b;
  font-size: 14px;
  line-height: 1.75;
}

.conversation-dialog.standalone .message-list {
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: 36px 24px 140px;
  color: #29231d;
  font-size: 15px;
  line-height: 1.78;
  scroll-padding-bottom: 140px;
}

.message-list.empty {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  color: var(--dialog-text-tertiary);
  min-height: 7rem;
}

.conversation-dialog.standalone .message-list.empty {
  min-height: 0;
}

.empty-message {
  margin: 0;
  color: var(--dialog-text-tertiary);
}

.chat-message {
  margin-bottom: 0.75rem;
}

.chat-user {
  color: #20252b;
}

.chat-ai {
  color: #20252b;
}

.answer-block {
  background: transparent;
  border: 0;
  padding: 0;
}

.answer-prose {
  font-size: 14px;
  line-height: 1.75;
}

.conversation-dialog.standalone .answer-prose {
  font-size: 15px;
  line-height: 1.78;
}

.answer-prose :deep(p) {
  margin: 0 0 0.75rem;
}

.answer-prose :deep(p:last-child) {
  margin-bottom: 0;
}

.thinking-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0.2rem 0 0.9rem;
  color: var(--dialog-text-tertiary);
  font-size: 12px;
  line-height: 1;
}

.loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--dialog-border);
  border-top-color: var(--dialog-blue);
  border-radius: 999px;
  animation: dialog-spin 0.8s linear infinite;
}

@keyframes dialog-spin {
  to {
    transform: rotate(360deg);
  }
}

.suggested-questions-section {
  margin-top: 0.95rem;
  padding-top: 0.75rem;
  border-top: 0.5px solid var(--dialog-border);
}

.suggested-questions-section > span {
  display: block;
  margin-bottom: 6px;
  color: var(--dialog-text-tertiary);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  line-height: 1;
  text-transform: uppercase;
}

.suggested-question-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.suggested-question-tags button {
  min-height: 24px;
  border: 0.5px solid var(--dialog-blue-200);
  border-radius: 999px;
  background: var(--dialog-blue-50);
  color: var(--dialog-blue-800);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  line-height: 1;
  padding: 3px 10px;
  text-align: left;
}

.suggested-question-tags button:hover {
  background: var(--dialog-blue-200);
}

.chat-message :deep(p),
.chapter-context :deep(p) {
  margin: 0 0 0.55rem;
}

.chat-message :deep(p:last-child),
.chapter-context :deep(p:last-child) {
  margin-bottom: 0;
}

.dialog-input {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 14px;
  border-top: 0.5px solid var(--dialog-border);
  background: #ffffff;
}

.conversation-dialog.standalone .dialog-input {
  position: sticky;
  bottom: 0;
  align-items: center;
  padding: 10px 24px 18px;
  border-top: 0;
  background: linear-gradient(180deg, rgba(247, 244, 238, 0), #f7f4ee 30%, #f7f4ee);
}

.conversation-dialog.standalone .dialog-toolbar,
.conversation-dialog.standalone .input-row {
  width: 100%;
  max-width: 760px;
}

.conversation-dialog.standalone .dialog-toolbar {
  justify-content: flex-start;
}

.dialog-toolbar {
  display: flex;
  gap: 6px;
}

.dialog-toolbar button {
  height: 24px;
  border: 0.5px solid var(--dialog-border);
  border-radius: 8px;
  background: var(--dialog-bg-secondary);
  color: var(--dialog-text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  line-height: 1;
  padding: 3px 8px;
}

.dialog-toolbar button:hover {
  border-color: var(--dialog-border-secondary);
  color: #20252b;
}

.dialog-toolbar button.active {
  border-color: var(--dialog-blue-200);
  background: var(--dialog-blue-50);
  color: var(--dialog-blue-800);
}

.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dialog-input textarea {
  flex: 1;
  min-width: 0;
  min-height: calc(2em + 16px);
  height: calc(2em + 16px);
  max-height: 6.5rem;
  resize: vertical;
  border: 0.5px solid var(--dialog-border);
  border-radius: 8px;
  background: var(--dialog-bg-secondary);
  color: #20252b;
  font: inherit;
  font-size: 13px;
  line-height: 1.35;
  padding: 8px 12px;
}

.conversation-dialog.standalone .dialog-input textarea {
  min-height: 58px;
  height: 58px;
  border-color: rgba(102, 84, 66, 0.18);
  border-radius: 18px;
  background: rgba(255, 253, 249, 0.94);
  box-shadow: 0 14px 34px rgba(45, 35, 24, 0.08);
  color: #29231d;
  font-size: 14px;
  line-height: 1.45;
  padding: 13px 16px;
}

.dialog-input textarea:focus {
  outline: none;
  border-color: var(--dialog-blue);
  box-shadow: 0 0 0 2px rgba(24, 95, 165, 0.12);
}

.dialog-input textarea:disabled {
  cursor: not-allowed;
  color: var(--dialog-text-tertiary);
}

.input-row > button {
  flex: 0 0 30px;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 8px;
  background: #20252b;
  color: #ffffff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

.input-row > button:disabled {
  cursor: not-allowed;
  background: #b9bec5;
}

.quiz-mode {
  border-color: #9fe1cb;
}

.quiz-mode .dialog-header {
  border-bottom-color: var(--dialog-border);
  background: var(--dialog-bg-secondary);
}

.quiz-mode .mode-label {
  color: #085041;
}

.quiz-mode .dialog-input {
  border-top-color: var(--dialog-border);
  background: #ffffff;
}

.quiz-mode .dialog-input textarea:focus {
  border-color: #1d9e75;
  box-shadow: 0 0 0 2px rgba(29, 158, 117, 0.14);
}

.quiz-mode .input-row > button {
  background: #20252b;
}

.standalone-context-card {
  margin: 0 0 1.35rem;
}

@media (max-width: 720px) {
  .conversation-dialog {
    top: auto;
    right: 0.75rem;
    bottom: 0.75rem;
    left: 0.75rem;
    width: auto;
    max-height: calc(100vh - 1.5rem);
    flex-direction: column;
    transform: none;
  }

  .conversation-dialog.standalone {
    width: 100%;
    height: 100vh;
    margin: 0;
  }

  .conversation-dialog.standalone .dialog-header {
    align-items: flex-start;
    min-height: auto;
    padding: 12px 16px;
  }

  .conversation-dialog.standalone .header-copy {
    flex: 1;
  }

  .standalone-actions {
    flex-wrap: wrap;
    justify-content: flex-end;
    max-width: 9rem;
  }

  .standalone-actions .source-button,
  .standalone-actions .delete-conversation-button {
    min-height: 28px;
    padding: 0.38rem 0.65rem;
  }

  .conversation-dialog.standalone .message-list {
    padding: 26px 16px 132px;
  }

  .conversation-dialog.standalone .dialog-input {
    padding: 8px 16px 14px;
  }

  .dialog-context-sidebar {
    flex: 0 0 auto;
    max-height: 32vh;
    border-right: 0;
    border-bottom: 0.5px solid var(--dialog-border);
  }

  .header-meta {
    display: none;
  }
}
</style>
