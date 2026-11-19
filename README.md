# 美股科技巨頭財報追蹤（mywu-cloud/ustech）

自動從 TradingView 抓取美股科技 / AI 公司每季財報（EPS、營收：預測 vs 實際、驚喜幅度、公布日期），
逐季累積成長期資料庫，並提供互動儀表板與 CSV / Excel 匯出。

- 網站：Cloudflare Pages（`public/` 為輸出目錄，無 build 指令）
- 更新：GitHub Actions 每日 3 次（台灣時間 07:23 / 12:23 / 21:23）→ 有變動才 commit → Pages 自動重新部署

## 功能
| 分頁 | 內容 |
|---|---|
| 季度財報 | 對照原 Excel 表：市值、EPS預測/已發布/驚喜/超出預期%、營收預測/實際、營收驚喜%、YoY、公布日期；可排序、切換財報季 |
| 個股長期趨勢 | 營收 + GAAP EPS（約 8 年）、營收YoY、毛利率/淨利率、歷季 EPS/營收驚喜 |
| 多公司比較 | 任選指標（營收YoY、毛利率、EPS驚喜%…）熱力圖 + 走勢線 |
| 即將公布 | 下一次財報日期、倒數天數、共識預測 |
| 追蹤名單 | 本機顯示/隱藏、永久新增/刪除說明 |

匯出：每頁右上「CSV」匯出目前畫面；`public/data/exports/` 內含
`earnings.xlsx`（各季、全部歷史、EPS驚喜矩陣、營收/YoY/EPS/毛利率/淨利率樞紐表）、`earnings_all.csv`、`earnings_<季>.csv`。

## 新增 / 刪除公司
1. GitHub → Actions → **Update earnings** → Run workflow
   - `add`：`NASDAQ:AVGO|Broadcom|博通;NYSE:TSM|TSMC ADR|台積電ADR`
   - `remove`：`INTC,QCOM`
2. 或直接編輯 `config/companies.json`。

刪除的公司歷史會保留（`active:false`），重新加入可延續。代號用 TradingView 格式 `交易所:代號`。

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
