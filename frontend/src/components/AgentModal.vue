<template>
  <div v-if="show" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-container">
      <header class="modal-header">
        <h2>DeepTree Author</h2>
        <button class="close-btn" @click="$emit('close')">&times;</button>
      </header>

      <div class="modal-body">
        <p class="description">
          Enter a mathematical domain or topic. The AI will architect a comprehensive textbook 
          starting from first principles.
        </p>

        <div class="input-group">
          <label for="domain">Mathematical Domain</label>
          <input 
            id="domain"
            v-model="domain" 
            type="text" 
            placeholder="e.g., Differential Geometry, Category Theory..."
            :disabled="loading"
            @keyup.enter="handleCreate"
          />
        </div>

        <div class="features-list">
          <div class="feature-item">
            <span class="icon">📐</span>
            <div>
              <strong>Axiomatic Basis</strong>
              <p>Generated from core axioms and primitive objects.</p>
            </div>
          </div>
          <div class="feature-item">
            <span class="icon">🌲</span>
            <div>
              <strong>Recursive Depth</strong>
              <p>Topics expanded into intuition, formalism, and nuance.</p>
            </div>
          </div>
        </div>
      </div>

      <footer class="modal-footer">
        <button class="secondary-btn" @click="$emit('close')" :disabled="loading">Cancel</button>
        <button 
          class="primary-btn" 
          @click="handleCreate" 
          :disabled="loading || !domain.trim()"
        >
          {{ loading ? 'Initializing...' : 'Start Authoring' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  show: Boolean,
  loading: Boolean
})

const emit = defineEmits(['close', 'create'])

const domain = ref('')

const handleCreate = () => {
  if (domain.value.trim() && !props.loading) {
    emit('create', domain.value.trim())
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-container {
  background: white;
  width: 90%;
  max-width: 500px;
  border-radius: 16px;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.modal-header {
  padding: 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #f1f5f9;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  color: #1e293b;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #94a3b8;
  cursor: pointer;
}

.modal-body {
  padding: 1.5rem;
}

.description {
  color: #64748b;
  font-size: 0.95rem;
  line-height: 1.5;
  margin-bottom: 1.5rem;
}

.input-group {
  margin-bottom: 1.5rem;
}

.input-group label {
  display: block;
  font-size: 0.875rem;
  font-weight: 600;
  color: #475569;
  margin-bottom: 0.5rem;
}

.input-group input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.2s;
}

.input-group input:focus {
  outline: none;
  border-color: var(--accent-color);
}

.features-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.feature-item {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.feature-item .icon {
  font-size: 1.25rem;
  padding: 0.5rem;
  background: #f1f5f9;
  border-radius: 8px;
}

.feature-item strong {
  display: block;
  font-size: 0.9rem;
  color: #1e293b;
}

.feature-item p {
  margin: 0.25rem 0 0 0;
  font-size: 0.8rem;
  color: #64748b;
}

.modal-footer {
  padding: 1.25rem 1.5rem;
  background: #f8fafc;
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  border-top: 1px solid #f1f5f9;
}

.secondary-btn {
  padding: 0.6rem 1.25rem;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-weight: 600;
  color: #475569;
  cursor: pointer;
}

.primary-btn {
  padding: 0.6rem 1.5rem;
  background: var(--accent-color);
  border: none;
  border-radius: 8px;
  font-weight: 600;
  color: white;
  cursor: pointer;
}

.primary-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
