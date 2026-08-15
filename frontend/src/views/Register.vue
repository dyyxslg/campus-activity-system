<template>
  <div class="auth-page">
    <div class="auth-card hover-card">
      <div class="auth-title">
        <span class="auth-logo">🎓</span>
        <h2>注册学生账号</h2>
        <p>加入校园社团活动</p>
      </div>

      <el-form :model="form" :rules="rules" ref="formRef" size="large">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名（3-50位）" :prefix-icon="User" clearable />
        </el-form-item>
        <el-form-item prop="nickname">
          <el-input v-model="form.nickname" placeholder="昵称（可选）" :prefix-icon="Avatar" clearable />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码（至少6位）"
            :prefix-icon="Lock" show-password />
        </el-form-item>
        <el-form-item prop="confirm">
          <el-input v-model="form.confirm" type="password" placeholder="确认密码"
            :prefix-icon="Lock" show-password @keyup.enter="submit" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="submit-btn" :loading="loading" @click="submit">
            注 册
          </el-button>
        </el-form-item>
      </el-form>

      <div class="auth-footer">
        已有账号？<el-link type="primary" @click="$router.push('/login')">去登录</el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Avatar } from '@element-plus/icons-vue'
import { useAuthStore } from '../store/auth'

const auth = useAuthStore()
const router = useRouter()
const formRef = ref()

const form = reactive({ username: '', nickname: '', password: '', confirm: '' })
const loading = ref(false)

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 50, message: '用户名长度 3-50 位', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_, v, cb) =>
        v === form.password ? cb() : cb(new Error('两次输入的密码不一致')),
      trigger: 'blur',
    },
  ],
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  try {
    await auth.register({
      username: form.username,
      nickname: form.nickname,
      password: form.password,
    })
    ElMessage.success('注册成功，请登录')
    router.push('/login')
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
