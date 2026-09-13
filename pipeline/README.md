# Environmental data pipeline — technical reference

This is the **Environmental Sustainability** pillar of the S&P 500
sustainability score: Level (current emissions burden) + Velocity
(decarbonization pace) + Integrity (data trustworthiness). See
`docs/SCORE_METHODOLOGY.md` for how the three pillars are combined into
a final score, and `docs/DATA_DICTIONARY.md` for every column in every
output file. This file explains how the underlying data was collected
and how each script fits together.

## Design principle: never fabricate a number

Every script in this pipeline leaves a field blank rather than guess
when confidence is low, and every estimate is explicitly flagged
(`*_is_estimated`, `*_basis` columns) rather than presented as
equivalent to a real disclosure. This rule shows up everywhere below —
it's the one property to preserve if you extend any part of this.

## Pipeline stages, in order

### 1. Report extraction — `pipeline/pdf_extraction/`

Collects each company's Scope 1/2 GHG emissions and revenue straight
from their own CDP climate disclosure or general sustainability report.
Split into two halves for cost reasons: finding a company's report PDF
needs a web search (expensive if done at scale inside an LLM context),
extracting numbers from a found PDF does not.

- `extract_emissions.py` — the parser. Handles three CDP export layouts
  plus a generic fallback for non-CDP reports (see "What the parser
  handles" below).
- `process_company.py` — downloads one PDF, calls `extract_emissions.py`,
  appends one row to a batch CSV. Never crashes without writing a row —
  a failure gets a `notes` value instead (`download_error: ...`,
  `not_a_pdf`, `no_fields_extracted`) so gaps stay visible.
- `mark_not_found.py` — appends a `data_source=none,
  notes=no_public_report_found` row, for a company that was actually
  searched and came up empty (never call this for a company that wasn't
  searched — see "Never claim searched" below).
- `merge_batches.py` — rebuilds `data/environmental_emissions_master.csv`
  from the seed file (`data/environmental_emissions_raw.csv`, a handful
  of hand-verified companies) plus every `data/batches/batch_*.csv`,
  deduped by ticker. Re-run any time a batch file changes.
- `rescan_all_cached.py` — regression-checks the current parser against
  every PDF already cached in `pdf_extraction/pdfs/`, zero new network
  calls. Run after any parser change before trusting it at scale.
- `reprocess_cached.py` — re-runs the current extractor against one
  batch CSV's rows, using cached PDFs only.
- `remaining_tickers/remaining_batch_NN.txt` — per-batch tracking of
  which companies still needed a search attempt during collection
  (`TICKER,Company Name` per line). Collection is complete, so these are
  now empty/historical, kept for provenance. Batch `02` does not exist
  and should not be recreated — an early off-by-one in batch generation
  made it an exact duplicate of batch 01's list, which already covers it.

**Search strategy used**: `"{Company Name}" CDP climate change response
OR CDP corporate questionnaire PDF {year}` first; if nothing, a fallback
search for a data-table-style report (`"ESG data summary" OR "GRI index"
OR "SASB index"`) rather than a generic "sustainability report" search —
tested at 94% hit rate for CDP PDFs vs. 7% for narrative-only
sustainability reports found via a generic query, since large companies
that disclose real numbers typically publish a separate data-table PDF
alongside their glossy narrative one.

### What the parser handles

CDP's own PDF export format changed across cycles and varies
company-to-company. `extract_emissions.py` detects and handles, in
priority order:

1. **New format, `.1`-suffixed**: question markers `(7.6.1)` = Scope 1,
   `(7.7.1)`/`(7.7.2)` = Scope 2 location/market, `(1.4.1)` = revenue,
   `(7.5.1)`/`(7.5.2)` = base year.
2. **New format, "compact"** (no `.1` suffix): question markers `(7.6)` /
   `(7.7)` only, location/market values as a consecutive pair under a
   shared "Reporting year" row. Scope 1/2 blocks also carry prior-year
   comparison data further down whose value can exceed the current
   year's — the parser takes the first numeric line after "Reporting
   year", not the block maximum, specifically to avoid grabbing the
   wrong year (a real bug caught on a company whose past-year figure
   exceeded its current-year one).
3. **Old format, pre-2024**: lettered section numbers (`(C6.1)` = Scope
   1, `(C6.3)` = Scope 2) instead of decimals.
4. **Generic fallback** for non-CDP reports: a labelled multi-year table
   (takes the most recent column) or a single "NUMBER metric tons CO2e"
   phrase, including a `(MTCO2e)`-abbreviated label variant.

**Known, deliberately-unhandled case**: a company that publishes a
self-authored "CDP response" summary (not the official CDP-generated
export) using inline prose numbering instead of parenthesized question
markers doesn't match any of the above. Not worth chasing with regex —
would need either an LLM-read-the-summary approach or manual entry.

**Also known**: CDP's real exports state upfront that unanswered
questions are excluded from the PDF entirely — a missing field isn't
always a parser bug. Base-year fields are only reported when a Scope 1
headline figure was also found, since the position-based logic that
finds them becomes unreliable otherwise.

### Manual entries (non-generalizable table layouts, each cross-verified)

A handful of companies used one-off table layouts not worth generalizing
into the parser. Each was entered by hand and cross-checked against the
source document's own internal totals before being trusted — the
verification arithmetic is kept here and in each row's `notes` column:

- **Nike (NKE)**: emissions broken out by facility type rather than a
  single Scope 1/2 row. Verified across three independent tables in the
  same document, all agreeing exactly: Scope 1 = 57,390, Scope 2
  location-based = 211,322, market-based = 12,120 tCO2e.
- **Warner Bros. Discovery (WBD)**: footnote digits glued directly onto
  row labels (e.g. "Scope 11" = "Scope 1" + footnote 1). Verified: Scope
  1 (80,650) + Scope 2 location (112,921) = 193,571 matches the
  document's own stated location-based total; 80,650 + market (116,285)
  = 196,935 matches the stated market-based total.
- **Salesforce (CRM)**: figures in thousands, column header trailing the
  data. Verified: 6 + 293 + 1,155 = 1,454 (thousand tCO2e) matches the
  document's own "Total absolute emissions" row.
- **J.M. Smucker (SJM)**: an assurance-letter schedule. Verified:
  165,414 + 176,567 = 341,981 and 165,414 + 629 = 166,043, both matching
  the document's stated LBM/MBM totals.
- **Teledyne (TDY)**: a decoy "Total Emissions from Perfluorinated
  Compounds (PFCs)" row shares its label prefix with the real Scope 1
  total. Verified: 58,970 + 51,971 = 110,941 matches the stated Scope
  1+2 total.
- **J.B. Hunt, JPMorgan Chase**: current-year-first tables / mixed
  layouts within one document; JPMorgan verified via 100,024 + 6,806 =
  106,830 matching the document's own combined total.
- **Vivmark Residential (VMRK)**: AvalonBay Communities and Equity
  Residential merged into VMRK in 2026; no combined-entity filing exists
  yet, so the row is AvalonBay's own pre-merger CDP response only —
  roughly half the combined company's real footprint. Flagged in the
  row's `notes`.

### 2. Supplemental sources — EPA GHGRP, SBTi, Climate TRACE

Three independent, zero-search-cost sources, each matched to the ticker
roster by **exact normalized company name only** (no fuzzy matching) —
a false-positive company match is worse than a missed one.

**`epa_ghgrp/`** (Scope 1 only, real government data). EPA's Greenhouse
Gas Reporting Program (facilities emitting ≥25,000 tCO2e/yr must
report; free bulk download) matched to tickers by parent-company name.
`epa_ghgrp_matches.csv` is the lookup table; `match_epa_ghgrp.py` builds
it, `patch_epa_matches.py` backfills any batch-file row that has a
matched note but a blank value. GHGRP is a registry of direct emitters,
not a corporate disclosure framework — it has no Scope 2 concept, so
`scope2_*` is always blank on an `epa_ghgrp` row (never read that blank
as "zero").

**`sbti/`** (Velocity's real input). Science Based Targets initiative's
official target dashboard (`sbti_companies.xlsx`, free, updated weekly)
matched by exact normalized name. `match_sbti.py` builds
`sbti_matches.csv` — near-term/long-term/net-zero target status,
target years, and the target's own free-text description (usually
states the exact % reduction and base year). `Commitment removed` is a
real, meaningful status (a company set a target, then withdrew it) —
treated as a negative signal in scoring, not a missing-data placeholder.

**`climate_trace/`** (Integrity's independent-observation input). A real
Climate TRACE "Ownership" data package download (Power sector,
worldwide, free, no login) matched the same way via
`match_climate_trace.py`. This is the only source in this pipeline that
isn't self-reported — Climate TRACE estimates emissions from
satellite/sensor observation of physical infrastructure. **What it
actually gives**: confirmation that a company owns specific Power-sector
physical assets an independent tracker also observes, *not* a
re-measurement of the company's total emissions (that would require
joining this Ownership package against Climate TRACE's separate
Emissions package by `source_id`, which wasn't completed — the
`avg_share_percent` column is a real read-before-trusting caveat here:
utilities show up with genuine high-percentage operational ownership,
while asset managers like BlackRock show up with tiny single-digit
percentages from index-fund equity stakes, a completely different
signal).

### 3. Tier 2 CO2 estimation — `tier2_estimation/`

For any ticker missing a real value for a **specific scope**,
`estimate_tier2.py` fills in an estimate for that scope only — modeled
on LSEG's published carbon-estimate "median model" (see
`docs/references/lseg-carbon-estimate-methodology.pdf`, the actual fact
sheet this is based on): take the median emissions intensity (tCO2e per
revenue, and separately per employee) among real peers **with a real
value for that same scope**, in the same GICS sector/sub-industry, then
scale by the target's own size. A 5-peer floor is used instead of
LSEG's 10, since 503 companies across ~130 GICS sub-industries rarely
clears 10 real-data peers at the narrow level.

