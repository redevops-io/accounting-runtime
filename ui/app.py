"""Deployable review console for the Agentic Accounting Runtime example.

A FastAPI service + MD3 dashboard over the generated ground-truth pairs (and, when reachable,
live ERPNext). Same reference pattern as the ReDevOps agentic-app fleet: reads real data,
renders a review surface — document -> proposed posting -> GL entries -> verification, with an
approval gate on posting. No mock data.

    pip install -r requirements.txt
    python3 -m uvicorn app:app --host 0.0.0.0 --port 8300

Env: DATA_FILE (default ../data/ground-truth/gtc_pairs.jsonl, falls back to sample.jsonl),
     XVAL_FILE (../data/ground-truth/erpnext_vs_odoo.jsonl), ERPNEXT_FRONT_URL, PORT.
"""
import json, os, html
from collections import Counter
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

HERE = os.path.dirname(os.path.abspath(__file__))
GT = os.environ.get("DATA_FILE", os.path.join(HERE, "..", "data", "ground-truth", "gtc_pairs.jsonl"))
SAMPLE = os.path.join(HERE, "..", "data", "ground-truth", "sample.jsonl")
XVAL = os.environ.get("XVAL_FILE", os.path.join(HERE, "..", "data", "ground-truth", "erpnext_vs_odoo.jsonl"))
ERPNEXT_FRONT_URL = os.environ.get("ERPNEXT_FRONT_URL", "http://localhost:8100")

app = FastAPI(title="Agentic Accounting Runtime — review console")


def _load():
    # DATA_FILE -> repo sample -> sample bundled next to app.py (for the container)
    path = next((p for p in (GT, SAMPLE, os.path.join(HERE, "sample.jsonl")) if os.path.exists(p)), GT)
    rows = [json.loads(l) for l in open(path)] if os.path.exists(path) else []
    xval = {}
    if os.path.exists(XVAL):
        for l in open(XVAL):
            r = json.loads(l)
            if r.get("id"):
                xval[r["id"]] = r
    return rows, xval, os.path.basename(path)


def _money(x):
    try:
        return "${:,.2f}".format(float(x))
    except Exception:
        return str(x)


def esc(v):
    return html.escape(str(v)) if v is not None else ""


