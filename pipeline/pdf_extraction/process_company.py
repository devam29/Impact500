"""
Download one company's emissions report PDF, extract Scope 1/2 fields via
extract_emissions.py, and append one row to the shared CSV. Designed to
be called once per company after a web search has already located the
PDF URL -- the search step and this extraction step are kept separate on
purpose, so locating a document never requires reading the whole thing.

Usage:
    py process_company.py <ticker> <security_name> <pdf_url> <source_type> <csv_path>

source_type: "cdp_pdf" or "sustainability_report" -- decided by whoever
found the document, based on what kind of report it is; recorded in the
output row so low-confidence (sustainability_report) rows can be told
apart from high-confidence (cdp_pdf) ones later.

Never fabricates data: on any failure (download, parse, no fields found)
the row is still written with whatever was found (possibly nothing) plus
a `notes` column explaining what happened, so gaps are visible rather
than silently missing.
"""
import csv
import os
import sys
import traceback

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_emissions import extract  # noqa: E402

FIELDNAMES = [
    "ticker", "security", "data_source", "report_url",
    "scope1_tco2e", "scope2_location_tco2e", "scope2_market_tco2e",
    "scope1_base_year_end", "scope1_base_year_tco2e", "revenue_usd",
    "is_cdp_format", "notes",
]

PDF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdfs")


def append_row(csv_path, row):
    file_exists = os.path.isfile(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        if not file_exists or os.path.getsize(csv_path) == 0:
            writer.writeheader()
        writer.writerow(row)


def process(ticker, security, pdf_url, source_type, csv_path):
    os.makedirs(PDF_DIR, exist_ok=True)
    pdf_path = os.path.join(PDF_DIR, f"{ticker}.pdf")
    row = {"ticker": ticker, "security": security, "data_source": source_type,
           "report_url": pdf_url}

    # Some corporate sites (CDN/WAF-fronted) return 403 to a bare
    # requests.get with a minimal UA but succeed with a fuller
    # browser-like header set (Accept/Accept-Language/Referer). Try the
    # cheap request first, only pay for the fuller one on failure.
    header_variants = [
        {"User-Agent": "Mozilla/5.0 (research script; hackathon project)"},
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/pdf,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
        },
    ]
    resp = None
    last_err = None
    for headers in header_variants:
        try:
            resp = requests.get(pdf_url, timeout=30, headers=headers)
            resp.raise_for_status()
            break
        except Exception as e:
            last_err = e
            resp = None
    if resp is None:
        row["notes"] = f"download_error: {last_err}"
        append_row(csv_path, row)
        print(f"{ticker}: FAIL download_error {last_err}")
        return
    try:
        if not resp.content[:4] == b"%PDF":
            row["notes"] = "not_a_pdf"
            append_row(csv_path, row)
            print(f"{ticker}: FAIL not_a_pdf")
            return
        with open(pdf_path, "wb") as f:
            f.write(resp.content)
    except Exception as e:
        row["notes"] = f"download_error: {e}"
        append_row(csv_path, row)
        print(f"{ticker}: FAIL download_error {e}")
        return

    try:
        fields = extract(pdf_path)
        row.update(fields)
        if not fields.get("scope1_tco2e") and not fields.get("scope2_location_tco2e") \
                and not fields.get("scope2_market_tco2e"):
            row["notes"] = "no_fields_extracted"
    except Exception as e:
        row["notes"] = f"extract_error: {e}"
        traceback.print_exc()

    append_row(csv_path, row)
    got = [k for k in ("scope1_tco2e", "scope2_location_tco2e", "scope2_market_tco2e") if row.get(k)]
    print(f"{ticker}: OK found={got or 'none'}")


if __name__ == "__main__":
    _, ticker, security, pdf_url, source_type, csv_path = sys.argv
    process(ticker, security, pdf_url, source_type, csv_path)
