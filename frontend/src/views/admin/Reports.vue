<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <h2 class="page-title"><el-icon><Document /></el-icon> 报表导出</h2>
    </div>

    <el-card shadow="never" class="export-card">
      <div class="export-row">
        <el-select v-model="activityId" placeholder="请选择要导出报表的活动" clearable filterable
          style="width: 320px" :loading="activityLoading">
          <el-option v-for="a in activityOptions" :key="a.id" :label="a.title" :value="a.id" />
        </el-select>
        <el-button type="primary" :icon="Download" :disabled="!activityId" :loading="exporting" @click="doExport">
          生成并下载 CSV 报表
        </el-button>
      </div>
      <p class="hint">报表包含「活动信息 + 全部报名名单」，异步生成，大活动也不会阻塞请求。</p>
    </el-card>

    <el-card shadow="never" class="list-card">
      <template #header><b>我的导出任务</b></template>
      <el-table :data="tasks">
        <el-table-column label="ID" prop="id" width="70" align="center" />
        <el-table-column label="类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.task_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="活动" min-width="180">
          <template #default="{ row }">{{ row.activity_id ? `活动 #${row.activity_id}` : '-' }}</template>
        </el-table-column>
        <el-table-column label="进度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :status="progressStatus(row.status)"
              :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column label="结果" min-width="150">
          <template #default="{ row }">
            <template v-if="row.status === 'SUCCESS'">
              成功 {{ row.success_count }} 条<template v-if="row.fail_count"> / 失败 {{ row.fail_count }}</template>
            </template>
            <el-tag v-else-if="row.status === 'FAILED'" type="danger" size="small"
              :title="row.error_message || ''">失败</el-tag>
            <span v-else class="sub">{{ statusText(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="170">
          <template #default="{ row }">{{ fmt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" align="center">
          <template #default="{ row }">
            <el-button v-if="row.status === 'SUCCESS'" text type="primary" size="small"
              :icon="Download" @click="download(row)">下载</el-button>
            <el-button v-else-if="row.status === 'PENDING' || row.status === 'RUNNING'" text type="warning" size="small"
              @click="refresh">刷新</el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Document } from '@element-plus/icons-vue'
import { activityApi, taskApi, downloadBlob } from '../../api'

const loading = ref(false)
const activityLoading = ref(false)
const exporting = ref(false)
const activityId = ref(null)
const activityOptions = ref([])
const tasks = ref([])

const fmt = (v) => (v ? v.replace('T', ' ').slice(0, 16) : '-')
const statusText = (s) => ({ PENDING: '排队中', RUNNING: '生成中' }[s] || s)
const progressStatus = (s) => {
  if (s === 'SUCCESS') return 'success'
  if (s === 'FAILED') return 'exception'
  return undefined
}

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

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = await taskApi.listReports()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function doExport() {
  if (!activityId.value) return
  exporting.value = true
  try {
    const record = await taskApi.submitReport(activityId.value)
    ElMessage.success('任务已提交，正在生成报表…')
    loadTasks()
    // 后台轮询直至完成
    pollAndDownload(record.id)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    exporting.value = false
  }
}

async function pollAndDownload(recordId) {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms))
  for (let i = 0; i < 40; i++) {
    await wait(1500)
    const p = await taskApi.reportProgress(recordId)
    loadTasks()
    if (p.status === 'SUCCESS') {
      const blob = await taskApi.downloadReport(recordId)
      downloadBlob(blob, `活动报表_${recordId}.csv`)
      ElMessage.success('报表已生成并下载')
      return
    }
    if (p.status === 'FAILED') {
      ElMessage.error('报表生成失败')
      return
    }
  }
  ElMessage.warning('仍在生成中，可稍后在任务列表点击“刷新”查看进度并手动下载')
}

async function download(row) {
  try {
    const blob = await taskApi.downloadReport(row.id)
    downloadBlob(blob, `活动报表_${row.id}.csv`)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function refresh() {
  loadTasks()
}

onMounted(() => {
  loadActivities()
  loadTasks()
})
</script>

<style scoped>
.export-card {
  border-radius: 10px;
  margin-bottom: 16px;
}
.export-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.hint {
  color: #909399;
  font-size: 13px;
  margin: 12px 0 0;
}
.sub {
  color: #909399;
  font-size: 12px;
}
</style>
