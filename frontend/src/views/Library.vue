<template>
  <div class="library-wrapper" ref="libraryRef">
    <header class="library-header">
      <div class="header-content">
        <img class="home-logo" src="/logo.png" alt="Math Book Translator logo" />
        <div>
          <h1>Interactive Library</h1>
          <p>Translate and manage your math textbooks</p>
        </div>
      </div>

      <div class="header-actions">
        <button class="icon-btn response-styles-btn" @click="showResponseStyles = true" title="Response Styles">
          <span class="icon">📝</span>
          Response Styles
        </button>
        <button class="icon-btn settings-btn" @click="showSettings = true" title="Settings">
          <span class="icon">⚙️</span>
          Settings
        </button>
        <button class="icon-btn ai-author-btn" @click="handleStartAgent" title="AI Author">
          <span class="icon">🤖</span>
          AI Author
        </button>
        <button class="primary-btn add-book-btn" @click="showImport = true">
          <span class="icon">➕</span>
          Add Book
        </button>
      </div>
    </header>

    <div v-if="loading" class="loading-state">Loading books...</div>
    <div v-else-if="error" class="error-state">{{ error }}</div>

    <div v-else class="book-grid">
      <div v-for="book in books" :key="book.id" class="book-card">
        <div class="book-card-main">
          <button class="delete-icon-btn" @click="deleteBook(book.id)" title="Delete Book">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"></path><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path></svg>
          </button>

          <div class="book-info">
            <div v-if="editingBookId === book.id" class="edit-title">
              <input
                v-model="editTitle"
                @blur="saveTitle(book)"
                @keyup.enter="saveTitle(book)"
                ref="titleInput"
              />
            </div>
            <h3 v-else class="book-title" @dblclick="startEditing(book)" title="Double click to rename">
              {{ book.title }}
            </h3>

            <div class="book-meta">
              <span :class="['status-tag', book.status]">
                <span class="status-dot"></span>
                {{ statusLabel(book) }}
              </span>
              <span class="date">{{ new Date(book.created_at).toLocaleDateString() }}</span>
            </div>

            <div v-if="showBookProgress(book)" :class="['book-progress', { 'guides-progress': isGeneratingGuides(book) }]">
              <div class="progress-track">
                <div
                  class="progress-fill"
                  :style="isGeneratingGuides(book) ? undefined : { width: `${translationPercent(book)}%` }"
                ></div>
              </div>
              <span>{{ progressText(book) }}</span>
            </div>
          </div>
        </div>

        <div class="book-actions">
          <router-link :to="{ name: 'reader', params: { id: book.id }}" class="action-link main-action">
            <button class="action-btn read">
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a4 4 0 0 0-4-4H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a4 4 0 0 1 4-4h6z"></path></svg>
              Open
            </button>
          </router-link>

          <div class="secondary-actions">
            <button
              v-if="book.type === 'generated'"
              class="action-btn console-btn"
              @click="openConsole(book)"
              title="Agent Console"
            >
              <span class="icon" style="font-size: 1rem;">terminal</span>
              Console
            </button>

            <button
              class="action-btn translate"
              @click="translateBook(book)"
              :disabled="isBackgroundBusy(book)"
              :title="isTranslating(book) ? 'Translating...' : book.status === 'generating_guides' ? 'Generating guides...' : 'Translate'"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 8 6 6"></path><path d="m4 14 6-6 2-3"></path><path d="M2 5h12"></path><path d="M7 2h1"></path><path d="m22 22-5-10-5 10"></path><path d="M14 18h6"></path></svg>
              <span>{{ isTranslating(book) ? `${translationPercent(book)}%` : book.status === 'generating_guides' ? 'Guides...' : 'Translate' }}</span>
            </button>

            <button
              class="action-btn profile-btn"
              @click="analyzeLearningProfile(book)"
              :disabled="profileAnalyzingBookId === book.id"
              title="Analyze Learning Profile"
            >
              {{ profileAnalyzingBookId === book.id ? 'Analyzing...' : 'Analyze' }}
            </button>

            <button
              class="action-btn profile-view-btn"
              @click="openLearningProfile(book)"
              :disabled="profileLoading && selectedProfileBook?.id === book.id"
              title="View Learning Profile"
            >
              Profile
            </button>

            <button
              class="action-btn book-quiz-btn"
              @click="startBookQuiz(book)"
              title="Book Quiz"
            >
              Book Quiz
            </button>

            <router-link :to="{ name: 'notes', params: { id: book.id }}" class="action-link">
               <button class="action-btn notes-btn" title="View Notes">
                 <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15.5 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8.5L15.5 3Z"></path><path d="M15 3v6h6"></path><line x1="9" y1="13" x2="15" y2="13"></line><line x1="9" y1="17" x2="15" y2="17"></line></svg>
                 Notes
               </button>
            </router-link>
          </div>
          <p v-if="profileStatuses[book.id]?.should_analyze" class="learning-profile-hint">
            你最近有新的笔记和 Quiz 记录，可以分析生成学习画像。
          </p>
        </div>
      </div>
    </div>

    <!-- Modals -->
    <ImportModal
      :show="showImport"
      :loading="importing || uploading"
      :preflight-warning="preflightWarning"
      :outline-review="outlineReview"
      :books="books"
      @close="closeImportModal"
      @import="handleImport"
      @upload="handleUpload"
      @import-package="handlePackageImport"
      @export-package="handlePackageExport"
      @confirm-preflight="confirmPreflightImport"
      @cancel-preflight="cancelPreflightImport"
      @confirm-outline="confirmOutlineImport"
      @cancel-outline="cancelOutlineImport"
    />

    <SettingsModal
      :show="showSettings"
      @close="showSettings = false"
      @save="onSaveSettings"
    />

    <MacroSettingsModal
      :show="showResponseStyles"
      @close="showResponseStyles = false"
      @save="onSaveResponseStyles"
    />

    <AgentConsole
      :show="showConsole"
      :bookId="selectedBook?.id"
      :bookTitle="selectedBook?.title"
      @close="showConsole = false"
    />

    <div v-if="showProfileModal" class="modal-overlay" @click.self="closeLearningProfile">
      <div class="profile-modal" role="dialog" aria-modal="true" aria-labelledby="profile-modal-title">
        <header class="profile-modal-header">
          <div>
            <p class="profile-modal-kicker">Learning Profile</p>
            <h2 id="profile-modal-title">{{ selectedProfileBook?.title || 'User.md' }}</h2>
          </div>
          <button class="modal-close-btn" @click="closeLearningProfile" title="Close Learning Profile">Close</button>
        </header>

        <div v-if="profileSummary" class="profile-summary">{{ profileSummary }}</div>
        <div v-if="profileLoading" class="profile-state">Loading learning profile...</div>
        <div v-else-if="profileError" class="profile-state profile-error">{{ profileError }}</div>
        <article v-else class="profile-content markdown-content" v-html="profileHtml"></article>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useBookStore } from '../stores/bookStore'
