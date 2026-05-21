<template>
  <div class="placeholder">
    <el-empty :description="title + ' - 功能开发中'" />
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, default: '' },
})
</script>
