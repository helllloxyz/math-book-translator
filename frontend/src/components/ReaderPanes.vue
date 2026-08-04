<template>
  <main ref="viewportRef" class="content-viewport" :class="effectiveViewMode" @scroll="handleViewportScroll">
    <div v-if="loading" class="reader-content-skeleton" aria-label="正在加载章节">
      <span class="content-skeleton-title"></span>
      <span v-for="index in 7" :key="index" class="content-skeleton-line" :class="`line-${index}`"></span>
    </div>
    <section v-else-if="!currentItem" class="center-state reader-empty-state">
      <span aria-hidden="true">§</span>
      <h2>选择一个章节开始阅读</h2>
      <p>目录中的章节、学习摘要和导读会在这里展开。</p>
    </section>

    <template v-else-if="effectiveViewMode === 'single'">
      <div class="pane-container single-layout">
        <div class="text-column">
          <div
            class="markdown-body latex-content"
            data-content-target="translated"
            data-annotation-eligible="true"
            :key="`single-${currentItem.id}`"
            v-html="renderedTarget"
          ></div>
          <nav v-if="previousItem || nextItem" class="reader-pagination" aria-label="Chapter navigation">
            <button
              v-if="previousItem"
              type="button"
              class="pagination-button"
              @click="emit('go-previous')"
            >
              <span>上一篇</span>
              <strong>{{ previousItem.title }}</strong>
            </button>
            <span v-else></span>
            <button
              v-if="nextItem"
              type="button"
              class="pagination-button pagination-button-next"
              @click="emit('go-next')"
            >
              <span>下一篇</span>
              <strong>{{ nextItem.title }}</strong>
            </button>
          </nav>
        </div>
      </div>
    </template>

    <template v-else>
      <div ref="leftPaneRef" class="pane source-pane" @scroll="syncPaneScroll('left', $event)">
        <div
          class="markdown-body latex-content"
          :data-content-target="leftContentTarget"
          :data-annotation-eligible="leftAnnotationEligible ? 'true' : 'false'"
          :key="leftPaneKey"
          v-html="leftPaneHtml"
        ></div>
      </div>

      <div ref="rightPaneRef" class="pane target-pane" @scroll="syncPaneScroll('right', $event)">
        <div v-if="isGuideDual && guideLoading" class="pane-state">Loading chapter guide...</div>
        <div v-else-if="guideUnavailable" class="pane-state">
          No chapter guide is available for this chapter yet.
        </div>
        <div
          v-else
          class="markdown-body latex-content"
          :class="{ 'guide-content': isGuideDual }"
          :data-content-target="rightContentTarget"
          :data-annotation-eligible="rightAnnotationEligible ? 'true' : 'false'"
          :key="rightPaneKey"
          v-html="rightPaneHtml"
        ></div>
        <nav v-if="previousItem || nextItem" class="reader-pagination" aria-label="Chapter navigation">
          <button
            v-if="previousItem"
            type="button"
            class="pagination-button"
            @click="emit('go-previous')"
          >
            <span>上一篇</span>
            <strong>{{ previousItem.title }}</strong>
          </button>
          <span v-else></span>
          <button
            v-if="nextItem"
            type="button"
            class="pagination-button pagination-button-next"
            @click="emit('go-next')"
          >
            <span>下一篇</span>
            <strong>{{ nextItem.title }}</strong>
          </button>
        </nav>
      </div>
    </template>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'

const viewportRef = defineModel('viewportRef')

