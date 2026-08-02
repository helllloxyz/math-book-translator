<template>
  <div class="notes-page">
    <header class="page-header" ref="headerRef">
      <div class="header-content">
        <div class="notes-breadcrumbs">
          <router-link :to="{ name: 'reader', params: { id: bookId } }" class="back-link">← 返回阅读器</router-link>
          <router-link to="/" class="library-inline-link">图书馆</router-link>
        </div>
        <p class="page-kicker">READING NOTES</p>
        <h1>{{ book?.title || '正在加载…' }}</h1>
        <p class="page-description">从笔记回到对应章节，继续阅读、提问和复习。</p>
      </div>
    </header>

    <div class="notes-container">
      <div v-if="loading" class="notes-loading-state" aria-label="正在加载笔记">
        <div v-for="index in 3" :key="index" class="note-skeleton" aria-hidden="true">
          <span></span><span></span><span></span>
        </div>
      </div>
      <section v-else-if="error" class="error-state notes-feedback-state">
        <p>{{ error }}</p>
        <button type="button" class="secondary-btn" @click="fetchNotes">重新加载</button>
      </section>
      <section v-else-if="notes.length === 0" class="empty-state notes-feedback-state">
        <span class="empty-note-symbol" aria-hidden="true">¶</span>
        <h2>还没有笔记</h2>
        <p>回到阅读器，选中一段文字提问，或创建一条章节笔记。</p>
        <router-link :to="{ name: 'reader', params: { id: bookId } }" class="primary-link">返回阅读器</router-link>
      </section>
      
      <div v-else class="notes-grid">
        <NoteCard 
            v-for="(note, idx) in notes" 
            :key="note.id" 
            :note="note"
            class="page-note-card"
            @delete="pendingDeleteNote = note"
            @chat="handleNoteChat(note, $event)"
            @open-source="openNoteSource(note)"
          />
      </div>
    </div>

    <Transition name="toast">
      <div v-if="notification" class="app-toast" :class="`toast-${notification.type}`" role="status" aria-live="polite">
        <span>{{ notification.message }}</span>
        <button type="button" aria-label="关闭提示" @click="notification = null">×</button>
      </div>
    </Transition>

    <div v-if="pendingDeleteNote" class="modal-overlay confirm-overlay" @click.self="pendingDeleteNote = null">
      <section class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-note-title">
        <p class="confirm-kicker">删除笔记</p>
        <h2 id="delete-note-title">确定删除这条笔记？</h2>
        <p>笔记中的对话内容会一并删除，此操作无法撤销。</p>
        <footer class="confirm-actions">
          <button type="button" class="secondary-btn" @click="pendingDeleteNote = null">取消</button>
          <button type="button" class="danger-btn" :disabled="deletingNote" @click="handleDeleteNote">
            {{ deletingNote ? '正在删除…' : '确认删除' }}
          </button>
        </footer>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBookStore } from '../stores/bookStore'
import { useChat } from '../composables/useChat'
import { renderMath } from '../utils/renderer'
import NoteCard from '../components/NoteCard.vue'

const route = useRoute()
const router = useRouter()
const bookStore = useBookStore()
const { streamChat } = useChat()
const bookId = route.params.id

const notes = ref([])
const loading = ref(true)
const error = ref(null)
const headerRef = ref(null)
const pendingDeleteNote = ref(null)
const deletingNote = ref(false)
const notification = ref(null)
let notificationTimer = null

const book = computed(() => bookStore.books.find(b => b.id == bookId) || bookStore.currentBook)

const triggerRenderMath = () => {
  nextTick(() => {
    if (headerRef.value) {
      renderMath(headerRef.value)
    }
  })
}

onMounted(async () => {
  if (!book.value) {
      await bookStore.fetchBookDetails(bookId)
  }
  fetchNotes()
  triggerRenderMath()
})

onBeforeUnmount(() => {
  if (notificationTimer) window.clearTimeout(notificationTimer)
})

watch(book, triggerRenderMath)

const fetchNotes = async () => {
    loading.value = true
    error.value = null
    try {
        notes.value = await bookStore.fetchBookNotes(bookId)
    } catch (e) {
        error.value = `笔记加载失败：${e.message}`
    } finally {
        loading.value = false
    }
}

const showNotification = (message, type = 'info') => {
  if (notificationTimer) window.clearTimeout(notificationTimer)
  notification.value = { message, type }
  notificationTimer = window.setTimeout(() => {
    notification.value = null
    notificationTimer = null
  }, 4200)
}

const openNoteSource = async (note) => {
  await router.push({
    name: 'reader',
    params: { id: bookId },
    query: {
      reader_type: 'chapter',
      chapter_id: note.chapter_id,
      note_id: note.id
    }
  })
}

const handleDeleteNote = async () => {
  if (!pendingDeleteNote.value || deletingNote.value) return
  const note = pendingDeleteNote.value
  deletingNote.value = true
  try {
    await bookStore.deleteNote(note.id)
    notes.value = notes.value.filter(n => n.id !== note.id)
    pendingDeleteNote.value = null
    showNotification('笔记已删除', 'success')
  } catch (e) {
    showNotification(`笔记删除失败：${e.message}`, 'error')
  } finally {
    deletingNote.value = false
  }
}

const handleNoteChat = async (note, userPrompt) => {
    // Current chapter ID is not strictly needed here for existing notes 
    // but useChat expects it for /note command new note creation.
    // Existing notes already have an ID.
    await streamChat(note, userPrompt, note.chapter_id)
}
</script>

<style scoped>
.notes-page {
    min-height: 100vh;
    background: #fcfcfc;
}

.page-header {
    background: white;
    padding: 1.5rem 2rem;
    border-bottom: 1px solid #eee;
    margin-bottom: 2rem;
}

.header-content {
    max-width: 1000px;
    margin: 0 auto;
}

.back-link {
    text-decoration: none;
    color: #666;
    font-size: 0.9rem;
    display: inline-block;
    margin-bottom: 0.5rem;
}

.back-link:hover {
    color: var(--primary-color);
}

h1 {
    margin: 0;
    color: var(--primary-color);
    font-size: 1.8rem;
}

.notes-container {
    max-width: 1000px;
    margin: 0 auto;
    padding: 0 2rem 4rem 2rem;
}

.notes-grid {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.page-note-card {
    position: relative !important;
    top: auto !important;
    width: 100%;
}

.loading-state, .error-state, .empty-state {
    text-align: center;
    padding: 3rem;
    color: #888;
    font-size: 1.1rem;
}

.error-state {
    color: #d32f2f;
}
</style>