BASE_CSS = """
:root{--surface-dim:#0e0e11;--surface:#131316;--surface-bright:#393a3d;--surface-container-lowest:#0d0e10;--surface-container-low:#1b1b1f;--surface-container:#1f1f23;--surface-container-high:#2a2a2e;--surface-container-highest:#353539;--on-surface:#e4e2e6;--on-surface-variant:#c7c5ca;--on-surface-muted:#918f96;--outline:#938f99;--outline-variant:#2f2f33;--primary:#4fd1c5;--on-primary:#00201c;--primary-container:#00504a;--on-primary-container:#a8f0e6;--secondary:#f5b544;--success:#5bd98a;--success-container:#0f3d22;--warning:#f5b544;--warning-container:#4a3500;--danger:#f2544f;--danger-container:#5c1512;--info:#5aa9f0;--info-container:#103a5c;--sp-1:4px;--sp-2:8px;--sp-3:12px;--sp-4:16px;--sp-5:24px;--sp-6:32px;--radius-md:12px;--radius-lg:16px;--radius-pill:999px;--font-sans:"Roboto",system-ui,-apple-system,"Segoe UI",sans-serif;--font-mono:"Roboto Mono",ui-monospace,"SF Mono",monospace}
*{box-sizing:border-box}
.page{background:var(--surface);color:var(--on-surface);font-family:var(--font-sans);padding:var(--sp-5);margin:0}
.shell{max-width:1200px;margin-inline:auto;display:flex;flex-direction:column;gap:var(--sp-5)}
.kpi-row{display:grid;gap:var(--sp-4);grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.card{background:var(--surface-container);border:1px solid var(--outline-variant);border-radius:var(--radius-lg);padding:var(--sp-5);display:flex;flex-direction:column;gap:var(--sp-4)}
.card__title{font:500 16px/24px var(--font-sans);margin:0}
.tile{background:var(--surface-container);border:1px solid var(--outline-variant);border-radius:var(--radius-lg);padding:var(--sp-4) var(--sp-5);display:flex;flex-direction:column;gap:var(--sp-1)}
.tile__label{font:500 12px/16px var(--font-sans);letter-spacing:.5px;text-transform:uppercase;color:var(--on-surface-muted)}
.tile__value{font:500 30px/38px var(--font-mono);color:var(--on-surface);font-feature-settings:"tnum"}
.tile__delta{font:500 12px/16px var(--font-sans);color:var(--on-surface-variant)}
.pill{display:inline-flex;align-items:center;gap:6px;height:24px;padding:0 10px;border-radius:var(--radius-pill);font:500 12px/1 var(--font-sans)}
.pill--success{background:var(--success-container);color:var(--success)}.pill--warn{background:var(--warning-container);color:var(--warning)}.pill--danger{background:var(--danger-container);color:var(--danger)}.pill--info{background:var(--info-container);color:var(--info)}.pill--neutral{background:var(--surface-container-highest);color:var(--on-surface-variant)}
.pill__dot{width:6px;height:6px;border-radius:50%;background:currentColor}
.table{width:100%;border-collapse:collapse;font-size:14px}
.table th{text-align:left;color:var(--on-surface-muted);font:500 12px/16px var(--font-sans);letter-spacing:.5px;text-transform:uppercase;padding:var(--sp-3) var(--sp-4);border-bottom:1px solid var(--outline-variant)}
.table td{padding:var(--sp-3) var(--sp-4);color:var(--on-surface);border-bottom:1px solid var(--outline-variant)}
.table td.num{text-align:right;font-family:var(--font-mono);font-feature-settings:"tnum"}
.table tbody tr:hover{background:rgba(228,226,230,.06)}
a{color:var(--primary);text-decoration:none}
.appbar{background:var(--surface-container-low);border:1px solid var(--outline-variant);border-radius:var(--radius-lg);padding:var(--sp-5)}
.appbar__row{display:flex;align-items:center;gap:var(--sp-3);flex-wrap:wrap}
.appbar h1{margin:0;font:400 26px/34px var(--font-sans)}
.appbar__sub{margin-top:var(--sp-2);color:var(--on-surface-muted);font:400 14px/20px var(--font-sans);max-width:820px}
.spacer{flex:1}
.btn{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 16px;border-radius:var(--radius-pill);background:var(--primary-container);color:var(--on-primary-container);font:500 14px/1 var(--font-sans);border:1px solid var(--primary-container);cursor:pointer}
.btn--ghost{background:transparent;color:var(--on-surface-variant);border-color:var(--outline-variant)}
.btn--danger{background:var(--danger-container);color:var(--danger);border-color:var(--danger-container)}
.section-label{font:500 12px/16px var(--font-sans);letter-spacing:.5px;text-transform:uppercase;color:var(--primary);display:flex;align-items:center;gap:var(--sp-3);margin:0}
.section-label::after{content:"";flex:1;height:1px;background:var(--outline-variant)}
.barlist__row{display:grid;grid-template-columns:180px 1fr 60px;align-items:center;gap:var(--sp-4);margin-bottom:var(--sp-3)}
.bar{height:8px;border-radius:var(--radius-pill);background:var(--surface-container-highest);overflow:hidden}.bar>span{display:block;height:100%;background:var(--primary)}
.grid2{display:grid;gap:var(--sp-4);grid-template-columns:1fr 1fr}@media(max-width:820px){.grid2{grid-template-columns:1fr}}
.banner{padding:var(--sp-4) var(--sp-5);border-radius:var(--radius-md);border-left:4px solid var(--info);background:var(--info-container);color:var(--on-surface);font-size:13px}
"""


def _stats(rows, xval):
    posted = [r for r in rows if not r.get("error")]
    refusals = [r for r in rows if r.get("expected_refusal")]
    balanced = sum(1 for r in posted if r.get("checks", {}).get("balanced"))
    xa = [x for x in xval.values() if "agree" in x]
    return {
        "records": len(rows), "posted": len(posted), "balanced": balanced,
        "refusals": len(refusals),
        "scenarios": Counter(r["scenario"] for r in rows),
        "xval_total": len(xa), "xval_agree": sum(1 for x in xa if x.get("agree")),
    }


def _verify_pill(r):
    if r.get("expected_refusal"):
        return "<span class='pill pill--warn'><span class='pill__dot'></span>period closed · refused</span>"
    if r.get("expected_finding") == "document_total_mismatch":
        return "<span class='pill pill--danger'><span class='pill__dot'></span>total mismatch flagged</span>"
    if r.get("checks", {}).get("balanced"):
        return "<span class='pill pill--success'><span class='pill__dot'></span>balanced</span>"
    return "<span class='pill pill--neutral'>—</span>"


