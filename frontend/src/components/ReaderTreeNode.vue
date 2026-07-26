<template>
  <li class="tree-node">
    <button
      v-if="isDirectory"
      class="directory-row"
      type="button"
      :style="{ paddingLeft: `${depth * 0.85 + 0.35}rem` }"
      @click="expanded = !expanded"
    >
      <span class="disclosure">{{ expanded ? 'v' : '>' }}</span>
      <span ref="titleRef" class="item-title" v-html="renderedDisplayTitle"></span>
    </button>

    <button
      v-else
      class="leaf-row"
      :class="{ active: currentItemId === node.id }"
      type="button"
      :style="{ paddingLeft: `${depth * 0.85 + 0.35}rem` }"
      @click="$emit('select-leaf', node)"
    >
      <span class="leaf-marker" aria-hidden="true">•</span>
      <span ref="titleRef" class="item-title" v-html="renderedDisplayTitle"></span>
    </button>

    <ul v-if="isDirectory && expanded" class="tree-children">
      <ReaderTreeNode
        v-for="child in node.children || []"
        :key="child.id"
        :node="child"
        :depth="depth + 1"
        :current-item-id="currentItemId"
        @select-leaf="$emit('select-leaf', $event)"
      />
    </ul>
  </li>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { renderMarkdown, renderMath } from '../utils/renderer'

const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  depth: {
    type: Number,
    default: 0
  },
  currentItemId: {
    type: [Number, String],
    default: null
  }
})

defineEmits(['select-leaf'])

const expanded = ref(false)
const titleRef = ref(null)
const isDirectory = computed(() => props.node?.kind !== 'leaf')
const labelText = computed(() => String(props.node?.label || '').replace(/\s+/g, ' ').trim())
const titleText = computed(() => String(props.node?.title || '').replace(/\s+/g, ' ').trim())
const visibleLabel = computed(() => {
  if (!labelText.value) return false
  return !titleText.value.startsWith(labelText.value)
})
const displayTitle = computed(() => {
  return props.node?.title || ''
})
const escapeHtml = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&#39;')
const renderedDisplayTitle = computed(() => {
  const renderedTitle = renderMarkdown(displayTitle.value)
    .replace(/^<p>/, '')
    .replace(/<\/p>\n?$/, '')

  return visibleLabel.value
    ? `${escapeHtml(labelText.value)} ${renderedTitle}`
    : renderedTitle
})

const renderTitleMath = async () => {
  await nextTick()
  if (!titleRef.value) return
  try {
    renderMath(titleRef.value)
  } catch (error) {
    console.error('Failed to render sidebar title math:', error)
  }
}

watch(renderedDisplayTitle, renderTitleMath, { immediate: true, flush: 'post' })
</script>

<style scoped>
.tree-node,
.tree-children {
  list-style: none;
  margin: 0;
  padding: 0;
}

.directory-row,
.leaf-row {
  width: 100%;
  min-height: 2.25rem;
  border: 1px solid transparent;
  border-radius: 0.45rem;
  background: transparent;
  color: #352d22;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.38rem;
  margin-bottom: 0.14rem;
  padding: 0.42rem 0.5rem;
  text-align: left;
  font: inherit;
  transition: background 140ms ease, border-color 140ms ease;
}

.directory-row {
  color: #5a4d3d;
}

.leaf-row:hover,
.directory-row:hover {
  background: rgba(255, 255, 255, 0.78);
  border-color: #eadfce;
}

.leaf-row.active {
  background: #fff7e8;
  border-color: #d8b77c;
  box-shadow: 0 7px 18px rgba(82, 61, 32, 0.08);
  font-weight: 700;
}

.disclosure {
  flex: 0 0 1rem;
  color: #8b7962;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 1.1rem;
  font-weight: 700;
  line-height: 1;
  text-align: center;
}

.leaf-marker {
  flex: 0 0 1rem;
  color: #b09b7d;
  font-size: 0.92rem;
  line-height: 1;
  text-align: center;
}

.item-title {
  min-width: 0;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
</style>