import { renderMarkdown, renderMath } from '../utils/renderer'
import ImportModal from '../components/ImportModal.vue'
import SettingsModal from '../components/SettingsModal.vue'
import MacroSettingsModal from '../components/MacroSettingsModal.vue'
import AgentConsole from '../components/AgentConsole.vue'
import { extractImportPreflight, formatImportErrorMessage } from '../utils/importPreflight'

const bookStore = useBookStore()
const router = useRouter()
const showImport = ref(false)
const showSettings = ref(false)
const showResponseStyles = ref(false)
const showConsole = ref(false)
const selectedBook = ref(null)
const uploading = ref(false)
const importing = ref(false)
const preflightWarning = ref(null)
const outlineReview = ref(null)
const pendingImport = ref(null)
const editingBookId = ref(null)
const editTitle = ref('')
const titleInput = ref(null)
const libraryRef = ref(null)
const profileStatuses = ref({})
const profileAnalyzingBookId = ref(null)
const showProfileModal = ref(false)
const selectedProfileBook = ref(null)
const profileLoading = ref(false)
const profileError = ref('')
const profileMarkdown = ref('')
const profileSummary = ref('')

const books = computed(() => bookStore.books)
const loading = computed(() => bookStore.loading)
const error = computed(() => bookStore.error)
const profileHtml = computed(() => renderMarkdown(profileMarkdown.value, selectedProfileBook.value))

