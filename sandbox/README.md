# ERPNext ground-truth generator (Phase-2 spike)

A **dedicated, disposable** ERPNext instance that posts invoices through ERPNext's real
posting engine and reads the auto-generated `GL Entry` rows back — producing
correct-by-construction `{document → posting → gl_entries}` pairs. This is the answer to
the hardest data family: no public dataset pairs a source document with its resulting
double-entry treatment (see `~/Documents/AI_ACCOUNTING_RUNTIME_DATA_SOURCES.md`), so we
mint the pairs from the accounting engine itself.

## Why a separate instance
The generator posts thousands of invoices across an edge-case matrix — it must not pollute
the demo's "Summit Roofing Co." (`agents/books`) or the live stack. This sandbox is fully
isolated: its own compose project (`erpgen`), site (`frontend`), DB volumes, and port
(**8100**, vs the demo's 8092). Reset = `docker compose -p erpgen down -v`.

## Stand it up
```bash
docker compose -p erpgen up -d        # pinned frappe/erpnext v16.31.1 @digest; creates site
# wait for erpgen-create-site-1 to exit 0, then :8100 serves ERPNext (Administrator / admin)
```

## Generate
```bash
./run_generator.sh 500                 # -> ../data/ground-truth/gtc_pairs.jsonl
```
`generate_ground_truth.py` runs *inside* `erpgen-backend-1` via the bench virtualenv python
(the proven path from `agents/books/seed_erpnext.py`). It creates a dedicated **Ground Truth
Co.** with the Standard US CoA + tax account, then posts Purchase Invoices across scenarios.

## Scenario matrix (per 270-cycle)
| scenario | n | what it exercises |
|---|---|---|
| standard | 90 | single-line invoice → expense/creditor posting |
| with_tax | 60 | On-Net-Total sales tax → 3-line GL (expense, tax, creditor) |
| multi_line | 40 | 3 lines, mixed materials/overhead accounts |
| discount | 25 | line discount % → net vs gross |
| foreign_currency | 20 | EUR/GBP invoice → base-currency conversion in GL |
| duplicate | 5 | same vendor+bill_no as a prior invoice (positive for dup-detection) |
| **closed_period** | 15 | dated into a frozen period → engine **refuses** (negative ground truth for "period open" check) |
| **tax_mismatch** | 15 | document `declared_total` ≠ engine-computed total (labeled `expected_finding`) |

Negatives matter as much as positives: `closed_period` yields a real engine refusal
(`accounts_frozen_till_date` on Company; blocks even Administrator — requires
`set_posting_time: 1` so the backdated date is honored), and `tax_mismatch` yields a
posted-but-flagged invoice where the document disagrees with the ledger — both are the
ground truth the verification coverage gate is tested against.

## Companion tooling
- **`normalize_documents.py`** — maps the real CORD (1,000) + SROIE (987) receipt images
  into this same `document` schema, so real images drive the extraction front-end.
  → `../data/documents/normalized/{cord,sroie}.jsonl` (+ sample PNGs).
- **`cross_validate_odoo.py`** — replays a slice of the generated invoices through a
  **second, independent engine** (Odoo 17, `odoo/docker-compose.yml`, port 8101) and
  compares the double-entry. First run: **50/50 agree** (expense debit == payable credit,
  both balanced) → the postings are real accounting, not an ERPNext artifact.
  → `../data/ground-truth/erpnext_vs_odoo.jsonl`.

## Record shape (one JSONL line)
```json
{"id":"GTC-00001","scenario":"standard","voucher":"ACC-PINV-2026-00001",
 "document":{"supplier_name":"...","bill_no":"INV-2026001","invoice_date":"2026-08-01",
             "currency":"USD","fx_to_usd":1.0,"lines":[{"item_code":"...","qty":6,"unit_price":158,"amount":948.0}],"taxes":[]},
 "posting_proposal":{"grand_total":948.0,"base_grand_total":948.0,"net_total":948.0,"total_taxes":0.0,"credit_to":"Creditors - GTC"},
 "gl_entries":[{"account":"Creditors - GTC","debit":0.0,"credit":948.0,"against":"..."},
               {"account":"Administrative Expenses - GTC","debit":948.0,"credit":0.0,"against":"..."}],
 "checks":{"debits":948.0,"credits":948.0,"balanced":true,"n_gl":2}}
```
`document` = the extraction target (what OCR/LLM reads off the vendor invoice).
`gl_entries` = correct-by-construction ground truth (ERPNext enforced debits==credits).

## First run
500 invoices → **500 posted, 500 balanced, 0 errors** (2026-08-06). Scales linearly:
`./run_generator.sh 5000`. Deterministic RNG seed → reproducible.

## Next
- Cross-validate a slice against Odoo's `account.move.line` (second engine, LGPL-3.0).
- Pair the `document` blocks with real invoice *images* (CORD/SROIE) for the extraction front-end.
- Add closed-period and tax-mismatch negative scenarios for the verification coverage gate.
