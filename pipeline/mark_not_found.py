"""Append a 'no public report found' row so the ticker is visibly accounted
for in the CSV rather than silently missing.
Usage: py mark_not_found.py <ticker> <security_name> <csv_path>"""
import sys
from process_company import append_row, FIELDNAMES  # noqa: E402

_, ticker, security, csv_path = sys.argv
row = {k: "" for k in FIELDNAMES}
row.update({"ticker": ticker, "security": security, "data_source": "none",
            "notes": "no_public_report_found"})
append_row(csv_path, row)
print(f"{ticker}: no report found")
