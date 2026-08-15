<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <h2 class="page-title"><el-icon><UserFilled /></el-icon> 账号管理</h2>
      <div class="search-bar">
        <el-input v-model="filters.keyword" placeholder="搜索用户名/昵称" clearable style="width: 200px"
          :prefix-icon="Search" @keyup.enter="load" @clear="load" />
        <el-select v-model="filters.role" placeholder="全部角色" clearable style="width: 120px" @change="load">
          <el-option label="学生" value="student" />
          <el-option label="管理员" value="admin" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="load">查询</el-button>
        <el-button type="primary" :icon="Plus" class="ml-auto" @click="createDialog = true">新建账号</el-button>
      </div>
    </div>

    <el-card shadow="never" class="list-card">
      <el-table :data="items">
        <el-table-column label="ID" prop="id" width="70" align="center" />
        <el-table-column label="用户名" prop="username" min-width="140" />
        <el-table-column label="昵称" prop="nickname" min-width="140">
          <template #default="{ row }">{{ row.nickname || '-' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.role === 'admin' ? 'warning' : 'primary'" effect="light" round size="small">
              {{ row.role === 'admin' ? '管理员' : '学生' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" effect="dark" round size="small">
              {{ row.is_active ? '正常' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="注册时间" width="180">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="280" align="center">
          <template #default="{ row }">
            <el-button v-if="!isSelf(row)" text type="primary" size="small" @click="openReset(row)">重置密码</el-button>
            <el-button v-if="!isSelf(row)" :text="true" :type="row.is_active ? 'danger' : 'success'" size="small"
              @click="toggleActive(row)">
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
            <el-button v-if="!isSelf(row)" text type="danger" size="small" @click="remove(row)">删除</el-button>
            <el-tag v-if="isSelf(row)" type="info" size="small">当前账号</el-tag>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination background layout="prev, pager, next, total"
          :total="total" :page-size="filters.page_size" :current-page="filters.page"
          @current-change="(p) => { filters.page = p; load() }" />
      </div>
    </el-card>

    <!-- 新建账号 -->
    <el-dialog v-model="createDialog" title="新建账号" width="440px">
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="3-50 位字符" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="createForm.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="createForm.nickname" placeholder="选填" />
        </el-form-item>
        <el-form-item label="角色" prop="role">
          <el-radio-group v-model="createForm.role">
            <el-radio value="student">学生</el-radio>
            <el-radio value="admin">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="createUser">创建</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码 -->
    <el-dialog v-model="resetDialog" title="重置密码" width="400px">
      <p class="reset-tip">正在为 <b>{{ resetTarget?.username }}</b> 重置密码</p>
      <el-input v-model="resetPassword" type="password" show-password placeholder="请输入新密码（至少 6 位）" />
      <template #footer>
        <el-button @click="resetDialog = false">取消</el-button>
        <el-button type="primary" :loading="resetting" @click="doReset">确定重置</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, UserFilled } from '@element-plus/icons-vue'
import { userApi } from '../../api'
import { useAuthStore } from '../../store/auth'

const auth = useAuthStore()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const filters = reactive({ page: 1, page_size: 20, keyword: '', role: '' })

const createDialog = ref(false)
const creating = ref(false)
const createFormRef = ref()
const createForm = reactive({ username: '', password: '', nickname: '', role: 'student' })
const createRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, min: 6, message: '密码至少 6 位', trigger: 'blur' }],
}

const resetDialog = ref(false)
const resetting = ref(false)
const resetTarget = ref(null)
const resetPassword = ref('')

const fmt = (v) => (v ? v.replace('T', ' ').slice(0, 16) : '-')
const isSelf = (row) => row.id === auth.user?.id

async function load() {
  loading.value = true
  try {
    const data = await userApi.list({
      page: filters.page,
      page_size: filters.page_size,
      keyword: filters.keyword || undefined,
      role: filters.role || undefined,
    })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function createUser() {
  await createFormRef.value.validate()
  creating.value = true
  try {
    await userApi.create({ ...createForm })
    ElMessage.success('账号创建成功')
    createDialog.value = false
    createForm.username = ''
    createForm.password = ''
    createForm.nickname = ''
    load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

function openReset(row) {
  resetTarget.value = row
  resetPassword.value = ''
  resetDialog.value = true
}

async function doReset() {
  if (!resetPassword.value || resetPassword.value.length < 6) {
    return ElMessage.warning('请输入至少 6 位的新密码')
  }
  resetting.value = true
  try {
    await userApi.resetPassword(resetTarget.value.id, resetPassword.value)
    ElMessage.success('密码已重置')
    resetDialog.value = false
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    resetting.value = false
  }
}

async function toggleActive(row) {
  const action = row.is_active ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(
      `确定${action}账号「${row.username}」？${row.is_active ? '禁用后该账号将无法登录和使用系统。' : ''}`,
      `${action}账号`,
      { type: 'warning', confirmButtonText: '确定', cancelButtonText: '取消' }
    )
  } catch { return }
  try {
    await userApi.setActive(row.id, !row.is_active)
    ElMessage.success(`已${action}`)
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除账号「${row.username}」？如该账号存在报名记录则无法删除。`,
      '删除账号',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch { return }
  try {
    await userApi.remove(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(load)
</script>

<style scoped>
.search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ml-auto {
  margin-left: auto;
}
.pager {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
.reset-tip {
  margin: 0 0 12px;
  color: #606266;
}
</style>
