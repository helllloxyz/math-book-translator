<template>
  <Transition name="fade">
    <div v-if="show" class="console-overlay" @click.self="$emit('close')">
      <Transition name="slide-up">
        <div v-if="show" class="console-modal">
          <header class="console-header">
            <div class="title">
              <div class="terminal-dots">
                <span></span><span></span><span></span>
              </div>
              <h3>Agent Console - {{ bookTitle }}</h3>
            </div>
            <button class="close-btn" @click="$emit('close')">&times;</button>
          </header>

          <div class="console-body" ref="logContainer" @scroll="handleScroll">
            <div v-if="history.length === 0 && !sending" class="empty-log">
              <div class="system-art">
                <pre>
  ____                   _____              
 |  _ \  ___  ___ _ __  |_   _| __ ___  ___ 
 | | | |/ _ \/ _ \ '_ \   | || '__/ _ \/ _ \
 | |_| |  __/  __/ |_) |  | || | |  __/  __/
 |____/ \___|\___| .__/   |_||_|  \___|\___|
                 |_|                        
                </pre>
              </div>
              <p>DeepTree Authoring Environment Initialized.</p>
              <p>Type <code>help</code> to see available commands.</p>
            </div>
            <div v-else class="log-entries">
              <div v-for="(entry, idx) in history" :key="idx" class="log-entry" :class="entry.status">
                <div class="log-meta">
                  <span class="log-time">{{ formatTime(entry.timestamp) }}</span>
                  <span class="log-node" v-if="entry.node !== 'console'">{{ entry.node }}</span>
                </div>
                <div class="log-content">
                  <span class="log-command" v-if="entry.command">> {{ entry.command }}</span>
                  <div class="log-response" v-if="entry.response" v-html="renderMarkdown(entry.response)"></div>
                </div>
              </div>
              
              <!-- Thinking / Loading Animation -->
              <div v-if="isAgentActive" class="log-entry info">
                <div class="log-meta">
                  <span class="log-time">{{ formatTime(new Date()) }}</span>
                  <span class="log-node">agent</span>
                </div>
                <div class="log-content">
                  <div class="thinking-wrapper">
                    <div class="spinner"></div>
                    <span class="thinking-text">
                      {{ sending ? 'Sending command...' : 'Agent is working...' }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <footer class="console-footer">
            <div class="input-wrapper">
              <span class="prompt">$</span>
              <input 
                ref="inputField"
                v-model="userInput" 
                @keydown.up.prevent="navigateHistory('up')"
                @keydown.down.prevent="navigateHistory('down')"
                @keyup.enter="sendCommand" 
                placeholder="Type command..."
                :disabled="isAgentActive"
                class="console-input"
              />
              <div class="footer-actions">
                <button @click="sendCommand" :disabled="isAgentActive || !userInput.trim()" class="send-btn">
                  <template v-if="isAgentActive">
                    <div class="spinner mini"></div>
                  </template>
                  <template v-else>
                    Execute
                  </template>
                </button>
              </div>
            </div>
          </footer>
        </div>
      </Transition>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch, computed } from 'vue'
import { useBookStore } from '../stores/bookStore'
import { renderMarkdown as mdRenderer } from '../utils/renderer'

const props = defineProps({
  show: Boolean,
  bookId: Number,
  bookTitle: String
})

const emit = defineEmits(['close'])

const bookStore = useBookStore()
const history = ref([])
const userInput = ref('')
const sending = ref(false)
const logContainer = ref(null)
const inputField = ref(null)
const localBookId = ref(props.bookId)
const localBookTitle = ref(props.bookTitle)

// Command History logic
const commandHistory = ref([])
const historyIndex = ref(-1)
const userScrolledUp = ref(false)
let refreshInterval = null

const isAgentActive = computed(() => {
  if (sending.value) return true
  if (history.value.length === 0) return false
  const lastEntry = history.value[history.value.length - 1]
  // Only consider it 'active' if it's an 'info' status from a non-system node
  return lastEntry.status === 'info' && lastEntry.node !== 'system' && lastEntry.node !== 'console'
})

