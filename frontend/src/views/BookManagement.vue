<template>
  <main class="management-page">
    <div v-if="loading" class="management-shell management-loading" aria-label="正在加载书籍状态">
      <div class="skeleton skeleton-nav"></div>
      <div class="skeleton skeleton-hero"></div>
      <div class="skeleton-grid">
        <div class="skeleton skeleton-panel"></div>
        <div class="skeleton skeleton-panel"></div>
      </div>
    </div>

    <section v-else-if="error" class="management-shell management-error">
      <p class="eyebrow">BOOK OPERATIONS</p>
      <h1>没有读到这本书的管理数据</h1>
      <p>{{ error }}</p>
      <div class="error-actions">
        <button class="button button-primary" type="button" @click="loadSnapshot">重新加载</button>
        <router-link class="button button-secondary" :to="{ name: 'library' }">返回书库</router-link>
      </div>
    </section>

    <div v-else-if="snapshot" class="management-shell">
      <header class="management-header">
        <router-link class="back-link" :to="{ name: 'library' }" aria-label="返回书库">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6" /></svg>
          书库
        </router-link>
        <nav class="section-nav" aria-label="页面导航">
          <a href="#status">状态</a>
          <a href="#chapters">章节</a>
          <router-link :to="{ name: 'book-learning', params: { id: bookId } }" target="_blank" rel="noopener">
            Quiz · 画像 ↗
          </router-link>
        </nav>
        <button class="refresh-button" type="button" :disabled="refreshing" @click="loadSnapshot(true)">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8.1 8.1 0 1 0 .1 3M20 4v7h-7" /></svg>
          {{ refreshing ? '刷新中' : '刷新' }}
        </button>
      </header>

      <section class="book-hero" aria-labelledby="management-title">
        <div class="hero-copy">
          <p class="eyebrow">BOOK OPERATIONS · {{ formatDate(snapshot.book.created_at) }}</p>
          <h1 id="management-title">{{ snapshot.book.title }}</h1>
          <p class="hero-description">查看原文、译文与导读是否就绪，定位需要维护的章节。学习评估与画像已整理到独立工作区。</p>
          <div class="hero-actions">
            <router-link class="button button-primary" :to="{ name: 'reader', params: { id: bookId } }">
              进入阅读
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
            </router-link>
            <router-link class="button button-secondary" :to="{ name: 'book-learning', params: { id: bookId } }" target="_blank" rel="noopener">
              查看 Quiz · 画像
            </router-link>
          </div>
        </div>

        <div class="readiness-block" :class="`readiness-${snapshot.book.readiness}`">
          <div class="readiness-topline">
            <span class="live-dot" aria-hidden="true"></span>
            {{ snapshot.book.status_label }}
          </div>
          <strong>{{ snapshot.book.readiness_label }}</strong>
          <p>{{ readinessDescription }}</p>
          <div v-if="snapshot.book.is_busy" class="processing-line">
            <span></span>
          </div>
        </div>
      </section>

      <dl class="metric-strip">
        <div>
          <dt>正文章节</dt>
          <dd>{{ snapshot.content.source_chapters }}</dd>
          <small>{{ snapshot.content.chapters_total }} 个目录节点</small>
        </div>
        <div>
          <dt>译文覆盖</dt>
          <dd>{{ formatPercent(snapshot.content.translation_ratio) }}</dd>
          <small>{{ snapshot.content.translated_chapters }} / {{ snapshot.content.source_chapters }} 章</small>
        </div>
        <div>
          <dt>章节导读</dt>
          <dd>{{ snapshot.content.chapter_guides_ready }}</dd>
          <small>{{ guideAttentionText }}</small>
        </div>
      </dl>

      <section id="status" class="management-section status-section" aria-label="内容状态与维护">
        <div class="status-layout">
          <div class="pipeline" aria-label="内容处理流程">
            <article class="pipeline-row">
              <span class="pipeline-index">A</span>
              <div class="pipeline-copy">
                <h3>原文与章节结构</h3>
                <p>导入后形成 {{ snapshot.content.source_chapters }} 个有正文的章节，共 {{ snapshot.content.chapters_total }} 个目录节点。</p>
              </div>
              <span class="state-label state-ready">已就绪</span>
            </article>
            <article class="pipeline-row">
              <span class="pipeline-index">B</span>
              <div class="pipeline-copy">
                <h3>章节译文</h3>
                <p v-if="missingTranslationCount">仍有 {{ missingTranslationCount }} 章缺少译文；已有译文不会在“补全”操作中被覆盖。</p>
                <p v-else>所有有正文的章节均已有译文，可直接用于阅读、Guide、Chat 与 Quiz。</p>
              </div>
              <span :class="['state-label', missingTranslationCount ? 'state-attention' : 'state-ready']">
                {{ missingTranslationCount ? '待补全' : '已就绪' }}
              </span>
            </article>
            <article class="pipeline-row">
              <span class="pipeline-index">C</span>
              <div class="pipeline-copy">
                <h3>读前导读</h3>
                <p>{{ guidePipelineDescription }}</p>
              </div>
              <span :class="['state-label', guideNeedsWork ? 'state-attention' : 'state-ready']">
                {{ guideNeedsWork ? '待更新' : '已就绪' }}
              </span>
            </article>
          </div>

          <aside class="operation-panel">
            <p class="operation-kicker">MAINTENANCE</p>
            <h3>只重做需要重做的部分</h3>
            <p>重生成会消耗模型调用。操作被拆分后，你可以先判断问题发生在哪一层。</p>
            <div class="operation-list">
              <button type="button" :disabled="snapshot.book.is_busy || !missingTranslationCount || Boolean(loadingAction)" @click="completeTranslations">
                <span>
                  <strong>补全缺失译文</strong>
                  <small>保留已有译文，只处理缺失章节</small>
                </span>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
              </button>
              <button class="operation-regenerate" type="button" :disabled="snapshot.book.is_busy || Boolean(loadingAction)" @click="requestGuideRegeneration">
                <span>
                  <strong>重新生成全书导读</strong>
                  <small>会覆盖现有 Guide，并产生较多模型调用</small>
                </span>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
              </button>
            </div>
          </aside>
        </div>
      </section>

      <section id="chapters" class="management-section chapters-section">
        <header class="section-heading">
          <div>
            <p class="section-index">02 / CHAPTERS</p>
            <h2>章节概览</h2>
          </div>
          <p>按章节核对译文、导读与 Quiz 记录；重新翻译只替换所选章节，旧文件会保留到新译文成功写入。</p>
        </header>

        <div class="chapter-tools">
          <label class="chapter-search">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
            <span class="sr-only">搜索章节</span>
            <input v-model.trim="chapterQuery" type="search" placeholder="搜索编号或章节标题" />
          </label>
          <div class="filter-switch" role="group" aria-label="章节筛选">
            <button type="button" :class="{ active: chapterFilter === 'all' }" @click="chapterFilter = 'all'">全部 {{ snapshot.chapters.length }}</button>
            <button type="button" :class="{ active: chapterFilter === 'attention' }" @click="chapterFilter = 'attention'">需要处理 {{ actionableChapterCount }}</button>
          </div>
        </div>

        <div v-if="filteredChapters.length" class="chapter-table-wrap">
          <table class="chapter-table">
            <thead>
              <tr>
                <th>章节</th>
                <th>正文</th>
                <th>译文</th>
                <th>导读</th>
                <th>Quiz</th>
                <th><span class="sr-only">操作</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="chapter in displayedChapters" :key="chapter.id">
                <td class="chapter-name-cell">
                  <span class="chapter-number">{{ chapter.chapter_index }}</span>
                  <strong>{{ chapter.title }}</strong>
                  <small v-if="chapter.title_zh && chapter.title_en">{{ chapter.title_en }}</small>
                </td>
                <td>
                  <span :class="['compact-state', chapter.source.exists ? 'is-ready' : 'is-error']">
                    {{ chapter.source.exists ? '已导入' : '缺失' }}
                  </span>
                  <small>{{ formatCharacters(chapter.source.characters) }}</small>
                </td>
                <td>
                  <span :class="['compact-state', stateClass(chapter.translation.status)]">
                    {{ translationLabel(chapter.translation.status) }}
                  </span>
                  <small>{{ formatCharacters(chapter.translation.characters) }}</small>
                </td>
                <td>
                  <span :class="['compact-state', stateClass(chapter.guide.status)]">
                    {{ guideLabel(chapter.guide.status) }}
                  </span>
                  <small>{{ chapter.guide.count ? `${chapter.guide.count} 份` : '尚未生成' }}</small>
                </td>
                <td>
                  <strong class="quiz-attempt-count">{{ chapter.quiz.attempts }}</strong>
                  <small>{{ chapter.quiz.attempts ? `平均 ${formatPercent(chapter.quiz.average_score)}` : '暂无作答' }}</small>
                </td>
                <td class="chapter-actions-cell">
                  <router-link :to="chapterReaderRoute(chapter)" target="_blank" rel="noopener" title="在新标签页中打开本章" aria-label="在新标签页中打开本章">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V4H6.5A2.5 2.5 0 0 0 4 6.5z" /><path d="M4 6.5v13" /></svg>
                  </router-link>
                  <button v-if="chapter.guide.status !== 'ready'" type="button" :title="chapter.guide.status === 'missing' ? '生成本章导读' : '重新生成本章导读'" :aria-label="chapter.guide.status === 'missing' ? '生成本章导读' : '重新生成本章导读'" :disabled="snapshot.book.is_busy || !chapter.source.exists || Boolean(loadingAction)" @click="generateChapterGuide(chapter)">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3-1.1 4.1L7 8.2l3.9 1.1L12 13l1.1-3.7L17 8.2l-3.9-1.1zM5 15l-.7 2.3L2 18l2.3.7L5 21l.7-2.3L8 18l-2.3-.7zM19 14l-.9 3.1L15 18l3.1.9L19 22l.9-3.1L23 18l-3.1-.9z" /></svg>
                  </button>
                  <button type="button" title="重新翻译本章" aria-label="重新翻译本章" :disabled="snapshot.book.is_busy || !chapter.source.exists" @click="requestChapterRetranslation(chapter)">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8.1 8.1 0 1 0 .1 3M20 4v7h-7" /></svg>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="displayedChapters.length < filteredChapters.length" class="chapter-load-more">
            <span>已显示 {{ displayedChapters.length }} / {{ filteredChapters.length }} 章</span>
            <button type="button" @click="chapterLimit += 24">继续显示 24 章</button>
          </div>
        </div>
        <div v-else class="inline-empty">
          <p>没有符合当前筛选条件的章节。</p>
          <button type="button" @click="chapterQuery = ''; chapterFilter = 'all'">清除筛选</button>
        </div>
      </section>

    </div>

    <Transition name="toast">
      <div v-if="notice" class="management-toast" :class="`toast-${notice.type}`" role="status">
        <span>{{ notice.message }}</span>
        <button type="button" aria-label="关闭提示" @click="notice = null">×</button>
      </div>
    </Transition>

    <div v-if="confirmation" class="confirm-overlay" @click.self="confirmation = null">
      <section class="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
        <p class="eyebrow">REGENERATE</p>
        <h2 id="confirm-title">{{ confirmation.title }}</h2>
        <p>{{ confirmation.description }}</p>
        <div v-if="confirmation.kind === 'chapter'" class="confirm-note">新译文生成成功后才会替换当前译文。章节导读随后会标为“已过期”，直到你重新生成导读。</div>
        <div v-else class="confirm-note confirm-cost-note">这是全书操作，会发起多次模型调用并消耗较多 Token。启动后请等待后台完成，避免重复提交。</div>
        <footer>
          <button class="button button-secondary" type="button" @click="confirmation = null">取消</button>
          <button class="button button-primary" type="button" :disabled="Boolean(loadingAction)" @click="confirmRegeneration">
            {{ loadingAction ? '正在启动' : confirmation.kind === 'guides' ? '确认重新生成全书导读' : '确认重新生成' }}
          </button>
        </footer>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useBookStore } from '../stores/bookStore'

