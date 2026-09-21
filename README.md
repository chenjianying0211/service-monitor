# 服務監控平台（Service Monitor）

監測本機所有服務（網站、nginx 轉發、TCP 連接埠、SSL 憑證、Docker 容器），中斷 / 恢復時透過 **多個 LINE 官方帳號** 與 **Email** 通知指定的人。

- 後端：FastAPI + APScheduler + SQLAlchemy（MSSQL，既有容器 `mssql_2022_rtm_gdr1`，資料庫 `ServiceMonitor`，帳號 `monitor_app`）
- 前端：Vue 3 + Element Plus + ECharts（打包進同一個映像）
- 服務位址：`http://127.0.0.1:8090`（host 網路，只綁本機，透過 nginx 對外）

## 常用指令
```bash
cd ~/claude-projects/service-monitor
docker compose up -d --build     # 更新 / 啟動
docker compose logs -f           # 看紀錄
docker compose restart
```
帳號密碼存在資料庫 `users` 表（bcrypt 雜湊），可在「系統設定」新增管理員、改密碼。第一次啟動（表為空）會建立 `admin`，初始密碼印在 `docker compose logs`。
`.env` 內的 `FERNET_KEY` 用來加密 LINE Token / SMTP 密碼，**遺失就無法解密，請備份**。

## 監測類型
| 類型 | 說明 |
|---|---|
| HTTP / 關鍵字 | 狀態碼、回應時間、內容關鍵字 |
| 轉發服務（proxy_pair） | 同時打「對外網域」與「nginx 後端」，判斷是後端掛了還是轉發 / DNS / SSL 壞了 |
| TCP | host:port 可否連線 |
| SSL 憑證 | 剩餘天數低於門檻即告警 |
| Docker 容器 | running + healthcheck |

連續失敗 N 次 → 中斷（開事件、發通知）；持續中斷每 X 分鐘重複提醒；恢復時通知並附中斷時長。維護時段內不發通知。

## 主機分類
「主機」頁管理主機（名稱、IP、OS、區域、資源群組、VM 規格），監測項目可指定所屬主機，總覽頁預設依主機分區（可切換依標籤）。
Docker 容器監測只能看到平台所在主機（testlinux）的容器；其他主機請用 TCP / HTTP 監測。

## MCP 通道（讓 AI 新增 / 查詢監測）
- 網址：`https://monitor.careloger.com/mcp/`（Streamable HTTP，MCP SDK 2.x）
- 驗證：`Authorization: Bearer smk_...`（或 `X-API-Key`）。金鑰在「系統設定 → MCP 通道 / API 金鑰」產生，只存 SHA-256 雜湊，產生時顯示一次，可隨時撤銷。
- Claude Code：
  ```bash
  claude mcp add --transport http service-monitor https://monitor.careloger.com/mcp/ --header "Authorization: Bearer <金鑰>"
  ```
- 工具：`dashboard_summary`、`list_hosts`、`list_monitors`、`get_monitor`、`list_notify_groups`、`list_open_incidents`、`test_target`、`create_host`、`create_monitor`、`update_monitor`、`set_monitor_enabled`、`check_monitor_now`、`delete_monitor`
- 工具直接呼叫網頁 API 同一套函式，驗證規則、排程、通知群組行為與網頁一致。

## 通知設定流程
1. **LINE 官方帳號**：LINE Developers 建 Messaging API channel → 貼上 Channel Access Token + Secret → 把平台顯示的 Webhook URL 貼回 LINE 並開啟 Use webhook。
2. 使用者加好友、或把機器人拉進群組並輸入「綁定」→ 出現在「聯絡人 → 待啟用」→ 管理員啟用。
3. Email：新增 SMTP（Gmail 用應用程式密碼）→ 新增 Email 聯絡人。
4. 建立 **通知群組**（收件人 + 負責的監測項目），監測項目也可個別選擇群組與事件（中斷 / 恢復 / 提醒）。

> LINE Notify 已於 2025/3/31 停止，本平台使用 Messaging API push message，免費方案有每月則數上限，可在介面查詢額度。

## 對外開放（nginx，2026-09-21 已完成）
1. DNS 新增 A 紀錄：`monitor.careloger.com → 20.196.72.34`
2. 簽憑證（沿用 certbot_manager 的 webroot 方式）
3. 在 `~/nginx_proxy/nginx/conf.d/default.conf.template` 加入：
```nginx
server {
    listen 80;
    server_name monitor.careloger.com;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://$host$request_uri; }
}
server {
    listen 443 ssl;
    server_name monitor.careloger.com;
    ssl_certificate     /etc/letsencrypt/live/monitor.careloger.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/monitor.careloger.com/privkey.pem;
    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
4. `docker exec nginx_proxy nginx -t && docker exec nginx_proxy nginx -s reload`

## 憑證續期自動 reload nginx
certbot 續期成功時執行 `renewal-hooks/deploy/flag-nginx-reload.sh` 留下標記，主機 cron 每 15 分鐘執行
`~/nginx_proxy/scripts/reload-nginx-if-renewed.sh`：看到標記 → `nginx -t` 通過才 reload，紀錄在 `~/logs/nginx-cert-reload.log`。

## 已知限制
- 平台自己掛掉時無法通知自己：建議之後用外部免費服務定期打 `https://monitor.careloger.com/healthz`。
- 資料表以 `create_all` 建立，既有表的新欄位由 `backend/app/migrate.py` 補上（未導入 Alembic）。
