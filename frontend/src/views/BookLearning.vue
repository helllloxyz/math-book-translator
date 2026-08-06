<template>
  <main class="learning-page">
    <div v-if="loading" class="learning-shell learning-loading" aria-label="正在加载 Quiz 评估与学习画像">
      <div class="skeleton skeleton-nav"></div>
      <div class="skeleton skeleton-hero"></div>
      <div class="skeleton-grid">
        <div class="skeleton skeleton-panel"></div>
        <div class="skeleton skeleton-panel"></div>
      </div>
    </div>

    <section v-else-if="error" class="learning-shell learning-error">
      <p class="eyebrow">LEARNING REVIEW</p>
      <h1>没有读到这本书的学习数据</h1>
      <p>{{ error }}</p>
      <div class="error-actions">
        <button class="button button-primary" type="button" @click="loadSnapshot">重新加载</button>
        <router-link class="button button-secondary" :to="{ name: 'library' }">返回书库</router-link>
      </div>
    </section>

    <div v-else-if="snapshot" class="learning-shell">
      <header class="learning-header">
        <router-link class="back-link" :to="{ name: 'library' }" aria-label="返回书库">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 18-6-6 6-6" /></svg>
          书库
        </router-link>
        <nav class="section-nav" aria-label="页面导航">
          <a href="#quiz">Quiz 评估</a>
          <a href="#profile">学习画像</a>
        </nav>
        <router-link class="status-link" :to="{ name: 'book-management', params: { id: bookId } }" target="_blank" rel="noopener">
          内容状态 ↗
        </router-link>
      </header>

      <section class="learning-hero" aria-labelledby="learning-title">
        <div class="hero-copy">
          <p class="eyebrow">LEARNING REVIEW · {{ formatDate(snapshot.book.created_at) }}</p>
          <h1 id="learning-title">{{ snapshot.book.title }}</h1>
          <p class="hero-description">把 Quiz 作答、笔记证据和学习画像放在同一个复习工作区。这里关注“是否真正理解”，内容生成与维护留在状态页。</p>
          <div class="hero-actions">
            <button class="button button-primary" type="button" :disabled="loadingAction === 'quiz'" @click="startBookQuiz">
              {{ loadingAction === 'quiz' ? '正在选择题目' : '开始全书 Quiz' }}
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
            </button>
            <router-link class="button button-secondary" :to="{ name: 'notes', params: { id: bookId } }" target="_blank" rel="noopener">
              查看学习笔记 ↗
            </router-link>
          </div>
        </div>

        <aside class="evidence-block" :class="{ 'has-pending': snapshot.profile.should_analyze }">
          <div class="evidence-topline">
            <span class="live-dot" aria-hidden="true"></span>
            LEARNING EVIDENCE
          </div>
          <strong>{{ snapshot.profile.should_analyze ? '有新证据待整理' : '画像与记录同步' }}</strong>
          <p>{{ profilePendingText }}</p>
          <button
            type="button"
            :disabled="!snapshot.profile.should_analyze || Boolean(loadingAction)"
            @click="analyzeProfile"
          >
            {{ loadingAction === 'profile' ? '正在分析…' : snapshot.profile.should_analyze ? '更新学习画像' : '画像已是最新' }}
          </button>
        </aside>
      </section>

      <dl class="metric-strip">
        <div>
          <dt>已生成题目</dt>
          <dd>{{ snapshot.quiz.questions }}</dd>
          <small>覆盖全书与章节练习</small>
        </div>
        <div>
          <dt>Quiz 作答</dt>
          <dd>{{ snapshot.quiz.attempts }}</dd>
          <small>{{ snapshot.quiz.completed }} 次掌握</small>
        </div>
        <div>
          <dt>平均评估</dt>
          <dd>{{ formatPercent(snapshot.quiz.average_score) }}</dd>
          <small>基于语义理解评估</small>
        </div>
        <div>
          <dt>学习笔记</dt>
          <dd>{{ snapshot.activity.notes }}</dd>
          <small>{{ totalPendingEvidence }} 条待纳入画像</small>
        </div>
      </dl>

      <section id="quiz" class="learning-section quiz-section">
        <header class="section-heading">
          <div>
            <p class="section-index">01 / QUIZ REVIEW</p>
            <h2>Quiz 评估</h2>
          </div>
          <p>这里呈现语义评估结果，不把关键词命中当成掌握。样本较少时，它更适合作为下一轮阅读的方向提示。</p>
        </header>

        <div v-if="snapshot.quiz.attempts" class="quiz-layout">
          <div class="quiz-summary">
            <div class="score-figure">
              <span>平均评估</span>
              <strong>{{ formatPercent(snapshot.quiz.average_score) }}</strong>
              <p>基于 {{ snapshot.quiz.attempts }} 次作答</p>
            </div>
            <dl class="outcome-list">
              <div><dt><span class="outcome-dot completed"></span>掌握</dt><dd>{{ snapshot.quiz.completed }}</dd></div>
              <div><dt><span class="outcome-dot partial"></span>部分掌握</dt><dd>{{ snapshot.quiz.partial }}</dd></div>
              <div><dt><span class="outcome-dot wrong"></span>需要复习</dt><dd>{{ snapshot.quiz.wrong }}</dd></div>
            </dl>
          </div>

          <div class="type-evaluation">
            <h3>按能力类型</h3>
            <div v-for="type in snapshot.quiz.type_breakdown" :key="type.question_type" class="type-row">
              <div class="type-row-heading">
                <span>{{ type.label }}</span>
                <span>{{ type.attempts }} 次 · {{ formatPercent(type.average_score) }}</span>
              </div>
              <div class="score-track" aria-hidden="true"><span :style="{ transform: `scaleX(${type.average_score || 0})` }"></span></div>
            </div>
          </div>

          <div class="recent-evaluations">
            <div class="subsection-heading">
              <h3>最近评估</h3>
              <span>展开可查看回答与反馈</span>
            </div>
            <details v-for="attempt in snapshot.quiz.recent_attempts" :key="attempt.id" class="attempt-row">
              <summary>
                <span class="attempt-status" :class="`attempt-${attempt.evaluation_status}`">{{ attempt.evaluation_status_label }}</span>
                <span class="attempt-main">
                  <strong>{{ attempt.question_text }}</strong>
                  <small>{{ attempt.chapter_title }} · {{ attempt.question_type_label }} · {{ formatDateTime(attempt.created_at) }}</small>
                </span>
                <span class="attempt-score">{{ formatPercent(attempt.score) }}</span>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
              </summary>
              <div class="attempt-detail">
                <div><span>你的回答</span><p>{{ attempt.answer_text }}</p></div>
                <div><span>评估反馈</span><p>{{ attempt.feedback_text || '暂无文字反馈' }}</p></div>
                <div v-if="attempt.missing_points?.length"><span>尚缺要点</span><ul><li v-for="point in attempt.missing_points" :key="point">{{ point }}</li></ul></div>
              </div>
            </details>
          </div>
        </div>

        <div v-else class="quiz-empty">
          <div class="empty-mark" aria-hidden="true">Q</div>
          <div>
            <h3>还没有可评估的作答</h3>
            <p>完成几次章节 Quiz 或全书 Quiz 后，这里会按概念解释、定理理解、证明策略和概念连接展示学习表现。</p>
          </div>
          <button class="button button-primary" type="button" :disabled="loadingAction === 'quiz'" @click="startBookQuiz">开始第一次全书 Quiz</button>
        </div>
      </section>

      <section id="profile" class="learning-section profile-section">
        <header class="section-heading">
          <div>
            <p class="section-index">02 / LEARNING PROFILE</p>
            <h2>学习画像</h2>
          </div>
          <p>画像把分散的笔记和 Quiz 反馈压缩成强项、薄弱概念、常见误区与下一步目标，不替代原始学习记录。</p>
        </header>

        <div class="profile-layout">
          <aside class="profile-meta">
            <div>
              <span>上次分析</span>
              <strong>{{ snapshot.profile.last_analyzed_at ? formatDateTime(snapshot.profile.last_analyzed_at) : '尚未分析' }}</strong>
            </div>
            <div>
              <span>累计分析</span>
              <strong>{{ snapshot.profile.meta?.analysis_count || 0 }} 次</strong>
            </div>
            <div>
              <span>待处理证据</span>
              <strong>{{ totalPendingEvidence }} 条</strong>
            </div>
            <button class="button button-primary" type="button" :disabled="!snapshot.profile.should_analyze || Boolean(loadingAction)" @click="analyzeProfile">
              {{ loadingAction === 'profile' ? '正在分析' : snapshot.profile.should_analyze ? '更新画像' : '画像已是最新' }}
            </button>
          </aside>
          <article ref="profileRef" class="profile-document markdown-content" v-html="profileHtml"></article>
        </div>
      </section>
    </div>

    <Transition name="toast">
      <div v-if="notice" class="learning-toast" :class="`toast-${notice.type}`" role="status" aria-live="polite">
        <span>{{ notice.message }}</span>
        <button type="button" aria-label="关闭提示" @click="notice = null">×</button>
      </div>
    </Transition>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBookStore } from '../stores/bookStore'
