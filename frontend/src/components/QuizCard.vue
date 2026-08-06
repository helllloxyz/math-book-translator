<template>
  <article
    class="quiz-card"
    :class="{ active, loading: card.loading }"
    @click="emit('activate', card)"
  >
    <header class="card-header">
      <div class="title-group">
        <strong>{{ card.title }}</strong>
        <p>{{ statusLabel }}</p>
      </div>
      <span class="state-pill">{{ card.masteryState }}</span>
    </header>

    <section ref="promptRef" class="quiz-section latex-content" v-html="renderMarkdown(card.prompt)"></section>

    <section v-if="card.answer" class="response-block">
      <h4>Latest answer</h4>
      <div ref="answerRef" class="latex-content" v-html="renderMarkdown(card.answer)"></div>
    </section>

    <section v-if="card.evaluation" class="response-block evaluation-block">
      <h4>Evaluation</h4>
      <div ref="evaluationRef" class="latex-content" v-html="renderMarkdown(card.evaluation)"></div>
    </section>

    <form class="answer-form" @submit.prevent.stop="submitAnswer">
      <textarea
        v-model="draft"
        :placeholder="answerPlaceholder"
        :disabled="card.loading"
        @click.stop
      ></textarea>
      <button type="submit" :disabled="card.loading || !draft.trim()">
        {{ card.loading ? 'Evaluating...' : 'Submit' }}
      </button>
    </form>
  </article>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { renderMarkdown, renderMath as renderKatexMath } from '../utils/renderer'

const props = defineProps({
  card: {
    type: Object,
    required: true
  },
  active: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['activate', 'submit'])

const draft = ref('')
const promptRef = ref(null)
const answerRef = ref(null)
const evaluationRef = ref(null)

const statusLabel = computed(() => {
  if (props.card.loading) return 'Evaluating answer...'
  if (props.card.masteryState === 'dialogue') return 'Start or continue below'
  if (props.card.evaluation) return 'Review available'
  if (props.card.answer) return 'Answer submitted'
  return 'Not attempted'
})

const answerPlaceholder = computed(() => {
  if (props.card.masteryState === 'dialogue') return '输入“开始”或“出题”，让 Agent 先出一道题...'
  return 'Write your answer...'
})

const renderMath = () => {
  nextTick(() => {
    ;[promptRef.value, answerRef.value, evaluationRef.value]
      .filter(Boolean)
      .forEach(element => renderKatexMath(element))
  })
}

const submitAnswer = () => {
  const answer = draft.value.trim()
  if (!answer || props.card.loading) return
  draft.value = ''
  emit('submit', props.card, answer)
}

watch(() => props.card.prompt, renderMath)
watch(() => props.card.answer, renderMath)
watch(() => props.card.evaluation, renderMath)

onMounted(renderMath)
</script>

<style scoped>
.quiz-card {
  box-sizing: border-box;
  width: 100%;
  border: 1px solid #e5e7eb;
  border-left: 3px solid transparent;
  border-radius: 8px;
  background: #fff;
  padding: 0.75rem;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.quiz-card *,
.quiz-card *::before,
.quiz-card *::after {
  box-sizing: border-box;
}

.quiz-card:hover {
  border-color: #cbd5e1;
}

.quiz-card.active {
  border-color: #16a34a;
  border-left-color: #16a34a;
  background: #f7fdf9;
}

.quiz-card.loading {
  cursor: progress;
}

.card-header {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: flex-start;
}

.title-group {
  min-width: 0;
}

.title-group strong {
  display: block;
  color: #111827;
  font-size: 0.9rem;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-group p {
  margin: 0.2rem 0 0;
  color: #6b7280;
  font-size: 0.75rem;
  line-height: 1.3;
}

.state-pill {
  flex-shrink: 0;
  border: 1px solid #bbf7d0;
  border-radius: 999px;
  color: #15803d;
  background: #f0fdf4;
  font-size: 0.7rem;
  font-weight: 600;
  line-height: 1;
  padding: 0.25rem 0.45rem;
}

.quiz-section {
  margin-top: 0.65rem;
  color: #1f2937;
  font-size: 0.84rem;
  line-height: 1.55;
}

.response-block {
  margin-top: 0.65rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f8fafc;
  padding: 0.55rem 0.6rem;
  color: #334155;
  font-size: 0.82rem;
  line-height: 1.5;
}

.evaluation-block {
  border-color: #bbf7d0;
  background: #f7fdf9;
}

.response-block h4 {
  margin: 0 0 0.35rem;
  color: #475569;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.quiz-section :deep(p),
.response-block :deep(p) {
  margin: 0 0 0.55rem;
}

.quiz-section :deep(p:last-child),
.response-block :deep(p:last-child) {
  margin-bottom: 0;
}

.answer-form {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.65rem;
}

.answer-form textarea {
  width: 100%;
  min-height: 4.75rem;
  max-height: 9rem;
  resize: vertical;
  border: 1px solid #cbd5e1;
  border-radius: 7px;
  padding: 0.55rem 0.65rem;
  color: #111827;
  font: inherit;
  font-size: 0.84rem;
  line-height: 1.45;
}

.answer-form textarea:focus {
  outline: none;
  border-color: #16a34a;
  box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.12);
}

.answer-form textarea:disabled {
  cursor: not-allowed;
  background: #f8fafc;
  color: #94a3b8;
}

.answer-form button {
  align-self: flex-end;
  min-width: 5rem;
  height: 2rem;
  border: 1px solid #16a34a;
  border-radius: 7px;
  background: #16a34a;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.answer-form button:disabled {
  cursor: not-allowed;
  border-color: #cbd5e1;
  background: #e2e8f0;
  color: #94a3b8;
}
</style>
