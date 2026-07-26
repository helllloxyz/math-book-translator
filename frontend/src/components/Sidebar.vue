<template>
  <nav class="sidebar">
    <div class="sidebar-heading">
      <h3>Book Map</h3>
      <router-link to="/" class="library-link">← Library </router-link>
    </div>

    <div class="tabs" role="tablist" aria-label="Reader content navigation">
      <button
        class="tab-button"
        :class="{ active: activeTab === 'book' }"
        type="button"
        role="tab"
        :aria-selected="activeTab === 'book'"
        @click="activeTab = 'book'"
      >
        Book
      </button>
      <button
        class="tab-button"
        :class="{ active: activeTab === 'guide' }"
        type="button"
        role="tab"
        :aria-selected="activeTab === 'guide'"
        @click="activeTab = 'guide'"
      >
        Guide
      </button>
    </div>

    <p v-if="visibleTree.length === 0" class="empty-state">{{ emptyMessage }}</p>

    <ul v-else class="tree-root">
      <ReaderTreeNode
        v-for="node in visibleTree"
        :key="node.id"
        :node="node"
        :current-item-id="currentItemId"
        @select-leaf="$emit('select-item', $event)"
      />
    </ul>
  </nav>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { flattenReaderLeaves } from '../utils/readerTree'
import ReaderTreeNode from './ReaderTreeNode.vue'

const props = defineProps({
  bookTree: {
    type: Array,
    default: () => []
  },
  guideTree: {
    type: Array,
    default: () => []
  },
  currentItemId: {
    type: [Number, String],
    default: null
  }
})

defineEmits(['select-item'])

const activeTab = ref('book')

const visibleTree = computed(() => {
  return activeTab.value === 'guide'
    ? props.guideTree
    : props.bookTree
})

const emptyMessage = computed(() => {
  return activeTab.value === 'guide'
    ? 'No guides yet.'
    : 'No chapters found.'
})

const syncTabWithCurrentItem = (itemId) => {
  if (flattenReaderLeaves(props.bookTree).some((item) => item.id === itemId)) activeTab.value = 'book'
  if (flattenReaderLeaves(props.guideTree).some((item) => item.id === itemId)) activeTab.value = 'guide'
}

watch(() => props.currentItemId, syncTabWithCurrentItem, { immediate: true })
</script>

<style scoped>
.sidebar {
  width: 320px;
  height: 100vh;
  overflow-y: auto;
  border-right: 1px solid #e8e1d6;
  padding: 1.1rem;
  background:
    linear-gradient(180deg, rgba(255, 251, 243, 0.96), rgba(248, 244, 236, 0.98)),
    radial-gradient(circle at 18% 0%, rgba(180, 139, 92, 0.15), transparent 34%);
}

.sidebar-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

h3 {
  margin: 0;
  color: #2e261b;
  font-size: 0.78rem;
  letter-spacing: 0.13em;
  text-transform: uppercase;
}

.library-link {
  flex: 0 0 auto;
  border-bottom: 1px solid transparent;
  color: #675a49;
  font-size: 0.78rem;
  font-weight: 650;
  line-height: 1.2;
  text-decoration: none;
  transition: border-color 140ms ease, color 140ms ease;
}

.library-link:hover {
  border-color: #9a7a4c;
  color: #2e261b;
}

.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.25rem;
  margin-bottom: 1rem;
  padding: 0.22rem;
  border: 1px solid #e1d5c4;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.85);
}

.tab-button {
  cursor: pointer;
  border: 0;
  border-radius: 999px;
  padding: 0.48rem 0.45rem;
  background: transparent;
  color: #7b6b57;
  font: inherit;
  font-size: 0.82rem;
  font-weight: 650;
  transition: background 160ms ease, color 160ms ease, box-shadow 160ms ease;
}

.tab-button.active {
  background: #2f291f;
  color: #fff8ea;
  box-shadow: 0 5px 16px rgba(62, 47, 28, 0.2);
}

.empty-state {
  margin: 1.5rem 0;
  color: #888;
  font-size: 0.9rem;
  line-height: 1.5;
}

.tree-root {
  list-style: none;
  padding: 0;
  margin: 0;
}
</style>
