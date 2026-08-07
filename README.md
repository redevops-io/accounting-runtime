# Agentic Accounting Runtime — an example

A working **example** of a governed AI layer for bookkeeping: it reads documents, proposes
the accounting treatment, and posts it to a real ledger — **without fabricating the numbers**.
The accounting engine computes the double-entry; a second engine cross-checks it. Built in a
few hours by composing open-source software.

> This is a **reference example**, not a finished product. It demonstrates the approach and a
> tested data foundation. See [what a full deployment adds](#going-further) below.

## The idea

The hardest data problem in AI accounting is ground truth: no public dataset pairs a source
document with its *correct* bookkeeping entry (real ledgers are private). So we don't
fabricate entries — we **generate them from a real accounting engine** and cross-validate
across a second one:

- **[ERPNext](https://github.com/frappe/erpnext)** (GPL-3.0) posts each invoice; its engine
  computes balanced `GL Entry` rows — correct by construction.
- **[Odoo](https://github.com/odoo/odoo)** (LGPL-3.0) independently posts the same invoices;
  agreement between two engines = strong evidence the postings are real accounting.

## What's here

| Path | What |
|---|---|
| `sandbox/generate_ground_truth.py` | Posts invoices through ERPNext across 8 scenarios (incl. tax, multi-currency, discount, **closed-period refusals**, **tax-mismatch**), reads the GL back, verifies debits==credits |
| `sandbox/cross_validate_odoo.py` | Replays a slice through Odoo and compares the double-entry |
| `sandbox/normalize_documents.py` | Maps real CORD/SROIE receipt images into the runtime's document schema |
| `sandbox/*.compose.yml` | Disposable ERPNext (:8100) + Odoo (:8101), pinned to digests |
| `docs/MANUAL.md` | How the AI Runtime Stack is used, task by task, with clear AI-does / you-do boundaries |
| `data/PROVENANCE.md` | Every dataset, source, and license |

**First run:** 5,100 postings, 100% balanced, 300 correct period-closed refusals, 0 errors;
Odoo cross-validation 50/50 agree. Sample output: `data/ground-truth/sample.jsonl`.

## Quickstart

```bash
# 1. bring up the disposable engines
cd sandbox && docker compose -p erpgen up -d          # ERPNext on :8100 (admin/admin)
docker compose -p odoogen -f odoo/docker-compose.yml up -d   # Odoo on :8101

# 2. generate correct-by-construction posting pairs
./run_generator.sh 500                                 # -> data/ground-truth/gtc_pairs.jsonl

# 3. cross-validate against the second engine
N=50 python3 cross_validate_odoo.py                    # -> erpnext_vs_odoo.jsonl
```

## Going further

This example is the foundation. A production deployment adds: production **document
extraction** (real W-2s/invoices/receipts), the **QuickBooks Online / Xero / Drake** adapters,
the **console / review UI**, human-in-the-loop workflows, multi-tenant auth and SOC 2,
**e-file/MeF** where relevant, and hardening at scale. **We'd love to help build that** —
[redevops.io](https://redevops.io).

## License

[AGPL-3.0 with the section-13 network clause waived](./LICENSE). Third-party components and
data sources: [LICENSES.md](./LICENSES.md).
