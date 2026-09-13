"""
Match the teammate's Upright Project "Net Impact Model" export
(data/upright_final_esg.json, 505 companies) to our S&P 500 ticker
roster, and pull out only the columns useful for merging into one
dataset -- not the full JSON (narrative explanations, scrape metadata,
duplicate screener_* fields, per-sub-metric detail).

This is a DIFFERENT dataset from anything else in this pipeline: Upright
measures modeled, monetized impact in "cents per dollar of revenue"
across four categories (Environment, Health, Knowledge, Society) --
NOT physical Scope 1/2 tCO2e tonnage. Do not treat its "GHG emissions"
cost figure as comparable to or a substitute for scope1_tco2e /
scope2_*_tco2e elsewhere in this repo. It's included here as its own,
separately-labelled columns for the teammate's pillar work, not folded
into the Level/Velocity/Integrity emissions columns.

Same conservative matching philosophy as sbti/match_sbti.py and
climate_trace/match_climate_trace.py: exact normalized company name
only, no fuzzy/substring matching. Upright's JSON has no ticker field,
only a company name (e.g. "WALMART", "ALPHABET") -- so an unmatched
name (e.g. dual-class listings like GOOG/GOOGL, whose constituent
"Security" name includes "(Class A)"/"(Class C)") is left out entirely
rather than guessed.

Usage: py match_upright.py
Reads:  ../../data/upright_final_esg.json, ../../sp500_constituents.csv
Writes: upright_matches.csv
"""
import csv
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PIPELINE_DIR = os.path.dirname(HERE)
REPO_DIR = os.path.dirname(PIPELINE_DIR)

UPRIGHT_PATH = os.path.join(REPO_DIR, "data", "upright_final_esg.json")
CONSTITUENTS_PATH = os.path.join(REPO_DIR, "sp500_constituents.csv")
OUT_PATH = os.path.join(HERE, "upright_matches.csv")

SUFFIXES = [
    "INCORPORATED", "CORPORATION", "COMPANY", "HOLDINGS", "HOLDING",
    "GROUP", "ENTERPRISES", "INTERNATIONAL", "INC", "CORP", "CO", "LLC",
    "LTD", "LP", "PLC", "LLP",
]

# Hand-verified aliases: Upright's informal/short company name -> our
# CURRENT S&P 500 constituent's official ticker (sp500_constituents.csv
# is the source of truth for the ticker/security name, per this repo's
# hard scope constraint). Each of these was checked one at a time against
# the live constituent list before being added here -- this is NOT fuzzy
# matching, it's a fixed, auditable list of confirmed identities (e.g.
# "Cisco Systems" and constituent security "Cisco" are the same company,
# CSCO). Deliberately excludes anything that ISN'T clearly still the same
# current entity -- see match_upright.py's module docstring / README for
# examples of names that look similar but are NOT aliased on purpose
# (Marathon Oil vs Marathon Petroleum, Oracle Corporation Japan vs Oracle
# Corporation, WestRock vs the post-merger Smurfit Westrock, Paramount
# Global vs the post-merger Paramount Skydance, dual-class tickers like
# Alphabet/Honeywell/Fox/News Corp where the Upright name doesn't specify
# which class/entity).
UPRIGHT_NAME_ALIASES = {
    "CISCO SYSTEMS": "CSCO",
    "JOHN DEERE": "DE",
    "ELI LILLY": "LLY",
    "CHUBB": "CB",
    "VERIZON COMMUNICATIONS": "VZ",
    "MARSH & MCLENNAN COMPANIES": "MRSH",
    "TRAVELERS": "TRV",
    "TAKE TWO INTERACTIVE SOFTWARE": "TTWO",
    "FACTSET RESEARCH SYSTEMS": "FDS",
    "F5 NETWORKS": "FFIV",
    "CAMDEN PROPERTY": "CPT",
    "BUNGE LIMITED": "BG",
    "FIFTH THIRD BANK": "FITB",
    "MCCORMICK": "MKC",
    "NORFOLK SOUTHERN RAILWAY": "NSC",
    "OLD DOMINION FREIGHT LINE": "ODFL",
    "SEMPRA ENERGY": "SRE",
    "ROBINHOOD": "HOOD",
    "PUBLIC SERVICE": "PEG",
    "VISTRA ENERGY": "VST",
    "AIR PRODUCTS & CHEMICALS": "APD",
    "ESSEX PROPERTY": "ESS",
    "FEDERAL REALTY INVESTMENT": "FRT",
    "CASEY'S GENERAL STORES": "CASY",
    "L3HARRIS TECHNOLOGIES": "LHX",
    "GLOBE LIFE AND ACCIDENT INSURANCE": "GL",
    "CARRIER": "CARR",
    "BROWN-FORMAN": "BF.B",  # constituent's Security field uses an
                              # en-dash ("Brown–Forman"), not a
                              # hyphen, which normalize() doesn't strip.
    "ARTHUR J. GALLAGHER": "AJG",
    "C. H. ROBINSON WORLDWIDE": "CHRW",
    "EVEREST RE": "EG",
    "HARTFORD FINANCIAL SERVICES": "HIG",
    "LYONDELLBASELL INDUSTRIES": "LYB",
    "ROYAL CARIBBEAN CRUISES": "RCL",
    "NORTHERN": "NTRS",
    "BANK OF NEW YORK MELLON": "BNY",
    "BOSTON PROPERTIES": "BXP",
    "AMERICAN WATER": "AWK",  # constituent security is "American Water
                               # Works" -- same company, missing "Works".
}


