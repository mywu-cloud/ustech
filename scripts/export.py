#!/usr/bin/env python3
"""由 public/data/earnings.json 產生 CSV / XLSX 匯出檔（台股慣例：紅=優於預期/成長，綠=低於預期/衰退）"""
import csv
import json
import os

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "public", "data", "earnings.json")
EXP = os.path.join(ROOT, "public", "data", "exports")

FIELDS = [
    ("rq", "財報季"), ("ticker", "代號"), ("name", "商品"), ("name_zh", "中文名"),
    ("fiscal_period", "公司財年季"), ("release_date", "公布日期"), ("status", "狀態"),
    ("market_cap", "市值(B)"), ("eps_est", "EPS預測"), ("eps_act", "已發布EPS"),
    ("eps_surprise", "驚喜"), ("eps_surprise_pct", "超出預期%"),
    ("rev_est", "預測營收(B)"), ("rev_act", "實際營收(B)"), ("rev_surprise_pct", "營收驚喜%"),
    ("revenue", "營收(B,財報)"), ("rev_yoy", "營收YoY%"), ("eps_gaap", "GAAP EPS"),
    ("eps_gaap_yoy", "GAAP EPS YoY%"), ("net_income", "淨利(B)"), ("gross_margin", "毛利率%"),
    ("net_margin", "淨利率%"),
]
RED, GREEN = "D7263D", "1B9E4B"
HDR = PatternFill("solid", fgColor="FFB000")
THIN = Side(style="thin", color="999999")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def qkey(q):
    return int(q[:4]) * 4 + int(q[5])


def rows_all(db, active_only=True):
    out = []
    for tk, co in db["companies"].items():
        if active_only and not co.get("active", True):
            continue
        for q, h in co["history"].items():
            out.append({**h, "ticker": tk, "name": co["name"], "name_zh": co.get("name_zh", "")})
    out.sort(key=lambda x: (-qkey(x["rq"]), x.get("release_date") or "9999", x["ticker"]))
    return out


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM：Excel 開啟中文不亂碼
        w = csv.writer(f)
        w.writerow([z for _, z in FIELDS])
        for r in rows:
            w.writerow(["" if r.get(k) is None else r.get(k) for k, _ in FIELDS])


def style_header(ws, ncol, row=1):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(bold=True)
        cell.fill = HDR
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX


def posneg(ws, rng):
    ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=["0"], font=Font(color=RED, bold=True)))
    ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan", formula=["0"], font=Font(color=GREEN, bold=True)))


def sheet_table(ws, rows, fields):
    ws.append([z for _, z in fields])
    style_header(ws, len(fields))
    for r in rows:
        ws.append([r.get(k) for k, _ in fields])
    n = len(rows) + 1
    for i, (k, z) in enumerate(fields, 1):
        col = get_column_letter(i)
        ws.column_dimensions[col].width = max(10, min(26, len(z) * 2 + 2))
        if k.endswith("pct") or k.endswith("yoy") or k == "eps_surprise":
            posneg(ws, f"{col}2:{col}{n}")
            for c in ws[f"{col}2:{col}{n}"]:
                c[0].number_format = '0.00'
        elif k in ("eps_est", "eps_act", "eps_gaap"):
            for c in ws[f"{col}2:{col}{n}"]:
                c[0].number_format = '0.00'
        elif k in ("market_cap", "rev_est", "rev_act", "revenue", "net_income"):
            for c in ws[f"{col}2:{col}{n}"]:
                c[0].number_format = '#,##0.00'
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(fields))}{n}"


def pivot(ws, db, field, title, fmt="0.00", color=False):
    cos = [(tk, c) for tk, c in db["companies"].items() if c.get("active", True)]
    qs = sorted({q for _, c in cos for q, h in c["history"].items() if h.get(field) is not None}, key=qkey)
    ws.append([title] + qs)
    style_header(ws, len(qs) + 1)
    for tk, c in cos:
        ws.append([f"{tk} {c.get('name_zh','')}"] + [c["history"].get(q, {}).get(field) for q in qs])
    ws.column_dimensions["A"].width = 18
    for i in range(2, len(qs) + 2):
        ws.column_dimensions[get_column_letter(i)].width = 10
    rng = f"B2:{get_column_letter(len(qs)+1)}{len(cos)+1}"
    for row in ws[rng]:
        for c in row:
            c.number_format = fmt
    if color:
        posneg(ws, rng)
    ws.freeze_panes = "B2"


def main():
    db = json.load(open(DATA, encoding="utf-8"))
    os.makedirs(EXP, exist_ok=True)
    allrows = rows_all(db)
    write_csv(os.path.join(EXP, "earnings_all.csv"), allrows)

    reported = sorted({r["rq"] for r in allrows if r.get("eps_est") is not None}, key=qkey)
    for q in reported:
        write_csv(os.path.join(EXP, f"earnings_{q}.csv"), [r for r in allrows if r["rq"] == q])
    latest = max((r["rq"] for r in allrows if r.get("eps_act") is not None and r.get("eps_est") is not None),
                 key=qkey, default=None)

    wb = Workbook()
    ws = wb.active
    ws.title = "說明"
    for line in [
        ["美股科技 / AI 巨頭財報追蹤"],
        ["更新時間 (UTC)", db.get("updated_at")],
        ["資料來源", db.get("source")],
        ["財報季規則", db.get("quarter_rule")],
        ["單位", "B = 十億美元；EPS 預測/已發布為 TradingView 調整後 EPS；GAAP EPS 為稀釋每股盈餘"],
        ["顏色", "紅色 = 優於預期 / 成長；綠色 = 低於預期 / 衰退（台股慣例）"],
        ["免責聲明", "本資料僅供研究參考，不構成任何投資建議；資料可能延遲或有誤，請以公司公告為準。"],
    ]:
        ws.append(line)
    ws["A1"].font = Font(bold=True, size=14)
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 80

    short = [f for f in FIELDS if f[0] in ("name", "name_zh", "ticker", "market_cap", "eps_est", "eps_act",
                                            "eps_surprise", "eps_surprise_pct", "rev_est", "rev_act",
                                            "rev_surprise_pct", "release_date", "status")]
    for q in reversed(reported[-6:]):
        rs = sorted([r for r in allrows if r["rq"] == q], key=lambda x: x.get("release_date") or "9999")
        sheet_table(wb.create_sheet(f"{q}" + ("(最新)" if q == latest else "")), rs, short)
    sheet_table(wb.create_sheet("全部歷史"), allrows, FIELDS)
    pivot(wb.create_sheet("EPS驚喜%矩陣"), db, "eps_surprise_pct", "EPS驚喜%", color=True)
    pivot(wb.create_sheet("營收趨勢(B)"), db, "revenue", "營收(B)", "#,##0.00")
    pivot(wb.create_sheet("營收YoY%"), db, "rev_yoy", "營收YoY%", color=True)
    pivot(wb.create_sheet("GAAP EPS趨勢"), db, "eps_gaap", "GAAP EPS", color=False)
    pivot(wb.create_sheet("毛利率%"), db, "gross_margin", "毛利率%")
    pivot(wb.create_sheet("淨利率%"), db, "net_margin", "淨利率%", color=True)
    wb.save(os.path.join(EXP, "earnings.xlsx"))
    print("匯出完成：", sorted(os.listdir(EXP)))


if __name__ == "__main__":
    main()
