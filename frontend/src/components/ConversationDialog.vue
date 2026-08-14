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
          title="Go to source"
          aria-label="Go to source"
          @click="emit('go-source', card)"
        >
          <svg class="action-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4H6.5A2.5 2.5 0 0 0 4 6.5z" /><path d="M4 6.5v13" /></svg>
        </button>

        <button
          v-if="canDelete"
          type="button"
          class="delete-conversation-button"
          title="Delete"
          aria-label="Delete"
          @click="emit('delete', card)"
        >
          <svg class="action-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7l1-3h4l1 3" /></svg>
        </button>

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
                v-if="isQuiz"
                type="button"
                class="regenerate-quiz-button"
                :disabled="card.loading"
                title="出新题"
                aria-label="出新题"
                @click="emit('regenerate')"
              >
                <svg class="action-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.34 5.66" /><path d="M20 4v7h-7" /></svg>
                <span>出新题</span>
              </button>
              <button
                v-if="canGoSource"
                type="button"
                class="source-button"
                title="Go to source"
                aria-label="Go to source"
                @click="emit('go-source', card)"
              >
                <svg class="action-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4H6.5A2.5 2.5 0 0 0 4 6.5z" /><path d="M4 6.5v13" /></svg>
              </button>

              <details class="standalone-details" title="详细信息">
                <summary aria-label="详细信息">
                  <svg class="action-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5" /><path d="M12 10.5v5M12 7.5h.01" /></svg>
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
                title="Delete"
                aria-label="Delete"
                @click="emit('delete', card)"
              >
                <svg class="action-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7l1-3h4l1 3" /></svg>
              </button>
            </div>
            <button v-if="!standalone" type="button" class="close-button" aria-label="Close conversation" @click="emit('close')">
              ×
            </button>
          </div>
        </header>

        <div class="dialog-content">
          <section ref="messagesRef" class="message-list latex-content" :class="{ empty: !messages.length && !selectedText && !quizCandidates.length }">
            <details
              v-if="isSelectionNote && selectedText"
              class="question-block latex-content question-context-details"
              open
            >
              <summary>Selected context</summary>
              <div class="question-context-content" v-html="renderMessage(selectedText)"></div>
            </details>
            <p v-if="showEmptyMessage" class="empty-message">{{ emptyMessage }}</p>
            <template v-else>
              <details
                v-if="isQuiz && quizCandidates.length"
                class="quiz-candidate-pool"
                :open="!card.questionId"
              >
                <summary>
                  <span>本轮题库</span>
                  <strong>{{ quizCandidates.length }} 道候选题</strong>
                  <em>{{ card.questionId ? '已选择，点击可展开' : '请选一题作答' }}</em>
                </summary>
                <div class="quiz-candidate-list">
                  <button
                    v-for="(question, candidateIndex) in quizCandidates"
                    :key="question.id"
                    type="button"
                    class="quiz-candidate"
                    :class="{ selected: question.id === card.questionId }"
                    :disabled="card.loading || quizSelectionLocked"
                    :aria-pressed="question.id === card.questionId"
                    @click="emit('select-question', question)"
                  >
                    <span class="candidate-number">{{ String(candidateIndex + 1).padStart(2, '0') }}</span>
                    <div class="candidate-copy">
                      <small>{{ question.question_type_label || question.question_type }}</small>
                      <div
                        class="candidate-text"
                        :class="{ typing: isCandidateTyping(question) }"
                        v-html="renderMessage(question.display_text || question.question_text)"
                      ></div>
                    </div>
                    <span class="candidate-action">{{ question.id === card.questionId ? '已选' : '回答这题' }}</span>
                  </button>
                </div>
              </details>
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
                  <div class="answer-prose" :class="{ 'typewriter-active': isTypingMessage(index, message) }" v-html="renderMessage(message.content)"></div>
                  <section v-if="message.suggestedQuestions.length" class="suggested-questions-section" aria-label="Suggested questions">
                    <span>Suggested questions</span>
                    <div class="suggested-question-tags">
                      <button
                        v-for="question in message.suggestedQuestions"
                        :key="question"
                        type="button"
                        @click="draft = question"
                        v-html="renderInlineMarkdown(question)"
                      ></button>
                    </div>
                  </section>
                </template>
              </article>
              <div v-if="isWaitingForFirstToken" class="thinking-indicator" role="status" aria-live="polite">
                <span class="loading-spinner" aria-hidden="true"></span>
                <span>{{ loadingLabel }}</span>
              </div>
              <div v-if="isQuiz && card.quizGenerationError" class="quiz-generation-error" role="alert">
                <strong>这次出题没成功</strong>
                <p>{{ card.quizGenerationError }}</p>
                <button type="button" @click="emit('regenerate')">再试一次</button>
              </div>
            </template>
          </section>

          <form class="dialog-input" @submit.prevent="submitPrompt">
            <p v-if="isQuiz" class="quiz-answer-guidance">
              <strong>{{ quizTypeLabel }}</strong>
              <span>{{ answerGuidance }}</span>
            </p>
            <div v-if="!isQuiz" class="dialog-toolbar" aria-label="Response style">
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
                ref="composerRef"
                v-model="draft"
                :placeholder="placeholder"
                :disabled="card.loading || quizQuestionUnavailable"
                rows="2"
                @keydown.enter.exact.prevent="submitPrompt"
              ></textarea>
              <button type="submit" :disabled="card.loading || quizQuestionUnavailable || !draft.trim()" :aria-label="card.loading ? loadingLabel : 'Send'">
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
import { deserializeMessages, renderInlineMarkdown, renderMarkdown } from '../utils/renderer'

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

