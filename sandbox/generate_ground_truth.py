#!/usr/bin/env python3
"""Ground-truth generator for the AI Accounting Runtime.

Runs INSIDE the dedicated erpgen ERPNext sandbox backend. Posts Purchase Invoices
across an edge-case matrix through ERPNext's REAL posting engine, reads the
auto-generated GL Entries back, verifies debits==credits, and emits one JSONL
record per invoice:

    {scenario, document{...}, posting_proposal{...}, gl_entries[...], checks{...}}

The `document` block is the extraction target (what an OCR/LLM should read off the
vendor invoice). The `gl_entries` are correct-by-construction ground truth (ERPNext
computed them, debits==credits enforced). Together they mint the document->treatment
pairs that no public dataset provides.

Env: COUNT (default 240), OUT (default /tmp/gtc_pairs.jsonl).
Modelled on agents/books/seed_erpnext.py (the proven bootstrap).
"""
import frappe, os, json, datetime, random, traceback
from frappe.utils import nowdate, getdate, add_days

if not getattr(frappe.local, "site", None):
    frappe.init(site=os.environ.get("FRAPPE_SITE", "frontend"))
    frappe.connect(); frappe.set_user("Administrator")

COMPANY = "Ground Truth Co."
ABBR = "GTC"
CURRENCY = "USD"
TODAY = getdate(nowdate())
MONTH_START = TODAY.replace(day=1)
COUNT = int(os.environ.get("COUNT", "240"))
OUT = os.environ.get("OUT", "/tmp/gtc_pairs.jsonl")
RNG = random.Random(20260806)  # deterministic — no wall-clock/entropy so runs reproduce

VENDORS = ["ABC Building Supply", "Metro Metal Roofing", "Felt & Underlayment Co",
           "FastEquip Rentals", "Ironclad Fasteners", "Summit Fuel & Oil",
           "BlueSky Insurance Brokers", "Precision Tool Hire", "Nova Logistics LLC",
           "Granite Aggregates Inc", "Cobalt Electrical Supply", "Harborview Timber"]
ITEMS = [("MAT-MEMBRANE", "TPO Membrane Roll", "materials"),
         ("MAT-FASTENER", "Fastener Box (500ct)", "materials"),
         ("MAT-INSUL", "Polyiso Insulation Board", "materials"),
         ("SVC-INSTALL", "Installation Labor (day)", "overhead"),
         ("SVC-HAUL", "Debris Haul-away", "overhead"),
         ("EQP-RENTAL", "Boom Lift Rental (day)", "overhead")]
FX = {"USD": 1.0, "EUR": 1.08, "GBP": 1.27}  # to company currency (USD)


def log(m): print("GEN>", m)


# ---- fixtures (mirrors the proven seed) -------------------------------------
def _tree(dt, name, is_group=1, parent=None, pf=None):
    if frappe.db.exists(dt, name):
        return
    tf = {"Item Group": "item_group_name", "Customer Group": "customer_group_name",
          "Supplier Group": "supplier_group_name", "Territory": "territory_name"}[dt]
    d = {"doctype": dt, "is_group": is_group, tf: name}
    if parent and pf:
        d[pf] = parent
    frappe.get_doc(d).insert(ignore_permissions=True)


def ensure_prereqs():
    if frappe.db.exists("DocType", "Warehouse Type") and not frappe.db.exists("Warehouse Type", "Transit"):
        frappe.get_doc({"doctype": "Warehouse Type", "name": "Transit"}).insert(ignore_permissions=True)
    for u in ("Nos", "Unit", "Day"):
        if not frappe.db.exists("UOM", u):
            frappe.get_doc({"doctype": "UOM", "uom_name": u}).insert(ignore_permissions=True)
    _tree("Territory", "All Territories")
    _tree("Item Group", "All Item Groups")
    if not frappe.db.exists("Item Group", "Materials"):
        frappe.get_doc({"doctype": "Item Group", "item_group_name": "Materials",
                        "is_group": 0, "parent_item_group": "All Item Groups"}).insert(ignore_permissions=True)
    _tree("Supplier Group", "All Supplier Groups")
    for pl, s, b in (("Standard Buying", 0, 1),):
        if not frappe.db.exists("Price List", pl):
            frappe.get_doc({"doctype": "Price List", "price_list_name": pl, "currency": CURRENCY,
                            "enabled": 1, "selling": s, "buying": b}).insert(ignore_permissions=True)
    frappe.db.commit()


