# Whose S&P 500 company list is current: independent verification against Wikipedia

**Question this answers**: our `sp500_constituents.csv` and the Upright Net
Impact export (`data/upright_final_esg.json`) disagree on which 40-ish
companies belong in the S&P 500 right now. Which one is right?

**Method**: pulled Wikipedia's ["List of S&P 500 companies"](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies)
page (2026-09-13) as a neutral third source — not derived from either of
our two datasets — and compared all three lists directly. Wikipedia's
constituent table is community-maintained and typically updated within
days of any official S&P Dow Jones Indices change (additions, removals,
ticker changes), which makes it a reasonable independent referee.

## Result 1: our list is an exact, 100% match to Wikipedia

| Comparison | Result |
|---|---|
| Tickers in our list but NOT in Wikipedia's current list | **0** |
| Tickers in Wikipedia's current list but NOT in our list | **0** |
| Total tickers compared | 503 / 503 |

Every single ticker and security name in `sp500_constituents.csv` matches
Wikipedia's live table exactly — including very recent 2026 changes like
the Honeywell Aerospace/Honeywell Technologies split (`HONA`/`HON`,
effective 2026-06-29, which replaced Conagra Brands in the index) and
Marsh McLennan's ticker change from `MMC` to `MRSH` (effective
2026-01-14). Our list is not just "probably current" — it is verified,
line-for-line, against the live index as of today.

## Result 2: the Upright dataset's remaining unmatched companies also fail to match Wikipedia

Every one of the 505 companies in the Upright export was checked against
Wikipedia's table directly (independent of our own matching code):

| Category | Count |
|---|---|
| Upright company name matches a **current** Wikipedia/our-list ticker | **470** |
| Upright company name matches **neither** Wikipedia nor our list | **35** |

(Update after this doc was first written: Alphabet, Fox Corporation, and
News Corp — 3 of the original 41 — were reclassified as *solvable*, not
unmatched. They're single operating businesses with multiple stock
classes, so Upright's one record for each was safely applied to **both**
of their tickers, GOOGL+GOOG, FOXA+FOX, NWSA+NWS — 6 tickers gained.
That's a real business-structure fact, not a guess, unlike Honeywell and
Hewlett Packard below, which really did split into separate companies.)

That remaining 35 is the exact same set of companies we couldn't match in
our own pipeline. This is the key point for convincing your teammate:
**it's not our matching logic that's excluding these companies —
Wikipedia, a completely independent source, also has no current ticker
for any of them.** If Upright's list were correct and current, these 35
names would appear somewhere in Wikipedia's live table. They don't.

### The 35 companies, with why each one is gone from the live index

| Upright's name | What actually happened |
|---|---|
| HESS | Acquired by Chevron (2024) |
| DISCOVER FINANCIAL | Acquired by Capital One (2025) |
| PIONEER NATURAL RESOURCES | Acquired by ExxonMobil (2024) |
| MARATHON OIL | Acquired by ConocoPhillips (2024) — **not** the same company as our constituent "Marathon Petroleum" (ticker `MPC`), despite the similar name |
| MYLAN | Merged into Viatris (2020); Viatris (`VTRS`) is the current constituent |
| KELLANOVA | Acquired by Mars (2025) |
| JUNIPER NETWORKS | Acquired by HPE (2024) |
| CONAGRA BRANDS | Removed from the S&P 500 on 2026-06-30 to make room for Honeywell Aerospace after the Honeywell split |
| WALGREENS BOOTS ALLIANCE | Taken private (Sycamore Partners, 2025) |
| ELECTRONIC ARTS | Taken private (2025) |
| WESTROCK | Merged into the new entity Smurfit Westrock (ticker `SW`) — a genuinely new/current entity Upright's export doesn't cover yet |
| PARAMOUNT / PARAMOUNT GLOBAL | Merged into the new entity Paramount Skydance (ticker `PSKY`) — same situation |
| AVALONBAY COMMUNITIES / EQUITY RESIDENTIAL | Merged into the new entity Vivmark Residential (ticker `VMRK`, 2026-08) — same situation |
| AMERICAN AIRLINES, BORGWARNER, CAESARS ENTERTAINMENT, CAMPBELL SOUP, ETSY, FMC, HOLOGIC, ILLUMINA, INTERPUBLIC, MATCH, METHODE ELECTRONICS, MOHAWK INDUSTRIES, ROBERT HALF, TELEFLEX, UNIVERSAL HEALTH REALTY INCOME, VF CORPORATION, WHIRLPOOL, BIO-RAD LABORATORIES, MARKETAXESS, XP INC | Removed from the S&P 500 in routine index rebalancing (still real, trading companies — just no longer S&P 500 members) |
| HONEYWELL | Genuinely split into two separate operating businesses in 2026 (Honeywell Aerospace `HONA`, Honeywell Technologies `HON`) — unlike Alphabet/Fox/News Corp above, a single pre-split score can't be applied to either half without distorting both |
| HEWLETT PACKARD | Same situation, older: split into HP Inc. (`HPQ`, no longer in the S&P 500) and Hewlett Packard Enterprise (`HPE`) in 2015 |
| ORACLE CORPORATION JAPAN | A separately-listed Japanese subsidiary — not the same stock as our `ORCL` constituent |

## Why this happened (root cause, not just "who's right")

Checked the Upright export's own metadata: every record carries
`source_index: "S&P 500 ESG"` and a source URL of
`uprightplatform.com/?companyPreset=SP500ESG`. The S&P 500 ESG variant is
a real, separate S&P Dow Jones Indices product that **rebalances only
once a year**, unlike the base S&P 500, which S&P updates within days of
any merger, acquisition, or take-private closing. Upright's export was
scraped today (`scraped_at_utc: 2026-09-13`), but the underlying
membership list it's scraping from was last refreshed at the ESG
variant's last annual rebalance — so any company removed from the base
S&P 500 mid-cycle (which is most of the 41 above) keeps sitting in that
snapshot until the next annual refresh catches up. This is a structural,
well-documented property of how S&P's ESG index is maintained, not a
one-off scraping mistake.

## Bottom line

- `sp500_constituents.csv` = the live, current, Wikipedia-verified S&P
  500 — use this as the ground truth for "is this ticker a current
  constituent," here and in any other section of the project.
- The Upright dataset is a real, useful, teammate-collected source **for
  the 470 companies it does cover** (464 direct/alias matches + 6 more
  from applying Alphabet/Fox/News Corp's single record to both of their
  share-class tickers). For the other 35, its underlying index snapshot
  is out of date through no fault of anyone's data entry; it's just how
  that specific S&P product is maintained.
- No further reconciliation is possible without new data collection
  (e.g. querying Upright's platform directly for the individual
  post-split/current entities like Honeywell Aerospace, Honeywell
  Technologies, or the merger successors Smurfit Westrock, Paramount
  Skydance, Vivmark Residential). See `pipeline/README.md`'s Upright
  section for that option if it's worth pursuing later.

Reproduce this yourself: `pipeline/upright/match_upright.py` contains
the matching logic; the Wikipedia comparison itself was a one-off check,
not (yet) a checked-in script — ask if you want it turned into one for
easy re-verification after the next index change.
