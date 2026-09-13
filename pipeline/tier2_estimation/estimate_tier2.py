"""
Tier 2 sector-median emissions estimate, for tickers with no real
disclosed Scope 1/2 figure (data_source=none in the master file) --
implements the "Median model" from LSEG's published ESG carbon
estimate methodology (LSEG ESG carbon data and estimate models fact
sheet), adapted to this project's smaller universe (503 companies vs.
LSEG's full global coverage).

LSEG's median model (the fallback of last resort in their own four-step
cascade -- reported, then a company's-own-history CO2 model, then an
energy model, then this):
  1. Compute CO2/employees and CO2/revenue ratios for all real-data
     peer companies in the same industry classification.
  2. Take the MEDIAN of those ratios, multiplied by the target
     company's own employees (and separately, its own revenue).
  3. Average the two results (or use just one, if only one input is
     available).
  4. If fewer than ~10 peers exist at the narrowest classification
     level, widen to a broader one.

This implementation follows that same shape, with GICS Sector /
Sub-Industry (from sp500_constituents.csv) standing in for LSEG's TRBC
codes, and a lower peer-count floor (5, not 10) since our total universe
is 503 companies, not LSEG's full global coverage -- a strict 10-company
floor at the Sub-Industry level would almost never be met here.

**This produces an ESTIMATE, not a disclosure.** Every row this script
touches is tagged `is_estimated=True` in the final combined CSV
(build_combined_dataset.py) specifically so it can be styled/colored
differently from real data wherever this is displayed -- never merge an
estimated and a real figure without that distinction remaining visible.
This script also never overwrites a real number: build_combined_dataset.py
only applies a Tier 2 estimate to a ticker with no real Scope 1/2 value
at all.

Usage: py estimate_tier2.py
Reads:  ../../data/environmental_emissions_master.csv,
        ../../sp500_constituents.csv, financials_cache.csv
Writes: tier2_estimates.csv
"""
import csv
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(PIPELINE_DIR)

MASTER_PATH = os.path.join(REPO_DIR, "data", "environmental_emissions_master.csv")
CONSTITUENTS_PATH = os.path.join(REPO_DIR, "sp500_constituents.csv")
FINANCIALS_PATH = os.path.join(HERE, "financials_cache.csv")
OUT_PATH = os.path.join(HERE, "tier2_estimates.csv")

MIN_PEERS = 5  # LSEG uses 10 against their full global coverage; we relax
               # this since our whole universe is 503 companies, not
               # LSEG's full coverage -- a strict 10-peer floor at the
               # Sub-Industry level would almost never be met here.


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def combined_scope12(row):
    """Prefer market-based Scope 2 (matches what a company is actually
    accountable for after its own clean-energy purchases) over
    location-based; fall back to location-based if market-based is
    missing. Returns (total, scope1, scope2_used) or None if no Scope 1
    figure is present at all -- a Scope-2-only row isn't a usable peer
    for this ratio, since Scope 1 is definitionally required to be a
    'Scope 1+2' data point."""
    s1 = to_float(row.get("scope1_tco2e"))
    if s1 is None:
        return None
    s2 = to_float(row.get("scope2_market_tco2e"))
    if s2 is None:
        s2 = to_float(row.get("scope2_location_tco2e"))
    if s2 is None:
        s2 = 0.0
    return s1 + s2, s1, s2


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


def median_ratio(peer_ratios):
    if not peer_ratios:
        return None
    return statistics.median(peer_ratios)


