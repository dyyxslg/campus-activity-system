<template>
  <el-container class="admin-layout">
    <el-aside width="220px" class="aside">
      <div class="logo" @click="$router.push('/admin/dashboard')">
        <span>🎓</span> 活动管理后台
      </div>
      <el-menu :default-active="activePath" router class="side-menu">
        <el-menu-item index="/admin/dashboard">
          <el-icon><Odometer /></el-icon><span>数据概览</span>
        </el-menu-item>
        <el-menu-item index="/admin/activities">
          <el-icon><Calendar /></el-icon><span>活动管理</span>
        </el-menu-item>
        <el-menu-item index="/admin/registrations">
          <el-icon><Tickets /></el-icon><span>报名记录</span>
        </el-menu-item>
        <el-menu-item index="/admin/reports">
          <el-icon><Download /></el-icon><span>报表导出</span>
        </el-menu-item>
        <el-menu-item index="/admin/ai">
          <el-icon><MagicStick /></el-icon><span>AI 分析</span>
        </el-menu-item>
        <el-menu-item index="/admin/users">
          <el-icon><User /></el-icon><span>账号管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="crumb">{{ route.meta.title || '' }}</div>
        <div class="header-right">
          <el-button text type="primary" @click="$router.push('/activities')">
            <el-icon style="margin-right:4px"><HomeFilled /></el-icon>返回学生端
          </el-button>
          <el-dropdown @command="onCommand">
            <span class="user-trigger">
              <el-avatar :size="30" class="avatar">{{ auth.nickname.charAt(0) }}</el-avatar>
              <span class="nickname">{{ auth.nickname }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const activePath = computed(() => {
  const p = route.path
  if (p.startsWith('/admin/activities')) return '/admin/activities'
  return p
})

function onCommand(cmd) {
  if (cmd === 'logout') {
    auth.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}
</script>

<style scoped>
.admin-layout {
  height: 100vh;
}
.aside {
  background: #1f2937;
  color: #fff;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 60px;
  padding: 0 20px;
  font-weight: 700;
  font-size: 16px;
  color: #fff;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.side-menu {
  border-right: none;
  background: transparent;
  --el-menu-bg-color: transparent;
  --el-menu-text-color: #d1d5db;
  --el-menu-hover-bg-color: rgba(255, 255, 255, 0.08);
  --el-menu-active-color: #60a5fa;
}
.side-menu :deep(.el-menu-item.is-active) {
  background: rgba(96, 165, 250, 0.15);
  border-right: 3px solid #60a5fa;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  height: 60px;
}
.crumb {
  font-size: 16px;
  font-weight: 600;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.avatar {
  background: #1f2937;
  color: #fff;
}
.main {
  background: #f5f7fa;
}
</style>