const props = defineProps({
  currentItem: {
    type: Object,
    default: null
  },
  loading: {
    type: Boolean,
    default: false
  },
  renderedSource: {
    type: String,
    default: ''
  },
  renderedGuide: {
    type: String,
    default: ''
  },
  renderedTarget: {
    type: String,
    default: ''
  },
  guideItem: {
    type: Object,
    default: null
  },
  guideLoading: {
    type: Boolean,
    default: false
  },
  viewMode: {
    type: String,
    required: true
  },
  previousItem: {
    type: Object,
    default: null
  },
  nextItem: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['go-previous', 'go-next', 'scroll-progress'])
const leftPaneRef = ref(null)
const rightPaneRef = ref(null)
const syncScrollLock = ref(false)

const effectiveViewMode = computed(() => {
  if (props.viewMode === 'guide-dual') return 'guide-dual'
  return props.viewMode === 'dual' && props.renderedSource ? 'dual' : 'single'
})

const isGuideDual = computed(() => effectiveViewMode.value === 'guide-dual')
const isSelectedGuideDual = computed(() => (
  isGuideDual.value && ['guide', 'learning'].includes(props.currentItem?.type)
))

const translatedOrSourceHtml = computed(() => {
  return String(props.renderedTarget || '').trim() ? props.renderedTarget : props.renderedSource
})

const leftPaneHtml = computed(() => {
  if (!isGuideDual.value) return props.renderedSource
  return isSelectedGuideDual.value ? props.renderedSource : translatedOrSourceHtml.value
})

const rightPaneHtml = computed(() => {
  if (!isGuideDual.value) return translatedOrSourceHtml.value
  return isSelectedGuideDual.value ? translatedOrSourceHtml.value : props.renderedGuide
})

const guideUnavailable = computed(() => {
  return isGuideDual.value && !String(rightPaneHtml.value || '').trim()
})

const leftAnnotationEligible = computed(() => !isGuideDual.value || !isSelectedGuideDual.value)
const rightAnnotationEligible = computed(() => !isGuideDual.value || isSelectedGuideDual.value)
const leftContentTarget = computed(() => effectiveViewMode.value === 'dual' ? 'raw' : 'translated')
const rightContentTarget = computed(() => 'translated')

const emitScrollProgress = (element) => {
  if (!element) return
  const scrollRange = element.scrollHeight - element.clientHeight
  const progress = scrollRange <= 0 ? 0 : Math.round((element.scrollTop / scrollRange) * 100)
  emit('scroll-progress', Math.max(0, Math.min(100, progress)))
}

const handleViewportScroll = (event) => {
  if (effectiveViewMode.value === 'single') emitScrollProgress(event.currentTarget)
}

const syncPaneScroll = (side, event) => {
  if (syncScrollLock.value || !['dual', 'guide-dual'].includes(effectiveViewMode.value)) return
  const source = event.currentTarget
  const target = side === 'left' ? rightPaneRef.value : leftPaneRef.value
  if (!source || !target) return
  emitScrollProgress(source)

  const sourceRange = source.scrollHeight - source.clientHeight
  const targetRange = target.scrollHeight - target.clientHeight
  if (sourceRange <= 0 || targetRange <= 0) return

  syncScrollLock.value = true
  target.scrollTop = (source.scrollTop / sourceRange) * targetRange
  window.requestAnimationFrame(() => {
    syncScrollLock.value = false
  })
}

const leftPaneKey = computed(() => {
  return isGuideDual.value
    ? `translated-${props.currentItem?.id || 'missing'}`
    : `source-${props.currentItem?.id || 'missing'}`
})

const rightPaneKey = computed(() => {
  return isGuideDual.value
    ? `guide-${props.guideItem?.id || props.currentItem?.id || 'missing'}`
    : `target-${props.currentItem?.id || 'missing'}`
})
</script>

<style scoped>
.content-viewport {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.content-viewport.dual .pane,
.content-viewport.guide-dual .pane {
  flex: 1;
  overflow-y: auto;
}

.content-viewport.single {
  overflow-y: auto;
  justify-content: center;
}

.pane-container.single-layout {
  display: flex;
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
  min-height: 100%;
}

.text-column {
  flex: 0 1 800px;
  padding: 3rem 4rem;
  width: 100%;
  max-width: 800px;
  position: relative;
  margin: 0 auto;
}

.pane {
  padding: 2rem 3rem;
  position: relative;
  border-right: 1px solid #f0f0f0;
}

.pane:last-child {
  border-right: 0;
}

.markdown-body {
  line-height: 1.8;
}

.guide-content {
  font-size: 0.95rem;
}

.pane-state {
  min-height: 12rem;
  display: grid;
  place-items: center;
  border: 1px dashed #ddcfbc;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.58);
  color: #7b6b57;
  font-size: 0.92rem;
  line-height: 1.5;
  padding: 1.5rem;
  text-align: center;
}

.reader-pagination {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 1rem;
  margin-top: 3rem;
  padding-top: 1.25rem;
  border-top: 1px solid #eee4d7;
}

.pagination-button {
  min-width: 0;
  border: 1px solid #e5dacb;
  border-radius: 0.45rem;
  background: #fffaf1;
  color: #352d22;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.24rem;
  padding: 0.75rem 0.9rem;
  text-align: left;
  font: inherit;
  transition: background 140ms ease, border-color 140ms ease, transform 140ms ease;
}

.pagination-button:hover {
  background: #fff4df;
  border-color: #d2b57f;
  transform: translateY(-1px);
}

.pagination-button span {
  color: #7b6b57;
  font-size: 0.78rem;
}

.pagination-button strong {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: 0.94rem;
  line-height: 1.35;
}

.pagination-button-next {
  align-items: flex-end;
  text-align: right;
}

.center-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  color: #999;
}

@media (max-width: 1180px) {
  .text-column {
    padding: 2rem 2.5rem;
  }
}

@media (max-width: 900px) {
  .content-viewport {
    min-height: 0;
  }

  .content-viewport.single {
    overflow: visible;
  }

  .content-viewport.dual,
  .content-viewport.guide-dual {
    flex-direction: column;
  }

  .pane-container.single-layout {
    min-height: auto;
  }

  .text-column,
  .pane {
    max-width: none;
    padding: 1.5rem;
    border-right: 0;
  }

  .pane {
    border-bottom: 1px solid #f0f0f0;
  }

  .pane:last-child {
    border-bottom: 0;
  }

  .reader-pagination {
    grid-template-columns: 1fr;
  }

  .pagination-button-next {
    align-items: flex-start;
    text-align: left;
  }
}
</style>