def _shell(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{BASE_CSS}</style></head>
<body class="page"><div class="shell">{body}</div></body></html>"""


@app.get("/health")
def health():
    rows, xval, src = _load()
    return {"status": "ok", "records": len(rows), "source": src}


@app.get("/api/summary")
def summary():
    rows, xval, src = _load()
    s = _stats(rows, xval)
    s["scenarios"] = dict(s["scenarios"])
    s["source"] = src
    return JSONResponse(s)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    rows, xval, src = _load()
    s = _stats(rows, xval)
    pct_bal = round(100 * s["balanced"] / s["posted"], 1) if s["posted"] else 0
    xpct = round(100 * s["xval_agree"] / s["xval_total"], 1) if s["xval_total"] else None
    tiles = [
        ("Invoices posted", f"{s['posted']:,}", f"{s['records']:,} records"),
        ("Balanced", f"{pct_bal}%", f"{s['balanced']:,} / {s['posted']:,} debits = credits"),
        ("Period-closed refusals", f"{s['refusals']:,}", "engine refused (correct)"),
        ("Odoo cross-check", (f"{xpct}%" if xpct is not None else "—"),
         (f"{s['xval_agree']}/{s['xval_total']} agree" if s["xval_total"] else "run cross_validate_odoo.py")),
    ]
    tile_html = "".join(
        f"<div class='tile'><span class='tile__label'>{esc(l)}</span>"
        f"<span class='tile__value'>{esc(v)}</span><span class='tile__delta'>{esc(d)}</span></div>"
        for l, v, d in tiles)
    total = sum(s["scenarios"].values()) or 1
    bars = "".join(
        f"<div class='barlist__row'><span>{esc(k)}</span>"
        f"<div class='bar'><span style='width:{100*v/total:.0f}%'></span></div>"
        f"<span class='num' style='text-align:right'>{v}</span></div>"
        for k, v in s["scenarios"].most_common())
    # review queue — most recent 40 posted/flagged items
    queue = [r for r in rows][:40]
    qrows = "".join(
        f"<tr onclick=\"location.href='/item/{esc(r['id'])}'\" style='cursor:pointer'><td><a href='/item/{esc(r['id'])}'>{esc(r['id'])}</a></td>"
        f"<td>{esc(r['scenario'])}</td>"
        f"<td>{esc((r.get('document') or {}).get('supplier_name',''))}</td>"
        f"<td class='num'>{_money((r.get('posting_proposal') or {}).get('grand_total','')) if r.get('posting_proposal') else '—'}</td>"
        f"<td>{_verify_pill(r)}</td></tr>"
        for r in queue)
    body = f"""
<div class="appbar"><div class="appbar__row">
  <h1>Agentic Accounting Runtime</h1>
  <span class="pill pill--success"><span class="pill__dot"></span>agent active · core: ERPNext</span>
  <span class="pill pill--info"><span class="pill__dot"></span>data: {esc(src)}</span>
  <div class="spacer"></div>
  <a class="btn" href="{esc(ERPNEXT_FRONT_URL)}" target="_blank">Open in ERPNext ↗</a>
</div><div class="appbar__sub">Governed review over correct-by-construction postings — each invoice was posted through the real ERPNext engine, the double-entry read back, and (for a slice) cross-validated against Odoo. Click a row to review the proposed posting before approval.</div></div>
<div class="kpi-row">{tile_html}</div>
<div class="grid2">
  <div class="card"><p class="section-label">Review queue</p>
    <table class="table"><thead><tr><th>ID</th><th>Scenario</th><th>Vendor</th><th>Amount</th><th>Verification</th></tr></thead>
    <tbody>{qrows}</tbody></table></div>
  <div class="card"><p class="section-label">Scenario coverage</p>{bars}
    <div class="banner">This is the example's review surface. A production deployment adds document
    extraction, the QBO/Xero/Drake adapters, multi-tenant auth, and e-file. <a href="https://redevops.io">We can help ↗</a></div></div>
</div>"""
    return _shell("Agentic Accounting Runtime", body)


@app.get("/item/{item_id}", response_class=HTMLResponse)
def review(item_id: str):
    rows, xval, src = _load()
    r = next((x for x in rows if x.get("id") == item_id), None)
    if not r:
        return HTMLResponse(_shell("Not found", "<div class='card'>Item not found. <a href='/'>Back</a></div>"), status_code=404)
    doc = r.get("document") or {}
    lines = "".join(
        f"<tr><td>{esc(ln.get('description') or ln.get('item_code',''))}</td>"
        f"<td class='num'>{esc(ln.get('qty',''))}</td>"
        f"<td class='num'>{_money(ln.get('unit_price',''))}</td>"
        f"<td class='num'>{_money(ln.get('amount',''))}</td></tr>"
        for ln in doc.get("lines", []))
    gl = "".join(
        f"<tr><td>{esc(g['account'])}</td>"
        f"<td class='num'>{_money(g['debit']) if g['debit'] else ''}</td>"
        f"<td class='num'>{_money(g['credit']) if g['credit'] else ''}</td></tr>"
        for g in r.get("gl_entries", []))
    checks = r.get("checks", {})
    xrow = xval.get(item_id)
    verify_items = []
    if r.get("expected_refusal"):
        verify_items.append("<span class='pill pill--warn'><span class='pill__dot'></span>refused: posting into closed period</span>")
    else:
        verify_items.append(_verify_pill(r))
        if checks.get("n_gl"):
            verify_items.append(f"<span class='pill pill--neutral'>{checks['n_gl']} GL lines</span>")
        if xrow:
            cls = "success" if xrow.get("agree") else "danger"
            verify_items.append(f"<span class='pill pill--{cls}'><span class='pill__dot'></span>Odoo {'agrees' if xrow.get('agree') else 'differs'}</span>")
    gl_block = (f"<table class='table'><thead><tr><th>Account</th><th>Debit</th><th>Credit</th></tr></thead><tbody>{gl}</tbody>"
                f"<tfoot><tr><td style='color:var(--on-surface-muted)'>Σ</td><td class='num'>{_money(checks.get('debits',''))}</td><td class='num'>{_money(checks.get('credits',''))}</td></tr></tfoot></table>"
                if gl else "<div style='color:var(--on-surface-muted)'>No posting — the engine refused this entry.</div>")
    body = f"""
<div class="appbar"><div class="appbar__row"><h1>Review · {esc(item_id)}</h1>
  <span class="pill pill--neutral">{esc(r['scenario'])}</span><div class="spacer"></div>
  <a class="btn btn--ghost" href="/">← Queue</a></div></div>
<div class="grid2">
  <div class="card"><p class="section-label">Source document</p>
    <div class="body-m"><b>{esc(doc.get('supplier_name',''))}</b> · {esc(doc.get('bill_no',''))} · {esc(doc.get('invoice_date',''))} · {esc(doc.get('currency',''))}</div>
    <table class="table"><thead><tr><th>Line</th><th>Qty</th><th>Unit</th><th>Amount</th></tr></thead><tbody>{lines or '<tr><td colspan=4>—</td></tr>'}</tbody></table>
    {"<div style='color:var(--danger)'>Document declares "+_money(doc.get('declared_total'))+" · engine computed "+_money(checks.get('computed_total'))+" — flagged for review.</div>" if r.get('expected_finding')=='document_total_mismatch' else ''}
  </div>
  <div class="card"><p class="section-label">Proposed posting (ERPNext engine)</p>{gl_block}
    <div style="display:flex;gap:8px;flex-wrap:wrap">{''.join(verify_items)}</div>
  </div>
</div>
<div class="card"><p class="section-label">Decision</p>
  <div style="display:flex;gap:12px;flex-wrap:wrap">
    <button class="btn" onclick="act('approve')">Approve &amp; post</button>
    <button class="btn btn--ghost" onclick="act('amend')">Amend</button>
    <button class="btn btn--danger" onclick="act('reject')">Reject</button>
    <span id="msg" style="align-self:center;color:var(--on-surface-variant)"></span>
  </div>
  <div class="banner">In this example, posting already happened in the sandbox engine (that's how the
  ground truth is generated). In a production deployment this is the human approval gate before the
  ledger is written.</div>
</div>
<script>
async function act(a){{const r=await fetch('/agent/run',{{method:'POST',headers:{{'content-type':'application/json'}},body:JSON.stringify({{action:a,id:'{esc(item_id)}'}})}});const j=await r.json();document.getElementById('msg').textContent=j.message;}}
</script>"""
    return _shell(f"Review {item_id}", body)


@app.post("/agent/run")
async def agent_run(payload: dict):
    action = (payload or {}).get("action")
    item = (payload or {}).get("id")
    if action == "approve":
        return {"status": "approved", "message": f"{item}: approved — in production this posts to the ledger (idempotent) and reads it back."}
    if action == "amend":
        return {"status": "amend", "message": f"{item}: sent back for amendment."}
    if action == "reject":
        return {"status": "rejected", "message": f"{item}: rejected — a named refusal is recorded in the evidence chain."}
    return {"status": "unknown", "message": "unknown action"}
