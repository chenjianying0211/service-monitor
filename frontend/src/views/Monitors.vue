<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>監測項目</h2>
        <div class="sub">共 {{ list.length }} 個 · 點名稱看詳細圖表與事件</div>
      </div>
      <div class="tools">
        <el-select v-model="hostFilter" placeholder="全部主機" clearable style="width:160px">
          <el-option label="未指定主機" :value="0" />
          <el-option v-for="h in hosts" :key="h.id" :label="h.name" :value="h.id" />
        </el-select>
        <el-input v-model="q" placeholder="搜尋" prefix-icon="Search" clearable style="width:200px" />
        <el-button type="primary" icon="Plus" @click="edit(null)">新增監測</el-button>
      </div>
    </div>

    <div class="cats">
      <button class="cat" :class="{ on: !cat }" @click="cat = ''">
        全部 <span class="cnt">{{ scoped.length }}</span>
      </button>
      <button v-for="c in catList" :key="c.key" class="cat" :class="{ on: cat === c.key }"
              @click="cat = cat === c.key ? '' : c.key">
        <el-icon><component :is="c.icon" /></el-icon>{{ c.label }}
        <span class="cnt">{{ c.n }}</span>
        <span v-if="c.down" class="down-dot" :title="`${c.down} 個異常`"></span>
      </button>
    </div>

    <div class="card" style="padding:0">
      <el-table :data="filtered" v-loading="loading" style="width:100%" row-key="id">
        <el-table-column label="狀態" width="100">
          <template #default="{ row }">
            <el-tag :type="STATUS[st(row)].tag" size="small" round>{{ STATUS[st(row)].label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="名稱" min-width="200">
          <template #default="{ row }">
            <router-link :to="`/monitors/${row.id}`"><b>{{ row.name }}</b></router-link>
            <div class="muted ellipsis mono" :title="row.target">{{ row.target }}</div>
          </template>
        </el-table-column>
        <el-table-column label="主機" width="130">
          <template #default="{ row }"><span v-if="row.host_id">{{ hostName(row.host_id) }}</span><span v-else class="muted">—</span></template>
        </el-table-column>
        <el-table-column label="類型" width="150">
          <template #default="{ row }">{{ TYPE_LABEL[row.type] }}</template>
        </el-table-column>
        <el-table-column label="標籤" width="140">
          <template #default="{ row }">
            <el-tag v-for="t in tagsOf(row)" :key="t" size="small" effect="plain" style="margin:2px">{{ t }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="間隔" width="90">
          <template #default="{ row }">{{ fmtDuration(row.interval_sec) }}</template>
        </el-table-column>
        <el-table-column label="通知群組" width="150">
          <template #default="{ row }">
            <span v-if="!row.groups.length" class="warn-text">⚠ 未設定</span>
            <el-tag v-for="g in row.groups" :key="g.group_id" size="small" type="info" style="margin:2px">{{ groupName(g.group_id) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最後檢查" min-width="200">
          <template #default="{ row }">
            <div>{{ fromNow(row.last_check_at) }}<span v-if="row.last_latency_ms != null" class="muted"> · {{ row.last_latency_ms }} ms</span></div>
            <div class="muted ellipsis" :title="row.last_message">{{ row.last_message }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-tooltip content="立即檢查"><el-button text circle icon="Refresh" @click="checkNow(row)" :loading="checking === row.id" /></el-tooltip>
            <el-tooltip :content="row.enabled ? '暫停' : '恢復'"><el-button text circle :icon="row.enabled ? 'VideoPause' : 'VideoPlay'" @click="toggle(row)" /></el-tooltip>
            <el-tooltip content="編輯"><el-button text circle icon="Edit" @click="edit(row)" /></el-tooltip>
            <el-tooltip content="刪除"><el-button text circle icon="Delete" type="danger" @click="remove(row)" /></el-tooltip>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <MonitorForm v-model="formOpen" :monitor="current" @saved="load" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api'
import MonitorForm from '../components/MonitorForm.vue'
import { CATEGORIES, STATUS, TYPE_LABEL, categoryOf, fmtDuration, fromNow } from '../utils'

const list = ref([])
const groups = ref([])
const hosts = ref([])
const hostFilter = ref('')
const loading = ref(false)
const q = ref('')
const cat = ref('')
const formOpen = ref(false)
const current = ref(null)
const checking = ref(null)

async function load() {
  loading.value = true
  try { [list.value, groups.value, hosts.value] = await Promise.all([http.get('/monitors'), http.get('/groups'), http.get('/hosts')]) } finally { loading.value = false }
}
onMounted(load)

const st = (r) => (r.enabled ? r.status : 'PAUSED')
const tagsOf = (r) => (r.tags || '').split(',').map((s) => s.trim()).filter(Boolean)
const hostName = (id) => hosts.value.find((h) => h.id === id)?.name || `#${id}`
const groupName = (id) => groups.value.find((g) => g.id === id)?.name || `#${id}`
// 先套用主機與搜尋，分類按鈕上的數字才會跟著變
const scoped = computed(() => {
  const kw = q.value.trim().toLowerCase()
  return list.value.filter((m) => (hostFilter.value == null || hostFilter.value === '' || (m.host_id || 0) === hostFilter.value)
    && (!kw || [m.name, m.target, m.tags].some((s) => (s || '').toLowerCase().includes(kw))))
})
const catList = computed(() => CATEGORIES.map((c) => {
  const items = scoped.value.filter((m) => categoryOf(m) === c.key)
  return { ...c, n: items.length, down: items.filter((m) => m.enabled && ['DOWN', 'PENDING'].includes(m.status)).length }
}).filter((c) => c.n || cat.value === c.key))
const filtered = computed(() => scoped.value.filter((m) => !cat.value || categoryOf(m) === cat.value))

function edit(row) { current.value = row; formOpen.value = true }
async function checkNow(row) {
  checking.value = row.id
  try { await http.post(`/monitors/${row.id}/check`); await load(); ElMessage.success('檢查完成') } finally { checking.value = null }
}
async function toggle(row) {
  const r = await http.post(`/monitors/${row.id}/toggle`)
  ElMessage.success(r.enabled ? '已恢復監測' : '已暫停監測')
  load()
}
async function remove(row) {
  await ElMessageBox.confirm(`確定刪除「${row.name}」？所有歷史紀錄也會一併刪除。`, '刪除監測', { type: 'warning', confirmButtonText: '刪除', cancelButtonText: '取消' })
  await http.delete(`/monitors/${row.id}`)
  ElMessage.success('已刪除')
  load()
}
</script>

<style scoped>
.tools { display: flex; gap: 8px; flex-wrap: wrap; }
.cats { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
.cat {
  display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 999px;
  border: 1px solid var(--sm-border); background: var(--sm-card); color: var(--el-text-color-primary);
  font: inherit; cursor: pointer; transition: all .15s; position: relative;
}
.cat:hover { border-color: var(--sm-accent); color: var(--sm-accent); }
.cat.on { background: var(--sm-accent); border-color: var(--sm-accent); color: #fff; }
.cnt { font-size: 12px; padding: 0 7px; border-radius: 999px; background: var(--sm-border); color: var(--sm-muted); font-variant-numeric: tabular-nums; }
.cat.on .cnt { background: rgba(255,255,255,.25); color: #fff; }
.down-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--sm-down); position: absolute; top: 2px; right: 2px; }
.warn-text { color: var(--sm-pending); font-size: 12.5px; }
</style>
