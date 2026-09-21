import axios from 'axios'
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

function read(key) {
  try { return localStorage.getItem(key) || '' } catch { return '' }
}
function write(key, val) {
  try { val ? localStorage.setItem(key, val) : localStorage.removeItem(key) } catch { /* ignore */ }
}

export const auth = {
  token: ref(read('sm_token')),
  username: ref(read('sm_user')),
  set(token, username) {
    this.token.value = token; this.username.value = username
    write('sm_token', token); write('sm_user', username)
  },
  clear() { this.set('', '') },
}

const http = axios.create({ baseURL: '/api', timeout: 60000 })

http.interceptors.request.use((cfg) => {
  if (auth.token.value) cfg.headers.Authorization = `Bearer ${auth.token.value}`
  return cfg
})

http.interceptors.response.use(
  (r) => r.data,
  (err) => {
    const status = err.response?.status
    let msg = err.response?.data?.detail || err.message
    if (Array.isArray(msg)) msg = msg.map((d) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join('；')
    if (status === 401 && !err.config.url.includes('/auth/login')) {
      auth.clear()
      if (location.pathname !== '/login') location.href = `/login?next=${encodeURIComponent(location.pathname)}`
    } else if (!err.config.silent) {
      ElMessage.error(msg)
    }
    return Promise.reject(new Error(msg))
  },
)

export default http
