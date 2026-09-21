<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>服務總覽</h2>
        <div class="sub">每 15 秒自動更新 · 最後更新 {{ updated ? fmtTime(updated) : '—' }}</div>
      </div>
      <div class="tools">
        <el-radio-group v-model="groupBy">
          <el-radio-button value="host">依主機</el-radio-button>
          <el-radio-button value="tag">依標籤</el-radio-button>
        </el-radio-group>
        <el-input v-model="q" placeholder="搜尋名稱 / 目標 / 標籤" prefix-icon="Search" clearable style="width:220px" />
        <el-button type="primary" icon="Plus" @click="formOpen = true">新增監測</el-button>
      </div>
    </div>

    <div class="banner card" :class="overall.cls">
      <span class="dot pulse" :style="{ background: overall.color, color: overall.color }"></span>
      <div>
        <div class="banner-title">{{ overall.title }}</div>
        <div class="muted">{{ overall.sub }}</div>
      </div>
    </div>

    <div class="stats">
      <div v-for="s in statCards" :key="s.key" class="stat card" :class="{ on: filter === s.key }"
           @click="filter = filter === s.key ? '' : s.key">
        <div class="stat-label"><span class="dot" :style="{ background: s.color }"></span>{{ s.label }}</div>
        <div class="stat-num" :style="{ color: s.num ? s.color : '' }">{{ s.num }}</div>
      </div>
    </div>

    <el-skeleton v-if="loading && !data" :rows="6" animated />
    <el-empty v-else-if="data && !data.monitors.length" description="還沒有監測項目">
      <el-button type="primary" @click="formOpen = true">新增第一個監測</el-button>
    </el-empty>

    <template v-else-if="data">
      <div v-for="grp in grouped" :key="grp.key" class="section">
        <div v-if="grp.host" class="host-head card" :class="grpState(grp)">
          <span class="os">{{ (grp.host.os || '').toLowerCase().includes('win') ? '⊞' : '🐧' }}</span>
          <div class="host-info">
            <div class="host-name">{{ grp.host.name }}
              <span class="mono muted">{{ grp.host.ip }}</span></div>
            <div class="muted host-meta">
              <span v-if="grp.host.os">{{ grp.host.os }}</span>
              <span v-if="grp.host.region">{{ grp.host.region }}</span>
              <span v-if="grp.host.vm_size">{{ grp.host.vm_size }}</span>
              <span v-if="grp.host.resource_group">{{ grp.host.resource_group }}</span>
            </div>
          </div>
          <div class="host-sum">
            <span v-for="c in sumOf(grp.items)" :key="c.k" class="sum-chip"><span class="dot" :style="{ background: c.color }"></span>{{ c.n }}</span>
          </div>
        </div>
        <div v-else class="section-title">{{ grp.title }} <span class="muted">· {{ grp.items.length }}</span></div>
        <div class="grid">
          <router-link v-for="m in grp.items" :key="m.id" :to="`/monitors/${m.id}`" class="mon card" :class="m.status.toLowerCase()">
            <div class="mon-head">
              <span class="dot" :class="{ pulse: m.status === 'DOWN' }"
                    :style="{ background: STATUS[m.status].color, color: STATUS[m.status].color }"></span>
              <div class="mon-name ellipsis" :title="m.name">{{ m.name }}</div>
              <el-tag size="small" :type="STATUS[m.status].tag" effect="light" round>{{ STATUS[m.status].label }}</el-tag>
            </div>
            <div class="mon-sub ellipsis muted" :title="m.target">{{ TYPE_LABEL[m.type] }} · {{ m.target }}
              <template v-if="groupBy === 'host' && m.tags"> · {{ m.tags }}</template></div>
            <HeartbeatBar :beats="m.heartbeats" :slots="36" />
            <div class="mon-foot">
              <span class="ellipsis msg" :class="{ bad: m.status === 'DOWN' || m.status === 'PENDING' }" :title="m.last_message">
                {{ m.last_message || '等待第一次檢查…' }}
              </span>
              <span class="mono muted">{{ m.last_latency_ms != null ? `${m.last_latency_ms}ms` : '' }}</span>
            </div>
            <div class="uptimes">
              <div><span class="muted">24h</span><b class="uptime" :class="uptimeClass(m.uptime_24h)">{{ fmtPct(m.uptime_24h) }}</b></div>
              <div><span class="muted">7 天</span><b class="uptime" :class="uptimeClass(m.uptime_7d)">{{ fmtPct(m.uptime_7d) }}</b></div>
              <div><span class="muted">30 天</span><b class="uptime" :class="uptimeClass(m.uptime_30d)">{{ fmtPct(m.uptime_30d) }}</b></div>
            </div>
          </router-link>
        </div>
      </div>

      <div class="card recent">
        <div class="section-title" style="margin-bottom:8px">最近事件</div>
        <el-empty v-if="!data.recent_incidents.length" description="沒有中斷事件 🎉" :image-size="60" />
        <el-timeline v-else>
          <el-timeline-item v-for="i in data.recent_incidents" :key="i.id" :timestamp="fmtTime(i.started_at)"
                            :type="i.resolved_at ? 'success' : 'danger'" placement="top">
            <router-link :to="`/monitors/${i.monitor_id}`"><b>{{ i.monitor_name }}</b></router-link>
            <el-tag size="small" :type="i.resolved_at ? 'success' : 'danger'" style="margin-left:8px">
              {{ i.resolved_at ? `已恢復 · ${fromNow(i.resolved_at)}` : '進行中' }}
            </el-tag>
            <div class="muted" style="margin-top:4px">{{ i.cause }}</div>
          </el-timeline-item>
        </el-timeline>
      </div>
    </template>

    <MonitorForm v-model="formOpen" @saved="load" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import http from '../api'
