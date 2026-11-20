#!/usr/bin/env python3
"""
抓取 TradingView 美股科技/AI 公司財報資料，合併進長期歷史資料庫。

資料來源：TradingView scanner（https://scanner.tradingview.com/america/scan，非官方公開端點）
- 最新一季：EPS 預測 / 實際、營收預測 / 實際、公布日期、下一季預測與日期
- 歷史陣列（最多 32 季）：營收、GAAP 稀釋 EPS、淨利、毛利 → 用於長期趨勢

季度標籤 rq（Report Quarter，財報季）：以「公布日 − 60 天」所在的日曆季度命名，
對齊附表習慣（例：NVDA 8/26 公布 → 2026Q2；MU 6/25 公布 → 2026Q2）。

用法：
  python scripts/fetch.py                       # 線上抓取
  python scripts/fetch.py --fixture tests/x.json  # 用離線快照測試
"""
import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "companies.json")
SEED_GLOB = os.path.join(ROOT, "config")
OUT_DIR = os.path.join(ROOT, "public", "data")
OUT = os.path.join(OUT_DIR, "earnings.json")

SCAN_URL = "https://scanner.tradingview.com/america/scan"
COLUMNS = [
    "name", "description", "market_cap_basic",
    "earnings_per_share_fq", "earnings_per_share_forecast_fq",
    "revenue_fq", "revenue_forecast_fq",
    "earnings_release_date", "earnings_release_next_date",
    "earnings_per_share_forecast_next_fq", "revenue_forecast_next_fq",
    "fiscal_period_current", "fiscal_period_end_fq",
    "total_revenue_fq_h", "earnings_per_share_diluted_fq_h",
    "net_income_fq_h", "gross_profit_fq_h",
]
# 快照 fixture 中金額欄位以「百萬美元」儲存
MONEY = {"market_cap_basic", "revenue_fq", "revenue_forecast_fq", "revenue_forecast_next_fq",
         "total_revenue_fq_h", "net_income_fq_h", "gross_profit_fq_h"}
LAG_DAYS = 60
B = 1e9


# ---------- quarter helpers ----------
def rq_from_ts(ts):
    if not ts:
        return None
    d = dt.datetime.fromtimestamp(ts, dt.timezone.utc) - dt.timedelta(days=LAG_DAYS)
    return f"{d.year}Q{(d.month - 1) // 3 + 1}"


def rq_from_date(s):
    return rq_from_ts(dt.datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc).timestamp())


def rq_idx(rq):
    return int(rq[:4]) * 4 + int(rq[5]) - 1


def idx_rq(i):
    return f"{i // 4}Q{i % 4 + 1}"


def ts_date(ts):
    """美東時間日期（財報多在美東盤前/盤後公布）"""
    if not ts:
        return None
    return (dt.datetime.fromtimestamp(ts, dt.timezone.utc) - dt.timedelta(hours=5)).strftime("%Y-%m-%d")


def r(v, n=4):
    return None if v is None else round(float(v), n)


