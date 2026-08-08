<template>
  <header class="reader-toolbar" ref="toolbarRef">
    <div class="toolbar-left">
      <button
        type="button"
        class="panel-toggle-button"
        :title="sidebarOpen ? '收起目录' : '展开目录'"
        :aria-label="sidebarOpen ? '收起目录' : '展开目录'"
        :aria-pressed="sidebarOpen"
        @click="$emit('toggle-sidebar')"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 5h16v14H4zM9 5v14M12.5 9h4M12.5 12h4M12.5 15h2.5"></path>
        </svg>
      </button>
      <div class="reader-breadcrumbs">
        <span v-if="bookTitle">{{ bookTitle }}</span>
        <h2 v-if="currentTitle">{{ currentTitle }}</h2>
        <h2 v-else-if="bookTitle">选择章节开始阅读</h2>
      </div>
    </div>

    <div class="toolbar-right">
      <div v-if="canEditChapterStatus" class="status-controls" aria-label="Chapter reading status">
        <label class="status-field">
          <span class="status-field-label">阅读进度</span>
          <select
            class="status-select"
            :class="progressClass"
            :value="readingStatus.progress"
            @change="$emit('update-reading-progress', $event.target.value)"
          >
            <option
              v-for="option in progressOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="status-field">
          <span class="status-field-label">理解程度</span>
          <select
            class="status-select"
            :class="difficultyClass"
            :value="readingStatus.difficulty"
            @change="$emit('update-reading-difficulty', $event.target.value)"
          >
            <option
              v-for="option in difficultyOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
        </label>
      </div>

      <div class="toolbar-actions" aria-label="Reader tools">
        <button
          type="button"
          class="icon-tool-btn pane-btn"
          :class="{ active: viewMode === 'dual' }"
          :disabled="!canToggleViewMode"
          :aria-pressed="viewMode === 'dual'"
          title="Translation dual panel"
          aria-label="Show source and translation dual panel"
          @click="$emit('set-view-mode', viewMode === 'dual' ? 'single' : 'dual')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3" y="4" width="7" height="16" rx="1.5"></rect>
            <rect x="14" y="4" width="7" height="16" rx="1.5"></rect>
            <path d="M5.4 8h2.8M5.4 11h2M15.8 8h2.8M15.8 11h2M15.8 14h2.3"></path>
          </svg>
          <span class="tool-label">原文对照</span>
        </button>
        <button
          type="button"
          class="icon-tool-btn pane-btn"
          :class="{ active: viewMode === 'guide-dual' }"
          :disabled="!canToggleViewMode"
          :aria-pressed="viewMode === 'guide-dual'"
          title="Guide dual panel"
          aria-label="Show source and guide dual panel"
          @click="$emit('set-view-mode', viewMode === 'guide-dual' ? 'single' : 'guide-dual')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 6.5l5-2 6 2 5-2v13l-5 2-6-2-5 2z"></path>
            <path d="M9 4.5v13M15 6.5v13"></path>
            <path d="M12 9.2l1.2 2.5 2.6.4-1.9 1.9.5 2.6-2.4-1.3-2.4 1.3.5-2.6-1.9-1.9 2.6-.4z"></path>
          </svg>
          <span class="tool-label">章节导读</span>
        </button>
        <button
          type="button"
          class="icon-tool-btn"
          title="Quiz"
          aria-label="Open quiz"
          @click="$emit('open-quiz')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 19h.01"></path>
            <path d="M9.3 9a2.8 2.8 0 1 1 4.5 2.2c-1 .7-1.8 1.3-1.8 2.8"></path>
            <circle cx="12" cy="12" r="9"></circle>
          </svg>
          <span class="tool-label">Quiz</span>
        </button>
        <button
          type="button"
          class="icon-tool-btn"
          :class="{ active: notesOpen }"
          :title="notesOpen ? 'Hide notes' : 'Show notes'"
          :aria-label="notesOpen ? 'Hide notes panel' : 'Show notes panel'"
          :aria-pressed="notesOpen"
          @click="$emit('toggle-notes')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 4h9l3 3v13H6z"></path>
            <path d="M15 4v4h4M8.5 11h7M8.5 14h7M8.5 17h4"></path>
          </svg>
          <span class="notes-dot" aria-hidden="true"></span>
          <span class="tool-label">笔记</span>
          <span v-if="notesCount" class="tool-count" aria-label="笔记数量">{{ notesCount }}</span>
        </button>
      </div>
    </div>
    <div class="chapter-progress-track" aria-hidden="true">
      <span :style="{ width: `${readingPercent}%` }"></span>
    </div>
  </header>
</template>

<script setup>
import { computed, ref, onMounted, watch, nextTick } from 'vue'
import { renderMath } from '../utils/renderer'
import {
  defaultChapterReadingStatus,
  difficultyOptions,
  progressOptions
} from '../utils/chapterReadingStatus'

