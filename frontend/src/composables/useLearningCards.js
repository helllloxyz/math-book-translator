import { computed, ref } from 'vue'
import { deserializeMessages, serializeMessages } from '../utils/chatMessages.js'

const QUIZ_METADATA_KEY = 'quizQuestion'

const parseSerializedPayload = (rawValue) => {
    if (typeof rawValue !== 'string') return {}
    const content = rawValue.trim()
    if (!content || !content.startsWith('{')) return {}
    try {
        const parsed = JSON.parse(content)
        return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
    } catch (_error) {
        return {}
    }
}

const normalizeQuizMetadata = (metadata = {}) => {
    const questionId = metadata.questionId ?? metadata.question_id ?? null
    return {
        questionId,
        questionType: metadata.questionType || metadata.question_type || 'concept_explain',
        expectedPoints: Array.isArray(metadata.expectedPoints)
            ? metadata.expectedPoints
            : Array.isArray(metadata.expected_points)
                ? metadata.expected_points
                : [],
        rubric: metadata.rubric || metadata.evaluation_rubric || {},
        personalizationContext: metadata.personalizationContext || metadata.personalization_context || '',
        questionText: metadata.questionText || metadata.question_text || '',
        quizMode: metadata.quizMode || metadata.quiz_mode || 'chapter',
        questionTypeLabel: metadata.questionTypeLabel || metadata.question_type_label || '',
        answerGuidance: metadata.answerGuidance || metadata.answer_guidance || ''
    }
}

const extractQuizMetadata = (rawValue) => {
    const payload = parseSerializedPayload(rawValue)
    const metadata = payload[QUIZ_METADATA_KEY] || payload.quiz_question || payload.quiz || null
    return metadata && typeof metadata === 'object' ? normalizeQuizMetadata(metadata) : null
}

const serializeCardMessages = (messages, quizMetadata = null) => {
    if (!quizMetadata?.questionId) return serializeMessages(messages)
    return JSON.stringify({
        messages: JSON.parse(serializeMessages(messages)),
        [QUIZ_METADATA_KEY]: {
            questionId: quizMetadata.questionId,
            questionType: quizMetadata.questionType || 'concept_explain',
            expectedPoints: Array.isArray(quizMetadata.expectedPoints) ? quizMetadata.expectedPoints : [],
            rubric: quizMetadata.rubric || {},
            personalizationContext: quizMetadata.personalizationContext || '',
            questionText: quizMetadata.questionText || '',
            quizMode: quizMetadata.quizMode || 'chapter',
            questionTypeLabel: quizMetadata.questionTypeLabel || '',
            answerGuidance: quizMetadata.answerGuidance || ''
        }
    })
}

