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
            title="打开偏好设置"
            aria-label="打开偏好设置"
            :aria-expanded="headerToolsOpen"
            aria-haspopup="menu"
            @click="toggleHeaderTools"
          >
            偏好设置
            <span class="menu-chevron" aria-hidden="true">⌄</span>
          </button>
          <div v-if="headerToolsOpen" class="action-menu header-tools-menu" role="menu">
            <button class="menu-item response-styles-btn" role="menuitem" @click="showResponseStyles = true; closeMenus()" title="管理回复风格">
              回复风格
            </button>
            <button class="menu-item settings-btn" role="menuitem" @click="showSettings = true; closeMenus()" title="配置模型与存储">
              模型与存储
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
          <div class="book-card-toolbar">
            <nav class="book-quick-links" :aria-label="`《${book.title}》学习入口`">
              <router-link
                :to="{ name: 'book-management', params: { id: book.id } }"
                target="_blank"
                rel="noopener"
                class="book-icon-link"
                aria-label="内容状态（在新标签页打开）"
                data-tooltip="内容状态"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M5.5 15.8a7.5 7.5 0 1 1 13 0" />
                  <path d="m12 13 3.2-3.2" />
                  <path d="M4.8 19h14.4" />
                  <path d="M7 7.5 8.4 9M17 7.5 15.6 9M12 4.5V7" />
                </svg>
              </router-link>
              <router-link
                :to="{ name: 'notes', params: { id: book.id } }"
                target="_blank"
                rel="noopener"
                class="book-icon-link"
                aria-label="笔记（在新标签页打开）"
                data-tooltip="笔记"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M6.5 3.5h9l3 3v14h-12z" />
                  <path d="M15.5 3.5v3h3M9.5 11h6M9.5 15h4" />
                  <path d="M4 7.5h2.5M4 12h2.5M4 16.5h2.5" />
                </svg>
              </router-link>
              <router-link
                :to="{ name: 'book-learning', params: { id: book.id } }"
                target="_blank"
                rel="noopener"
                class="book-icon-link"
                aria-label="Quiz 与学习画像（在新标签页打开）"
                data-tooltip="Quiz · 学习画像"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 3.5 14 7l4-.2-.3 4 2.8 2.7-3.3 2.2.8 3.8-4-.7-2 3.2-2-3.2-4 .7.8-3.8-3.3-2.2 2.8-2.7-.3-4 4 .2z" />
                  <path d="M10.5 10.3a1.7 1.7 0 1 1 2.2 1.6c-.7.3-.7.8-.7 1.3M12 16.2h.01" />
                </svg>
                <span v-if="profileStatuses[book.id]?.should_analyze" class="quick-link-alert" aria-hidden="true"></span>
              </router-link>
            </nav>

            <div class="action-menu-wrap book-menu-wrap" @click.stop>
              <button
                class="book-menu-trigger"
                type="button"
                :aria-label="`管理《${book.title}》`"
                :aria-expanded="openBookMenuId === book.id"
                aria-haspopup="menu"
                data-tooltip="更多操作"
                @click="toggleBookMenu(book.id)"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="5" cy="12" r="1.25" />
                  <circle cx="12" cy="12" r="1.25" />
                  <circle cx="19" cy="12" r="1.25" />
                </svg>
                <span v-if="profileStatuses[book.id]?.should_analyze" class="book-menu-alert" aria-hidden="true"></span>
              </button>
              <div v-if="openBookMenuId === book.id" class="action-menu book-action-menu" role="menu">
                <p class="menu-section-label">图书文件</p>
                <button class="menu-item" role="menuitem" @click="startEditing(book); closeMenus()">重命名</button>
                <button
                  class="menu-item"
                  role="menuitem"
                  :disabled="exportingBookId === book.id"
                  @click="handlePackageExport(book); closeMenus()"
                >
                  {{ exportingBookId === book.id ? '正在导出…' : '导出图书包' }}
                </button>
                <div class="menu-divider"></div>
                <button class="menu-item menu-item-danger" role="menuitem" @click="requestDeleteBook(book); closeMenus()">删除图书</button>
              </div>
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
                  画像待更新
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
      @close="closeImportModal"
      @import="handleImport"
      @upload="handleUpload"
      @import-package="handlePackageImport"
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

  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, computed, nextTick, watch } from 'vue'
