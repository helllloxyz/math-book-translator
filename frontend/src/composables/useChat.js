import { ref } from 'vue'
import { apiClient, buildApiUrl } from '../api/client'
import { deserializeMessages, serializeMessages } from '../utils/renderer'
import { appendWithTypewriter } from '../utils/typewriterStream'

const QUIZ_METADATA_KEY = 'quizQuestion'

export function useChat() {
    const chatLoading = ref(false)

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
            questionText: metadata.questionText || metadata.question_text || ''
        }
    }

    const extractQuizMetadata = (rawValue) => {
        const payload = parseSerializedPayload(rawValue)
        const metadata = payload[QUIZ_METADATA_KEY] || payload.quiz_question || payload.quiz || null
        return metadata && typeof metadata === 'object' ? normalizeQuizMetadata(metadata) : null
    }

    const readCardQuizMetadata = (card) => {
        const serializedMetadata = extractQuizMetadata(card.noteContent || '')
        const questionId = card.questionId ?? serializedMetadata?.questionId ?? null
        if (questionId == null) return null
        return {
            questionId,
            questionType: card.questionType || serializedMetadata?.questionType || 'concept_explain',
            expectedPoints: Array.isArray(card.expectedPoints)
                ? card.expectedPoints
                : serializedMetadata?.expectedPoints || [],
            rubric: card.rubric || serializedMetadata?.rubric || {},
            personalizationContext: card.personalizationContext || serializedMetadata?.personalizationContext || '',
            questionText: card.questionText || serializedMetadata?.questionText || ''
        }
    }

    const applyCardQuizMetadata = (card) => {
        const metadata = readCardQuizMetadata(card)
        if (!metadata) return null
        card.questionId = metadata.questionId
        card.questionType = metadata.questionType
        card.expectedPoints = metadata.expectedPoints
        card.rubric = metadata.rubric
        card.personalizationContext = metadata.personalizationContext
        card.questionText = metadata.questionText
        return metadata
    }

    const serializeCardMessages = (card) => {
        const serializedMessages = serializeMessages(card.messages)
        const quizMetadata = card.type === 'quiz' ? readCardQuizMetadata(card) : null
        if (!quizMetadata) return serializedMessages
        return JSON.stringify({
            messages: JSON.parse(serializedMessages),
            [QUIZ_METADATA_KEY]: quizMetadata
        })
    }

    const appendResponseStylePrompt = (content, stylePrompt = '') => {
        const prompt = String(stylePrompt || '').trim()
        if (!prompt) return content
        return `${content}\n\n${prompt}`
    }

    const buildHistory = (messages, requestOptions = {}) => {
        const lastUserIndex = messages.reduce((lastIndex, message, index) => (
            message.role === 'user' ? index : lastIndex
        ), -1)

        return messages.map((message, index) => {
            return {
                role: message.role,
                content: index === lastUserIndex
                    ? appendResponseStylePrompt(message.content, requestOptions.responseStylePrompt)
                    : message.content
            }
        })
    }

    const normalizeMessages = (rawMessages) => {
        return deserializeMessages(rawMessages)
    }

    const ensureCardMessages = (card) => {
        applyCardQuizMetadata(card)
        const parsedMessages = normalizeMessages(Array.isArray(card.messages) ? card.messages : (card.noteContent || ''))
        card.messages = parsedMessages
        card.noteContent = serializeCardMessages(card)
        return card.messages
    }

    const ensureNoteMessages = (note) => {
        const parsedMessages = normalizeMessages(Array.isArray(note.messages) ? note.messages : (note.note_content || ''))
        note.messages = parsedMessages
        note.note_content = serializeMessages(parsedMessages)
        return note.messages
    }

    const syncCardMessages = (card) => {
        card.noteContent = serializeCardMessages(card)
    }

    const cardNoteType = (card) => {
        if (card.type === 'quiz') return 'quiz_chat'
        if (card.type === 'chapter') return 'chapter_chat'
        return 'selection_chat'
    }

    const provisionalTitle = (prompt) => {
        const normalized = prompt.replace(/\s+/g, ' ').trim()
        if (normalized.length <= 28) return normalized
        return `${normalized.slice(0, 28)}...`
    }

    const syncNoteMessages = (note) => {
        note.note_content = serializeMessages(note.messages)
    }

    const appendAssistantContent = async (messages, assistantIndex, chunk, afterAppend) => {
        await appendWithTypewriter(chunk, (visibleChunk) => {
            const currentAssistant = messages[assistantIndex] || { role: 'assistant', content: '' }
            messages[assistantIndex] = {
                ...currentAssistant,
                content: `${currentAssistant.content || ''}${visibleChunk}`
            }
            afterAppend?.()
        })
    }

    const formatQuizAttemptFeedback = (result) => {
        const statusLabels = {
            completed: '完成',
            partial: '部分正确',
            wrong: '需要重做'
        }
        const missing = Array.isArray(result?.missing_points) && result.missing_points.length
            ? `\n\n**缺失要点**\n${result.missing_points.map(point => `- ${point}`).join('\n')}`
            : ''
        const followup = result?.followup_text ? `\n\n**追问**\n${result.followup_text}` : ''
        return [
            `**评估：${statusLabels[result?.evaluation_status] || result?.evaluation_status || '未知'}**`,
            result?.feedback_text || '已记录本次 Quiz 答题。',
            missing,
            followup
        ].filter(Boolean).join('\n\n')
    }

    const streamCardChat = async (card, userPrompt, contextText, options = {}) => {
        if (!userPrompt.trim() || card.loading) return

        const messages = ensureCardMessages(card)
        messages.push({ role: 'user', content: userPrompt })
        syncCardMessages(card)
        const shouldCreateNote = !card.noteId && card.bookId && card.sourceType && card.sourceId
        const firstMessageNoteContent = card.noteContent
        const history = buildHistory(messages, {
            responseStylePrompt: options.responseStylePrompt
        })
        card.loading = true
        const assistantIndex = messages.push({ role: 'assistant', content: '' }) - 1
        syncCardMessages(card)
        options.onUpdate?.(card)

        if (shouldCreateNote) {
            const fallbackTitle = provisionalTitle(userPrompt)
            const noteTitle = card.type === 'quiz' && card.questionSummary
                ? card.questionSummary
                : fallbackTitle
            card.title = noteTitle
            card.questionSummary = noteTitle
            try {
                const createRes = await apiClient.post('/notes', {
                    book_id: Number(card.bookId),
                    chapter_id: Number.isFinite(Number(card.chapterId)) ? Number(card.chapterId) : null,
                    source_type: card.sourceType,
                    source_id: card.sourceId,
                    source_title: card.sourceTitle || '',
                    selected_text: card.selectedText || '',
                    note_content: firstMessageNoteContent,
                    title: noteTitle,
                    type: cardNoteType(card),
                    start_index: 0
                })
                card.noteId = createRes.data.id

                if (card.type !== 'quiz') {
                    apiClient.post('/generate-title', {
                        context: contextText || card.selectedText || '',
                        prompt: userPrompt
                    }).then(titleRes => {
                        const generatedTitle = titleRes.data.title
                        if (!generatedTitle) return
                        card.title = generatedTitle
                        card.questionSummary = generatedTitle
                        apiClient.put(`/notes/${card.noteId}`, { title: generatedTitle })
                        options.onUpdate?.(card)
                    }).catch(error => {
                        console.error('Failed to generate card title:', error)
                    })
                }
            } catch (error) {
                console.error('Failed to create card note:', error)
            }
        }

        try {
            const quizMetadata = card.type === 'quiz' ? applyCardQuizMetadata(card) : null
            if (card.type === 'quiz' && card.questionId && quizMetadata?.questionId != null) {
                const response = await apiClient.post(`/quiz/questions/${card.questionId}/attempts`, {
                    answer_text: userPrompt
                })
                messages[assistantIndex] = {
                    role: 'assistant',
                    content: formatQuizAttemptFeedback(response.data)
                }
                syncCardMessages(card)
                options.onUpdate?.(card)
                return
            }

            const response = await fetch(buildApiUrl('/chat/stream'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: card.type === 'quiz' ? 'quiz' : 'chat',
                    context: contextText,
                    messages: history
                })
            })
            if (!response.ok) throw new Error('Network response was not ok')
            const reader = response.body.getReader()
            const decoder = new TextDecoder()
            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                const chunk = decoder.decode(value, { stream: true })
                await appendAssistantContent(messages, assistantIndex, chunk, () => {
                    syncCardMessages(card)
                    options.onUpdate?.(card)
                })
            }
        } catch (err) {
            const currentAssistant = messages[assistantIndex] || { role: 'assistant', content: '' }
            messages[assistantIndex] = {
                ...currentAssistant,
                content: `${currentAssistant.content || ''}\n\n[Error: ${err.message}]`
            }
            syncCardMessages(card)
            options.onUpdate?.(card)
        } finally {
            syncCardMessages(card)
            card.loading = false
            options.onUpdate?.(card)
            if (card.noteId) {
                try {
                    await apiClient.put(`/notes/${card.noteId}`, { note_content: card.noteContent })
                } catch (error) {
                    console.error('Failed to persist card chat:', error)
                }
            }
        }
    }

    const streamChat = async (note, userPrompt, currentChapterId) => {
        if (!userPrompt.trim() || note.loading) return

        const messages = ensureNoteMessages(note)

        // Handle /note command
        if (userPrompt.startsWith('/note ')) {
            const noteContent = userPrompt.slice(6).trim()
            if (!noteContent) return

            messages.push({ role: 'user', content: noteContent })
            syncNoteMessages(note)

            if (!note.id) {
                note.title = 'Note...'
                try {
                    const createRes = await apiClient.post('/notes', {
                        chapter_id: currentChapterId,
                        selected_text: note.selected_text,
                        note_content: note.note_content,
                        title: note.title,
                        type: 'custom_note',
                        start_index: 0
                    })
                    note.id = createRes.data.id
                    return { action: 'added_to_list' }
                } catch (err) {
                    console.error('Failed to save note:', err)
                }
            } else {
                apiClient.put(`/notes/${note.id}`, { note_content: note.note_content })
            }
            return
        }

        const isFirstMessage = !note.id && messages.length === 0

        messages.push({ role: 'user', content: userPrompt })
        syncNoteMessages(note)

        // Auto-save logic
        if (isFirstMessage) {
            note.title = 'Note...'
            try {
                const createRes = await apiClient.post('/notes', {
                    chapter_id: currentChapterId,
                    selected_text: note.selected_text,
                    note_content: note.note_content,
                    title: note.title,
                    type: 'custom_note',
                    start_index: 0
                })
                note.id = createRes.data.id

                // Async generate title
                apiClient.post('/generate-title', {
                    context: note.selected_text,
                    prompt: userPrompt
                }).then(titleRes => {
                    note.title = titleRes.data.title
                    apiClient.put(`/notes/${note.id}`, { title: note.title })
                })
            } catch (err) {
                console.error('Failed to auto-save note:', err)
            }
        }

        const history = buildHistory(messages)

        note.loading = true
        const assistantIndex = messages.push({ role: 'assistant', content: '' }) - 1
        syncNoteMessages(note)

        try {
            const response = await fetch(buildApiUrl('/chat/stream'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    context: note.selected_text,
                    messages: history
                })
            })

            if (!response.ok) throw new Error('Network response was not ok')

            const reader = response.body.getReader()
            const decoder = new TextDecoder()

            while (true) {
                const { done, value } = await reader.read()
                if (done) break
                const chunk = decoder.decode(value, { stream: true })
                await appendAssistantContent(messages, assistantIndex, chunk, () => {
                    syncNoteMessages(note)
                })
            }
        } catch (err) {
            const currentAssistant = messages[assistantIndex] || { role: 'assistant', content: '' }
            messages[assistantIndex] = {
                ...currentAssistant,
                content: `${currentAssistant.content || ''}\n\n[Error: ${err.message}]`
            }
        } finally {
            note.loading = false
            syncNoteMessages(note)
            if (note.id) {
                apiClient.put(`/notes/${note.id}`, { note_content: note.note_content })
            }
        }

        if (isFirstMessage) return { action: 'added_to_list' }
    }

    return {
        chatLoading,
        streamChat,
        streamCardChat
    }
}
