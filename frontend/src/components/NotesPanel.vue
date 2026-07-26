<template>
  <aside class="notes-panel" aria-label="Notes">
    <header class="notes-header">
      <div class="title-group">
        <p v-if="currentTitle" class="chapter-title">{{ currentTitle }}</p>
        <h2>Notes</h2>
      </div>
      <button type="button" class="chapter-note-button" @click="emit('create-chapter-note')">
        +
      </button>
    </header>

    <section v-if="noteCards.length" class="notes-list" aria-label="Saved notes">
      <button
        v-for="note in noteCards"
        :key="note.id"
        type="button"
        class="note-index-card"
        :class="[bookmarkClass(note), { active: note.id === activeId }]"
        @click="emit('activate-note', note)"
      >
        <span class="note-symbol" aria-hidden="true">{{ noteTypeSymbol(note) }}</span>
        <span class="note-copy">
          <strong>{{ note.questionSummary || note.title || 'Untitled note' }}</strong>
        </span>
      </button>
    </section>

    <section v-else class="empty-state">
      <h3>还没有 Notes</h3>
      <p>选中文本或创建章节 Note，把问题和上下文留在这里。</p>
    </section>
  </aside>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  notes: {
    type: Array,
    default: () => []
  },
  activeId: {
    type: String,
    default: null
  },
  currentTitle: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['create-chapter-note', 'activate-note'])

const noteCards = computed(() => props.notes.filter((note) => note && note.type !== 'quiz'))

const bookmarkClass = (note) => {
  if (note?.type === 'selection') return 'bookmark-key-step'
  if (note?.type === 'chapter') return 'bookmark-theorem'
  return 'bookmark-note'
}

const noteTypeSymbol = (note) => {
  if (note?.type === 'selection') return '¶'
  if (note?.type === 'chapter') return '§'
  return '•'
}
</script>

<style scoped>
.notes-panel {
  box-sizing: border-box;
  width: min(300px, 100%);
  height: 100%;
  min-height: 0;
  border-left: 0.5px solid #d9d9d9;
  background: #ffffff;
  color: #20252b;
  display: flex;
  flex-direction: column;
  --bookmark-purple: #7f77dd;
  --bookmark-purple-50: #eeedfe;
  --bookmark-purple-200: #afa9ec;
  --bookmark-purple-900: #26215c;
  --bookmark-teal: #1d9e75;
  --bookmark-teal-50: #e1f5ee;
  --bookmark-teal-200: #9fe1cb;
  --bookmark-teal-900: #04342c;
  --bookmark-border: #d9d9d9;
  --bookmark-muted: #8a929c;
}

.notes-panel *,
.notes-panel *::before,
.notes-panel *::after {
  box-sizing: border-box;
}

.notes-header {
  flex-shrink: 0;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 10px 12px;
  border-bottom: 0.5px solid var(--bookmark-border);
  background: #f6f7f8;
}

.title-group {
  min-width: 0;
}

.chapter-title {
  margin: 0 0 0.18rem;
  color: var(--bookmark-muted);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.06em;
  line-height: 1.3;
  text-transform: uppercase;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 9.5rem;
}

.notes-header h2 {
  margin: 0;
  color: #20252b;
  font-size: 13px;
  line-height: 1.2;
  font-weight: 500;
  letter-spacing: 0;
}

.chapter-note-button {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border: 0.5px solid var(--bookmark-border);
  border-radius: 6px;
  background: #ffffff;
  color: #5f6873;
  cursor: pointer;
  font: inherit;
  font-size: 16px;
  font-weight: 400;
  line-height: 1;
  padding: 0;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.chapter-note-button:hover {
  border-color: var(--bookmark-muted);
  background: #ffffff;
  color: #20252b;
}

.notes-list {
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 10px;
}

.note-index-card {
  position: relative;
  width: 100%;
  overflow: hidden;
  border: 0.5px solid var(--bookmark-border);
  border-radius: 8px;
  background: var(--bookmark-active-bg);
  color: inherit;
  cursor: pointer;
  display: flex;
  flex-direction: row;
  align-items: flex-start;
  gap: 9px;
  padding: 10px;
  text-align: left;
  transition: background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}

.note-index-card:hover {
  border-color: var(--bookmark-active-border);
}

.note-index-card.active {
  border-color: var(--bookmark-accent);
  background: var(--bookmark-accent);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.28), 0 8px 18px rgba(31, 41, 55, 0.14);
}

.note-index-card.active strong {
  color: #ffffff;
  font-weight: 500;
}

.note-index-card.active .note-symbol {
  background: rgba(255, 255, 255, 0.18);
  color: #ffffff;
}

.note-symbol {
  flex: 0 0 18px;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #ffffff;
  color: var(--bookmark-label);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 12px;
  line-height: 1;
  margin-top: 1px;
}

.note-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.note-index-card strong {
  width: 100%;
  color: var(--bookmark-ink);
  display: block;
  font-size: 14px;
  font-weight: 400;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.bookmark-theorem {
  --bookmark-accent: var(--bookmark-purple);
  --bookmark-label: #3c3489;
  --bookmark-ink: var(--bookmark-purple-900);
  --bookmark-active-bg: var(--bookmark-purple-50);
  --bookmark-active-border: var(--bookmark-purple-200);
}

.bookmark-key-step {
  --bookmark-accent: var(--bookmark-teal);
  --bookmark-label: #085041;
  --bookmark-ink: var(--bookmark-teal-900);
  --bookmark-active-bg: var(--bookmark-teal-50);
  --bookmark-active-border: var(--bookmark-teal-200);
}

.bookmark-note {
  --bookmark-accent: #3f4751;
  --bookmark-label: #5f6873;
  --bookmark-ink: #3f4751;
  --bookmark-active-bg: #f6f7f8;
  --bookmark-active-border: #b9bec5;
}

.empty-state {
  margin: 1rem 0.8rem;
  border: 0.5px dashed var(--bookmark-border);
  border-radius: 8px;
  background: #f6f7f8;
  padding: 1rem 0.85rem;
}

.empty-state h3 {
  margin: 0;
  color: #20252b;
  font-size: 0.95rem;
  line-height: 1.3;
}

.empty-state p {
  margin: 0.45rem 0 0;
  color: #5f6873;
  font-size: 0.78rem;
  line-height: 1.5;
}
</style>