import HeartbeatBar from '../components/HeartbeatBar.vue'
import MonitorForm from '../components/MonitorForm.vue'
import { STATUS, TYPE_LABEL, fmtPct, fmtTime, fromNow, uptimeClass } from '../utils'

const data = ref(null)
const loading = ref(false)
const updated = ref(null)
const q = ref('')
const filter = ref('')
const readGb = () => { try { return localStorage.getItem('sm_group_by') || 'host' } catch { return 'host' } }
const groupBy = ref(readGb())
watch(groupBy, (v) => { try { localStorage.setItem('sm_group_by', v) } catch { /* ignore */ } })
const formOpen = ref(false)

async function load() {
  loading.value = true
  try { data.value = await http.get('/dashboard', { silent: true }); updated.value = new Date() } finally { loading.value = false }
}
let timer
onMounted(() => { load(); timer = setInterval(load, 15000) })
onBeforeUnmount(() => clearInterval(timer))

const statCards = computed(() => {
  const c = data.value?.counts || {}
  return [
    { key: 'UP', label: '正常', num: c.UP || 0, color: 'var(--sm-up)' },
    { key: 'DOWN', label: '中斷', num: c.DOWN || 0, color: 'var(--sm-down)' },
    { key: 'PENDING', label: '異常中', num: c.PENDING || 0, color: 'var(--sm-pending)' },
    { key: 'PAUSED', label: '暫停 / 未檢查', num: (c.PAUSED || 0) + (c.UNKNOWN || 0), color: 'var(--sm-paused)' },
  ]
})

const overall = computed(() => {
  const c = data.value?.counts || {}
  if (c.DOWN) return { cls: 'down', color: 'var(--sm-down)', title: `${c.DOWN} 個服務中斷中`, sub: '已依設定發送通知，點擊卡片查看詳情' }
  if (c.PENDING) return { cls: 'pending', color: 'var(--sm-pending)', title: `${c.PENDING} 個服務檢查異常`, sub: '尚未達到告警門檻，持續觀察中' }
  return { cls: 'up', color: 'var(--sm-up)', title: '所有服務運作正常', sub: `共 ${data.value?.total ?? 0} 個監測項目` }
})

