<template>
  <div class="page-container" v-loading="loading">
    <div class="page-header">
      <h2 class="page-title"><el-icon><Tickets /></el-icon> 我的报名</h2>
    </div>

    <el-card v-if="items.length" shadow="never" class="list-card">
      <el-table :data="items" style="width: 100%">
        <el-table-column label="活动名称" min-width="200">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="$router.push(`/activities/${row.activity_id}`)">
              {{ row.activity_title }}
            </el-link>
          </template>
        </el-table-column>

        <el-table-column label="报名状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.registration_status === 'SIGNED' ? 'success' : 'info'" effect="light" round>
              {{ row.registration_status === 'SIGNED' ? '已报名' : '已取消' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="活动状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="activityStatus(row.activity_status).type" size="small">
              {{ activityStatus(row.activity_status).label }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="活动开始" width="180">
          <template #default="{ row }">{{ fmt(row.event_start_at) }}</template>
        </el-table-column>

        <el-table-column label="报名时间" width="180">
          <template #default="{ row }">{{ fmt(row.signed_at) }}</template>
        </el-table-column>

        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button v-if="row.registration_status === 'SIGNED'" type="danger" plain size="small"
              :loading="cancelingId === row.activity_id" @click="cancel(row)">
              取消报名
            </el-button>
            <el-button v-else text type="primary" size="small"
              @click="$router.push(`/activities/${row.activity_id}`)">
              重新报名
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-empty v-else-if="!loading" description="你还没有报名任何活动">
      <el-button type="primary" @click="$router.push('/activities')">去逛逛活动</el-button>
    </el-empty>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Tickets } from '@element-plus/icons-vue'
import { registrationApi } from '../../api'

const loading = ref(false)
const items = ref([])
const cancelingId = ref(null)

const fmt = (v) => (v ? v.replace('T', ' ').slice(0, 16) : '-')
const activityStatus = (s) =>
  ({ OPEN: { label: '报名中', type: 'success' }, CLOSED: { label: '已截止', type: 'info' }, FINISHED: { label: '已结束', type: 'warning' } }[s] || { label: s, type: 'info' })

async function load() {
  loading.value = true
  try {
    items.value = await registrationApi.my()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function cancel(row) {
  try {
    await ElMessageBox.confirm(`确定取消《${row.activity_title}》的报名吗？`, '取消报名', {
      type: 'warning',
      confirmButtonText: '确定取消',
      cancelButtonText: '再想想',
    })
  } catch { return }
  cancelingId.value = row.activity_id
  try {
    await registrationApi.cancel(row.activity_id)
    ElMessage.success('已取消报名')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    cancelingId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.list-card {
  border-radius: 10px;
}
</style>
