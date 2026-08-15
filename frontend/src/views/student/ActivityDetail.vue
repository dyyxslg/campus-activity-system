<template>
  <div class="page-container" v-loading="loading">
    <div class="detail-wrap">
      <el-button text type="primary" :icon="ArrowLeft" class="back-btn" @click="$router.back()">
        返回列表
      </el-button>

      <el-card v-if="activity" class="detail-card" shadow="never">
        <div class="detail-head">
          <div>
            <h2 class="detail-title">{{ activity.title }}</h2>
            <div class="detail-meta">
              <el-tag :type="statusMeta.type" effect="dark" round>{{ statusMeta.label }}</el-tag>
              <span class="creator">创建于 {{ fmt(activity.created_at) }}</span>
            </div>
          </div>
          <el-tag v-if="isFull" type="danger" effect="plain" size="large">名额已满</el-tag>
        </div>

        <!-- 报名窗口与进度 -->
        <div class="signup-box">
          <div class="box-row">
            <span class="label">报名时间</span>
            <span>{{ fmt(activity.signup_start_at) }} ~ {{ fmt(activity.signup_end_at) }}</span>
          </div>
          <div class="box-row">
            <span class="label">活动时间</span>
            <span>{{ fmt(activity.event_start_at) }} ~ {{ fmt(activity.event_end_at) }}</span>
          </div>
          <div class="box-row">
            <span class="label">报名进度</span>
            <div class="progress-wrap">
              <el-progress :percentage="percent" :stroke-width="12"
                :color="isFull ? '#f56c6c' : '#2563eb'"
                :format="() => `${activity.signed_count}/${activity.max_participants}`" />
            </div>
          </div>
        </div>

        <div class="desc-box">
          <h4 class="desc-title">活动介绍</h4>
          <p class="desc-text">{{ activity.description || '暂无活动介绍' }}</p>
        </div>

        <!-- 报名操作 -->
        <div class="action-bar">
          <template v-if="myStatus === 'SIGNED'">
            <el-button type="success" disabled>✓ 已报名</el-button>
            <el-button type="danger" plain :loading="acting" @click="doCancel">取消报名</el-button>
          </template>
          <template v-else>
            <el-button type="primary" size="large" :disabled="!canSignup || isFull"
              :loading="acting" @click="doSignup">
              {{ actionHint }}
            </el-button>
            <span v-if="myStatus === 'CANCELED'" class="hint">（之前已取消，可重新报名）</span>
          </template>
        </div>
      </el-card>

      <el-empty v-else-if="!loading" description="活动不存在或无权查看" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'
import { activityApi, registrationApi } from '../../api'
import { useAuthStore } from '../../store/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const activityId = Number(route.params.id)

const loading = ref(false)
const acting = ref(false)
const activity = ref(null)
const myStatus = ref(null) // null 未报名 / SIGNED / CANCELED

const STATUS_META = {
  DRAFT: { label: '草稿', type: 'info' },
  OPEN: { label: '报名中', type: 'success' },
  CLOSED: { label: '已截止', type: 'info' },
  FINISHED: { label: '已结束', type: 'warning' },
}
const statusMeta = computed(() => STATUS_META[activity.value?.status] || { label: activity.value?.status, type: 'info' })
const fmt = (v) => (v ? v.replace('T', ' ').slice(0, 16) : '-')
const percent = computed(() =>
  activity.value ? Math.round(Math.min((activity.value.signed_count / activity.value.max_participants) * 100, 100)) : 0
)
const isFull = computed(() => activity.value && activity.value.signed_count >= activity.value.max_participants)

const canSignup = computed(() => {
  if (!activity.value) return false
  const now = new Date()
  return (
    activity.value.status === 'OPEN' &&
    now >= new Date(activity.value.signup_start_at) &&
    now <= new Date(activity.value.signup_end_at) &&
    !isFull.value
  )
})

const actionHint = computed(() => {
  if (!activity.value) return ''
  if (isFull.value) return '名额已满'
  if (activity.value.status !== 'OPEN') return '当前不可报名'
  if (myStatus.value === 'CANCELED') return '重新报名'
  return '立即报名'
})

async function load() {
  loading.value = true
  try {
    activity.value = await activityApi.detail(activityId)
    if (auth.isLoggedIn) {
      try {
        const s = await registrationApi.myStatus(activityId)
        myStatus.value = s.status || null
      } catch { /* 未登录场景忽略 */ }
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function doSignup() {
  if (!auth.isLoggedIn) {
    ElMessage.warning('请先登录再报名')
    router.push({ name: 'login', query: { redirect: route.fullPath } })
    return
  }
  acting.value = true
  try {
    const r = await registrationApi.signup(activityId)
    myStatus.value = 'SIGNED'
    activity.value.signed_count = r.signed_count
    ElMessage.success('报名成功！')
  } catch (e) {
    ElMessage.error(e.message)
    if (e.status === 400) load() // 名额/状态变化时刷新最新数据
  } finally {
    acting.value = false
  }
}

async function doCancel() {
  try {
    await ElMessageBox.confirm('确定要取消报名吗？名额将立即释放。', '取消报名', {
      type: 'warning',
      confirmButtonText: '确定取消',
      cancelButtonText: '再想想',
    })
  } catch { return }
  acting.value = true
  try {
    const r = await registrationApi.cancel(activityId)
    myStatus.value = 'CANCELED'
    activity.value.signed_count = r.signed_count
    ElMessage.success('已取消报名')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    acting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.detail-wrap {
  max-width: 860px;
  margin: 0 auto;
}
.back-btn {
  margin-bottom: 12px;
}
.detail-card {
  border-radius: 12px;
  padding: 8px 12px;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f2f5;
}
.detail-title {
  margin: 0 0 10px;
  font-size: 24px;
  font-weight: 700;
}
.detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}
.creator {
  color: #909399;
  font-size: 13px;
}
.signup-box {
  background: #f8fafc;
  border-radius: 10px;
  padding: 18px 20px;
  margin: 20px 0;
}
.box-row {
  display: flex;
  align-items: center;
  margin: 8px 0;
  font-size: 14px;
}
.box-row .label {
  width: 90px;
  color: #909399;
  flex-shrink: 0;
}
.progress-wrap {
  flex: 1;
  display: flex;
  align-items: center;
}
.progress-wrap :deep(.el-progress) {
  width: 100%;
}
.desc-box {
  margin-top: 8px;
}
.desc-title {
  margin: 0 0 8px;
  font-size: 15px;
}
.desc-text {
  color: #606266;
  line-height: 1.8;
  white-space: pre-wrap;
  margin: 0;
}
.action-bar {
  margin-top: 24px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-top: 1px solid #f0f2f5;
  padding-top: 20px;
}
.hint {
  color: #909399;
  font-size: 13px;
}
</style>
