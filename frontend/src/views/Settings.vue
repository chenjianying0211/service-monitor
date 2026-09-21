<template>
  <div class="page">
    <div class="page-head"><div><h2>系統設定</h2></div></div>
    <el-row :gutter="14">
      <el-col :md="12" :xs="24">
        <div class="card">
          <div class="bar"><b>維護時段</b><el-button size="small" type="primary" icon="Plus" @click="mDlg = true">新增</el-button></div>
          <div class="muted" style="margin-bottom:8px">維護時段內仍會檢查，但不發送通知。</div>
          <el-table :data="windows" size="small">
            <el-table-column label="範圍" prop="monitor_name" min-width="120" />
            <el-table-column label="時間" min-width="220"><template #default="{ row }">
              {{ fmtTime(row.start_at) }}<br />→ {{ fmtTime(row.end_at) }}
              <el-tag v-if="isActive(row)" size="small" type="warning">進行中</el-tag></template></el-table-column>
            <el-table-column label="備註" prop="note" min-width="100" />
            <el-table-column width="50"><template #default="{ row }">
              <el-button text circle icon="Delete" type="danger" @click="delWindow(row)" /></template></el-table-column>
          </el-table>
        </div>
      </el-col>
      <el-col :md="12" :xs="24">
        <div class="card">
          <div class="bar"><b>管理員帳號</b><el-button size="small" type="primary" icon="Plus" @click="uDlg = true">新增</el-button></div>
          <el-table :data="users" size="small">
            <el-table-column label="帳號" prop="username" />
            <el-table-column label="建立時間"><template #default="{ row }">{{ fmtTime(row.created_at) }}</template></el-table-column>
            <el-table-column width="50"><template #default="{ row }">
              <el-button v-if="row.username !== auth.username.value" text circle icon="Delete" type="danger" @click="delUser(row)" /></template></el-table-column>
          </el-table>
        </div>
        <div class="card" style="margin-top:14px">
          <b>修改我的密碼</b>
          <el-form label-position="top" style="margin-top:10px">
            <el-form-item label="舊密碼"><el-input v-model="pw.old_password" type="password" show-password /></el-form-item>
            <el-form-item label="新密碼（至少 6 碼）"><el-input v-model="pw.new_password" type="password" show-password /></el-form-item>
            <el-button type="primary" @click="changePw">更新密碼</el-button>
          </el-form>
        </div>
      </el-col>
    </el-row>

    <div class="card" style="margin-top:0">
      <div class="bar"><b>MCP 通道 / API 金鑰</b><el-button size="small" type="primary" icon="Plus" @click="newKey">產生金鑰</el-button></div>
      <div class="muted" style="margin-bottom:10px">
        讓 AI（Claude Code、Claude Desktop 等 MCP client）查詢與新增監測。MCP 網址：
        <code class="mono">{{ mcpUrl }}</code>，以 <code>Authorization: Bearer &lt;金鑰&gt;</code> 驗證。金鑰只在產生時顯示一次。
      </div>
      <el-table :data="keys" size="small">
        <el-table-column label="名稱" prop="name" min-width="140" />
        <el-table-column label="金鑰" width="140"><template #default="{ row }"><span class="mono">{{ row.prefix }}…</span></template></el-table-column>
        <el-table-column label="建立者" prop="created_by" width="100" />
        <el-table-column label="建立時間" width="170"><template #default="{ row }">{{ fmtTime(row.created_at) }}</template></el-table-column>
        <el-table-column label="最後使用" width="170"><template #default="{ row }">{{ fmtTime(row.last_used_at) }}</template></el-table-column>
        <el-table-column width="60"><template #default="{ row }">
          <el-tooltip content="撤銷"><el-button text circle icon="Delete" type="danger" @click="delKey(row)" /></el-tooltip></template></el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="keyDlg" title="金鑰已產生" width="640px" :close-on-click-modal="false">
      <el-alert type="warning" :closable="false" show-icon title="請立即複製保存，關閉後無法再次查看。" style="margin-bottom:12px" />
      <div class="gc-sec">API 金鑰</div>
      <div class="copy-row"><el-input :model-value="created.key" readonly class="mono" /><el-button icon="CopyDocument" @click="copy(created.key)" /></div>
      <div class="gc-sec">Claude Code 加入指令</div>
      <div class="copy-row"><el-input :model-value="cliCmd" readonly type="textarea" :rows="3" class="mono" /><el-button icon="CopyDocument" @click="copy(cliCmd)" /></div>
      <div class="gc-sec">JSON 設定（Claude Desktop / 其他 client）</div>
      <div class="copy-row"><el-input :model-value="jsonCfg" readonly type="textarea" :rows="9" class="mono" /><el-button icon="CopyDocument" @click="copy(jsonCfg)" /></div>
      <template #footer><el-button type="primary" @click="keyDlg = false">我已保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="mDlg" title="新增維護時段" width="480px">
      <el-form label-position="top">
        <el-form-item label="範圍">
          <el-select v-model="mForm.monitor_id" clearable placeholder="全部監測" style="width:100%">
            <el-option v-for="m in monitors" :key="m.id" :value="m.id" :label="m.name" /></el-select></el-form-item>
        <el-form-item label="時間">
          <el-date-picker v-model="mForm.range" type="datetimerange" start-placeholder="開始" end-placeholder="結束" style="width:100%" /></el-form-item>
        <el-form-item label="備註"><el-input v-model="mForm.note" placeholder="例如：系統升級" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="mDlg = false">取消</el-button><el-button type="primary" @click="saveWindow">儲存</el-button></template>
    </el-dialog>

    <el-dialog v-model="uDlg" title="新增管理員" width="420px">
      <el-form label-position="top">
        <el-form-item label="帳號"><el-input v-model="uForm.username" /></el-form-item>
        <el-form-item label="密碼（至少 6 碼）"><el-input v-model="uForm.password" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer><el-button @click="uDlg = false">取消</el-button><el-button type="primary" @click="saveUser">建立</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import http, { auth } from '../api'
