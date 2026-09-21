<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>通知紀錄</h2>
        <div class="sub">最近 {{ list.length }} 筆 · 失敗 {{ failCount }} 筆</div>
      </div>
      <div class="tools">
        <el-radio-group v-model="only" size="default">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="fail">只看失敗</el-radio-button>
        </el-radio-group>
        <el-button icon="Refresh" @click="load">重新整理</el-button>
      </div>
    </div>
    <div class="card" style="padding:0">
      <el-table :data="shown" v-loading="loading">
        <el-table-column type="expand">
          <template #default="{ row }">
            <pre class="content">{{ row.content }}</pre>
            <div v-if="row.error" class="err">錯誤：{{ row.error }}</div>
          </template>
        </el-table-column>
        <el-table-column label="時間" width="170"><template #default="{ row }">{{ fmtTime(row.ts) }}</template></el-table-column>
        <el-table-column label="結果" width="80"><template #default="{ row }">
          <el-tag size="small" :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失敗' }}</el-tag></template></el-table-column>
        <el-table-column label="事件" width="100"><template #default="{ row }">{{ EVENT_LABEL[row.event] || row.event }}</template></el-table-column>
        <el-table-column label="管道" width="80"><template #default="{ row }">{{ row.channel === 'email' ? 'Email' : 'LINE' }}</template></el-table-column>
        <el-table-column label="收件人" min-width="160"><template #default="{ row }">{{ row.contact_name || row.target }}</template></el-table-column>
        <el-table-column label="監測項目" min-width="160"><template #default="{ row }">{{ row.monitor_name || '—' }}</template></el-table-column>
        <el-table-column label="錯誤" min-width="200" show-overflow-tooltip><template #default="{ row }"><span class="err">{{ row.error }}</span></template></el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http from '../api'
import { EVENT_LABEL, fmtTime } from '../utils'

const list = ref([])
const loading = ref(false)
const only = ref('')
const failCount = computed(() => list.value.filter((l) => !l.success).length)
const shown = computed(() => (only.value === 'fail' ? list.value.filter((l) => !l.success) : list.value))
async function load() {
  loading.value = true
  try { list.value = await http.get('/notification-logs') } finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.tools { display: flex; gap: 8px; }
.content { white-space: pre-wrap; margin: 0 20px 8px; font-family: inherit; }
.err { color: var(--sm-down); margin: 0 20px; }
</style>
