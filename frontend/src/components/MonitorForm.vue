<template>
  <el-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)"
             :title="form.id ? '編輯監測' : '新增監測'" width="680px" top="5vh" destroy-on-close>
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="監測類型" prop="type">
        <div class="types">
          <div v-for="t in TYPE_OPTIONS" :key="t.value" class="type-card" :class="{ on: form.type === t.value }"
               @click="form.type = t.value">
            <b>{{ t.label }}</b><span>{{ t.desc }}</span>
          </div>
        </div>
      </el-form-item>

      <el-row :gutter="16">
        <el-col :sm="12" :xs="24">
          <el-form-item label="名稱" prop="name"><el-input v-model="form.name" placeholder="例如：官網" /></el-form-item>
        </el-col>
        <el-col :sm="12" :xs="24">
          <el-form-item label="所屬主機">
            <el-select v-model="form.host_id" clearable placeholder="未指定" style="width:100%">
              <el-option v-for="h in hosts" :key="h.id" :value="h.id" :label="`${h.name}${h.ip ? '（' + h.ip + '）' : ''}`" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="標籤"><el-input v-model="form.tags" placeholder="逗號分隔，例如：正式,醫院" /></el-form-item>
        </el-col>
      </el-row>

      <el-alert v-if="isPush" type="info" :closable="false" show-icon style="margin-bottom:16px"
                title="其他主機自行監控，定時呼叫本平台的回報網址；逾時未回報或回報異常時，由這台依通知群組發送通知。"
                :description="form.id ? '' : '儲存後會產生專屬回報網址，並附上 Linux / Windows 設定範例。'" />
      <el-form-item v-if="isPush && form.id" label="回報網址與設定範例">
        <PushGuide :token="form.target" can-regenerate @regenerate="regenerate" style="width:100%" />
      </el-form-item>
      <el-form-item v-if="!isPush" :label="targetLabel" prop="target">
        <el-input v-model="form.target" :placeholder="targetPlaceholder" />
        <div v-if="form.type === 'docker'" class="form-hint">Docker 容器監測只能看到監控平台所在主機（testlinux）上的容器；其他主機請用 TCP / HTTP 監測。</div>
      </el-form-item>
      <el-form-item v-if="form.type === 'proxy_pair'" label="後端網址（nginx proxy_pass 的目標）" prop="backend_url">
        <el-input v-model="form.backend_url" placeholder="http://127.0.0.1:8081" />
        <div class="form-hint">若後端正常但網域失敗，會判定為「轉發異常」並在通知中說明。</div>
      </el-form-item>
      <el-form-item v-if="form.type === 'keyword'" label="必須包含的關鍵字" prop="keyword">
        <el-input v-model="form.keyword" />
      </el-form-item>

      <el-row :gutter="16" v-if="isHttp">
        <el-col :sm="8" :xs="12">
          <el-form-item label="方法">
            <el-select v-model="form.method"><el-option v-for="m in ['GET', 'HEAD', 'POST']" :key="m" :value="m" /></el-select>
          </el-form-item>
        </el-col>
        <el-col :sm="8" :xs="12">
          <el-form-item label="預期狀態碼"><el-input v-model="form.expected_status" placeholder="200-399" /></el-form-item>
        </el-col>
        <el-col :sm="8" :xs="24">
          <el-form-item label="選項">
            <el-checkbox v-model="form.follow_redirects">跟隨轉址</el-checkbox>
            <el-checkbox v-model="form.ignore_tls">忽略憑證錯誤</el-checkbox>
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item v-if="form.type === 'ssl_cert'" label="剩餘天數低於幾天告警">
        <el-input-number v-model="form.ssl_warn_days" :min="0" :max="365" />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :sm="6" :xs="12">
          <el-form-item :label="isPush ? '預期回報間隔（秒）' : '檢查間隔（秒）'"><el-input-number v-model="form.interval_sec" :min="20" :step="10" controls-position="right" /></el-form-item>
        </el-col>
        <el-col :sm="6" :xs="12">
          <el-form-item :label="isPush ? '寬限秒數' : '逾時（秒）'"><el-input-number v-model="form.timeout_sec" :min="1" :max="120" controls-position="right" /></el-form-item>
        </el-col>
        <el-col :sm="6" :xs="12">
          <el-form-item :label="isPush ? '連續異常幾次才告警' : '連續失敗幾次才告警'"><el-input-number v-model="form.retries" :min="1" :max="20" controls-position="right" /></el-form-item>
        </el-col>
        <el-col :sm="6" :xs="12">
          <el-form-item label="重複提醒（分，0=不提醒）"><el-input-number v-model="form.resend_interval_min" :min="0" :step="30" controls-position="right" /></el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="通知群組">
        <div class="groups">
          <div v-if="!groups.length" class="muted">尚未建立通知群組，請先到「通知設定 → 通知群組」建立。</div>
          <div v-for="g in groups" :key="g.id" class="group-row">
            <el-checkbox :model-value="!!linkOf(g.id)" @change="toggleGroup(g.id, $event)">{{ g.name }}</el-checkbox>
            <el-checkbox-group v-if="linkOf(g.id)" v-model="linkOf(g.id).events" size="small">
              <el-checkbox-button value="down">中斷</el-checkbox-button>
              <el-checkbox-button value="up">恢復</el-checkbox-button>
              <el-checkbox-button value="reminder">重複提醒</el-checkbox-button>
            </el-checkbox-group>
          </div>
        </div>
      </el-form-item>

      <el-form-item label="說明"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
      <el-form-item><el-switch v-model="form.enabled" active-text="啟用監測" /></el-form-item>

      <el-alert v-if="testResult" :type="testResult.ok ? 'success' : 'error'" :closable="false" show-icon
                :title="`${testResult.ok ? '測試成功' : '測試失敗'}：${testResult.message}${testResult.latency_ms != null ? `（${testResult.latency_ms} ms）` : ''}`" />
    </el-form>
    <template #footer>
      <el-button @click="runTest" :loading="testing" icon="VideoPlay">立即測試</el-button>
      <el-button @click="$emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" @click="save" :loading="saving">儲存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../api'