# ---------- fetch ----------
def fetch_live(symbols):
    body = json.dumps({"symbols": {"tickers": symbols}, "columns": COLUMNS}).encode()
    req = urllib.request.Request(SCAN_URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
        "User-Agent": "Mozilla/5.0 (ustech-earnings tracker)",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        j = json.load(resp)
    rows = {}
    for x in j.get("data", []):
        rows[x["s"]] = dict(zip(COLUMNS, x["d"]))
    return rows


def fetch_fixture(path):
    j = json.load(open(path, encoding="utf-8"))
    cols = j["cols"]
    rows = {}
    for x in j["data"]:
        row = {}
        for c, v in zip(cols, x["d"]):
            if c in MONEY and v is not None:
                v = [None if a is None else a * 1e6 for a in v] if isinstance(v, list) else v * 1e6
            row[c] = v
        rows[x["s"]] = row
    return rows


# ---------- merge ----------
def load_seeds():
    seeds = {}
    for fn in sorted(os.listdir(SEED_GLOB)):
        if fn.startswith("seed_") and fn.endswith(".csv"):
            for row in csv.DictReader(open(os.path.join(SEED_GLOB, fn), encoding="utf-8")):
                seeds.setdefault(row["ticker"], []).append(row)
    return seeds


def derive(rec, hist):
    e, a = rec.get("eps_est"), rec.get("eps_act")
    if e is not None and a is not None:
        rec["eps_surprise"] = r(a - e)
        rec["eps_surprise_pct"] = r((a - e) / abs(e) * 100, 2) if e else None
    re_, ra = rec.get("rev_est"), rec.get("rev_act") or rec.get("revenue")
    if re_ is not None and ra is not None and re_:
        rec["rev_surprise_pct"] = r((ra - re_) / abs(re_) * 100, 2)
    rev = rec.get("revenue") or rec.get("rev_act")
    if rev:
        if rec.get("gross_profit") is not None:
            rec["gross_margin"] = r(rec["gross_profit"] / rev * 100, 2)
        if rec.get("net_income") is not None:
            rec["net_margin"] = r(rec["net_income"] / rev * 100, 2)
    prev = hist.get(idx_rq(rq_idx(rec["rq"]) - 4))
    if prev:
        pr = prev.get("revenue") or prev.get("rev_act")
        if rev and pr:
            rec["rev_yoy"] = r((rev - pr) / abs(pr) * 100, 2)
        if rec.get("eps_gaap") is not None and prev.get("eps_gaap"):
            rec["eps_gaap_yoy"] = r((rec["eps_gaap"] - prev["eps_gaap"]) / abs(prev["eps_gaap"]) * 100, 2)
    rec["status"] = "reported" if (rec.get("eps_act") is not None or rec.get("revenue") is not None) else "pending"


def merge(db, cfg, rows, now_iso):
    seeds = load_seeds()
    active = set()
    for c in cfg["companies"]:
        sym = c["symbol"]
        tk = sym.split(":")[1]
        active.add(tk)
        co = db["companies"].setdefault(tk, {"ticker": tk, "history": {}})
        co.update({"symbol": sym, "name": c.get("name", tk), "name_zh": c.get("name_zh", ""),
                   "tags": c.get("tags", []), "active": True})
        hist = co["history"]
        row = rows.get(sym)

        # 1) seed（只補空缺，不覆蓋）
        for s in seeds.get(tk, []):
            rq = (s.get("rq") or "").strip() or rq_from_date(s["release_date"])
            rec = hist.setdefault(rq, {"rq": rq})
            for k_out, k_in, mul in (("eps_est", "eps_est", 1), ("eps_act", "eps_act", 1),
                                     ("rev_est", "rev_est_b", 1), ("rev_act", "rev_act_b", 1),
                                     ("market_cap", "market_cap_b", 1)):
                if rec.get(k_out) is None and s.get(k_in):
                    rec[k_out] = r(float(s[k_in]) * mul)
            if s.get("release_date"):
                rec.setdefault("release_date", s["release_date"])
            rec.setdefault("source", "seed")

        if not row:
            print(f"[warn] {sym}: TradingView 無資料", file=sys.stderr)
            continue

        co["description"] = row.get("description")
        co["market_cap"] = r((row.get("market_cap_basic") or 0) / B, 2)
        co["fiscal_period"] = row.get("fiscal_period_current")
        rq = rq_from_ts(row.get("earnings_release_date"))
        co["latest_rq"] = rq

        # 2) 最新一季快照（會覆蓋同季的預測/實際，以 TradingView 最新為準）
        if rq:
            rec = hist.setdefault(rq, {"rq": rq})
            rec.update({
                "fiscal_period": row.get("fiscal_period_current"),
                "release_date": ts_date(row.get("earnings_release_date")),
                "eps_est": r(row.get("earnings_per_share_forecast_fq")),
                "eps_act": r(row.get("earnings_per_share_fq")),
                "rev_est": r((row.get("revenue_forecast_fq") or 0) / B) if row.get("revenue_forecast_fq") else rec.get("rev_est"),
                "rev_act": r((row.get("revenue_fq") or 0) / B) if row.get("revenue_fq") else rec.get("rev_act"),
                "source": "tradingview",
            })
            rec.setdefault("captured_at", now_iso)
            rec.setdefault("market_cap", co["market_cap"])  # 首次抓到該季時的市值

            # 3) 歷史陣列 → 長期趨勢（h[0] = 最新一季）
            base = rq_idx(rq)
            arrs = {k: row.get(f) or [] for k, f in (("revenue", "total_revenue_fq_h"),
                                                    ("eps_gaap", "earnings_per_share_diluted_fq_h"),
                                                    ("net_income", "net_income_fq_h"),
                                                    ("gross_profit", "gross_profit_fq_h"))}
            n = max((len(v) for v in arrs.values()), default=0)
            for i in range(n):
                q = idx_rq(base - i)
                h = hist.setdefault(q, {"rq": q})
                for k, arr in arrs.items():
                    if i < len(arr) and arr[i] is not None:
                        h[k] = r(arr[i]) if k == "eps_gaap" else r(arr[i] / B)
                h.setdefault("source", "tradingview-history")

        # 4) 下一季（待公布）
        nts = row.get("earnings_release_next_date")
        nrq = rq_from_ts(nts)
        co["next"] = {
            "rq": nrq, "release_date": ts_date(nts),
            "eps_est": r(row.get("earnings_per_share_forecast_next_fq")),
            "rev_est": r((row.get("revenue_forecast_next_fq") or 0) / B) if row.get("revenue_forecast_next_fq") else None,
        }
        if nrq and nrq != rq:
            nrec = hist.setdefault(nrq, {"rq": nrq})
            if nrec.get("eps_act") is None:
                nrec.update({"release_date": co["next"]["release_date"], "eps_est": co["next"]["eps_est"],
                             "rev_est": co["next"]["rev_est"], "source": "tradingview-forecast"})

    for tk, co in db["companies"].items():
        if tk not in active:
            co["active"] = False  # 已移除：保留歷史，前端預設隱藏
        hist = co["history"]
        for q in sorted(hist, key=rq_idx):
            derive(hist[q], hist)
        co["history"] = {q: hist[q] for q in sorted(hist, key=rq_idx)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture")
    ap.add_argument("--fresh", action="store_true", help="不讀取既有資料，重建")
    a = ap.parse_args()

    cfg = json.load(open(CONFIG, encoding="utf-8"))
    syms = [c["symbol"] for c in cfg["companies"]]
    rows = fetch_fixture(a.fixture) if a.fixture else fetch_live(syms)
    print(f"抓到 {len(rows)}/{len(syms)} 檔")
    if not rows:
        sys.exit("TradingView 回傳 0 筆，停止（不覆寫資料）")

    db = {"companies": {}}
    if os.path.exists(OUT) and not a.fresh:
        db = json.load(open(OUT, encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    sig = lambda d: json.dumps({k: v for k, v in d.items() if k != "updated_at"}, sort_keys=True)
    before = sig(db)
    merge(db, cfg, rows, now)
    if sig(db) != before or "updated_at" not in db:
        db["updated_at"] = now  # 資料有變動才更新時間，避免無意義 commit
    else:
        print("資料無變動")
    db["source"] = "TradingView scanner (unofficial)"
    db["quarter_rule"] = f"rq = 公布日 − {LAG_DAYS} 天所在日曆季"
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT_DIR, "companies.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    print("寫入", OUT)


if __name__ == "__main__":
    main()
