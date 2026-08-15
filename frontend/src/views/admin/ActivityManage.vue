<template>
  <div v-loading="loading">
    <div class="toolbar">
      <el-input v-model="filters.keyword" placeholder="搜索活动名称" clearable :prefix-icon="Search"
        style="width: 240px" @keyup.enter="load" @clear="load" />
      <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 140px" @change="load">
        <el-option label="草稿" value="DRAFT" />
        <el-option label="报名中" value="OPEN" />
        <el-option label="已截止" value="CLOSED" />
        <el-option label="已结束" value="FINISHED" />
      </el-select>
      <el-checkbox v-model="filters.mine_only" @change="load">只看我创建</el-checkbox>
      <el-button type="primary" :icon="Plus" class="ml-auto" @click="$router.push('/admin/activities/new')">
        新建活动
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="items">
        <el-table-column label="活动名称" min-width="200">
          <template #default="{ row }">{{ row.title }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusMeta(row.status).type" effect="dark" round size="small">
              {{ statusMeta(row.status).label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="报名进度" width="130" align="center">
          <template #default="{ row }">
            <span :class="{ full: row.signed_count >= row.max_participants }">
              {{ row.signed_count }}/{{ row.max_participants }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="报名时间" width="230">
          <template #default="{ row }">
            {{ fmt(row.signup_start_at) }}<br /><span class="sub">~ {{ fmt(row.signup_end_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="330" align="center">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="$router.push(`/admin/activities/${row.id}/edit`)">编辑</el-button>
            <el-button text type="success" size="small" @click="viewList(row)">报名名单</el-button>
            <el-dropdown trigger="click" @command="(cmd) => onTransition(row, cmd)">
              <el-button text type="warning" size="small">状态流转<el-icon style="margin-left:2px"><ArrowDown /></el-icon></el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="t in transitions(row.status)" :key="t.to" :command="t.to">
                    {{ t.label }}
                  </el-dropdown-item>
                  <el-dropdown-item v-if="!transitions(row.status).length" disabled>无可用操作</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-button text type="danger" size="small" @click="remove(row)">删除</el-button>
          </template>
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, ArrowDown } from '@element-plus/icons-vue'
import { activityApi } from '../../api'

const router = useRouter()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const filters = reactive({ page: 1, page_size: 10, status: '', keyword: '', mine_only: false })

const statusMeta = (s) =>
  ({ DRAFT: { label: '草稿', type: 'info' }, OPEN: { label: '报名中', type: 'success' }, CLOSED: { label: '已截止', type: 'info' }, FINISHED: { label: '已结束', type: 'warning' } }[s] || { label: s, type: 'info' })
const fmt = (v) => (v ? v.replace('T', ' ').slice(0, 16) : '-')

function transitions(status) {
  const map = {
    DRAFT: [{ to: 'OPEN', label: '上架开放报名' }],
    OPEN: [
      { to: 'CLOSED', label: '截止报名' },
      { to: 'FINISHED', label: '结束活动' },
    ],
    CLOSED: [
      { to: 'OPEN', label: '重新开放' },
      { to: 'FINISHED', label: '结束活动' },
    ],
    FINISHED: [],
  }
  return map[status] || []
}

async function load() {
  loading.value = true
  try {
    const data = await activityApi.list({
      page: filters.page,
      page_size: filters.page_size,
      status: filters.status || undefined,
      keyword: filters.keyword || undefined,
      mine_only: filters.mine_only,
    })
    items.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

async function onTransition(row, to) {
  try {
    await ElMessageBox.confirm(`确认将《${row.title}》流转为「${statusMeta(to).label}」？`, '状态流转', {
      type: 'warning',
      confirmButtonText: '确认',
      cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await activityApi.transition(row.id, to)
    ElMessage.success('状态已更新')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function viewList(row) {
  router.push({ path: '/admin/registrations', query: { activity_id: row.id } })
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除《${row.title}》？仅草稿可删除，且不可恢复。`, '删除活动', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await activityApi.remove(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.ml-auto {
  margin-left: auto;
}
.full {
  color: #f56c6c;
  font-weight: 600;
}
.sub {
  color: #909399;
}
.pager {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
