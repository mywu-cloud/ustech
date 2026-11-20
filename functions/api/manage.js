// Cloudflare Pages Function：/api/manage
// 由網站「追蹤名單」頁的管理表單呼叫，代為觸發 GitHub Actions「Update earnings」(workflow_dispatch)。
//
// 需在 Cloudflare Pages → Settings → Variables and Secrets 設定（類型選 Secret）：
//   GH_TOKEN（或 USTECH_TOKEN） Fine-grained token，只授權 mywu-cloud/ustech，權限 Actions: Read and write
//   ADMIN_PASSWORD  管理密碼（建議 16 字以上）
// 選填：GH_REPO（預設 mywu-cloud/ustech）、GH_WORKFLOW（預設 update.yml）、GH_REF（預設 main）
//
// POST /api/manage   body {password, add, remove}   → 觸發 workflow
// GET  /api/manage   header X-Admin-Password          → 最近 5 次手動執行狀態

const enc = new TextEncoder();

// 正規化：全形→半形、去前後空白/換行、去外層引號（避免 Secret 貼上時夾帶）
const norm = s => {
  s = String(s ?? "").normalize("NFKC").trim();
  if (s.length >= 2 && /^(["'])[\s\S]*\1$/.test(s)) s = s.slice(1, -1).trim();
  return s;
};

async function same(a, b) {
  // 固定時間比對（先 hash 再比，避免長度與時間差洩漏）
  const [x, y] = await Promise.all([a, b].map(s => crypto.subtle.digest("SHA-256", enc.encode(String(s)))));
  const A = new Uint8Array(x), B = new Uint8Array(y);
  let d = 0;
  for (let i = 0; i < A.length; i++) d |= A[i] ^ B[i];
  return d === 0;
}

const json = (obj, status = 200) =>
  new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

function cfg(env) {
  return {
    repo: env.GH_REPO || "mywu-cloud/ustech",
    wf: env.GH_WORKFLOW || "update.yml",
    ref: env.GH_REF || "main",
  };
}

const gh = (env, path, init = {}) =>
  fetch(`https://api.github.com/repos/${cfg(env).repo}${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${env.GH_TOKEN || env.USTECH_TOKEN}`,
      accept: "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "ustech-pages",
      ...(init.body ? { "content-type": "application/json" } : {}),
    },
  });

async function auth(env, pw) {
  if (!(env.GH_TOKEN || env.USTECH_TOKEN) || !env.ADMIN_PASSWORD) return json({ ok: false, error: "伺服器尚未設定 GH_TOKEN / ADMIN_PASSWORD" }, 500);
  if (!norm(pw) || !(await same(norm(pw), norm(env.ADMIN_PASSWORD)))) {
    await new Promise(r => setTimeout(r, 800)); // 減緩暴力猜測
    return json({ ok: false, error: "密碼錯誤" }, 401);
  }
  return null;
}

// 與 scripts/manage.py 相同格式：交易所:代號|英文名|中文名|標籤1,標籤2，多筆以 ; 分隔
const SYM = /^([A-Z]{2,10}:)?[A-Z][A-Z0-9.]{0,9}$/;
function validate(add, remove) {
  add = norm(add);
  remove = norm(remove).toUpperCase();
  if (!add && !remove) return "請填寫要新增或刪除的公司";
  if (add.length > 3000 || remove.length > 500) return "內容過長";
  if (/[\r\n`$\\<>#]/.test(add)) return "新增內容含不允許的字元";
  if (!/^[A-Z0-9.:,\s]*$/.test(remove)) return "刪除欄只能填代號，以逗號分隔";
  for (const spec of add.split(";").map(s => s.trim()).filter(Boolean)) {
    const p = spec.split("|").map(s => s.trim());
    if (!SYM.test(p[0].toUpperCase())) return `代號格式錯誤：${p[0]}（例 NASDAQ:AVGO）`;
    if (p.length > 4) return `欄位過多：${spec}`;
  }
  return { add, remove };
}

export async function onRequestPost({ request, env }) {
  let body;
  try { body = await request.json(); } catch { return json({ ok: false, error: "格式錯誤" }, 400); }
  const deny = await auth(env, body.password);
  if (deny) return deny;
  const v = validate(body.add, body.remove);
  if (typeof v === "string") return json({ ok: false, error: v }, 400);

  const { wf, ref } = cfg(env);
  const r = await gh(env, `/actions/workflows/${wf}/dispatches`, {
    method: "POST",
    body: JSON.stringify({ ref, inputs: { add: v.add, remove: v.remove } }),
  });
  if (r.status !== 204) {
    const t = await r.text();
    return json({ ok: false, error: `GitHub 回應 ${r.status}`, detail: t.slice(0, 300) }, 502);
  }
  return json({ ok: true, add: v.add, remove: v.remove });
}

export async function onRequestGet({ request, env }) {
  const deny = await auth(env, request.headers.get("x-admin-password"));
  if (deny) return deny;
  const { wf } = cfg(env);
  const r = await gh(env, `/actions/workflows/${wf}/runs?event=workflow_dispatch&per_page=5`);
  if (!r.ok) return json({ ok: false, error: `GitHub 回應 ${r.status}` }, 502);
  const d = await r.json();
  return json({
    ok: true,
    runs: (d.workflow_runs || []).map(x => ({
      id: x.id, status: x.status, conclusion: x.conclusion,
      created_at: x.created_at, updated_at: x.updated_at, url: x.html_url,
    })),
  });
}