const order = { DOWN: 0, PENDING: 1, UNKNOWN: 2, UP: 3, PAUSED: 4 }
const grouped = computed(() => {
  const kw = q.value.trim().toLowerCase()
  const list = (data.value?.monitors || []).filter((m) => {
    if (filter.value && !(filter.value === 'PAUSED' ? ['PAUSED', 'UNKNOWN'].includes(m.status) : m.status === filter.value)) return false
    return !kw || [m.name, m.target, m.tags].some((s) => (s || '').toLowerCase().includes(kw))
  })
  const minOrder = (items) => Math.min(...items.map((m) => order[m.status]))
  const sortItems = (items) => items.sort((a, b) => order[a.status] - order[b.status] || a.name.localeCompare(b.name))
  const buckets = new Map()
  if (groupBy.value === 'host') {
    const hosts = data.value?.hosts || []
    for (const m of list) {
      const key = m.host_id && hosts.some((h) => h.id === m.host_id) ? m.host_id : 0
      if (!buckets.has(key)) buckets.set(key, [])
      buckets.get(key).push(m)
    }
    return [...buckets.entries()]
      .map(([key, items]) => {
        const host = hosts.find((h) => h.id === key)
        return { key: `h${key}`, host, title: '未指定主機', items: sortItems(items), sort: host ? host.sort_order : 1e9, name: host?.name || '~' }
      })
      .sort((a, b) => a.sort - b.sort || a.name.localeCompare(b.name))
  }
  for (const m of list) {
    const tag = (m.tags || '未分類').split(',')[0].trim() || '未分類'
    if (!buckets.has(tag)) buckets.set(tag, [])
    buckets.get(tag).push(m)
  }
  return [...buckets.entries()]
    .map(([tag, items]) => ({ key: `t${tag}`, title: tag, items: sortItems(items) }))
    .sort((a, b) => minOrder(a.items) - minOrder(b.items) || a.title.localeCompare(b.title))
})

const sumOf = (items) => [
  { k: 'UP', color: 'var(--sm-up)', n: items.filter((m) => m.status === 'UP').length },
  { k: 'DOWN', color: 'var(--sm-down)', n: items.filter((m) => m.status === 'DOWN').length },
  { k: 'PENDING', color: 'var(--sm-pending)', n: items.filter((m) => m.status === 'PENDING').length },
  { k: 'PAUSED', color: 'var(--sm-paused)', n: items.filter((m) => ['PAUSED', 'UNKNOWN'].includes(m.status)).length },
].filter((c) => c.n)
const grpState = (g) => (g.items.some((m) => m.status === 'DOWN') ? 'down' : g.items.some((m) => m.status === 'PENDING') ? 'pending' : 'up')
</script>

<style scoped>
.tools { display: flex; gap: 8px; flex-wrap: wrap; }
.banner { display: flex; align-items: center; gap: 14px; margin-bottom: 14px; border-left: 4px solid var(--sm-up); }
.banner.down { border-left-color: var(--sm-down); }
.banner.pending { border-left-color: var(--sm-pending); }
.banner .dot { width: 14px; height: 14px; }
.banner-title { font-size: 16px; font-weight: 650; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.stat { cursor: pointer; transition: border-color .15s; }
.stat:hover, .stat.on { border-color: var(--sm-accent); }
.stat-label { display: flex; align-items: center; gap: 8px; color: var(--sm-muted); font-size: 13px; }
.stat-num { font-size: 28px; font-weight: 700; margin-top: 4px; font-variant-numeric: tabular-nums; }
.section { margin-bottom: 20px; }
.section-title { font-weight: 650; margin-bottom: 10px; font-size: 15px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.mon { display: flex; flex-direction: column; gap: 10px; color: inherit; transition: transform .12s, box-shadow .12s; }
.mon:hover { transform: translateY(-2px); box-shadow: 0 8px 20px rgba(0,0,0,.08); }
.mon.down { border-color: color-mix(in srgb, var(--sm-down) 50%, var(--sm-border)); }
.mon-head { display: flex; align-items: center; gap: 10px; }
.mon-name { font-weight: 600; flex: 1; font-size: 15px; }
.mon-sub { font-size: 12.5px; margin-top: -4px; }
.mon-foot { display: flex; justify-content: space-between; gap: 10px; font-size: 12.5px; }
.msg { color: var(--sm-muted); }
.msg.bad { color: var(--sm-down); }
.uptimes { display: grid; grid-template-columns: repeat(3, 1fr); border-top: 1px solid var(--sm-border); padding-top: 8px; font-size: 12px; }
.uptimes div { display: flex; flex-direction: column; gap: 2px; }
.uptimes b { font-size: 14px; font-variant-numeric: tabular-nums; }
.recent { margin-top: 8px; }
.host-head { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; padding: 12px 16px; border-left: 4px solid var(--sm-up); }
.host-head.down { border-left-color: var(--sm-down); }
.host-head.pending { border-left-color: var(--sm-pending); }
.host-head .os { font-size: 22px; }
.host-info { flex: 1; min-width: 0; }
.host-name { font-weight: 650; font-size: 16px; display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.host-meta { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12.5px; margin-top: 2px; }
.host-sum { display: flex; gap: 12px; }
.sum-chip { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; font-variant-numeric: tabular-nums; }
@media (max-width: 720px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .grid { grid-template-columns: 1fr; }
}
</style>