def main():
    gics = load_gics()
    fin = load_financials()

    with open(MASTER_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    # Build peer emissions-intensity ratios per (level, group) for every
    # real-data (Tier 1) company: revenue-based and employee-based, plus
    # the peer's own scope1-share of its total (for splitting the
    # estimate back into scope1/scope2 later).
    by_sub_industry = {}   # sub_industry -> list of (rev_ratio, emp_ratio, scope1_share)
    by_sector = {}
    all_ratios = []

    tier1_rows = []
    for row in rows:
        cs = combined_scope12(row)
        if cs is None:
            continue
        total, s1, s2 = cs
        ticker = row["ticker"]
        g = gics.get(ticker)
        f_ = fin.get(ticker)
        if not g or not f_:
            continue
        rev = f_["revenue_usd"]
        emp = f_["employees"]
        rev_ratio = total / rev if rev and rev > 0 else None
        emp_ratio = total / emp if emp and emp > 0 else None
        scope1_share = s1 / total if total > 0 else None
        entry = (rev_ratio, emp_ratio, scope1_share)
        by_sub_industry.setdefault(g["sub_industry"], []).append(entry)
        by_sector.setdefault(g["sector"], []).append(entry)
        all_ratios.append(entry)
        tier1_rows.append(ticker)

    print(f"Tier 1 (real data) companies usable as peers: {len(tier1_rows)}")

    def best_group(sub_industry, sector):
        """Cascade: Sub-Industry -> Sector -> global, same shape as
        LSEG's TRBC-level widening, stopping at the first level with
        enough peers."""
        for label, group_key, table in [
            ("sub_industry", sub_industry, by_sub_industry),
            ("sector", sector, by_sector),
        ]:
            entries = table.get(group_key, [])
            if len(entries) >= MIN_PEERS:
                return label, group_key, entries
        return "global", "All S&P 500", all_ratios

    out_rows = []
    for row in rows:
        ticker = row["ticker"]
        # Estimate for ANY ticker with no real Scope 1/2 number -- not
        # just data_source=none. A row with data_source=cdp_pdf/
        # sustainability_report but notes=no_fields_extracted (a report
        # was found, the parser just couldn't pull a number from it) is
        # functionally the same gap from a "do we have a usable figure"
        # standpoint, and there turn out to be 137 of these alongside
        # the 124 genuine data_source=none rows -- skipping them would
        # silently leave over half the "no real number" gap uncovered.
        if combined_scope12(row) is not None:
            continue  # has a real number already -- never override it
        g = gics.get(ticker)
        f_ = fin.get(ticker)
        if not g:
            continue  # can't classify into a peer group at all
        rev = f_["revenue_usd"] if f_ else None
        emp = f_["employees"] if f_ else None
        if not rev and not emp:
            continue  # nothing to scale a ratio by

        level, group_key, entries = best_group(g["sub_industry"], g["sector"])
        rev_ratios = [e[0] for e in entries if e[0] is not None]
        emp_ratios = [e[1] for e in entries if e[1] is not None]
        shares = [e[2] for e in entries if e[2] is not None]

        rev_med = median_ratio(rev_ratios)
        emp_med = median_ratio(emp_ratios)
        share_med = median_ratio(shares) or 0.5

        est_from_rev = rev_med * rev if (rev_med is not None and rev) else None
        est_from_emp = emp_med * emp if (emp_med is not None and emp) else None
        estimates = [e for e in (est_from_rev, est_from_emp) if e is not None]
        if not estimates:
            continue
        total_est = sum(estimates) / len(estimates)

        method_parts = []
        if est_from_rev is not None:
            method_parts.append("revenue")
        if est_from_emp is not None:
            method_parts.append("employees")
        method = "median_model_" + "+".join(method_parts)

        notes = (
            f"Tier 2 ESTIMATE (LSEG median-model style), NOT a disclosure -- "
            f"see pipeline/tier2_estimation/estimate_tier2.py. Peer group: "
            f"{level} = '{group_key}' ({len(entries)} Tier 1 peers, "
            f"floor={MIN_PEERS}). "
            + (f"Revenue-based: median peer tCO2e/$ revenue ({rev_med:.6g}) "
               f"x this company's revenue (${rev:,.0f}) = {est_from_rev:,.0f} tCO2e. "
               if est_from_rev is not None else "")
            + (f"Employee-based: median peer tCO2e/employee ({emp_med:.6g}) "
               f"x this company's employee count ({emp:,.0f}) = {est_from_emp:,.0f} tCO2e. "
               if est_from_emp is not None else "")
            + f"Final estimate is the average of the available method(s): {total_est:,.0f} tCO2e. "
            + f"Split into scope1/scope2 using the peer group's median "
              f"scope1-share ({share_med:.2%}) -- this split is a secondary "
              f"approximation layered on top of the primary total estimate, "
              f"not independently estimated."
        )

        out_rows.append({
            "ticker": ticker,
            "tier2_scope1_tco2e": f"{total_est * share_med:.1f}",
            "tier2_scope2_tco2e": f"{total_est * (1 - share_med):.1f}",
            "tier2_method": method,
            "tier2_sector_used": f"{level}:{group_key}",
            "tier2_peer_count": len(entries),
            "tier2_notes": notes,
        })

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "tier2_scope1_tco2e", "tier2_scope2_tco2e",
                                           "tier2_method", "tier2_sector_used",
                                           "tier2_peer_count", "tier2_notes"])
        w.writeheader()
        for row in out_rows:
            w.writerow(row)

    print(f"Tier 2 estimates produced: {len(out_rows)}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
