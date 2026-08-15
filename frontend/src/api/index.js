// 后端接口封装：全部通过统一 http 实例（自动带 token / 统一错误）
import http from './http'

export const authApi = {
  register: (data) => http.post('/auth/register', data),
  login: (data) => http.post('/auth/login', data),
  me: () => http.get('/auth/me'),
}

export const activityApi = {
  list: (params) => http.get('/activities', { params }),
  detail: (id) => http.get(`/activities/${id}`),
  create: (data) => http.post('/activities', data),
  update: (id, data) => http.put(`/activities/${id}`, data),
  transition: (id, target_status) => http.post(`/activities/${id}/status`, { target_status }),
  remove: (id) => http.delete(`/activities/${id}`),
}

export const registrationApi = {
  signup: (activityId) => http.post(`/registrations/${activityId}`),
  cancel: (activityId) => http.delete(`/registrations/${activityId}`),
  my: () => http.get('/registrations/my'),
  myStatus: (activityId) => http.get(`/registrations/${activityId}/status`),
  activityList: (activityId, params) =>
    http.get(`/registrations/activity/${activityId}`, { params }),
  all: (params) => http.get('/registrations', { params }),
}

export const taskApi = {
  submitReport: (activityId) => http.post(`/tasks/reports/${activityId}`),
  reportProgress: (recordId) => http.get(`/tasks/reports/${recordId}/progress`),
  downloadReport: (recordId) =>
    http.get(`/tasks/reports/${recordId}/download`, { responseType: 'blob' }),
  listReports: (params) => http.get('/tasks/reports', { params }),
  submitAi: (activityId) => http.post(`/tasks/ai/${activityId}`),
  aiResult: (activityId) => http.get(`/tasks/ai/${activityId}/result`),
}

export const userApi = {
  list: (params) => http.get('/admin/users', { params }),
  create: (data) => http.post('/admin/users', data),
  resetPassword: (id, new_password) => http.put(`/admin/users/${id}/password`, { new_password }),
  setActive: (id, is_active) => http.put(`/admin/users/${id}/active`, { is_active }),
  remove: (id) => http.delete(`/admin/users/${id}`),
}

// 工具：解析后端返回的报表 Blob 并触发下载
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