import { renderMarkdown, renderMath } from '../utils/renderer'

const route = useRoute()
const router = useRouter()
const bookStore = useBookStore()
const bookId = computed(() => Number(route.params.id))
const snapshot = ref(null)
const loading = ref(true)
const error = ref('')
const loadingAction = ref('')
const notice = ref(null)
const profileRef = ref(null)
let noticeTimer = null

const totalPendingEvidence = computed(() => (
  Number(snapshot.value?.profile.unprocessed_notes_count || 0)
  + Number(snapshot.value?.profile.unprocessed_quiz_count || 0)
))

const profilePendingText = computed(() => {
  if (!snapshot.value?.profile.should_analyze) return '当前没有新的笔记或 Quiz 证据需要分析。'
  return `${snapshot.value.profile.unprocessed_notes_count || 0} 条笔记、${snapshot.value.profile.unprocessed_quiz_count || 0} 次 Quiz 等待纳入画像。`
})

const profileHtml = computed(() => {
  const rawProfile = snapshot.value?.profile.markdown || ''
  const content = !rawProfile || rawProfile.includes('No analyzed learning activity yet')
    ? '# 尚未生成学习画像\n\n创建阅读笔记或完成 Quiz 后，可以在这里把学习证据整理成强项、薄弱概念和下一步目标。'
    : rawProfile
  return renderMarkdown(content)
})

