import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { useLearningCards } from './useLearningCards.js'

const chapter = {
  id: 42,
  readerType: 'chapter',
  title_zh: '21.5 Orientations and Atlases',
  title_en: 'Orientations and Atlases'
}

const {
  activeConversationId,
  askCards,
  createChapterCard,
  createPendingQuizCard,
  createQuizQuestionCard,
  hydrateQuizQuestionCard,
  ensureChapterCard,
  ensureSelectionCard,
  loadAskNotes
} = useLearningCards()

loadAskNotes([], chapter)
assert.equal(askCards.value.length, 0, 'loading an empty chapter should not create a default chat note')
assert.equal(activeConversationId.value, null, 'empty notes should not open a conversation automatically')

const chapterNote = ensureChapterCard(chapter)
assert.equal(chapterNote.scopeLabel, '本章')
assert.equal(chapterNote.questionSummary, 'New chapter note')
assert.equal(chapterNote.sourceTitle, '21.5 Orientations and Atlases')
assert.equal(chapterNote.contextScope, 'chapter', 'chapter notes should use the complete chapter as prompt context')

const firstCreatedChapterNote = createChapterCard(chapter)
const secondCreatedChapterNote = createChapterCard(chapter)
assert.notEqual(
  firstCreatedChapterNote.id,
  secondCreatedChapterNote.id,
  '+ Chapter Note should create independent chapter note cards'
)
assert.equal(
  askCards.value.filter(card => card.type === 'chapter').length,
  3,
  'chapter notes should not be collapsed into a singleton'
)

const selectionNote = ensureSelectionCard(chapter, 'det(∂yʲ / ∂xⁱ) > 0')
assert.equal(selectionNote.scopeLabel, '片段')
assert.equal(selectionNote.questionSummary, 'New selection note')
assert.equal(selectionNote.sourceTitle, '21.5 Orientations and Atlases')
assert.equal(selectionNote.selectedText, 'det(∂yʲ / ∂xⁱ) > 0')
assert.equal(selectionNote.contextScope, 'selection', 'selection-only notes should limit prompt context to the selection')
assert.equal(selectionNote.initialPrompt, '', 'selection context should not be duplicated into the question composer')

const chapterNoteFromSelection = createChapterCard(chapter, { initialPrompt: 'What does this orientation condition mean?' })
assert.equal(chapterNoteFromSelection.initialPrompt, 'What does this orientation condition mean?', 'chapter notes opened from a selection should prefill the composer without narrowing chapter context')

const pendingQuizCard = createPendingQuizCard(chapter, {
  quizMode: 'chapter',
  questionType: 'proof_strategy'
})
assert.equal(pendingQuizCard.loading, true, 'a new Quiz page should start in a visible generating state')
assert.equal(pendingQuizCard.quizGenerating, true)
assert.equal(pendingQuizCard.questionType, 'proof_strategy')
assert.deepEqual(pendingQuizCard.messages, [{ role: 'assistant', content: '' }])

hydrateQuizQuestionCard(pendingQuizCard, {
  id: 8,
  question_type: 'proof_strategy',
  question_type_label: '证明策略',
  question_text: 'Explain the key turn in this proof.'
}, '', { questionContent: 'Explain the key' })
assert.equal(pendingQuizCard.questionId, 8)
assert.equal(pendingQuizCard.messages[0].content, 'Explain the key', 'Quiz question metadata should support progressive question reveal')

const quizCard = createQuizQuestionCard(chapter, {
  id: 9,
  question_type: 'concept_explain',
  question_type_label: '概念讲解',
  quiz_mode: 'book',
  question_text: 'Explain an oriented atlas.',
  answer_guidance: 'Use your own words; no formulas required.',
  expected_points: ['compatible charts'],
  evaluation_rubric: { completed: 'Accurate explanation' }
})
assert.equal(quizCard.questionId, 9)
assert.equal(quizCard.questionType, 'concept_explain')
assert.equal(quizCard.questionTypeLabel, '概念讲解')
assert.equal(quizCard.quizMode, 'book')
assert.equal(quizCard.answerGuidance, 'Use your own words; no formulas required.')
assert.deepEqual(quizCard.expectedPoints, ['compatible charts'])
assert.deepEqual(quizCard.rubric, { completed: 'Accurate explanation' })
assert.equal(quizCard.messages[0].content, 'Explain an oriented atlas.')

