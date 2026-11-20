# 美股科技巨頭財報追蹤（mywu-cloud/ustech）

自動從 TradingView 抓取美股科技 / AI 公司每季財報（EPS、營收：預測 vs 實際、驚喜幅度、公布日期），
逐季累積成長期資料庫，並提供互動儀表板與 CSV / Excel 匯出。

- 網站：Cloudflare Pages（`public/` 為輸出目錄，無 build 指令）— <https://ustech.pages.dev>，並嵌入 PiNNCafe 聊股室 <https://stock.pinncafe.com/#ustech>「美股財報」分頁
- 更新：GitHub Actions 每日 3 次（台灣時間 07:23 / 12:23 / 21:23）→ 有變動才 commit → Pages 自動重新部署

## 功能
| 分頁 | 內容 |
|---|---|
| 季度財報 | 對照原 Excel 表：市值、EPS預測/已發布/驚喜/超出預期%、營收預測/實際、營收驚喜%、YoY、公布日期；可排序、切換財報季 |
| 個股長期趨勢 | 營收 + GAAP EPS（約 8 年）、營收YoY、毛利率/淨利率、歷季 EPS/營收驚喜 |
| 多公司比較 | 任選指標（營收YoY、毛利率、EPS驚喜%…）熱力圖 + 走勢線 |
| 即將公布 | 下一次財報日期、倒數天數、共識預測 |
| 追蹤名單 | 本機顯示 / 隱藏、快速新增（輸入代號自動查交易所與英文名）、移除 / 重新加入、管理表單（密碼保護，永久新增 / 更新 / 刪除） |

匯出：每頁右上「CSV」匯出目前畫面；`public/data/exports/` 內含
`earnings.xlsx`（各季、全部歷史、EPS驚喜矩陣、營收/YoY/EPS/毛利率/淨利率樞紐表）、`earnings_all.csv`、`earnings_<季>.csv`。

## 新增 / 刪除公司

