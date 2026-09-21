<template>
  <div class="push-guide">
    <div class="sec">回報網址（請當作密碼保管）</div>
    <div class="copy-row">
      <el-input :model-value="url" readonly class="mono" />
      <el-button icon="CopyDocument" @click="copy(url)" />
      <el-button v-if="canRegenerate" icon="RefreshRight" @click="$emit('regenerate')">重新產生</el-button>
    </div>
    <div class="hint">
      參數：<code>status=up|down</code>（預設 up）、<code>msg=說明</code>（會出現在通知）、<code>ping=毫秒</code>（畫圖用）。
      超過「預期回報間隔 + 寬限秒數」沒回報，或回報 <code>down</code>，就會依通知群組發 LINE / Email。
    </div>
    <el-tabs v-model="tab" class="tabs">
      <el-tab-pane label="Linux（cron）" name="linux">
        <div class="sec">最簡單：每分鐘回報「還活著」（主機或排程停了就會告警）</div>
        <pre class="code">{{ linuxSimple }}</pre>
        <div class="sec">檢查自己的服務後回報（例：/usr/local/bin/push-monitor.sh，再用 cron 每分鐘執行）</div>
        <pre class="code">{{ linuxScript }}</pre>
      </el-tab-pane>
      <el-tab-pane label="Windows（PowerShell）" name="win">
        <div class="sec">C:\scripts\push-monitor.ps1：檢查 Windows 服務後回報</div>
        <pre class="code">{{ winScript }}</pre>
        <div class="sec">以系統管理員身分建立每分鐘執行的排程</div>
        <pre class="code">{{ winTask }}</pre>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({ token: String, canRegenerate: Boolean })
defineEmits(['regenerate'])
const tab = ref('linux')
const url = computed(() => `${location.origin}/api/push/${props.token}`)

const linuxSimple = computed(() => `# crontab -e
* * * * * curl -fsS -m 10 "${url.value}" >/dev/null 2>&1`)

const linuxScript = computed(() => `#!/bin/sh
URL="${url.value}"
if systemctl is-active --quiet nginx; then
  curl -fsS -m 10 "$URL?status=up&msg=nginx+running" >/dev/null
else
  curl -fsS -m 10 -G "$URL" --data-urlencode "status=down" \\
       --data-urlencode "msg=nginx 服務停止" >/dev/null
fi`)

const winScript = computed(() => `$Url = "${url.value}"
$Svc = "MSSQLSERVER"
try {
  $s = Get-Service -Name $Svc -ErrorAction Stop
  if ($s.Status -eq "Running") { $q = "status=up&msg=" + [uri]::EscapeDataString("$Svc running") }
  else { $q = "status=down&msg=" + [uri]::EscapeDataString("$Svc 狀態：$($s.Status)") }
} catch { $q = "status=down&msg=" + [uri]::EscapeDataString("找不到服務 $Svc") }
Invoke-RestMethod -Uri "$($Url)?$q" -TimeoutSec 10 | Out-Null`)

const winTask = `schtasks /create /tn "ServiceMonitorPush" /sc minute /mo 1 /ru SYSTEM /f ^
  /tr "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\scripts\\push-monitor.ps1"`

async function copy(text) {
  try { await navigator.clipboard.writeText(text); ElMessage.success('已複製') } catch { ElMessage.info('請手動選取複製') }
}
</script>

<style scoped>
.sec { font-size: 12px; color: var(--sm-muted); margin: 10px 0 4px; }
.copy-row { display: flex; gap: 6px; }
.hint { font-size: 12.5px; color: var(--sm-muted); line-height: 1.7; margin-top: 8px; }
.tabs { margin-top: 6px; }
.code {
  background: var(--sm-bg); border: 1px solid var(--sm-border); border-radius: 8px; padding: 10px 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px;
  white-space: pre; overflow-x: auto; margin: 0;
}
code { background: var(--sm-border); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
</style>