const showNotice = (message, type = 'success') => {
  if (noticeTimer) window.clearTimeout(noticeTimer)
  notice.value = { message, type }
  noticeTimer = window.setTimeout(() => {
    notice.value = null
    noticeTimer = null
  }, 4800)
}

const loadSnapshot = async () => {
  loading.value = true
  error.value = ''
  try {
    snapshot.value = await bookStore.fetchBookManagement(bookId.value)
    await nextTick()
    if (profileRef.value) renderMath(profileRef.value)
  } catch (err) {
    error.value = err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

const analyzeProfile = async () => {
  loadingAction.value = 'profile'
  try {
    const result = await bookStore.analyzeLearningProfile(bookId.value)
    showNotice(result.summary || '学习画像已更新')
    await loadSnapshot()
  } catch (err) {
    showNotice(err.message, 'error')
  } finally {
    loadingAction.value = ''
  }
}

const startBookQuiz = async () => {
  loadingAction.value = 'quiz'
  try {
    const target = await bookStore.selectBookQuizTarget(bookId.value)
    window.sessionStorage.setItem(`bookQuizTarget:${bookId.value}`, JSON.stringify(target))
    await router.push({
      name: 'reader',
      params: { id: bookId.value },
      query: {
        reader_type: 'chapter',
        chapter_id: target.chapter_id,
        quiz: '1',
        quiz_mode: 'book',
        question_type: target.question_type
      }
    })
  } catch (err) {
    showNotice(`无法开始全书 Quiz：${err.message}`, 'error')
  } finally {
    loadingAction.value = ''
  }
}

const formatPercent = value => value === null || value === undefined ? '—' : `${Math.round(Number(value) * 100)}%`
const formatDate = value => value ? new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }).format(new Date(value)) : '未知日期'
const formatDateTime = value => value ? new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '尚无记录'

onMounted(loadSnapshot)
onBeforeUnmount(() => {
  if (noticeTimer) window.clearTimeout(noticeTimer)
})
</script>

<style scoped>
.learning-page {
  width: 100%;
  min-height: 100dvh;
  overflow-x: clip;
  color: var(--color-ink);
  font-family: var(--font-ui);
}

.learning-shell {
  width: min(100%, 1440px);
  margin: 0 auto;
  padding: 0 3.25rem 7rem;
}

.learning-header {
  min-height: 72px;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  border-bottom: 1px solid var(--color-line-strong);
}

.back-link,
.status-link,
.section-nav a {
  color: var(--color-muted);
  font-size: .78rem;
  font-weight: 650;
  text-decoration: none;
}

