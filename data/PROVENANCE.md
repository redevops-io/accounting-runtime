# Data provenance — AI Accounting Runtime
Retrieved 2026-08-06. See ~/Documents/AI_ACCOUNTING_RUNTIME_DATA_SOURCES.md for full analysis.
All items below are public-domain or clearly reuse-licensed. NO gated/copyrighted content staged.

## regulatory/ (POLICY_DERIVED evidence corpus)
- irc/usc26.xml — IRC Title 26, USLM XML, 55.9 MB, 2,276 sections.
  src: uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc26@119-102.zip · LICENSE: PUBLIC DOMAIN (17 USC §105)
- cfr/title-26-full.xml — 26 CFR full text, 84 MB (ECFR root).
  cfr/title-26-structure.json — hierarchy, 2 MB.
  src: ecfr.gov/api/versioner/v1/{full,structure}/2026-08-04/title-26.* · LICENSE: PUBLIC DOMAIN
- irs-pubs/{p334,p538,p946,p463}.pdf — IRS pubs (334 Small Business, 538 Accounting Periods/Methods,
  946 Depreciation, 463 Travel). src: irs.gov/pub/irs-pdf/ · LICENSE: PUBLIC DOMAIN
  (NOTE: Pub 535 discontinued — 334 supersedes.)

## coa/ (chart-of-accounts seeds — ERPNext, GPL-3.0)
- standard_chart_of_accounts.py / _with_account_number.py — generic (US-style) built-in template.
- de_kontenplan_SKR04.json, fr_plan_comptable_general.json, in_standard_chart_of_accounts.json — localized.
  src: raw.githubusercontent.com/frappe/erpnext/develop/.../chart_of_accounts/

## tax/
- eu-vat-rates.json — EU VAT standard/reduced rates. src: github.com/benbucksch/eu-vat-rates · LICENSE: MIT

## documents/ (extraction inputs)
- cord-v2/ — CORD receipts, 1,000 records (line items + tax + boxes), 2.2 GB.
  src: HF naver-clova-ix/cord-v2 · LICENSE: CC-BY-4.0
- sroie-2019/ — SROIE receipts, 987 records (company/date/address/total + boxes), 487 MB.
  src: HF jsdnrs/ICDAR2019-SROIE · LICENSE: CC-BY-4.0
  (No dataset pairs document→treatment; that link is minted by the ERPNext generator.)

## statements/ (verification / tie-out)
- 2024q1/ — SEC EDGAR Financial Statement Data Set: sub(6,028)/num(3,428,695)/tag/pre TSV.
  src: sec.gov/files/dera/data/financial-statement-data-sets/2024q1.zip · LICENSE: PUBLIC DOMAIN
  NOTE: SEC endpoints require a descriptive User-Agent header or 403.

## NOT staged (do not embed — see manifest): FASB ASC, GASB, IFRS, Deloitte IAS Plus, DocILE data, RVL-CDIP, FUNSD.

## ground-truth/ (GENERATED — the document→treatment pairs no public dataset provides)
- gtc_pairs.jsonl — 5,400 records through ERPNext's real engine (2026-08-06):
  5,100 posted / 5,100 balanced / 300 expected refusals (closed_period) / 0 unexpected failures.
  Dates spread across FY2026 (Jan–Aug). 8 scenarios: standard/with_tax/multi_line/discount/
  foreign_currency/duplicate/closed_period(negative)/tax_mismatch(labeled). Generator:
  sandbox/generate_ground_truth.py (deterministic seed). Engine: dedicated erpgen ERPNext
  v16.31.1 sandbox (:8100), company "Ground Truth Co.". Scales linearly (COUNT env).
  LICENSE: generated data is ours (engine GPL-3.0 does not encumber output).

## documents/normalized/ (real images mapped to our document schema)
- cord.jsonl (1,000) + sroie.jsonl (987) — CORD/SROIE receipts normalized into the runtime's
  `document` schema (SROIE: supplier/date/total; CORD: line-items/tax/total). samples/*.png = a
  few decoded images. Generator: sandbox/normalize_documents.py. LICENSE: CC-BY-4.0 (source data).

## ground-truth/erpnext_vs_odoo.jsonl (two-engine cross-validation)
- A slice of the generated `standard` invoices replayed through Odoo 17's independent posting
  engine and compared to ERPNext's double-entry. First run: 50/50 agree (expense debit ==
  payable credit, both balanced). Generator: sandbox/cross_validate_odoo.py. Two disposable
  engines: erpgen ERPNext (:8100) + odoogen Odoo (:8101).
