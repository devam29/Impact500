"""
Match Science Based Targets initiative (SBTi) company target data to our
S&P 500 ticker roster, as a real-data input for the Velocity sub-score --
whether a company is decarbonizing fast enough, benchmarked against a real
science-based pathway. This is a separate signal from the Level sub-score's
raw Scope 1/2 tonnage (collected elsewhere in this pipeline): a company can
have a validated science-based target even when we have no disclosed
emissions figure for it, and vice versa.

Source: SBTi's official by-company target dashboard export
(sbti_companies.xlsx, downloaded from
https://files.sciencebasedtargets.org/production/files/companies-excel.xlsx,
~15,600 companies globally, updated weekly by SBTi).

Conservative by design (same "never fabricate" principle as the rest of
this pipeline, and the same approach as epa_ghgrp/match_epa_ghgrp.py):
only accepts a match when the normalized company name is IDENTICAL to a
normalized SBTi company name, and only when that normalized name is
unambiguous (maps to exactly one SBTi row). No fuzzy/substring matching --
that risks a false match (e.g. a generically-named subsidiary). Anything
not an exact, unambiguous match is left out entirely rather than guessed.

Usage: py match_sbti.py
Writes sbti_matches.csv: ticker, security, sbti_company_name,
near_term_status, near_term_target_classification, near_term_target_year,
long_term_status, long_term_target_year, net_zero_status, net_zero_year,
full_target_language, date_updated
"""
import csv
import glob
import os
import re

import openpyxl

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


def load_sbti_by_name():
    """normalized company name -> row dict, skipping ambiguous names that
    map to more than one distinct SBTi company (leave those out entirely
    rather than guess which one is the S&P 500 constituent)."""
    wb = openpyxl.load_workbook(
        os.path.join(HERE, "sbti_companies.xlsx"), read_only=True, data_only=True)
    ws = wb["Data"]
    rows = ws.iter_rows(values_only=True)
    header = next(rows)
    idx = {name: i for i, name in enumerate(header) if name}

    by_name = {}
    ambiguous = set()
    for row in rows:
        company_name = row[idx["company_name"]]
        key = normalize(company_name)
        if not key:
            continue
        if key in by_name and normalize(by_name[key][idx["company_name"]]) == key \
                and by_name[key][idx["company_name"]] != company_name:
            ambiguous.add(key)
        by_name[key] = row
    for key in ambiguous:
        by_name.pop(key, None)
    return by_name, idx


def main():
    roster = load_ticker_roster()
    print(f"Ticker roster: {len(roster)} companies")
    sbti_by_name, idx = load_sbti_by_name()
    print(f"SBTi companies (unambiguous normalized names): {len(sbti_by_name)}")

    fields = [
        "near_term_status", "near_term_target_classification", "near_term_target_year",
        "long_term_status", "long_term_target_year", "net_zero_status", "net_zero_year",
        "full_target_language", "date_updated",
    ]

    matches = []
    for ticker, name in sorted(roster.items()):
        key = normalize(name)
        if key in sbti_by_name:
            row = sbti_by_name[key]
            out = [ticker, name, row[idx["company_name"]]]
            for field in fields:
                out.append(row[idx[field]])
            matches.append(out)

    out_path = os.path.join(HERE, "sbti_matches.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "security", "sbti_company_name"] + fields)
        for row in matches:
            w.writerow(row)

    print(f"\nExact normalized-name matches: {len(matches)}")
    for row in matches:
        ticker, name, sbti_name = row[0], row[1], row[2]
        near_term_status = row[3]
        print(f"  {ticker:6} {name:35} -> {sbti_name:35} [{near_term_status}]")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
