<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>主機</h2>
        <div class="sub">共 {{ hosts.length }} 台 · 監測項目可歸屬到主機，總覽頁會依主機分區顯示</div>
      </div>
      <el-button type="primary" icon="Plus" @click="open(null)">新增主機</el-button>
    </div>

    <el-empty v-if="!loading && !hosts.length" description="還沒有主機" />
    <div class="grid">
      <div v-for="h in hosts" :key="h.id" class="card host">
        <div class="h-head">
          <span class="os" :class="osClass(h.os)">{{ osIcon(h.os) }}</span>
          <div class="grow">
            <div class="h-name">{{ h.name }}</div>
            <div class="mono muted">{{ h.ip || '—' }}</div>
          </div>
          <el-button text circle icon="Edit" @click="open(h)" />
          <el-button text circle icon="Delete" type="danger" @click="remove(h)" />
        </div>
        <div class="meta">
          <span v-if="h.os"><el-icon><Monitor /></el-icon>{{ h.os }}</span>
          <span v-if="h.region"><el-icon><Location /></el-icon>{{ h.region }}</span>
          <span v-if="h.vm_size"><el-icon><Cpu /></el-icon>{{ h.vm_size }}</span>
          <span v-if="h.resource_group"><el-icon><FolderOpened /></el-icon>{{ h.resource_group }}</span>
        </div>
        <div v-if="h.description" class="muted">{{ h.description }}</div>
        <div class="counts">
          <span v-for="c in countList(h)" :key="c.key" class="cnt">
            <span class="dot" :style="{ background: c.color }"></span>{{ c.label }} <b>{{ c.n }}</b>
          </span>
          <span v-if="!h.monitor_ids.length" class="muted">尚無監測項目</span>
        </div>
      </div>
    </div>

    <el-dialog v-model="dlg" :title="form.id ? '編輯主機' : '新增主機'" width="620px">
      <el-form label-position="top">
        <el-row :gutter="12">
          <el-col :sm="12" :xs="24"><el-form-item label="主機名稱"><el-input v-model="form.name" placeholder="例如 testlinux" /></el-form-item></el-col>
          <el-col :sm="12" :xs="24"><el-form-item label="IP"><el-input v-model="form.ip" class="mono" /></el-form-item></el-col>
          <el-col :sm="12" :xs="24"><el-form-item label="作業系統">
            <el-select v-model="form.os" clearable allow-create filterable style="width:100%">
              <el-option value="Linux" /><el-option value="Windows" /></el-select></el-form-item></el-col>
          <el-col :sm="12" :xs="24"><el-form-item label="區域"><el-input v-model="form.region" placeholder="Korea Central" /></el-form-item></el-col>
          <el-col :sm="12" :xs="24"><el-form-item label="資源群組"><el-input v-model="form.resource_group" /></el-form-item></el-col>
          <el-col :sm="12" :xs="24"><el-form-item label="VM 規格"><el-input v-model="form.vm_size" placeholder="Standard_D2s_v3" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="說明"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="排序（小的在前）"><el-input-number v-model="form.sort_order" /></el-form-item>
        <el-form-item label="歸屬這台主機的監測項目">
          <el-select v-model="form.monitor_ids" multiple filterable collapse-tags collapse-tags-tooltip :max-collapse-tags="6" style="width:100%" placeholder="選擇監測項目">
            <el-option v-for="m in monitors" :key="m.id" :value="m.id"
                       :label="m.host_id && m.host_id !== form.id ? `${m.name}（目前在 ${hostName(m.host_id)}）` : m.name" />
          </el-select>
          <div class="form-hint">一個監測項目只能屬於一台主機；選了已屬於其他主機的項目會移過來。</div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg = false">取消</el-button><el-button type="primary" @click="save">儲存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api'

const hosts = ref([])
const monitors = ref([])
const loading = ref(false)
const dlg = ref(false)
const form = reactive({})

async function load() {
  loading.value = true
  try { [hosts.value, monitors.value] = await Promise.all([http.get('/hosts'), http.get('/monitors')]) } finally { loading.value = false }
}
onMounted(load)

const hostName = (id) => hosts.value.find((h) => h.id === id)?.name || `#${id}`
const osIcon = (os) => ((os || '').toLowerCase().includes('win') ? '⊞' : (os || '').toLowerCase().includes('linux') ? '🐧' : '🖥')
const osClass = (os) => ((os || '').toLowerCase().includes('win') ? 'win' : 'linux')
const countList = (h) => [
  { key: 'UP', label: '正常', color: 'var(--sm-up)', n: h.counts.UP },
  { key: 'DOWN', label: '中斷', color: 'var(--sm-down)', n: h.counts.DOWN },
  { key: 'PENDING', label: '異常', color: 'var(--sm-pending)', n: h.counts.PENDING },
  { key: 'PAUSED', label: '暫停', color: 'var(--sm-paused)', n: h.counts.PAUSED + h.counts.UNKNOWN },
].filter((c) => c.n)

function open(h) {
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, h ? JSON.parse(JSON.stringify(h))
    : { name: '', ip: '', os: 'Linux', region: '', resource_group: '', vm_size: '', description: '', sort_order: 0, monitor_ids: [] })
  dlg.value = true
}
async function save() {
  if (!form.name) return ElMessage.warning('請輸入主機名稱')
  const { id, counts, created_at, ...body } = form
  if (id) await http.put(`/hosts/${id}`, body); else await http.post('/hosts', body)
  dlg.value = false; ElMessage.success('已儲存'); load()
}
async function remove(h) {
  await ElMessageBox.confirm(`確定刪除主機「${h.name}」？底下的監測項目不會刪除，會變成「未指定主機」。`, '刪除主機',
    { type: 'warning', confirmButtonText: '刪除', cancelButtonText: '取消' })
  await http.delete(`/hosts/${h.id}`); ElMessage.success('已刪除'); load()
}
</script>

<style scoped>
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.host { display: flex; flex-direction: column; gap: 10px; }
.h-head { display: flex; align-items: center; gap: 12px; }
.grow { flex: 1; min-width: 0; }
.h-name { font-weight: 650; font-size: 16px; }
.os { width: 40px; height: 40px; border-radius: 10px; display: grid; place-items: center; font-size: 20px; flex-shrink: 0; }
.os.linux { background: color-mix(in srgb, var(--sm-pending) 18%, transparent); }
.os.win { background: color-mix(in srgb, var(--sm-accent) 18%, transparent); color: var(--sm-accent); font-size: 24px; }
.meta { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 12.5px; color: var(--sm-muted); }
.meta span { display: inline-flex; align-items: center; gap: 4px; }
.counts { display: flex; flex-wrap: wrap; gap: 12px; border-top: 1px solid var(--sm-border); padding-top: 8px; font-size: 13px; }
.cnt { display: inline-flex; align-items: center; gap: 6px; }
</style>
