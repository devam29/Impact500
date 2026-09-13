"""
Tier 2 sector-median emissions estimate, for tickers missing a real
Scope 1 and/or Scope 2 figure -- implements the "Median model" from
LSEG's published ESG carbon estimate methodology (LSEG ESG carbon data
and estimate models fact sheet), adapted to this project's smaller
universe (503 companies vs. LSEG's full global coverage).

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

**Scope 1 and Scope 2 are estimated INDEPENDENTLY, not as a combined
total split by an average share.** Earlier versions of this script only
ever estimated when a company had NEITHER scope disclosed, and derived
each scope from a single combined-total estimate divided by peer
scope1-share. That silently left 87 companies with a real disclosure for
ONE scope and a totally blank other scope (85 with real Scope 1/no
Scope 2, 2 with real Scope 2/no Scope 1) -- the has-both-scopes-blank
gate never triggered for them at all. Now each scope gets its own peer
pool (built only from peers with a REAL, non-estimated value for that
specific scope), its own median ratio, and its own independent
estimate -- so a company can have a real Scope 1 and an estimated
Scope 2 side by side, each clearly flagged.

**This produces an ESTIMATE, not a disclosure.** Every value this script
produces is tagged with its own `scope{1,2}_is_estimated=True` in the
final combined CSV (build_combined_dataset.py) specifically so it can be
styled/colored differently from real data wherever this is displayed --
never merge an estimated and a real figure without that distinction
remaining visible. This script also never overwrites a real number:
build_combined_dataset.py only ever applies a Tier 2 estimate to the
specific scope that has no real value, leaving a real scope on the same
row untouched.

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


def real_scope1(row):
    return to_float(row.get("scope1_tco2e"))


def real_scope2(row):
    """Prefer market-based Scope 2 (matches what a company is actually
    accountable for after its own clean-energy purchases) over
    location-based; fall back to location-based if market-based is
    missing. Returns None if neither is present."""
    s2 = to_float(row.get("scope2_market_tco2e"))
    if s2 is None:
        s2 = to_float(row.get("scope2_location_tco2e"))
    return s2


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


def build_peer_index(rows, gics, fin, real_value_fn):
    """Build (rev_ratio, emp_ratio) peer entries per (sub_industry,
    sector), using only companies with a REAL value for this specific
    scope (never another company's own estimate)."""
    by_sub_industry, by_sector, all_ratios = {}, {}, []
    peer_count = 0
    for row in rows:
        value = real_value_fn(row)
        if value is None:
            continue
        ticker = row["ticker"]
        g = gics.get(ticker)
        f_ = fin.get(ticker)
        if not g or not f_:
            continue
        rev, emp = f_["revenue_usd"], f_["employees"]
        entry = (
            value / rev if rev and rev > 0 else None,
            value / emp if emp and emp > 0 else None,
        )
        if entry[0] is None and entry[1] is None:
            continue
        by_sub_industry.setdefault(g["sub_industry"], []).append(entry)
        by_sector.setdefault(g["sector"], []).append(entry)
        all_ratios.append(entry)
        peer_count += 1
    return by_sub_industry, by_sector, all_ratios, peer_count


def best_group(sub_industry, sector, by_sub_industry, by_sector, all_ratios):
    for label, group_key, table in [
        ("sub_industry", sub_industry, by_sub_industry),
        ("sector", sector, by_sector),
    ]:
        entries = table.get(group_key, [])
        if len(entries) >= MIN_PEERS:
            return label, group_key, entries
    return "global", "All S&P 500", all_ratios


def estimate_for_ticker(ticker, gics, fin, by_sub_industry, by_sector, all_ratios, scope_label):
    g = gics.get(ticker)
    f_ = fin.get(ticker, {})
    rev, emp = f_.get("revenue_usd"), f_.get("employees")
    if not g or (not rev and not emp):
        return None

    level, group_key, entries = best_group(g["sub_industry"], g["sector"],
                                             by_sub_industry, by_sector, all_ratios)
    rev_ratios = [e[0] for e in entries if e[0] is not None]
    emp_ratios = [e[1] for e in entries if e[1] is not None]
    rev_med = median_ratio(rev_ratios)
    emp_med = median_ratio(emp_ratios)

    est_from_rev = rev_med * rev if (rev_med is not None and rev) else None
    est_from_emp = emp_med * emp if (emp_med is not None and emp) else None
    estimates = [e for e in (est_from_rev, est_from_emp) if e is not None]
    if not estimates:
        return None
    total_est = sum(estimates) / len(estimates)

    method_parts = []
    if est_from_rev is not None:
        method_parts.append("revenue")
    if est_from_emp is not None:
        method_parts.append("employees")
    method = "median_model_" + "+".join(method_parts)

    notes = (
        f"Tier 2 {scope_label} ESTIMATE (LSEG median-model style), NOT a "
        f"disclosure -- see pipeline/tier2_estimation/estimate_tier2.py. "
        f"Peer group: {level} = '{group_key}' ({len(entries)} Tier 1 peers "
        f"with a real {scope_label} value, floor={MIN_PEERS}). "
        + (f"Revenue-based: median peer {scope_label} tCO2e/$ revenue "
           f"({rev_med:.6g}) x this company's revenue (${rev:,.0f}) = "
           f"{est_from_rev:,.0f} tCO2e. " if est_from_rev is not None else "")
        + (f"Employee-based: median peer {scope_label} tCO2e/employee "
           f"({emp_med:.6g}) x this company's employee count "
           f"({emp:,.0f}) = {est_from_emp:,.0f} tCO2e. " if est_from_emp is not None else "")
        + f"Final estimate is the average of the available method(s): "
          f"{total_est:,.0f} tCO2e."
    )

    return {
        "tco2e": f"{total_est:.1f}",
        "method": method,
        "sector_used": f"{level}:{group_key}",
        "peer_count": len(entries),
        "notes": notes,
    }


def main():
    gics = load_gics()
    fin = load_financials()

    with open(MASTER_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    s1_sub, s1_sector, s1_all, s1_peers = build_peer_index(rows, gics, fin, real_scope1)
    s2_sub, s2_sector, s2_all, s2_peers = build_peer_index(rows, gics, fin, real_scope2)
    print(f"Tier 1 (real Scope 1) peers usable: {s1_peers}")
    print(f"Tier 1 (real Scope 2) peers usable: {s2_peers}")

    out_rows = []
    s1_estimated = 0
    s2_estimated = 0
    for row in rows:
        ticker = row["ticker"]
        out = {"ticker": ticker}

        if real_scope1(row) is None:
            est = estimate_for_ticker(ticker, gics, fin, s1_sub, s1_sector, s1_all, "Scope 1")
            if est:
                s1_estimated += 1
                out.update({
                    "tier2_scope1_tco2e": est["tco2e"],
                    "tier2_scope1_method": est["method"],
                    "tier2_scope1_sector_used": est["sector_used"],
                    "tier2_scope1_peer_count": est["peer_count"],
                    "tier2_scope1_notes": est["notes"],
                })

        if real_scope2(row) is None:
            est = estimate_for_ticker(ticker, gics, fin, s2_sub, s2_sector, s2_all, "Scope 2")
            if est:
                s2_estimated += 1
                out.update({
                    "tier2_scope2_tco2e": est["tco2e"],
                    "tier2_scope2_method": est["method"],
                    "tier2_scope2_sector_used": est["sector_used"],
                    "tier2_scope2_peer_count": est["peer_count"],
                    "tier2_scope2_notes": est["notes"],
                })

        if len(out) > 1:  # more than just "ticker" -- at least one scope estimated
            out_rows.append(out)

    fields = [
        "ticker",
        "tier2_scope1_tco2e", "tier2_scope1_method", "tier2_scope1_sector_used",
        "tier2_scope1_peer_count", "tier2_scope1_notes",
        "tier2_scope2_tco2e", "tier2_scope2_method", "tier2_scope2_sector_used",
        "tier2_scope2_peer_count", "tier2_scope2_notes",
    ]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in out_rows:
            w.writerow(row)

    print(f"Tickers with a Scope 1 estimate: {s1_estimated}")
    print(f"Tickers with a Scope 2 estimate: {s2_estimated}")
    print(f"Total rows written (at least one scope estimated): {len(out_rows)}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
