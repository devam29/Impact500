"""
Combine everything this pipeline has collected so far into one CSV:
- environmental_emissions_master.csv (Level input: real disclosed Scope
  1/2 tonnage from CDP PDFs, sustainability reports, and EPA GHGRP, per
  merge_batches.py)
- sbti/sbti_matches.csv (Velocity input: SBTi science-based target status,
  per sbti/match_sbti.py)
- climate_trace/climate_trace_matches.csv (Integrity input: independent,
  satellite/sensor-based confirmation that a company owns Power-sector
  assets Climate TRACE also tracks -- per
  climate_trace/match_climate_trace.py)
- tier2_estimation/tier2_estimates.csv, if it exists (Level input,
  ESTIMATED not disclosed -- sector-median emissions intensity scaled by
  the company's own revenue/employees, for tickers with no real report.
  Per tier2_estimation/estimate_tier2.py.)
- upright/upright_matches.csv, if it exists (a completely separate
  teammate dataset -- Upright Project's Net Impact Model. NOT a Scope 1/2
  tCO2e figure: it's a modeled, monetized cost/benefit score in "cents
  per dollar of revenue" across four categories (Environment, Health,
  Knowledge, Society). Included here purely because the teammate's job
  is now to merge their data with this one into a single file -- it is
  NOT folded into or compared against the Level/Velocity/Integrity
  emissions columns above, and every column is prefixed `upright_` so
  that's never ambiguous. Per upright/match_upright.py.)

This does NOT compute level_score/velocity_score/integrity_score -- it
only merges the raw inputs collected so far into one row-per-ticker file,
same "raw inputs, not final scores" spirit as environmental_emissions_master.csv
itself (see pipeline/README.md). A ticker with no match on any of these
gets blank fields for that source -- absence is left visible, not filled
with a guess.

Usage: py build_combined_dataset.py
Reads:  ../data/environmental_emissions_master.csv, sbti/sbti_matches.csv,
        climate_trace/climate_trace_matches.csv,
        tier2_estimation/tier2_estimates.csv (optional),
        upright/upright_matches.csv (optional)
Writes: ../data/environmental_combined.csv
"""
import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(HERE)

MASTER_PATH = os.path.join(REPO_DIR, "data", "environmental_emissions_master.csv")
SBTI_PATH = os.path.join(HERE, "sbti", "sbti_matches.csv")
CLIMATE_TRACE_PATH = os.path.join(HERE, "climate_trace", "climate_trace_matches.csv")
TIER2_PATH = os.path.join(HERE, "tier2_estimation", "tier2_estimates.csv")
UPRIGHT_PATH = os.path.join(HERE, "upright", "upright_matches.csv")
OUT_PATH = os.path.join(REPO_DIR, "data", "environmental_combined.csv")

SBTI_FIELDS = [
    "sbti_near_term_status", "sbti_near_term_target_classification",
    "sbti_near_term_target_year", "sbti_long_term_status",
    "sbti_long_term_target_year", "sbti_net_zero_status",
    "sbti_net_zero_year", "sbti_full_target_language", "sbti_date_updated",
]

CLIMATE_TRACE_FIELDS = [
    "climatetrace_power_asset_count", "climatetrace_power_subsectors",
    "climatetrace_power_countries", "climatetrace_power_avg_share_percent",
]

TIER2_FIELDS = [
    "tier2_scope1_tco2e", "tier2_scope2_tco2e", "tier2_method",
    "tier2_sector_used", "tier2_peer_count", "tier2_notes",
]

UPRIGHT_SOURCE_FIELDS = [
    "upright_company_name", "industry", "revenue_musd", "employee_count",
    "net_impact_ratio_percent", "rank_top_percent",
    "environment_cost_cents_per_dollar", "environment_benefit_cents_per_dollar",
    "ghg_emissions_cost_cents_per_dollar", "ghg_emissions_benefit_cents_per_dollar",
    "non_ghg_emissions_cost_cents_per_dollar",
    "society_cost_cents_per_dollar", "society_benefit_cents_per_dollar",
    "health_cost_cents_per_dollar", "health_benefit_cents_per_dollar",
    "knowledge_cost_cents_per_dollar", "knowledge_benefit_cents_per_dollar",
    "largest_cost", "largest_benefit", "upright_url",
]
# Prefixed with upright_ in the output so these are never confused with
# this pipeline's own tCO2e emissions columns -- see the module docstring.
UPRIGHT_FIELDS = [f"upright_{f}" if not f.startswith("upright_") else f
                   for f in UPRIGHT_SOURCE_FIELDS]


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


