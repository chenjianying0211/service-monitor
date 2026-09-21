<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>MCP 使用說明</h2>
        <div class="sub">讓 AI（Claude Code、Claude Desktop、VS Code、Cursor 等）用一般對話查詢與管理監控</div>
      </div>
      <el-button type="primary" icon="Key" @click="$router.push('/settings')">產生 / 管理金鑰</el-button>
    </div>

    <div class="card hero">
      <div class="hero-text">
        <b>這是什麼？</b>
        <p>
          MCP（Model Context Protocol）是讓 AI 工具連接外部系統的標準。連上之後，你可以直接對 AI 說
          「幫 mssql 主機加一個 1433 的監測，通知 IT 值班」，AI 會自己查主機、查通知群組、建立監測並回報結果。
        </p>
        <p class="muted">平台本身不呼叫任何 AI，也不消耗 AI 額度；用量算在你使用的 AI 工具帳號上。</p>
      </div>
      <div class="hero-url">
        <div class="lbl">MCP 網址</div>
        <div class="copy-row"><el-input :model-value="url" readonly class="mono" /><el-button icon="CopyDocument" @click="copy(url)" /></div>
        <div class="lbl">驗證方式</div>
        <code class="mono">Authorization: Bearer &lt;API 金鑰&gt;</code>
      </div>
    </div>

    <h3>① 取得 API 金鑰</h3>
    <div class="card">
      <ol class="steps">
        <li>由平台管理員到 <router-link to="/settings">系統設定 → MCP 通道 / API 金鑰</router-link> 按「產生金鑰」，名稱建議寫「使用者 - 裝置」，例如「小王 - 筆電」。</li>
        <li>金鑰（<code>smk_</code> 開頭）<b>只會顯示一次</b>，請立即交給使用者並妥善保存，視同密碼。</li>
        <li>一人一把：之後可在同一頁看到各金鑰最後使用時間，離職或遺失時單獨撤銷即可。</li>
      </ol>
    </div>

    <h3>② 加入你的 AI 工具</h3>
    <div class="card">
      <el-tabs v-model="client">
        <el-tab-pane label="Claude Code" name="cc">
          <p>在終端機執行（把 <code>&lt;API 金鑰&gt;</code> 換成你的金鑰）：</p>
          <CodeBlock :code="ccCmd" />
          <p>確認連線：執行 <code>claude mcp list</code> 看到 <code>service-monitor</code> 顯示 connected，或在 Claude Code 裡輸入 <code>/mcp</code>。</p>
          <p class="muted">加上 <code>--scope user</code> 可讓所有專案都能用；預設只在目前資料夾生效。</p>
        </el-tab-pane>
        <el-tab-pane label="專案共用（.mcp.json）" name="project">
          <p>團隊專案可把設定放在 repo 根目錄的 <code>.mcp.json</code>，金鑰用環境變數帶入，<b>不要把金鑰寫進 repo</b>：</p>
          <CodeBlock :code="projectJson" />
          <p>每個人在自己的環境設定：</p>
          <CodeBlock :code="envCmd" />
        </el-tab-pane>
        <el-tab-pane label="VS Code / Cursor / 其他" name="json">
          <p>支援 HTTP 傳輸與自訂 header 的 MCP client，可使用這段設定（各工具的設定檔位置請參考其文件）：</p>
          <CodeBlock :code="genericJson" />
        </el-tab-pane>
        <el-tab-pane label="不支援自訂 header 的 client" name="remote">
          <p>部分 client（例如只能加 stdio 伺服器的桌面 App）無法直接帶 header，可透過 <code>mcp-remote</code> 轉接（需安裝 Node.js）：</p>
          <CodeBlock :code="remoteJson" />
        </el-tab-pane>
      </el-tabs>
    </div>

    <h3>③ 開始使用：可以這樣對 AI 說</h3>
    <div class="examples">
      <div v-for="g in examples" :key="g.title" class="card ex-group">
        <div class="ex-title"><el-icon><component :is="g.icon" /></el-icon>{{ g.title }}</div>
        <button v-for="e in g.items" :key="e" class="ex" @click="copy(e)" title="點一下複製">
          <span>{{ e }}</span><el-icon><CopyDocument /></el-icon>
        </button>
      </div>
    </div>

    <h3>工具清單 <span class="muted small">（即時讀取自伺服器，共 {{ tools.length }} 個）</span></h3>
    <div class="card" style="padding:0">
      <el-table :data="tools" v-loading="loading">
        <el-table-column label="工具" width="210">
          <template #default="{ row }"><span class="mono tool-name">{{ row.name }}</span></template>
        </el-table-column>
        <el-table-column label="類型" width="90">
          <template #default="{ row }">
            <el-tag size="small" :type="KIND[row.kind].tag">{{ KIND[row.kind].label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="說明" min-width="280">
          <template #default="{ row }"><div class="desc">{{ row.description }}</div></template>
        </el-table-column>
        <el-table-column label="參數" min-width="300">
          <template #default="{ row }">
            <span v-if="!row.params.length" class="muted">無</span>
            <div v-for="p in row.params" :key="p.name" class="param">
              <span class="mono" :class="{ req: p.required }">{{ p.name }}</span>
              <span class="muted mono ptype">{{ p.type }}</span>
              <el-tag v-if="p.required" size="small" type="danger" effect="plain">必填</el-tag>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <h3>注意事項</h3>
    <div class="card">
      <ul class="notes">
        <li><b>刪除會直接生效</b>：<code>delete_monitor</code> 會連同歷史紀錄刪除，多數 AI 工具在執行前會詢問確認，請看清楚再允許。</li>
        <li><b>主機與通知群組用名稱指定</b>：AI 會先用 <code>list_hosts</code>、<code>list_notify_groups</code> 查正確名稱；名稱打錯會收到現有清單。</li>
        <li><b>Docker 容器</b>只能監測平台所在主機（testlinux）；其他主機請用 TCP / HTTP，或「外部回報」。</li>
        <li><b>外部回報（push）</b>建立後會回傳 <code>push_url</code>，把它設定到對方主機的排程即可。</li>
        <li>AI 做的變更與網頁操作完全相同，會立刻出現在總覽與監測列表。</li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { ElButton, ElMessage } from 'element-plus'
import http from '../api'

async function copy(text) {
  try { await navigator.clipboard.writeText(text); ElMessage.success('已複製') } catch { ElMessage.info('請手動選取複製') }
}

// 小型程式碼區塊（右上角複製）
const CodeBlock = defineComponent({
  props: { code: String },
  setup: (props) => () => h('div', { class: 'code-wrap' }, [
    h('pre', { class: 'code' }, props.code),
    h(ElButton, { class: 'code-copy', size: 'small', icon: 'CopyDocument', onClick: () => copy(props.code) }),
  ]),
})

const KIND = {
  read: { label: '唯讀', tag: 'success' },
  write: { label: '寫入', tag: 'warning' },
  destructive: { label: '刪除', tag: 'danger' },
}

const client = ref('cc')
const tools = ref([])
const loading = ref(false)
const url = ref(`${location.origin}/mcp/`)

onMounted(async () => {
  loading.value = true
  try {
    const r = await http.get('/mcp-info')
    tools.value = r.tools
    url.value = r.url
  } finally { loading.value = false }
})

const ccCmd = computed(() => `claude mcp add --transport http service-monitor ${url.value} \\
  --header "Authorization: Bearer <API 金鑰>"`)

const projectJson = computed(() => JSON.stringify({ mcpServers: { 'service-monitor': {
  type: 'http', url: url.value, headers: { Authorization: 'Bearer ${SERVICE_MONITOR_KEY}' } } } }, null, 2))

const envCmd = `# Linux / macOS（寫進 ~/.bashrc 或 ~/.zshrc）
export SERVICE_MONITOR_KEY="smk_..."

# Windows PowerShell
setx SERVICE_MONITOR_KEY "smk_..."`

const genericJson = computed(() => JSON.stringify({ mcpServers: { 'service-monitor': {
  type: 'http', url: url.value, headers: { Authorization: 'Bearer <API 金鑰>' } } } }, null, 2))

const remoteJson = computed(() => JSON.stringify({ mcpServers: { 'service-monitor': {
  command: 'npx',
  args: ['-y', 'mcp-remote', url.value, '--header', 'Authorization:${AUTH_HEADER}'],
  env: { AUTH_HEADER: 'Bearer <API 金鑰>' } } } }, null, 2))

const examples = [
  { title: '查詢狀態', icon: 'View', items: [
    '現在監控平台有沒有服務中斷？',
    '列出 testlinux 上所有監測項目和狀態',
    'inspect.careloger.com 最近 30 天的可用率和中斷紀錄？',
    '目前有哪些進行中的中斷事件？',
  ] },
  { title: '新增監測', icon: 'Plus', items: [
    '幫 mssql 主機（13.78.194.229）加一個 1433 的 TCP 監測，通知 IT 值班',
    '監測 https://example.com，頁面要包含「登入」兩個字，每 5 分鐘檢查一次',
    '幫 windowstest 建一個外部回報監測，每 5 分鐘回報一次，給我回報網址和 PowerShell 範例',
    '新增主機 ahfuserver2，IP 20.1.2.3，Linux，Korea Central',
  ] },
  { title: '調整與管理', icon: 'Setting', items: [
    '把所有 SSL 憑證監測的警戒天數改成 21 天',
    '暫停 careloger.com 的監測，維護完我再叫你恢復',
    '立即重新檢查所有中斷中的項目',
    '先試打 10.0.0.5:3389 看看連不連得到，通了再幫我建立監測',
  ] },
]
</script>

<style scoped>
h3 { font-size: 16px; margin: 22px 0 10px; }
.small { font-size: 12.5px; font-weight: 400; }
.hero { display: grid; grid-template-columns: 1.4fr 1fr; gap: 20px; }
.hero p { margin: 8px 0 0; line-height: 1.7; }
.hero-url { display: flex; flex-direction: column; gap: 6px; }
.lbl { font-size: 12px; color: var(--sm-muted); }
.copy-row { display: flex; gap: 6px; }
.steps, .notes { margin: 0; padding-left: 20px; line-height: 1.9; }
p { line-height: 1.7; margin: 6px 0; }
code { background: var(--sm-border); padding: 1px 6px; border-radius: 4px; font-size: 12.5px; }
:deep(.code-wrap) { position: relative; margin: 6px 0 10px; }
:deep(.code) {
  background: var(--sm-bg); border: 1px solid var(--sm-border); border-radius: 8px; padding: 12px 44px 12px 14px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px;
  white-space: pre; overflow-x: auto; margin: 0;
}
:deep(.code-copy) { position: absolute; top: 8px; right: 8px; }
.examples { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
.ex-group { display: flex; flex-direction: column; gap: 6px; }
.ex-title { display: flex; align-items: center; gap: 6px; font-weight: 650; margin-bottom: 4px; }
.ex {
  display: flex; justify-content: space-between; align-items: center; gap: 8px; text-align: left;
  padding: 8px 10px; border: 1px solid var(--sm-border); border-radius: 8px; background: transparent;
  color: var(--el-text-color-primary); font: inherit; font-size: 13px; cursor: pointer; line-height: 1.5;
}
.ex:hover { border-color: var(--sm-accent); color: var(--sm-accent); }
.ex .el-icon { flex-shrink: 0; opacity: .5; }
.tool-name { font-weight: 600; }
.desc { white-space: pre-line; line-height: 1.6; font-size: 13px; }
.param { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; line-height: 1.9; }
.param .req { font-weight: 600; }
.ptype { font-size: 11.5px; }
@media (max-width: 800px) { .hero { grid-template-columns: 1fr; } }
</style>