.back-link { width: fit-content; display: inline-flex; align-items: center; gap: .35rem; }
.status-link { justify-self: end; }
.back-link:hover,
.status-link:hover,
.section-nav a:hover { color: var(--color-ink); }
.back-link:focus-visible,
.status-link:focus-visible,
.section-nav a:focus-visible,
.button:focus-visible,
.evidence-block button:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 3px; }
.section-nav { display: flex; gap: 1.75rem; }

.back-link svg,
.button svg,
.attempt-row summary > svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.learning-hero {
  min-height: 390px;
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(310px, .75fr);
  gap: clamp(3rem, 8vw, 8rem);
  align-items: end;
  padding: 5.5rem 0 4rem;
}

.eyebrow,
.section-index {
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
  font-size: clamp(2.65rem, 5vw, 4.75rem);
  font-weight: 580;
  line-height: .98;
  letter-spacing: -.06em;
  overflow-wrap: anywhere;
  text-wrap: balance;
}

.hero-description { max-width: 62ch; margin: 1.5rem 0 0; color: var(--color-muted); font-size: .98rem; line-height: 1.8; }
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
  transition: transform .2s ease, color .2s ease, background .2s ease, border-color .2s ease;
}
.button:not(:disabled):active { transform: translateY(1px); }
.button-primary { border: 1px solid var(--color-ink); color: #fffaf2; background: var(--color-ink); }
.button-primary:hover:not(:disabled) { border-color: var(--color-accent-dark); background: var(--color-accent-dark); }
.button-secondary { border: 1px solid var(--color-line-strong); color: var(--color-ink); background: rgba(255,255,255,.55); }
.button-secondary:hover { background: var(--color-surface-raised); }
.button:disabled,
.evidence-block button:disabled { opacity: .55; cursor: not-allowed; }

.evidence-block { padding: 1.4rem 0 1.4rem 1.5rem; border-left: 3px solid var(--color-success); }
.evidence-block.has-pending { border-color: var(--color-warning); }
.evidence-topline { display: flex; align-items: center; gap: .5rem; color: var(--color-muted); font-family: var(--font-mono); font-size: .68rem; font-weight: 700; letter-spacing: .1em; }
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.evidence-block strong { display: block; margin-top: .7rem; font-size: 1.65rem; line-height: 1.2; letter-spacing: -.03em; }
.evidence-block p { margin: .7rem 0 0; color: var(--color-muted); font-size: .82rem; line-height: 1.7; }
.evidence-block button { margin-top: 1rem; padding: .5rem 0; border: 0; border-bottom: 1px solid currentColor; color: var(--color-accent-dark); background: transparent; font-size: .74rem; font-weight: 700; cursor: pointer; }

.metric-strip { display: grid; grid-template-columns: repeat(4, 1fr); margin: 0; border-block: 1px solid var(--color-line-strong); }
.metric-strip > div { padding: 1.4rem 1.25rem 1.4rem 0; }
.metric-strip > div + div { padding-left: 1.25rem; border-left: 1px solid var(--color-line); }
.metric-strip dt { color: var(--color-muted); font-size: .72rem; font-weight: 650; }
.metric-strip dd { margin: .38rem 0 .05rem; font-family: var(--font-mono); font-size: 1.55rem; font-weight: 650; letter-spacing: -.04em; }
.metric-strip small { color: var(--color-faint); font-size: .69rem; }

.learning-section { padding: 6.5rem 0 1rem; scroll-margin-top: 1rem; }
.section-heading { display: grid; grid-template-columns: minmax(0, 1fr) minmax(260px, 400px); gap: 4rem; align-items: end; margin-bottom: 2.5rem; }
.section-heading h2 { margin: 0; font-size: clamp(2rem, 3vw, 3rem); font-weight: 580; line-height: 1; letter-spacing: -.05em; }
.section-heading > p { margin: 0; color: var(--color-muted); font-size: .83rem; line-height: 1.75; }

.quiz-layout { display: grid; grid-template-columns: minmax(260px, .7fr) minmax(320px, 1fr); gap: 3rem 5rem; }
.quiz-summary { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; padding: 1.6rem 0; border-block: 1px solid var(--color-line-strong); }
.score-figure span,
.profile-meta span { color: var(--color-muted); font-size: .68rem; }
.score-figure strong { display: block; margin: .5rem 0; font-family: var(--font-mono); font-size: 3rem; line-height: 1; letter-spacing: -.08em; }
.score-figure p { margin: 0; color: var(--color-faint); font-size: .7rem; }
.outcome-list { margin: 0; }
.outcome-list div { display: flex; justify-content: space-between; padding: .45rem 0; border-bottom: 1px solid var(--color-line); font-size: .72rem; }
.outcome-list dt { display: flex; align-items: center; gap: .45rem; color: var(--color-muted); }
.outcome-list dd { margin: 0; font-family: var(--font-mono); font-weight: 700; }
.outcome-dot { width: 7px; height: 7px; border-radius: 50%; }
.outcome-dot.completed { background: var(--color-success); }
.outcome-dot.partial { background: var(--color-warning); }
.outcome-dot.wrong { background: var(--color-danger); }
.type-evaluation { padding: 1.6rem 0; border-block: 1px solid var(--color-line-strong); }
.type-evaluation h3,
.subsection-heading h3 { margin: 0 0 1.2rem; font-size: .88rem; }
.type-row + .type-row { margin-top: 1.05rem; }
.type-row-heading { display: flex; justify-content: space-between; gap: 1rem; margin-bottom: .38rem; color: var(--color-muted); font-size: .69rem; }
.type-row-heading span:first-child { color: var(--color-ink); font-weight: 650; }
.score-track { height: 5px; overflow: hidden; background: var(--color-surface-muted); }
.score-track span { display: block; width: 100%; height: 100%; transform-origin: left; background: var(--color-accent); transition: transform .55s cubic-bezier(.16,1,.3,1); }
.recent-evaluations { grid-column: 1 / -1; }
.subsection-heading { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--color-line-strong); }
.subsection-heading span { color: var(--color-faint); font-size: .67rem; }
.attempt-row { border-bottom: 1px solid var(--color-line); }
.attempt-row summary { display: grid; grid-template-columns: auto minmax(0, 1fr) 60px 20px; gap: 1rem; align-items: center; padding: 1.1rem 0; list-style: none; cursor: pointer; }
.attempt-row summary::-webkit-details-marker { display: none; }
.attempt-status { display: inline-flex; align-items: center; width: fit-content; padding: .25rem .5rem; border-radius: 999px; font-size: .68rem; font-weight: 700; white-space: nowrap; }
.attempt-completed { color: var(--color-success); background: var(--color-success-soft); }
.attempt-partial { color: var(--color-warning); background: var(--color-warning-soft); }
.attempt-wrong { color: var(--color-danger); background: var(--color-danger-soft); }
.attempt-main { min-width: 0; }
.attempt-main strong { display: block; overflow: hidden; font-size: .76rem; font-weight: 650; text-overflow: ellipsis; white-space: nowrap; }
.attempt-main small { display: block; margin-top: .28rem; color: var(--color-faint); font-size: .64rem; }
.attempt-score { font-family: var(--font-mono); font-size: .78rem; text-align: right; }
.attempt-row[open] summary > svg { transform: rotate(180deg); }
.attempt-detail { display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; padding: 0 7rem 1.5rem 0; }
.attempt-detail span { color: var(--color-accent-dark); font-family: var(--font-mono); font-size: .62rem; letter-spacing: .08em; }
.attempt-detail p,
.attempt-detail ul { margin: .45rem 0 0; color: var(--color-muted); font-size: .74rem; line-height: 1.7; }
.quiz-empty { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 1.5rem; align-items: center; padding: 2rem 0; border-block: 1px solid var(--color-line-strong); }
.empty-mark { width: 52px; height: 52px; display: grid; place-items: center; border: 1px solid var(--color-line-strong); border-radius: 50%; color: var(--color-accent-dark); font-family: var(--font-mono); }
.quiz-empty h3 { margin: 0; font-size: 1rem; }
.quiz-empty p { max-width: 70ch; margin: .4rem 0 0; color: var(--color-muted); font-size: .76rem; line-height: 1.65; }

