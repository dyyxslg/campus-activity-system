<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <h2 class="page-title">{{ isEdit ? '编辑活动' : '新建活动' }}</h2>
      <el-button text type="primary" :icon="Back" @click="$router.push('/admin/activities')">返回列表</el-button>
    </div>

    <el-card shadow="never" class="form-card">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" v-loading="saving">
        <el-form-item label="活动名称" prop="title">
          <el-input v-model="form.title" placeholder="请输入活动名称" maxlength="100" show-word-limit />
        </el-form-item>

        <el-form-item label="报名人数上限" prop="max_participants">
          <el-input-number v-model="form.max_participants" :min="1" :max="100000" style="width: 200px" />
          <span class="tip">超出后系统将自动拒绝后续报名（Redis 锁防超报）</span>
        </el-form-item>

        <el-form-item label="报名时间" required>
          <div class="time-range">
            <el-date-picker v-model="form.signup_start_at" type="datetime" placeholder="开始"
              value-format="YYYY-MM-DD HH:mm:ss" :disabled-date="(t) => t < new Date(new Date().setDate(new Date().getDate() - 1))" />
            <span>至</span>
            <el-date-picker v-model="form.signup_end_at" type="datetime" placeholder="截止"
              value-format="YYYY-MM-DD HH:mm:ss" />
          </div>
        </el-form-item>

        <el-form-item label="活动时间" required>
          <div class="time-range">
            <el-date-picker v-model="form.event_start_at" type="datetime" placeholder="开始"
              value-format="YYYY-MM-DD HH:mm:ss" />
            <span>至</span>
            <el-date-picker v-model="form.event_end_at" type="datetime" placeholder="结束"
              value-format="YYYY-MM-DD HH:mm:ss" />
          </div>
        </el-form-item>

        <el-form-item label="活动介绍" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="6"
            placeholder="介绍活动内容、流程、注意事项等" maxlength="2000" show-word-limit />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="submit">{{ isEdit ? '保存修改' : '创建活动' }}</el-button>
          <el-button @click="$router.push('/admin/activities')">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back } from '@element-plus/icons-vue'
import { activityApi } from '../../api'

const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const activityId = Number(route.params.id)

const loading = ref(false)
const saving = ref(false)
const formRef = ref()

const form = reactive({
  title: '',
  max_participants: 50,
  signup_start_at: '',
  signup_end_at: '',
  event_start_at: '',
  event_end_at: '',
  description: '',
})

const rules = {
  title: [{ required: true, message: '请输入活动名称', trigger: 'blur' }],
  max_participants: [{ required: true, message: '请设置人数上限', trigger: 'change' }],
}

function fmt(v) {
  return v ? v.replace('T', ' ').slice(0, 19) : ''
}

async function load() {
  if (!isEdit.value) return
  loading.value = true
  try {
    const d = await activityApi.detail(activityId)
    form.title = d.title
    form.max_participants = d.max_participants
    form.signup_start_at = fmt(d.signup_start_at)
    form.signup_end_at = fmt(d.signup_end_at)
    form.event_start_at = fmt(d.event_start_at)
    form.event_end_at = fmt(d.event_end_at)
    form.description = d.description || ''
  } catch (e) {
    ElMessage.error(e.message)
    router.push('/admin/activities')
  } finally {
    loading.value = false
  }
}

async function submit() {
  await formRef.value.validate()

  const payload = { ...form }
  // 时间校验提示（与后端一致）
  const t = (v) => new Date(v.replace(' ', 'T')).getTime()
  if (t(payload.signup_start_at) >= t(payload.signup_end_at)) {
    return ElMessage.error('报名开始时间必须早于报名截止时间')
  }
  if (t(payload.signup_end_at) > t(payload.event_start_at)) {
    return ElMessage.error('报名截止时间应早于活动开始时间')
  }
  if (t(payload.event_start_at) >= t(payload.event_end_at)) {
    return ElMessage.error('活动开始时间必须早于活动结束时间')
  }

  saving.value = true
  try {
    if (isEdit.value) {
      await activityApi.update(activityId, payload)
      ElMessage.success('保存成功')
    } else {
      await activityApi.create(payload)
      ElMessage.success('创建成功，已保存为草稿')
    }
    router.push('/admin/activities')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.form-card {
  max-width: 720px;
  border-radius: 10px;
}
.time-range {
  display: flex;
  align-items: center;
  gap: 8px;
}
.tip {
  color: #909399;
  font-size: 12px;
  margin-left: 12px;
}
</style>
