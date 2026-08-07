#!/usr/bin/env python3
"""Cross-validate ERPNext ground-truth postings against Odoo's independent engine.

For a slice of the generated `standard` USD invoices, post the SAME (vendor, amount)
into Odoo as a vendor bill, let Odoo compute its own journal items, and compare the
double-entry to ERPNext's. Agreement between two real accounting engines on the same
input = strong ground-truth evidence (the postings aren't an ERPNext artifact).

Compares structure + amounts (account identity differs between engines; the accounting
shape must not): expense debited by the net, payable credited by the net, both balanced.

Out: data/ground-truth/erpnext_vs_odoo.jsonl + a printed agreement summary.
"""
import xmlrpc.client as x
import json, os

URL = "http://localhost:8101"
DB = "gtc"
PW = "admin"
GT = "/mnt/backup/projects/accounting-runtime/data/ground-truth/gtc_pairs.jsonl"
OUT = "/mnt/backup/projects/accounting-runtime/data/ground-truth/erpnext_vs_odoo.jsonl"
N = int(os.environ.get("N", "50"))

common = x.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, "admin", PW, {})
models = x.ServerProxy(f"{URL}/xmlrpc/2/object")


def kw(model, method, *args, **kwargs):
    return models.execute_kw(DB, uid, PW, model, method, list(args), kwargs or {})


# one expense account + purchase journal to post against
EXP = kw("account.account", "search", [["account_type", "=", "expense"]], limit=1)[0]
PJOURNAL = kw("account.journal", "search", [["type", "=", "purchase"]], limit=1)[0]
_partners = {}


def partner(name):
    if name not in _partners:
        found = kw("res.partner", "search", [["name", "=", name]], limit=1)
        _partners[name] = found[0] if found else kw(
            "res.partner", "create", {"name": name, "supplier_rank": 1})
    return _partners[name]


def erpnext_shape(rec):
    """Reduce ERPNext gl_entries to (expense_debit, payable_credit, balanced)."""
    dr = sum(g["debit"] for g in rec["gl_entries"])
    cr = sum(g["credit"] for g in rec["gl_entries"])
    # creditor/payable is the credited line; expense is the debited line(s)
    pay = sum(g["credit"] for g in rec["gl_entries"] if g["credit"] > 0)
    exp = sum(g["debit"] for g in rec["gl_entries"] if g["debit"] > 0)
    return {"expense_debit": round(exp, 2), "payable_credit": round(pay, 2),
            "balanced": abs(dr - cr) < 0.01}


def odoo_post(rec):
    p = partner(rec["document"]["supplier_name"])
    lines = [(0, 0, {"name": ln["description"] or "line", "quantity": ln["qty"],
                     "price_unit": ln["unit_price"], "account_id": EXP,
                     "tax_ids": [(6, 0, [])]}) for ln in rec["document"]["lines"]]
    mid = kw("account.move", "create", {
        "move_type": "in_invoice", "partner_id": p, "journal_id": PJOURNAL,
        "invoice_date": rec["document"]["invoice_date"],
        "invoice_line_ids": lines})
    kw("account.move", "action_post", [mid])
    mls = kw("account.move.line", "search_read", [["move_id", "=", mid]],
             fields=["account_id", "account_type", "debit", "credit"])
    dr = round(sum(m["debit"] for m in mls), 2)
    cr = round(sum(m["credit"] for m in mls), 2)
    exp = round(sum(m["debit"] for m in mls if m["account_type"] == "expense"), 2)
    pay = round(sum(m["credit"] for m in mls if m["account_type"] == "liability_payable"), 2)
    return {"move": mid, "expense_debit": exp, "payable_credit": pay,
            "balanced": abs(dr - cr) < 0.01, "n_lines": len(mls)}


def main():
    print("odoo uid:", uid, "| expense acct:", EXP, "| purchase journal:", PJOURNAL)
    recs = [json.loads(l) for l in open(GT)
            if json.loads(l).get("scenario") == "standard"
            and not json.loads(l).get("error")
            and json.loads(l)["document"]["currency"] == "USD"][:N]
    out = open(OUT, "w")
    agree = 0
    for rec in recs:
        e = erpnext_shape(rec)
        try:
            o = odoo_post(rec)
        except Exception as ex:
            out.write(json.dumps({"id": rec["id"], "error": str(ex)[:200]}) + "\n")
            continue
        match = (e["balanced"] and o["balanced"]
                 and abs(e["expense_debit"] - o["expense_debit"]) < 0.01
                 and abs(e["payable_credit"] - o["payable_credit"]) < 0.01)
        agree += 1 if match else 0
        out.write(json.dumps({"id": rec["id"], "voucher": rec.get("voucher"),
                              "erpnext": e, "odoo": o, "agree": match}) + "\n")
    out.close()
    print(f"XVAL_OK compared={len(recs)} agree={agree} out={OUT}")


if __name__ == "__main__":
    main()
