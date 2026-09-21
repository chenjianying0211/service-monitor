<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>通知設定</h2>
        <div class="sub">流程：① 加 LINE 官方帳號 / SMTP → ② 聯絡人綁定或新增 → ③ 放進通知群組 → ④ 監測項目選擇要通知的群組</div>
      </div>
    </div>

    <el-tabs v-model="tab" class="card tabs">
      <!-- ============ 通知群組 ============ -->
      <el-tab-pane name="groups">
        <template #label><el-icon><Collection /></el-icon>&nbsp;通知群組</template>
        <div class="bar"><span class="muted">決定「哪些服務出事要通知哪些人」。</span>
          <el-button type="primary" icon="Plus" @click="openGroup(null)">新增群組</el-button></div>
        <el-empty v-if="!groups.length" description="還沒有通知群組" />
        <div class="group-grid">
          <div v-for="g in groups" :key="g.id" class="card group-card">
            <div class="gc-head"><b>{{ g.name }}</b>
              <div><el-button text circle icon="Edit" @click="openGroup(g)" />
                <el-button text circle icon="Delete" type="danger" @click="del('groups', g, g.name)" /></div></div>
            <div class="muted" v-if="g.description">{{ g.description }}</div>
            <div class="gc-sec">收件人（{{ g.contact_ids.length }}）</div>
            <div class="chips">
              <el-tag v-for="cid in g.contact_ids" :key="cid" size="small" :type="contactTag(cid)">
                {{ contactIcon(cid) }} {{ contactName(cid) }}</el-tag>
              <span v-if="!g.contact_ids.length" class="muted">無</span>
            </div>
            <div class="gc-sec">監測項目（{{ g.monitor_ids.length }}）</div>
            <div class="chips">
              <el-tag v-for="mid in g.monitor_ids.slice(0, 12)" :key="mid" size="small" effect="plain">{{ monitorName(mid) }}</el-tag>
              <span v-if="g.monitor_ids.length > 12" class="muted">…等 {{ g.monitor_ids.length }} 個</span>
              <span v-if="!g.monitor_ids.length" class="muted">無</span>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ============ 聯絡人 ============ -->
      <el-tab-pane name="contacts">
        <template #label><el-icon><User /></el-icon>&nbsp;聯絡人
          <el-badge v-if="pendingCount" :value="pendingCount" style="margin-left:6px" /></template>
        <el-alert v-if="pendingCount" type="warning" show-icon :closable="false" style="margin-bottom:12px"
                  :title="`有 ${pendingCount} 個 LINE 綁定申請待啟用`" description="確認身分後按「啟用」，並加入通知群組即可開始收到通知。" />
        <div class="bar">
          <el-radio-group v-model="contactFilter" size="small">
            <el-radio-button value="">全部</el-radio-button>
            <el-radio-button value="pending">待啟用</el-radio-button>
            <el-radio-button value="line">LINE</el-radio-button>
            <el-radio-button value="email">Email</el-radio-button>
          </el-radio-group>
          <el-button type="primary" icon="Plus" @click="openContact(null)">新增聯絡人</el-button>
        </div>
        <el-table :data="filteredContacts">
          <el-table-column label="狀態" width="90">
            <template #default="{ row }"><el-tag size="small" round :type="{ active: 'success', pending: 'warning', disabled: 'info' }[row.status]">
              {{ { active: '啟用', pending: '待啟用', disabled: '停用' }[row.status] }}</el-tag></template>
          </el-table-column>
          <el-table-column label="名稱" min-width="150"><template #default="{ row }"><b>{{ row.name }}</b>
            <div class="muted" v-if="row.note">{{ row.note }}</div></template></el-table-column>
          <el-table-column label="類型" width="140"><template #default="{ row }">{{ CONTACT_TYPE[row.type] }}
            <div class="muted" v-if="row.line_channel_id">{{ channelName(row.line_channel_id) }}</div></template></el-table-column>
          <el-table-column label="地址 / ID" min-width="200"><template #default="{ row }"><span class="mono ellipsis">{{ row.address }}</span></template></el-table-column>
          <el-table-column label="群組" min-width="150"><template #default="{ row }">
            <el-tag v-for="gid in row.group_ids" :key="gid" size="small" type="info" style="margin:2px">{{ groupName(gid) }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.status === 'pending'" size="small" type="success" @click="activate(row)">啟用</el-button>
              <el-button size="small" @click="testContact(row)" :loading="testing === row.id">測試</el-button>
              <el-button text circle icon="Edit" @click="openContact(row)" />
              <el-button text circle icon="Delete" type="danger" @click="del('contacts', row, row.name)" />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- ============ LINE 官方帳號 ============ -->
      <el-tab-pane name="line">
        <template #label><el-icon><ChatDotRound /></el-icon>&nbsp;LINE 官方帳號</template>
        <el-collapse style="margin-bottom:14px">
          <el-collapse-item title="📘 如何取得 LINE 官方帳號的 Token？（LINE Notify 已於 2025/3/31 停止服務，改用 Messaging API）">
            <ol class="guide">
              <li>到 <a href="https://developers.line.biz/console/" target="_blank">LINE Developers Console</a> 建立 Provider → 建立 <b>Messaging API</b> channel（會同時建立一個 LINE 官方帳號）。</li>
              <li><b>Basic settings</b> 分頁複製 <b>Channel secret</b>；<b>Messaging API</b> 分頁最下方 Issue <b>Channel access token (long-lived)</b>。</li>
              <li>在這裡「新增官方帳號」貼上兩個值，系統會驗證並產生 <b>Webhook URL</b>。</li>
              <li>回到 Messaging API 分頁 → Webhook URL 貼上 → 按 Verify → 開啟 <b>Use webhook</b>；並在 LINE Official Account Manager 關閉「自動回應訊息」，若要加入群組需開啟「允許加入群組」。</li>
              <li>要收通知的人掃 QR code 加好友（或把機器人拉進群組、在群組輸入 <code>綁定</code>），就會出現在「聯絡人 → 待啟用」。</li>
            </ol>
            <div class="muted">免費方案每月推播則數有限（依 LINE 官方方案），可在下方「額度」查看用量；可建立多個官方帳號分散額度或分不同單位使用。</div>
          </el-collapse-item>
        </el-collapse>
        <div class="bar"><span></span><el-button type="primary" icon="Plus" @click="openChannel(null)">新增官方帳號</el-button></div>
        <el-empty v-if="!channels.length" description="尚未新增 LINE 官方帳號" />
        <div class="group-grid">
          <div v-for="c in channels" :key="c.id" class="card group-card">
            <div class="gc-head"><div><b>{{ c.name }}</b> <el-tag v-if="!c.enabled" size="small" type="info">停用</el-tag></div>
              <div><el-button text circle icon="Edit" @click="openChannel(c)" />
                <el-button text circle icon="Delete" type="danger" @click="del('line-channels', c, c.name)" /></div></div>
            <div class="muted">Bot ID：<span class="mono">{{ c.bot_basic_id || '—' }}</span> · 聯絡人 {{ c.contact_count }} 位</div>
            <div class="gc-sec">Webhook URL</div>
            <div class="copy-row"><el-input :model-value="c.webhook_url" readonly size="small" class="mono" />
              <el-button size="small" icon="CopyDocument" @click="copy(c.webhook_url)" /></div>
            <div class="gc-sec">本月推播額度</div>
            <div v-if="quota[c.id]">
              <el-progress :percentage="quotaPct(quota[c.id])" :status="quotaPct(quota[c.id]) > 85 ? 'exception' : ''" />
              <span class="muted">已用 {{ quota[c.id].used }} / {{ quota[c.id].type === 'none' ? '無上限' : quota[c.id].limit }} 則</span>
            </div>
            <el-button v-else size="small" @click="loadQuota(c)" :loading="quotaLoading === c.id">查詢額度</el-button>
            <div v-if="c.bot_basic_id" class="gc-sec">加好友連結：<a :href="`https://line.me/R/ti/p/${c.bot_basic_id}`" target="_blank">line.me/R/ti/p/{{ c.bot_basic_id }}</a></div>
          </div>
        </div>
      </el-tab-pane>

      <!-- ============ SMTP ============ -->
      <el-tab-pane name="smtp">
        <template #label><el-icon><Message /></el-icon>&nbsp;Email（SMTP）</template>
        <div class="bar"><span class="muted">Gmail 請使用「應用程式密碼」（smtp.gmail.com / 587 / STARTTLS）。</span>
          <el-button type="primary" icon="Plus" @click="openSmtp(null)">新增 SMTP</el-button></div>
        <el-table :data="smtps">
          <el-table-column label="名稱" min-width="140"><template #default="{ row }"><b>{{ row.name }}</b>
            <el-tag v-if="row.is_default" size="small" style="margin-left:6px">預設</el-tag></template></el-table-column>
          <el-table-column label="伺服器" min-width="200"><template #default="{ row }"><span class="mono">{{ row.host }}:{{ row.port }}</span> · {{ row.security.toUpperCase() }}</template></el-table-column>
          <el-table-column label="寄件者" prop="from_addr" min-width="180" />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="testSmtp(row)">寄測試信</el-button>
              <el-button text circle icon="Edit" @click="openSmtp(row)" />
              <el-button text circle icon="Delete" type="danger" @click="del('smtp', row, row.name)" />
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <!-- 群組對話框 -->
    <el-dialog v-model="dlg.group" :title="gForm.id ? '編輯通知群組' : '新增通知群組'" width="600px">
      <el-form label-position="top">
        <el-form-item label="群組名稱"><el-input v-model="gForm.name" placeholder="例如：IT 值班、醫院專案負責人" /></el-form-item>
        <el-form-item label="說明"><el-input v-model="gForm.description" /></el-form-item>
        <el-form-item label="收件人（啟用中的聯絡人）">
          <el-select v-model="gForm.contact_ids" multiple filterable placeholder="選擇要收到通知的人" style="width:100%">
            <el-option v-for="c in contacts.filter((x) => x.status !== 'disabled')" :key="c.id" :value="c.id"
                       :label="`${c.name}（${CONTACT_TYPE[c.type]}${c.status === 'pending' ? '，待啟用' : ''}）`" />
          </el-select>
        </el-form-item>
        <el-form-item label="負責的監測項目">
          <el-select v-model="gForm.monitor_ids" multiple filterable collapse-tags collapse-tags-tooltip placeholder="選擇監測項目" style="width:100%">
            <el-option v-for="m in monitors" :key="m.id" :value="m.id" :label="m.name" />
          </el-select>
          <div style="margin-top:6px"><el-button size="small" text type="primary" @click="gForm.monitor_ids = monitors.map((m) => m.id)">全選</el-button>
            <el-button size="small" text @click="gForm.monitor_ids = []">清除</el-button></div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg.group = false">取消</el-button>
        <el-button type="primary" @click="saveGroup">儲存</el-button></template>
    </el-dialog>

    <!-- 聯絡人對話框 -->
    <el-dialog v-model="dlg.contact" :title="cForm.id ? '編輯聯絡人' : '新增聯絡人'" width="560px">
      <el-form label-position="top">
        <el-form-item label="類型">
          <el-radio-group v-model="cForm.type">
            <el-radio-button value="email">Email</el-radio-button>
            <el-radio-button value="line_user">LINE 個人</el-radio-button>
            <el-radio-button value="line_group">LINE 群組</el-radio-button>
          </el-radio-group>
          <div class="form-hint" v-if="cForm.type !== 'email' && !cForm.id">LINE 聯絡人建議用「加好友 / 群組輸入綁定」自動建立；若已知 userId（U 開頭）或 groupId（C 開頭）也可手動填。</div>
        </el-form-item>
        <el-form-item label="名稱"><el-input v-model="cForm.name" /></el-form-item>
        <el-form-item :label="cForm.type === 'email' ? 'Email' : (cForm.type === 'line_user' ? 'LINE userId' : 'LINE groupId')">
          <el-input v-model="cForm.address" class="mono" /></el-form-item>
        <el-form-item v-if="cForm.type !== 'email'" label="透過哪個 LINE 官方帳號發送">
          <el-select v-model="cForm.line_channel_id" style="width:100%">
            <el-option v-for="c in channels" :key="c.id" :value="c.id" :label="c.name" /></el-select></el-form-item>
        <el-form-item v-else label="SMTP（空白 = 使用預設）">
          <el-select v-model="cForm.smtp_profile_id" clearable style="width:100%">
            <el-option v-for="s in smtps" :key="s.id" :value="s.id" :label="s.name" /></el-select></el-form-item>
        <el-form-item label="加入通知群組">
          <el-select v-model="cForm.group_ids" multiple style="width:100%">
            <el-option v-for="g in groups" :key="g.id" :value="g.id" :label="g.name" /></el-select></el-form-item>
        <el-form-item label="狀態">
          <el-radio-group v-model="cForm.status">
            <el-radio value="active">啟用</el-radio><el-radio value="pending">待啟用</el-radio><el-radio value="disabled">停用</el-radio>
          </el-radio-group></el-form-item>
        <el-form-item label="備註"><el-input v-model="cForm.note" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg.contact = false">取消</el-button>
        <el-button type="primary" @click="saveContact">儲存</el-button></template>
    </el-dialog>

    <!-- LINE 官方帳號對話框 -->
    <el-dialog v-model="dlg.channel" :title="chForm.id ? '編輯 LINE 官方帳號' : '新增 LINE 官方帳號'" width="560px">
      <el-form label-position="top">
        <el-form-item label="名稱（自訂，例如：醫院 IT 通知）"><el-input v-model="chForm.name" /></el-form-item>
        <el-form-item label="Channel Access Token（long-lived）">
          <el-input v-model="chForm.access_token" type="textarea" :rows="3" class="mono"
                    :placeholder="chForm.id ? '留空表示不變更' : ''" /></el-form-item>
        <el-form-item label="Channel Secret">
          <el-input v-model="chForm.channel_secret" show-password class="mono" :placeholder="chForm.id ? '留空表示不變更' : ''" /></el-form-item>
        <el-form-item><el-switch v-model="chForm.enabled" active-text="啟用" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg.channel = false">取消</el-button>
        <el-button type="primary" @click="saveChannel" :loading="saving">驗證並儲存</el-button></template>
    </el-dialog>

    <!-- SMTP 對話框 -->
    <el-dialog v-model="dlg.smtp" :title="sForm.id ? '編輯 SMTP' : '新增 SMTP'" width="560px">
      <el-form label-position="top">
        <el-form-item label="名稱"><el-input v-model="sForm.name" placeholder="例如：公司 Gmail" /></el-form-item>
        <el-row :gutter="12">
          <el-col :span="14"><el-form-item label="主機"><el-input v-model="sForm.host" placeholder="smtp.gmail.com" /></el-form-item></el-col>
          <el-col :span="10"><el-form-item label="連接埠"><el-input-number v-model="sForm.port" :min="1" :max="65535" style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="加密">
          <el-radio-group v-model="sForm.security" @change="(v) => (sForm.port = { ssl: 465, starttls: 587, none: 25 }[v])">
            <el-radio-button value="starttls">STARTTLS</el-radio-button><el-radio-button value="ssl">SSL/TLS</el-radio-button><el-radio-button value="none">無</el-radio-button>
          </el-radio-group></el-form-item>
        <el-form-item label="帳號"><el-input v-model="sForm.username" /></el-form-item>
        <el-form-item label="密碼 / 應用程式密碼"><el-input v-model="sForm.password" show-password :placeholder="sForm.has_password ? '留空表示不變更' : ''" /></el-form-item>
        <el-form-item label="寄件者"><el-input v-model="sForm.from_addr" placeholder="監控平台 <alert@example.com>" /></el-form-item>
        <el-form-item><el-checkbox v-model="sForm.is_default">設為預設</el-checkbox></el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg.smtp = false">取消</el-button>
        <el-button type="primary" @click="saveSmtp">儲存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api'
import { CONTACT_TYPE } from '../utils'

const route = useRoute()
const router = useRouter()
const tab = ref(route.query.tab || 'groups')
watch(tab, (t) => router.replace({ query: { tab: t } }))

const groups = ref([]), contacts = ref([]), channels = ref([]), smtps = ref([]), monitors = ref([])
const dlg = reactive({ group: false, contact: false, channel: false, smtp: false })
const gForm = reactive({}), cForm = reactive({}), chForm = reactive({}), sForm = reactive({})
const contactFilter = ref('')
const testing = ref(null)
const saving = ref(false)
const quota = reactive({})
const quotaLoading = ref(null)

async function load() {
  ;[groups.value, contacts.value, channels.value, smtps.value, monitors.value] = await Promise.all(
    ['/groups', '/contacts', '/line-channels', '/smtp', '/monitors'].map((u) => http.get(u)))
}
onMounted(load)

const pendingCount = computed(() => contacts.value.filter((c) => c.status === 'pending').length)
const filteredContacts = computed(() => contacts.value.filter((c) => {
  const f = contactFilter.value
  if (f === 'pending') return c.status === 'pending'
  if (f === 'line') return c.type !== 'email'
  if (f === 'email') return c.type === 'email'
  return true
}))
const byId = (arr, id) => arr.value.find((x) => x.id === id)
const contactName = (id) => byId(contacts, id)?.name || `#${id}`
const contactIcon = (id) => (byId(contacts, id)?.type === 'email' ? '✉️' : '💬')
const contactTag = (id) => ({ pending: 'warning', disabled: 'info' }[byId(contacts, id)?.status] || 'success')
const monitorName = (id) => byId(monitors, id)?.name || `#${id}`
const channelName = (id) => byId(channels, id)?.name || `#${id}`
const groupName = (id) => byId(groups, id)?.name || `#${id}`
const quotaPct = (q) => (q.type === 'none' || !q.limit ? 0 : Math.min(100, Math.round((q.used / q.limit) * 100)))

const reset = (obj, val) => { Object.keys(obj).forEach((k) => delete obj[k]); Object.assign(obj, JSON.parse(JSON.stringify(val))) }
const strip = ({ id, created_at, has_password, webhook_url, contact_count, bot_basic_id, ...rest }) => rest

async function copy(text) {
  try { await navigator.clipboard.writeText(text); ElMessage.success('已複製') } catch { ElMessage.info(text) }
}
async function del(kind, row, name) {
  await ElMessageBox.confirm(`確定刪除「${name}」？`, '刪除', { type: 'warning', confirmButtonText: '刪除', cancelButtonText: '取消' })
  await http.delete(`/${kind}/${row.id}`)
  ElMessage.success('已刪除'); load()
}

// 群組
function openGroup(g) { reset(gForm, g || { name: '', description: '', contact_ids: [], monitor_ids: [] }); dlg.group = true }
async function saveGroup() {
  if (!gForm.name) return ElMessage.warning('請輸入群組名稱')
  if (gForm.id) await http.put(`/groups/${gForm.id}`, strip(gForm)); else await http.post('/groups', strip(gForm))
  dlg.group = false; ElMessage.success('已儲存'); load()
}

// 聯絡人
function openContact(c) {
  reset(cForm, c || { name: '', type: 'email', address: '', line_channel_id: channels.value[0]?.id ?? null, smtp_profile_id: null,
    status: 'active', note: '', group_ids: groups.value.length === 1 ? [groups.value[0].id] : [] })
  dlg.contact = true
}
async function saveContact() {
  if (!cForm.name || !cForm.address) return ElMessage.warning('請填寫名稱與地址')
  if (cForm.id) await http.put(`/contacts/${cForm.id}`, strip(cForm)); else await http.post('/contacts', strip(cForm))
  dlg.contact = false; ElMessage.success('已儲存'); load()
}
async function activate(c) {
  openContact(c); cForm.status = 'active'
}
async function testContact(c) {
  testing.value = c.id
  try { await http.post(`/contacts/${c.id}/test`); ElMessage.success(`已發送測試通知給 ${c.name}`) } finally { testing.value = null }
}

// LINE
function openChannel(c) { reset(chForm, c ? { id: c.id, name: c.name, enabled: c.enabled, access_token: '', channel_secret: '' } : { name: '', access_token: '', channel_secret: '', enabled: true }); dlg.channel = true }
async function saveChannel() {
  if (!chForm.name) return ElMessage.warning('請輸入名稱')
  saving.value = true
  try {
    if (chForm.id) await http.put(`/line-channels/${chForm.id}`, strip(chForm))
    else {
      const r = await http.post('/line-channels', strip(chForm))
      ElMessageBox.alert(`驗證成功：${r.bot.displayName || ''}（${r.bot.basicId || ''}）。請把 Webhook URL 貼到 LINE Developers：${r.webhook_url}`,
        '已新增官方帳號')
    }
    dlg.channel = false; load()
  } finally { saving.value = false }
}
async function loadQuota(c) {
  quotaLoading.value = c.id
  try { quota[c.id] = await http.get(`/line-channels/${c.id}/quota`) } finally { quotaLoading.value = null }
}

// SMTP
function openSmtp(s) { reset(sForm, s ? { ...s, password: '' } : { name: '', host: '', port: 587, security: 'starttls', username: '', password: '', from_addr: '', is_default: false }); dlg.smtp = true }
async function saveSmtp() {
  if (!sForm.name || !sForm.host || !sForm.from_addr) return ElMessage.warning('請填寫名稱、主機與寄件者')
  if (sForm.id) await http.put(`/smtp/${sForm.id}`, strip(sForm)); else await http.post('/smtp', strip(sForm))
  dlg.smtp = false; ElMessage.success('已儲存'); load()
}
async function testSmtp(s) {
  const { value } = await ElMessageBox.prompt('寄到哪個信箱？', '寄送測試信', { inputPattern: /^[^@\s]+@[^@\s]+$/, inputErrorMessage: 'Email 格式錯誤', confirmButtonText: '寄送', cancelButtonText: '取消' })
  await http.post(`/smtp/${s.id}/test`, { to: value })
  ElMessage.success('測試信已寄出')
}
</script>

<style scoped>
.tabs { padding-top: 6px; }
.bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
.group-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.group-card { display: flex; flex-direction: column; gap: 6px; }
.gc-head { display: flex; justify-content: space-between; align-items: center; font-size: 15px; }
.gc-sec { font-size: 12px; color: var(--sm-muted); margin-top: 6px; }
.chips { display: flex; flex-wrap: wrap; gap: 4px; }
.copy-row { display: flex; gap: 6px; }
.guide { line-height: 1.9; padding-left: 20px; margin: 4px 0 8px; }
code { background: var(--sm-border); padding: 1px 6px; border-radius: 4px; }
</style>
