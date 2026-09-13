"""
Match Climate TRACE's Power-sector ownership data to our S&P 500 ticker
roster, as an independent (satellite/sensor-based, not self-reported)
signal for the Integrity sub-score -- confirmation that a company
actually owns/controls specific power-generation assets that an
independent tracker also observes, separate from whatever the company
itself discloses.

Source: Climate TRACE's "Ownership" data package, Power sector only,
worldwide, downloaded via the guided wizard at
https://climatetrace.org/data (inventory version 5.10.0, pulled
2026-09-13). This file does NOT include emissions estimates -- it only
gives which physical assets (power plants) each parent company owns and
what share. Joining this against Climate TRACE's separate Emissions
package (same version, by source_id) to get an independent tCO2e number
per company is a natural next step but was not completed this session
(the guided wizard's multi-step flow proved unreliable to drive via
browser automation for a second, larger custom query -- see
pipeline/README.md for the full story). What's here is deliberately
just the ownership/coverage signal, not a cross-checked emissions number.

Conservative by design (same principle as epa_ghgrp and sbti matching):
only accepts a match when the normalized parent_name is IDENTICAL to a
normalized company name in our roster. No fuzzy matching.

Usage: py match_climate_trace.py
Writes climate_trace_matches.csv: ticker, security, asset_count,
sectors (always "power" here, kept for whenever more sectors are added),
subsectors (semicolon-joined distinct list), countries (semicolon-joined
distinct iso3 list), min/max/avg overall_share_percent, sample_source_names
(first 3, semicolon-joined)
"""
import csv
import glob
import os
import re
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(PIPELINE_DIR)

OWNERSHIP_PATH = os.path.join(HERE, "power_ownership_v5_10_0.csv")

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


def load_ownership_by_parent():
    by_parent = defaultdict(list)
    with open(OWNERSHIP_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = normalize(row["parent_name"])
            if key:
                by_parent[key].append(row)
    return by_parent


def main():
    roster = load_ticker_roster()
    print(f"Ticker roster: {len(roster)} companies")
    by_parent = load_ownership_by_parent()
    print(f"Climate TRACE Power-sector parent entities: {len(by_parent)}")

    matches = []
    for ticker, name in sorted(roster.items()):
        key = normalize(name)
        rows = by_parent.get(key)
        if not rows:
            continue
        shares = [float(r["overall_share_percent"]) for r in rows if r["overall_share_percent"]]
        subsectors = sorted(set(r["source_subsector"] for r in rows if r["source_subsector"]))
        countries = sorted(set(r["iso3_country"] for r in rows if r["iso3_country"]))
        sample_names = [r["source_name"] for r in rows[:3]]
        matches.append([
            ticker, name, len(rows), "power",
            ";".join(subsectors), ";".join(countries),
            f"{min(shares):.1f}" if shares else "",
            f"{max(shares):.1f}" if shares else "",
            f"{sum(shares)/len(shares):.1f}" if shares else "",
            ";".join(sample_names),
        ])

    out_path = os.path.join(HERE, "climate_trace_matches.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "security", "asset_count", "sectors", "subsectors",
                    "countries", "min_share_percent", "max_share_percent",
                    "avg_share_percent", "sample_source_names"])
        for row in matches:
            w.writerow(row)

    print(f"\nExact normalized-name matches: {len(matches)}")
    for row in matches:
        print(f"  {row[0]:6} {row[1]:35} {row[2]:>4} assets  avg share {row[8]}%")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