import { TYPE_OPTIONS } from '../utils'
import PushGuide from './PushGuide.vue'

const props = defineProps({ modelValue: Boolean, monitor: Object })
const emit = defineEmits(['update:modelValue', 'saved'])

const blank = () => ({
  id: null, name: '', type: 'http', target: '', backend_url: '', method: 'GET', expected_status: '200-399',
  keyword: '', timeout_sec: 10, interval_sec: 60, retries: 3, resend_interval_min: 60, ssl_warn_days: 14,
  follow_redirects: true, ignore_tls: false, enabled: true, tags: '', description: '', host_id: null, groups: [],
})
const form = reactive(blank())
const formRef = ref()
const groups = ref([])
const hosts = ref([])
const saving = ref(false)
const testing = ref(false)
const testResult = ref(null)

watch(() => props.modelValue, async (open) => {
  if (!open) return
  Object.assign(form, blank(), props.monitor ? JSON.parse(JSON.stringify(props.monitor)) : {})
  testResult.value = null
  ;[groups.value, hosts.value] = await Promise.all([http.get('/groups'), http.get('/hosts')])
  if (!props.monitor && groups.value.length === 1) form.groups = [{ group_id: groups.value[0].id, events: ['down', 'up', 'reminder'] }]
})

const router = useRouter()
const isPush = computed(() => form.type === 'push')
// 切到外部回報時套用較合理的預設：寬限 60 秒、異常一次就告警
watch(() => form.type, (t, old) => {
  if (t === 'push' && old && !form.id) {
    if (form.timeout_sec === 10) form.timeout_sec = 60
    if (form.retries === 3) form.retries = 1
  }
})
const isHttp = computed(() => ['http', 'keyword', 'proxy_pair'].includes(form.type))
const targetLabel = computed(() => ({
  http: '網址', keyword: '網址', proxy_pair: '對外網域網址', tcp: '主機:連接埠', ssl_cert: '網域（可加 :port）', docker: '容器名稱',
}[form.type]))
const targetPlaceholder = computed(() => ({
  http: 'https://example.com/health', keyword: 'https://example.com', proxy_pair: 'https://inspect.careloger.com',
  tcp: hostIp.value ? `${hostIp.value}:22` : '127.0.0.1:1433', ssl_cert: 'careloger.com', docker: 'nginx_proxy',
}[form.type]))
const hostIp = computed(() => hosts.value.find((h) => h.id === form.host_id)?.ip)

const rules = {
  name: [{ required: true, message: '請輸入名稱' }],
  target: [{ validator: (_, v, cb) => (form.type !== 'push' && !v ? cb(new Error('請輸入目標')) : cb()) }],
  backend_url: [{ validator: (_, v, cb) => (form.type === 'proxy_pair' && !v ? cb(new Error('請輸入後端網址')) : cb()) }],
  keyword: [{ validator: (_, v, cb) => (form.type === 'keyword' && !v ? cb(new Error('請輸入關鍵字')) : cb()) }],
}

const linkOf = (gid) => form.groups.find((g) => g.group_id === gid)
function toggleGroup(gid, on) {
  if (on) form.groups.push({ group_id: gid, events: ['down', 'up', 'reminder'] })
  else form.groups = form.groups.filter((g) => g.group_id !== gid)
}

const payload = () => {
  const { id, ...rest } = form
  if (rest.type === 'push' && !rest.target) rest.target = 'auto'  // 伺服器會產生密鑰
  return rest
}

async function regenerate() {
  await ElMessageBox.confirm('重新產生後舊的回報網址立即失效，對方主機的腳本必須改用新網址。確定？', '重新產生回報網址',
    { type: 'warning', confirmButtonText: '重新產生', cancelButtonText: '取消' })
  const r = await http.post(`/monitors/${form.id}/push-token`)
  form.target = r.push_url.split('/').pop()
  ElMessage.success('已產生新的回報網址')
  emit('saved')
}

async function runTest() {
  await formRef.value.validate()
  testing.value = true
  try { testResult.value = await http.post('/monitors/test', payload()) } finally { testing.value = false }
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    let created = null
    if (form.id) await http.put(`/monitors/${form.id}`, payload())
    else created = await http.post('/monitors', payload())
    ElMessage.success('已儲存')
    emit('update:modelValue', false)
    emit('saved')
    // 新建的外部回報：直接帶到詳情頁看回報網址與範例
    if (created?.push_url) router.push(`/monitors/${created.id}`)
  } finally { saving.value = false }
}
</script>

<style scoped>
.types { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 8px; width: 100%; }
.type-card {
  border: 1px solid var(--sm-border); border-radius: 10px; padding: 10px 12px; cursor: pointer;
  display: flex; flex-direction: column; gap: 3px; line-height: 1.35; transition: all .15s;
}
.type-card span { font-size: 12px; color: var(--sm-muted); }
.type-card:hover { border-color: var(--sm-accent); }
.type-card.on { border-color: var(--sm-accent); background: color-mix(in srgb, var(--sm-accent) 10%, transparent); }
.groups { display: flex; flex-direction: column; gap: 6px; width: 100%; }
.group-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
</style>