def ensure_fiscal_year(year):
    name = str(year)
    if not frappe.db.exists("Fiscal Year", name):
        frappe.get_doc({"doctype": "Fiscal Year", "year": name,
                        "year_start_date": datetime.date(year, 1, 1),
                        "year_end_date": datetime.date(year, 12, 31)}).insert(ignore_permissions=True)
    return name


def ensure_company():
    ensure_prereqs()
    for y in (2025, 2026, 2027):
        ensure_fiscal_year(y)
    frappe.db.commit()
    if not frappe.db.exists("Company", COMPANY):
        c = frappe.get_doc({"doctype": "Company", "company_name": COMPANY, "abbr": ABBR,
                            "default_currency": CURRENCY, "country": "United States",
                            "create_chart_of_accounts_based_on": "Standard Template",
                            "chart_of_accounts": "Standard", "enable_perpetual_inventory": 0})
        if c.meta.has_field("valuation_method"):
            c.valuation_method = "FIFO"
        c.insert(ignore_permissions=True); frappe.db.commit()
        log(f"created Company {COMPANY} (Standard CoA)")
    frappe.db.set_default("company", COMPANY)
    frappe.db.set_value("Global Defaults", "Global Defaults", "default_company", COMPANY)


def acc(fragment, root_type=None, account_type=None):
    f = {"company": COMPANY, "account_name": ["like", f"%{fragment}%"], "is_group": 0}
    if root_type:
        f["root_type"] = root_type
    if account_type:
        f["account_type"] = account_type
    r = frappe.get_all("Account", filters=f, fields=["name"], limit=1)
    return r[0].name if r else None


def expense_account(kind):
    if kind == "materials":
        return acc("Cost of Goods Sold") or acc("Stock Expenses") or acc("Expenses", root_type="Expense")
    return acc("Administrative Expenses") or acc("Indirect Expenses") or acc("Expenses", root_type="Expense")


def ensure_tax_account():
    name_like = "Sales Tax Payable"
    got = acc(name_like, root_type="Liability")
    if got:
        return got
    parent = (frappe.get_all("Account", filters={"company": COMPANY, "account_name": ["like", "%Duties and Taxes%"]},
                             fields=["name"], limit=1) or
              frappe.get_all("Account", filters={"company": COMPANY, "account_name": ["like", "%Current Liabilities%"], "is_group": 1},
                             fields=["name"], limit=1))
    if not parent:
        return None
    d = frappe.get_doc({"doctype": "Account", "account_name": name_like, "company": COMPANY,
                        "parent_account": parent[0].name, "account_type": "Tax",
                        "root_type": "Liability", "is_group": 0}).insert(ignore_permissions=True)
    return d.name


def ensure_supplier(name, currency="USD"):
    if not frappe.db.exists("Supplier", name):
        frappe.get_doc({"doctype": "Supplier", "supplier_name": name, "supplier_type": "Company",
                        "supplier_group": "All Supplier Groups",
                        "default_currency": currency}).insert(ignore_permissions=True)
    return name


def ensure_item(code, label, kind):
    if not frappe.db.exists("Item", code):
        frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": label,
                        "item_group": "Materials", "is_stock_item": 0,
                        "is_purchase_item": 1, "stock_uom": "Nos"}).insert(ignore_permissions=True)
    return code


def cost_center():
    cc = frappe.get_value("Company", COMPANY, "cost_center")
    if cc:
        return cc
    r = frappe.get_all("Cost Center", filters={"company": COMPANY, "is_group": 0}, fields=["name"], limit=1)
    return r[0].name if r else None


