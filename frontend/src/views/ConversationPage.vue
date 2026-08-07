<template>
  <main class="conversation-page">
    <ConversationDialog
      v-if="card"
      standalone
      :mode="card.type === 'quiz' ? 'quiz' : 'note'"
      :card="card"
      :metadata-info="metadata"
      @send="handleSend"
      @regenerate="handleRegenerateQuiz"
      @go-source="handleGoSource"
      @delete="handleDelete"
    />
    <section v-else class="missing-conversation">
      <h1>Conversation not found</h1>
      <p>Open the note from the reader again.</p>
    </section>

    <div v-if="pendingDeleteTarget" class="modal-overlay confirm-overlay" @click.self="pendingDeleteTarget = null">
      <section class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-conversation-title">
        <p class="confirm-kicker">删除对话</p>
        <h2 id="delete-conversation-title">确定删除这段笔记对话？</h2>
        <p>已保存的问答内容会一并删除，此操作无法撤销。</p>
        <p v-if="deleteError" class="confirm-inline-error">{{ deleteError }}</p>
        <footer class="confirm-actions">
          <button type="button" class="secondary-btn" :disabled="deleting" @click="pendingDeleteTarget = null">取消</button>
          <button type="button" class="danger-btn" :disabled="deleting" @click="confirmDelete">
            {{ deleting ? '正在删除…' : '确认删除' }}
          </button>
        </footer>
      </section>
    </div>
  </main>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ConversationDialog from '../components/ConversationDialog.vue'
import { apiClient } from '../api/client'
import { useChat } from '../composables/useChat'
import { useBookStore } from '../stores/bookStore'
import { useLearningCards } from '../composables/useLearningCards'
import { appendWithTypewriter } from '../utils/typewriterStream'
import {
  buildConversationDocumentTitle,
  conversationStorageKey,
  loadConversationPayload,
  saveConversationPayload
} from '../utils/conversationMetadata'

const route = useRoute()
const { streamCardChat } = useChat()
const bookStore = useBookStore()
const { hydrateQuizQuestionCard } = useLearningCards()

const conversationId = String(route.params.conversationId || '')
const card = ref(null)
const contextText = ref('')
const metadata = ref({})
const mode = ref('note')
const quizRequest = ref(null)
const pendingDeleteTarget = ref(null)
const deleting = ref(false)
const deleteError = ref('')

const persist = (updatedCard = card.value) => {
  if (!conversationId || !updatedCard) return
  saveConversationPayload(conversationId, {
    mode: mode.value,
    card: updatedCard,
    contextText: contextText.value,
    metadata: metadata.value,
    quizRequest: quizRequest.value
  })
}

const updateTitle = () => {
  document.title = buildConversationDocumentTitle(card.value, metadata.value)
}

const handleSend = async (payload) => {
  if (!card.value) return
  const prompt = typeof payload === 'string' ? payload : payload?.prompt
  if (!prompt) return
  await streamCardChat(card.value, prompt, contextText.value, {
    responseStylePrompt: typeof payload === 'string' ? '' : payload?.responseStylePrompt,
    onUpdate: (updatedCard) => {
      persist(updatedCard)
      updateTitle()
    }
  })
  persist()
  updateTitle()
}

const quizErrorMessage = (error) => {
  return error?.response?.data?.detail || error?.message || '请稍后重试。'
}

