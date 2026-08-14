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
        <p class="page-description">分别查看阅读笔记、Quiz 对话和原文标记，再回到对应章节继续阅读。</p>
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
      <template v-else>
        <nav class="notes-tabs" aria-label="阅读记录分类">
          <button
            v-for="category in NOTE_CATEGORIES"
            :key="category.id"
            type="button"
            class="notes-tab"
            :class="{ active: activeCategory === category.id }"
            :aria-pressed="activeCategory === category.id"
            @click="selectCategory(category.id)"
          >
            <span>{{ category.label }}</span>
            <span class="tab-count">{{ categoryCounts[category.id] }}</span>
          </button>
        </nav>

        <section v-if="filteredNotes.length === 0" class="empty-state notes-feedback-state">
          <span class="empty-note-symbol" aria-hidden="true">{{ activeCategoryCopy.symbol }}</span>
          <h2>{{ activeCategoryCopy.title }}</h2>
          <p>{{ activeCategoryCopy.description }}</p>
          <router-link :to="{ name: 'reader', params: { id: bookId } }" class="primary-link">返回阅读器</router-link>
        </section>

        <div v-else class="notes-grid">
          <template v-for="note in filteredNotes" :key="note.id">
            <AnnotationCard
              v-if="note.type === 'annotation'"
              :note="note"
              :style="annotationStyle(note)"
              @delete="pendingDeleteNote = note"
              @open-source="openNoteSource(note)"
            />
            <NoteCard
              v-else
              :note="note"
              class="page-note-card"
              @delete="pendingDeleteNote = note"
              @chat="handleNoteChat(note, $event)"
              @open-source="openNoteSource(note)"
            />
          </template>
        </div>
      </template>
    </div>

    <Transition name="toast">
      <div v-if="notification" class="app-toast" :class="`toast-${notification.type}`" role="status" aria-live="polite">
        <span>{{ notification.message }}</span>
        <button type="button" aria-label="关闭提示" @click="notification = null">×</button>
      </div>
    </Transition>

    <div v-if="pendingDeleteNote" class="modal-overlay confirm-overlay" @click.self="pendingDeleteNote = null">
      <section class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-note-title">
        <p class="confirm-kicker">删除{{ pendingDeleteLabel }}</p>
        <h2 id="delete-note-title">确定删除这条{{ pendingDeleteLabel }}？</h2>
        <p>{{ pendingDeleteDescription }}，此操作无法撤销。</p>
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
import {
  NOTE_CATEGORIES,
  annotationStyle,
  noteCategory,
  noteCategoryCounts,
  normalizeNoteCategory,
  notesInCategory
} from '../utils/noteCategories'
import AnnotationCard from '../components/AnnotationCard.vue'
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
const activeCategory = ref(normalizeNoteCategory(route.query.tab))
const filteredNotes = computed(() => notesInCategory(notes.value, activeCategory.value))
const categoryCounts = computed(() => noteCategoryCounts(notes.value))
const activeCategoryDefinition = computed(() => (
  NOTE_CATEGORIES.find(category => category.id === activeCategory.value) || NOTE_CATEGORIES[0]
))
const activeCategoryCopy = computed(() => ({
  notes: {
    symbol: '¶',
    title: '还没有笔记',
    description: '选中一段文字提问，或创建一条章节笔记。'
  },
  quiz: {
    symbol: '?',
    title: '还没有 Quiz 记录',
    description: '从阅读器开始 Quiz，保存后的对话会集中显示在这里。'
  },
  marks: {
    symbol: '⌖',
    title: '还没有标记',
    description: '在阅读器中选中文本，可以添加高亮或下划线。'
  }
}[activeCategory.value]))
const pendingDeleteLabel = computed(() => {
  const category = noteCategory(pendingDeleteNote.value)
  return category === 'quiz' ? 'Quiz 记录' : (category === 'marks' ? '标记' : '笔记')
})
const pendingDeleteDescription = computed(() => (
  noteCategory(pendingDeleteNote.value) === 'marks'
    ? '原文中对应的高亮或下划线也会一并移除'
    : '其中的对话内容会一并删除'
))

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

watch(() => route.query.tab, (category) => {
  activeCategory.value = normalizeNoteCategory(category)
})

const selectCategory = async (category) => {
  const normalizedCategory = normalizeNoteCategory(category)
  activeCategory.value = normalizedCategory
  const query = { ...route.query }
  if (normalizedCategory === 'notes') delete query.tab
  else query.tab = normalizedCategory
  await router.replace({ query })
}

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

const openNoteSource = (note) => {
  const sourceRoute = router.resolve({
    name: 'reader',
    params: { id: bookId },
    query: {
      reader_type: 'chapter',
      chapter_id: note.chapter_id,
      note_id: note.id
    }
  })
  window.open(sourceRoute.href, '_blank', 'noopener,noreferrer')
}

const handleDeleteNote = async () => {
  if (!pendingDeleteNote.value || deletingNote.value) return
  const note = pendingDeleteNote.value
  deletingNote.value = true
  try {
    await bookStore.deleteNote(note.id)
    notes.value = notes.value.filter(n => n.id !== note.id)
    pendingDeleteNote.value = null
    showNotification(`${activeCategoryDefinition.value.label} 已删除`, 'success')
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

.notes-tabs {
    display: flex;
    gap: 0.4rem;
    margin-bottom: 1.25rem;
    padding-bottom: 0.7rem;
    border-bottom: 1px solid var(--color-line);
}

.notes-tab {
    min-height: 38px;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.8rem;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    color: var(--color-muted);
    background: transparent;
    cursor: pointer;
    font: inherit;
    font-size: 0.82rem;
    font-weight: 650;
}

.notes-tab:hover {
    color: var(--color-ink);
    background: var(--color-surface-muted);
}

.notes-tab.active {
    border-color: var(--color-line-strong);
    color: var(--color-ink);
    background: var(--color-surface-raised);
    box-shadow: var(--shadow-sm);
}

.tab-count {
    min-width: 1.25rem;
    padding: 0.1rem 0.34rem;
    border-radius: 999px;
    color: var(--color-faint);
    background: var(--color-surface-muted);
    font-family: var(--font-mono);
    font-size: 0.65rem;
    line-height: 1.35;
    text-align: center;
}

.notes-tab.active .tab-count {
    color: var(--color-accent-dark);
    background: var(--color-accent-soft);
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

@media (max-width: 640px) {
    .notes-tabs {
        overflow-x: auto;
    }

    .notes-tab {
        flex: 1 0 auto;
        justify-content: center;
    }
}
</style>
