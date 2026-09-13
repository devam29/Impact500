"""
Compute the final Environmental Sustainability score: Level + Velocity +
Integrity, per CLAUDE.md's definition of done. Full methodology writeup
(why each formula, worked examples, sources) lives in
docs/SCORE_METHODOLOGY.md -- read that first if
you're trying to understand WHY, this file is the HOW.

Level: sector-relative emissions intensity (tCO2e / revenue), scored via
a percentile-anchored min-max (clip at the sector's 5th/95th percentile,
scale to 0-100, invert so lower intensity = higher score) -- MSCI's own
published carbon-intensity scoring approach, applied to our own data.

Velocity: tiered, because we mostly don't have a real emissions time
series (only 72/503 companies have a usable base-year figure):
  Tier A (real measured trend): observed annual reduction rate vs.
    SBTi's own published Absolute Contraction Approach requirement
    (4.2%/yr for 1.5C, 2.5%/yr for well-below-2C).
  Tier B (SBTi-matched, no usable trend): ordinal score from target
    classification x status.
  Tier C (no SBTi match at all): fixed low score -- silence on climate
    targets is informative, not neutral, but this is a value judgment,
    not a measured fact. Documented in the methodology doc.

Integrity: Disclosure Quality (source tier + completeness) plus, where
available, Cross-Source Agreement against Upright's INDEPENDENTLY
modeled GHG-cost data -- two separately-sourced environmental signals
compared against each other, standing in for the "self-report vs.
independent measurement" idea that originally needed Climate TRACE
Emissions data we never obtained.

Usage: py compute_environmental_scores.py
Reads:  ../../data/environmental_combined.csv, ../../sp500_constituents.csv,
        ../tier2_estimation/financials_cache.csv
Writes: ../../data/environmental_scores.csv
"""
import csv
import datetime
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(PIPELINE_DIR)

COMBINED_PATH = os.path.join(REPO_DIR, "data", "environmental_combined.csv")
CONSTITUENTS_PATH = os.path.join(REPO_DIR, "sp500_constituents.csv")
FINANCIALS_PATH = os.path.join(PIPELINE_DIR, "tier2_estimation", "financials_cache.csv")
OUT_PATH = os.path.join(REPO_DIR, "data", "environmental_scores.csv")

# SBTi's own published Absolute Contraction Approach minimum linear
# annual reduction rates (see docs/SCORE_METHODOLOGY.md for the
# source citation).
SBTI_RATE_1P5C = 0.042
SBTI_RATE_WB2C = 0.025

# CDP questionnaires report on the prior fiscal year; our collection ran
# through 2025-2026, so the most recent disclosed figures are
# predominantly FY2024. A fixed assumption, not extracted per-company --
# see the methodology doc's "Limitations" section.
ASSUMED_CURRENT_YEAR = 2024

# Tier B (target ambition only): additive points, same shape as CDP's own
# published Climate Change questionnaire scoring (points awarded per
# criterion actually met -- e.g. CDP awards +1 for an SBTi-validated
# target, +1 more for a longer target horizon, on top of a large base
# score) -- not CDP's literal point values (those are embedded across a
# ~100-page multi-section methodology we can't faithfully reproduce
# standalone), but the same "sum of real, named criteria" shape, which is
# more auditable than an arbitrary lookup table. See
# docs/SCORE_METHODOLOGY.md for the full reasoning.
TIER_B_VALIDATION_POINTS = {"Targets set": 2, "Committed": 1}  # is the target validated, or just declared?
TIER_B_AMBITION_POINTS = {"1.5": 2, "WELL-BELOW 2": 1}  # how strict is the target itself?
TIER_B_NET_ZERO_POINT = 1  # bonus: a validated or declared net-zero target on top of the near-term one
TIER_B_MAX_POINTS = (max(TIER_B_VALIDATION_POINTS.values()) + max(TIER_B_AMBITION_POINTS.values())
                      + TIER_B_NET_ZERO_POINT)  # 2 + 2 + 1 = 5

TIER_B_REMOVED = 10  # SBTi commitment REMOVED -- a real red flag, scored below Tier C's
                      # silence-is-worse-than-nothing baseline, not derived from points above
TIER_C_SCORE = 20  # no SBTi match at all -- documented value judgment

SOURCE_TIER_SCORE = {
    "cdp_pdf": 100,
    "sustainability_report": 70,
    "epa_ghgrp": 60,
}
ESTIMATED_SOURCE_SCORE = 20


