<template>
  <el-container class="layout">
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="logo">
        <span v-show="!isCollapse">IPAM</span>
        <span v-show="isCollapse">IP</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="isCollapse"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/switches">
          <el-icon><Monitor /></el-icon>
          <span>交换机管理</span>
        </el-menu-item>
        <el-menu-item index="/results">
          <el-icon><List /></el-icon>
          <span>扫描结果</span>
        </el-menu-item>
        <el-menu-item index="/routes">
          <el-icon><Connection /></el-icon>
          <span>路由表</span>
        </el-menu-item>
        <el-menu-item index="/subnets">
          <el-icon><Grid /></el-icon>
          <span>地址段管理</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Clock /></el-icon>
          <span>历史记录</span>
        </el-menu-item>
        <el-menu-item v-if="authStore.isAdmin" index="/users">
          <el-icon><UserFilled /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="navbar">
        <div class="navbar-left">
          <el-button text @click="isCollapse = !isCollapse">
            <el-icon :size="20"><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
          </el-button>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="pageTitle">{{ pageTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="navbar-right">
          <el-input v-model="searchText" placeholder="搜索 IP 或 MAC..." class="search-input" clearable
            @keyup.enter="handleSearch">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-dropdown trigger="click">
            <span class="user-info">
              <el-avatar :size="32" icon="UserFilled" />
              <span class="username">{{ authStore.user?.username }}</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="$router.push('/profile')">
                  <el-icon><Setting /></el-icon>个人设置
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main>
        <router-view v-slot="{ Component }">
          <transition name="fade-page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const isCollapse = ref(false)
const searchText = ref('')

const pageTitle = computed(() => {
  const titles = {
    '/dashboard': '仪表盘',
    '/switches': '交换机管理',
    '/results': '扫描结果',
    '/routes': '路由表',
    '/subnets': '地址段管理',
    '/history': '历史记录',
    '/users': '用户管理',
    '/profile': '个人设置',
    '/search': '搜索结果',
  }
  // 处理动态路由 /switches/:id
  const base = '/' + route.path.split('/')[1]
  return titles[route.path] || titles[base] || ''
})

function handleSearch() {
  const q = searchText.value.trim()
  if (q) {
    router.push({ path: '/search', query: { q } })
  }
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.layout {
  height: 100vh;
}
.sidebar {
  background-color: #304156;
  overflow-y: auto;
  transition: width 0.3s;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 20px;
  font-weight: bold;
  border-bottom: 1px solid rgba(255,255,255,0.1);
}
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 20px;
  gap: 16px;
}
.navbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.navbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.search-input {
  width: 280px;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.username {
  font-size: 14px;
  color: #303133;
}

/* 页面过渡动画 */
.fade-page-enter-active,
.fade-page-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.fade-page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}
.fade-page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
