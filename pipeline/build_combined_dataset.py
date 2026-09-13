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
  the company's own revenue/employees. Scope 1 and Scope 2 are estimated
  INDEPENDENTLY: a ticker with a real Scope 1 but no real Scope 2 gets
  only a Scope 2 estimate, and vice versa -- tagged separately via
  `scope1_is_estimated`/`scope2_is_estimated`. Per
  tier2_estimation/estimate_tier2.py.)
- upright/upright_matches.csv, if it exists (a completely separate
  teammate dataset -- Upright Project's Net Impact Model. NOT a Scope 1/2
  tCO2e figure: it's a modeled, monetized cost/benefit score in "cents
  per dollar of revenue" across four categories (Environment, Health,
  Knowledge, Society). Included here purely because the teammate's job
  is now to merge their data with this one into a single file -- it is
  NOT folded into or compared against the Level/Velocity/Integrity
  emissions columns above, and every column is prefixed `upright_` so
  that's never ambiguous. Per upright/match_upright.py.)
- upright/upright_estimates.csv, if it exists (for tickers with no real
  Upright record at all -- a peer-median PROXY of what an Upright-style
  score might look like, per upright/estimate_upright_gaps.py. Tagged
  `upright_is_estimated=True`; never overwrites a real Upright match.
  This is OUR OWN modeled proxy, not Upright's actual methodology or
  output -- never present it as if Upright itself produced it.)

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
UPRIGHT_ESTIMATES_PATH = os.path.join(HERE, "upright", "upright_estimates.csv")
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

TIER2_SCOPE1_FIELDS = [
    "tier2_scope1_tco2e", "tier2_scope1_method", "tier2_scope1_sector_used",
    "tier2_scope1_peer_count", "tier2_scope1_notes",
]
TIER2_SCOPE2_FIELDS = [
    "tier2_scope2_tco2e", "tier2_scope2_method", "tier2_scope2_sector_used",
    "tier2_scope2_peer_count", "tier2_scope2_notes",
]
TIER2_FIELDS = TIER2_SCOPE1_FIELDS + TIER2_SCOPE2_FIELDS

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

# The subset of UPRIGHT_FIELDS a peer-median proxy estimate can actually
# fill (the cents-per-dollar-of-revenue metrics) -- excludes company_name/
# industry/largest_cost/largest_benefit/upright_url (nothing sensible to
# estimate) and revenue_musd/employee_count (filled from the company's
# own REAL financials_cache.csv data instead, handled separately below).
UPRIGHT_ESTIMATABLE_FIELDS = [
    f for f in UPRIGHT_FIELDS
    if f not in ("upright_company_name", "upright_industry", "upright_revenue_musd",
                 "upright_employee_count", "upright_largest_cost",
                 "upright_largest_benefit", "upright_url")
]

