<template>
  <div class="page" v-if="m">
    <div class="page-head">
      <div>
        <el-button text icon="ArrowLeft" @click="$router.back()" style="margin-left:-12px">返回</el-button>
        <h2 class="title">
          <span class="dot" :class="{ pulse: st === 'DOWN' }" :style="{ background: STATUS[st].color, color: STATUS[st].color }"></span>
          {{ m.name }}
          <el-tag :type="STATUS[st].tag" round>{{ STATUS[st].label }}</el-tag>
        </h2>
        <div class="sub mono">{{ TYPE_LABEL[m.type] }} · {{ m.type === 'push' ? '外部回報' : m.target }}<span v-if="m.backend_url"> → {{ m.backend_url }}</span></div>
      </div>
      <div class="tools">
        <el-button icon="Refresh" @click="checkNow" :loading="checking">立即檢查</el-button>
        <el-button :icon="m.enabled ? 'VideoPause' : 'VideoPlay'" @click="toggle">{{ m.enabled ? '暫停' : '恢復' }}</el-button>
        <el-button type="primary" icon="Edit" @click="formOpen = true">編輯</el-button>
      </div>
    </div>

    <div class="kpis">
      <div class="card kpi"><div class="muted">目前回應</div><b>{{ m.last_latency_ms != null ? `${m.last_latency_ms} ms` : '—' }}</b></div>
      <div class="card kpi"><div class="muted">平均回應（{{ rangeLabel }}）</div><b>{{ avgLatency }}</b></div>
      <div class="card kpi"><div class="muted">可用率 24h</div><b class="uptime" :class="uptimeClass(m.uptime_24h)">{{ fmtPct(m.uptime_24h) }}</b></div>
      <div class="card kpi"><div class="muted">可用率 7 天</div><b class="uptime" :class="uptimeClass(m.uptime_7d)">{{ fmtPct(m.uptime_7d) }}</b></div>
      <div class="card kpi"><div class="muted">可用率 30 天</div><b class="uptime" :class="uptimeClass(m.uptime_30d)">{{ fmtPct(m.uptime_30d) }}</b></div>
    </div>

    <div v-if="m.type === 'push'" class="card" style="margin-bottom:14px">
      <b>回報網址與設定範例</b>
      <div class="muted" style="margin-top:4px">最後回報：{{ fmtTime(m.last_push_at) }}（{{ fromNow(m.last_push_at) }}）</div>
      <PushGuide :token="m.target" can-regenerate @regenerate="regenerate" />
    </div>

    <div class="card" style="margin-bottom:14px">
      <div class="row-head">
        <b>回應時間</b>
        <el-radio-group v-model="hours" size="small" @change="loadResults">
          <el-radio-button v-for="r in ranges" :key="r.h" :value="r.h">{{ r.label }}</el-radio-button>
        </el-radio-group>
      </div>
      <el-empty v-if="!results.length" description="尚無資料" :image-size="60" />
      <LatencyChart v-else :points="results" />
      <div class="muted" style="font-size:12px">紅色底色區段為檢查失敗期間。</div>
    </div>

    <el-row :gutter="14">
      <el-col :md="14" :xs="24">
        <div class="card">
          <b>中斷事件</b>
          <el-empty v-if="!incidents.length" description="沒有中斷紀錄 🎉" :image-size="60" />
          <el-timeline v-else style="margin-top:12px">
            <el-timeline-item v-for="i in incidents" :key="i.id" :type="i.resolved_at ? 'success' : 'danger'"
                              :timestamp="fmtTime(i.started_at)" placement="top">
              <el-tag size="small" :type="i.resolved_at ? 'success' : 'danger'">
                {{ i.resolved_at ? `已恢復，持續 ${fmtDuration(dur(i))}` : `進行中，已 ${fmtDuration(dur(i))}` }}
              </el-tag>
              <div style="margin-top:4px">{{ i.cause }}</div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </el-col>
      <el-col :md="10" :xs="24">
        <div class="card">
          <b>設定</b>
          <el-descriptions :column="1" size="small" border style="margin-top:12px">
            <el-descriptions-item :label="m.type === 'push' ? '預期回報間隔' : '檢查間隔'">{{ fmtDuration(m.interval_sec) }}</el-descriptions-item>
            <el-descriptions-item :label="m.type === 'push' ? '寬限' : '逾時'">{{ m.timeout_sec }} 秒</el-descriptions-item>
            <el-descriptions-item label="告警門檻">連續失敗 {{ m.retries }} 次</el-descriptions-item>
            <el-descriptions-item label="重複提醒">{{ m.resend_interval_min ? `每 ${m.resend_interval_min} 分鐘` : '不提醒' }}</el-descriptions-item>
            <el-descriptions-item v-if="['http','keyword','proxy_pair'].includes(m.type)" label="預期狀態碼">{{ m.expected_status }}</el-descriptions-item>
            <el-descriptions-item v-if="m.type === 'ssl_cert'" label="到期告警">≤ {{ m.ssl_warn_days }} 天</el-descriptions-item>
            <el-descriptions-item label="最後檢查">{{ fmtTime(m.last_check_at) }}</el-descriptions-item>
            <el-descriptions-item label="最後訊息">{{ m.last_message || '—' }}</el-descriptions-item>
            <el-descriptions-item v-if="m.description" label="說明">{{ m.description }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </el-col>
    </el-row>

    <MonitorForm v-model="formOpen" :monitor="m" @saved="loadAll" />
  </div>
  <div v-else class="page"><el-skeleton :rows="8" animated /></div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import http from '../api'
import LatencyChart from '../components/LatencyChart.vue'
import MonitorForm from '../components/MonitorForm.vue'
import PushGuide from '../components/PushGuide.vue'
import { STATUS, TYPE_LABEL, fmtDuration, fmtPct, fmtTime, fromNow, uptimeClass } from '../utils'

const route = useRoute()
const id = route.params.id
const m = ref(null)
const results = ref([])
const incidents = ref([])
const hours = ref(24)
const checking = ref(false)
const formOpen = ref(false)
const ranges = [{ h: 1, label: '1 小時' }, { h: 6, label: '6 小時' }, { h: 24, label: '24 小時' }, { h: 168, label: '7 天' }, { h: 720, label: '30 天' }]
const rangeLabel = computed(() => ranges.find((r) => r.h === hours.value)?.label)

const st = computed(() => (m.value.enabled ? m.value.status : 'PAUSED'))
const avgLatency = computed(() => {
  const v = results.value.filter((r) => r.ok && r.latency_ms != null)
  return v.length ? `${Math.round(v.reduce((a, b) => a + b.latency_ms, 0) / v.length)} ms` : '—'
})
const dur = (i) => dayjs(i.resolved_at || undefined).diff(dayjs(i.started_at), 'second')

const loadResults = async () => { results.value = await http.get(`/monitors/${id}/results`, { params: { hours: hours.value } }) }
async function loadAll() {
  const [a, , c] = await Promise.all([http.get(`/monitors/${id}`), loadResults(), http.get(`/monitors/${id}/incidents`)])
  m.value = a; incidents.value = c
}
async function checkNow() {
  checking.value = true
  try { await http.post(`/monitors/${id}/check`); await loadAll(); ElMessage.success('檢查完成') } finally { checking.value = false }
}
async function regenerate() {
  await ElMessageBox.confirm('重新產生後舊的回報網址立即失效，對方主機的腳本必須改用新網址。確定？', '重新產生回報網址',
    { type: 'warning', confirmButtonText: '重新產生', cancelButtonText: '取消' })
  await http.post(`/monitors/${id}/push-token`)
  ElMessage.success('已產生新的回報網址'); loadAll()
}
async function toggle() {
  const r = await http.post(`/monitors/${id}/toggle`)
  ElMessage.success(r.enabled ? '已恢復監測' : '已暫停監測')
  loadAll()
}
let timer
onMounted(() => { loadAll(); timer = setInterval(loadAll, 30000) })
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.title { display: flex; align-items: center; gap: 10px; }
.title .dot { width: 14px; height: 14px; }
.tools { display: flex; gap: 8px; flex-wrap: wrap; }
.kpis { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 14px; }
.kpi b { display: block; font-size: 22px; margin-top: 4px; font-variant-numeric: tabular-nums; }
.row-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px; }
.el-col { margin-bottom: 14px; }
@media (max-width: 900px) { .kpis { grid-template-columns: repeat(2, 1fr); } }
</style>
