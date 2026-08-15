<template>
  <div v-loading="loading">
    <!-- 统计卡片 -->
    <el-row :gutter="16">
      <el-col :span="6" v-for="card in statCards" :key="card.label">
        <el-card shadow="hover" class="stat-card hover-card">
          <div class="stat-inner">
            <div class="stat-icon" :style="{ background: card.bg }">
              <el-icon :size="26" color="#fff"><component :is="card.icon" /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ card.value }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 状态分布 + 最近活动 -->
    <el-row :gutter="16" class="mt20">
      <el-col :span="10">
        <el-card shadow="never" class="panel">
          <template #header><b>活动状态分布</b></template>
          <el-table :data="statusRows" size="small">
            <el-table-column label="状态" prop="label" />
            <el-table-column label="数量" prop="count" align="center" width="120">
              <template #default="{ row }">
                <el-tag :type="row.type" size="small">{{ row.count }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-head">
              <b>最近创建的活动</b>
              <el-button text type="primary" size="small" @click="$router.push('/admin/activities')">全部活动</el-button>
            </div>
          </template>
          <el-table :data="recent" size="small">
            <el-table-column label="活动名称" min-width="180">
              <template #default="{ row }">
                <el-link type="primary" :underline="false" @click="$router.push(`/admin/activities/${row.id}/edit`)">
                  {{ row.title }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="报名进度" width="150" align="center">
              <template #default="{ row }">
                <span :class="{ 'full-text': row.signed_count >= row.max_participants }">
                  {{ row.signed_count }}/{{ row.max_participants }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { activityApi, registrationApi, userApi } from '../../api'
import { Tickets, User, Calendar, DataAnalysis } from '@element-plus/icons-vue'

const loading = ref(false)
const stats = ref({ activityTotal: 0, openTotal: 0, regTotal: 0, userTotal: 0 })
const activities = ref([])

const statusMeta = (s) =>
  ({ DRAFT: { label: '草稿', type: 'info' }, OPEN: { label: '报名中', type: 'success' }, CLOSED: { label: '已截止', type: 'info' }, FINISHED: { label: '已结束', type: 'warning' } }[s] || { label: s, type: 'info' })

const statCards = computed(() => [
  { label: '活动总数', value: stats.value.activityTotal, icon: Calendar, bg: '#2563eb' },
  { label: '报名中活动', value: stats.value.openTotal, icon: DataAnalysis, bg: '#059669' },
  { label: '报名记录数', value: stats.value.regTotal, icon: Tickets, bg: '#d97706' },
  { label: '注册用户数', value: stats.value.userTotal, icon: User, bg: '#7c3aed' },
])

const statusRows = computed(() =>
  ['DRAFT', 'OPEN', 'CLOSED', 'FINISHED']
    .map((s) => ({ ...statusMeta(s), status: s, count: activities.value.filter((a) => a.status === s).length }))
    .filter((r) => r.count > 0 || r.status === 'OPEN')
)

const recent = computed(() => activities.value.slice(0, 5))

async function load() {
  loading.value = true
  try {
    // 活动：拉全量（规模小，page_size=100 覆盖）
    const act = await activityApi.list({ page: 1, page_size: 100 })
    activities.value = act.items
    stats.value.activityTotal = act.total
    stats.value.openTotal = act.items.filter((a) => a.status === 'OPEN').length

    // 报名总数 / 用户总数：仅取 total
    const reg = await registrationApi.all({ page: 1, page_size: 1 })
    stats.value.regTotal = reg.total
    const usr = await userApi.list({ page: 1, page_size: 1 })
    stats.value.userTotal = usr.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.mt20 {
  margin-top: 16px;
}
.stat-card {
  border-radius: 10px;
}
.stat-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}
.stat-icon {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-label {
  color: #909399;
  font-size: 13px;
}
.panel {
  border-radius: 10px;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.full-text {
  color: #f56c6c;
  font-weight: 600;
}
</style>
