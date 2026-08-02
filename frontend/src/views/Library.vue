<template>
  <div class="library-wrapper" ref="libraryRef">
    <header class="library-header">
      <div class="header-content">
        <img class="home-logo" src="/logo.png" alt="Math Book Translator logo" />
        <div>
          <h1>Interactive Library</h1>
          <p>翻译、阅读并管理你的数学书</p>
        </div>
      </div>

      <div class="header-actions" @click.stop>
        <div class="action-menu-wrap header-tools-wrap">
          <button
            class="icon-btn tools-menu-btn"
            type="button"
            title="Library tools"
            :aria-expanded="headerToolsOpen"
            aria-haspopup="menu"
            @click="toggleHeaderTools"
          >
            工具与设置
            <span class="menu-chevron" aria-hidden="true">⌄</span>
          </button>
          <div v-if="headerToolsOpen" class="action-menu header-tools-menu" role="menu">
            <button class="menu-item response-styles-btn" role="menuitem" @click="showResponseStyles = true; closeMenus()" title="Response Styles">
              Response Styles
            </button>
            <button class="menu-item settings-btn" role="menuitem" @click="showSettings = true; closeMenus()" title="Settings">
              设置
            </button>
            <button class="menu-item ai-author-btn" role="menuitem" @click="handleStartAgent(); closeMenus()" title="AI Author">
              AI Author
            </button>
          </div>
        </div>
        <button class="primary-btn add-book-btn" @click="showImport = true">
          添加图书
        </button>
      </div>
    </header>

    <div v-if="loading" class="book-grid library-skeleton" aria-label="正在加载图书">
      <div v-for="index in 3" :key="index" class="book-card skeleton-card" aria-hidden="true">
        <div class="skeleton-line skeleton-title"></div>
        <div class="skeleton-line skeleton-meta"></div>
        <div class="skeleton-line skeleton-action"></div>
      </div>
    </div>
    <section v-else-if="error" class="error-state library-feedback-state">
      <p>{{ error }}</p>
      <button type="button" class="secondary-btn" @click="bookStore.fetchBooks()">重新加载</button>
    </section>
    <section v-else-if="books.length === 0" class="library-empty-state">
      <span class="empty-index" aria-hidden="true">∅</span>
      <p class="empty-kicker">你的数学书房还没有内容</p>
      <h2>从一本 Markdown 数学书开始</h2>
      <p>导入后可以分章节阅读、翻译、提问、做笔记并生成学习导读。</p>
      <button type="button" class="primary-btn" @click="showImport = true">添加第一本图书</button>
    </section>

    <div v-else class="book-grid">
      <div v-for="(book, index) in books" :key="book.id" class="book-card">
        <div class="book-card-main">
          <div class="action-menu-wrap book-menu-wrap" @click.stop>
            <button
              class="book-menu-trigger"
              type="button"
              :aria-label="`管理《${book.title}》`"
              :aria-expanded="openBookMenuId === book.id"
              aria-haspopup="menu"
              @click="toggleBookMenu(book.id)"
            >
              <span aria-hidden="true">•••</span>
              <span v-if="profileStatuses[book.id]?.should_analyze" class="book-menu-alert" aria-hidden="true"></span>
            </button>
            <div v-if="openBookMenuId === book.id" class="action-menu book-action-menu" role="menu">
              <p class="menu-section-label">图书操作</p>
              <button class="menu-item" role="menuitem" @click="startEditing(book); closeMenus()">重命名</button>
              <button
                v-if="book.type === 'generated'"
                class="menu-item console-btn"
                role="menuitem"
                title="Agent Console"
                @click="openConsole(book); closeMenus()"
              >
                Agent Console
              </button>
              <button
                v-if="shouldOfferTranslation(book)"
                class="menu-item translate"
                role="menuitem"
                @click="translateBook(book); closeMenus()"
              >
                {{ book.status === 'failed' ? '重试翻译' : '开始翻译' }}
              </button>
              <button v-else-if="isBackgroundBusy(book)" class="menu-item" type="button" disabled>
                {{ isTranslating(book) ? `翻译中 ${translationPercent(book)}%` : '正在生成导读' }}
              </button>
              <router-link :to="{ name: 'notes', params: { id: book.id }}" class="menu-item menu-link" role="menuitem" @click="closeMenus">
                查看笔记
              </router-link>
              <button class="menu-item book-quiz-btn" role="menuitem" title="Book Quiz" @click="startBookQuiz(book); closeMenus()">
                Book Quiz
              </button>
              <p class="menu-section-label">学习画像</p>
              <button
                class="menu-item profile-btn"
                role="menuitem"
                title="Analyze Learning Profile"
                :disabled="profileAnalyzingBookId === book.id"
                @click="analyzeLearningProfile(book); closeMenus()"
              >
                {{ profileAnalyzingBookId === book.id ? '分析中…' : 'Analyze Learning Profile' }}
              </button>
              <button
                class="menu-item profile-view-btn"
                role="menuitem"
                title="View Learning Profile"
                :disabled="profileLoading && selectedProfileBook?.id === book.id"
                @click="openLearningProfile(book)"
              >
                View Learning Profile
              </button>
              <div class="menu-divider"></div>
              <button class="menu-item menu-item-danger" role="menuitem" @click="requestDeleteBook(book); closeMenus()">删除图书</button>
            </div>
          </div>

          <div class="book-info">
            <p class="book-sequence">VOLUME {{ formatBookIndex(index) }}</p>
            <div v-if="editingBookId === book.id" class="edit-title">
              <input
                v-model="editTitle"
                @blur="saveTitle(book)"
                @keyup.enter="saveTitle(book)"
                ref="titleInput"
              />
            </div>
            <h3 v-else class="book-title" @dblclick="startEditing(book)" :title="bookTitleTooltip(book)">
              {{ formatLibraryBookTitle(book.title) }}
            </h3>

            <div class="book-meta">
              <div class="book-state-line">
                <span :class="['status-tag', book.status]">
                  <span v-if="book.status === 'translated'" class="status-check" aria-hidden="true">✓</span>
                  <span v-else class="status-dot" aria-hidden="true"></span>
                  {{ statusLabel(book) }}
                </span>
                <span v-if="profileStatuses[book.id]?.should_analyze" class="book-insight">
                  <span aria-hidden="true"></span>
                  学习画像已更新
                </span>
              </div>
              <span class="date">{{ formatBookDate(book.created_at) }}</span>
            </div>

            <div v-if="showBookProgress(book)" class="book-progress">
              <div class="progress-track">
                <div
                  class="progress-fill"
                  :style="{ width: `${translationPercent(book)}%` }"
                ></div>
              </div>
              <span>{{ translationProgressText(book) }}</span>
            </div>
          </div>
        </div>

        <div class="book-actions">
          <router-link :to="{ name: 'reader', params: { id: book.id }}" class="action-link main-action action-btn read">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 3h6a4 4 0 0 1 4 4v14a4 4 0 0 0-4-4H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a4 4 0 0 1 4-4h6z"></path></svg>
            <span>继续阅读</span>
          </router-link>
        </div>
      </div>
    </div>

    <Transition name="toast">
      <div v-if="notification" class="app-toast" :class="`toast-${notification.type}`" role="status" aria-live="polite">
        <span>{{ notification.message }}</span>
        <button type="button" aria-label="关闭提示" @click="notification = null">×</button>
      </div>
    </Transition>

    <div v-if="pendingDeleteBook" class="modal-overlay confirm-overlay" @click.self="pendingDeleteBook = null">
      <section class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="delete-book-title">
        <p class="confirm-kicker">删除图书</p>
        <h2 id="delete-book-title">确定删除《{{ pendingDeleteBook.title }}》？</h2>
        <p>章节、译文、导读和笔记会一并删除，此操作无法撤销。</p>
        <footer class="confirm-actions">
          <button type="button" class="secondary-btn" @click="pendingDeleteBook = null">取消</button>
          <button type="button" class="danger-btn" :disabled="deletingBook" @click="deleteBook">
            {{ deletingBook ? '正在删除…' : '确认删除' }}
          </button>
        </footer>
      </section>
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
import { formatLibraryBookTitle } from '../utils/bookTitle'

