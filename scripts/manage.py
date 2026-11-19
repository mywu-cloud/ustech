#!/usr/bin/env python3
"""新增 / 刪除追蹤公司。
  python scripts/manage.py --add "NASDAQ:AVGO|Broadcom|博通" --add "NYSE:TSM|TSMC ADR|台積電ADR"
  python scripts/manage.py --remove INTC
add 格式：交易所:代號|英文名|中文名|標籤1,標籤2（英文名之後皆可省略），多筆以分號 ; 分隔
"""
import argparse
import json
import os

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "companies.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--add", action="append", default=[])
    ap.add_argument("--remove", action="append", default=[])
    a = ap.parse_args()
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    cos = cfg["companies"]
    for spec in [s.strip() for x in a.add for s in x.split(";") if s.strip()]:
        p = [s.strip() for s in spec.split("|")]
        sym = p[0].upper()
        if ":" not in sym:
            raise SystemExit(f"格式錯誤：{sym}，需為 交易所:代號，例 NASDAQ:AVGO")
        if any(c["symbol"] == sym for c in cos):
            print("已存在", sym)
            continue
        cos.append({"symbol": sym, "name": p[1] if len(p) > 1 and p[1] else sym.split(":")[1],
                    "name_zh": p[2] if len(p) > 2 else "",
                    "tags": [t for t in (p[3].split(",") if len(p) > 3 else []) if t]})
        print("新增", sym)
    for tk in [s.strip().upper() for x in a.remove for s in x.replace(";", ",").split(",") if s.strip()]:
        before = len(cos)
        cos[:] = [c for c in cos if c["symbol"].split(":")[1] != tk and c["symbol"] != tk]
        print("刪除" if len(cos) < before else "找不到", tk)
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()