const COMPOSER_MAX_LINES = 12

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
  metadataInfo: {
    type: Object,
    default: null
  },
  standalone: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'send', 'regenerate', 'select-question', 'go-source', 'delete'])

const draft = ref('')
const dialogRef = ref(null)
const messagesRef = ref(null)
const composerRef = ref(null)
const responseStyles = ref(DEFAULT_RESPONSE_STYLES)
const selectedResponseStyleId = ref('')

const isQuiz = computed(() => props.mode === 'quiz' || props.card?.type === 'quiz')
const isSelectionNote = computed(() => !isQuiz.value && props.card?.type === 'selection')
const isChapterNote = computed(() => !isQuiz.value && props.card?.type === 'chapter')
const canGoSource = computed(() => Boolean(props.metadataInfo?.bookId || props.card?.bookId || isSelectionNote.value))
const canDelete = computed(() => Boolean(props.card?.noteId))

const selectedText = computed(() => props.card?.selectedText || props.card?.selected_text || '')

const messages = computed(() => {
  if (!props.card) return []
  if (Array.isArray(props.card.messages)) return props.card.messages
  return deserializeMessages(props.card.noteContent || props.card.note_content || '')
})

const quizCandidates = computed(() => (
  Array.isArray(props.card?.quizCandidates) ? props.card.quizCandidates : []
))

const quizSelectionLocked = computed(() => (
  messages.value.some(message => message?.role === 'user')
))

const dialogTitle = computed(() => {
  if (!isQuiz.value) return 'Note'
  return props.card?.quizMode === 'book' ? '全书复习 Quiz' : '章节讲解 Quiz'
})
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
    selectedText.value
  ].filter(Boolean).length
})

const suggestedQuestionsFor = (message) => {
  if (message.role !== 'assistant' || isQuiz.value) return []
  if (!Array.isArray(message.suggestedQuestions)) return []
  return message.suggestedQuestions
    .map(question => String(question || '').trim())
    .filter(Boolean)
    .slice(0, 3)
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
  if (isQuiz.value && quizCandidates.value.some(question => String(question?.display_text || '').trim())) return false
  const lastAssistant = [...messages.value].reverse().find((message) => message.role === 'assistant')
  return !String(lastAssistant?.content || '').trim()
})

const quizQuestionUnavailable = computed(() => (
  isQuiz.value && (!props.card?.questionId || Boolean(props.card?.quizGenerationError))
))

const isTypingMessage = (index, message) => (
  Boolean(props.card?.quizGenerating)
  && message?.role === 'assistant'
  && index === displayMessages.value.length - 1
  && Boolean(String(message?.content || '').trim())
)

const isCandidateTyping = (question) => (
  Boolean(props.card?.quizGenerating)
  && String(question?.display_text || '') !== String(question?.question_text || '')
)

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
  if (isQuiz.value && props.card?.quizGenerationError) return '出新题后即可作答'
  if (isQuiz.value && props.card?.quizGenerating) return '题目生成中…'
  if (isQuiz.value && !props.card?.questionId) return '请先从上方选择一道题…'
  if (isQuiz.value) return '用自己的话讲讲，不必输入公式…'
  if (isChapterNote.value) return 'Ask about this chapter...'
  return 'Ask about this note...'
})

const quizTypeLabel = computed(() => props.card?.questionTypeLabel || '自然语言讲解')
const answerGuidance = computed(() => (
  props.card?.answerGuidance || '请像向同学讲解一样回答；重点说清理解和思路，不要求输入公式。'
))