const bookStore = useBookStore()
const router = useRouter()
const showImport = ref(false)
const showSettings = ref(false)
const showResponseStyles = ref(false)
const showConsole = ref(false)
const headerToolsOpen = ref(false)
const openBookMenuId = ref(null)
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
const notification = ref(null)
const pendingDeleteBook = ref(null)
const deletingBook = ref(false)

const books = computed(() => bookStore.books)
const loading = computed(() => bookStore.loading)
const error = computed(() => bookStore.error)
const profileHtml = computed(() => renderMarkdown(profileMarkdown.value, selectedProfileBook.value))

const formatBookIndex = (index) => String(index + 1).padStart(2, '0')

const bookTitleTooltip = (book) => {
  const originalTitle = String(book?.title || '').trim()
  const displayTitle = formatLibraryBookTitle(originalTitle)
  const renameHint = '双击书名或通过菜单重命名'
  if (!originalTitle || originalTitle === displayTitle) return `${displayTitle}\n${renameHint}`
  return `${displayTitle}\n原始名称：${originalTitle}\n${renameHint}`
}

const triggerRenderMath = () => {
  nextTick(() => {
    if (libraryRef.value) {
      renderMath(libraryRef.value)
    }
  })
}

let notificationTimer = null

const closeMenus = () => {
  headerToolsOpen.value = false
  openBookMenuId.value = null
}

const toggleHeaderTools = () => {
  const nextValue = !headerToolsOpen.value
  closeMenus()
  headerToolsOpen.value = nextValue
}

const toggleBookMenu = (bookId) => {
  const nextBookId = openBookMenuId.value === bookId ? null : bookId
  closeMenus()
  openBookMenuId.value = nextBookId
}

const showNotification = (message, type = 'info') => {
  if (notificationTimer) window.clearTimeout(notificationTimer)
  notification.value = { message, type }
  notificationTimer = window.setTimeout(() => {
    notification.value = null
    notificationTimer = null
  }, 4200)
}

