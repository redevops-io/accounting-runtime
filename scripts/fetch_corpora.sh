#!/usr/bin/env bash
# Fetch the license-clean data corpora for the AI Accounting Runtime.
# License verdicts: see ~/Documents/AI_ACCOUNTING_RUNTIME_DATA_SOURCES.md
# All sources here are public-domain or clearly reuse-licensed. NO gated/copyrighted content.
set +e
ROOT=/mnt/backup/projects/accounting-runtime/data
UA="ReDevOps accounting-runtime redevops@redevops.io"   # SEC requires a descriptive UA or 403
RAW=https://raw.githubusercontent.com/frappe/erpnext/develop/erpnext/accounts/doctype/account/chart_of_accounts
sz(){ du -h "$1" 2>/dev/null | cut -f1; }
ok(){ printf "  ✓ %-52s %s\n" "$2" "$(sz "$1")"; }

echo "== C. Regulatory: IRS publications (public domain) =="
for p in p334 p538 p946 p463; do
  curl -sL --max-time 60 -A "$UA" "https://www.irs.gov/pub/irs-pdf/$p.pdf" -o "$ROOT/regulatory/irs-pubs/$p.pdf" \
    && ok "$ROOT/regulatory/irs-pubs/$p.pdf" "irs-pubs/$p.pdf"
done

echo "== C. Regulatory: IRC Title 26 USLM XML (public domain) =="
curl -sL --max-time 120 "https://uscode.house.gov/download/releasepoints/us/pl/119/102/xml_usc26@119-102.zip" \
  -o "$ROOT/regulatory/irc/usc26.zip" && ok "$ROOT/regulatory/irc/usc26.zip" "irc/usc26.zip"
unzip -oq "$ROOT/regulatory/irc/usc26.zip" -d "$ROOT/regulatory/irc/" 2>/dev/null \
  && echo "    unzipped: $(ls "$ROOT/regulatory/irc/"*.xml 2>/dev/null | wc -l) xml"

echo "== C. Regulatory: 26 CFR via eCFR Versioner API (public domain) =="
curl -sL --max-time 60 "https://www.ecfr.gov/api/versioner/v1/structure/2026-08-04/title-26.json" \
  -o "$ROOT/regulatory/cfr/title-26-structure.json" && ok "$ROOT/regulatory/cfr/title-26-structure.json" "cfr/title-26-structure.json"
echo "    (full title-26.xml can be large; attempting with a cap)"
curl -sL --max-time 240 "https://www.ecfr.gov/api/versioner/v1/full/2026-08-04/title-26.xml" \
  -o "$ROOT/regulatory/cfr/title-26-full.xml" && ok "$ROOT/regulatory/cfr/title-26-full.xml" "cfr/title-26-full.xml"

echo "== A. Charts of Accounts: ERPNext localized templates (GPL-3.0) =="
for f in standard_chart_of_accounts.py standard_chart_of_accounts_with_account_number.py \
         verified/de_kontenplan_SKR04.json verified/fr_plan_comptable_general.json \
         verified/in_standard_chart_of_accounts.json; do
  out="$ROOT/coa/$(basename "$f")"
  curl -sL --max-time 60 "$RAW/$f" -o "$out" && ok "$out" "coa/$(basename "$f")"
done

echo "== A. Tax: EU VAT rates (MIT) =="
curl -sL --max-time 60 "https://raw.githubusercontent.com/benbucksch/eu-vat-rates/master/rates.json" \
  -o "$ROOT/tax/eu-vat-rates.json" && ok "$ROOT/tax/eu-vat-rates.json" "tax/eu-vat-rates.json"

echo "== D. Statements: SEC EDGAR Financial Statement Data Set, 2024q1 (public domain) =="
curl -sL --max-time 240 -A "$UA" \
  "https://www.sec.gov/files/dera/data/financial-statement-data-sets/2024q1.zip" \
  -o "$ROOT/statements/2024q1.zip" && ok "$ROOT/statements/2024q1.zip" "statements/2024q1.zip"
unzip -oq "$ROOT/statements/2024q1.zip" -d "$ROOT/statements/2024q1/" 2>/dev/null \
  && echo "    tables: $(ls "$ROOT/statements/2024q1/" 2>/dev/null | tr '\n' ' ')"

echo "== DONE =="
find "$ROOT" -type f | wc -l | sed 's/^/  total files: /'