const emptyMessage = computed(() => {
  return 'Ask a question to continue this note.'
})

const resetDraft = () => {
  draft.value = messages.value.length ? '' : String(props.card?.initialPrompt || '')
}

const showEmptyMessage = computed(() => !messages.value.length && !isQuiz.value)

const loadingLabel = computed(() => {
  if (isQuiz.value && props.card?.quizGenerating) return '正在为你准备题目…'
  return isQuiz.value ? '正在检查回答…' : 'Sending...'
})

const renderMessage = (messageContent) => renderMarkdown(messageContent)

const syncMessageScroll = () => {
  nextTick(() => {
    if (messagesRef.value && props.card?.loading) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

const resizeComposer = () => {
  nextTick(() => {
    const composer = composerRef.value
    if (!composer) return
    const styles = window.getComputedStyle(composer)
    const lineHeight = Number.parseFloat(styles.lineHeight)
      || Number.parseFloat(styles.fontSize) * 1.4
    const verticalPadding = Number.parseFloat(styles.paddingTop) + Number.parseFloat(styles.paddingBottom)
    const verticalBorder = Number.parseFloat(styles.borderTopWidth) + Number.parseFloat(styles.borderBottomWidth)
    const maxHeight = lineHeight * COMPOSER_MAX_LINES + verticalPadding + verticalBorder
    composer.style.height = 'auto'
    const naturalHeight = composer.scrollHeight + verticalBorder
    composer.style.maxHeight = `${maxHeight}px`
    composer.style.height = `${Math.min(naturalHeight, maxHeight)}px`
    composer.style.overflowY = naturalHeight > maxHeight ? 'auto' : 'hidden'
  })
}

const handleLatexCopy = (event) => {
  copySelectionAsLatex(event, dialogRef.value)
}

const submitPrompt = () => {
  const prompt = draft.value.trim()
  if (!prompt || props.card?.loading) return
  draft.value = ''
  emit('send', {
    prompt,
    responseStyleId: selectedResponseStyle.value?.id || '',
    responseStylePrompt: selectedResponseStyle.value?.prompt || ''
  })
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
  resetDraft()
  syncMessageScroll()
})
watch(() => props.card?.noteContent, syncMessageScroll)
watch(() => props.card?.note_content, syncMessageScroll)
watch(() => props.card?.messages, syncMessageScroll, { deep: true })
watch(draft, resizeComposer, { flush: 'post' })

onMounted(() => {
  resetDraft()
  syncMessageScroll()
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
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0.5px solid rgba(102, 84, 66, 0.18);
  border-radius: 8px;
  background: rgba(255, 253, 249, 0.72);
  color: #75695d;
  cursor: pointer;
  list-style: none;
  transition: border-color 180ms ease, background-color 180ms ease, color 180ms ease;
}

.standalone-details summary::-webkit-details-marker {
  display: none;
}

.standalone-details summary:hover,
.standalone-details[open] summary {
  border-color: rgba(102, 84, 66, 0.32);
  background: #ffffff;
  color: #29231d;
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

.regenerate-quiz-button {
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  border: 0.5px solid rgba(8, 80, 65, 0.24);
  border-radius: 999px;
  background: rgba(225, 245, 238, 0.76);
  color: #085041;
  cursor: pointer;
  font: inherit;
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.01em;
  transition: background-color 160ms ease, border-color 160ms ease, opacity 160ms ease;
}

.regenerate-quiz-button:hover:not(:disabled) {
  border-color: rgba(8, 80, 65, 0.42);
  background: #d3f0e6;
}

.regenerate-quiz-button:disabled {
  cursor: wait;
  opacity: 0.48;
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

.question-context-content :deep(p) {
  margin: 0;
}

.quiz-candidate-pool {
  margin: 0 0 1.6rem;
  border: 0.5px solid rgba(8, 80, 65, 0.2);
  border-radius: 14px;
  background: rgba(250, 252, 248, 0.72);
  overflow: hidden;
}

.quiz-candidate-pool > summary {
  min-height: 52px;
  display: grid;
  grid-template-columns: auto auto 1fr;
  align-items: baseline;
  gap: 8px;
  padding: 13px 15px;
  color: #28594d;
  cursor: pointer;
  list-style: none;
}

.quiz-candidate-pool > summary::-webkit-details-marker {
  display: none;
}

.quiz-candidate-pool > summary span {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.quiz-candidate-pool > summary strong {
  color: #173f36;
  font-size: 13px;
  font-weight: 650;
}

.quiz-candidate-pool > summary em {
  justify-self: end;
  color: #71847e;
  font-size: 11px;
  font-style: normal;
}

.quiz-candidate-list {
  display: grid;
  gap: 0;
  padding: 0 8px 8px;
}

.quiz-candidate {
  width: 100%;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: start;
  gap: 11px;
  padding: 14px 10px;
  border: 0;
  border-top: 0.5px solid rgba(8, 80, 65, 0.12);
  background: transparent;
  color: #29231d;
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.quiz-candidate:first-child {
  border-top-color: transparent;
}

.quiz-candidate:hover:not(:disabled),
.quiz-candidate.selected {
  border-radius: 10px;
  background: #edf7f2;
  box-shadow: inset 2px 0 #1d9e75;
}

.quiz-candidate:disabled {
  cursor: default;
}

.candidate-number {
  padding-top: 3px;
  color: #7e928b;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11px;
  letter-spacing: 0.04em;
}

.candidate-copy {
  min-width: 0;
  display: grid;
  gap: 5px;
}

.candidate-copy small {
  color: #397365;
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.04em;
}

.candidate-text {
  color: #29231d;
  font-size: 14px;
  line-height: 1.65;
}

.candidate-text :deep(p) {
  margin: 0;
}

.candidate-text.typing::after {
  content: '';
  display: inline-block;
  width: 0.38em;
  height: 1em;
  margin-left: 0.16em;
  border-radius: 2px;
  background: #1d9e75;
  vertical-align: -0.12em;
  animation: quiz-caret 0.78s steps(1, end) infinite;
}

.candidate-action {
  align-self: center;
  min-width: 4.8rem;
  padding: 5px 9px;
  border: 0.5px solid rgba(8, 80, 65, 0.2);
  border-radius: 999px;
  color: #28594d;
  font-size: 11px;
  font-weight: 650;
  text-align: center;
}

.quiz-candidate.selected .candidate-action {
  border-color: #1d9e75;
  background: #1d9e75;
  color: #ffffff;
}

.source-button {
  width: 32px;
  height: 32px;
  display: inline-grid;
  place-items: center;
  border: 0.5px solid var(--dialog-border);
  border-radius: 8px;
  background: var(--dialog-bg-secondary);
  color: var(--dialog-text-secondary);
  cursor: pointer;
  padding: 0;
}

.standalone-actions .source-button,
.standalone-actions .delete-conversation-button {
  width: 30px;
  height: 30px;
  border-color: rgba(102, 84, 66, 0.18);
  background: rgba(255, 253, 249, 0.72);
  color: #5f554a;
  padding: 0;
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
  width: 32px;
  height: 32px;
  display: inline-grid;
  place-items: center;
  border: 0.5px solid var(--dialog-border);
  border-radius: 8px;
  background: var(--dialog-bg-secondary);
  color: var(--dialog-text-secondary);
  cursor: pointer;
  padding: 0;
}

.action-icon {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
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

.typewriter-active::after {
  content: '';
  display: inline-block;
  width: 0.45em;
  height: 1.05em;
  margin-left: 0.18em;
  border-radius: 2px;
  background: #1d9e75;
  vertical-align: -0.14em;
  animation: quiz-caret 0.78s steps(1, end) infinite;
}

@keyframes quiz-caret {
  50% { opacity: 0; }
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

.quiz-generation-error {
  max-width: 34rem;
  padding: 16px 18px;
  border: 0.5px solid rgba(150, 72, 45, 0.22);
  border-radius: 12px;
  background: rgba(255, 247, 241, 0.88);
  color: #6d3524;
}

.quiz-generation-error strong,
.quiz-generation-error p {
  display: block;
  margin: 0;
}

.quiz-generation-error p {
  margin-top: 5px;
  color: #82513f;
  font-size: 13px;
}

.quiz-generation-error button {
  margin-top: 12px;
  padding: 6px 11px;
  border: 0;
  border-radius: 999px;
  background: #6d3524;
  color: #fffaf6;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
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
  max-height: 18rem;
  overflow-y: hidden;
  resize: none;
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
  height: auto;
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

.quiz-answer-guidance {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  margin: 0 0 0.55rem;
  color: #39635a;
  font-size: 0.78rem;
  line-height: 1.45;
}

.quiz-answer-guidance strong {
  flex: 0 0 auto;
  color: #085041;
  font-weight: 650;
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

  .quiz-candidate-pool > summary {
    grid-template-columns: auto 1fr;
  }

  .quiz-candidate-pool > summary em {
    display: none;
  }

  .quiz-candidate {
    grid-template-columns: 26px minmax(0, 1fr);
  }

  .candidate-action {
    grid-column: 2;
    justify-self: start;
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
