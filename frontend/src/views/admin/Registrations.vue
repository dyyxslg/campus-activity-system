<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <h2 class="page-title"><el-icon><Tickets /></el-icon> 报名记录总览</h2>
      <div class="search-bar">
        <el-select v-model="filters.activity_id" placeholder="全部活动" clearable filterable style="width: 200px"
          :loading="activityLoading" @change="load">
          <el-option v-for="a in activityOptions" :key="a.id" :label="a.title" :value="a.id" />
        </el-select>
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 130px" @change="load">
          <el-option label="已报名" value="SIGNED" />
          <el-option label="已取消" value="CANCELED" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索用户名/昵称" clearable style="width: 200px"
          :prefix-icon="Search" @keyup.enter="load" @clear="load" />
        <el-button type="primary" :icon="Search" @click="load">查询</el-button>
        <el-button text type="primary" :icon="Download" v-if="filters.activity_id" @click="exportCsv">
          导出该活动报表
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="list-card">
      <el-table :data="items">
        <el-table-column label="活动名称" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="$router.push(`/activities/${row.activity_id}`)">
              {{ row.activity_title }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column label="学生" min-width="140">
          <template #default="{ row }">
            {{ row.nickname || row.username }}
            <span class="sub">(@{{ row.username }})</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'SIGNED' ? 'success' : 'info'" round>
              {{ row.status === 'SIGNED' ? '已报名' : '已取消' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="报名时间" width="180">
          <template #default="{ row }">{{ fmt(row.signed_at) }}</template>
        </el-table-column>
        <el-table-column label="取消时间" width="180">
          <template #default="{ row }">{{ row.canceled_at ? fmt(row.canceled_at) : '-' }}</template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination background layout="prev, pager, next, total"
          :total="total" :page-size="filters.page_size" :current-page="filters.page"
          @current-change="(p) => { filters.page = p; load() }" />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, Download, Tickets } from '@element-plus/icons-vue'
import { activityApi, registrationApi, taskApi, downloadBlob } from '../../api'

const route = useRoute()
const loading = ref(false)
const activityLoading = ref(false)
const items = ref([])
const total = ref(0)
const activityOptions = ref([])
const filters = reactive({
  page: 1,
  page_size: 20,
  activity_id: route.query.activity_id ? Number(route.query.activity_id) : null,
  status: '',
  keyword: '',
})

const fmt = (v) => (v ? v.replace('T', ' ').slice(0, 16) : '-')

async function loadActivities() {
  activityLoading.value = true
  try {
    const data = await activityApi.list({ page: 1, page_size: 100 })
    activityOptions.value = data.items
  } catch { /* 下拉加载失败不影响列表 */ } finally {
    activityLoading.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const data = await registrationApi.all({
      page: filters.page,
      page_size: filters.page_size,
      activity_id: filters.activity_id || undefined,
      status: filters.status || undefined,
      keyword: filters.keyword || undefined,
    })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function exportCsv() {
  try {
    // 提交报表任务并轮询进度，完成后下载
    const record = await taskApi.submitReport(filters.activity_id)
    ElMessage.info('报表生成中，请稍候…')
    const progress = await pollProgress(record.id)
    if (!progress) return
    const blob = await taskApi.downloadReport(record.id)
    const name = `活动报表_${filters.activity_id}_${Date.now()}.csv`
    downloadBlob(blob, name)
    ElMessage.success('报表已下载')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function pollProgress(recordId) {
  // 最长等待 60s，每 1.5s 轮询一次
  const wait = (ms) => new Promise((r) => setTimeout(r, ms))
  for (let i = 0; i < 40; i++) {
    await wait(1500)
    const p = await taskApi.reportProgress(recordId)
    if (p.status === 'SUCCESS') return true
    if (p.status === 'FAILED') {
      ElMessage.error('报表生成失败，请稍后重试')
      return false
    }
  }
  ElMessage.warning('生成超时，请到“报表导出”页查看任务状态')
  return false
}

onMounted(() => {
  loadActivities()
  load()
})
</script>

<style scoped>
.search-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.sub {
  color: #909399;
  font-size: 12px;
}
.pager {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
