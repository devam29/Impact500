"""
Build the single JSON file the website consumes: one record per CURRENT
S&P 500 ticker (our own sp500_constituents.csv roster -- see
docs/UPRIGHT_DATA_VERIFICATION.md for why that's the correct roster, not
Upright's), in the same general shape as the teammate's original
data/upright_final_esg.json, but:

1. Re-keyed to OUR 503-ticker roster instead of Upright's 505-row one --
   every record here corresponds to a ticker in sp500_constituents.csv.
   A ticker with a real Upright match keeps Upright's full original
   record (all 18 metrics, both text explanations, etc. -- read straight
   from data/upright_final_esg.json for maximum fidelity, not
   reconstructed from our flattened CSV). A ticker with no real Upright
   record gets our own peer-median PROXY estimate instead
   (upright/upright_estimates.csv) -- always tagged
   `upright.is_estimated=true` so it's never confused with Upright's own
   output.
2. Adds this pipeline's own environmental data per ticker: real/estimated
   Scope 1/2 CO2 (`co2` block), SBTi target status (`sbti` block), and
   Climate TRACE Power-sector ownership (`climate_trace` block) -- the
   same data as data/environmental_combined.csv, just reshaped as nested
   JSON instead of a flat CSV row.
3. Adds the final computed Environmental Sustainability score (`scores`
   block) from data/environmental_scores.csv -- Level, Velocity,
   Integrity, and the composite, plus each pillar's basis/estimation
   flags. See docs/SCORE_METHODOLOGY.md for how these are
   computed.

data/upright_final_esg.json itself is left untouched -- it's the
teammate's raw external source and stays as provenance. This script's
output is a NEW, separate file.

Usage: py build_website_json.py
Reads:  ../data/environmental_combined.csv, ../data/environmental_scores.csv,
        ../data/upright_final_esg.json, ../sp500_constituents.csv,
        upright/upright_estimates.csv
Writes: ../data/sp500_metrics.json
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "upright"))
import match_upright as mu  # noqa: E402

COMBINED_PATH = os.path.join(REPO_DIR, "data", "environmental_combined.csv")
SCORES_PATH = os.path.join(REPO_DIR, "data", "environmental_scores.csv")
UPRIGHT_RAW_PATH = os.path.join(REPO_DIR, "data", "upright_final_esg.json")
CONSTITUENTS_PATH = os.path.join(REPO_DIR, "sp500_constituents.csv")
UPRIGHT_ESTIMATES_PATH = os.path.join(HERE, "upright", "upright_estimates.csv")
OUT_PATH = os.path.join(REPO_DIR, "data", "sp500_metrics.json")

SCORES_FIELDS = [
    "level_score", "level_intensity_tco2e_per_usd",
    "velocity_score", "velocity_basis", "velocity_details",
    "integrity_score", "integrity_disclosure_quality",
    "integrity_cross_source_agreement", "integrity_basis",
    "environmental_composite_score",
]

CO2_FIELDS = [
    "data_source", "report_url", "scope1_base_year_end",
    "scope1_base_year_tco2e", "revenue_usd", "is_cdp_format", "notes",
]
SBTI_FIELDS = [
    "sbti_near_term_status", "sbti_near_term_target_classification",
    "sbti_near_term_target_year", "sbti_long_term_status",
    "sbti_long_term_target_year", "sbti_net_zero_status",
    "sbti_net_zero_year", "sbti_full_target_language", "sbti_date_updated",
]
CT_FIELDS = [
    "climatetrace_power_asset_count", "climatetrace_power_subsectors",
    "climatetrace_power_countries", "climatetrace_power_avg_share_percent",
]
UPRIGHT_ESTIMATE_MEDIAN_FIELDS = [
    "net_impact_ratio_percent", "rank_top_percent",
    "environment_cost_cents_per_dollar", "environment_benefit_cents_per_dollar",
    "ghg_emissions_cost_cents_per_dollar", "ghg_emissions_benefit_cents_per_dollar",
    "non_ghg_emissions_cost_cents_per_dollar",
    "society_cost_cents_per_dollar", "society_benefit_cents_per_dollar",
    "health_cost_cents_per_dollar", "health_benefit_cents_per_dollar",
    "knowledge_cost_cents_per_dollar", "knowledge_benefit_cents_per_dollar",
]


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_constituents():
    by_ticker = {}
    with open(CONSTITUENTS_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            by_ticker[row["Symbol"]] = row
    return by_ticker


def load_raw_upright_by_ticker():
    """ticker -> the teammate's ORIGINAL, full-fidelity JSON record
    (all 18 metrics, both text explanations, etc.) -- reused verbatim for
    multi-class tickers (Alphabet/Fox/News Corp), same resolver as
    upright/match_upright.py so this stays consistent with
    environmental_combined.csv's upright_matched flag."""
    by_name, squish_by_name = mu.load_constituents()
    with open(UPRIGHT_RAW_PATH, encoding="utf-8") as f:
        raw_rows = json.load(f)
    by_ticker = {}
    for row in raw_rows:
        tickers = mu.resolve_tickers(row.get("company", ""), by_name, squish_by_name)
        for ticker in tickers:
            by_ticker[ticker] = row
    return by_ticker


