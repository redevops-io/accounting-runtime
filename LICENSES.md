# Licenses

## This project

Licensed under **AGPL-3.0 with an additional permission waiving section 13** (remote
network interaction) — see [`LICENSE`](./LICENSE). Practically: copyleft on distribution
of source, but **no network-use copyleft** (equivalent to GPLv3 for SaaS). This is a
license grant, not legal advice.

## Third-party software

This is an **example** that composes existing open-source engines. It does not fork or
embed them into a single binary — it talks to them **at arm's length** (REST / RPC over a
process boundary), which is what keeps the license boundaries clean.

| Component | License | How this project uses it | Commercial-deployment note |
|---|---|---|---|
| **ERPNext** (frappe/erpnext) | **GPL-3.0** | The accounting engine that computes the double-entry postings (ground-truth generator). Talked to over its REST API; deployed as a separate, unmodified service. | ✅ Usable. GPLv3 has **no network-use trigger**; an app calling ERPNext's API is not a derivative work. Deploy stock ERPNext as a separate service; if you *modify and distribute* it, those modifications are GPL. |
| **Odoo Community** | **LGPL-3.0** | Second, independent accounting engine used to cross-validate the postings (XML-RPC, separate process). | ✅ Usable, incl. commercially. Used only as an external validator here. |
| **huggingface_hub**, **pyarrow**, **pandas** | Apache-2.0 / permissive | Pull + read the document datasets. | ✅ Permissive. |

## Data sources (evaluation & testing)

| Dataset | Source | License |
|---|---|---|
| **CORD** (receipts, line items) | HF `naver-clova-ix/cord-v2` | **CC-BY-4.0** |
| **SROIE** (receipts) | HF `jsdnrs/ICDAR2019-SROIE` | **CC-BY-4.0** |
| **SEC EDGAR Financial Statement Data Sets** | sec.gov | **Public domain** (US Gov) |
| **IRC Title 26** (USLM XML) | uscode.house.gov | **Public domain** |
| **26 CFR** | ecfr.gov Versioner API | **Public domain** |
| **IRS Publications** (334, 538, 946, 463) | irs.gov/pub/irs-pdf | **Public domain** |
| **ERPNext charts of accounts** | frappe/erpnext | **GPL-3.0** |
| **EU VAT rates** | github.com/benbucksch/eu-vat-rates | **MIT** |

Full retrieval detail in [`data/PROVENANCE.md`](./data/PROVENANCE.md).

## Deliberately NOT used (do-not-embed)

FASB ASC (© Financial Accounting Foundation), GASB, IFRS, Deloitte IAS Plus — copyrighted;
referenced by number only, never reproduced. DocILE data and RVL-CDIP (research/unclear
license) and FUNSD (non-commercial) — excluded from this commercial-intent example.

## Clean commercial posture

Ship on **CC0 / permissive** components; keep any AGPL component (e.g. a validator) as an
**internal** tool; treat **ERPNext (GPLv3)** as an arm's-length optional backend. Integrations
to commercial systems (QuickBooks Online, Xero, Drake) require those vendors' developer/API
agreements — the bigger real-world gate than any open-source license. Confirm specifics with
counsel before shipping.
