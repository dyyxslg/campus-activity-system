<template>
  <div class="student-layout">
    <header class="site-header">
      <div class="brand" @click="$router.push('/activities')">
        <span class="brand-icon">🎓</span>
        <span class="brand-name">校园社团活动</span>
      </div>

      <nav class="nav">
        <el-menu mode="horizontal" :default-active="activeNav" router :ellipsis="false"
          class="nav-menu">
          <el-menu-item index="/activities">浏览活动</el-menu-item>
          <el-menu-item index="/my">我的报名</el-menu-item>
        </el-menu>
      </nav>

      <div class="user-area">
        <template v-if="auth.isLoggedIn">
          <el-dropdown @command="onUserCommand">
            <span class="user-trigger">
              <el-avatar :size="30" class="avatar">{{ auth.nickname.charAt(0) }}</el-avatar>
              <span class="nickname">{{ auth.nickname }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="my">我的报名</el-dropdown-item>
                <el-dropdown-item v-if="auth.isAdmin" command="admin">管理后台</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <el-button text type="primary" @click="$router.push('/login')">登录</el-button>
          <el-button type="primary" @click="$router.push('/register')">注册</el-button>
        </template>
      </div>
    </header>

    <main class="site-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const activeNav = computed(() => {
  if (route.path.startsWith('/my')) return '/my'
  return '/activities'
})

function onUserCommand(cmd) {
  if (cmd === 'logout') {
    auth.logout()
    ElMessage.success('已退出登录')
    router.push('/activities')
  } else if (cmd === 'my') {
    router.push('/my')
  } else if (cmd === 'admin') {
    router.push('/admin/dashboard')
  }
}
</script>

<style scoped>
.student-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.site-header {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 24px;
  height: 60px;
  padding: 0 24px;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
  box-shadow: 0 1px 6px rgba(0, 0, 0, 0.04);
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-weight: 700;
  font-size: 18px;
  color: #2563eb;
}
.brand-icon {
  font-size: 22px;
}
.nav {
  flex: 1;
}
.nav-menu {
  border-bottom: none;
}
.user-area {
  margin-left: auto;
}
.user-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #303133;
}
.avatar {
  background: #2563eb;
  color: #fff;
  font-weight: 600;
}
.nickname {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.site-main {
  flex: 1;
}
</style>
