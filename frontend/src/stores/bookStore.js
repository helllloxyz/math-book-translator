import { defineStore } from 'pinia'
import { apiClient } from '../api/client'

export const useBookStore = defineStore('book', {
  state: () => ({
    books: [],
    currentBook: null,
    loading: false,
    error: null
  }),
  actions: {
    async fetchBooks() {
      this.loading = true
      this.error = null
      try {
        const response = await apiClient.get('/books')
        this.books = response.data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    async fetchBookDetails(id) {
      this.loading = true
      this.currentBook = null
      try {
        const response = await apiClient.get(`/books/${id}`)
        this.currentBook = response.data
      } catch (err) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
    async fetchBookManagement(id) {
      try {
        const response = await apiClient.get(`/books/${id}/management`)
        return response.data
      } catch (err) {
        const message = err.response?.data?.detail || err.message
        this.error = message
        throw new Error(message)
      }
    },
    async uploadBook(file, options = {}) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('force', String(Boolean(options.force)));
        formData.append('preflight', String(options.preflight !== false));
        if (Array.isArray(options.outlineSelection)) {
          formData.append('outline_selection', JSON.stringify(options.outlineSelection));
        }
        if (options.outlinePlan && typeof options.outlinePlan === 'object') {
          formData.append('outline_plan', JSON.stringify(options.outlinePlan));
        }
        try {
            const response = await apiClient.post('/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });
            if (!response.data?.requires_confirmation) {
              await this.fetchBooks(); // Refresh list
            }
            return response.data;
        } catch (err) {
            this.error = err.message;
            throw err;
        }
    },
    async importBook(filePath, options = {}) {
      try {
        const response = await apiClient.post('/books/import', {
          file_path: filePath,
          force: Boolean(options.force),
          preflight: options.preflight !== false,
          outline_selection: Array.isArray(options.outlineSelection) ? options.outlineSelection : null,
          outline_plan: options.outlinePlan && typeof options.outlinePlan === 'object' ? options.outlinePlan : null
        });
        if (!response.data?.requires_confirmation) {
          await this.fetchBooks(); // Refresh list
        }
        return response.data;
      } catch (err) {
        this.error = err.message;
        throw err;
      }
    },
    async importBookPackage(file) {
      const formData = new FormData()
      formData.append('file', file)
      try {
        const response = await apiClient.post('/books/import-package', formData, {
          headers: {
            'Content-Type': 'multipart/form-data'
          }
        })
        await this.fetchBooks()
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async exportBookPackage(bookId, filename) {
      try {
        const response = await apiClient.get(`/books/${bookId}/export`, {
          responseType: 'blob'
        })
        const blobUrl = URL.createObjectURL(response.data)
        const link = document.createElement('a')
        link.href = blobUrl
        link.download = filename || `book-${bookId}.zip`
        document.body.appendChild(link)
        link.click()
        link.remove()
        URL.revokeObjectURL(blobUrl)
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async deleteBook(id) {
      try {
        await apiClient.delete(`/books/${id}`)
        this.books = this.books.filter(b => b.id !== id)
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async translateBook(id) {
      try {
        await apiClient.post(`/books/${id}/translate`)
        // Optimistically update status or fetch book details
        const book = this.books.find(b => b.id === id)
        if (book) book.status = 'translating'
      } catch (err) {
        const message = err.response?.data?.detail || err.message
        this.error = message
        throw new Error(message)
      }
    },
    async retranslateChapter(bookId, chapterId) {
      try {
        const response = await apiClient.post(`/books/${bookId}/chapters/${chapterId}/retranslate`)
        const book = this.books.find(item => item.id === Number(bookId))
        if (book) book.status = 'translating'
        return response.data
      } catch (err) {
        const message = err.response?.data?.detail || err.message
        this.error = message
        throw new Error(message)
      }
    },
    async generateBookGuides(id) {
      try {
        await apiClient.post(`/books/${id}/translate`)
        const book = this.books.find(item => item.id === id)
        if (book) book.status = 'generating_guides'
      } catch (err) {
        const message = err.response?.data?.detail || err.message
        this.error = message
        throw new Error(message)
      }
    },
    async renameBook(id, title) {
      try {
        await apiClient.put(`/books/${id}`, { title })
        const book = this.books.find(b => b.id === id)
        if (book) book.title = title
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async fetchChapterContent(chapterId) {
      try {
        const response = await apiClient.get(`/chapters/${chapterId}/content`)
        return response.data
      } catch (err) {
        console.error(err)
        return null
      }
    },
    async suggestChapterLatexRepair(chapterId, options = {}) {
      try {
        const response = await apiClient.post(`/chapters/${chapterId}/latex-repair/suggest`, {
          selected_text: options.selectedText || options.selected_text || '',
          content_target: options.contentTarget || options.content_target || 'translated',
          failed_candidates: Array.isArray(options.failedCandidates)
            ? options.failedCandidates
            : (options.failed_candidates || [])
        })
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      }
    },
    async applyChapterLatexRepair(chapterId, options = {}) {
      try {
        const response = await apiClient.post(`/chapters/${chapterId}/latex-repair/apply`, {
          original_text: options.originalText || options.original_text || '',
          replacement_text: options.replacementText || options.replacement_text || '',
          content_target: options.contentTarget || options.content_target || 'translated'
        })
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      }
    },
    async fetchChapterNotes(chapterId) {
      try {
        const response = await apiClient.get(`/chapters/${chapterId}/notes`)
        return response.data
      } catch (err) {
        console.error(err)
        throw err
      }
    },
    async fetchReaderTree(bookId) {
      try {
        const response = await apiClient.get(`/books/${bookId}/reader-tree`)
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async fetchReaderContent(bookId, options = {}) {
      try {
        const response = await apiClient.get(`/books/${bookId}/reader-content`, {
          params: {
            reader_type: options.readerType || options.reader_type || '',
            chapter_id: options.chapterId || options.chapter_id || null,
            guide_id: options.guideId || options.guide_id || ''
          }
        })
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async fetchSourceNotes(bookId, sourceType, sourceId) {
      try {
        const response = await apiClient.get(`/books/${bookId}/notes/source`, {
          params: {
            source_type: sourceType,
            source_id: sourceId
          }
        })
        return response.data
      } catch (err) {
        console.error(err)
        throw err
      }
    },
    async createAnnotation(annotation = {}) {
      try {
        const response = await apiClient.post('/notes', {
          book_id: annotation.bookId || annotation.book_id,
          chapter_id: annotation.chapterId || annotation.chapter_id || null,
          source_type: annotation.sourceType || annotation.source_type,
          source_id: annotation.sourceId || annotation.source_id,
          source_title: annotation.sourceTitle || annotation.source_title || '',
          selected_text: annotation.selectedText || annotation.selected_text || '',
          start_index: Number.isFinite(annotation.startIndex)
            ? annotation.startIndex
            : (annotation.start_index || 0),
          note_content: JSON.stringify({
            style: annotation.style === 'underline' ? 'underline' : 'highlight',
            content_target: annotation.contentTarget || annotation.content_target || 'translated'
          }),
          title: null,
          type: 'annotation'
        })
        return response.data
      } catch (err) {
        this.error = err.response?.data?.detail || err.message
        throw err
      }
    },
    async generateTopDownGuides(bookId) {
      try {
        const response = await apiClient.post(`/books/${bookId}/guides/top-down`)
        return response.data.guides
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async generateChapterGuide(bookId, chapterId) {
      try {
        const response = await apiClient.post(`/books/${bookId}/chapters/${chapterId}/guides`)
        return response.data.guides
      } catch (err) {
        const message = err.response?.data?.detail || err.message
        this.error = message
        throw new Error(message)
      }
    },
    async fetchBookGuides(bookId) {
      try {
        const response = await apiClient.get(`/books/${bookId}/guides`)
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async fetchBookGuide(bookId, filename) {
      try {
        const response = await apiClient.get(`/books/${bookId}/guides/${encodeURIComponent(filename)}`)
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async fetchLearningProfileStatus(bookId) {
      try {
        const response = await apiClient.get(`/books/${bookId}/quiz/profile/status`)
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async analyzeLearningProfile(bookId) {
      try {
        const response = await apiClient.post(`/books/${bookId}/quiz/profile/analyze`)
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async fetchLearningProfile(bookId) {
      try {
        const response = await apiClient.get(`/books/${bookId}/quiz/profile`)
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async fetchNextQuizQuestion(chapterId, options = {}) {
      try {
        const response = await apiClient.post(`/chapters/${chapterId}/quiz/next`, {
          quiz_mode: options.quizMode || options.quiz_mode || 'chapter',
          question_type: options.questionType || options.question_type || null,
          personalization_context: options.personalizationContext || options.personalization_context || null
        })
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async fetchQuizCandidates(chapterId, options = {}) {
      try {
        const response = await apiClient.post(`/chapters/${chapterId}/quiz/candidates`, {
          quiz_mode: options.quizMode || options.quiz_mode || 'chapter',
          question_type: options.questionType || options.question_type || null,
          personalization_context: options.personalizationContext || options.personalization_context || null,
          count: options.count || 3,
          previous_questions: options.previousQuestions || options.previous_questions || []
        })
        return Array.isArray(response.data?.questions) ? response.data.questions : []
      } catch (err) {
        const message = err.response?.data?.detail || err.message
        this.error = message
        throw new Error(message)
      }
    },
    async submitQuizAttempt(questionId, answerText, conversationHistory = []) {
      try {
        const response = await apiClient.post(`/quiz/questions/${questionId}/attempts`, {
          answer_text: answerText,
          conversation_history: conversationHistory
        })
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async selectBookQuizTarget(bookId, options = {}) {
      try {
        const response = await apiClient.post(`/books/${bookId}/quiz/select-target`, {
          personalization_context: options.personalizationContext || options.personalization_context || null
        })
        return response.data
      } catch (err) {
        this.error = err.message
        throw err
      }
    },
    async fetchBookNotes(bookId) {
      try {
        const response = await apiClient.get(`/books/${bookId}/notes`)
        return response.data
      } catch (err) {
        console.error(err)
        throw err
      }
    },
    async deleteNote(noteId) {
      try {
        await apiClient.delete(`/notes/${noteId}`)
      } catch (err) {
        console.error(err)
        throw err
      }
    }
  }
})