Scope 1 and Scope 2 are estimated completely independently — each has
its own peer pool, its own median, and its own
`scope1_is_estimated`/`scope2_is_estimated` flag, so a company can have
a real Scope 1 and an estimated Scope 2 side by side (e.g. `MMM`: real
EPA-sourced Scope 1, estimated Scope 2 since EPA GHGRP doesn't cover
Scope 2 at all). Needs revenue/employee data for every ticker, which
`fetch_financials.py` pulls live from `yfinance` (cached to
`financials_cache.csv`).

### 4. Upright merge and gap-filling — `upright/`

`match_upright.py` matches a teammate's Upright Project export
(`data/upright_final_esg.json`) to the ticker roster and joins it into
`environmental_combined.csv` as `upright_*` columns — **not a Scope 1/2
tCO2e source**: Upright measures modeled, monetized cost/benefit in
cents per dollar of revenue. Matched by exact normalized name, a
squished-name fallback (drops spaces/hyphens, still exact on a
deterministic transform), a hand-verified alias table for ~39 confirmed
same-company name variants, and a multi-class alias table for 3
companies (Alphabet, Fox Corporation, News Corp) whose multiple tickers
are the same operating business, not different companies.

The 33 tickers with no real Upright record (verified independently
against Wikipedia's live constituent table — see
`docs/UPRIGHT_DATA_VERIFICATION.md`) get a peer-median **proxy** instead,
via `estimate_upright_gaps.py` — same sector-cascade approach as Tier 2,
tagged `upright_is_estimated=True`, never presented as Upright's own
output.

