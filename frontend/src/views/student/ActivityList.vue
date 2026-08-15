<template>
  <div class="page-container">
    <div class="page-header">
      <h2 class="page-title"><el-icon><Compass /></el-icon> 浏览活动</h2>
      <div class="search-bar">
        <el-input v-model="filters.keyword" placeholder="搜索活动名称" clearable
          :prefix-icon="Search" style="width: 260px" @keyup.enter="load" @clear="load" />
        <el-button type="primary" :icon="Search" @click="load">搜索</el-button>
      </div>
    </div>

    <!-- 状态筛选 -->
    <el-radio-group v-model="filters.status" class="status-tabs" @change="load">
      <el-radio-button value="">全部</el-radio-button>
      <el-radio-button value="OPEN">报名中</el-radio-button>
      <el-radio-button value="CLOSED">已截止</el-radio-button>
      <el-radio-button value="FINISHED">已结束</el-radio-button>
    </el-radio-group>

    <!-- 活动卡片 -->
    <div v-loading="loading" class="card-grid">
      <el-card v-for="a in items" :key="a.id" class="activity-card hover-card" shadow="hover"
        @click="$router.push(`/activities/${a.id}`)">
        <div class="card-top">
          <span class="card-title">{{ a.title }}</span>
          <el-tag :type="statusMeta(a.status).type" size="small" effect="dark" round>
            {{ statusMeta(a.status).label }}
          </el-tag>
        </div>

        <div class="card-times">
          <p><el-icon><Clock /></el-icon> 报名 {{ fmt(a.signup_start_at) }} ~ {{ fmt(a.signup_end_at) }}</p>
          <p><el-icon><Calendar /></el-icon> 活动 {{ fmt(a.event_start_at) }} ~ {{ fmt(a.event_end_at) }}</p>
        </div>

        <div class="card-foot">
          <div class="capacity">
            <div class="capacity-text">
              <span>已报名</span>
              <b :class="{ full: a.signed_count >= a.max_participants }">
                {{ a.signed_count }}/{{ a.max_participants }}
              </b>
            </div>
            <el-progress :percentage="percent(a)" :stroke-width="8" :show-text="false"
              :color="a.signed_count >= a.max_participants ? '#f56c6c' : '#2563eb'" />
          </div>
          <el-button type="primary" plain size="small" class="view-btn">
            查看详情<el-icon style="margin-left:2px"><ArrowRight /></el-icon>
          </el-button>
        </div>
      </el-card>

      <el-empty v-if="!loading && !items.length" description="没有符合条件的活动" class="empty" />
    </div>

    <div class="pager">
      <el-pagination background layout="prev, pager, next, total"
        :total="total" :page-size="filters.page_size" :current-page="filters.page"
        @current-change="(p) => { filters.page = p; load() }" />
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Compass, Clock, Calendar, ArrowRight } from '@element-plus/icons-vue'
import { activityApi } from '../../api'

const loading = ref(false)
const items = ref([])
const total = ref(0)
const filters = reactive({ page: 1, page_size: 12, status: '', keyword: '' })

const STATUS_META = {
  DRAFT: { label: '草稿', type: 'info' },
  OPEN: { label: '报名中', type: 'success' },
  CLOSED: { label: '已截止', type: 'info' },
  FINISHED: { label: '已结束', type: 'warning' },
}
const statusMeta = (s) => STATUS_META[s] || { label: s, type: 'info' }
const fmt = (v) => (v ? v.replace('T', ' ').slice(0, 16) : '-')
const percent = (a) =>
  Math.round(Math.min((a.signed_count / a.max_participants) * 100, 100))

async function load() {
  loading.value = true
  try {
    const data = await activityApi.list({
      page: filters.page,
      page_size: filters.page_size,
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

onMounted(load)
</script>

<style scoped>
.search-bar {
  display: flex;
  gap: 8px;
}
.status-tabs {
  margin-bottom: 20px;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 16px;
  min-height: 200px;
}
.activity-card {
  cursor: pointer;
  border-radius: 10px;
  overflow: hidden;
}
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-times {
  margin: 12px 0;
  color: #909399;
  font-size: 13px;
}
.card-times p {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 4px 0;
}
.card-foot {
  border-top: 1px dashed #ebeef5;
  padding-top: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.capacity {
  flex: 1;
  margin-right: 12px;
}
.capacity-text {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}
.capacity-text b.full {
  color: #f56c6c;
}
.view-btn {
  flex-shrink: 0;
}
.empty {
  grid-column: 1 / -1;
}
.pager {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
</style>