const triggerRenderMath = () => {
  nextTick(() => {
    if (libraryRef.value) {
      renderMath(libraryRef.value)
    }
  })
}

onMounted(async () => {
  await bookStore.fetchBooks()
  await loadLearningProfileStatuses()
  triggerRenderMath()
})

watch(books, triggerRenderMath, { deep: true })

let pollingTimer = null

const isTranslating = (book) => book?.status === 'translating'
const isGeneratingGuides = (book) => book?.status === 'generating_guides'
const isBackgroundBusy = (book) => ['translating', 'generating_guides'].includes(book?.status)

const statusLabel = (book) => {
  if (book.type === 'generated' && book.agent_stage && !['init', 'ready'].includes(book.agent_stage)) return book.agent_stage
  const labels = {
    loaded: 'loaded',
    translating: 'translating',
    translated: 'translated',
    generating: 'generating',
    generating_guides: 'generating guides',
    failed: 'failed'
  }
  return labels[book.status] || book.status
}

const translationPercent = (book) => {
  const total = Number(book.translation_total || 0)
  if (total <= 0) return 0
  return Math.min(100, Math.round((Number(book.translation_completed || 0) / total) * 100))
}

const showBookProgress = (book) => {
  if (isGeneratingGuides(book)) return true
  return Number(book.translation_total || 0) > 0 && ['loaded', 'translating', 'translated', 'failed'].includes(book.status)
}

const translationProgressText = (book) => {
  const completed = Number(book.translation_completed || 0)
  const total = Number(book.translation_total || 0)
  const failed = Number(book.translation_failed || 0)
  return failed > 0 ? `${completed}/${total} translated, ${failed} failed` : `${completed}/${total} translated`
}

const progressText = (book) => {
  if (isGeneratingGuides(book)) return 'Generating top-down guides...'
  return translationProgressText(book)
}

const syncPolling = () => {
  const hasActiveTranslation = books.value.some(isBackgroundBusy)
  if (hasActiveTranslation && !pollingTimer) {
    pollingTimer = window.setInterval(() => bookStore.fetchBooks(), 15000)
  } else if (!hasActiveTranslation && pollingTimer) {
    window.clearInterval(pollingTimer)
    pollingTimer = null
  }
}

watch(books, syncPolling, { deep: true })

onBeforeUnmount(() => {
  if (pollingTimer) window.clearInterval(pollingTimer)
})

const handleStartAgent = () => {
  selectedBook.value = null // Null bookId triggers initialization mode in Console
  showConsole.value = true
}

const closeImportModal = () => {
  showImport.value = false
  preflightWarning.value = null
  outlineReview.value = null
  pendingImport.value = null
}

const applyImportConfirmationResult = (result) => {
  if (result?.requires_confirmation && result.confirmation_type === 'outline') {
    outlineReview.value = result.outline
    preflightWarning.value = null
    return true
  }
  if (result?.requires_confirmation) {
    preflightWarning.value = result.preflight
    outlineReview.value = null
    return true
  }
  return false
}

