<template>
  <header class="page-header">
    <h1 class="page-title" :class="{ 'page-title--gradient': gradient }">
      {{ title }}
    </h1>
    <p v-if="subtitle" class="page-subtitle">{{ subtitle }}</p>
  </header>
</template>

<script setup>
/**
 * PageHeader — 统一页面头部
 *
 * 用法：
 *   <PageHeader title="作业上传" subtitle="支持图片和 PDF 格式" />
 *   <PageHeader title="知识强化" subtitle="薄弱知识点" gradient />
 */
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  gradient: { type: Boolean, default: false }
})
</script>

<style scoped>
.page-title--gradient {
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
</style>
