<template>
  <div class="auth-page">
    <div class="auth-card hover-card">
      <div class="auth-title">
        <span class="auth-logo">🎓</span>
        <h2>校园社团活动报名系统</h2>
        <p>登录你的账号</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" size="large" @keyup.enter="submit">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" :prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码"
            :prefix-icon="Lock" show-password @keyup.enter="submit" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="submit-btn" :loading="loading" @click="submit">
            登 录
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        还没有账号？<el-link type="primary" @click="$router.push('/register')">立即注册</el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const formRef = ref()

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    const user = await auth.login(form.username, form.password)
    ElMessage.success(`欢迎回来，${user.nickname || user.username}`)
    // 管理员进后台，学生进活动页（优先回跳原目标）
    const target = user.role === 'admin' ? '/admin/dashboard' : route.query.redirect || '/activities'
    router.push(target)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  padding: 16px;
}
.auth-card {
  width: 400px;
  max-width: 100%;
  background: #fff;
  border-radius: 16px;
  padding: 40px 36px 28px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}
.auth-title {
  text-align: center;
  margin-bottom: 28px;
}
.auth-logo {
  font-size: 44px;
  display: block;
}
.auth-title h2 {
  margin: 8px 0 4px;
  font-size: 20px;
}
.auth-title p {
  margin: 0;
  color: #909399;
  font-size: 13px;
}
.submit-btn {
  width: 100%;
}
.auth-footer {
  text-align: center;
  color: #909399;
  font-size: 13px;
  margin-top: 8px;
}
</style>