const handleUpload = async (file) => {
  uploading.value = true
  pendingImport.value = { type: 'upload', file }
  preflightWarning.value = null
  outlineReview.value = null
  try {
    const result = await bookStore.uploadBook(file)
    if (!applyImportConfirmationResult(result)) {
      pendingImport.value = null
      showImport.value = false
    }
  } catch (e) {
    const failedPreflight = extractImportPreflight(e)
    if (failedPreflight) {
      preflightWarning.value = failedPreflight
      if (failedPreflight.severity === 'blocked') pendingImport.value = null
    } else {
      alert("Upload failed: " + importErrorMessage(e))
      pendingImport.value = null
    }
  } finally {
    uploading.value = false
  }
}

const handleImport = async (path) => {
  importing.value = true
  pendingImport.value = { type: 'local', path }
  preflightWarning.value = null
  outlineReview.value = null
  try {
    const result = await bookStore.importBook(path)
    if (!applyImportConfirmationResult(result)) {
      pendingImport.value = null
      showImport.value = false
    }
  } catch (e) {
    const failedPreflight = extractImportPreflight(e)
    if (failedPreflight) {
      preflightWarning.value = failedPreflight
      if (failedPreflight.severity === 'blocked') pendingImport.value = null
    } else {
      alert("Import failed: " + importErrorMessage(e))
      pendingImport.value = null
    }
  } finally {
    importing.value = false
  }
}

const handlePackageImport = async (file) => {
  importing.value = true
  preflightWarning.value = null
  outlineReview.value = null
  pendingImport.value = null
  try {
    await bookStore.importBookPackage(file)
    showImport.value = false
  } catch (e) {
    alert("Package import failed: " + importErrorMessage(e))
  } finally {
    importing.value = false
  }
}

const handlePackageExport = async (bookId) => {
  if (!bookId) return
  importing.value = true
  try {
    const book = books.value.find((item) => item.id === bookId)
    const safeTitle = (book?.title || 'book').replace(/[^0-9A-Za-z._\-\s]+/g, '_').trim() || 'book'
    await bookStore.exportBookPackage(bookId, `${safeTitle}-${book?.uuid || bookId}.zip`)
  } catch (e) {
    alert("Package export failed: " + importErrorMessage(e))
  } finally {
    importing.value = false
  }
}

const importErrorMessage = (error) => {
  return formatImportErrorMessage(error)
}

const confirmPreflightImport = async () => {
  if (!pendingImport.value) return
  const pending = pendingImport.value
  preflightWarning.value = null
  outlineReview.value = null
  if (pending.type === 'upload') {
    uploading.value = true
  } else {
    importing.value = true
  }

  try {
    if (pending.type === 'upload') {
      await bookStore.uploadBook(pending.file, {
        force: true,
        outlineSelection: pending.outlineSelection,
        outlinePlan: pending.outlinePlan
      })
    } else {
      await bookStore.importBook(pending.path, {
        force: true,
        outlineSelection: pending.outlineSelection,
        outlinePlan: pending.outlinePlan
      })
    }
    pendingImport.value = null
    showImport.value = false
  } catch (e) {
    const failedPreflight = extractImportPreflight(e)
    if (failedPreflight) {
      preflightWarning.value = failedPreflight
      if (failedPreflight.severity === 'blocked') pendingImport.value = null
    } else {
      alert("Import failed: " + importErrorMessage(e))
    }
  } finally {
    uploading.value = false
    importing.value = false
  }
}

const cancelPreflightImport = () => {
  preflightWarning.value = null
  pendingImport.value = null
}

const confirmOutlineImport = async (outlinePlan) => {
  if (!pendingImport.value) return
  pendingImport.value = {
    ...pendingImport.value,
    outlinePlan
  }
  outlineReview.value = null
  preflightWarning.value = null
  if (pendingImport.value.type === 'upload') {
    uploading.value = true
  } else {
    importing.value = true
  }

  try {
    let result
    if (pendingImport.value.type === 'upload') {
      result = await bookStore.uploadBook(pendingImport.value.file, { outlinePlan })
    } else {
      result = await bookStore.importBook(pendingImport.value.path, { outlinePlan })
    }
    if (!applyImportConfirmationResult(result)) {
      pendingImport.value = null
      showImport.value = false
    }
  } catch (e) {
    const failedPreflight = extractImportPreflight(e)
    if (failedPreflight) {
      preflightWarning.value = failedPreflight
      if (failedPreflight.severity === 'blocked') pendingImport.value = null
    } else {
      alert("Import failed: " + importErrorMessage(e))
    }
  } finally {
    uploading.value = false
    importing.value = false
  }
}

