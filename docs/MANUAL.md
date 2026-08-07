# AI Accounting Runtime — User Manual

A governed AI layer for bookkeeping and accounting work. It reads your documents, decides
the accounting treatment, proves it against the rules, and posts it to your books once you
approve — reproducibly and with an audit trail.

**The one rule that governs everything below:** the AI *extracts, retrieves, proposes,
verifies, and records*; **you decide**; and authoritative systems (your ledger, IRS e-file,
EFTPS) *execute*. Nothing that moves money or closes a period happens without an explicit
human approval, and every decision can be replayed later without re-running a model.

---

## 1. What runs where

The engine is a **server-side service** (the runtimes, retrieval, and ledger adapters). Each
platform ships a **thin client** onto it. Two ways to run it, from the same public repo:

- **Self-host** — `docker compose up` starts the runtime and connects to your existing
  accounting system (ERPNext, QuickBooks Online, Xero) or provisions an ERPNext for you.
  Runs on any Linux, Windows, or macOS machine or your own server.
- **Hosted** — sign up, connect QuickBooks/Xero over OAuth, nothing to install.

| Platform | What it is for |
|---|---|
| **Web console** (works everywhere) | The full operating console: Inbox · Review · Ledgers · Close & Reports · Tax · Audit |
| **Desktop app** (Windows / Linux / macOS) | The same console packaged, plus watch-a-folder import and offline document capture — the daily driver at a desk |
| **Mobile app** (iOS / Android) | Capture (photograph a receipt/invoice) and approve on the go (approve / amend / reject). The phone is a camera and an approval button — the engine never runs on it |

---

## 2. Under the hood — which part does what

The runtimes are not glued together ad-hoc; each owns one kind of decision.

| Component | Its job |
|---|---|
| **Document worker** | Parse the incoming invoice / bill / receipt: vendor, amount, date, tax, currency, line items |
| **Execution Planner** | Choose *how* to handle each part — deterministic parser vs. document model vs. retrieval-assisted classification vs. human review — optimizing confidence, cost, latency, and policy |
| **Context Runtime** | Retrieve the evidence a decision needs and route it to the right representation: vendor history and duplicates, prior coding decisions, chart-of-account descriptions, approval limits |
| **ReDevOps RAG** | Search the **tax / legal / policy corpus** — pinned, reference-first, authoritative text kept separate from historical examples and model explanation |
| **Mission Runtime** | Run the work as a governed mission: enforce the verification coverage gate, approval gates, checks (debits = credits, duplicate, period-open, read-back), and the replayable evidence chain |
| **Discovery Runtime** | Turn signals into work — "these bills arrived, propose processing them"; month-end and close prompts |
| **Your accounting system** (ERPNext / QuickBooks / Xero) | **The book of record.** It owns the chart of accounts, the authoritative journal entries, tax config, and financial statements. The runtime *proposes*; the ledger *posts* |

Two facts this implies:

- **It does search tax and legal documents.** Policy-derived decisions (deductibility, GL
  mapping, tax treatment, capitalize vs. expense) are grounded in retrieved **authoritative
  text** — the U.S. Internal Revenue Code (Title 26), Treasury Regulations (26 CFR), and IRS
  publications — and each such decision **cites the text it relied on**. U.S. GAAP is
  referenced by ASC number rather than reproduced, because that text is copyrighted.
- **It does parse documents into the ledger — but never blindly.** The worker extracts the
  fields; the ledger computes the actual double-entry. The runtime **does not fabricate
  journal entries**; the accounting engine produces them, and the runtime reads them back
  to confirm the books contain exactly what was approved.

---

## 3. Working with it, task by task

Each task below states plainly **what the runtime does** and **what you do**.

### 3.1 Create a ledger for a new company (onboarding)

- **The runtime does:** connect an existing QuickBooks/Xero/ERPNext, or provision a fresh
  ERPNext with the correct localized **chart of accounts and tax configuration**; store the
  engagement's policies (approval limits, GL-mapping preferences, who signs off).
- **You do:** enter the company name, country, entity type, fiscal year, and tax
  registrations; choose connect-existing or provision-new; confirm the chart of accounts.

### 3.2 Add documents

- **The runtime does:** accept documents from drag-and-drop, a watched folder, a forwarding
  email address (e.g. `bills@yourco…`), or the mobile camera; parse each one and choose the
  extraction method per document.
- **You do:** send the documents in. You never type an invoice by hand — you confirm what
  was read.

### 3.3 Review and approve

- **The runtime does:** turn each parsed document into a **proposal** showing the source
  document, the extracted fields, the proposed posting, the **evidence** behind each
  policy-derived decision (the cited IRS/CFR text), confidence, exceptions, and the
  before/after ledger impact. It blocks anything where a material element is not covered.
- **You do:** review the proposal and choose **Approve · Amend · Reject**. On approval the
  runtime posts once (idempotently), reads the record back, and reconciles it.

### 3.4 Close the month

- **The runtime does:** run the close checklist (all bills booked, bank reconciled, payroll
  posted, accruals done), verify the period, and **stage** the Period Closing.
- **You do:** clear any exceptions it surfaces, then **approve the close**. The closing entry
  never posts without your sign-off.

### 3.5 Quarterly reports and filing

- **The runtime does:** generate the period statements (P&L, balance sheet, cash flow) from
  the closed ledger and **prepare** the applicable returns (sales-tax, quarterly estimated
  tax, Form 941, …) as **draft workpapers with every number traced to a ledger entry**.
- **You do:** review and approve the drafts. **Actual filing** happens through an
  authoritative rail — your accounting platform's filing feature, an IRS-authorized e-file
  integration, or a state portal. The runtime prepares and hands off; it is not itself the
  e-file provider.

### 3.6 Pay taxes

- **The runtime does:** compute the liability, assemble the payment (amount, period,
  account), and — after your approval — route it through **EFTPS, a state portal, or a
  payments integration**, idempotently, then read the confirmation back into the evidence
  chain.
- **You do:** review the computed liability and **approve the payment**. A payment is a hard
  approval gate; the runtime never moves money on its own.

### 3.7 Audit and replay

- **The runtime does:** persist a replayable evidence chain for every transaction — the
  document, the parse, the cited rules, the proposal, the approver, the ledger response.
- **You do:** open any transaction months later; it renders from stored artifacts **without
  re-running any model** — the record you hand a regulator.

---

## 4. Boundaries — what the runtime will not do

- **It is not your ledger.** Your accounting system stays the book of record; the runtime
  proposes and governs, it does not replace the general ledger.
- **It does not file or pay autonomously.** E-filing needs a licensed provider or
  integration; tax payments go through EFTPS/state rails. The runtime prepares, gates on
  human approval, and records — it never becomes an unlicensed filer or money-mover.
- **It does not post past a hard gate.** Anything that moves money or closes a period
  requires explicit human approval and produces a replayable evidence chain. This is the
  point of the system — reliable and auditable, not autonomous-and-hope.
- **It does not reproduce copyrighted standards.** GAAP (FASB ASC) is referenced by number;
  the authoritative text it embeds and cites is public-domain (IRC, CFR, IRS pubs).

---

## 5. Real today vs. designed

Built and verified: the **data foundation** (real tax/regulation corpus, real documents,
correct-by-construction posting pairs cross-validated across two independent accounting
engines) and the ledger posting/read-back path. The console and the end-to-end mission flow
described above are the product being built on top of that foundation — see
`AI_ACCOUNTING_RUNTIME_IMPLEMENTATION_PLAN.md`.