const savedQuizPayload = JSON.parse(quizCard.noteContent)
assert.deepEqual(
  savedQuizPayload.quizQuestion,
  {
    questionId: 9,
    questionType: 'concept_explain',
    expectedPoints: ['compatible charts'],
    rubric: { completed: 'Accurate explanation' },
    personalizationContext: '',
    questionText: 'Explain an oriented atlas.',
    quizMode: 'book',
    questionTypeLabel: '概念讲解',
    answerGuidance: 'Use your own words; no formulas required.'
  },
  'structured quiz cards should serialize metadata needed for later attempts'
)
assert.deepEqual(
  savedQuizPayload.messages,
  [{ role: 'assistant', content: 'Explain an oriented atlas.' }],
  'structured quiz card payload should preserve normal serialized messages'
)

loadAskNotes([
  {
    id: 123,
    type: 'quiz_chat',
    selected_text: '',
    note_content: quizCard.noteContent,
    title: quizCard.questionSummary,
    source_type: 'chapter',
    source_id: 'chapter:42',
    source_title: '21.5 Orientations and Atlases',
    created_at: '2026-05-04T00:00:00Z'
  }
], chapter)
const reopenedQuizCard = askCards.value[0]
assert.equal(reopenedQuizCard.type, 'quiz')
assert.equal(reopenedQuizCard.questionId, 9)
assert.equal(reopenedQuizCard.questionType, 'concept_explain')
assert.equal(reopenedQuizCard.quizMode, 'book')
assert.equal(reopenedQuizCard.questionTypeLabel, '概念讲解')
assert.equal(reopenedQuizCard.answerGuidance, 'Use your own words; no formulas required.')
assert.deepEqual(reopenedQuizCard.expectedPoints, ['compatible charts'])
assert.deepEqual(reopenedQuizCard.rubric, { completed: 'Accurate explanation' })
assert.equal(reopenedQuizCard.questionText, 'Explain an oriented atlas.')
assert.deepEqual(reopenedQuizCard.messages, [{ role: 'assistant', content: 'Explain an oriented atlas.' }])

loadAskNotes([
  {
    id: 124,
    type: 'quiz_chat',
    selected_text: '',
    note_content: JSON.stringify([{ role: 'assistant', content: 'Legacy quiz prompt.' }]),
    title: 'Legacy quiz',
    source_type: 'chapter',
    source_id: 'chapter:42',
    source_title: '21.5 Orientations and Atlases'
  }
], chapter)
const legacyQuizCard = askCards.value[0]
assert.equal(legacyQuizCard.type, 'quiz')
assert.equal(legacyQuizCard.questionId, undefined, 'legacy quiz notes without metadata should stay readable')
assert.deepEqual(legacyQuizCard.messages, [{ role: 'assistant', content: 'Legacy quiz prompt.' }])

const useChatSource = readFileSync(new URL('./useChat.js', import.meta.url), 'utf8')
assert.match(
  useChatSource,
  /applyCardQuizMetadata\(card\)/,
  'streamCardChat should recover structured quiz metadata before routing the answer'
)
assert.match(
  useChatSource,
  /\/quiz\/questions\/\$\{card\.questionId\}\/attempts/,
  'streamCardChat should submit reopened structured quiz answers to the attempts endpoint'
)
assert.match(useChatSource, /conversation_history:\s*history/, 'follow-up answers should be evaluated with prior teach-back context')

const guide = {
  id: 'guide:01-reading-path.md',
  readerType: 'guide',
  title_zh: 'Top-down reading path',
  title_en: 'Top-down reading path'
}
loadAskNotes([], guide)
const guideNote = createChapterCard(guide)
assert.equal(guideNote.readerType, 'guide')
assert.equal(guideNote.scopeLabel, 'Guide')
assert.equal(guideNote.sourceTitle, 'Top-down reading path')

console.log('useLearningCards notes behavior ok')
