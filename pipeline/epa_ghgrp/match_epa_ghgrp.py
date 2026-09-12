"""
Match EPA GHGRP facility-level Scope 1 (direct) emissions to our S&P 500
ticker roster via the parent-company field, as a real-data supplement for
companies with no findable CDP/sustainability-report PDF.

GHGRP covers only Scope 1 (direct, on-site combustion/process emissions
from facilities emitting >=25,000 tCO2e/yr) -- it has no Scope 2 data,
since it's a regulatory registry of direct emitters, not a corporate
disclosure framework. So a match here can only ever fill scope1_tco2e.

Conservative by design (same "never fabricate" principle as the main
pipeline): only accepts a match when the normalized company name is
IDENTICAL to the normalized EPA parent-company name. No fuzzy/substring
matching -- that would risk false positives (e.g. matching the wrong
"American ..." company). Anything not an exact normalized match is left
out entirely rather than guessed.

Usage: py match_epa_ghgrp.py
Writes epa_ghgrp_matches.csv: ticker, security, epa_parent_company,
epa_scope1_tco2e, facility_count
"""
import csv
import glob
import os
import re

import openpyxl
from pyxlsb import open_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(PIPELINE_DIR)

SUFFIXES = [
    "INCORPORATED", "CORPORATION", "COMPANY", "HOLDINGS", "HOLDING",
    "GROUP", "ENTERPRISES", "INTERNATIONAL", "INC", "CORP", "CO", "LLC",
    "LTD", "LP", "PLC", "LLP",
]


def normalize(name):
    if not name:
        return ""
    s = name.upper()
    s = re.sub(r"[.,'\"()]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("THE "):
        s = s[4:]
    words = s.split(" ")
    while words and words[-1] in SUFFIXES:
        words.pop()
    return " ".join(words)


def load_ticker_roster():
    """Combine every ticker->name pair we have anywhere in the repo."""
    roster = {}
    for path in glob.glob(os.path.join(PIPELINE_DIR, "remaining_tickers", "*.txt")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                ticker, name = line.split(",", 1)
                roster[ticker] = name
    for path in glob.glob(os.path.join(REPO_DIR, "data", "batches", "*.csv")):
        with open(path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("ticker") and row.get("security"):
                    roster[row["ticker"]] = row["security"]
    master = os.path.join(REPO_DIR, "data", "environmental_emissions_master.csv")
    if os.path.isfile(master):
        with open(master, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("ticker") and row.get("security"):
                    roster[row["ticker"]] = row["security"]
    return roster


def load_epa_scope1_by_parent():
    """Facility Id -> Total reported direct emissions, from the 2023
    Direct Point Emitters sheet."""
    wb = openpyxl.load_workbook(
        os.path.join(HERE, "summary_2023", "ghgp_data_2023.xlsx"),
        read_only=True, data_only=True)
    ws = wb["Direct Point Emitters"]
    rows = ws.iter_rows(values_only=True)
    for _ in range(4):
        next(rows)  # skip title/notes/header rows
    facility_emissions = {}
    for row in rows:
        fac_id = row[0]
        total = row[13]
        if fac_id is not None and total is not None:
            facility_emissions[fac_id] = total

    # Facility Id -> parent company name, from the 2023 tab of the parent
    # company workbook.
    facility_parent = {}
    with open_workbook(os.path.join(HERE, "parent_company.xlsb")) as pwb:
        with pwb.get_sheet("2023") as sheet:
            rows = sheet.rows()
            next(rows)  # header
            for row in rows:
                vals = [c.v for c in row]
                if len(vals) < 10:
                    continue
                fac_id, parent_name = vals[0], vals[9]
                if fac_id is not None and parent_name:
                    facility_parent.setdefault(fac_id, []).append(parent_name)

    parent_totals = {}  # normalized parent name -> [raw_name, total, count]
    for fac_id, total in facility_emissions.items():
        for parent_name in facility_parent.get(fac_id, []):
            key = normalize(parent_name)
            if not key:
                continue
            entry = parent_totals.setdefault(key, [parent_name, 0.0, 0])
            entry[1] += total
            entry[2] += 1
    return parent_totals


def main():
    roster = load_ticker_roster()
    print(f"Ticker roster: {len(roster)} companies")
    parent_totals = load_epa_scope1_by_parent()
    print(f"EPA GHGRP parent companies (2023): {len(parent_totals)}")

    matches = []
    for ticker, name in sorted(roster.items()):
        key = normalize(name)
        if key in parent_totals:
            raw_name, total, count = parent_totals[key]
            matches.append((ticker, name, raw_name, total, count))

    out_path = os.path.join(HERE, "epa_ghgrp_matches.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "security", "epa_parent_company", "epa_scope1_tco2e", "facility_count"])
        for row in matches:
            w.writerow(row)

    print(f"\nExact normalized-name matches: {len(matches)}")
    for ticker, name, raw_name, total, count in matches:
        print(f"  {ticker:6} {name:35} -> {raw_name:35} {total:>14,.0f} t  ({count} facilities)")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