const route = useRoute()
const bookStore = useBookStore()
const bookId = computed(() => Number(route.params.id))
const snapshot = ref(null)
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const loadingAction = ref('')
const chapterQuery = ref('')
const chapterFilter = ref('all')
const chapterLimit = ref(24)
const confirmation = ref(null)
const notice = ref(null)
let pollingTimer = null
let noticeTimer = null

const missingTranslationCount = computed(() => {
  if (!snapshot.value) return 0
  return Math.max(0, snapshot.value.content.source_chapters - snapshot.value.content.translated_chapters)
})
const guideNeedsWork = computed(() => Boolean(
  snapshot.value && (
    snapshot.value.content.chapter_guides_missing || snapshot.value.content.chapter_guides_stale
  )
))
const actionableChapterCount = computed(() => snapshot.value?.chapters.filter(chapter => (
  chapter.translation.status !== 'ready' || chapter.guide.status !== 'ready'
)).length || 0)
const filteredChapters = computed(() => {
  const query = chapterQuery.value.toLocaleLowerCase()
  return (snapshot.value?.chapters || []).filter(chapter => {
    const matchesQuery = !query || `${chapter.chapter_index} ${chapter.title} ${chapter.title_en || ''}`.toLocaleLowerCase().includes(query)
    const matchesFilter = chapterFilter.value !== 'attention' || chapter.translation.status !== 'ready' || chapter.guide.status !== 'ready'
    return matchesQuery && matchesFilter
  })
})
const displayedChapters = computed(() => filteredChapters.value.slice(0, chapterLimit.value))
const readinessDescription = computed(() => {
  const descriptions = {
    ready: '正文、译文和章节导读都已就绪，可以把注意力放回阅读本身。',
    processing: '后台任务正在运行；页面会自动刷新，完成前请避免重复启动生成操作。',
    needs_attention: `有 ${missingTranslationCount.value} 个章节需要补全译文，请先处理内容层。`,
    guide_attention: '译文可读，但部分章节导读缺失或落后于当前译文。'
  }
  return descriptions[snapshot.value?.book.readiness] || '请检查下方的章节明细。'
})
const guideAttentionText = computed(() => {
  if (!snapshot.value) return ''
  const stale = snapshot.value.content.chapter_guides_stale
  const missing = snapshot.value.content.chapter_guides_missing
  if (!stale && !missing) return '全部与当前正文一致'
  return [stale ? `${stale} 份过期` : '', missing ? `${missing} 份缺失` : ''].filter(Boolean).join(' · ')
})
const guidePipelineDescription = computed(() => {
  if (!snapshot.value) return ''
  const content = snapshot.value.content
  if (!content.chapter_guides_stale && !content.chapter_guides_missing) {
    return `${content.chapter_guides_ready} 个章节导读均与当前正文同步。`
  }
  return `${content.chapter_guides_ready} 章可用，${content.chapter_guides_stale} 章已过期，${content.chapter_guides_missing} 章尚未生成。`
})
const showNotice = (message, type = 'success') => {
  if (noticeTimer) window.clearTimeout(noticeTimer)
  notice.value = { message, type }
  noticeTimer = window.setTimeout(() => {
    notice.value = null
    noticeTimer = null
  }, 4800)
}