# ---- scenario matrix --------------------------------------------------------
SCENARIOS = (["standard"] * 90 + ["with_tax"] * 60 + ["multi_line"] * 40 +
             ["discount"] * 25 + ["foreign_currency"] * 20 + ["duplicate"] * 5 +
             ["closed_period"] * 15 + ["tax_mismatch"] * 15)
FROZEN_UPTO = datetime.date(2025, 12, 31)   # books closed on/before this date


def gl_for(voucher_no):
    rows = frappe.get_all("GL Entry",
                          filters={"voucher_no": voucher_no, "is_cancelled": 0},
                          fields=["account", "debit", "credit", "against", "cost_center",
                                  "debit_in_account_currency", "credit_in_account_currency",
                                  "account_currency"], order_by="creation")
    return [dict(r) for r in rows]


def build_invoice(i, scenario, tax_acc, cc, last_doc):
    kinds = ITEMS
    cur = "USD"
    if scenario == "foreign_currency":
        cur = RNG.choice(["EUR", "GBP"])
    vendor = ensure_supplier(RNG.choice(VENDORS), currency=cur)
    # spread across 2026 (after the freeze, within FY2026) for temporal realism
    posting = max(datetime.date(2026, 1, 2), add_days(TODAY, -RNG.randint(0, 200)))
    if scenario == "closed_period":
        # deliberately date the invoice into the frozen/closed period → engine must refuse
        posting = datetime.date(2025, RNG.randint(1, 12), RNG.randint(1, 28))
    bill_no = f"INV-{2026000 + i}"
    nlines = 3 if scenario == "multi_line" else 1
    lines, doc_lines = [], []
    for _ in range(nlines):
        code, label, kind = RNG.choice(kinds)
        ensure_item(code, label, kind)
        qty = RNG.randint(1, 12)
        rate = RNG.choice([120, 240, 85, 1500, 450, 60, 980, 320]) + RNG.randint(0, 40)
        row = {"item_code": code, "qty": qty, "rate": rate, "expense_account": expense_account(kind)}
        disc = 0
        if scenario == "discount":
            disc = RNG.choice([5, 10, 12.5])
            row["discount_percentage"] = disc
        lines.append(row)
        doc_lines.append({"item_code": code, "description": label, "qty": qty,
                          "unit_price": rate, "discount_pct": disc,
                          "amount": round(qty * rate * (1 - disc / 100.0), 2)})
    pi = {"doctype": "Purchase Invoice", "company": COMPANY, "supplier": vendor,
          "posting_date": posting, "set_posting_time": 1,  # honor backdated posting_date
          "bill_no": bill_no, "bill_date": posting,
          "due_date": add_days(posting, 20), "currency": cur, "update_stock": 0,
          "conversion_rate": FX[cur], "items": lines,
          "remarks": f"GTC:{scenario}:{i}"}
    taxes = []
    if scenario == "with_tax" and tax_acc:
        rate = RNG.choice([6.25, 7.0, 8.25])
        pi["taxes"] = [{"charge_type": "On Net Total", "account_head": tax_acc,
                        "description": f"Sales Tax {rate}%", "rate": rate, "cost_center": cc,
                        "category": "Total", "add_deduct_tax": "Add"}]
        taxes = [{"kind": "sales_tax", "rate": rate}]
    if scenario == "duplicate" and last_doc:
        # re-use a prior vendor+bill_no+amount → the duplicate the runtime must catch
        pi["supplier"] = last_doc["supplier"]
        pi["bill_no"] = last_doc["bill_no"]
    doc = {"supplier_name": pi["supplier"], "bill_no": pi["bill_no"],
           "invoice_date": str(posting), "currency": cur, "fx_to_usd": FX[cur],
           "lines": doc_lines, "taxes": taxes}
    return pi, doc


