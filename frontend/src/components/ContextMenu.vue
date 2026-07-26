<template>
  <div v-if="visible" 
       class="context-menu" 
       :style="{ top: y + 'px', left: x + 'px' }">
    <button type="button" class="menu-item" @click="handleAction('note')">Note</button>
    <button type="button" class="menu-item" @click="handleAction('latex-repair')">Fix LaTeX</button>
  </div>
</template>

<script setup>
defineProps({
  visible: Boolean,
  x: Number,
  y: Number,
  selection: String
})

const emit = defineEmits(['action', 'close'])

const handleAction = (type) => {
  emit('action', type)
}
</script>

<style scoped>
.context-menu {
  position: fixed;
  background: white;
  border: 1px solid #ccc;
  box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
  z-index: 1000;
  border-radius: 4px;
  min-width: 150px;
}

.menu-item {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 0.9rem;
  text-align: left;
}

.menu-item:hover {
  background-color: #f0f0f0;
}
</style>