const syncPolling = () => {
  if (snapshot.value?.book.is_busy && !pollingTimer) {
    pollingTimer = window.setInterval(() => loadSnapshot(true), 5000)
  } else if (!snapshot.value?.book.is_busy && pollingTimer) {
    window.clearInterval(pollingTimer)
    pollingTimer = null
  }
}

const markBackgroundWorkStarted = (status) => {
  if (!snapshot.value) return
  snapshot.value.book.status = status
  snapshot.value.book.status_label = status === 'generating_guides' ? '正在生成导读' : '正在翻译'
  snapshot.value.book.readiness = 'processing'
  snapshot.value.book.readiness_label = '处理中'
  snapshot.value.book.is_busy = true
  syncPolling()
  window.setTimeout(() => loadSnapshot(true), 900)
}

const loadSnapshot = async (silent = false) => {
  if (!silent) loading.value = true
  else refreshing.value = true
  error.value = ''
  try {
    snapshot.value = await bookStore.fetchBookManagement(bookId.value)
    syncPolling()
  } catch (err) {
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const completeTranslations = async () => {
  loadingAction.value = 'translation'
  try {
    await bookStore.translateBook(bookId.value)
    markBackgroundWorkStarted('translating')
    showNotice('已开始补全缺失译文，页面会自动更新')
  } catch (err) {
    showNotice(err.message, 'error')
  } finally {
    loadingAction.value = ''
  }
}

const requestGuideRegeneration = () => {
  confirmation.value = {
    kind: 'guides',
    title: '重新生成全书导读？',
    description: '现有书籍导读、目录导读与章节导读都会按当前译文重新生成，并覆盖已有结果。'
  }
}

const requestChapterRetranslation = (chapter) => {
  confirmation.value = {
    kind: 'chapter',
    chapter,
    title: `重新翻译 ${chapter.chapter_index} ${chapter.title}？`,
    description: '该操作会重新调用翻译模型，并在成功后替换这一章的现有译文。'
  }
}

const generateChapterGuide = async (chapter) => {
  loadingAction.value = `guide-${chapter.id}`
  try {
    await bookStore.generateChapterGuide(bookId.value, chapter.id)
    showNotice(`${chapter.chapter_index} 的章节导读已生成`)
    await loadSnapshot(true)
  } catch (err) {
    showNotice(`无法生成章节导读：${err.message}`, 'error')
  } finally {
    loadingAction.value = ''
  }
}

const confirmRegeneration = async () => {
  const pending = confirmation.value
  if (!pending) return
  loadingAction.value = pending.kind
  try {
    if (pending.kind === 'chapter') {
      await bookStore.retranslateChapter(bookId.value, pending.chapter.id)
      markBackgroundWorkStarted('translating')
      showNotice(`已开始重新翻译 ${pending.chapter.chapter_index}，旧译文会保留至成功写入`)
    } else {
      await bookStore.generateBookGuides(bookId.value)
      markBackgroundWorkStarted('generating_guides')
      showNotice('已开始重新生成导读，页面会自动更新')
    }
    confirmation.value = null
  } catch (err) {
    showNotice(err.message, 'error')
  } finally {
    loadingAction.value = ''
  }
}

const chapterReaderRoute = chapter => ({
  name: 'reader',
  params: { id: bookId.value },
  query: { reader_type: 'chapter', chapter_id: chapter.id }
})

const formatPercent = value => value === null || value === undefined ? '—' : `${Math.round(Number(value) * 100)}%`
const formatCharacters = value => Number(value || 0).toLocaleString('zh-CN') + ' 字符'
const formatDate = value => value ? new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }).format(new Date(value)) : '未知日期'
const translationLabel = status => ({ ready: '已翻译', missing: '缺失', source_missing: '原文缺失' }[status] || status)
const guideLabel = status => ({ ready: '已同步', stale: '已过期', missing: '缺失' }[status] || status)
const stateClass = status => status === 'ready' ? 'is-ready' : status === 'stale' || status === 'missing' ? 'is-attention' : 'is-error'