export function useLearningCards() {
    const activeTab = ref('ask')
    const activeConversationId = ref(null)
    const askCards = ref([])
    const quizCards = ref([])
    let tempCardCounter = 0

    const activeAskCard = computed(() => {
        return askCards.value.find(card => card.id === activeConversationId.value) || null
    })

    const askCardType = (note) => {
        if (note.type === 'chapter_chat') return 'chapter'
        if (note.type === 'quiz_chat') return 'quiz'
        if (note.type === 'custom_note') return 'custom'
        return 'selection'
    }

    const subjectTitle = (chapter) => chapter.title_zh || chapter.title_en
    const subjectPrefix = (chapter) => chapter.readerType === 'chapter' || !chapter.readerType ? '章节' : '内容'
    const cardScopeLabel = (type, readerType = 'chapter') => {
        if (readerType === 'guide') return 'Guide'
        if (type === 'selection') return '片段'
        if (type === 'chapter') return '本章'
        if (type === 'quiz') return 'Quiz'
        return 'Note'
    }

    const askCardTitle = (note, chapter) => {
        const prefix = subjectPrefix(chapter)
        if (note.type === 'quiz_chat') return note.title || `Quiz：${subjectTitle(chapter)}`
        if (note.title) return note.title
        if (note.type === 'chapter_chat') return `${prefix}：${subjectTitle(chapter)}`
        if (note.type === 'custom_note') return note.selected_text ? `笔记：${note.selected_text}` : '笔记'
        return `选中：${note.selected_text}`
    }

    const toAskCard = (note, chapter) => {
        const messages = deserializeMessages(note.note_content || '')
        const quizMetadata = note.type === 'quiz_chat' ? extractQuizMetadata(note.note_content || '') : null
        const type = askCardType(note)
        const sourceTitle = subjectTitle(chapter) || 'Untitled chapter'
        const fallbackTitle = type === 'selection'
            ? 'New selection note'
            : type === 'chapter'
                ? 'New chapter note'
                : type === 'quiz'
                    ? `Quiz：${sourceTitle}`
                    : 'New note'
        const questionSummary = note.title || fallbackTitle

        const card = {
            id: note.id ? `note:${note.id}` : (note.tempId || `${note.type}:${chapter.id}:${note.selected_text || 'chapter'}`),
            noteId: note.id || null,
            noteType: note.type,
            type,
            readerType: chapter.readerType || 'chapter',
            title: askCardTitle(note, chapter),
            questionSummary,
            scopeLabel: cardScopeLabel(type, chapter.readerType || 'chapter'),
            bookId: chapter.bookId || chapter.book_id || '',
            chapterId: chapter.chapterId || chapter.id,
            sourceType: note.source_type || chapter.sourceType || chapter.source_type || '',
            sourceId: note.source_id || chapter.sourceId || chapter.source_id || '',
            sourceTitle: note.source_title || sourceTitle,
            selectedText: note.selected_text || '',
            contextScope: note.contextScope || note.context_scope || (type === 'selection' ? 'selection' : 'chapter'),
            initialPrompt: note.initialPrompt || note.initial_prompt || '',
            messages,
            noteContent: serializeCardMessages(messages, quizMetadata),
            loading: false,
            createdAt: note.created_at || null
        }
        if (quizMetadata?.questionId) {
            card.questionId = quizMetadata.questionId
            card.questionType = quizMetadata.questionType
            card.expectedPoints = quizMetadata.expectedPoints
            card.rubric = quizMetadata.rubric
            card.personalizationContext = quizMetadata.personalizationContext
            card.questionText = quizMetadata.questionText || messages.find(message => message.role === 'assistant')?.content || ''
            card.quizMode = quizMetadata.quizMode
            card.questionTypeLabel = quizMetadata.questionTypeLabel
            card.answerGuidance = quizMetadata.answerGuidance
        }
        return card
    }

    const ensureChapterCard = (chapter) => {
        const existing = askCards.value.find(card => (
            card.type === 'chapter' &&
            card.sourceId === (chapter.sourceId || chapter.source_id || '')
        ))
        if (existing) return existing
        return createChapterCard(chapter)
    }

    const createChapterCard = (chapter, options = {}) => {
        const card = toAskCard({
            id: null,
            tempId: `chapter_chat:${chapter.id}:temp:${++tempCardCounter}`,
            type: 'chapter_chat',
            selected_text: '',
            note_content: '',
            title: 'New chapter note',
            contextScope: 'chapter',
            initialPrompt: options.initialPrompt || '',
            source_type: chapter.sourceType || chapter.source_type,
            source_id: chapter.sourceId || chapter.source_id,
            source_title: subjectTitle(chapter)
        }, chapter)
        askCards.value.unshift(card)
        return card
    }

    const ensureQuizCard = (chapter) => {
        const existing = askCards.value.find(card => (
            card.type === 'quiz' &&
            card.sourceId === (chapter.sourceId || chapter.source_id || '')
        ))
        if (existing) return existing
        const card = toAskCard({
            id: null,
            type: 'quiz_chat',
            selected_text: '',
            note_content: '',
            title: `Quiz：${subjectTitle(chapter)}`,
            source_type: chapter.sourceType || chapter.source_type,
            source_id: chapter.sourceId || chapter.source_id,
            source_title: subjectTitle(chapter)
        }, chapter)
        askCards.value.unshift(card)
        return card
    }

    const hydrateQuizQuestionCard = (card, question, personalizationContext = '', options = {}) => {
        const questionText = question?.question_text || '请回答这道 Quiz。'
        const visibleQuestion = options.questionContent ?? questionText
        const questionType = question?.question_type || card?.questionType || 'concept_explain'
        const questionTypeLabel = question?.question_type_label || card?.questionTypeLabel || ''
        const quizMetadata = {
            questionId: question?.id || null,
            questionType,
            expectedPoints: question?.expected_points || [],
            rubric: question?.evaluation_rubric || {},
            personalizationContext: personalizationContext || '',
            questionText,
            quizMode: question?.quiz_mode || card?.quizMode || 'chapter',
            questionTypeLabel,
            answerGuidance: question?.answer_guidance || ''
        }

        card.questionId = quizMetadata.questionId
        card.questionType = quizMetadata.questionType
        card.expectedPoints = quizMetadata.expectedPoints
        card.rubric = quizMetadata.rubric
        card.personalizationContext = quizMetadata.personalizationContext
        card.questionText = quizMetadata.questionText
        card.quizMode = quizMetadata.quizMode
        card.questionTypeLabel = quizMetadata.questionTypeLabel
        card.answerGuidance = quizMetadata.answerGuidance
        card.questionSummary = options.questionSummary
            || `${questionTypeLabel || questionType}：${questionText.replace(/\s+/g, ' ').slice(0, 60)}`
        card.messages = [{ role: 'assistant', content: visibleQuestion }]
        card.noteContent = serializeCardMessages(card.messages, card)
        return card
    }

    const createPendingQuizCard = (chapter, options = {}) => {
        const sourceTitle = subjectTitle(chapter)
        const card = toAskCard({
            id: null,
            tempId: `quiz_pending:${chapter.id}:temp:${++tempCardCounter}`,
            type: 'quiz_chat',
            selected_text: '',
            note_content: '',
            title: `Quiz：${sourceTitle}`,
            source_type: chapter.sourceType || chapter.source_type,
            source_id: chapter.sourceId || chapter.source_id,
            source_title: sourceTitle
        }, chapter)
        card.quizMode = options.quizMode || 'chapter'
        card.questionType = options.questionType || ''
        card.personalizationContext = options.personalizationContext || ''
        card.questionSummary = '正在准备一组新题…'
        card.quizCandidates = []
        card.quizQuestionHistory = []
        card.messages = [{ role: 'assistant', content: '' }]
        card.loading = true
        card.quizGenerating = true
        card.quizGenerationError = ''
        askCards.value.unshift(card)
        return card
    }

    const createQuizQuestionCard = (chapter, question, personalizationContext = '') => {
        const sourceTitle = subjectTitle(chapter)
        const card = toAskCard({
            id: null,
            tempId: `quiz_question:${chapter.id}:${question?.id || ++tempCardCounter}`,
            type: 'quiz_chat',
            selected_text: '',
            note_content: '',
            title: `Quiz：${sourceTitle}`,
            source_type: chapter.sourceType || chapter.source_type,
            source_id: chapter.sourceId || chapter.source_id,
            source_title: sourceTitle
        }, chapter)
        hydrateQuizQuestionCard(card, question, personalizationContext)
        askCards.value.unshift(card)
        return card
    }

    const ensureSelectionCard = (chapter, selectedText, options = {}) => {
        const normalizedText = selectedText.trim()
        const existing = askCards.value.find(card => (
            card.type === 'selection' &&
            card.sourceId === (chapter.sourceId || chapter.source_id || '') &&
            card.selectedText === normalizedText
        ))
        if (existing) {
            if (!existing.messages.length && options.initialPrompt) {
                existing.initialPrompt = options.initialPrompt
            }
            return existing
        }
        const card = toAskCard({
            id: null,
            type: 'selection_chat',
            selected_text: normalizedText,
            note_content: '',
            title: 'New selection note',
            contextScope: 'selection',
            initialPrompt: options.initialPrompt || '',
            source_type: chapter.sourceType || chapter.source_type,
            source_id: chapter.sourceId || chapter.source_id,
            source_title: subjectTitle(chapter)
        }, chapter)
        askCards.value.unshift(card)
        return card
    }

    const activateAskCard = (card) => {
        activeTab.value = card.type === 'quiz' ? 'quiz' : 'ask'
        activeConversationId.value = card.id
    }

    const loadAskNotes = (notes, chapter) => {
        askCards.value = notes
            .filter(note => note.type === 'chapter_chat' || note.type === 'selection_chat' || note.type === 'custom_note' || note.type === 'quiz_chat')
            .map(note => toAskCard(note, chapter))
        activeConversationId.value = null
    }

    const loadQuizCards = (chapter) => {
        quizCards.value = [
            {
                id: `quiz:${chapter.id}:dialogue`,
                chapterId: chapter.id,
                type: 'quiz',
                title: 'Quiz 对话',
                prompt: '在下方输入“开始”或“出题”，让 Agent 基于本章 summary/concepts 提一个概念理解题。你回答后，它会继续点评、追问或给建议。',
                answer: '',
                evaluation: '',
                masteryState: 'dialogue',
                messages: [],
                noteContent: serializeMessages([]),
                loading: false
            }
        ]
    }

    return {
        activeTab,
        activeConversationId,
        askCards,
        quizCards,
        activeAskCard,
        createChapterCard,
        ensureChapterCard,
        ensureQuizCard,
        createPendingQuizCard,
        createQuizQuestionCard,
        hydrateQuizQuestionCard,
        ensureSelectionCard,
        activateAskCard,
        loadAskNotes,
        loadQuizCards
    }
}