def to_float(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def load_gics():
    gics = {}
    with open(CONSTITUENTS_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gics[row["Symbol"]] = row["GICS Sector"]
    return gics


def load_financials():
    fin = {}
    with open(FINANCIALS_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fin[row["ticker"]] = to_float(row.get("revenue_usd"))
    return fin


def combined_scope12(row):
    s1 = to_float(row["scope1_tco2e"]) if row["scope1_tco2e"] else to_float(row["tier2_scope1_tco2e"])
    s2 = to_float(row["scope2_market_tco2e"]) or to_float(row["scope2_location_tco2e"])
    if s2 is None:
        s2 = to_float(row["tier2_scope2_tco2e"]) or 0.0
    return s1, s2


def percentile(sorted_vals, pct):
    """Linear-interpolated percentile, pct in [0, 100]."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (pct / 100)
    f, c = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def percentile_anchored_score(value, sector_values):
    """MSCI-style: clip at the sector's 5th/95th percentile, min-max
    scale to 0-100, invert so LOWER intensity -> HIGHER score."""
    sorted_vals = sorted(sector_values)
    p5 = percentile(sorted_vals, 5)
    p95 = percentile(sorted_vals, 95)
    if p95 == p5:
        return 50.0  # degenerate sector (all identical) -- neutral score
    clipped = min(max(value, p5), p95)
    frac = (clipped - p5) / (p95 - p5)
    return round((1 - frac) * 100, 1)


def rank_percentile(value, all_values):
    """Plain percentile rank (0-100), used for Cross-Source Agreement --
    here we want relative POSITION, not magnitude, since we're comparing
    positions across two differently-scaled metrics (tCO2e/$ vs cents/$)."""
    sorted_vals = sorted(all_values)
    below = sum(1 for v in sorted_vals if v < value)
    return 100 * below / (len(sorted_vals) - 1) if len(sorted_vals) > 1 else 50.0


def compute_level_scores(rows, gics, fin):
    intensity_by_ticker = {}
    for row in rows:
        ticker = row["ticker"]
        rev = fin.get(ticker)
        s1, s2 = combined_scope12(row)
        if s1 is None or not rev or rev <= 0:
            continue
        intensity_by_ticker[ticker] = (s1 + s2) / rev

    by_sector = {}
    for ticker, intensity in intensity_by_ticker.items():
        sector = gics.get(ticker)
        if sector:
            by_sector.setdefault(sector, []).append(intensity)

    results = {}
    for ticker, intensity in intensity_by_ticker.items():
        sector = gics.get(ticker)
        sector_values = by_sector.get(sector, [intensity])
        score = percentile_anchored_score(intensity, sector_values)
        results[ticker] = {"level_score": score, "level_intensity_tco2e_per_usd": intensity}
    return results


def years_elapsed(base_year_end_str):
    try:
        base_year = datetime.datetime.strptime(base_year_end_str, "%m/%d/%Y").year
    except (ValueError, TypeError):
        return None
    return max(1, ASSUMED_CURRENT_YEAR - base_year)


def compute_velocity_for_row(row):
    base_val = to_float(row.get("scope1_base_year_tco2e"))
    base_year_end = row.get("scope1_base_year_end")
    current_s1 = to_float(row["scope1_tco2e"])  # Tier A only ever uses a REAL current value

    # sbti_matches.csv has a pre-existing encoding artifact (a mangled
    # degree sign, U+FFFD) inherited from the original SBTi Excel export
    # -- cosmetic fix for display here only, not touching the source data.
    classification = (row.get("sbti_near_term_target_classification", "") or "").replace("�", "°")
    status = row.get("sbti_near_term_status", "")

    if base_val and base_year_end and current_s1 is not None and base_val > 0:
        yrs = years_elapsed(base_year_end)
        if yrs:
            cumulative_reduction = (base_val - current_s1) / base_val
            observed_annual_rate = cumulative_reduction / yrs
            benchmark = SBTI_RATE_1P5C
            if classification == "Well-below 2°C":
                benchmark = SBTI_RATE_WB2C
            score = max(0.0, min(100.0, 100 * observed_annual_rate / benchmark))
            details = (
                f"Measured: {base_val:,.0f} -> {current_s1:,.0f} tCO2e over {yrs} yr(s) "
                f"({base_year_end} baseline, {ASSUMED_CURRENT_YEAR} assumed current year) = "
                f"{observed_annual_rate:.2%}/yr observed vs. {benchmark:.1%}/yr required "
                f"({'1.5C' if benchmark == SBTI_RATE_1P5C else 'well-below-2C'} pathway)."
            )
            return round(score, 1), "measured_trend", details

    if row["sbti_matched"] == "True":
        if status == "Commitment removed":
            return TIER_B_REMOVED, "target_ambition", "SBTi commitment removed -- negative signal."

        net_zero_status = row.get("sbti_net_zero_status", "")
        validation_points = TIER_B_VALIDATION_POINTS.get(status, 0)
        ambition_points = 0
        if "1.5" in classification:
            ambition_points = TIER_B_AMBITION_POINTS["1.5"]
        elif "WELL-BELOW 2" in classification.upper():
            ambition_points = TIER_B_AMBITION_POINTS["WELL-BELOW 2"]
        net_zero_points = TIER_B_NET_ZERO_POINT if net_zero_status in ("Targets set", "Committed") else 0

        points = validation_points + ambition_points + net_zero_points
        score = round(100 * points / TIER_B_MAX_POINTS, 1)
        details = (
            f"SBTi points: {validation_points}/2 for validation status ({status}) "
            f"+ {ambition_points}/2 for ambition ({classification or 'unclassified'}) "
            f"+ {net_zero_points}/1 for a net-zero target ({net_zero_status or 'none'}) "
            f"= {points}/{TIER_B_MAX_POINTS} -> {score}."
        )
        return score, "target_ambition", details

    return TIER_C_SCORE, "no_commitment", "No SBTi match -- no visible forward-looking climate target."


def compute_disclosure_quality(row):
    def source_score(is_estimated):
        if is_estimated == "True":
            return ESTIMATED_SOURCE_SCORE
        return SOURCE_TIER_SCORE.get(row.get("data_source"), ESTIMATED_SOURCE_SCORE)

    s1_score = source_score(row["scope1_is_estimated"])
    s2_score = source_score(row["scope2_is_estimated"])
    source_component = (s1_score + s2_score) / 2

    checks = [
        row["scope1_is_estimated"] == "False",
        row["scope2_is_estimated"] == "False",
        bool(row.get("scope1_base_year_tco2e")),
        bool(row.get("scope2_location_tco2e")) and bool(row.get("scope2_market_tco2e")),
    ]
    completeness = 100 * sum(checks) / len(checks)

    return round(0.6 * source_component + 0.4 * completeness, 1)


def compute_integrity_scores(rows, level_results):
    """Cross-Source Agreement needs a percentile rank in BOTH our own
    Level-intensity distribution and Upright's real GHG-cost
    distribution -- build both distributions first (only over companies
    with a REAL, non-estimated value in each), then score per-ticker."""
    ghg_cost_by_ticker = {}
    for row in rows:
        if row["upright_matched"] != "True":
            continue  # only a REAL Upright record counts as an independent check
        cost = to_float(row.get("upright_ghg_emissions_cost_cents_per_dollar"))
        if cost is not None:
            ghg_cost_by_ticker[row["ticker"]] = cost

    our_intensity_values = [v["level_intensity_tco2e_per_usd"] for v in level_results.values()]
    upright_cost_values = list(ghg_cost_by_ticker.values())  # more negative = worse

    results = {}
    for row in rows:
        ticker = row["ticker"]
        disclosure_quality = compute_disclosure_quality(row)

        if ticker in ghg_cost_by_ticker and ticker in level_results:
            our_pct = rank_percentile(level_results[ticker]["level_intensity_tco2e_per_usd"], our_intensity_values)
            # Flip sign so higher = worse for both distributions, consistent direction.
            upright_pct = rank_percentile(-ghg_cost_by_ticker[ticker], [-c for c in upright_cost_values])
            agreement = 100 - abs(our_pct - upright_pct)
            integrity = round(0.6 * disclosure_quality + 0.4 * agreement, 1)
            results[ticker] = {
                "integrity_score": integrity,
                "integrity_disclosure_quality": disclosure_quality,
                "integrity_cross_source_agreement": round(agreement, 1),
                "integrity_basis": "with_cross_validation",
            }
        else:
            results[ticker] = {
                "integrity_score": disclosure_quality,
                "integrity_disclosure_quality": disclosure_quality,
                "integrity_cross_source_agreement": "",
                "integrity_basis": "disclosure_quality_only",
            }
    return results


def spearman(xs, ys):
    def rank(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        for pos, idx in enumerate(order):
            ranks[idx] = pos
        return ranks
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mean_rx, mean_ry = sum(rx) / n, sum(ry) / n
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry)) / n
    sx = (sum((a - mean_rx) ** 2 for a in rx) / n) ** 0.5
    sy = (sum((b - mean_ry) ** 2 for b in ry) / n) ** 0.5
    return cov / (sx * sy) if sx and sy else 1.0


def main():
    gics = load_gics()
    fin = load_financials()
    with open(COMBINED_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"Master rows: {len(rows)}")

    level_results = compute_level_scores(rows, gics, fin)
    print(f"Level scores computed: {len(level_results)} / {len(rows)}")

    velocity_results = {}
    basis_counts = {"measured_trend": 0, "target_ambition": 0, "no_commitment": 0}
    for row in rows:
        score, basis, details = compute_velocity_for_row(row)
        velocity_results[row["ticker"]] = (score, basis, details)
        basis_counts[basis] += 1
    print(f"Velocity basis counts: {basis_counts}")

    integrity_results = compute_integrity_scores(rows, level_results)
    cross_val_count = sum(1 for v in integrity_results.values() if v["integrity_basis"] == "with_cross_validation")
    print(f"Integrity rows with Cross-Source Agreement: {cross_val_count} / {len(rows)}")

    out_rows = []
    for row in rows:
        ticker = row["ticker"]
        level = level_results.get(ticker)
        vscore, vbasis, vdetails = velocity_results[ticker]
        integ = integrity_results[ticker]

        level_score = level["level_score"] if level else ""
        composite_equal = round((level_score + vscore + integ["integrity_score"]) / 3, 1) if level else ""

        out_rows.append({
            "ticker": ticker,
            "security": row.get("security", ""),
            "gics_sector": gics.get(ticker, ""),
            "level_score": level_score,
            "level_intensity_tco2e_per_usd": level["level_intensity_tco2e_per_usd"] if level else "",
            "scope1_is_estimated": row["scope1_is_estimated"],
            "scope2_is_estimated": row["scope2_is_estimated"],
            "velocity_score": vscore,
            "velocity_basis": vbasis,
            "velocity_details": vdetails,
            "integrity_score": integ["integrity_score"],
            "integrity_disclosure_quality": integ["integrity_disclosure_quality"],
            "integrity_cross_source_agreement": integ["integrity_cross_source_agreement"],
            "integrity_basis": integ["integrity_basis"],
            "environmental_composite_score": composite_equal,
        })

    # Sorted best-to-worst by the final score, so the CSV reads as a
    # ranking out of the box -- ties (e.g. missing Level score) sort last.
    out_rows.sort(key=lambda r: r["environmental_composite_score"]
                  if r["environmental_composite_score"] != "" else -1, reverse=True)

    fields = [
        "ticker", "security", "gics_sector",
        "level_score", "level_intensity_tco2e_per_usd",
        "scope1_is_estimated", "scope2_is_estimated",
        "velocity_score", "velocity_basis", "velocity_details",
        "integrity_score", "integrity_disclosure_quality",
        "integrity_cross_source_agreement", "integrity_basis",
        "environmental_composite_score",
    ]
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in out_rows:
            w.writerow(row)
    print(f"Wrote {OUT_PATH}")

    # Weight-sensitivity check: does the RANKING change much under
    # different pillar weights? Only over rows with a Level score
    # (composite requires all three).
    scored = [r for r in out_rows if r["level_score"] != ""]
    equal = [r["environmental_composite_score"] for r in scored]
    level_heavy = [round(0.5 * r["level_score"] + 0.25 * velocity_results[r["ticker"]][0]
                          + 0.25 * integrity_results[r["ticker"]]["integrity_score"], 1) for r in scored]
    velocity_heavy = [round(0.25 * r["level_score"] + 0.5 * velocity_results[r["ticker"]][0]
                             + 0.25 * integrity_results[r["ticker"]]["integrity_score"], 1) for r in scored]
    print(f"Weight-sensitivity (Spearman rank correlation vs. equal-weight composite):")
    print(f"  Level-heavy (50/25/25):    {spearman(equal, level_heavy):.3f}")
    print(f"  Velocity-heavy (25/50/25): {spearman(equal, velocity_heavy):.3f}")


if __name__ == "__main__":
    main()
