import { createRouter, createWebHistory } from 'vue-router'
import { auth } from './api'

const routes = [
  { path: '/login', component: () => import('./views/Login.vue'), meta: { public: true, bare: true } },
  { path: '/', component: () => import('./views/Dashboard.vue'), meta: { title: '總覽' } },
  { path: '/hosts', component: () => import('./views/Hosts.vue'), meta: { title: '主機' } },
  { path: '/monitors', component: () => import('./views/Monitors.vue'), meta: { title: '監測項目' } },
  { path: '/monitors/:id', component: () => import('./views/MonitorDetail.vue'), meta: { title: '監測詳情' } },
  { path: '/incidents', component: () => import('./views/Incidents.vue'), meta: { title: '中斷事件' } },
  { path: '/notifications', component: () => import('./views/Notifications.vue'), meta: { title: '通知設定' } },
  { path: '/logs', component: () => import('./views/Logs.vue'), meta: { title: '通知紀錄' } },
  { path: '/mcp-guide', component: () => import('./views/McpGuide.vue'), meta: { title: 'MCP 使用說明', public: true } },
  { path: '/settings', component: () => import('./views/Settings.vue'), meta: { title: '系統設定' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  if (!to.meta.public && !auth.token.value) return { path: '/login', query: { next: to.fullPath } }
  document.title = to.meta.title ? `${to.meta.title}｜服務監控平台` : '服務監控平台'
})

export default router