.profile-layout { display: grid; grid-template-columns: minmax(230px, .55fr) minmax(0, 1.7fr); gap: 5rem; align-items: start; }
.profile-meta { position: sticky; top: 1.5rem; display: grid; border-top: 1px solid var(--color-line-strong); }
.profile-meta > div { display: grid; gap: .3rem; padding: 1rem 0; border-bottom: 1px solid var(--color-line); }
.profile-meta strong { font-size: .8rem; }
.profile-meta .button { margin-top: 1rem; }
.profile-document { min-height: 320px; padding: 2.5rem clamp(1.5rem, 4vw, 4rem); border: 1px solid var(--color-line); border-radius: 16px; background: var(--color-surface-raised); box-shadow: 0 18px 52px rgba(63,49,31,.065); }
:deep(.profile-document h1),
:deep(.profile-document h2),
:deep(.profile-document h3) { letter-spacing: -.03em; }
:deep(.profile-document h1) { margin-top: 0; font-size: 1.65rem; }
:deep(.profile-document h2) { margin-top: 2rem; padding-top: 1.2rem; border-top: 1px solid var(--color-line); font-size: 1.15rem; }
:deep(.profile-document h3) { font-size: .92rem; }
:deep(.profile-document p),
:deep(.profile-document li) { color: var(--color-ink-soft); font-size: .82rem; line-height: 1.8; }

