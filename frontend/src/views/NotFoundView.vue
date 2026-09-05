<template>
  <div class="not-found">
    <div class="nf-card fade-in-up">
      <div class="nf-code">404</div>
      <h2>页面不存在</h2>
      <p>你访问的页面走丢了，不如回到首页继续学习吧</p>
      <el-button type="primary" class="btn-primary" size="large" @click="$router.push('/dashboard')">
        返回首页
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.not-found {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-page);
}
.nf-card {
  text-align: center;
  padding: 40px;
}
.nf-code {
  font-size: 96px;
  font-weight: 900;
  background: linear-gradient(135deg, #2d6cdf 0%, #1f5fc4 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  line-height: 1;
}
h2 {
  margin: 12px 0 8px;
}
p {
  color: var(--text-secondary);
  margin-bottom: 22px;
}
</style>
