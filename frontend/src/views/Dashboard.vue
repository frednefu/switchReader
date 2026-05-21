<template>
  <div class="dashboard">
    <h2>仪表盘</h2>
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="交换机" :value="stats.switch_count" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="IP 地址" :value="stats.total_ips" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="MAC 地址" :value="stats.total_macs" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <el-statistic title="子网" :value="stats.subnet_count" />
        </el-card>
      </el-col>
    </el-row>
    <el-empty description="更多功能即将上线" />
  </div>
</template>

<script setup>
import { reactive } from 'vue'

const stats = reactive({
  switch_count: 0,
  total_ips: 0,
  total_macs: 0,
  subnet_count: 0,
})
</script>

<style scoped>
.dashboard h2 {
  margin: 0 0 20px;
}
.stat-row {
  margin-bottom: 20px;
}
.stat-card {
  text-align: center;
}
</style>
