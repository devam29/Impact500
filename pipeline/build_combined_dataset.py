"""
Combine everything this pipeline has collected so far into one CSV:
- environmental_emissions_master.csv (Level input: real disclosed Scope
  1/2 tonnage from CDP PDFs, sustainability reports, and EPA GHGRP, per
  merge_batches.py)
- sbti/sbti_matches.csv (Velocity input: SBTi science-based target status,
  per sbti/match_sbti.py)

This does NOT compute level_score/velocity_score/integrity_score -- it
only merges the raw inputs collected so far into one row-per-ticker file,
same "raw inputs, not final scores" spirit as environmental_emissions_master.csv
itself (see pipeline/README.md). A ticker with no SBTi match gets blank
sbti_* fields, same convention as a ticker with no emissions match getting
data_source=none -- absence is left visible, not filled with a guess.

Usage: py build_combined_dataset.py
Reads:  ../data/environmental_emissions_master.csv, sbti/sbti_matches.csv
Writes: ../data/environmental_combined.csv
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(HERE)

MASTER_PATH = os.path.join(REPO_DIR, "data", "environmental_emissions_master.csv")
SBTI_PATH = os.path.join(HERE, "sbti", "sbti_matches.csv")
OUT_PATH = os.path.join(REPO_DIR, "data", "environmental_combined.csv")

SBTI_FIELDS = [
    "sbti_near_term_status", "sbti_near_term_target_classification",
    "sbti_near_term_target_year", "sbti_long_term_status",
    "sbti_long_term_target_year", "sbti_net_zero_status",
    "sbti_net_zero_year", "sbti_full_target_language", "sbti_date_updated",
]


def load_sbti_by_ticker():
    by_ticker = {}
    with open(SBTI_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            by_ticker[row["ticker"]] = {
                "sbti_near_term_status": row["near_term_status"],
                "sbti_near_term_target_classification": row["near_term_target_classification"],
                "sbti_near_term_target_year": row["near_term_target_year"],
                "sbti_long_term_status": row["long_term_status"],
                "sbti_long_term_target_year": row["long_term_target_year"],
                "sbti_net_zero_status": row["net_zero_status"],
                "sbti_net_zero_year": row["net_zero_year"],
                "sbti_full_target_language": row["full_target_language"],
                "sbti_date_updated": row["date_updated"],
            }
    return by_ticker


def main():
    sbti_by_ticker = load_sbti_by_ticker()
    print(f"SBTi matches available: {len(sbti_by_ticker)}")

    with open(MASTER_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        master_fields = reader.fieldnames
        rows = list(reader)
    print(f"Master rows: {len(rows)}")

    out_fields = master_fields + ["sbti_matched"] + SBTI_FIELDS
    matched_count = 0
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for row in rows:
            sbti = sbti_by_ticker.get(row["ticker"])
            out = dict(row)
            if sbti:
                matched_count += 1
                out["sbti_matched"] = "True"
                out.update(sbti)
            else:
                out["sbti_matched"] = "False"
                for field in SBTI_FIELDS:
                    out[field] = ""
            w.writerow(out)

    print(f"Rows with an SBTi match: {matched_count} / {len(rows)}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
