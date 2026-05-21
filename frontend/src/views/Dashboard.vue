<template>
  <div class="dashboard">
    <h2>仪表盘</h2>

    <el-row :gutter="20" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: linear-gradient(135deg, #409eff, #337ecc);">
              <el-icon :size="24"><Monitor /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.switch_count }}</div>
              <div class="stat-title">活跃交换机</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: linear-gradient(135deg, #67c23a, #529b2e);">
              <el-icon :size="24"><Connection /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_ips }}</div>
              <div class="stat-title">唯一 IP 地址</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: linear-gradient(135deg, #e6a23c, #cf9236);">
              <el-icon :size="24"><Discount /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total_macs }}</div>
              <div class="stat-title">MAC 地址</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: linear-gradient(135deg, #f56c6c, #e06060);">
              <el-icon :size="24"><Grid /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.subnet_count }}</div>
              <div class="stat-title">管理子网</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="14">
        <el-card shadow="hover">
          <template #header><strong>地址段利用率</strong></template>
          <div v-if="subnets.length === 0" style="text-align:center;color:#909399;padding:60px 0;">
            暂无地址段数据，请先在「地址段管理」中添加地址段
          </div>
          <div v-else ref="chartRef" style="height: 350px;"></div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="hover">
          <template #header><strong>查询可用 IP</strong></template>
          <el-form label-width="80px">
            <el-form-item label="地址段">
              <el-select v-model="selectedSubnetId" placeholder="选择地址段" style="width: 100%"
                @change="fetchAvailableIps">
                <el-option v-for="s in subnets" :key="s.subnet_id"
                  :label="`${s.name} (${s.subnet_cidr})`" :value="s.subnet_id" />
              </el-select>
            </el-form-item>
          </el-form>
          <el-table :data="availableIps" max-height="280" v-loading="loadingIps" stripe>
            <el-table-column type="index" label="#" width="50" />
            <el-table-column prop="ip" label="IP 地址" />
          </el-table>
          <div v-if="availableIps.length === 0 && selectedSubnetId" style="text-align:center;color:#909399;padding:20px;">
            该地址段暂无可用 IP
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import api from '@/api'

const stats = reactive({
  switch_count: 0,
  total_ips: 0,
  total_macs: 0,
  subnet_count: 0,
})

const subnets = ref([])
const selectedSubnetId = ref(null)
const availableIps = ref([])
const loadingIps = ref(false)
const chartRef = ref(null)
let chartInstance = null

async function fetchStats() {
  try {
    const { data } = await api.get('/dashboard/stats')
    Object.assign(stats, data)
  } catch { /* handled by interceptor */ }
}

async function fetchUtilization() {
  try {
    const { data } = await api.get('/dashboard/subnet-utilization')
    subnets.value = data
    await nextTick()
    renderChart(data)
  } catch { /* handled by interceptor */ }
}

async function fetchAvailableIps() {
  if (!selectedSubnetId.value) return
  loadingIps.value = true
  try {
    const { data } = await api.get('/dashboard/available-ips', {
      params: { subnet_id: selectedSubnetId.value, limit: 100 }
    })
    availableIps.value = data.available_ips.map(ip => ({ ip }))
  } catch { /* handled by interceptor */ }
  finally { loadingIps.value = false }
}

function renderChart(data) {
  if (!chartRef.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }
  const names = data.map(d => d.name + '\n' + d.subnet_cidr)
  const used = data.map(d => d.used_ips)
  const free = data.map(d => d.free_ips)

  chartInstance.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: function (params) {
        const el = data[params[0].dataIndex]
        return `<b>${el.name}</b><br/>${el.subnet_cidr}<br/>
          已用: ${el.used_ips} / 可用: ${el.free_ips} / 总计: ${el.total_ips}<br/>
          利用率: ${el.utilization_pct}%`
      }
    },
    legend: { data: ['已用', '可用'] },
    grid: { left: '3%', right: '4%', bottom: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: names,
      axisLabel: { interval: 0, rotate: 30, fontSize: 11 },
    },
    yAxis: { type: 'value', name: 'IP 数量' },
    series: [
      { name: '已用', type: 'bar', stack: 'total', data: used, itemStyle: { color: '#f56c6c' } },
      { name: '可用', type: 'bar', stack: 'total', data: free, itemStyle: { color: '#67c23a' } },
    ],
  })
}

onMounted(() => {
  fetchStats()
  fetchUtilization()
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
.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 4px 0;
}
.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.stat-info {
  text-align: left;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  color: #303133;
  line-height: 1.2;
}
.stat-title {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
}
</style>
