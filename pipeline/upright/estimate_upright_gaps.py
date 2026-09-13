"""
Peer-median PROXY estimate of Upright-style Net Impact metrics for the
~33 current S&P 500 tickers Upright's export has no real record for (see
match_upright.py and docs/UPRIGHT_DATA_VERIFICATION.md for why those 33 aren't
covered -- mostly companies added to the S&P 500 since Upright's "S&P 500
ESG" snapshot was last refreshed, plus a few genuinely-split businesses
like Honeywell that can't reuse a pre-split score).

**This is NOT Upright's methodology and NOT real Upright data.** Upright
computes its Net Impact Model from detailed, company-specific
activity-based modeling -- what a company actually does, not just what
industry it's in. This script does something far cruder, same spirit as
tier2_estimation/estimate_tier2.py's CO2 median model: take the MEDIAN of
each cents-per-dollar-of-revenue metric among real Upright-covered peers
in the same GICS sector/sub-industry, and use that median as this
company's proxy value. Since Upright's metrics are already normalized
per dollar of revenue, no further scaling by the target's own size is
needed for those columns (unlike the CO2 Tier 2 model, which estimates an
absolute tonnage and does need that scaling step).

Every row this script produces is tagged `upright_is_estimated=True` in
the combined CSV, specifically so it is never displayed or cited as if
it were Upright's own output. Never overwrites a real Upright match.

Usage: py estimate_upright_gaps.py
Reads:  upright_matches.csv (Tier 1 peers), ../../sp500_constituents.csv,
        ../tier2_estimation/financials_cache.csv (real revenue/employees
        -- used as-is, not estimated, since we already have it)
Writes: upright_estimates.csv
"""
import csv
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(PIPELINE_DIR)

UPRIGHT_MATCHES_PATH = os.path.join(HERE, "upright_matches.csv")
CONSTITUENTS_PATH = os.path.join(REPO_DIR, "sp500_constituents.csv")
FINANCIALS_PATH = os.path.join(PIPELINE_DIR, "tier2_estimation", "financials_cache.csv")
OUT_PATH = os.path.join(HERE, "upright_estimates.csv")

MIN_PEERS = 5  # same floor as tier2_estimation/estimate_tier2.py, same
               # reasoning: 503 companies across ~130 GICS sub-industries
               # rarely clears a 10-peer floor at the narrow level.

# The cents-per-dollar-of-revenue metrics we take a peer median of.
# Deliberately excludes revenue_musd/employee_count (we have REAL data
# for those already, from financials_cache.csv -- no need to guess) and
# largest_cost/largest_benefit/upright_url (free text/links, nothing
# sensible to estimate).
MEDIAN_FIELDS = [
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


def load_gics():
    gics = {}
    with open(CONSTITUENTS_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gics[row["Symbol"]] = {
                "sector": row["GICS Sector"],
                "sub_industry": row["GICS Sub-Industry"],
            }
    return gics


def load_financials():
    fin = {}
    with open(FINANCIALS_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fin[row["ticker"]] = {
                "revenue_usd": to_float(row.get("revenue_usd")),
                "employees": to_float(row.get("employees")),
            }
    return fin


def load_real_upright():
    with open(UPRIGHT_MATCHES_PATH, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    gics = load_gics()
    fin = load_financials()
    real_rows = load_real_upright()
    real_tickers = {r["ticker"] for r in real_rows}
    all_tickers = list(gics.keys())
    missing = [t for t in all_tickers if t not in real_tickers]
    print(f"Real Upright matches (Tier 1 peers): {len(real_tickers)}")
    print(f"Tickers with no real Upright data: {len(missing)}")

    # Peer group -> list of {field: value} dicts, for every real row with
    # a known GICS classification.
    by_sub_industry = {}
    by_sector = {}
    all_peer_values = []
    for row in real_rows:
        g = gics.get(row["ticker"])
        if not g:
            continue
        values = {f: to_float(row.get(f)) for f in MEDIAN_FIELDS}
        by_sub_industry.setdefault(g["sub_industry"], []).append(values)
        by_sector.setdefault(g["sector"], []).append(values)
        all_peer_values.append(values)

    def best_group(sub_industry, sector):
        for label, group_key, table in [
            ("sub_industry", sub_industry, by_sub_industry),
            ("sector", sector, by_sector),
        ]:
            entries = table.get(group_key, [])
            if len(entries) >= MIN_PEERS:
                return label, group_key, entries
        return "global", "All S&P 500", all_peer_values

    fields = ["ticker", "upright_is_estimated", "upright_peer_group_used",
              "upright_peer_count", "upright_revenue_musd", "upright_employee_count"] \
        + MEDIAN_FIELDS + ["upright_estimate_notes"]

    out_rows = []
    for ticker in missing:
        g = gics.get(ticker)
        level, group_key, entries = best_group(g["sub_industry"], g["sector"])

        medians = {}
        for f in MEDIAN_FIELDS:
            vals = [e[f] for e in entries if e[f] is not None]
            medians[f] = statistics.median(vals) if vals else ""

        f_ = fin.get(ticker, {})
        revenue_usd = f_.get("revenue_usd")
        employees = f_.get("employees")

        notes = (
            f"PROXY ESTIMATE, not real Upright data -- see "
            f"pipeline/upright/estimate_upright_gaps.py. Peer group: "
            f"{level} = '{group_key}' ({len(entries)} real Upright-covered "
            f"peers, floor={MIN_PEERS}). Each cents-per-dollar-of-revenue "
            f"figure is the MEDIAN of that peer group's real Upright "
            f"values for the same metric -- a crude industry-average "
            f"proxy, not Upright's own company-specific modeling. "
            f"Revenue/employee figures are this company's own real data "
            f"(from yfinance), not estimated."
        )

        row = {
            "ticker": ticker,
            "upright_is_estimated": "True",
            "upright_peer_group_used": f"{level}:{group_key}",
            "upright_peer_count": len(entries),
            "upright_revenue_musd": f"{revenue_usd / 1e6:.1f}" if revenue_usd else "",
            "upright_employee_count": f"{employees:.0f}" if employees else "",
            "upright_estimate_notes": notes,
        }
        row.update(medians)
        out_rows.append(row)

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in out_rows:
            w.writerow(row)

    print(f"Proxy estimates produced: {len(out_rows)}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
