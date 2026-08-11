<template>
  <li class="tree-node">
    <button
      v-if="isDirectory"
      class="directory-row"
      type="button"
      :aria-expanded="expanded"
      :style="{ paddingLeft: `${depth * 0.85 + 0.35}rem` }"
      @click="expanded = !expanded"
    >
      <span class="disclosure" :class="{ expanded }" aria-hidden="true">
        <svg viewBox="0 0 12 12" focusable="false">
          <path d="M4.7 10c-.2 0-.4-.1-.5-.2-.3-.3-.3-.8 0-1.1L6.9 6 4.2 3.3c-.3-.3-.3-.8 0-1.1.3-.3.8-.3 1.1 0l3.3 3.2c.3.3.3.8 0 1.1L5.3 9.7c-.2.2-.4.3-.6.3Z" />
        </svg>
      </span>
      <span ref="titleRef" class="item-title" v-html="renderedDisplayTitle"></span>
    </button>

    <button
      v-else
      ref="rowRef"
      class="leaf-row"
      :class="{ active: isCurrentItem }"
      type="button"
      :aria-current="isCurrentItem ? 'page' : undefined"
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
const rowRef = ref(null)
const isDirectory = computed(() => props.node?.kind !== 'leaf')
const isCurrentItem = computed(() => (
  props.currentItemId !== null &&
  props.currentItemId !== undefined &&
  String(props.currentItemId) === String(props.node?.id)
))
const containsCurrentItem = computed(() => {
  if (!isDirectory.value || props.currentItemId === null || props.currentItemId === undefined) return false

  const targetId = String(props.currentItemId)
  const containsTarget = (node) => {
    if (String(node?.id) === targetId) return true
    return (node?.children || []).some(containsTarget)
  }

  return (props.node?.children || []).some(containsTarget)
})
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
watch(containsCurrentItem, (containsCurrent) => {
  if (containsCurrent) expanded.value = true
}, { immediate: true })
watch(isCurrentItem, async (isCurrent) => {
  if (!isCurrent) return
  await nextTick()
  rowRef.value?.scrollIntoView?.({ block: 'nearest' })
}, { immediate: true, flush: 'post' })
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

.directory-row:hover .disclosure {
  color: #5f4e39;
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
  display: grid;
  width: 1rem;
  height: 1rem;
  place-items: center;
  transition: color 160ms ease;
}

.disclosure svg {
  width: 0.75rem;
  height: 0.75rem;
  fill: currentColor;
  transform-origin: center;
  transition: transform 180ms cubic-bezier(0.2, 0.75, 0.25, 1);
}

.disclosure.expanded svg {
  transform: rotate(90deg);
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

@media (prefers-reduced-motion: reduce) {
  .disclosure svg {
    transition: none;
  }
}
</style>
