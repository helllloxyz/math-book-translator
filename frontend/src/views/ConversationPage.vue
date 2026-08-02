<template>
  <main class="conversation-page">
    <ConversationDialog
      v-if="card"
      standalone
      :mode="card.type === 'quiz' ? 'quiz' : 'note'"
      :card="card"
      :chapter-summary="chapterSummary"
      :metadata-info="metadata"
      @send="handleSend"
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
import { useChat } from '../composables/useChat'
import { useBookStore } from '../stores/bookStore'
import {
  buildConversationDocumentTitle,
  conversationStorageKey,
  loadConversationPayload,
  saveConversationPayload
} from '../utils/conversationMetadata'

const route = useRoute()
const { streamCardChat } = useChat()
const bookStore = useBookStore()

const conversationId = String(route.params.conversationId || '')
const card = ref(null)
const contextText = ref('')
const chapterSummary = ref('')
const metadata = ref({})
const mode = ref('note')
const pendingDeleteTarget = ref(null)
const deleting = ref(false)
const deleteError = ref('')

const persist = (updatedCard = card.value) => {
  if (!conversationId || !updatedCard) return
  saveConversationPayload(conversationId, {
    mode: mode.value,
    card: updatedCard,
    contextText: contextText.value,
    chapterSummary: chapterSummary.value,
    metadata: metadata.value
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
  chapterSummary.value = payload.chapterSummary || ''
  metadata.value = payload.metadata || {}
  mode.value = payload.mode || 'note'
  updateTitle()
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