import { useBookStore } from '../stores/bookStore'
import { renderMath } from '../utils/renderer'
import ImportModal from '../components/ImportModal.vue'
import SettingsModal from '../components/SettingsModal.vue'
import MacroSettingsModal from '../components/MacroSettingsModal.vue'
import { extractImportPreflight, formatImportErrorMessage } from '../utils/importPreflight'
import { formatLibraryBookTitle } from '../utils/bookTitle'

const bookStore = useBookStore()
const showImport = ref(false)
const showSettings = ref(false)
const showResponseStyles = ref(false)
const headerToolsOpen = ref(false)
const openBookMenuId = ref(null)
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
const exportingBookId = ref(null)
const notification = ref(null)
const pendingDeleteBook = ref(null)
const deletingBook = ref(false)

const books = computed(() => bookStore.books)
const loading = computed(() => bookStore.loading)
const error = computed(() => bookStore.error)

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

const statusLabel = (book) => {
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

const handlePackageExport = async (book) => {
  if (!book?.id || exportingBookId.value) return
  exportingBookId.value = book.id
  try {
    const safeTitle = (book?.title || 'book').replace(/[^0-9A-Za-z._\-\s]+/g, '_').trim() || 'book'
    await bookStore.exportBookPackage(book.id, `${safeTitle}-${book?.uuid || book.id}.zip`)
    showNotification('图书包已开始下载', 'success')
  } catch (e) {
    showNotification(`图书包导出失败：${importErrorMessage(e)}`, 'error')
  } finally {
    exportingBookId.value = null
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

.book-card-toolbar {
  position: absolute;
  top: 1rem;
  right: 1rem;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 0.2rem;
}

.book-quick-links {
  display: flex;
  align-items: center;
  gap: 0.12rem;
  padding-right: 0.22rem;
  border-right: 1px solid #dce5ec;
}

.book-quick-links .book-icon-link {
  position: relative;
  width: 34px;
  height: 34px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  padding: 0;
  border-radius: 9px;
  color: #596b7d;
  text-decoration: none;
  transition: color 180ms ease, background 180ms ease, transform 180ms ease;
}

.book-quick-links .book-icon-link:hover {
  color: var(--library-accent-dark);
  background: #eef4ff;
  transform: translateY(-1px);
}

.book-quick-links .book-icon-link:active {
  transform: translateY(0);
}

.book-quick-links .book-icon-link:focus-visible,
.book-menu-trigger:focus-visible {
  outline: 2px solid var(--library-accent);
  outline-offset: 2px;
}

.book-icon-link svg,
.book-menu-trigger svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.book-menu-trigger svg circle {
  fill: currentColor;
  stroke: none;
}

.book-icon-link::after,
.book-menu-trigger::after {
  content: attr(data-tooltip);
  position: absolute;
  top: calc(100% + 0.48rem);
  left: 50%;
  z-index: 45;
  width: max-content;
  max-width: 11rem;
  padding: 0.36rem 0.5rem;
  border-radius: 7px;
  color: #fff;
  background: #263142;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.16);
  font-size: 0.68rem;
  font-weight: 600;
  line-height: 1.2;
  pointer-events: none;
  opacity: 0;
  transform: translate(-50%, -3px);
  transition: opacity 140ms ease, transform 140ms ease;
  white-space: nowrap;
}

.book-icon-link:hover::after,
.book-icon-link:focus-visible::after,
.book-menu-trigger:hover::after,
.book-menu-trigger:focus-visible::after {
  opacity: 1;
  transform: translate(-50%, 0);
}

.book-menu-trigger[aria-expanded="true"]::after {
  display: none;
}

.quick-link-alert {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 6px;
  height: 6px;
  border: 1px solid #fff;
  border-radius: 50%;
  background: #b7791f;
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

  .book-card-toolbar {
    top: 0.85rem;
    right: 0.85rem;
  }

  .book-quick-links .book-icon-link {
    width: 36px;
    height: 36px;
  }

  .modal-overlay {
    padding: 1rem;
    align-items: stretch;
  }
}
</style>
