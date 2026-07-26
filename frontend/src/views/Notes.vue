<template>
  <div class="notes-page">
    <header class="page-header" ref="headerRef">
      <div class="header-content">
        <router-link to="/" class="back-link">← Back to Library</router-link>
        <h1>Notes for {{ book?.title || 'Loading...' }}</h1>
      </div>
    </header>

    <div class="notes-container">
      <div v-if="loading" class="loading-state">Loading notes...</div>
      <div v-else-if="error" class="error-state">{{ error }}</div>
      <div v-else-if="notes.length === 0" class="empty-state">No notes found for this book.</div>
      
      <div v-else class="notes-grid">
        <NoteCard 
            v-for="(note, idx) in notes" 
            :key="note.id" 
            :note="note"
            class="page-note-card"
            @delete="handleDeleteNote(note)"
            @chat="handleNoteChat(note, $event)"
          />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { useBookStore } from '../stores/bookStore'
import { useChat } from '../composables/useChat'
import { renderMath } from '../utils/renderer'
import NoteCard from '../components/NoteCard.vue'

const route = useRoute()
const bookStore = useBookStore()
const { streamChat } = useChat()
const bookId = route.params.id

const notes = ref([])
const loading = ref(true)
const error = ref(null)
const headerRef = ref(null)

const book = computed(() => bookStore.books.find(b => b.id == bookId) || bookStore.currentBook)

const triggerRenderMath = () => {
  nextTick(() => {
    if (headerRef.value) {
      renderMath(headerRef.value)
    }
  })
}

onMounted(async () => {
  if (!book.value) {
      await bookStore.fetchBookDetails(bookId)
  }
  fetchNotes()
  triggerRenderMath()
})

watch(book, triggerRenderMath)

const fetchNotes = async () => {
    loading.value = true
    try {
        notes.value = await bookStore.fetchBookNotes(bookId)
    } catch (e) {
        error.value = "Failed to load notes: " + e.message
    } finally {
        loading.value = false
    }
}

const handleDeleteNote = async (note) => {
  try {
    await bookStore.deleteNote(note.id)
    notes.value = notes.value.filter(n => n.id !== note.id)
  } catch (e) {
    alert("Failed to delete note: " + e.message)
  }
}

const handleNoteChat = async (note, userPrompt) => {
    // Current chapter ID is not strictly needed here for existing notes 
    // but useChat expects it for /note command new note creation.
    // Existing notes already have an ID.
    await streamChat(note, userPrompt, note.chapter_id)
}
</script>

<style scoped>
.notes-page {
    min-height: 100vh;
    background: #fcfcfc;
}

.page-header {
    background: white;
    padding: 1.5rem 2rem;
    border-bottom: 1px solid #eee;
    margin-bottom: 2rem;
}

.header-content {
    max-width: 1000px;
    margin: 0 auto;
}

.back-link {
    text-decoration: none;
    color: #666;
    font-size: 0.9rem;
    display: inline-block;
    margin-bottom: 0.5rem;
}

.back-link:hover {
    color: var(--primary-color);
}

h1 {
    margin: 0;
    color: var(--primary-color);
    font-size: 1.8rem;
}

.notes-container {
    max-width: 1000px;
    margin: 0 auto;
    padding: 0 2rem 4rem 2rem;
}

.notes-grid {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
}

.page-note-card {
    position: relative !important;
    top: auto !important;
    width: 100%;
}

.loading-state, .error-state, .empty-state {
    text-align: center;
    padding: 3rem;
    color: #888;
    font-size: 1.1rem;
}

.error-state {
    color: #d32f2f;
}
</style>
