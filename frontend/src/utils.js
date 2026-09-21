import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-tw'

dayjs.extend(relativeTime)
dayjs.locale('zh-tw')

export const TYPE_OPTIONS = [
  { value: 'http', label: 'HTTP(S) 網址', desc: '檢查網址回應狀態碼與回應時間' },
  { value: 'keyword', label: 'HTTP 關鍵字', desc: '網頁內容需包含指定文字' },
  { value: 'proxy_pair', label: '轉發服務（nginx）', desc: '同時檢查網域與後端，分辨是後端掛還是轉發壞' },
  { value: 'tcp', label: 'TCP 連接埠', desc: '檢查 host:port 是否可連線（資料庫、SSH…）' },
  { value: 'ssl_cert', label: 'SSL 憑證到期', desc: '憑證剩餘天數低於門檻時告警' },
  { value: 'docker', label: 'Docker 容器', desc: '容器是否運行中、健康檢查是否正常' },
]
export const TYPE_LABEL = Object.fromEntries(TYPE_OPTIONS.map((o) => [o.value, o.label]))

export const STATUS = {
  UP: { label: '正常', color: 'var(--sm-up)', tag: 'success' },
  DOWN: { label: '中斷', color: 'var(--sm-down)', tag: 'danger' },
  PENDING: { label: '異常中', color: 'var(--sm-pending)', tag: 'warning' },
  PAUSED: { label: '已暫停', color: 'var(--sm-paused)', tag: 'info' },
  UNKNOWN: { label: '等待檢查', color: 'var(--sm-paused)', tag: 'info' },
}

export const EVENT_LABEL = { down: '中斷', up: '恢復', reminder: '重複提醒', test: '測試' }
export const CONTACT_TYPE = { line_user: 'LINE 個人', line_group: 'LINE 群組', email: 'Email' }

export const fmtTime = (s) => (s ? dayjs(s).format('YYYY-MM-DD HH:mm:ss') : '—')
export const fromNow = (s) => (s ? dayjs(s).fromNow() : '—')
export const fmtPct = (v) => (v === null || v === undefined ? '—' : `${v.toFixed(v === 100 ? 0 : 2)}%`)

export function fmtDuration(sec) {
  if (sec == null) return '—'
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60)
  if (d) return `${d} 天 ${h} 小時`
  if (h) return `${h} 小時 ${m} 分`
  if (m) return `${m} 分`
  return `${sec} 秒`
}

export function uptimeClass(v) {
  if (v == null) return ''
  if (v >= 99.5) return 'good'
  if (v >= 95) return 'warn'
  return 'bad'
}
