# `environmental_combined.csv` — column reference

One row per S&P 500 ticker (503 rows total, including a few dual-class
listings like GOOG/GOOGL). Built by `pipeline/build_combined_dataset.py`
from four sources joined on `ticker`:

- **Level input, real** (`environmental_emissions_master.csv`, built by
  `pipeline/merge_batches.py`) — real disclosed Scope 1/2 tonnage,
  collected from CDP PDFs, sustainability reports, and EPA GHGRP.
- **Level input, estimated** (`pipeline/tier2_estimation/tier2_estimates.csv`,
  built by `pipeline/tier2_estimation/estimate_tier2.py`) — for tickers
  with no real number at all, a sector-median emissions-intensity
  estimate scaled by the company's own revenue/employees, modeled on
  LSEG's published carbon-estimate methodology. **Never overwrites a real
  number** — only ever fills a ticker with zero real Scope 1/2 data.
- **Velocity input** (`pipeline/sbti/sbti_matches.csv`, built by
  `pipeline/sbti/match_sbti.py`) — Science Based Targets initiative
  target status, matched by exact normalized company name.
- **Integrity input** (`pipeline/climate_trace/climate_trace_matches.csv`,
  built by `pipeline/climate_trace/match_climate_trace.py`) — independent,
  satellite/sensor-based confirmation (not self-reported) that a company
  owns Power-sector physical assets Climate TRACE also tracks.

This file holds **raw collected inputs, not computed scores** — it is not
`level_score`, `velocity_score`, or `integrity_score`. Turning these
numbers into those scores (sector-relative normalization, weighting
against a science-based pathway, etc.) is separate, later work.

**Every estimated row is tagged `is_estimated=True`.** This is the
column to key any color-coding or visual distinction off of when
displaying this data — real and estimated Scope 1/2 figures should never
look the same on a chart or table without that flag being visible
somewhere (a badge, a footnote marker, a distinct color — whatever fits
the actual display).

## Quick numbers (as of the 2026-09-13 collection pass)

- **All 503 / 503 companies now have a CO2 figure — full coverage.**
  249 real disclosed + 254 Tier 2 estimated = 503, 0 blank.
- **249 / 503 companies (~50%)** have a real, disclosed Scope 1 and/or
  Scope 2 number (`is_estimated=False` with a populated `scope1_tco2e`
  and/or `scope2_*`).
- **254 / 503 companies (~50%)** have a Tier 2 **estimate**
  (`is_estimated=True`) instead — this covers both the tickers with
  `data_source=none` and tickers where a real report was found but the
  parser couldn't extract a usable number from it
  (`notes=no_fields_extracted` or similar) — both are the same practical
  gap from a "do we have a usable figure" standpoint.