onMounted(async () => {
  document.addEventListener('click', closeMenus)
  await bookStore.fetchBooks()
  await loadLearningProfileStatuses()
  triggerRenderMath()
})

watch(books, triggerRenderMath, { deep: true })

let pollingTimer = null

const isTranslating = (book) => book?.status === 'translating'
const isBackgroundBusy = (book) => ['translating', 'generating_guides'].includes(book?.status)
const shouldOfferTranslation = (book) => !['translated', 'translating', 'generating_guides'].includes(book?.status)

const statusLabel = (book) => {
  if (book.type === 'generated' && book.agent_stage && !['init', 'ready'].includes(book.agent_stage)) return book.agent_stage
  const labels = {
    loaded: '待翻译',
    translating: '翻译中',
    translated: '已翻译',
    generating: '生成中',
    generating_guides: '生成导读中',
    failed: '处理失败'
  }
  return labels[book.status] || book.status
}

const translationPercent = (book) => {
  const total = Number(book.translation_total || 0)
  if (total <= 0) return 0
  return Math.min(100, Math.round((Number(book.translation_completed || 0) / total) * 100))
}

const showBookProgress = (book) => {
  return isTranslating(book) && Number(book.translation_total || 0) > 0
}

const translationProgressText = (book) => {
  const completed = Number(book.translation_completed || 0)
  const total = Number(book.translation_total || 0)
  const failed = Number(book.translation_failed || 0)
  return failed > 0 ? `${completed} / ${total} · ${failed} 个失败` : `${completed} / ${total}`
}

const formatBookDate = (value) => {
  if (!value) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  }).format(new Date(value))
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
  if (notificationTimer) window.clearTimeout(notificationTimer)
  document.removeEventListener('click', closeMenus)
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
      showNotification('图书已导入', 'success')
    }
  } catch (e) {
    const failedPreflight = extractImportPreflight(e)
    if (failedPreflight) {
      preflightWarning.value = failedPreflight
      if (failedPreflight.severity === 'blocked') pendingImport.value = null
    } else {
      showNotification(`上传失败：${importErrorMessage(e)}`, 'error')
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
      showNotification('图书已导入', 'success')
    }
  } catch (e) {
    const failedPreflight = extractImportPreflight(e)
    if (failedPreflight) {
      preflightWarning.value = failedPreflight
      if (failedPreflight.severity === 'blocked') pendingImport.value = null
    } else {
      showNotification(`导入失败：${importErrorMessage(e)}`, 'error')
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
    showNotification('图书包已导入', 'success')
  } catch (e) {
    showNotification(`图书包导入失败：${importErrorMessage(e)}`, 'error')
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
    showNotification('图书包已开始下载', 'success')
  } catch (e) {
    showNotification(`图书包导出失败：${importErrorMessage(e)}`, 'error')
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
    showNotification('图书已导入', 'success')
  } catch (e) {
    const failedPreflight = extractImportPreflight(e)
    if (failedPreflight) {
      preflightWarning.value = failedPreflight
      if (failedPreflight.severity === 'blocked') pendingImport.value = null
    } else {
      showNotification(`导入失败：${importErrorMessage(e)}`, 'error')
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
      showNotification('图书已导入', 'success')
    }
  } catch (e) {
    const failedPreflight = extractImportPreflight(e)
    if (failedPreflight) {
      preflightWarning.value = failedPreflight
      if (failedPreflight.severity === 'blocked') pendingImport.value = null
    } else {
      showNotification(`导入失败：${importErrorMessage(e)}`, 'error')
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
  showNotification('设置已保存', 'success')
}

const onSaveResponseStyles = (styles) => {
  console.log("Response styles saved:", styles)
  showNotification('回复风格已保存', 'success')
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
  try {
    if (editTitle.value.trim() && editTitle.value !== book.title) {
      await bookStore.renameBook(book.id, editTitle.value.trim())
      showNotification('图书名称已更新', 'success')
    }
  } catch (error) {
    showNotification(`重命名失败：${error.message}`, 'error')
  } finally {
    editingBookId.value = null
  }
}

const translateBook = async (book) => {
  try {
    await bookStore.translateBook(book.id)
    showNotification('翻译任务已开始', 'success')
  } catch (e) {
    showNotification(`无法开始翻译：${e.message}`, 'error')
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
    showNotification('学习画像已更新', 'success')
  } catch (e) {
    showNotification(`学习画像分析失败：${e.message}`, 'error')
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
  closeMenus()
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
    showNotification(`无法开始 Book Quiz：${e.message}`, 'error')
  }
}

const requestDeleteBook = (book) => {
  pendingDeleteBook.value = book
}

const deleteBook = async () => {
  if (!pendingDeleteBook.value || deletingBook.value) return
  const book = pendingDeleteBook.value
  deletingBook.value = true

  try {
    await bookStore.deleteBook(book.id)
    pendingDeleteBook.value = null
    showNotification('图书已删除', 'success')
  } catch (e) {
    showNotification(`删除失败：${e.message}`, 'error')
  } finally {
    deletingBook.value = false
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
