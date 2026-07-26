<template>
  <aside class="learning-sidebar">
    <header class="sidebar-header">
      <div class="tabs" role="tablist" aria-label="Learning tools">
        <button
          type="button"
          class="tab-button"
          :class="{ active: activeTab === 'ask' }"
          @click="emit('update:activeTab', 'ask')"
        >
          Ask
        </button>
        <button
          type="button"
          class="tab-button"
          :class="{ active: activeTab === 'quiz' }"
          @click="emit('update:activeTab', 'quiz')"
        >
          Quiz
        </button>
      </div>
    </header>

    <section v-if="activeTab === 'ask'" class="sidebar-body">
      <div v-if="askVisibleCards.length" class="card-list">
        <ConversationCard
          v-for="card in askVisibleCards"
          :key="card.id"
          :card="card"
          :active="card.id === activeConversationId"
          @activate="emit('activate-card', $event)"
        />
      </div>
      <div v-else class="empty-state">
        Select text or open a chapter conversation to ask questions.
      </div>
    </section>

    <section v-else class="sidebar-body">
      <div v-if="quizCards.length" class="card-list">
        <QuizCard
          v-for="card in quizCards"
          :key="card.id"
          :card="card"
          :active="activeQuizId === card.id"
          @activate="emit('activate-quiz', $event)"
          @submit="(card, answer) => emit('submit-quiz', card, answer)"
        />
        <ConversationCard
          v-for="card in quizConversationCards"
          :key="`conversation-${card.id}`"
          :card="card"
          :active="activeQuizId === card.id || activeConversationId === card.id"
          @activate="emit('activate-quiz', $event)"
        />
      </div>
      <slot v-else name="quiz">
        <div class="empty-state">
          Quiz cards will appear here.
        </div>
      </slot>
    </section>

    <form v-if="showSidebarInput" class="ask-input" @submit.prevent="sendDraft">
      <label>{{ targetLabel }}</label>
      <textarea
        v-model="draft"
        :placeholder="inputPlaceholder"
        :disabled="inputDisabled"
        @keydown.enter.exact.prevent="sendDraft"
      ></textarea>
      <button type="submit" :disabled="inputDisabled || !draft.trim()">
        {{ activeCard?.loading ? 'Sending...' : 'Send' }}
      </button>
    </form>
  </aside>
</template>

<script setup>
import { computed, ref } from 'vue'
import ConversationCard from './ConversationCard.vue'
import QuizCard from './QuizCard.vue'

const props = defineProps({
  activeTab: {
    type: String,
    required: true
  },
  askCards: {
    type: Array,
    required: true
  },
  quizCards: {
    type: Array,
    required: true
  },
  activeConversationId: {
    type: [String, null],
    default: null
  },
  activeQuizId: {
    type: [String, null],
    default: null
  },
  activeCard: {
    type: [Object, null],
    default: null
  }
})

const emit = defineEmits(['update:activeTab', 'activate-card', 'send', 'activate-quiz', 'submit-quiz'])

const draft = ref('')

const targetLabel = computed(() => {
  return `发送到：${props.activeCard?.title || '当前章节'}`
})

const showSidebarInput = computed(() => {
  return props.activeTab === 'ask' || (props.activeTab === 'quiz' && props.activeCard?.type === 'quiz')
})

const inputPlaceholder = computed(() => {
  if (props.activeTab === 'quiz') return '输入“开始”或“出题”，让 Agent 提出第一道题；也可以继续回答或追问...'
  return 'Ask about this context...'
})

const inputDisabled = computed(() => {
  return !props.activeCard || props.activeCard.loading
})

const askVisibleCards = computed(() => {
  return props.askCards.filter(card => card.type !== 'quiz')
})

const quizConversationCards = computed(() => {
  const liveQuizCards = props.quizCards.filter(card => Array.isArray(card.messages) && card.messages.length > 0)
  const savedQuizCards = props.askCards.filter(card => card.type === 'quiz')
  return [...liveQuizCards, ...savedQuizCards]
})

const sendDraft = () => {
  const prompt = draft.value.trim()
  if (!prompt || inputDisabled.value) return
  emit('send', prompt)
  draft.value = ''
}
</script>

<style scoped>
.learning-sidebar {
  width: 360px;
  flex: 0 0 360px;
  height: 100vh;
  border-left: 1px solid #e5e7eb;
  background: #f8fafc;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  flex-shrink: 0;
  padding: 0.75rem;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}

.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem;
  padding: 0.2rem;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f8fafc;
}

.tab-button {
  height: 2rem;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}

.tab-button.active {
  background: #fff;
  color: #1d4ed8;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.sidebar-body {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem;
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.empty-state {
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 1rem;
  color: #64748b;
  background: #fff;
  font-size: 0.85rem;
  line-height: 1.5;
}

.ask-input {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  border-top: 1px solid #e5e7eb;
  background: #fff;
}

.ask-input label {
  color: #475569;
  font-size: 0.75rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ask-input textarea {
  width: 100%;
  min-height: 4.75rem;
  max-height: 9rem;
  resize: vertical;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  padding: 0.55rem 0.65rem;
  color: #111827;
  font: inherit;
  font-size: 0.88rem;
  line-height: 1.45;
}

.ask-input textarea:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}

.ask-input textarea:disabled {
  cursor: not-allowed;
  background: #f8fafc;
  color: #94a3b8;
}

.ask-input button {
  align-self: flex-end;
  min-width: 5rem;
  height: 2rem;
  border: 1px solid #2563eb;
  border-radius: 7px;
  background: #2563eb;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.ask-input button:disabled {
  cursor: not-allowed;
  border-color: #cbd5e1;
  background: #e2e8f0;
  color: #94a3b8;
}

@media (max-width: 1180px) {
  .learning-sidebar {
    width: 320px;
    flex-basis: 320px;
  }
}

@media (max-width: 900px) {
  .learning-sidebar {
    width: 100%;
    flex: 0 0 auto;
    height: 42vh;
    min-height: 320px;
    border-left: 0;
    border-top: 1px solid #e5e7eb;
  }
}
</style>
