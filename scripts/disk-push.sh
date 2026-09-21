#!/bin/sh
# 磁碟使用率檢查 → 回報到服務監控平台（外部回報 / 獨立服務）
#
# 用法：disk-push.sh <回報網址> [門檻%，預設 90] [掛載點...，預設 /]
# cron：*/5 * * * * /path/to/disk-push.sh "https://monitor.careloger.com/api/push/<密鑰>" 90 / >/dev/null 2>&1
#
# 任一掛載點使用率 ≥ 門檻 → status=down（平台依通知群組發 LINE / Email），否則 status=up。
# 設 DISK_PUSH_TEST=1 會在訊息前加上「（測試）」。
set -u
URL="${1:?缺少回報網址}"
THRESHOLD="${2:-90}"
if [ $# -ge 2 ]; then shift 2; else shift $#; fi
[ $# -eq 0 ] && set -- /

status=up
detail=""
for mp in "$@"; do
  # df -P：POSIX 格式，避免長裝置名稱換行
  line=$(df -P -h "$mp" 2>/dev/null | awk 'NR==2 {print $2, $3, $4, $5}') || line=""
  if [ -z "$line" ]; then
    status=down
    detail="${detail}${detail:+；}$mp 無法讀取"
    continue
  fi
  size=$(echo "$line" | cut -d' ' -f1)
  used=$(echo "$line" | cut -d' ' -f2)
  avail=$(echo "$line" | cut -d' ' -f3)
  pct=$(echo "$line" | cut -d' ' -f4 | tr -d '%')
  if [ "$pct" -ge "$THRESHOLD" ]; then
    status=down
    detail="${detail}${detail:+；}⚠ $mp 使用 ${pct}%（${used}/${size}，剩 ${avail}）"
  else
    detail="${detail}${detail:+；}$mp 使用 ${pct}%（剩 ${avail}）"
  fi
done

host=$(hostname)
if [ "$status" = down ]; then
  msg="$host 磁碟空間不足（門檻 ${THRESHOLD}%）：$detail"
else
  msg="$host 磁碟正常：$detail"
fi
[ "${DISK_PUSH_TEST:-0}" = 1 ] && msg="（測試）$msg"

curl -fsS -m 15 -G "$URL" --data-urlencode "status=$status" --data-urlencode "msg=$msg"
echo
