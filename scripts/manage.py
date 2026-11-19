#!/usr/bin/env python3
"""新增 / 更新 / 刪除追蹤公司（由網站「追蹤名單」管理表單或 GitHub Actions 呼叫）。
  python scripts/manage.py --add "NASDAQ:AVGO|Broadcom|博通|半導體,AI;NYSE:TSM|TSMC ADR|台積電ADR" --remove "INTC,QCOM"
add 格式：交易所:代號|英文名|中文名|標籤1,標籤2（英文名之後皆可省略），多筆以分號 ; 分隔
  - 代號已存在 → 只更新有填的欄位（可用來改中文名 / 標籤）
  - 只填代號沒填交易所（例 AVGO）→ 自動向 TradingView 查詢 NASDAQ / NYSE / AMEX
  - 未填英文名 → 由 TradingView 名稱自動補上
remove：代號，多筆以逗號 , 分隔（歷史資料保留，標記為停用，重新加入可延續）
"""
import argparse
import json
import os
import re
import unicodedata
import urllib.request

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "companies.json")
SCAN_URL = "https://scanner.tradingview.com/america/scan"
EXCH = ["NASDAQ", "NYSE", "AMEX", "NYSEARCA", "CBOE"]
SYM = re.compile(r"^([A-Z]{2,10}:)?[A-Z][A-Z0-9.]{0,9}$")


def lookup(tickers):
    """回傳 {完整代碼: 英文名}；查詢失敗回傳 {}"""
    body = json.dumps({"symbols": {"tickers": tickers}, "columns": ["description", "market_cap_basic"]}).encode()
    req = urllib.request.Request(SCAN_URL, data=body, method="POST", headers={
        "Content-Type": "application/json",
        "Origin": "https://www.tradingview.com",
        "Referer": "https://www.tradingview.com/",
        "User-Agent": "Mozilla/5.0 (ustech-earnings tracker)",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            rows = json.load(resp).get("data", [])
    except Exception as e:  # noqa: BLE001
        print("TradingView 查詢失敗：", e)
        return {}
    rows.sort(key=lambda x: -(x["d"][1] or 0))
    return {x["s"]: x["d"][0] for x in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", action="append", default=[])
    ap.add_argument("--remove", action="append", default=[])
    a = ap.parse_args()
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    cos = cfg["companies"]
    nf = lambda s: unicodedata.normalize("NFKC", s).strip()

    for spec in [nf(s) for x in a.add for s in nf(x).split(";") if s.strip()]:
        p = [s.strip() for s in spec.split("|")] + [""] * 4
        sym = p[0].upper().replace("-", ":", 1)
        if not SYM.match(sym):
            raise SystemExit(f"代號格式錯誤：{p[0]}，需為 交易所:代號，例 NASDAQ:AVGO")
        tk = sym.split(":")[-1]
        old = next((c for c in cos if c["symbol"].split(":")[1] == tk), None)
        if ":" not in sym:
            if old:
                sym = old["symbol"]
            else:
                hits = lookup([f"{e}:{tk}" for e in EXCH])
                if not hits:
                    raise SystemExit(f"TradingView 找不到 {tk}，請改填 交易所:代號（例 NASDAQ:{tk}）")
                sym = next(iter(hits))
                if not p[1]:
                    p[1] = hits[sym]
        elif not p[1] and not old:
            p[1] = lookup([sym]).get(sym, "")
        tags = [t.strip() for t in re.split(r"[,/、]", p[3]) if t.strip()]
        if old:  # 已存在 → 只更新有填的欄位
            old["symbol"] = sym
            if p[1]:
                old["name"] = p[1]
            if p[2]:
                old["name_zh"] = p[2]
            if tags:
                old["tags"] = tags
            print("更新", sym)
        else:
            cos.append({"symbol": sym, "name": p[1] or tk, "name_zh": p[2], "tags": tags})
            print("新增", sym, p[1])

    for tk in [nf(s).upper() for x in a.remove for s in x.replace(";", ",").split(",") if s.strip()]:
        before = len(cos)
        cos[:] = [c for c in cos if c["symbol"].split(":")[1] != tk and c["symbol"] != tk]
        print("刪除" if len(cos) < before else "找不到", tk)

    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
