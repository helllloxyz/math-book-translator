<template>
  <div
    v-if="visible"
    class="context-menu"
    :class="{ 'annotation-menu': activeAnnotationId }"
    :style="{ top: y + 'px', left: x + 'px' }"
    role="toolbar"
    aria-label="文本操作"
    @mousedown.prevent
  >
    <template v-if="activeAnnotationId">
      <button type="button" class="menu-item" @click="handleAction('annotation-note')">
        写笔记
      </button>
      <button type="button" class="menu-item danger-item" @click="handleAction('annotation-remove')">
        移除标注
      </button>
    </template>
    <template v-else>
      <button v-if="annotationAllowed" type="button" class="menu-item annotation-item" title="黄色标注" @click="handleAction('annotation-highlight')">
        <span class="highlight-swatch" aria-hidden="true">A</span>
        <span>黄色标注</span>
      </button>
      <button v-if="annotationAllowed" type="button" class="menu-item annotation-item" title="下划线" @click="handleAction('annotation-underline')">
        <span class="underline-swatch" aria-hidden="true">A</span>
        <span>下划线</span>
      </button>
      <span v-if="annotationAllowed" class="menu-divider" aria-hidden="true"></span>
      <button type="button" class="menu-item" @click="handleAction('selection-note')">选中提问</button>
      <button type="button" class="menu-item" @click="handleAction('chapter-note')">章节提问</button>
      <button type="button" class="menu-item" @click="handleAction('latex-repair')">修复公式</button>
    </template>
  </div>
</template>

<script setup>
defineProps({
  visible: Boolean,
  x: Number,
  y: Number,
  selection: String,
  activeAnnotationId: {
    type: Number,
    default: null
  },
  annotationAllowed: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['action', 'close'])

const handleAction = (type) => {
  emit('action', type)
}
</script>

<style scoped>
.context-menu {
  position: fixed;
  display: flex;
  align-items: center;
  gap: 2px;
  max-width: calc(100vw - 24px);
  padding: 5px;
  border: 1px solid #d8d0c4;
  border-radius: 9px;
  background: #fffdf8;
  box-shadow: 0 10px 28px rgba(54, 45, 32, 0.16), 0 2px 6px rgba(54, 45, 32, 0.08);
  z-index: 1000;
  overflow-x: auto;
  color: #3d372f;
}

.menu-item {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  padding: 7px 9px;
  color: inherit;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
  transition: background-color 160ms ease, color 160ms ease, transform 160ms ease;
}

.menu-item:hover {
  background: #f2eee6;
}

.menu-item:active {
  transform: translateY(1px);
}

.menu-item:focus-visible {
  outline: 2px solid #8a6d3b;
  outline-offset: 1px;
}

.annotation-item {
  padding-left: 7px;
}

.highlight-swatch,
.underline-swatch {
  display: inline-flex;
  width: 21px;
  height: 21px;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 13px;
  font-weight: 700;
}

.highlight-swatch {
  background: #f8e79b;
}

.underline-swatch {
  text-decoration: underline;
  text-decoration-color: #9b742d;
  text-decoration-thickness: 2px;
  text-underline-offset: 3px;
}

.menu-divider {
  width: 1px;
  height: 22px;
  margin: 0 3px;
  background: #ddd5c9;
}

.danger-item {
  color: #9a3d32;
}

.danger-item:hover {
  background: #f8e9e5;
}

.annotation-menu {
  min-width: auto;
}
</style>