const cancelOutlineImport = () => {
  outlineReview.value = null
  pendingImport.value = null
}

const onSaveSettings = (settings) => {
  console.log("Settings saved:", settings)
  // Here we could also send to backend
}

const onSaveResponseStyles = (styles) => {
  console.log("Response styles saved:", styles)
}

const openConsole = (book) => {
  selectedBook.value = book
  showConsole.value = true
}

const startEditing = (book) => {
  editingBookId.value = book.id
  editTitle.value = book.title
  nextTick(() => {
    if (titleInput.value) {
      titleInput.value.focus()
    }
  })
}

const saveTitle = async (book) => {
  if (editingBookId.value !== book.id) return
  if (editTitle.value.trim() && editTitle.value !== book.title) {
    await bookStore.renameBook(book.id, editTitle.value)
  }
  editingBookId.value = null
}

const translateBook = async (book) => {
  try {
    await bookStore.translateBook(book.id)
  } catch (e) {
    alert("Translation trigger failed: " + e.message)
  }
}

const loadLearningProfileStatuses = async () => {
  const entries = await Promise.all(
    books.value.map(async (book) => {
      try {
        return [book.id, await bookStore.fetchLearningProfileStatus(book.id)]
      } catch (_error) {
        return [book.id, null]
      }
    })
  )
  profileStatuses.value = Object.fromEntries(entries.filter(([, status]) => status))
}

const analyzeLearningProfile = async (book) => {
  profileAnalyzingBookId.value = book.id
  try {
    const result = await bookStore.analyzeLearningProfile(book.id)
    profileStatuses.value = {
      ...profileStatuses.value,
      [book.id]: await bookStore.fetchLearningProfileStatus(book.id)
    }
    selectedProfileBook.value = book
    profileSummary.value = result?.summary || ''
    profileMarkdown.value = result?.profile_markdown || ''
    profileError.value = ''
    profileLoading.value = false
    showProfileModal.value = true
    triggerRenderMath()
  } catch (e) {
    alert("Learning profile analysis failed: " + e.message)
  } finally {
    profileAnalyzingBookId.value = null
  }
}

const profileErrorMessage = (error) => {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  return error?.message || 'Learning profile could not be loaded.'
}

const openLearningProfile = async (book) => {
  selectedProfileBook.value = book
  profileMarkdown.value = ''
  profileSummary.value = ''
  profileError.value = ''
  profileLoading.value = true
  showProfileModal.value = true

  try {
    const result = await bookStore.fetchLearningProfile(book.id)
    profileMarkdown.value = result?.markdown || ''
  } catch (e) {
    profileError.value = profileErrorMessage(e)
  } finally {
    profileLoading.value = false
    triggerRenderMath()
  }
}

const closeLearningProfile = () => {
  showProfileModal.value = false
  selectedProfileBook.value = null
  profileMarkdown.value = ''
  profileSummary.value = ''
  profileError.value = ''
  profileLoading.value = false
}

const startBookQuiz = async (book) => {
  try {
    const target = await bookStore.selectBookQuizTarget(book.id)
    window.sessionStorage.setItem(`bookQuizTarget:${book.id}`, JSON.stringify(target))
    await router.push({
      name: 'reader',
      params: { id: book.id },
      query: {
        reader_type: 'chapter',
        chapter_id: target.chapter_id,
        quiz: '1',
        question_type: target.question_type
      }
    })
  } catch (e) {
    alert("Book Quiz failed: " + e.message)
  }
}

