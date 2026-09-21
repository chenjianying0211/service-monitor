<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>中斷事件</h2>
        <div class="sub">進行中 {{ openCount }} 件 · 共 {{ list.length }} 筆</div>
      </div>
      <div class="tools">
        <el-radio-group v-model="onlyOpen" @change="load">
          <el-radio-button :value="false">全部</el-radio-button>
          <el-radio-button :value="true">只看進行中</el-radio-button>
        </el-radio-group>
        <el-button icon="Refresh" @click="load">重新整理</el-button>
      </div>
    </div>
    <div class="card" style="padding:0">
      <el-table :data="list" v-loading="loading">
        <el-table-column label="狀態" width="100">
          <template #default="{ row }">
            <el-tag :type="row.resolved_at ? 'success' : 'danger'" size="small" round>{{ row.resolved_at ? '已恢復' : '進行中' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="監測項目" min-width="180">
          <template #default="{ row }"><router-link :to="`/monitors/${row.monitor_id}`"><b>{{ row.monitor_name }}</b></router-link></template>
        </el-table-column>
        <el-table-column label="原因" prop="cause" min-width="280" show-overflow-tooltip />
        <el-table-column label="開始" width="170"><template #default="{ row }">{{ fmtTime(row.started_at) }}</template></el-table-column>
        <el-table-column label="恢復" width="170"><template #default="{ row }">{{ fmtTime(row.resolved_at) }}</template></el-table-column>
        <el-table-column label="持續" width="120"><template #default="{ row }">{{ fmtDuration(row.duration_sec) }}</template></el-table-column>
        <el-table-column label="確認" width="160">
          <template #default="{ row }">
            <span v-if="row.acked_by" class="muted">{{ row.acked_by }} 已確認</span>
            <el-button v-else size="small" @click="ack(row)">我知道了</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import http from '../api'
import { fmtDuration, fmtTime } from '../utils'

const list = ref([])
const loading = ref(false)
const onlyOpen = ref(false)
const openCount = computed(() => list.value.filter((i) => !i.resolved_at).length)

async function load() {
  loading.value = true
  try { list.value = await http.get('/incidents', { params: { only_open: onlyOpen.value } }) } finally { loading.value = false }
}
async function ack(row) { await http.post(`/incidents/${row.id}/ack`); load() }
onMounted(load)
</script>

<style scoped>
.tools { display: flex; gap: 8px; flex-wrap: wrap; }
</style>