watch(() => snapshot.value?.book.is_busy, syncPolling)
watch([chapterQuery, chapterFilter], () => { chapterLimit.value = 24 })
onMounted(loadSnapshot)
onBeforeUnmount(() => {
  if (pollingTimer) window.clearInterval(pollingTimer)
  if (noticeTimer) window.clearTimeout(noticeTimer)
})
</script>

<style scoped>
.management-page {
  width: 100%;
  min-height: 100dvh;
  overflow-x: clip;
  color: var(--color-ink);
  font-family: var(--font-ui);
}

.management-shell {
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 0 3.25rem 7rem;
}

.management-header {
  min-height: 72px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  border-bottom: 1px solid var(--color-line-strong);
}

.back-link,
.refresh-button,
.section-nav a {
  color: var(--color-muted);
  font-size: .78rem;
  font-weight: 650;
  text-decoration: none;
}

.back-link {
  width: fit-content;
  display: inline-flex;
  align-items: center;
  gap: .35rem;
}

.back-link:hover,
.section-nav a:hover { color: var(--color-ink); }
.back-link svg,
.refresh-button svg,
.button svg,
.operation-list svg,
.chapter-actions-cell svg,
.chapter-search svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.section-nav { display: flex; gap: 1.75rem; }
.refresh-button {
  justify-self: end;
  display: inline-flex;
  align-items: center;
  gap: .45rem;
  padding: .45rem .65rem;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.book-hero {
  min-height: 360px;
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(310px, .75fr);
  gap: clamp(3rem, 8vw, 8rem);
  align-items: end;
  padding: 5.5rem 0 4rem;
}

.eyebrow,
.section-index,
.operation-kicker {
  margin: 0 0 1rem;
  color: var(--color-accent-dark);
  font-family: var(--font-mono);
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .16em;
}

.hero-copy h1 {
  max-width: 18ch;
  margin: 0;
  font-family: var(--font-ui);
  font-size: clamp(2.65rem, 5vw, 4.75rem);
  font-weight: 580;
  line-height: .98;
  letter-spacing: -.06em;
  overflow-wrap: anywhere;
  text-wrap: balance;
}

.hero-description {
  max-width: 60ch;
  margin: 1.5rem 0 0;
  color: var(--color-muted);
  font-size: .98rem;
  line-height: 1.8;
}

.hero-actions { display: flex; gap: .65rem; margin-top: 2rem; }
.button {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: .45rem;
  padding: .65rem 1rem;
  border-radius: 8px;
  font-size: .8rem;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}
.button-primary { border: 1px solid var(--color-ink); color: #fffaf2; background: var(--color-ink); }
.button-primary:hover { border-color: var(--color-accent-dark); background: var(--color-accent-dark); }
.button-secondary { border: 1px solid var(--color-line-strong); color: var(--color-ink); background: rgba(255,255,255,.55); }
.button-secondary:hover { background: var(--color-surface-raised); }

.readiness-block {
  position: relative;
  padding: 1.4rem 0 1.4rem 1.5rem;
  border-left: 3px solid var(--color-success);
}
.readiness-needs_attention { border-color: var(--color-danger); }
.readiness-processing,
.readiness-guide_attention { border-color: var(--color-warning); }
.readiness-topline { display: flex; align-items: center; gap: .5rem; color: var(--color-muted); font-size: .74rem; font-weight: 700; }
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.readiness-block strong { display: block; margin-top: .7rem; font-size: 1.65rem; line-height: 1.2; letter-spacing: -.03em; }
.readiness-block p { margin: .7rem 0 0; color: var(--color-muted); font-size: .85rem; line-height: 1.7; }
.processing-line { height: 2px; margin-top: 1.2rem; overflow: hidden; background: var(--color-line); }
.processing-line span { display: block; width: 45%; height: 100%; background: var(--color-warning); animation: status-scan 1.8s ease-in-out infinite; }
@keyframes status-scan { from { transform: translateX(-110%); } to { transform: translateX(330%); } }

.metric-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  margin: 0;
  border-block: 1px solid var(--color-line-strong);
}
.metric-strip > div { padding: 1.4rem 1.25rem 1.4rem 0; }
.metric-strip > div + div { padding-left: 1.25rem; border-left: 1px solid var(--color-line); }
.metric-strip dt { color: var(--color-muted); font-size: .72rem; font-weight: 650; }
.metric-strip dd { margin: .38rem 0 .05rem; font-family: var(--font-mono); font-size: 1.55rem; font-weight: 650; letter-spacing: -.04em; }
.metric-strip small { color: var(--color-faint); font-size: .69rem; }

.management-section { padding: 6.5rem 0 1rem; scroll-margin-top: 1rem; }
.section-heading { display: grid; grid-template-columns: minmax(0, 1fr) minmax(260px, 400px); gap: 4rem; align-items: end; margin-bottom: 2.5rem; }
.section-heading h2 { margin: 0; font-family: var(--font-ui); font-size: clamp(2rem, 3vw, 3rem); font-weight: 580; line-height: 1; letter-spacing: -.05em; }
.section-heading > p { margin: 0; color: var(--color-muted); font-size: .83rem; line-height: 1.75; }

.status-layout { display: grid; grid-template-columns: minmax(0, 1.65fr) minmax(320px, .75fr); gap: 4rem; }
.pipeline { border-top: 1px solid var(--color-line-strong); }
.pipeline-row { display: grid; grid-template-columns: 38px minmax(0, 1fr) auto; gap: 1.25rem; align-items: start; padding: 1.8rem 0; border-bottom: 1px solid var(--color-line); }
.pipeline-index { width: 30px; height: 30px; display: grid; place-items: center; border: 1px solid var(--color-line-strong); border-radius: 50%; color: var(--color-muted); font-family: var(--font-mono); font-size: .67rem; }
.pipeline-copy h3 { margin: 0 0 .4rem; font-size: .98rem; }
.pipeline-copy p { margin: 0; color: var(--color-muted); font-size: .8rem; line-height: 1.65; }
.state-label,
.compact-state { display: inline-flex; align-items: center; width: fit-content; border-radius: 999px; font-size: .68rem; font-weight: 700; white-space: nowrap; }
.state-label { padding: .3rem .6rem; }
.state-ready,
.is-ready { color: var(--color-success); background: var(--color-success-soft); }
.state-attention,
.is-attention { color: var(--color-warning); background: var(--color-warning-soft); }
.is-error { color: var(--color-danger); background: var(--color-danger-soft); }

.operation-panel { padding: 1.7rem; border: 1px solid var(--color-line-strong); border-radius: 16px; background: rgba(255,253,248,.62); box-shadow: 0 18px 50px rgba(63,49,31,.06); }
.operation-panel h3 { margin: 0; font-size: 1.35rem; letter-spacing: -.025em; }
.operation-panel > p:not(.operation-kicker) { margin: .7rem 0 1.2rem; color: var(--color-muted); font-size: .78rem; line-height: 1.65; }
.operation-list { border-top: 1px solid var(--color-line); }
.operation-list button { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 1rem 0; border: 0; border-bottom: 1px solid var(--color-line); color: var(--color-ink); text-align: left; background: transparent; cursor: pointer; }
.operation-list button:not(:disabled):hover { color: var(--color-accent-dark); transform: translateX(3px); }
.operation-list .operation-regenerate { color: #875c21; }
.operation-list .operation-regenerate:not(:disabled):hover { color: #9f3e2b; }
.operation-list span { display: grid; gap: .2rem; }
.operation-list strong { font-size: .78rem; }
.operation-list small { color: var(--color-muted); font-size: .68rem; font-weight: 450; }

.chapter-tools { display: flex; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
.chapter-search { min-width: min(100%, 360px); display: flex; align-items: center; gap: .6rem; padding: 0 .8rem; border: 1px solid var(--color-line); border-radius: 8px; color: var(--color-muted); background: rgba(255,255,255,.55); }
.chapter-search input { width: 100%; min-height: 40px; padding: 0; border: 0; outline: 0; background: transparent; font-size: .76rem; }
.filter-switch { display: flex; align-items: center; padding: 3px; border: 1px solid var(--color-line); border-radius: 8px; background: rgba(255,255,255,.55); }
.filter-switch button { padding: .45rem .75rem; border: 0; border-radius: 5px; color: var(--color-muted); background: transparent; font-size: .7rem; cursor: pointer; }
.filter-switch button.active { color: var(--color-ink); background: var(--color-surface-raised); box-shadow: var(--shadow-sm); }
.chapter-table-wrap { width: 100%; max-width: 100%; overflow-x: auto; contain: inline-size; border-top: 1px solid var(--color-line-strong); }
.chapter-table { width: 100%; border-collapse: collapse; text-align: left; }
.chapter-table th { padding: .8rem 1rem .8rem 0; color: var(--color-faint); font-family: var(--font-mono); font-size: .62rem; letter-spacing: .08em; text-transform: uppercase; }
.chapter-table td { min-width: 105px; padding: 1.15rem 1rem 1.15rem 0; border-top: 1px solid var(--color-line); vertical-align: middle; }
.chapter-table tbody tr:hover { background: rgba(255,255,255,.32); }
.chapter-name-cell { min-width: 300px !important; }
.chapter-number { display: block; margin-bottom: .2rem; color: var(--color-accent-dark); font-family: var(--font-mono); font-size: .64rem; }
.chapter-name-cell strong { max-width: 34ch; display: block; font-size: .8rem; line-height: 1.4; }
.chapter-table td small { display: block; max-width: 36ch; margin-top: .3rem; overflow: hidden; color: var(--color-faint); font-size: .64rem; line-height: 1.35; text-overflow: ellipsis; white-space: nowrap; }
.compact-state { padding: .22rem .48rem; }
.quiz-attempt-count { font-family: var(--font-mono); font-size: 1rem; }
.chapter-actions-cell { min-width: 118px !important; white-space: nowrap; }
.chapter-actions-cell a,
.chapter-actions-cell button { width: 32px; height: 32px; display: inline-grid; place-items: center; margin-left: .25rem; border: 1px solid var(--color-line); border-radius: 6px; color: var(--color-muted); background: var(--color-surface-raised); cursor: pointer; }
.chapter-actions-cell a:hover,
.chapter-actions-cell button:hover { border-color: var(--color-line-strong); color: var(--color-ink); }
.inline-empty { padding: 3rem; border-block: 1px solid var(--color-line); color: var(--color-muted); text-align: center; }
.inline-empty button { border: 0; color: var(--color-accent-dark); background: transparent; cursor: pointer; }
.chapter-load-more { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 1rem 0; border-bottom: 1px solid var(--color-line-strong); color: var(--color-faint); font-size: .68rem; }
.chapter-load-more button { padding: .45rem .7rem; border: 1px solid var(--color-line); border-radius: 6px; color: var(--color-ink); background: var(--color-surface-raised); font-size: .7rem; cursor: pointer; }
.chapter-load-more button:hover { border-color: var(--color-line-strong); }

.management-error { display: grid; place-content: center; min-height: 100dvh; text-align: center; }
.management-error h1 { max-width: 20ch; margin: 0; font-family: var(--font-ui); font-size: 2rem; }
.management-error > p:not(.eyebrow) { color: var(--color-muted); }
.error-actions { display: flex; justify-content: center; gap: .5rem; }
.management-loading { padding-top: 2rem; }
.skeleton { position: relative; overflow: hidden; border-radius: 12px; background: var(--color-surface-muted); }
.skeleton::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,.65), transparent); animation: skeleton-shimmer 1.5s infinite; }
@keyframes skeleton-shimmer { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
.skeleton-nav { height: 42px; }
.skeleton-hero { height: 300px; margin-top: 2rem; }
.skeleton-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 2rem; margin-top: 2rem; }
.skeleton-panel { height: 280px; }

.management-toast { position: fixed; right: 1.5rem; bottom: 1.5rem; z-index: 30; max-width: min(420px, calc(100vw - 2rem)); display: flex; align-items: center; gap: 1rem; padding: .85rem 1rem; border: 1px solid var(--color-line-strong); border-radius: 9px; color: var(--color-ink); background: var(--color-surface-raised); box-shadow: var(--shadow-lg); font-size: .76rem; }
.management-toast::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: var(--color-success); }
.management-toast.toast-error::before { background: var(--color-danger); }
.management-toast button { margin-left: auto; border: 0; color: var(--color-muted); background: transparent; cursor: pointer; }
.toast-enter-active,.toast-leave-active { transition: opacity .2s ease, transform .2s ease; }
.toast-enter-from,.toast-leave-to { opacity: 0; transform: translateY(8px); }

