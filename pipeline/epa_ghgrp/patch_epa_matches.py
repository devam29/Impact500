"""
One-time backfill: for tickers already attempted via CDP/sustainability-
report search that came up with no usable Scope 1 number, patch in the
real EPA GHGRP Scope 1 (direct emissions) figure from
epa_ghgrp_matches.csv where an exact normalized parent-company match
exists. Only touches rows that currently have no scope1_tco2e -- never
overwrites a real CDP/sustainability-report figure.

Usage: py patch_epa_matches.py <path-to-batch-csv> [<path-to-batch-csv> ...]
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIELDNAMES = [
    "ticker", "security", "data_source", "report_url",
    "scope1_tco2e", "scope2_location_tco2e", "scope2_market_tco2e",
    "scope1_base_year_end", "scope1_base_year_tco2e", "revenue_usd",
    "is_cdp_format", "notes",
]

with open(os.path.join(HERE, "epa_ghgrp_matches.csv"), encoding="utf-8", newline="") as f:
    epa_by_ticker = {r["ticker"]: r for r in csv.DictReader(f)}

for path in sys.argv[1:]:
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    patched = 0
    for row in rows:
        epa = epa_by_ticker.get(row["ticker"])
        if epa is None or row.get("scope1_tco2e"):
            continue
        prior_note = row.get("notes") or ""
        prior_source = row.get("data_source")
        prior_url = row.get("report_url")
        row["data_source"] = "epa_ghgrp"
        row["scope1_tco2e"] = epa["epa_scope1_tco2e"]
        row["notes"] = (
            f"EPA GHGRP 2023 Direct Emitters, matched via parent company "
            f"'{epa['epa_parent_company']}' ({epa['facility_count']} facilities). "
            f"Scope 1 (direct/on-site) only -- GHGRP does not cover Scope 2. "
            f"Prior attempt: data_source={prior_source}, "
            f"report_url={prior_url or 'n/a'}, notes={prior_note or 'n/a'}"
        )
        patched += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"{path}: patched {patched} rows")
