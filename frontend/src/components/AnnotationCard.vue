<template>
  <article class="annotation-card" :class="`annotation-card--${style}`">
    <header class="annotation-header">
      <div class="annotation-heading">
        <span class="annotation-kind">{{ style === 'underline' ? '下划线' : '高亮' }}</span>
        <strong>{{ note.source_title || '阅读标记' }}</strong>
      </div>
      <div class="annotation-actions">
        <time v-if="note.created_at" :datetime="note.created_at">{{ formatDate(note.created_at) }}</time>
        <button
          v-if="note.chapter_id"
          type="button"
          class="source-btn"
          title="在新标签页打开原文"
          aria-label="在新标签页打开原文"
          @click="emit('open-source')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M14 5h5v5M19 5l-8 8M18 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
          </svg>
        </button>
        <button type="button" class="delete-btn" title="删除标记" aria-label="删除标记" @click="emit('delete')">×</button>
      </div>
    </header>
    <blockquote ref="selectedTextRef" class="annotation-text latex-content">
      {{ displayText }}
    </blockquote>
  </article>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { renderMath } from '../utils/renderer'
import { normalizeLegacyAnnotationText } from '../utils/annotationText'

const props = defineProps({
  note: {
    type: Object,
    required: true
  },
  style: {
    type: String,
    default: 'highlight'
  }
})

const emit = defineEmits(['delete', 'open-source'])
const selectedTextRef = ref(null)
const displayText = computed(() => (
  normalizeLegacyAnnotationText(props.note.selected_text) || '未保存标记文本'
))

const formatDate = (date) => new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'short',
  day: 'numeric'
}).format(new Date(date))

const renderSelectedTextMath = () => {
  nextTick(() => {
    if (selectedTextRef.value) renderMath(selectedTextRef.value)
  })
}

watch(displayText, renderSelectedTextMath)
onMounted(renderSelectedTextMath)
</script>

<style scoped>
.annotation-card {
  overflow: hidden;
  border: 1px solid var(--color-line);
  border-left: 3px solid #d8ad2d;
  border-radius: var(--radius-md);
  background: var(--color-surface-raised);
  box-shadow: var(--shadow-sm);
}

.annotation-card--underline {
  border-left-color: var(--color-accent);
}

.annotation-header,
.annotation-heading,
.annotation-actions {
  display: flex;
  align-items: center;
}

.annotation-header {
  justify-content: space-between;
  gap: 1rem;
  padding: 0.8rem 1rem;
  border-bottom: 1px solid var(--color-line);
  background: var(--color-surface-muted);
}

.annotation-heading,
.annotation-actions {
  min-width: 0;
  gap: 0.65rem;
}

.annotation-heading strong {
  overflow: hidden;
  color: var(--color-ink);
  font-size: 0.82rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.annotation-kind {
  flex: 0 0 auto;
  padding: 0.2rem 0.48rem;
  border-radius: 999px;
  color: #735500;
  background: rgba(247, 218, 92, 0.42);
  font-size: 0.68rem;
  font-weight: 700;
}

.annotation-card--underline .annotation-kind {
  color: var(--color-accent-dark);
  background: var(--color-accent-soft);
}

.annotation-actions time {
  color: var(--color-faint);
  font-size: 0.72rem;
}

.source-btn,
.delete-btn {
  border: 0;
  color: var(--color-muted);
  background: transparent;
  cursor: pointer;
}

.source-btn {
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  padding: 0;
}

.source-btn svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}

.source-btn:hover {
  color: var(--color-accent-dark);
}

.delete-btn {
  padding: 0 0.15rem;
  font-size: 1.2rem;
  line-height: 1;
}

.delete-btn:hover {
  color: var(--color-danger);
}

.annotation-text {
  margin: 0;
  padding: 1.1rem 1.2rem 1.2rem;
  color: var(--color-ink);
  font-family: var(--font-display);
  font-size: 1rem;
  line-height: 1.7;
}

@media (max-width: 640px) {
  .annotation-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .annotation-actions {
    width: 100%;
  }

  .annotation-actions time {
    margin-right: auto;
  }
}
</style>