const handleScroll = () => {
  if (!logContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value
  // If user scrolls up more than 50px from bottom, stop auto-scrolling
  userScrolledUp.value = scrollHeight - scrollTop - clientHeight > 50
}

const navigateHistory = (direction) => {
  if (commandHistory.value.length === 0) return
  
  if (direction === 'up') {
    if (historyIndex.value < commandHistory.value.length - 1) {
      historyIndex.value++
      userInput.value = commandHistory.value[commandHistory.value.length - 1 - historyIndex.value]
    }
  } else {
    if (historyIndex.value > 0) {
      historyIndex.value--
      userInput.value = commandHistory.value[commandHistory.value.length - 1 - historyIndex.value]
    } else {
      historyIndex.value = -1
      userInput.value = ''
    }
  }
}

const fetchHistory = async (forceScroll = false) => {
  if (!localBookId.value) return

  try {
    const data = await bookStore.fetchAgentHistory(localBookId.value)
    const hasNewMessages = data.length > history.value.length
    history.value = data
    
    if (hasNewMessages && (forceScroll || !userScrolledUp.value)) {
      await nextTick()
      scrollToBottom()
    }
  } catch (e) {
    console.error("Failed to fetch console history")
  }
}

const sendCommand = async () => {
  if (!userInput.value.trim() || sending.value) return
  
  const cmd = userInput.value.trim()
  
  // Add to command history
  if (commandHistory.value[commandHistory.value.length - 1] !== cmd) {
    commandHistory.value.push(cmd)
    if (commandHistory.value.length > 50) commandHistory.value.shift()
  }
  historyIndex.value = -1
  
  userInput.value = ''
  sending.value = true
  userScrolledUp.value = false
  
  await nextTick()
  scrollToBottom()
  
  try {
    if (!localBookId.value) {
      const newBookId = await bookStore.initAgentBook(cmd)
      localBookId.value = newBookId
      localBookTitle.value = cmd
      
      if (refreshInterval) clearInterval(refreshInterval)
      await fetchHistory(true)
      refreshInterval = setInterval(() => fetchHistory(false), 3000)
    } else {
      await bookStore.interactWithAgent(localBookId.value, cmd)
      await fetchHistory(true)
    }
  } catch (e) {
    console.error("Command failed", e)
    history.value.push({
      timestamp: new Date().toISOString(),
      node: 'error',
      response: `**Error:** ${e.message}`,
      status: 'error'
    })
  } finally {
    sending.value = false
    nextTick(() => {
      inputField.value?.focus()
      scrollToBottom()
    })
  }
}

const scrollToBottom = () => {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

const formatTime = (ts) => {
  const date = new Date(ts)
  return date.toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit' })
}

const renderMarkdown = (text) => {
  return mdRenderer(text)
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    localBookId.value = props.bookId
    localBookTitle.value = props.bookTitle
    userScrolledUp.value = false
    
    if (localBookId.value) {
      fetchHistory(true)
      refreshInterval = setInterval(() => fetchHistory(false), 3000)
    } else {
      history.value = [{
        timestamp: new Date().toISOString(),
        node: 'system',
        response: "### DeepTree Author\n\nPlease confirm the **mathematical domain or topic** you wish to author:",
        status: 'success'
      }]
    }
    nextTick(() => inputField.value?.focus())
  } else {
    if (refreshInterval) clearInterval(refreshInterval)
  }
})