### 5. Final scoring — `scoring/compute_environmental_scores.py`

Combines everything above into `data/environmental_scores.csv`: Level,
Velocity, and Integrity scores plus the composite. Full formulas, worked
examples, and source citations are in `docs/SCORE_METHODOLOGY.md` — this
is the file to read to understand *why* each number is computed the way
it is.

### 6. Website export — `build_website_json.py`

Reshapes everything into `data/sp500_metrics.json`, one record per
current ticker with `co2`, `sbti`, `climate_trace`, `upright`, and
`scores` blocks. Real Upright rows keep the teammate's full original
JSON record verbatim for maximum fidelity. `data/upright_final_esg.json`
itself is never modified.

## Reproducing this pipeline end to end

```
py pipeline/pdf_extraction/merge_batches.py
py pipeline/epa_ghgrp/match_epa_ghgrp.py        # if the EPA source data changed
py pipeline/sbti/match_sbti.py                  # if the SBTi source data changed
py pipeline/climate_trace/match_climate_trace.py
py pipeline/tier2_estimation/fetch_financials.py
py pipeline/tier2_estimation/estimate_tier2.py
py pipeline/upright/match_upright.py
py pipeline/upright/estimate_upright_gaps.py
py pipeline/build_combined_dataset.py
py pipeline/scoring/compute_environmental_scores.py
py pipeline/build_website_json.py
```

Requires `py -m pip install pymupdf requests openpyxl yfinance`.

## Final coverage

- **Scope 1**: 247 real disclosures + 256 Tier 2 estimates = 503/503.
- **Scope 2**: 164 real disclosures + 339 Tier 2 estimates = 503/503.
- **SBTi match**: 223/503. **Climate TRACE Power-ownership match**:
  67/503. **Upright match**: 470 real + 33 proxy = 503/503.
- Real-disclosure sources: `cdp_pdf` 157, `sustainability_report` 138,
  `epa_ghgrp` 84 (some overlap resolved by preferring whichever source
  was found first).

See `docs/DATA_DICTIONARY.md` for the full column-by-column reference
across all three output files, and `docs/RESEARCH_LOG.md` for why
several free "obvious" data sources (CDP's own open data, Wikirate, an
NLP-derived ESG dataset) were investigated and rejected before this
direct-extraction approach was built.
