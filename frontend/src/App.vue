<template>
  <div class="app-wrapper">
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>

<style>
html, body, #app {
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  max-width: none !important; /* 强制取消最大宽度限制 */
  overflow: hidden; /* 防止出现双滚动条 */
  display: block;   /* 防止父级变成 flex 导致的挤压 */
}

.app-wrapper {
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  flex: 1;
  height: 100vh;
  min-width: 0;
  overflow-y: auto;
  background-color: var(--bg-color);
}
</style>