import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuthStore } from '../store/auth'

const routes = [
  { path: '/', redirect: '/activities' },
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
  { path: '/register', name: 'register', component: () => import('../views/Register.vue') },

  // ---------- 学生端 ----------
  {
    path: '/',
    component: () => import('../layouts/StudentLayout.vue'),
    children: [
      { path: 'activities', name: 'activities', component: () => import('../views/student/ActivityList.vue'), meta: { title: '浏览活动' } },
      { path: 'activities/:id', name: 'activityDetail', component: () => import('../views/student/ActivityDetail.vue'), meta: { title: '活动详情' } },
      { path: 'my', name: 'myRegistrations', component: () => import('../views/student/MyRegistrations.vue'), meta: { title: '我的报名', requiresAuth: true } },
    ],
  },

  // ---------- 管理端 ----------
  {
    path: '/admin',
    component: () => import('../layouts/AdminLayout.vue'),
    meta: { requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', name: 'dashboard', component: () => import('../views/admin/Dashboard.vue'), meta: { title: '概览' } },
      { path: 'activities', name: 'adminActivities', component: () => import('../views/admin/ActivityManage.vue'), meta: { title: '活动管理' } },
      { path: 'activities/new', name: 'activityNew', component: () => import('../views/admin/ActivityEdit.vue'), meta: { title: '新建活动' } },
      { path: 'activities/:id/edit', name: 'activityEdit', component: () => import('../views/admin/ActivityEdit.vue'), meta: { title: '编辑活动' } },
      { path: 'registrations', name: 'adminRegistrations', component: () => import('../views/admin/Registrations.vue'), meta: { title: '报名记录' } },
      { path: 'reports', name: 'reports', component: () => import('../views/admin/Reports.vue'), meta: { title: '报表导出' } },
      { path: 'ai', name: 'aiAnalysis', component: () => import('../views/admin/AiAnalysis.vue'), meta: { title: 'AI 分析' } },
      { path: 'users', name: 'users', component: () => import('../views/admin/Users.vue'), meta: { title: '账号管理' } },
    ],
  },

  { path: '/:pathMatch(.*)*', redirect: '/activities' },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return auth.isLoggedIn ? { name: 'activities' } : { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 校园社团活动报名` : '校园社团活动报名系统'
})

export default router