def load_climate_trace_by_ticker():
    by_ticker = {}
    with open(CLIMATE_TRACE_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            by_ticker[row["ticker"]] = {
                "climatetrace_power_asset_count": row["asset_count"],
                "climatetrace_power_subsectors": row["subsectors"],
                "climatetrace_power_countries": row["countries"],
                "climatetrace_power_avg_share_percent": row["avg_share_percent"],
            }
    return by_ticker


def load_tier2_by_ticker():
    if not os.path.isfile(TIER2_PATH):
        return {}
    by_ticker = {}
    with open(TIER2_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            by_ticker[row["ticker"]] = {field: row.get(field, "") for field in TIER2_FIELDS}
    return by_ticker


def load_upright_by_ticker():
    if not os.path.isfile(UPRIGHT_PATH):
        return {}
    by_ticker = {}
    with open(UPRIGHT_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            by_ticker[row["ticker"]] = {
                out_field: row.get(src_field, "")
                for src_field, out_field in zip(UPRIGHT_SOURCE_FIELDS, UPRIGHT_FIELDS)
            }
    return by_ticker


def main():
    sbti_by_ticker = load_sbti_by_ticker()
    print(f"SBTi matches available: {len(sbti_by_ticker)}")
    ct_by_ticker = load_climate_trace_by_ticker()
    print(f"Climate TRACE Power-ownership matches available: {len(ct_by_ticker)}")
    tier2_by_ticker = load_tier2_by_ticker()
    print(f"Tier 2 estimates available: {len(tier2_by_ticker)}")
    upright_by_ticker = load_upright_by_ticker()
    print(f"Upright Net Impact matches available: {len(upright_by_ticker)}")

    with open(MASTER_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        master_fields = reader.fieldnames
        rows = list(reader)
    print(f"Master rows: {len(rows)}")

    out_fields = (master_fields + ["sbti_matched"] + SBTI_FIELDS
                  + ["climatetrace_power_matched"] + CLIMATE_TRACE_FIELDS
                  + ["is_estimated"] + TIER2_FIELDS
                  + ["upright_matched"] + UPRIGHT_FIELDS)
    sbti_matched_count = 0
    ct_matched_count = 0
    tier2_used_count = 0
    upright_matched_count = 0
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        for row in rows:
            out = dict(row)

            sbti = sbti_by_ticker.get(row["ticker"])
            if sbti:
                sbti_matched_count += 1
                out["sbti_matched"] = "True"
                out.update(sbti)
            else:
                out["sbti_matched"] = "False"
                for field in SBTI_FIELDS:
                    out[field] = ""

            ct = ct_by_ticker.get(row["ticker"])
            if ct:
                ct_matched_count += 1
                out["climatetrace_power_matched"] = "True"
                out.update(ct)
            else:
                out["climatetrace_power_matched"] = "False"
                for field in CLIMATE_TRACE_FIELDS:
                    out[field] = ""

            # Tier 2 only ever fills in for a ticker with no real Level
            # number -- never overrides real disclosed data.
            has_real_scope = bool(row.get("scope1_tco2e") or row.get("scope2_location_tco2e")
                                   or row.get("scope2_market_tco2e"))
            tier2 = tier2_by_ticker.get(row["ticker"])
            if tier2 and not has_real_scope:
                tier2_used_count += 1
                out["is_estimated"] = "True"
                out.update(tier2)
            else:
                out["is_estimated"] = "False"
                for field in TIER2_FIELDS:
                    out[field] = ""

            upright = upright_by_ticker.get(row["ticker"])
            if upright:
                upright_matched_count += 1
                out["upright_matched"] = "True"
                out.update(upright)
            else:
                out["upright_matched"] = "False"
                for field in UPRIGHT_FIELDS:
                    out[field] = ""

            w.writerow(out)

    print(f"Rows with an SBTi match: {sbti_matched_count} / {len(rows)}")
    print(f"Rows with a Climate TRACE Power-ownership match: {ct_matched_count} / {len(rows)}")
    print(f"Rows using a Tier 2 estimate: {tier2_used_count} / {len(rows)}")
    print(f"Rows with an Upright Net Impact match: {upright_matched_count} / {len(rows)}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