const deleteBook = async (id) => {
  if (!confirm("Are you sure you want to delete this book? This action cannot be undone.")) return

  try {
    await bookStore.deleteBook(id)
  } catch (e) {
    alert("Delete failed: " + e.message)
  }
}
</script>

<style scoped>
.library-wrapper {
  --library-ink: #14213d;
  --library-muted: #64748b;
  --library-line: #dbe3ea;
  --library-panel: #ffffff;
  --library-accent: #2563eb;
  --library-accent-dark: #1d4ed8;
  --library-mint: #0f766e;

  width: 100%;
  padding: 2.25rem 2rem 3rem;
  max-width: 1240px;
  margin: 0 auto;
}

.library-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.5rem;
  margin-bottom: 2rem;
  padding: 1.15rem;
  border: 1px solid rgba(203, 213, 225, 0.72);
  border-radius: 24px;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.09), transparent 34%),
    linear-gradient(135deg, #ffffff 0%, #f7faf9 100%);
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.06);
}

.header-content {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  min-width: 0;
}

.home-logo {
  width: 72px;
  height: 72px;
  flex: 0 0 auto;
  object-fit: cover;
  border-radius: 18px;
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.1);
}

.library-header h1 {
  font-size: clamp(2rem, 4vw, 2.65rem);
  margin: 0 0 0.3rem 0;
  color: var(--library-ink);
  line-height: 1.1;
  letter-spacing: -0.045em;
}

.library-header p {
  color: var(--library-muted);
  margin: 0;
  font-size: 0.95rem;
}

.header-actions {
  display: flex;
  gap: 0.55rem;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.icon-btn {
  display: flex;
  align-items: center;
  gap: 0.42rem;
  padding: 0.52rem 0.82rem;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--library-line);
  border-radius: 999px;
  font-weight: 600;
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.2s;
  color: #334155;
  white-space: nowrap;
}

.icon-btn:hover {
  background: #ffffff;
  border-color: #b8c6d1;
  color: var(--library-ink);
  transform: translateY(-1px);
}

.ai-author-btn:hover {
  border-color: #5eead4;
  color: var(--library-mint);
}

.primary-btn {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.56rem 0.95rem;
  background: var(--library-accent);
  color: white;
  border: none;
  border-radius: 999px;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.2s, background 0.2s;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.18);
  white-space: nowrap;
}

.primary-btn:hover {
  background: var(--library-accent-dark);
  transform: translateY(-1px);
}

.primary-btn:active {
  transform: translateY(0);
}

.edit-title input {
  width: 100%;
  padding: 0.5rem;
  font-size: 1.2rem;
  margin-bottom: 1rem;
}

.book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(315px, 1fr));
  gap: 1rem;
}

.book-card {
  background: var(--library-panel);
  border: 1px solid rgba(203, 213, 225, 0.86);
  border-radius: 22px;
  display: flex;
  flex-direction: column;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.045);
}

.book-card::before {
  content: "";
  position: absolute;
  inset: 0 0 auto;
  height: 4px;
  background: linear-gradient(90deg, #2563eb, #14b8a6, #94a3b8);
  opacity: 0.75;
}

.book-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
  border-color: #93c5fd;
}

.book-card-main {
  padding: 1.08rem 1.15rem 0.78rem;
  flex-grow: 1;
}

.book-info {
  display: flex;
  flex-direction: column;
}

.book-title {
  margin: 0 2.15rem 0.58rem 0;
  font-size: 1.24rem;
  font-weight: 700;
  line-height: 1.26;
  color: var(--library-ink);
  letter-spacing: -0.022em;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.book-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 0.42rem;
  padding-top: 0.5rem;
  border-top: 1px solid #eef2f7;
}