const generateQuizQuestion = async () => {
  if (!card.value || !quizRequest.value?.chapterId || card.value.loading) return

  const request = quizRequest.value
  card.value.loading = true
  card.value.quizGenerating = true
  card.value.quizGenerationError = ''
  card.value.questionId = null
  card.value.questionText = ''
  card.value.questionSummary = '正在准备一道新题…'
  card.value.messages = [{ role: 'assistant', content: '' }]
  card.value.noteContent = ''
  persist()
  updateTitle()

  try {
    const question = await bookStore.fetchNextQuizQuestion(request.chapterId, {
      quizMode: request.quizMode || 'chapter',
      questionType: request.questionType || null,
      personalizationContext: request.personalizationContext || ''
    })
    const typeLabel = question?.question_type_label || question?.question_type || 'Quiz'
    let visibleQuestion = ''

    hydrateQuizQuestionCard(card.value, question, request.personalizationContext || '', {
      questionContent: '',
      questionSummary: `${typeLabel} · 正在呈现题目…`
    })
    card.value.loading = true
    card.value.quizGenerating = true
    persist()

    await appendWithTypewriter(question?.question_text || '请回答这道 Quiz。', (chunk) => {
      visibleQuestion += chunk
      hydrateQuizQuestionCard(card.value, question, request.personalizationContext || '', {
        questionContent: visibleQuestion,
        questionSummary: `${typeLabel} · 正在呈现题目…`
      })
      card.value.loading = true
      card.value.quizGenerating = true
      persist()
    }, { chunkSize: 3, intervalMs: 18 })

    hydrateQuizQuestionCard(card.value, question, request.personalizationContext || '')
    card.value.loading = false
    card.value.quizGenerating = false
    persist()
    updateTitle()

    if (card.value.noteId) {
      apiClient.put(`/notes/${card.value.noteId}`, {
        note_content: card.value.noteContent,
        title: card.value.questionSummary
      }).catch((error) => {
        console.error('Failed to persist regenerated Quiz question:', error)
      })
    }
  } catch (error) {
    card.value.loading = false
    card.value.quizGenerating = false
    card.value.quizGenerationError = quizErrorMessage(error)
    card.value.messages = []
    persist()
    updateTitle()
  }
}

const handleRegenerateQuiz = () => {
  generateQuizQuestion()
}

const handleGoSource = () => {
  if (!metadata.value?.bookId) return
  const params = new URLSearchParams()
  if (metadata.value.readerType) params.set('reader_type', metadata.value.readerType)
  if (metadata.value.chapterId) params.set('chapter_id', metadata.value.chapterId)
  if (metadata.value.guideId) params.set('guide_id', metadata.value.guideId)
  const query = params.toString()
  window.open(`/book/${metadata.value.bookId}${query ? `?${query}` : ''}`, '_blank', 'noopener')
}

const handleDelete = (target) => {
  if (!target?.noteId) return
  pendingDeleteTarget.value = target
  deleteError.value = ''
}

const confirmDelete = async () => {
  if (!pendingDeleteTarget.value || deleting.value) return
  const target = pendingDeleteTarget.value
  deleting.value = true
  deleteError.value = ''
  try {
    await bookStore.deleteNote(target.noteId)
    window.localStorage.removeItem(conversationStorageKey(conversationId))
    pendingDeleteTarget.value = null
    card.value = null
    document.title = 'Conversation not found'
  } catch (error) {
    deleteError.value = `删除失败：${error.message}`
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  const payload = loadConversationPayload(conversationId)
  if (!payload?.card) return

  card.value = reactive(payload.card)
  contextText.value = payload.contextText || ''
  metadata.value = payload.metadata || {}
  mode.value = payload.mode || 'note'
  quizRequest.value = payload.quizRequest || null
  updateTitle()
  if (mode.value === 'quiz' && quizRequest.value && (!card.value.questionId || card.value.quizGenerating)) {
    card.value.loading = false
    generateQuizQuestion()
  }
})

watch(card, () => {
  persist()
  updateTitle()
}, { deep: true })
</script>

<style scoped>
.conversation-page {
  width: 100%;
  min-height: 100vh;
  overflow: hidden;
  background:
    radial-gradient(circle at 50% -18%, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0) 32rem),
    #f7f4ee;
  color: #2c251f;
}

.missing-conversation {
  max-width: 34rem;
  margin: 5rem auto;
  padding: 0 1rem;
}

.missing-conversation h1 {
  margin: 0;
  color: #201a15;
  font-size: 1.4rem;
  line-height: 1.25;
}

.missing-conversation p {
  margin: 0.7rem 0 0;
  color: #7a6c5d;
  font-size: 0.95rem;
  line-height: 1.5;
}
</style>