def normalize(name):
    if not name:
        return ""
    s = name.upper()
    s = re.sub(r"[.,'\"()]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("THE "):
        s = s[4:]
    words = s.split(" ")
    # A trailing "THE" comes from a constituent name like "Home Depot
    # (The)" -- the parens are stripped above, leaving a bare trailing
    # "THE" token. Pop it (and any suffix after it) same as any other
    # suffix, so "Home Depot (The)" normalizes the same as Upright's
    # plain "HOME DEPOT".
    while words and words[-1] in SUFFIXES + ["THE"]:
        words.pop()
    return " ".join(words)


def squish(key):
    """Drop spaces/hyphens for a secondary exact-match pass -- catches
    things like 'ExxonMobil' (constituent) vs 'EXXON MOBIL' (Upright),
    same company, just spaced differently. Still an exact match on a
    deterministic transform, not fuzzy/edit-distance matching."""
    return key.replace(" ", "").replace("-", "")


def load_constituents():
    """normalized name -> ticker (plus a squished-name fallback index),
    skipping any normalized name that maps to more than one distinct
    ticker (dual-class listings like GOOG/GOOGL don't collapse to the
    same normalized name today, but this guards against it if that ever
    changes). Also cross-checks every ticker in sp500_constituents.csv
    against a live current-S&P-500 set isn't needed here -- this file
    *is* the live list already, per the repo's hard scope constraint."""
    by_name = {}
    ambiguous = set()
    with open(CONSTITUENTS_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = normalize(row["Security"])
            if not key:
                continue
            if key in by_name and by_name[key] != row["Symbol"]:
                ambiguous.add(key)
            by_name[key] = row["Symbol"]
    for key in ambiguous:
        by_name.pop(key, None)

    squish_by_name = {}
    squish_ambiguous = set()
    for key, ticker in by_name.items():
        sk = squish(key)
        if sk in squish_by_name and squish_by_name[sk] != ticker:
            squish_ambiguous.add(sk)
        squish_by_name[sk] = ticker
    for sk in squish_ambiguous:
        squish_by_name.pop(sk, None)

    return by_name, squish_by_name


def to_number(s):
    """Strip a trailing unit label and thousands separators, e.g.
    '648,125.00 M$' -> 648125.0, '2,100,000 employees' -> 2100000.0,
    '-20%' -> -20.0. Returns '' (not None) if unparseable, so it writes
    cleanly to CSV without a stray 'None'."""
    if not s:
        return ""
    m = re.search(r"-?[\d,]+\.?\d*", s)
    if not m:
        return ""
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return ""


def metric_value(metrics, metric_name, field):
    for m in metrics:
        if m.get("metric") == metric_name:
            v = m.get(field)
            return to_number(v) if v else ""
    return ""


# Alias keys above are written in natural form (may still have periods,
# apostrophes, etc.) -- normalize them the same way constituent/Upright
# names are normalized, so e.g. "CASEY'S GENERAL STORES" (written with an
# apostrophe for readability) still matches normalize()'s apostrophe-
# stripped output "CASEYS GENERAL STORES".
NORMALIZED_ALIASES = {normalize(k): v for k, v in UPRIGHT_NAME_ALIASES.items()}


def resolve_ticker(name, by_name, squish_by_name):
    """Try, in order: exact normalized-name match, the hand-verified
    alias table, then a squished (space/hyphen-insensitive) exact match.
    Returns None if nothing matches -- left out entirely, never guessed."""
    key = normalize(name)
    if key in by_name:
        return by_name[key]
    if key in NORMALIZED_ALIASES:
        return NORMALIZED_ALIASES[key]
    sk = squish(key)
    if sk in squish_by_name:
        return squish_by_name[sk]
    return None


def main():
    by_name, squish_by_name = load_constituents()
    print(f"S&P 500 constituents (unambiguous normalized names): {len(by_name)}")

    with open(UPRIGHT_PATH, encoding="utf-8") as f:
        upright_rows = json.load(f)
    print(f"Upright companies in source JSON: {len(upright_rows)}")

    fields = [
        "ticker", "security", "upright_company_name", "industry",
        "revenue_musd", "employee_count",
        "net_impact_ratio_percent", "rank_top_percent",
        "environment_cost_cents_per_dollar", "environment_benefit_cents_per_dollar",
        "ghg_emissions_cost_cents_per_dollar", "ghg_emissions_benefit_cents_per_dollar",
        "non_ghg_emissions_cost_cents_per_dollar",
        "society_cost_cents_per_dollar", "society_benefit_cents_per_dollar",
        "health_cost_cents_per_dollar", "health_benefit_cents_per_dollar",
        "knowledge_cost_cents_per_dollar", "knowledge_benefit_cents_per_dollar",
        "largest_cost", "largest_benefit", "upright_url",
    ]

    matches = []
    unmatched = []
    for row in upright_rows:
        name = row.get("company", "")
        ticker = resolve_ticker(name, by_name, squish_by_name)
        if not ticker:
            unmatched.append(name)
            continue
        cat = row.get("category_totals", {})
        metrics = row.get("metrics", [])
        matches.append({
            "ticker": ticker,
            "security": name,
            "upright_company_name": name,
            "industry": row.get("industry", ""),
            "revenue_musd": to_number(row.get("revenue", "")),
            "employee_count": to_number(row.get("employee_count", "")),
            "net_impact_ratio_percent": to_number(row.get("net_impact_ratio", "")),
            "rank_top_percent": to_number(row.get("rank_top_percent", "")),
            "environment_cost_cents_per_dollar": to_number(cat.get("Environment", {}).get("cost", "")),
            "environment_benefit_cents_per_dollar": to_number(cat.get("Environment", {}).get("benefit", "")),
            "ghg_emissions_cost_cents_per_dollar": metric_value(metrics, "GHG emissions", "cost"),
            "ghg_emissions_benefit_cents_per_dollar": metric_value(metrics, "GHG emissions", "benefit"),
            "non_ghg_emissions_cost_cents_per_dollar": metric_value(metrics, "Non-GHG emissions", "cost"),
            "society_cost_cents_per_dollar": to_number(cat.get("Society", {}).get("cost", "")),
            "society_benefit_cents_per_dollar": to_number(cat.get("Society", {}).get("benefit", "")),
            "health_cost_cents_per_dollar": to_number(cat.get("Health", {}).get("cost", "")),
            "health_benefit_cents_per_dollar": to_number(cat.get("Health", {}).get("benefit", "")),
            "knowledge_cost_cents_per_dollar": to_number(cat.get("Knowledge", {}).get("cost", "")),
            "knowledge_benefit_cents_per_dollar": to_number(cat.get("Knowledge", {}).get("benefit", "")),
            "largest_cost": row.get("largest_cost", ""),
            "largest_benefit": row.get("largest_benefit", ""),
            "upright_url": row.get("upright_url", ""),
        })

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in matches:
            w.writerow(row)

    print(f"\nExact normalized-name matches: {len(matches)} / {len(upright_rows)}")
    print(f"Unmatched Upright company names ({len(unmatched)}):")
    for name in unmatched:
        print(f"  {name}")
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    main()
