// Cloudflare Pages Function：/api/lookup?q=AVGO 或 ?q=NASDAQ:AVGO
// 「快速新增」用：向 TradingView scanner（與 scripts/fetch.py 同一端點）查詢代號，
// 回傳完整 TradingView 代碼、英文名稱與市值，名稱自動帶出。不需密碼、唯讀。

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": status === 200 ? "public, max-age=86400" : "no-store" },
  });

const EXCH = ["NASDAQ", "NYSE", "AMEX", "NYSEARCA", "CBOE"];

export async function onRequestGet({ request }) {
  const q = String(new URL(request.url).searchParams.get("q") || "").normalize("NFKC").trim().toUpperCase().replace("-", ":");
  if (!/^([A-Z]{2,10}:)?[A-Z][A-Z0-9.]{0,9}$/.test(q)) return json({ ok: false, error: "代號格式錯誤" }, 400);
  const tickers = q.includes(":") ? [q] : EXCH.map(e => `${e}:${q}`);
  let r;
  try {
    r = await fetch("https://scanner.tradingview.com/america/scan", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        origin: "https://www.tradingview.com",
        referer: "https://www.tradingview.com/",
        "user-agent": "Mozilla/5.0 (ustech-earnings tracker)",
      },
      body: JSON.stringify({ symbols: { tickers }, columns: ["name", "description", "market_cap_basic"] }),
    });
  } catch (e) {
    return json({ ok: false, error: "TradingView 連線失敗" }, 502);
  }
  if (!r.ok) return json({ ok: false, error: `TradingView 回應 ${r.status}` }, 502);
  const d = await r.json().catch(() => ({}));
  const hits = (d.data || []).map(x => ({
    symbol: x.s, ticker: x.d[0], name: x.d[1] || x.d[0],
    market_cap: typeof x.d[2] === "number" ? Math.round(x.d[2] / 1e9) : null,
  })).sort((a, b) => (b.market_cap || 0) - (a.market_cap || 0));
  if (!hits.length) return json({ ok: false, error: `TradingView 找不到 ${q}` }, 404);
  return json({ ok: true, hits });
}