.status-tag {
  font-size: 0.62rem;
  padding: 0.2rem 0.5rem;
  border-radius: 100px;
  text-transform: uppercase;
  font-weight: 700;
  letter-spacing: 0.055em;
  display: flex;
  align-items: center;
  gap: 5px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-tag.loaded {
  background: #eef2ff; color: #4f46e5;
}
.status-tag.loaded .status-dot { background: #6366f1; }

.status-tag.translated {
  background: #ecfdf5; color: #059669;
}
.status-tag.translated .status-dot { background: #10b981; }

.status-tag.translating {
  background: #fffbeb; color: #d97706;
}
.status-tag.translating .status-dot {
  background: #f59e0b;
  animation: pulse 1.5s infinite;
}

.status-tag.generating {
  background: #f5f3ff; color: #7c3aed;
}
.status-tag.generating .status-dot {
  background: #8b5cf6;
  animation: pulse 1.5s infinite;
}

.status-tag.generating_guides {
  background: #ecfeff; color: #0891b2;
}
.status-tag.generating_guides .status-dot {
  background: #06b6d4;
  animation: pulse 1.5s infinite;
}

.status-tag.failed {
  background: #fef2f2; color: #dc2626;
}
.status-tag.failed .status-dot { background: #ef4444; }

.book-progress {
  margin-top: 0.52rem;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  color: var(--library-muted);
  font-size: 0.68rem;
  font-weight: 600;
}

.progress-track {
  flex: 1;
  height: 4px;
  overflow: hidden;
  border-radius: 999px;
  background: #e6edf3;
}

.progress-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #38bdf8, #10b981);
  transition: width 0.25s ease;
}

.guides-progress .progress-track {
  position: relative;
}

.guides-progress .progress-fill {
  width: 45%;
  background: linear-gradient(90deg, #06b6d4, #67e8f9, #0891b2);
  animation: guides-progress-slide 1.2s ease-in-out infinite;
}

@keyframes guides-progress-slide {
  0% { transform: translateX(-110%); }
  100% { transform: translateX(230%); }
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.4; }
  100% { opacity: 1; }
}

.date {
  font-size: 0.7rem;
  color: #7890a6;
  font-weight: 600;
}

.book-actions {
  padding: 0.68rem 1.15rem 0.85rem;
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.72), rgba(241, 245, 249, 0.82));
  border-top: 1px solid #e8eef5;
  display: grid;
  gap: 0.5rem;
}

.secondary-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.45rem;
}

.action-link {
  text-decoration: none;
  display: block;
}

.main-action {
  width: 100%;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  min-height: 31px;
  padding: 0.34rem 0.55rem;
  border-radius: 10px;
  font-size: 0.76rem;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid #dbe5ee;
  transition: background 0.2s, border-color 0.2s, color 0.2s, transform 0.2s, box-shadow 0.2s;
  white-space: nowrap;
}

.action-btn.read {
  background: var(--library-ink);
  color: white;
  border-color: var(--library-ink);
  min-height: 33px;
  padding: 0.36rem 0.68rem;
  font-size: 0.8rem;
}

.action-btn.read:hover {
  background: var(--library-accent);
  border-color: var(--library-accent);
  box-shadow: 0 8px 18px rgba(37, 99, 235, 0.2);
  transform: translateY(-1px);
}

.action-btn.translate {
  background: white;
  color: #1e5664;
}

.action-btn.translate:hover:not(:disabled) {
  background: #ecfeff;
  border-color: #99f6e4;
}

.action-btn.translate:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.action-btn.notes-btn {
  background: white;
  color: #475569;
}

.action-btn.notes-btn:hover {
  background: #f8fafc;
  border-color: #b9c8d6;
}

.action-btn.profile-btn,
.action-btn.profile-view-btn,
.action-btn.book-quiz-btn,
.action-btn.console-btn {
  background: white;
  color: #475569;
}

.action-btn.profile-btn:hover,
.action-btn.profile-view-btn:hover,
.action-btn.book-quiz-btn:hover,
.action-btn.console-btn:hover {
  background: #f1f5f9;
  border-color: #b9c8d6;
  color: var(--library-ink);
}

