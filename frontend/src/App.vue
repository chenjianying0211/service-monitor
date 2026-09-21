<template>
  <router-view v-if="route.meta.bare || (route.meta.public && !auth.token.value)" />
  <div v-else class="layout" :class="{ collapsed }">
    <aside class="side">
      <div class="brand">
        <svg viewBox="0 0 32 32" width="28" height="28"><circle cx="16" cy="16" r="14" fill="#22c55e" /><path d="M6 17h5l3-7 4 13 3-6h5" stroke="#fff" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" /></svg>
        <span v-show="!collapsed">服務監控平台</span>
      </div>
      <nav>
        <router-link v-for="n in nav" :key="n.to" :to="n.to" class="nav-item"
                     :class="{ active: isActive(n.to) }" :title="n.label" @click="mobileClose">
          <el-icon :size="18"><component :is="n.icon" /></el-icon>
          <span v-show="!collapsed">{{ n.label }}</span>
          <el-badge v-if="n.to === '/incidents' && openIncidents" v-show="!collapsed"
                    :value="openIncidents" class="nav-badge" />
        </router-link>
      </nav>
      <div class="side-foot" v-show="!collapsed">
        <span class="dot" :style="{ background: 'var(--sm-up)' }"></span> 監控運作中
      </div>
    </aside>
    <div class="main">
      <header class="top">
        <el-button text circle @click="collapsed = !collapsed"><el-icon :size="18"><Fold /></el-icon></el-button>
        <div class="crumb">{{ route.meta.title }}</div>
        <div class="grow"></div>
        <el-tooltip :content="dark ? '切換淺色' : '切換深色'">
          <el-button text circle @click="toggleDark">
            <el-icon :size="18"><component :is="dark ? 'Sunny' : 'Moon'" /></el-icon>
          </el-button>
        </el-tooltip>
        <el-dropdown @command="onCmd">
          <span class="user"><el-avatar :size="28">{{ (auth.username.value || '?')[0].toUpperCase() }}</el-avatar>
            <span class="uname">{{ auth.username.value }}</span></span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="settings" icon="Setting">系統設定</el-dropdown-item>
              <el-dropdown-item command="logout" icon="SwitchButton" divided>登出</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </header>
      <main><router-view :key="route.fullPath" /></main>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http, { auth } from './api'

const route = useRoute()
const router = useRouter()
const nav = [
  { to: '/', label: '總覽', icon: 'Odometer' },
  { to: '/hosts', label: '主機', icon: 'Platform' },
  { to: '/monitors', label: '監測項目', icon: 'Monitor' },
  { to: '/incidents', label: '中斷事件', icon: 'WarningFilled' },
  { to: '/notifications', label: '通知設定', icon: 'Bell' },
  { to: '/logs', label: '通知紀錄', icon: 'Document' },
  { to: '/mcp-guide', label: 'MCP 說明', icon: 'Connection' },
  { to: '/settings', label: '系統設定', icon: 'Setting' },
]
const isActive = (to) => (to === '/' ? route.path === '/' : route.path.startsWith(to))

const collapsed = ref(window.innerWidth < 900)
const mobileClose = () => { if (window.innerWidth < 900) collapsed.value = true }

const readPref = () => { try { return localStorage.getItem('sm_dark') } catch { return null } }
const dark = ref(readPref() ? readPref() === '1' : window.matchMedia('(prefers-color-scheme: dark)').matches)
const applyDark = () => document.documentElement.classList.toggle('dark', dark.value)
const toggleDark = () => {
  dark.value = !dark.value
  try { localStorage.setItem('sm_dark', dark.value ? '1' : '0') } catch { /* ignore */ }
  applyDark()
}
applyDark()

const openIncidents = ref(0)
let timer
async function poll() {
  if (!auth.token.value || route.meta.bare) return
  try {
    const list = await http.get('/incidents', { params: { only_open: true, limit: 100 }, silent: true })
    openIncidents.value = list.length
  } catch { /* ignore */ }
}
onMounted(() => { poll(); timer = setInterval(poll, 30000) })
onBeforeUnmount(() => clearInterval(timer))
watch(() => route.path, poll)

function onCmd(cmd) {
  if (cmd === 'logout') { auth.clear(); router.push('/login') }
  else router.push('/settings')
}
</script>

<style scoped>
.layout { display: flex; min-height: 100%; }
.side {
  width: 220px; flex-shrink: 0; background: var(--sm-side); color: var(--sm-side-text);
  display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh; transition: width .2s;
}
.collapsed .side { width: 64px; }
.brand { display: flex; align-items: center; gap: 10px; padding: 18px 18px 22px; font-weight: 700; font-size: 16px; color: #fff; white-space: nowrap; }
nav { display: flex; flex-direction: column; gap: 2px; padding: 0 10px; }
.nav-item {
  display: flex; align-items: center; gap: 12px; padding: 10px 12px; border-radius: 8px;
  color: var(--sm-side-text); white-space: nowrap; position: relative;
}
.nav-item:hover { background: rgba(255,255,255,.06); color: #fff; }
.nav-item.active { background: rgba(96,165,250,.16); color: #fff; }
.nav-item.active::before { content: ''; position: absolute; left: -10px; top: 8px; bottom: 8px; width: 3px; border-radius: 3px; background: #60a5fa; }
.nav-badge { margin-left: auto; }
.side-foot { margin-top: auto; padding: 16px 20px; font-size: 12px; display: flex; align-items: center; gap: 8px; opacity: .8; }
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.top {
  height: 56px; display: flex; align-items: center; gap: 8px; padding: 0 16px;
  background: var(--sm-card); border-bottom: 1px solid var(--sm-border); position: sticky; top: 0; z-index: 10;
}
.crumb { font-weight: 600; }
.grow { flex: 1; }
.user { display: flex; align-items: center; gap: 8px; cursor: pointer; outline: none; }
@media (max-width: 900px) {
  .side { position: fixed; z-index: 20; left: 0; }
  .collapsed .side { width: 0; overflow: hidden; }
  .uname { display: none; }
}
</style>
