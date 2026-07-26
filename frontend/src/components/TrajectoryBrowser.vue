<template>
  <div class="trajectory-browser">
    <header class="browser-header">
      <h4>Cognitive Trajectory</h4>
      <button class="refresh-btn" @click="fetchHistory" :disabled="loading">
        {{ loading ? '...' : 'Refresh' }}
      </button>
    </header>

    <div v-if="history.length === 0" class="empty-history">
      No interaction history found.
    </div>
    
    <div v-else class="timeline">
      <div v-for="(entry, idx) in history" :key="idx" class="timeline-entry" :class="entry.status">
        <div class="entry-dot"></div>
        <div class="entry-content">
          <div class="entry-meta">
            <span class="timestamp">{{ formatTime(entry.timestamp) }}</span>
            <span class="node">Node: {{ entry.node }}</span>
          </div>
          <div class="entry-command"><code>{{ entry.command }}</code></div>
          <div v-if="entry.prompt" class="entry-prompt">
            <strong>Prompt:</strong> {{ entry.prompt }}
          </div>
          <div v-if="entry.response" class="entry-response">
             <details>
               <summary>AI Response ({{ entry.response.length }} chars)</summary>
               <div class="response-text">{{ entry.response }}</div>
             </details>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useBookStore } from '../stores/bookStore'

const props = defineProps({
  bookId: Number
})

const bookStore = useBookStore()
const history = ref([])
const loading = ref(false)

const fetchHistory = async () => {
  loading.value = true
  try {
    history.value = await bookStore.fetchAgentHistory(props.bookId)
    // Show newest first
    history.value.reverse()
  } catch (e) {
    console.error("Failed to fetch history")
  } finally {
    loading.value = false
  }
}

const formatTime = (ts) => {
  const date = new Date(ts)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

onMounted(fetchHistory)
</script>

<style scoped>
.trajectory-browser {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.browser-header {
  padding: 1rem;
  border-bottom: 1px solid #f1f5f9;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.browser-header h4 {
  margin: 0;
  color: #1e293b;
  font-size: 0.9rem;
}

.refresh-btn {
  background: none;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  font-size: 0.75rem;
  padding: 2px 8px;
  cursor: pointer;
}

.timeline {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.timeline-entry {
  position: relative;
  padding-left: 1.5rem;
  border-left: 2px solid #f1f5f9;
}

.entry-dot {
  position: absolute;
  left: -6px;
  top: 0;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #cbd5e1;
  border: 2px solid white;
}

.success .entry-dot { background: #10b981; }
.revoked .entry-dot { background: #f59e0b; }
.error .entry-dot { background: #ef4444; }

.entry-meta {
  display: flex;
  justify-content: space-between;
  font-size: 0.7rem;
  color: #94a3b8;
  margin-bottom: 0.25rem;
}

.entry-command {
  font-size: 0.85rem;
  font-weight: 600;
  color: #334155;
  margin-bottom: 0.5rem;
}

.entry-prompt {
  font-size: 0.8rem;
  color: #64748b;
  background: #f8fafc;
  padding: 0.5rem;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.entry-response summary {
  font-size: 0.75rem;
  color: var(--accent-color);
  cursor: pointer;
}

.response-text {
  font-size: 0.75rem;
  white-space: pre-wrap;
  color: #475569;
  padding: 0.5rem;
  background: #f1f5f9;
  border-radius: 4px;
  margin-top: 0.25rem;
}

.empty-history {
  padding: 2rem;
  text-align: center;
  color: #94a3b8;
  font-size: 0.9rem;
}
</style>
