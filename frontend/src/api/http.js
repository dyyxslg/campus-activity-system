import axios from 'axios'
import { ElMessage } from 'element-plus'

// 后端地址：本地开发直接跨域请求（后端已配置 CORS）
const http = axios.create({
  baseURL: 'http://127.0.0.1:8000/api/v1',
  timeout: 30000,
})

// 请求拦截：自动附带 JWT
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：统一取 data，失败提取后端 detail
http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    const msg =
      typeof detail === 'string'
        ? detail
        : detail?.map?.((d) => d.msg).join('; ') ||
          error.message ||
          '请求失败'

    if (status === 401) {
      // 登录态失效：清除并回到登录页
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      if (!location.hash.includes('/login')) {
        location.hash = '#/login'
      }
    }
    // 封装成带状态码的错误，方便页面按 400/403/429 做差异化提示
    const err = new Error(msg)
    err.status = status
    return Promise.reject(err)
  }
)

export default http