def load_upright_estimates_by_ticker():
    by_ticker = {}
    with open(UPRIGHT_ESTIMATES_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            by_ticker[row["ticker"]] = row
    return by_ticker


SCORES_NUMERIC_FIELDS = {
    "level_score", "level_intensity_tco2e_per_usd", "velocity_score",
    "integrity_score", "integrity_disclosure_quality",
    "integrity_cross_source_agreement", "environmental_composite_score",
}


def load_scores_by_ticker():
    by_ticker = {}
    with open(SCORES_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rec = {}
            for field in SCORES_FIELDS:
                val = row.get(field, "")
                rec[field] = to_float(val) if field in SCORES_NUMERIC_FIELDS else val
            by_ticker[row["ticker"]] = rec
    return by_ticker


def fmt_signed_pct(value):
    """Matches the original JSON's net_impact_ratio convention: signed,
    whole-number percent, e.g. '+37%' / '-6%'."""
    if value is None:
        return None
    return f"{value:+.0f}%"


def fmt_unsigned_pct(value):
    """Matches rank_top_percent's convention: no sign, whole number."""
    if value is None:
        return None
    return f"{value:.0f}%"


def fmt_signed_decimal(value):
    """Matches category_totals/metrics cost-benefit convention: signed,
    one decimal place, no unit suffix (unit is a separate field), e.g.
    '-15.2' / '+0.9'."""
    if value is None:
        return None
    return f"{value:+.1f}"


def build_upright_block(ticker, combined_row, raw_upright_by_ticker, estimates_by_ticker):
    if combined_row["upright_matched"] == "True":
        raw = raw_upright_by_ticker.get(ticker)
        block = dict(raw) if raw else {}
        block["is_estimated"] = False
        return block

    if combined_row["upright_is_estimated"] == "True":
        est = estimates_by_ticker.get(ticker, {})

        def v(field):
            val = to_float(est.get(field))
            return val

        category_totals = {
            "Environment": {
                "cost": fmt_signed_decimal(v("environment_cost_cents_per_dollar")),
                "benefit": fmt_signed_decimal(v("environment_benefit_cents_per_dollar")),
                "unit": "cents per dollar of revenue",
            },
            "Health": {
                "cost": fmt_signed_decimal(v("health_cost_cents_per_dollar")),
                "benefit": fmt_signed_decimal(v("health_benefit_cents_per_dollar")),
                "unit": "cents per dollar of revenue",
            },
            "Knowledge": {
                "cost": fmt_signed_decimal(v("knowledge_cost_cents_per_dollar")),
                "benefit": fmt_signed_decimal(v("knowledge_benefit_cents_per_dollar")),
                "unit": "cents per dollar of revenue",
            },
            "Society": {
                "cost": fmt_signed_decimal(v("society_cost_cents_per_dollar")),
                "benefit": fmt_signed_decimal(v("society_benefit_cents_per_dollar")),
                "unit": "cents per dollar of revenue",
            },
        }
        metrics = [
            {
                "category": "Environment", "metric": "GHG emissions",
                "cost": fmt_signed_decimal(v("ghg_emissions_cost_cents_per_dollar")),
                "benefit": fmt_signed_decimal(v("ghg_emissions_benefit_cents_per_dollar")),
                "unit": "cents per dollar of revenue",
            },
            {
                "category": "Environment", "metric": "Non-GHG emissions",
                "cost": fmt_signed_decimal(v("non_ghg_emissions_cost_cents_per_dollar")),
                "benefit": None,
                "unit": "cents per dollar of revenue",
            },
        ]
        return {
            "company": combined_row.get("security", ticker),
            "industry": None,  # Upright's own industry taxonomy -- not something we estimate
            "revenue_musd": to_float(est.get("upright_revenue_musd")),
            "employee_count": to_float(est.get("upright_employee_count")),
            "net_impact_ratio": fmt_signed_pct(v("net_impact_ratio_percent")),
            "rank_top_percent": fmt_unsigned_pct(v("rank_top_percent")),
            "category_totals": category_totals,
            "metrics": metrics,
            "largest_cost": None,
            "largest_benefit": None,
            "upright_url": None,
            "is_estimated": True,
            "estimate_method": "peer_median_proxy",
            "estimate_peer_group": est.get("upright_peer_group_used"),
            "estimate_peer_count": est.get("upright_peer_count"),
            "estimate_notes": est.get("upright_estimate_notes"),
        }

    return None  # should not happen -- 503/503 coverage as of this build


def main():
    constituents = load_constituents()
    raw_upright_by_ticker = load_raw_upright_by_ticker()
    estimates_by_ticker = load_upright_estimates_by_ticker()
    scores_by_ticker = load_scores_by_ticker()

    with open(COMBINED_PATH, encoding="utf-8", newline="") as f:
        combined_rows = list(csv.DictReader(f))
    print(f"Combined rows: {len(combined_rows)}")

    records = []
    real_upright = 0
    est_upright = 0
    for row in combined_rows:
        ticker = row["ticker"]
        cons = constituents.get(ticker, {})

        co2 = {field: row.get(field, "") for field in CO2_FIELDS}
        s1_est = row["scope1_is_estimated"] == "True"
        s2_est = row["scope2_is_estimated"] == "True"
        co2["is_estimated"] = s1_est or s2_est  # backward-compat summary flag
        co2["scope1"] = {
            "tco2e": to_float(row.get("scope1_tco2e")) if not s1_est
                     else to_float(row.get("tier2_scope1_tco2e")),
            "is_estimated": s1_est,
            "estimate": {
                "method": row.get("tier2_scope1_method", ""),
                "sector_used": row.get("tier2_scope1_sector_used", ""),
                "peer_count": row.get("tier2_scope1_peer_count", ""),
                "notes": row.get("tier2_scope1_notes", ""),
            } if s1_est else None,
        }
        co2["scope2"] = {
            "location_tco2e": to_float(row.get("scope2_location_tco2e")),
            "market_tco2e": to_float(row.get("scope2_market_tco2e")),
            "tco2e": (to_float(row.get("scope2_market_tco2e")) or to_float(row.get("scope2_location_tco2e")))
                     if not s2_est else to_float(row.get("tier2_scope2_tco2e")),
            "is_estimated": s2_est,
            "estimate": {
                "method": row.get("tier2_scope2_method", ""),
                "sector_used": row.get("tier2_scope2_sector_used", ""),
                "peer_count": row.get("tier2_scope2_peer_count", ""),
                "notes": row.get("tier2_scope2_notes", ""),
            } if s2_est else None,
        }

        sbti = {"matched": row["sbti_matched"] == "True"}
        if sbti["matched"]:
            sbti.update({f.replace("sbti_", ""): row.get(f, "") for f in SBTI_FIELDS})

        climate_trace = {"matched": row["climatetrace_power_matched"] == "True"}
        if climate_trace["matched"]:
            climate_trace.update({f.replace("climatetrace_power_", ""): row.get(f, "")
                                   for f in CT_FIELDS})

        upright_block = build_upright_block(ticker, row, raw_upright_by_ticker, estimates_by_ticker)
        if upright_block is not None:
            if upright_block.get("is_estimated"):
                est_upright += 1
            else:
                real_upright += 1

        records.append({
            "ticker": ticker,
            "security": row.get("security", ""),
            "gics_sector": cons.get("GICS Sector", ""),
            "gics_sub_industry": cons.get("GICS Sub-Industry", ""),
            "headquarters_location": cons.get("Headquarters Location", ""),
            "co2": co2,
            "sbti": sbti,
            "climate_trace": climate_trace,
            "upright": upright_block,
            "scores": scores_by_ticker.get(ticker),
        })

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"Records written: {len(records)}")
    print(f"  with real Upright data: {real_upright}")
    print(f"  with Upright PROXY estimate: {est_upright}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