.action-btn.profile-btn:disabled,
.action-btn.profile-view-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.learning-profile-hint {
  margin: 0.05rem 0 0;
  padding: 0.52rem 0.65rem;
  color: #7c4a03;
  font-size: 0.74rem;
  line-height: 1.45;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 12px;
}

.delete-icon-btn {
  position: absolute;
  top: 0.9rem;
  right: 0.9rem;
  background: white;
  border: 1px solid #e6edf3;
  border-radius: 10px;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
  opacity: 0;
  z-index: 10;
}

.book-card:hover .delete-icon-btn {
  opacity: 1;
}

.delete-icon-btn:hover {
  background: #fef2f2;
  color: #ef4444;
  border-color: #fee2e2;
}

.loading-state, .error-state {
  text-align: center;
  padding: 4rem;
  color: var(--library-muted);
  background: white;
  border-radius: 20px;
  border: 1px dashed #e2e8f0;
  margin-top: 2rem;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2rem;
  background: rgba(15, 23, 42, 0.48);
}

.profile-modal {
  width: min(760px, 100%);
  max-height: min(760px, 90vh);
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 14px;
  box-shadow: 0 24px 70px rgba(15, 23, 42, 0.24);
  overflow: hidden;
}

.profile-modal-header {
  display: flex;
  justify-content: space-between;
  gap: 1.5rem;
  padding: 1.5rem 1.75rem;
  border-bottom: 1px solid #e2e8f0;
}

.profile-modal-kicker {
  margin: 0 0 0.35rem;
  color: #64748b;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.profile-modal-header h2 {
  margin: 0;
  color: var(--primary-color);
  font-size: 1.35rem;
  line-height: 1.3;
}

.modal-close-btn {
  align-self: flex-start;
  padding: 0.45rem 0.8rem;
  background: white;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  color: #475569;
  font-weight: 700;
  cursor: pointer;
}

.modal-close-btn:hover {
  background: #f8fafc;
}

.profile-summary {
  margin: 1rem 1.75rem 0;
  padding: 0.75rem 0.9rem;
  border: 1px solid #bfdbfe;
  border-radius: 10px;
  color: #1e3a8a;
  background: #eff6ff;
  font-size: 0.88rem;
  line-height: 1.5;
}

.profile-state {
  padding: 2rem 1.75rem;
  color: #64748b;
  font-weight: 600;
}

.profile-error {
  color: #b91c1c;
}

.profile-content {
  overflow: auto;
  padding: 1.25rem 1.75rem 1.75rem;
  color: #1e293b;
  line-height: 1.7;
}

.profile-content :deep(h1),
.profile-content :deep(h2),
.profile-content :deep(h3) {
  color: var(--primary-color);
  line-height: 1.35;
}

.profile-content :deep(h1) {
  font-size: 1.45rem;
}

.profile-content :deep(h2) {
  margin-top: 1.4rem;
  font-size: 1.2rem;
}

.profile-content :deep(p),
.profile-content :deep(ul),
.profile-content :deep(ol) {
  margin: 0.65rem 0;
}

.profile-content :deep(code) {
  padding: 0.1rem 0.25rem;
  border-radius: 4px;
  background: #f1f5f9;
}

@media (max-width: 640px) {
  .library-wrapper {
    padding: 2rem 1rem;
  }

  .library-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 1.25rem;
    margin-bottom: 2rem;
  }

  .header-content {
    gap: 0.85rem;
  }

  .home-logo {
    width: 68px;
    height: 68px;
    border-radius: 16px;
  }

  .library-header h1 {
    font-size: 2rem;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .header-actions > button {
    flex: 1 1 9rem;
    justify-content: center;
  }

  .book-grid {
    grid-template-columns: 1fr;
  }

  .secondary-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .modal-overlay {
    padding: 1rem;
    align-items: stretch;
  }

  .profile-modal {
    max-height: 100%;
  }

  .profile-modal-header {
    flex-direction: column;
    gap: 1rem;
  }
}
</style>