- **A real bug was found and fixed while verifying this data (2026-09-13,
  second pass)**: 7 `epa_ghgrp` rows (3M, Albemarle, Baxter, Biogen,
  BlackRock, Brown-Forman, Delta Air Lines) had `data_source=epa_ghgrp`
  and a fully-formed match note, but a **blank `scope1_tco2e`** — the
  real number was sitting right there in `epa_ghgrp_matches.csv` the
  whole time, it just never got written into these 7 specific batch-file
  rows during an earlier session. All 7 were backfilled with their real
  EPA figures, which correctly moved them out of the Tier 2 estimate pool
  (they're real Level data now) and added them to the Tier 1 peer pool
  used to compute everyone else's sector-median estimates — worth
  knowing if a number you saw earlier for one of these 7, or for a
  Tier-2-estimated peer in the same sector, has since shifted slightly.
- **The last gap (Fiserv, `FISV`) was closed in a third pass (2026-09-13)**:
  Yahoo's `.info` endpoint returns null revenue/employees for this ticker
  (likely fallout from Fiserv's 2023 `FISV`→`FI` ticker change), which
  had left it with neither a real number nor an estimate. Its most recent
  annual revenue ($21.193B) was pulled instead from
  `yf.Ticker('FISV').income_stmt` (a real, non-fabricated Yahoo Finance
  figure, just from a different endpoint) and manually added to
  `financials_cache.csv`, which let `estimate_tier2.py` produce a normal
  revenue-based Tier 2 estimate for it like any other company.
- **223 / 503 companies (~44%)** matched to an SBTi record.
- **67 / 503 companies (~13%)** matched to a Climate TRACE Power-sector
  asset-ownership record.

## Columns

### Identity

| Column | Meaning |
|---|---|
| `ticker` | Stock ticker, as listed in the S&P 500. |
| `security` | Company name as used in our source ticker lists (may differ slightly from the company's own legal name). |

### Level — raw disclosed emissions

| Column | Meaning |
|---|---|
| `data_source` | Where the numbers below came from: `cdp_pdf` (a CDP climate-change questionnaire PDF), `sustainability_report` (a company sustainability/ESG/impact report, lower confidence than CDP), `epa_ghgrp` (matched via EPA's Greenhouse Gas Reporting Program — real government data, but **Scope 1 only**, see caveat below), or `none` (searched, nothing public found). |
| `report_url` | The actual PDF URL the numbers were extracted from (or matched from, for EPA). Blank for EPA rows with no PDF (`epa_ghgrp`'s value comes from a government database, not a document). |
| `scope1_tco2e` | Direct emissions (Scope 1), in metric tons CO2-equivalent. Blank if not found/extracted. |
| `scope2_location_tco2e` | Indirect emissions from purchased electricity, **location-based** method (grid average), in tCO2e. |
| `scope2_market_tco2e` | Indirect emissions from purchased electricity, **market-based** method (accounts for renewable energy purchases/certificates) — usually lower than location-based for companies buying clean power. |
| `scope1_base_year_end` | The company's stated baseline year for its Scope 1 reduction target (e.g. `12/31/2019`), when disclosed. |
| `scope1_base_year_tco2e` | Scope 1 emissions in that base year — lets you compute how far a company has moved from its own stated starting point. |
| `revenue_usd` | Annual revenue as stated in the same document (mainly present for CDP PDFs, which ask for it directly) — useful for computing emissions intensity (tCO2e / $ revenue). |
| `is_cdp_format` | Internal parser flag: `new`, `old`, or `False` — which CDP questionnaire layout the parser recognized, if any. Not a data-quality signal by itself (occasionally `new` shows up on a non-CDP document that merely *mentions* CDP — see `notes` and the pipeline README for one confirmed case). |
| `notes` | Free text: extraction problems (`no_fields_extracted`, `download_error: ...`), or — for manually-entered rows — a full explanation of how the number was verified against the source document's own internal totals. **Always read this before trusting a row that looks unusual.** |

**EPA GHGRP caveat**: `epa_ghgrp` rows only ever populate `scope1_tco2e`.
EPA's Greenhouse Gas Reporting Program is a registry of direct emitters
(facilities emitting ≥25,000 tCO2e/yr must report), not a corporate
disclosure framework — it has no Scope 2 concept at all. Never treat a
blank `scope2_*` on an `epa_ghgrp` row as "zero" or "not disclosed" — it
means "this source doesn't cover that scope."

**Reading `data_source` vs. actually having a number**: `data_source` in
{`cdp_pdf`, `sustainability_report`} means a real report was found and a
genuine extraction attempt was made — it does **not** guarantee
`scope1_tco2e` etc. are populated. Check `notes` for
`no_fields_extracted` or `download_error` to see whether that attempt
actually yielded a number. `data_source=epa_ghgrp` rows always have a
number (that's the point of the match) but only for `scope1_tco2e`.

### Level — ESTIMATED emissions (Tier 2, only for `data_source=none`)

For the ~124 companies with no real report found at all, this pipeline
can optionally fill in an **estimate** — never a substitute for real
data, and never applied on top of a real number. Modeled on LSEG's
published carbon-estimate "median model": take the median emissions
intensity (tCO2e per $ revenue, and separately per employee) among real
S&P 500 peers in the same GICS sector/sub-industry, then scale it by the
target company's own revenue/employee count.

| Column | Meaning |
|---|---|
| `is_estimated` | **`True`/`False` — the column to key any color-coding off of.** `True` means every emissions figure on this row is a Tier 2 estimate, not a disclosure. |
| `tier2_scope1_tco2e` / `tier2_scope2_tco2e` | The estimated split, in tCO2e. The scope1/scope2 split itself is a secondary approximation (using the peer group's median scope1-share) layered on top of a single combined-total estimate — see `tier2_notes` for the arithmetic. |
| `tier2_method` | Which inputs were available: `median_model_revenue`, `median_model_employees`, or `median_model_revenue+employees` (averaged, matching LSEG's approach of averaging both methods when both are available). |
| `tier2_sector_used` | Which peer group actually supplied the median, e.g. `sub_industry:Semiconductors` or `sector:Information Technology` — the model widens from sub-industry to sector (and finally to the whole S&P 500) if the narrower group doesn't have enough real-data peers (`tier2_peer_count`). |
| `tier2_peer_count` | How many real-data (Tier 1) companies were in that peer group. |
| `tier2_notes` | The full arithmetic: which ratios were used, what they were multiplied by, and the resulting estimate. Read this before citing a specific estimated number anywhere. |

**This is genuinely an estimate, not a disclosure** — two S&P 500
companies in the same GICS sub-industry can have very different actual
emissions profiles even at similar revenue, so treat any individual
`tier2_*` number as directionally informative, not a substitute for the
real figure this pipeline was never able to find.

### Velocity — Science Based Targets initiative status

| Column | Meaning |
|---|---|
| `sbti_matched` | `True`/`False` — whether this ticker matched an SBTi record by exact normalized company name (same conservative, no-fuzzy-matching approach used for EPA GHGRP — a false match risks attributing the wrong company's target). |
| `sbti_near_term_status` | `Targets set` (validated by SBTi), `Committed` (pledged to submit a target, not yet validated), `Commitment removed` (had a target, then withdrew or let it lapse — a real, meaningful signal; Tesla and Amazon are both in this state as of this pull), or blank if unmatched. |
| `sbti_near_term_target_classification` | The ambition level of the target, e.g. `1.5°C` or `Well-below 2°C` — which warming pathway the target is consistent with. |
| `sbti_near_term_target_year` | The year the company's near-term target is due (e.g. `2030`, or `FY2030` for a fiscal-year target). |
| `sbti_long_term_status` | Same status vocabulary as `sbti_near_term_status`, but for the company's long-term (typically 2040-2050) target, if any. |
| `sbti_long_term_target_year` | Target year for the long-term target. |
| `sbti_net_zero_status` | Whether the company has a validated net-zero commitment specifically (distinct from a near/long-term reduction target). |
| `sbti_net_zero_year` | The year the company commits to reach net zero. |
| `sbti_full_target_language` | The exact free-text description SBTi publishes for this company's target — usually states the precise % reduction and base year in plain language (e.g. "commits to reduce absolute scope 1 and scope 2 GHG emissions 50.4% by 2032 from a 2024 base year"). This is the most information-dense field — worth reading directly rather than relying only on the structured columns above. |
| `sbti_date_updated` | When SBTi last updated this company's record. |

### Integrity — Climate TRACE independent Power-sector ownership

Independent of anything the company self-reports: Climate TRACE estimates
emissions from satellite/sensor observation of physical assets, then
separately publishes who owns each asset. These columns say whether an
S&P 500 company shows up as an owner of Power-sector assets Climate TRACE
tracks — **not** an independent re-measurement of the company's total
Scope 1/2 emissions (that would require joining this ownership data
against Climate TRACE's separate Emissions package by `source_id`, which
wasn't completed this session — see `pipeline/README.md`).

| Column | Meaning |
|---|---|
| `climatetrace_power_matched` | `True`/`False` — whether this ticker appears as a parent owner of any Power-sector asset in Climate TRACE's data. |
| `climatetrace_power_asset_count` | How many distinct Power-sector assets (plants) this company appears as an owner of, anywhere in the world. |
| `climatetrace_power_subsectors` | Which Power subsectors these assets fall into (e.g. `electricity-generation`), semicolon-separated. |
| `climatetrace_power_countries` | ISO3 country codes of the assets' locations, semicolon-separated. |
| `climatetrace_power_avg_share_percent` | The company's average ownership share across its matched assets, 0-100. **Read this before treating a match as meaningful**: utilities like Duke Energy (`DUK`) average ~92% (real operational ownership), while asset managers like BlackRock (`BLK`, 1,862 assets, ~5.2% avg share) and State Street (`STT`, 1,066 assets, ~3.1% avg share) show up because of small index-fund equity stakes, not operational control — a completely different signal that a naive "asset count" alone would conflate. |

## Known data-quality flags worth reading before using a specific row

A few rows have unusual circumstances noted in `notes` — worth knowing
about before citing them:

- **VMRK (Vivmark Residential)**: this ticker is the August 2026 merger
  of AvalonBay Communities and Equity Residential. The entered figure is
  **AvalonBay's own pre-merger CDP data only** — roughly half the
  combined company's real footprint, not a combined-entity disclosure
  (none exists yet).
- **NKE (Nike), WBD (Warner Bros. Discovery), CRM (Salesforce), SJM
  (J.M. Smucker), TDY (Teledyne)**: these five were entered **manually**
  rather than by the automated parser, because their reports use
  one-off table layouts the general-purpose parser can't safely
  generalize from (risk of grabbing the wrong year, wrong sub-metric, or
  a decoy row). Each was cross-verified against that same document's own
  internal arithmetic (e.g. summed sub-totals matching a stated grand
  total) before being entered — see each row's `notes` for the exact
  verification performed.

See `pipeline/README.md` for the full collection methodology, the
project's "never fabricate a number" rule, and what's planned next
(Tier 2 sector-median estimation for the 124 `none` companies).