.confirm-overlay { position: fixed; inset: 0; z-index: 40; display: grid; place-items: center; padding: 1rem; background: rgba(28,27,24,.38); backdrop-filter: blur(5px); }
.confirm-dialog { width: min(100%, 500px); padding: 2rem; border: 1px solid rgba(255,255,255,.55); border-radius: 16px; background: var(--color-surface-raised); box-shadow: var(--shadow-lg); }
.confirm-dialog h2 { margin: 0; font-family: var(--font-ui); font-size: 1.45rem; letter-spacing: -.03em; }
.confirm-dialog > p:not(.eyebrow) { color: var(--color-muted); font-size: .8rem; line-height: 1.7; }
.confirm-note { padding: .8rem; border-left: 2px solid var(--color-warning); color: var(--color-muted); background: var(--color-warning-soft); font-size: .72rem; line-height: 1.6; }
.confirm-cost-note { border-left-color: var(--color-danger); color: #7d3e30; background: var(--color-danger-soft); }
.confirm-dialog footer { display: flex; justify-content: flex-end; gap: .5rem; margin-top: 1.5rem; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }

@media (max-width: 960px) {
  .management-shell { padding-inline: 1.5rem; }
  .management-header { grid-template-columns: 1fr auto; }
  .section-nav { display: none; }
  .book-hero { grid-template-columns: 1fr; gap: 3rem; padding-block: 4rem 3rem; }
  .readiness-block { max-width: 520px; }
  .metric-strip { grid-template-columns: repeat(3, 1fr); }
  .metric-strip > div:nth-child(4) { padding-left: 0; border-left: 0; border-top: 1px solid var(--color-line); }
  .metric-strip > div:nth-child(n+4) { border-top: 1px solid var(--color-line); }
  .status-layout { grid-template-columns: 1fr; gap: 2.5rem; }
}

@media (max-width: 720px) {
  .management-shell { padding-inline: 1rem; padding-bottom: 4rem; }
  .management-header { min-height: 60px; }
  .hero-copy h1 { font-size: 2.5rem; }
  .hero-actions { align-items: stretch; flex-direction: column; }
  .metric-strip { grid-template-columns: repeat(2, 1fr); }
  .metric-strip > div { padding: 1rem !important; border-top: 1px solid var(--color-line); border-left: 0 !important; }
  .metric-strip > div:nth-child(even) { border-left: 1px solid var(--color-line) !important; }
  .metric-strip > div:first-child,
  .metric-strip > div:nth-child(2) { border-top: 0; }
  .management-section { padding-top: 4.5rem; }
  .section-heading { grid-template-columns: 1fr; gap: 1rem; }
  .chapter-tools { align-items: stretch; flex-direction: column; }
  .chapter-search { min-width: 100%; }
  .filter-switch button { flex: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .processing-line span,
  .skeleton::after { animation: none; }
}
</style>
