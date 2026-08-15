<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <h2 class="page-title"><el-icon><DataAnalysis /></el-icon> AI 数据分析</h2>
    </div>

    <el-card shadow="never" class="select-card">
      <div class="select-row">
        <el-select v-model="activityId" placeholder="选择要分析的活动" clearable filterable
          style="width: 340px" :loading="activityLoading">
          <el-option v-for="a in activityOptions" :key="a.id"
            :label="`${a.title}（已报名 ${a.signed_count}/${a.max_participants}）`" :value="a.id" />
        </el-select>
        <el-button type="primary" :icon="MagicStick" :disabled="!activityId" :loading="running" @click="analyze">
          生成 AI 分析报告
        </el-button>
      </div>
      <p class="hint">基于报名数据生成智能分析报告：热度评估、规律总结、建议与展望。</p>
    </el-card>

    <el-card v-if="result" shadow="never" class="result-card">
      <template #header>
        <div class="result-head">
          <b>分析结果</b>
          <span class="sub">模型：{{ result.model }} · {{ fmt(result.created_at) }}</span>
        </div>
      </template>

      <div v-if="result.stats_json" class="stat-grid">
        <el-card v-for="card in statCards" :key="card.label" shadow="hover" class="mini-stat hover-card">
          <div class="mini-value" :title="card.value">{{ card.value }}</div>
          <div class="mini-label">{{ card.label }}</div>
        </el-card>
      </div>

      <div class="report-body">{{ result.report }}</div>
    </el-card>

    <el-empty v-else-if="!running && !loading" description="选择活动并点击「生成 AI 分析报告」，即可查看智能分析结果" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, DataAnalysis } from '@element-plus/icons-vue'
import { activityApi, taskApi } from '../../api'

const loading = ref(false)
const activityLoading = ref(false)
const running = ref(false)
const activityId = ref(null)
const activityOptions = ref([])
const result = ref(null)

const fmt = (v) => (v ? v.replace('T', ' ').slice(0, 16) : '-')

const statCards = computed(() => {
  const s = result.value?.stats_json || {}
  return [
    { label: '活动名称', value: s.activity_title || '-' },
    { label: '当前报名', value: s.current_signed ?? '-' },
    { label: '报名上限', value: s.capacity ?? '-' },
    { label: '累计取消', value: s.total_cancels ?? '-' },
    { label: '报名占用率', value: s.occupancy_rate != null ? `${Math.round(s.occupancy_rate * 100)}%` : '-' },
    { label: '报名高峰', value: s.peak_signup_hours?.length ? s.peak_signup_hours.join('时、') + '时' : '-' },
  ]
})

async function loadActivities() {
  activityLoading.value = true
  try {
    const data = await activityApi.list({ page: 1, page_size: 100 })
    activityOptions.value = data.items
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    activityLoading.value = false
  }
}

async function analyze() {
  if (!activityId.value) return
  running.value = true
  result.value = null
  try {
    await taskApi.submitAi(activityId.value)
    ElMessage.success('分析任务已提交，AI 正在生成报告…')
    await pollResult(activityId.value)
  } catch (e) {
    if (e.status === 400) {
      ElMessage.warning('当前环境未配置 AI 服务（AI_ENABLE=false），此为演示环境的预期行为。配置大模型 API 后即可使用。')
    } else {
      ElMessage.error(e.message)
    }
  } finally {
    running.value = false
  }
}

async function pollResult(id) {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms))
  for (let i = 0; i < 40; i++) {
    await wait(1500)
    try {
      const r = await taskApi.aiResult(id)
      result.value = r
      ElMessage.success('分析完成')
      return
    } catch (e) {
      // 404 = 尚未生成完成，继续等待；其余错误直接抛出
      if (e.status !== 404) throw e
    }
  }
  ElMessage.warning('分析耗时较长，可稍后重试')
}

onMounted(loadActivities)
</script>

<style scoped>
.select-card {
  border-radius: 10px;
  margin-bottom: 16px;
}
.select-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hint {
  color: #909399;
  font-size: 13px;
  margin: 12px 0 0;
}
.result-card {
  border-radius: 10px;
}
.result-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.sub {
  color: #909399;
  font-size: 12px;
}
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.mini-stat {
  border-radius: 8px;
  text-align: center;
  padding: 8px 0;
}
.mini-value {
  font-size: 22px;
  font-weight: 700;
  color: #2563eb;
}
.mini-label {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
.report-body {
  line-height: 1.9;
  white-space: pre-wrap;
  color: #303133;
  font-size: 14px;
  background: #f8fafc;
  border-radius: 10px;
  padding: 16px 20px;
}
</style>