const props = defineProps({
  bookTitle: {
    type: String,
    default: ''
  },
  currentTitle: {
    type: String,
    default: ''
  },
  canEditChapterStatus: {
    type: Boolean,
    default: false
  },
  canToggleViewMode: {
    type: Boolean,
    default: true
  },
  readingStatus: {
    type: Object,
    default: defaultChapterReadingStatus
  },
  viewMode: {
    type: String,
    required: true
  },
  sidebarOpen: {
    type: Boolean,
    default: true
  },
  notesOpen: {
    type: Boolean,
    default: true
  },
  notesCount: {
    type: Number,
    default: 0
  },
  readingPercent: {
    type: Number,
    default: 0
  }
})

defineEmits([
  'set-view-mode',
  'open-quiz',
  'toggle-sidebar',
  'toggle-notes',
  'update-reading-progress',
  'update-reading-difficulty'
])

const toolbarRef = ref(null)
const progressClass = computed(() => `status-progress-${props.readingStatus.progress || 'unread'}`)
const difficultyClass = computed(() => `status-difficulty-${props.readingStatus.difficulty || 'unmarked'}`)

const triggerRenderMath = () => {
  nextTick(() => {
    if (toolbarRef.value) {
      renderMath(toolbarRef.value)
    }
  })
}

onMounted(triggerRenderMath)
watch(() => props.bookTitle, triggerRenderMath)
</script>

<style scoped>
.reader-toolbar {
  min-height: 64px;
  padding: 0.7rem 1.4rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1.25rem;
  background: #fffdf9;
}

.toolbar-left {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.toolbar-left h2 {
  font-size: 0.98rem;
  font-weight: 650;
  margin: 0;
  color: #28231d;
  max-width: 420px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.toolbar-right {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.85rem;
  min-width: 0;
}

.status-controls,
.toolbar-actions {
  display: flex;
  align-items: center;
}

.status-controls {
  gap: 0.5rem;
  padding-right: 0.85rem;
  border-right: 1px solid #e8dfd2;
}

.status-field {
  display: inline-flex;
  align-items: center;
  gap: 0.36rem;
  color: #756756;
  font-size: 0.76rem;
  font-weight: 650;
  white-space: nowrap;
}

.status-select {
  min-width: 5.25rem;
  border: 1px solid #d8cec0;
  border-radius: 4px;
  color: #2f2b25;
  cursor: pointer;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 650;
  line-height: 1.2;
  padding: 0.35rem 1.65rem 0.35rem 0.55rem;
  background-color: #fff;
  transition: border-color 140ms ease, background 140ms ease, color 140ms ease;
}

.status-progress-unread {
  background: #f6f2eb;
  border-color: #d6caba;
  color: #635846;
}

.status-progress-reading {
  background: #eef5fb;
  border-color: #a9c5d9;
  color: #24566f;
}

.status-progress-skipped {
  background: #f2f0f0;
  border-color: #c9c1bd;
  color: #6a5650;
}

.status-progress-finished {
  background: #edf6f0;
  border-color: #a8cbb4;
  color: #245d39;
}

.status-difficulty-unmarked {
  background: #f6f2eb;
  border-color: #d6caba;
  color: #635846;
}

.status-difficulty-confused {
  background: #fff7e3;
  border-color: #dfc47e;
  color: #735b13;
}

.status-difficulty-hard {
  background: #f8eeee;
  border-color: #d3aaa8;
  color: #7a3431;
}

.toolbar-actions {
  gap: 0.32rem;
  padding: 0.22rem;
  border: 1px solid #ded4c6;
  border-radius: 6px;
  background: #fbf8f3;
}

.icon-tool-btn {
  width: 2.15rem;
  height: 2.05rem;
  display: inline-grid;
  place-items: center;
  position: relative;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 4px;
  color: #51483c;
  cursor: pointer;
  transition: background 140ms ease, border-color 140ms ease, color 140ms ease;
}

.pane-btn {
  width: 2.35rem;
}

.icon-tool-btn svg {
  width: 1.15rem;
  height: 1.15rem;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}

.icon-tool-btn:hover:not(:disabled) {
  background: #fff;
  border-color: #d9cbb8;
  color: #2e261b;
}

.icon-tool-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.icon-tool-btn.active {
  border-color: #c8b58e;
  background: #fffdf7;
  color: #604815;
}

.notes-dot {
  position: absolute;
  right: 0.38rem;
  top: 0.36rem;
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 999px;
  background: #b9ad9d;
}

.icon-tool-btn.active .notes-dot {
  background: #2f8f60;
  box-shadow: 0 0 0 2px #e6f3eb;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

@media (max-width: 1180px) {
  .reader-toolbar {
    padding: 0 1rem;
  }
}

@media (max-width: 900px) {
  .reader-toolbar {
    min-height: 64px;
    height: auto;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
  }

  .toolbar-left,
  .toolbar-right {
    min-width: 0;
    flex-wrap: wrap;
  }

  .status-controls {
    border-right: 0;
    padding-right: 0;
    flex-wrap: wrap;
  }
}
</style>