onMounted(() => {
  if (props.show) {
    if (localBookId.value) {
      fetchHistory(true)
      refreshInterval = setInterval(() => fetchHistory(false), 3000)
    }
  }
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<style scoped>
/* Modal Transitions */
.fade-enter-active, .fade-leave-active { transition: opacity 0.3s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.slide-up-enter-active, .slide-up-leave-active { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
.slide-up-enter-from, .slide-up-leave-to { transform: translateY(20px) scale(0.98); opacity: 0; }

.console-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 2000;
  backdrop-filter: blur(8px);
}

.console-modal {
  background: #0f0f0f;
  width: 95%;
  max-width: 900px;
  height: 85vh;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 30px 60px -12px rgba(0, 0, 0, 0.8), 0 0 0 1px #333;
  overflow: hidden;
  font-family: 'Fira Code', 'JetBrains Mono', 'Courier New', monospace;
}

/* Header Styles */
.console-header {
  background: #1a1a1a;
  padding: 0.8rem 1.2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #2a2a2a;
}

.terminal-dots {
  display: flex;
  gap: 6px;
  margin-right: 12px;
}

.terminal-dots span {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
.terminal-dots span:nth-child(1) { background: #ff5f56; }
.terminal-dots span:nth-child(2) { background: #ffbd2e; }
.terminal-dots span:nth-child(3) { background: #27c93f; }

.console-header .title {
  display: flex;
  align-items: center;
  color: #a0a0a0;
}

.console-header h3 {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 500;
  letter-spacing: 0.5px;
}

.close-btn {
  background: none;
  border: none;
  color: #666;
  font-size: 1.8rem;
  cursor: pointer;
  line-height: 1;
  transition: color 0.2s;
}

.close-btn:hover { color: #fff; }

/* Body Styles */
.console-body {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  background: #0a0a0a;
  color: #e0e0e0;
  font-size: 0.9rem;
  line-height: 1.6;
  scrollbar-width: thin;
  scrollbar-color: #333 transparent;
}

.console-body::-webkit-scrollbar { width: 6px; }
.console-body::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }

.log-entry {
  margin-bottom: 1.2rem;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateX(-5px); }
  to { opacity: 1; transform: translateX(0); }
}

.log-meta {
  display: flex;
  gap: 0.8rem;
  margin-bottom: 0.3rem;
  font-size: 0.75rem;
  opacity: 0.6;
}

.log-time { color: #569cd6; }
.log-node { 
  background: #252525;
  padding: 0 6px;
  border-radius: 3px;
  color: #ce9178;
}

.log-entry.error .log-node { color: #f44747; background: rgba(244, 71, 71, 0.1); }
.log-entry.success .log-node { color: #6a9955; }

.log-command {
  color: #4fc1ff;
  font-weight: 600;
  display: block;
  margin-bottom: 0.5rem;
}

.log-response { color: #d4d4d4; }
.log-response :deep(h1), .log-response :deep(h2), .log-response :deep(h3) {
  color: #569cd6;
  margin: 1rem 0 0.5rem 0;
  font-size: 1.1rem;
}
.log-response :deep(p) { margin: 0 0 0.8rem 0; }
.log-response :deep(code) { 
  background: #1e1e1e; 
  padding: 2px 6px; 
  border-radius: 4px;
  color: #ce9178;
  font-size: 0.85rem;
}
.log-response :deep(pre) {
  background: #1e1e1e;
  padding: 1rem;
  border-radius: 6px;
  overflow-x: auto;
  border: 1px solid #333;
}
.log-response :deep(ul), .log-response :deep(ol) {
  padding-left: 1.5rem;
  margin-bottom: 0.8rem;
}

/* Footer Styles */
.console-footer {
  background: #1a1a1a;
  padding: 1rem 1.2rem;
  border-top: 1px solid #2a2a2a;
}

.input-wrapper {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  background: #000;
  padding: 0.4rem 0.8rem;
  border-radius: 6px;
  border: 1px solid #333;
  transition: border-color 0.2s;
}

.input-wrapper:focus-within { border-color: #569cd6; }

.prompt {
  color: #27c93f;
  font-weight: bold;
  font-size: 1.1rem;
}

.console-input {
  flex: 1;
  background: none;
  border: none;
  color: #fff;
  font-family: inherit;
  font-size: 1rem;
  outline: none;
  padding: 0.6rem 0;
}

.send-btn {
  background: #252525;
  color: #ccc;
  border: 1px solid #333;
  padding: 0.5rem 1.2rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 500;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 80px;
}

.send-btn:hover:not(:disabled) {
  background: #333;
  color: #fff;
  border-color: #444;
}

.send-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Thinking Animation */
.thinking-wrapper {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  margin-top: 0.4rem;
  color: #569cd6;
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(86, 156, 214, 0.2);
  border-top-color: #569cd6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner.mini { width: 14px; height: 14px; border-top-color: #fff; }

@keyframes spin { to { transform: rotate(360deg); } }

/* Empty State */
.empty-log {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #444;
  text-align: center;
}

.system-art pre {
  font-size: 0.6rem;
  line-height: 1.1;
  margin-bottom: 1.5rem;
  color: #222;
}

.empty-log p { margin: 0.2rem 0; font-size: 0.85rem; }
</style>
