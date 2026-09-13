"""Re-run the current (improved) extractor against a batch CSV's rows,
using the PDF already cached in pdfs/<ticker>.pdf -- no new network
requests, no new searches. Rows with no cached PDF (no_public_report_found
/ download_error) are left untouched since there's nothing to reprocess.
Overwrites the CSV in place with an updated version.

Usage: py reprocess_cached.py <csv_path>
"""
import csv
import os
import sys

from extract_emissions import extract
from process_company import FIELDNAMES, PDF_DIR

csv_path = sys.argv[1]

with open(csv_path, encoding="utf-8", newline="") as f:
    rows = list(csv.DictReader(f))

updated = 0
newly_found = 0
for row in rows:
    ticker = row["ticker"]
    pdf_path = os.path.join(PDF_DIR, f"{ticker}.pdf")
    if not os.path.isfile(pdf_path):
        continue  # nothing cached for this one, leave row as-is
    had_data_before = bool(row.get("scope1_tco2e"))
    try:
        fields = extract(pdf_path)
    except Exception as e:
        print(f"{ticker}: reprocess error {e}")
        continue
    # Clear every extractable field first, then apply the fresh result --
    # otherwise a field the new pass deliberately omits (e.g. base year,
    # now correctly withheld when Scope 1 itself is unanswered) would
    # keep its stale value from an earlier, less careful extraction pass.
    extractable = ("scope1_tco2e", "scope1_source_detail", "scope2_location_tco2e",
                   "scope2_market_tco2e", "scope1_base_year_end",
                   "scope1_base_year_tco2e", "revenue_usd")
    for k in extractable:
        row[k] = ""
    for k, v in fields.items():
        row[k] = v
    got_data_now = bool(row.get("scope1_tco2e") or row.get("scope2_location_tco2e") or row.get("scope2_market_tco2e"))
    if got_data_now and row.get("notes") == "no_fields_extracted":
        row["notes"] = ""  # stale note from the earlier failed extraction pass
    if not had_data_before and got_data_now:
        newly_found += 1
        print(f"{ticker}: RECOVERED scope1={row.get('scope1_tco2e')}")
    updated += 1

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

print(f"Reprocessed {updated} cached rows, newly recovered {newly_found}, total rows {len(rows)}")