import { fmtTime } from '../utils'

const windows = ref([]), users = ref([]), monitors = ref([]), keys = ref([])
const mDlg = ref(false), uDlg = ref(false)
const mForm = reactive({ monitor_id: null, range: null, note: '' })
const uForm = reactive({ username: '', password: '' })
const pw = reactive({ old_password: '', new_password: '' })

async function load() {
  ;[windows.value, users.value, monitors.value, keys.value] = await Promise.all(['/maintenance', '/users', '/monitors', '/api-keys'].map((u) => http.get(u)))
}
onMounted(load)
const isActive = (w) => dayjs().isAfter(dayjs(w.start_at)) && dayjs().isBefore(dayjs(w.end_at))

async function saveWindow() {
  if (!mForm.range) return ElMessage.warning('請選擇時間')
  await http.post('/maintenance', { monitor_id: mForm.monitor_id || null, start_at: mForm.range[0].toISOString(), end_at: mForm.range[1].toISOString(), note: mForm.note })
  mDlg.value = false; Object.assign(mForm, { monitor_id: null, range: null, note: '' }); load()
}
async function delWindow(w) { await http.delete(`/maintenance/${w.id}`); load() }
async function saveUser() {
  await http.post('/users', uForm); uDlg.value = false; Object.assign(uForm, { username: '', password: '' }); ElMessage.success('已建立'); load()
}
async function delUser(u) {
  await ElMessageBox.confirm(`確定刪除管理員「${u.username}」？`, '刪除', { type: 'warning', confirmButtonText: '刪除', cancelButtonText: '取消' })
  await http.delete(`/users/${u.id}`); load()
}
const mcpUrl = `${location.origin}/mcp/`
const keyDlg = ref(false)
const created = reactive({ key: '', mcp_url: '' })
const cliCmd = computed(() => `claude mcp add --transport http service-monitor ${created.mcp_url || mcpUrl} --header "Authorization: Bearer ${created.key}"`)
const jsonCfg = computed(() => JSON.stringify({ mcpServers: { 'service-monitor': {
  type: 'http', url: created.mcp_url || mcpUrl, headers: { Authorization: `Bearer ${created.key}` } } } }, null, 2))
async function newKey() {
  const { value } = await ElMessageBox.prompt('金鑰名稱（例如：Claude Code - 筆電）', '產生 API 金鑰',
    { inputPattern: /\S+/, inputErrorMessage: '請輸入名稱', confirmButtonText: '產生', cancelButtonText: '取消' })
  Object.assign(created, await http.post('/api-keys', { name: value }))
  keyDlg.value = true; load()
}
async function delKey(k) {
  await ElMessageBox.confirm(`撤銷金鑰「${k.name}」？使用中的 AI 會立即無法連線。`, '撤銷金鑰', { type: 'warning', confirmButtonText: '撤銷', cancelButtonText: '取消' })
  await http.delete(`/api-keys/${k.id}`); load()
}
async function copy(text) {
  try { await navigator.clipboard.writeText(text); ElMessage.success('已複製') } catch { ElMessage.info('請手動選取複製') }
}
async function changePw() {
  await http.post('/auth/password', pw); Object.assign(pw, { old_password: '', new_password: '' }); ElMessage.success('密碼已更新')
}
</script>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.el-col { margin-bottom: 14px; }
.gc-sec { font-size: 12px; color: var(--sm-muted); margin: 10px 0 4px; }
.copy-row { display: flex; gap: 6px; align-items: flex-start; }
code { background: var(--sm-border); padding: 1px 6px; border-radius: 4px; }
</style>