.learning-error { display: grid; place-content: center; min-height: 100dvh; text-align: center; }
.learning-error h1 { max-width: 20ch; margin: 0; font-size: 2rem; }
.learning-error > p:not(.eyebrow) { color: var(--color-muted); }
.error-actions { display: flex; justify-content: center; gap: .5rem; }
.learning-loading { padding-top: 2rem; }
.skeleton { position: relative; overflow: hidden; border-radius: 12px; background: var(--color-surface-muted); }
.skeleton::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, transparent, rgba(255,255,255,.65), transparent); animation: skeleton-shimmer 1.5s infinite; }
@keyframes skeleton-shimmer { from { transform: translateX(-100%); } to { transform: translateX(100%); } }
.skeleton-nav { height: 42px; }
.skeleton-hero { height: 300px; margin-top: 2rem; }
.skeleton-grid { display: grid; grid-template-columns: 1.5fr 1fr; gap: 2rem; margin-top: 2rem; }
.skeleton-panel { height: 280px; }

.learning-toast { position: fixed; right: 1.5rem; bottom: 1.5rem; z-index: 30; max-width: min(420px, calc(100vw - 2rem)); display: flex; align-items: center; gap: 1rem; padding: .85rem 1rem; border: 1px solid var(--color-line-strong); border-radius: 9px; color: var(--color-ink); background: var(--color-surface-raised); box-shadow: var(--shadow-lg); font-size: .76rem; }
.learning-toast::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: var(--color-success); }
.learning-toast.toast-error::before { background: var(--color-danger); }
.learning-toast button { margin-left: auto; border: 0; color: var(--color-muted); background: transparent; cursor: pointer; }
.toast-enter-active,.toast-leave-active { transition: opacity .2s ease, transform .2s ease; }
.toast-enter-from,.toast-leave-to { opacity: 0; transform: translateY(8px); }

@media (max-width: 960px) {
  .learning-shell { padding-inline: 1.5rem; }
  .learning-header { grid-template-columns: 1fr auto; }
  .section-nav { display: none; }
  .learning-hero { grid-template-columns: 1fr; gap: 3rem; padding-block: 4rem 3rem; }
  .evidence-block { max-width: 520px; }
  .metric-strip { grid-template-columns: repeat(2, 1fr); }
  .metric-strip > div:nth-child(3) { padding-left: 0; border-left: 0; }
  .metric-strip > div:nth-child(n+3) { border-top: 1px solid var(--color-line); }
  .profile-layout { grid-template-columns: 1fr; gap: 2.5rem; }
  .profile-meta { position: static; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
  .profile-meta .button { grid-column: 1 / -1; }
}

@media (max-width: 720px) {
  .learning-shell { padding-inline: 1rem; padding-bottom: 4rem; }
  .learning-header { min-height: 60px; }
  .status-link { font-size: .7rem; }
  .hero-copy h1 { font-size: 2.5rem; }
  .hero-actions { align-items: stretch; flex-direction: column; }
  .metric-strip > div { padding: 1rem !important; }
  .learning-section { padding-top: 4.5rem; }
  .section-heading { grid-template-columns: 1fr; gap: 1rem; }
  .quiz-layout { grid-template-columns: 1fr; gap: 1.5rem; }
  .recent-evaluations { grid-column: auto; }
  .attempt-row summary { grid-template-columns: auto minmax(0,1fr) 18px; }
  .attempt-score { display: none; }
  .attempt-detail { grid-template-columns: 1fr; gap: 1rem; padding-right: 0; }
  .quiz-empty { grid-template-columns: auto 1fr; }
  .quiz-empty .button { grid-column: 1 / -1; }
  .profile-meta { grid-template-columns: 1fr; }
  .profile-meta .button { grid-column: auto; }
  .profile-document { padding: 1.5rem; }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton::after { animation: none; }
}
</style>