UPRIGHT_ESTIMATE_META_FIELDS = [
    "upright_is_estimated", "upright_peer_group_used", "upright_peer_count",
    "upright_estimate_notes",
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


def load_upright_estimates_by_ticker():
    if not os.path.isfile(UPRIGHT_ESTIMATES_PATH):
        return {}
    by_ticker = {}
    with open(UPRIGHT_ESTIMATES_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out = {}
            for f_est in UPRIGHT_ESTIMATABLE_FIELDS:
                src_field = f_est[len("upright_"):]  # estimate file uses unprefixed names
                out[f_est] = row.get(src_field, "")
            out["upright_peer_group_used"] = row.get("upright_peer_group_used", "")
            out["upright_peer_count"] = row.get("upright_peer_count", "")
            out["upright_estimate_notes"] = row.get("upright_estimate_notes", "")
            out["upright_revenue_musd"] = row.get("upright_revenue_musd", "")
            out["upright_employee_count"] = row.get("upright_employee_count", "")
            by_ticker[row["ticker"]] = out
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
    upright_estimates_by_ticker = load_upright_estimates_by_ticker()
    print(f"Upright Net Impact PROXY estimates available: {len(upright_estimates_by_ticker)}")

    with open(MASTER_PATH, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        master_fields = reader.fieldnames
        rows = list(reader)
    print(f"Master rows: {len(rows)}")

    out_fields = (master_fields + ["sbti_matched"] + SBTI_FIELDS
                  + ["climatetrace_power_matched"] + CLIMATE_TRACE_FIELDS
                  + ["is_estimated", "scope1_is_estimated", "scope2_is_estimated"] + TIER2_FIELDS
                  + ["upright_matched"] + UPRIGHT_FIELDS + UPRIGHT_ESTIMATE_META_FIELDS)
    sbti_matched_count = 0
    ct_matched_count = 0
    scope1_estimated_count = 0
    scope2_estimated_count = 0
    upright_matched_count = 0
    upright_estimated_count = 0
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

            # Scope 1 and Scope 2 are estimated INDEPENDENTLY -- a row can
            # have a real Scope 1 and an estimated Scope 2 side by side
            # (or vice versa). Tier 2 only ever fills the specific scope
            # that has no real value; it never overrides a real number.
            has_real_scope1 = bool(row.get("scope1_tco2e"))
            has_real_scope2 = bool(row.get("scope2_location_tco2e") or row.get("scope2_market_tco2e"))
            tier2 = tier2_by_ticker.get(row["ticker"], {})

            if not has_real_scope1 and tier2.get("tier2_scope1_tco2e"):
                scope1_estimated_count += 1
                out["scope1_is_estimated"] = "True"
                for field in TIER2_SCOPE1_FIELDS:
                    out[field] = tier2.get(field, "")
            else:
                out["scope1_is_estimated"] = "False"
                for field in TIER2_SCOPE1_FIELDS:
                    out[field] = ""

            if not has_real_scope2 and tier2.get("tier2_scope2_tco2e"):
                scope2_estimated_count += 1
                out["scope2_is_estimated"] = "True"
                for field in TIER2_SCOPE2_FIELDS:
                    out[field] = tier2.get(field, "")
            else:
                out["scope2_is_estimated"] = "False"
                for field in TIER2_SCOPE2_FIELDS:
                    out[field] = ""

            # Backward-compatible summary flag: "some estimated figure
            # appears on this row" -- kept for anything still keying off
            # the single old is_estimated column, but scope1_is_estimated/
            # scope2_is_estimated are the columns to actually use now.
            out["is_estimated"] = "True" if (out["scope1_is_estimated"] == "True"
                                              or out["scope2_is_estimated"] == "True") else "False"

            upright = upright_by_ticker.get(row["ticker"])
            if upright:
                upright_matched_count += 1
                out["upright_matched"] = "True"
                out.update(upright)
                out["upright_is_estimated"] = "False"
                for field in UPRIGHT_ESTIMATE_META_FIELDS:
                    if field != "upright_is_estimated":
                        out[field] = ""
            else:
                out["upright_matched"] = "False"
                for field in UPRIGHT_FIELDS:
                    out[field] = ""
                # No real match -- fall back to a peer-median PROXY
                # estimate if one exists (never the other way around).
                estimate = upright_estimates_by_ticker.get(row["ticker"])
                if estimate:
                    upright_estimated_count += 1
                    out["upright_is_estimated"] = "True"
                    out.update(estimate)
                else:
                    out["upright_is_estimated"] = "False"
                    for field in UPRIGHT_ESTIMATE_META_FIELDS:
                        if field != "upright_is_estimated":
                            out[field] = ""

            w.writerow(out)

    print(f"Rows with an SBTi match: {sbti_matched_count} / {len(rows)}")
    print(f"Rows with a Climate TRACE Power-ownership match: {ct_matched_count} / {len(rows)}")
    print(f"Rows with a Scope 1 Tier 2 estimate: {scope1_estimated_count} / {len(rows)}")
    print(f"Rows with a Scope 2 Tier 2 estimate: {scope2_estimated_count} / {len(rows)}")
    print(f"Rows with a real Upright Net Impact match: {upright_matched_count} / {len(rows)}")
    print(f"Rows using an Upright PROXY estimate: {upright_estimated_count} / {len(rows)}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