def main():
    frappe.flags.in_import = True
    ensure_company()
    tax_acc = ensure_tax_account()
    cc = cost_center()
    # Freeze the books on/before FROZEN_UPTO so closed_period invoices are refused by the
    # engine. In v16 this lives on Company (accounts_frozen_till_date); the check explicitly
    # blocks even Administrator (see general_ledger.check_freezing_date). This is the negative
    # ground truth for the "accounting period is open" verification check.
    frappe.db.set_value("Company", COMPANY, "accounts_frozen_till_date", FROZEN_UPTO)
    frappe.db.set_value("Company", COMPANY, "role_allowed_for_frozen_entries", "")
    frappe.db.commit()
    out = open(OUT, "w")
    n_ok = n_bal = n_fail = n_refusal = 0
    last_doc = None
    scen_counts = {}
    for i in range(1, COUNT + 1):
        scenario = SCENARIOS[i % len(SCENARIOS)]
        # in_import suppresses bare-site notifications but ALSO bypasses the freezing-date
        # check — so for closed_period we let it run (company + FY already exist, so no
        # notification will fire) to get a real period-closed refusal.
        frappe.flags.in_import = (scenario != "closed_period")
        rec = {"id": f"GTC-{i:05d}", "scenario": scenario}
        try:
            pi_dict, doc = build_invoice(i, scenario, tax_acc, cc, last_doc)
            pi = frappe.get_doc(pi_dict)
            pi.insert(ignore_permissions=True)
            pi.submit()
            gl = gl_for(pi.name)
            dr = round(sum(g["debit"] for g in gl), 2)
            crd = round(sum(g["credit"] for g in gl), 2)
            balanced = abs(dr - crd) < 0.01
            rec.update({
                "voucher": pi.name,
                "document": doc,
                "posting_proposal": {
                    "grand_total": pi.grand_total, "base_grand_total": pi.base_grand_total,
                    "net_total": pi.net_total, "total_taxes": pi.total_taxes_and_charges,
                    "credit_to": pi.credit_to},
                "gl_entries": [{"account": g["account"], "debit": g["debit"], "credit": g["credit"],
                                "against": g["against"]} for g in gl],
                "checks": {"debits": dr, "credits": crd, "balanced": balanced,
                           "n_gl": len(gl)}})
            if scenario == "tax_mismatch":
                # the DOCUMENT declares a total that disagrees with the engine-computed one
                # (a real vendor/OCR error the verifier must catch). GL still balances.
                delta = RNG.choice([pi.total_taxes_and_charges or round(pi.net_total * 0.07, 2),
                                    round(pi.grand_total * 0.1, 2), 100.0]) or 100.0
                declared = round(pi.grand_total - delta, 2)
                rec["document"]["declared_total"] = declared
                rec["checks"]["declared_total"] = declared
                rec["checks"]["computed_total"] = pi.grand_total
                rec["checks"]["declared_matches_computed"] = abs(declared - pi.grand_total) < 0.01
                rec["expected_finding"] = "document_total_mismatch"
            n_ok += 1
            n_bal += 1 if balanced else 0
            last_doc = doc | {"supplier": pi.supplier}
            frappe.db.commit()
        except Exception as e:
            frappe.db.rollback()
            rec.update({"error": f"{type(e).__name__}: {str(e)[:200]}"})
            if scenario == "closed_period":
                rec["expected_refusal"] = True
                rec["refusal_type"] = "period_closed"
                n_refusal += 1
            else:
                n_fail += 1
        scen_counts[scenario] = scen_counts.get(scenario, 0) + 1
        out.write(json.dumps(rec, default=str) + "\n")
    out.close()
    print(f"GEN_OK count={COUNT} posted={n_ok} balanced={n_bal} "
          f"expected_refusals={n_refusal} unexpected_failures={n_fail} "
          f"out={OUT} scenarios={json.dumps(scen_counts)}")


try:
    main()
except Exception:
    print("GEN_ERROR\n" + traceback.format_exc())
