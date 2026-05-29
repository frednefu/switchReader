<template>
  <div class="org-page">
    <div class="page-header">
      <div class="header-left">
        <h2>组织机构管理</h2>
        <el-switch
          v-model="showAll"
          active-text="显示全部部门"
          inactive-text="仅显示有账号部门"
          @change="loadTree"
        />
      </div>
      <div class="header-right">
        <el-input
          v-model="treeFilter"
          placeholder="搜索部门..."
          :prefix-icon="Search"
          clearable
          style="width: 220px"
          @input="filterTree"
        />
        <el-button type="primary" :loading="syncing" @click="handleSync">同步组织机构</el-button>
        <el-button :icon="Refresh" circle @click="loadTree" />
      </div>
    </div>

    <div class="org-content">
      <div class="tree-panel">
        <el-tree
          ref="treeRef"
          :data="displayTree"
          :props="treeProps"
          node-key="id"
          default-expand-all
          highlight-current
          :expand-on-click-node="true"
          :filter-node-method="filterNode"
          @node-click="handleNodeClick"
        >
          <template #default="{ node, data }">
            <span class="tree-node">
              <el-icon><OfficeBuilding /></el-icon>
              <span class="node-label">{{ data.dwmc || data.dwjc || data.dwbm }}</span>
              <el-badge
                v-show="data.user_count > 0 || showAll"
                :value="data.user_count"
                :type="data.user_count > 0 ? 'primary' : 'info'"
                class="node-badge"
              />
            </span>
          </template>
        </el-tree>
      </div>

      <div class="detail-panel">
        <template v-if="selectedDept">
          <div class="detail-header">
            <h3>{{ selectedDept.dwmc || selectedDept.dwjc }}</h3>
            <span class="detail-code">编码：{{ selectedDept.dwbm }}</span>
          </div>
          <el-table :data="deptUsers" stripe v-loading="usersLoading" empty-text="该部门暂无账号" size="small">
            <el-table-column prop="gh" label="工号" width="110" />
            <el-table-column prop="name" label="姓名" width="80" />
            <el-table-column prop="gender" label="性别" width="55" />
            <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip />
            <el-table-column prop="phone" label="办公电话" width="120" />
            <el-table-column prop="mobile" label="移动电话" width="120" />
            <el-table-column prop="role" label="角色" width="70">
              <template #default="{ row }">
                <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'" size="small">
                  {{ row.role === 'admin' ? '管理员' : '用户' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="状态" width="70">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
                  {{ row.is_active ? '启用' : '禁用' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else description="请选择左侧部门查看账号" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, OfficeBuilding } from '@element-plus/icons-vue'
import { syncDepartments, getDepartmentTree, getDepartmentUsers } from '@/api/departments'

const treeRef = ref(null)
const showAll = ref(false)
const treeFilter = ref('')
const syncing = ref(false)
const usersLoading = ref(false)
const treeData = ref([])
const displayTree = ref([])
const selectedDept = ref(null)
const deptUsers = ref([])
const treeProps = { children: 'children', label: 'dwmc' }

async function loadTree() {
  try {
    treeData.value = await getDepartmentTree(showAll.value)
    displayTree.value = treeData.value
    if (treeFilter.value) {
      filterTree()
    }
  } catch (e) {
    ElMessage.error('加载组织机构失败')
  }
}

function filterNode(value, data) {
  if (!value) return true
  const kw = value.toLowerCase()
  return (
    (data.dwmc && data.dwmc.toLowerCase().includes(kw)) ||
    (data.dwjc && data.dwjc.toLowerCase().includes(kw)) ||
    (data.dwbm && data.dwbm.toLowerCase().includes(kw))
  )
}

function filterTree() {
  treeRef.value?.filter(treeFilter.value)
}

async function handleNodeClick(data) {
  selectedDept.value = data
  await loadDeptUsers(data.id)
}

async function loadDeptUsers(deptId) {
  usersLoading.value = true
  try {
    deptUsers.value = await getDepartmentUsers(deptId)
  } catch (e) {
    deptUsers.value = []
    ElMessage.error('加载部门用户失败')
  } finally {
    usersLoading.value = false
  }
}

async function handleSync() {
  syncing.value = true
  try {
    const res = await syncDepartments()
    ElMessage.success(`同步完成：共 ${res.total} 个单位，新增 ${res.created}，更新 ${res.updated}`)
    await loadTree()
  } catch (e) {
    ElMessage.error('同步组织机构失败')
  } finally {
    syncing.value = false
  }
}

onMounted(loadTree)
</script>

<style scoped>
.org-page {
  padding: 20px;
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 10px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 20px;
}
.header-left h2 {
  margin: 0;
  font-size: 20px;
  white-space: nowrap;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}
.org-content {
  display: flex;
  gap: 16px;
  flex: 1;
  overflow: hidden;
}
.tree-panel {
  width: 320px;
  flex-shrink: 0;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 12px;
  overflow-y: auto;
  background: #fff;
}
.detail-panel {
  flex: 1;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 16px;
  overflow-y: auto;
  background: #fff;
}
.detail-header {
  margin-bottom: 14px;
}
.detail-header h3 {
  margin: 0 0 4px 0;
  font-size: 17px;
}
.detail-code {
  color: #909399;
  font-size: 12px;
}
.tree-node {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
}
.node-label {
  flex: 1;
}
.node-badge {
  margin-left: auto;
}
</style>