### 網站操作（建議）
在網站「**追蹤名單**」分頁（操作方式與 [TW-AI](https://stock.pinncafe.com/#twai) 相同；也可從 <https://stock.pinncafe.com/#ustech> 進入）：

| 動作 | 操作 |
|---|---|
| 新增 | 上方「**快速新增**」輸入代號（`AVGO` 或 `NYSE:TSM`），可填中文名、標籤 → 按「＋ 加入」或 Enter；交易所與英文名會向 TradingView 查詢自動帶出。或直接在下方表單填一列（TradingView 代碼 / 英文名 / 中文名 / 標籤），按「＋ 再加一列」可多筆 |
| 更新 | 填入已存在的代號 → 只更新有填的欄位（例如改中文名或標籤） |
| 刪除 | 名單第 2 欄按「**移除**」；或先取消勾選數家，再按「**取消勾選的 → 排入刪除**」一次加入 |
| 重新加入 | 已移除公司第 2 欄按「**重新加入**」（帶出原名稱與標籤） |
| 送出 | 下方輸入**管理密碼** → 「送出」→ 確認；約 3–10 分鐘後重新整理即可看到。「查看執行狀態」可看最近 5 次執行結果 |

- 僅「取消勾選」＝只在自己瀏覽器隱藏（存 localStorage），**不會**刪除。
- 標籤以 `,` 分隔（全形「，、」會自動轉換），例 `半導體,AI`。
- 刪除的公司歷史保留（`active:false`），重新加入可延續趨勢。

### 運作方式
```
網站表單 ──POST /api/manage──▶ Cloudflare Pages Function（functions/api/manage.js）
                                 │ 驗證 ADMIN_PASSWORD
                                 ▼
             GitHub API：觸發 workflow_dispatch「Update earnings」（inputs: add / remove）
                                 ▼
        scripts/manage.py 改 config/companies.json → fetch.py 抓 TradingView → export.py → commit
                                 ▼
                     Cloudflare Pages 自動重新部署

快速新增 ──GET /api/lookup?q=AVGO──▶ functions/api/lookup.js ──▶ TradingView scanner（查交易所 / 英文名，不需密碼）
```
GitHub token 只存在 Cloudflare Secret，不會出現在前端；沒有密碼無法送出。
`GET /api/manage`（header `X-Admin-Password`）回傳最近 5 次手動執行狀態。

### 一次性設定
1. **GitHub token**：個人頭像 → Settings → Developer settings → Personal access tokens → **Fine-grained tokens**（或直接開 <https://github.com/settings/personal-access-tokens/new>）
   - Repository access：**Only select repositories** → `mywu-cloud/ustech`
   - Repository permissions：**Actions: Read and write**（其他不用開）
2. **Cloudflare Pages** → ustech → 設定 → 變數與機密（**Production**），類型 **Secret**：
   - `GH_TOKEN`（或 `USTECH_TOKEN`）：上一步的 token（`github_pat_` 開頭）
   - `ADMIN_PASSWORD`：管理密碼（建議 16 字以上；區分大小寫）
   - 選填：`GH_REPO`（預設 `mywu-cloud/ustech`）、`GH_WORKFLOW`（預設 `update.yml`）、`GH_REF`（預設 `main`）
3. **重新部署**：部署 → 最新一筆「⋯」→ **重試部署**。⚠️ 變數只套用到之後的部署，**每次修改變數都要重新部署**（或推一個 commit）。

### 疑難排解
| 訊息 | 原因 / 處理 |
|---|---|
| 伺服器尚未設定 GH_TOKEN / ADMIN_PASSWORD | 變數未設定、設在 Preview、名稱拼錯，或設定後尚未重新部署 |
| 密碼錯誤（你輸入了 N 個字元） | 與 `ADMIN_PASSWORD` 不符。比對前兩邊都會去前後空白 / 換行 / 外層引號、全形轉半形，但**區分大小寫**。核對字數；避免瀏覽器自動填入別的密碼；改密碼後記得重新部署 |
| GitHub 回應 401 | token 過期或錯誤 → 重新產生並更新 `GH_TOKEN`，再重新部署 |
| GitHub 回應 403 / 404 | token 沒選到 ustech 或 Actions 權限不是 Read and write |
| 查不到 XXX 的交易所 | TradingView 查詢失敗或代號不存在 → 改輸入 `交易所:代號`（可在 TradingView 個股頁網址看到，例 `NASDAQ-AVGO` → `NASDAQ:AVGO`） |
| 執行失敗（查看執行狀態 ❌） | 點「詳細」看 Actions log；常見為代號格式錯誤 |

### 備用方式（不經網站）
- GitHub → Actions → **Update earnings** → Run workflow
  - `add`：`交易所:代號|英文名|中文名|標籤1,標籤2`，多筆以 `;` 分隔（英文名之後皆可省略；代號已存在則更新有填欄位）
    例：`NASDAQ:AVGO|Broadcom|博通|半導體,AI;NYSE:TSM|TSMC ADR|台積電ADR`
  - `remove`：`INTC,QCOM`
- 或直接編輯 `config/companies.json`。

## 資料規則
- **財報季 rq** = 公布日 − 60 天所在日曆季（例：NVDA 8/26、MU 6/25 → 2026Q2），讓不同財年制的公司可放在同一季比較；公司自身財年季另存於 `fiscal_period`。
- **EPS 預測 / 已發布**：TradingView 調整後 EPS（與共識同口徑）；**GAAP EPS**：稀釋每股盈餘。
- 預測值無歷史回溯，從 2026Q2（`config/seed_2026Q2.csv`，取自原手工表）起逐季累積；營收、GAAP EPS、淨利、毛利可回溯約 32 季。
- 資料來源為 TradingView 非官方 scanner 端點，欄位若變動需調整 `scripts/fetch.py`。

## 本機執行
```bash
pip install openpyxl
python scripts/fetch.py            # 抓取並合併
python scripts/export.py           # 產生 CSV / XLSX
python -m http.server -d public    # 預覽 http://localhost:8000
```

> ⚠️ 本專案資料僅供研究參考，不構成投資建議；請以公司正式公告為準。

## 檔案結構
| 路徑 | 說明 |
|---|---|
| `public/index.html` | 網站（單檔 HTML + Chart.js） |
| `functions/api/manage.js` | Cloudflare Pages Function：管理表單後端（觸發 workflow） |
| `functions/api/lookup.js` | Cloudflare Pages Function：快速新增查代號 |
| `config/companies.json` | 追蹤名單設定 |
| `scripts/manage.py` | 新增 / 更新 / 刪除名單（workflow 呼叫） |
| `scripts/fetch.py` | 抓 TradingView，合併成 `public/data/earnings.json` |
| `scripts/export.py` | 匯出 CSV / Excel |
| `.github/workflows/update.yml` | 每日 3 次排程 + 手動新增 / 刪除 |

> ⚠️ 資料僅供研究參考，不構成投資建議；請以公司正式公告為準。
