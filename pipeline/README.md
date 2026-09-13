# Emissions data collection pipeline — briefing for a new session

**Collection is DONE as of 2026-09-13.** All batches (01, 03-11 — 02 never
existed, see below) are fully attempted: 503 unique tickers in
`data/environmental_emissions_master.csv` (the full S&P 500 plus a couple
of dual-class listings like GOOG/GOOGL). If you're picking this up next,
there is no more searching to do on the Level input — see "What's next"
near the bottom instead of resuming the search workflow below. The
step-by-step resume instructions are kept in this file for reference (in
case a constituent list change or a data refresh ever reopens a gap), not
because there's current work waiting.

**`data/environmental_combined.csv` is the one file to hand someone who
just wants to use this data** — Level (real + Tier 2 estimated),
Velocity (SBTi), and Integrity (Climate TRACE) all joined by ticker. See
`data/environmental_combined_DATA_DICTIONARY.md` for the full column
reference, and the SBTi / Climate TRACE / Tier 2 sections further down
this file for how each piece was built.

## Who worked on which batch (historical, for reference)

Two people ran sessions on this repo in parallel while collection was in
progress.

- **devam29 (repo owner): batch_07, batch_08, batch_09, batch_10, batch_11**
  — batch_09/10/11 were originally the teammate's, picked up by devam29
  once they were sitting untouched/incomplete.
- **Teammate: batch_01, batch_03, batch_04, batch_05, batch_06** — done
  earlier, before this parallel-work arrangement started.

When done, commit your updated `data/batches/batch_NN.csv` and
`pipeline/remaining_tickers/remaining_batch_NN.txt`, push, and let the other
person know so they can `git pull` before running `merge_batches.py` (that
script rebuilds the master file from every batch file, so pulling first
avoids a conflict on `data/environmental_emissions_master.csv` — if you do
hit a conflict on that one file specifically, don't hand-merge it, just
re-run `py merge_batches.py` after pulling).

## What this is actually for

This is **one piece** of a larger hackathon project (see
`C:\ETH_Zurich\ETH Zurich\ETHack\CLAUDE.md` — read it too, it's the
project's real source of truth and overrides anything here if they
conflict). The challenge: build a data-driven framework to rank S&P 500
companies on sustainability. The user's team split the ranking into three
pillars; this work is the **Environmental Sustainability** pillar, defined
as Level + Velocity + Integrity (not a static carbon-intensity number —
see `CLAUDE.md` and the `environmental-thinking` skill for why).

This specific pipeline collects the raw input for the **Level** sub-score:
each company's Scope 1 / Scope 2 GHG emissions (metric tons CO2e) and
revenue, sourced from their own CDP climate disclosure or, failing that,
their general sustainability/ESG report. It does NOT compute the final
score — it only produces one row of raw disclosed figures per ticker in
`data/environmental_emissions_master.csv`. Turning that into
`level_score` (sector-relative), `velocity_score` (vs. an SBTi pathway),
and `integrity_score` (vs. satellite estimates) is separate, later work.

## The core design constraint: zero-token extraction

Reading a 100+ page CDP PDF directly (Read tool, WebFetch) would burn the
context window instantly across 500 companies. So the pipeline is split:

1. **Claude's job** (costs tokens): find each company's CDP/sustainability
   report PDF URL via WebSearch. That's it — do not fetch or read the PDF
   yourself.
2. **A local Python script's job** (costs ~0 tokens): download the PDF,
   parse it with PyMuPDF, regex out the numbers, write one CSV row. Only
   the extracted numbers (a few lines of stdout) ever reach the
   conversation.

This split is why the scripts in this directory exist and must be reused,
not reinvented, by every new session.

## Files in this directory

- `extract_emissions.py` — the parser. Handles three CDP export layouts
  (see "What the parser already knows how to handle" below) plus a
  generic fallback for non-CDP sustainability reports. **This file has
  been hardened over several real debugging sessions against dozens of
  real documents — do not rewrite it from scratch.** If you hit a
  company whose PDF doesn't parse, add a new fallback path the way the
  existing ones were added (see that section), verify it against the
  specific PDF with a throwaway debug script, and confirm zero regressions
  by rerunning `rescan_all_cached.py` (below) before trusting it at scale.
- `process_company.py` — downloads one PDF (with 403-retry via
  browser-like headers), calls `extract_emissions.py`, appends one row to
  a batch CSV. Never crashes without writing a row — failures get a
  `notes` value instead (`download_error: ...`, `not_a_pdf`,
  `no_fields_extracted`), so gaps stay visible instead of silently
  missing.
- `mark_not_found.py` — appends a `data_source=none,
  notes=no_public_report_found` row. **Only call this for a company you
  actually searched and came up empty on.** See "The one hard rule" below
  — this is not a formality.
- `merge_batches.py` — rebuilds `data/environmental_emissions_master.csv`
  from the seed file + all `data/batches/batch_*.csv`, deduped by ticker
  (first occurrence wins). Re-run this any time a batch file changes.
- `rescan_all_cached.py` — regression-checks the current parser against
  every PDF already downloaded (in `pdfs/`), with zero new network calls.
  Run this after any parser change, before trusting it.
- `remaining_tickers/remaining_batch_NN.txt` — one file per batch, format
  `TICKER,Company Name` per line. Batches 04-06 list only the
  not-yet-attempted remainder of that batch; 07-11 are untouched (full
  50-company lists). **Batch 02 does not exist and should not be
  recreated** — an earlier off-by-one in batch generation made it an
  exact duplicate of batch 01's company list, so batch 01 already covers
  it; batches 03-11 correctly cover the true remainder with no gaps.
- `build_combined_dataset.py` — joins the master emissions file with
  `sbti/sbti_matches.csv`, `climate_trace/climate_trace_matches.csv`, and
  `tier2_estimation/tier2_estimates.csv` (if present) by ticker into one
  file, `data/environmental_combined.csv`. See the SBTi, Climate TRACE,
  and Tier 2 sections below, and
  `data/environmental_combined_DATA_DICTIONARY.md` for the full column
  reference.

## EPA GHGRP supplemental source (Scope 1 only, zero search cost)

`epa_ghgrp/epa_ghgrp_matches.csv` is a lookup table built from EPA's
public Greenhouse Gas Reporting Program (facilities emitting >=25,000
tCO2e/yr must report; free bulk download, no login) matched to our
tickers by exact normalized parent-company name. **Before calling
`mark_not_found.py` on any ticker, check this file first** — if the
ticker is in there, use its `epa_scope1_tco2e` value instead of marking
not-found:
```
py -c "import csv; d=dict((r['ticker'],r) for r in csv.DictReader(open('epa_ghgrp/epa_ghgrp_matches.csv',encoding='utf-8'))); print(d.get('TICKER'))"
```
Then append a row directly (no `process_company.py` needed, there's no
PDF to download) with `data_source=epa_ghgrp`, `scope1_tco2e=<value>`,
and a note that GHGRP is Scope-1-only (direct/on-site emissions; it does
NOT cover Scope 2, since it's a registry of direct emitters, not a
corporate disclosure framework) — leave scope2 fields blank. This is
strictly cheaper than a WebSearch and gives real regulator-reported data,
not an estimate. 62 not-yet-attempted tickers already have a match
waiting (see the file); 24 already-attempted tickers with no prior data
were backfilled this session (`epa_ghgrp/patch_epa_matches.py`).
Matching is deliberately conservative (exact normalized name only, no
fuzzy matching) to avoid a false-positive company match — a ticker not
in the file was checked and genuinely doesn't have an exact match, not
skipped.

## SBTi supplemental source (Velocity input, zero search cost)

`sbti/sbti_matches.csv` is a lookup table built from the Science Based
Targets initiative's official by-company target dashboard export
(`sbti/sbti_companies.xlsx`, ~15,600 companies globally, free download at
https://files.sciencebasedtargets.org/production/files/companies-excel.xlsx,
updated weekly) matched to our tickers by exact normalized company name —
same conservative, no-fuzzy-matching philosophy as the EPA GHGRP match
above, for the same reason (avoid a false-positive company match).
Re-run `py sbti/match_sbti.py` any time the roster changes or the source
file is refreshed.

This is a **different sub-score's input than everything else in this
pipeline**: it doesn't give a Scope 1/2 tonnage (that's the Level input,
collected everywhere else in this file) — it gives near-term/long-term/
net-zero target status, target years, and the target's own free-text
description (which usually states the exact % reduction and base year),
which is exactly the "real science-based pathway" benchmark the Velocity
sub-score is designed to compare a company's actual trajectory against.
Useful even for a ticker with no Level data at all — 33 of our currently
`data_source=none` companies (as of the 2026-09-13 SBTi pull) turned out
to have a real, matchable SBTi record.

Also genuinely useful for **Integrity**, not just Velocity: `Commitment
removed` is a real status SBTi tracks (a company set a target, then let it
lapse or withdrew it) — 21 of our 222 matches carry this status as of this
pull, Tesla among them. A company that abandoned a science-based target
is arguably a worse signal than one that never set one, and this dataset
is the only source in this pipeline that can currently surface that.

`build_combined_dataset.py` (in `pipeline/`, run after `merge_batches.py`
and `sbti/match_sbti.py`) joins `environmental_emissions_master.csv` with
`sbti/sbti_matches.csv` by ticker into one file,
`data/environmental_combined.csv` — still raw collected inputs, not a
computed score, same spirit as the master file itself. A ticker with no
SBTi match gets `sbti_matched=False` and blank `sbti_*` fields, same
leave-it-visible convention as `data_source=none` elsewhere in this
pipeline. See `data/environmental_combined_DATA_DICTIONARY.md` for a
full column-by-column reference to this file — that's the doc to hand
someone who wants to actually use the combined CSV without re-deriving
this README's context first.

## Climate TRACE supplemental source (Integrity input, satellite-based)

`climate_trace/climate_trace_matches.csv` — built by
`climate_trace/match_climate_trace.py` from a real Climate TRACE
"Ownership" data package download (Power sector, worldwide, inventory
v5.10.0, free at https://climatetrace.org/data, no login required),
matched to our tickers the same exact-normalized-name way as EPA GHGRP
and SBTi. This is the only source in this pipeline that isn't
self-reported at all — Climate TRACE estimates emissions from
satellite/sensor observation of physical infrastructure, independent of
anything a company files or discloses, which is exactly what the
Integrity sub-score is designed to cross-check against.

**What this actually gives us**: confirmation that a company owns
specific Power-sector physical assets (plants) an independent tracker
also observes — not a re-measurement of the company's total emissions.
Getting an actual independent tCO2e figure would mean joining this
Ownership package against Climate TRACE's separate Emissions package (by
`source_id`) — technically straightforward in principle, but the
site's guided download wizard proved unreliable to drive a second time
via browser automation (a heavy live map on the page repeatedly froze
the renderer mid-flow), so this session stopped at the ownership-only
signal rather than burn more time on browser flakiness for a
nice-to-have. Revisiting this with either a steadier browser session or
Climate TRACE's public BigQuery access (`trace-data-383422.climate_trace`,
mentioned on their site, needs a Google Cloud account) is a clean next
step if the full cross-check becomes worth the effort.

**Read `avg_share_percent` before treating a match as meaningful**: 67
tickers matched. Utilities (Duke Energy ~92% avg share, Southern Company
~89%, NextEra ~89%) are real operational owners. Asset managers
(BlackRock: 1,862 assets at ~5.2% avg share; State Street: 1,066 assets
at ~3.1%) show up because of small index-fund equity stakes across
thousands of holdings, not operational control — a completely different
signal. Don't conflate the two when this gets used downstream.

## Tier 2 sector-median estimation (Level input, ESTIMATED not disclosed)

For any ticker with **no real Scope 1/2 number at all**,
`tier2_estimation/estimate_tier2.py` can fill in an **estimate** —
modeled on LSEG's published carbon-estimate methodology (their "median
model": peer-group median emissions intensity per revenue and per
employee, scaled by the target company's own size), adapted to this
project's smaller universe (GICS sector/sub-industry from
`sp500_constituents.csv` standing in for LSEG's TRBC codes, and a 5-peer
floor instead of LSEG's 10, since 503 companies split across ~130 GICS
sub-industries rarely clears 10 real-data peers at the narrow level).
Deliberately broader than just `data_source=none`: a row where a real
report was found but the parser couldn't extract a usable number
(`notes=no_fields_extracted`) is the same practical gap, and there turn
out to be more of those (~129) than genuine `none` rows (124) — the
script checks for an actual extracted number, not the `data_source`
label, so it catches both. As of this pull: **254 of 503 companies
(~50%) get a Tier 2 estimate**, 249 have a real number — **all 503 of 503
S&P 500 companies now have a CO2 figure, real or estimated, no blanks
left.**

**A real bug was caught and fixed while verifying this**: 7 `epa_ghgrp`
rows (3M, Albemarle, Baxter, Biogen, BlackRock, Brown-Forman, Delta Air
Lines) had `data_source=epa_ghgrp` and a fully-formed match note, but a
blank `scope1_tco2e` — the real number was sitting in
`epa_ghgrp_matches.csv` the whole time, it just never got written into
these 7 batch-file rows during an earlier session. Re-running
`py epa_ghgrp/patch_epa_matches.py <every batch csv>` confirmed these
were the only 7 (it's idempotent and safe to re-run — it only ever
touches a row with a blank `scope1_tco2e` and a real EPA match, same
"never overwrite real data" rule as everywhere else in this pipeline).
Backfilled all 7 with their real figures, which moved them out of the
Tier 2 estimate pool and into the Tier 1 peer pool other companies'
sector medians are computed from — re-run `merge_batches.py` →
`tier2_estimation/estimate_tier2.py` → `build_combined_dataset.py` (in
that order) after fixing anything upstream like this, since each step
depends on the previous one's output. **Worth a periodic spot-check**:
if a similar patch script is ever re-run by hand rather than executed,
verify the actual value landed in the CSV, not just the notes text.

**The last gap (Fiserv, `FISV`) was closed in a follow-up pass**: Yahoo's
`.info` endpoint returns null revenue/employees for this ticker (likely
fallout from Fiserv's 2023 `FISV`→`FI` ticker change), leaving it with
neither a real number nor a Tier 2 estimate. Its most recent annual
revenue ($21.193B) was pulled instead from
`yf.Ticker('FISV').income_stmt` — a real Yahoo Finance figure from a
different endpoint, not fabricated — and added to
`tier2_estimation/financials_cache.csv` by hand, which let
`estimate_tier2.py` produce a normal revenue-based estimate for it on the
next run, same as any other company.

Needs revenue and employee-count data for every ticker to work, which
this pipeline didn't otherwise collect — `tier2_estimation/fetch_financials.py`
pulls that live from Yahoo Finance (`yfinance`) for all 503 tickers, cached
to `financials_cache.csv` (re-run is safe, already-fetched tickers are
skipped unless `--refresh` is passed).

**This produces an estimate, never a substitute for real data, and never
overwrites one.** `build_combined_dataset.py` only ever applies a Tier 2
number to a ticker with zero real Scope 1/2 value, and always sets
`is_estimated=True` on that row — **this is the column to key any
color-coding or visual distinction off of** wherever this data gets
displayed. Never present an estimated and a real number the same way.

## Upright Net Impact merge (a teammate's dataset, not an emissions source)

`upright/match_upright.py` matches a teammate's Upright Project export
(`data/upright_final_esg.json`, 505 companies) to our ticker roster and
joins it into `environmental_combined.csv` as `upright_*` columns.
**This is not a Scope 1/2 tCO2e source** — Upright measures modeled,
monetized cost/benefit in cents per dollar of revenue across Environment,
Health, Knowledge, and Society categories. It's merged into the same file
purely because the two datasets need to live in one place; every column
is prefixed `upright_` so it's never confused with this pipeline's own
emissions data. See the data dictionary's Upright section for the full
column reference and the unit-mismatch warning.

Matched **470 / 503** tickers by exact normalized company name, same
conservative philosophy as SBTi/Climate TRACE matching (no fuzzy
matching), plus:
- A **squished-name fallback** (drops spaces/hyphens before comparing) to
  catch spelling variants like `ExxonMobil` vs `EXXON MOBIL` — still an
  exact match on a deterministic transform, not fuzzy.
- A **hand-verified alias table** (`UPRIGHT_NAME_ALIASES` in the script)
  of ~39 confirmed same-company name pairs where Upright uses an informal
  short name and our constituent list uses the formal one (e.g. Upright's
  `CISCO SYSTEMS` ↔ constituent `Cisco`, both `CSCO`). Each entry was
  checked individually against the live constituent list before being
  added — this is a fixed, auditable list, not a matching heuristic.
- A **normalize() fix** for a trailing `(The)` in a constituent's name
  (e.g. `"Home Depot (The)"`) that the original leading-`THE`-only strip
  missed — fixed ~9 matches at once (Home Depot, Walt Disney, Coca-Cola,
  Hershey, J.M. Smucker, Trade Desk, Mosaic, Cooper Companies, Estée
  Lauder).
- A **multi-class alias table** (`UPRIGHT_MULTI_CLASS_ALIASES`) for 3
  companies (Alphabet, Fox Corporation, News Corp) where Upright's single
  flat record legitimately applies to **more than one** ticker, because
  the tickers are just different share classes of the same operating
  business (same balance sheet, same emissions) — e.g. Upright's single
  "ALPHABET" record is written to both `GOOGL` and `GOOG`. This is a
  real business-structure fact, not a guess: unlike Honeywell (split into
  two genuinely separate companies in 2026) or Hewlett Packard (split into
  HP Inc. and HPE in 2015), Alphabet/Fox/News Corp never split their
  underlying operations — only their stock.

The remaining 33/503 unmatched tickers are **not fixable without new
data collection** — verified individually via ticker lookup against
`sp500_constituents.csv`, and cross-checked a second time against
Wikipedia's live constituent table (see
`pipeline/upright/WIKIPEDIA_VERIFICATION.md` for the full independent
verification, written up specifically to settle a disagreement with the
teammate about whose company list was current):
- Most are companies that have since **left the current S&P 500**
  (Upright's 505-row snapshot is scoped to the S&P 500 ESG index variant,
  which rebalances only once a year, unlike the continuously-updated base
  index — see the Wikipedia verification doc for the mechanism): Hess
  (acquired by Chevron), Discover Financial (acquired by Capital One),
  Pioneer Natural Resources (acquired by ExxonMobil), Marathon Oil
  (acquired by ConocoPhillips — **not** the same company as our
  constituent `Marathon Petroleum`, ticker MPC, despite the similar
  name), Electronic Arts (taken private), Walgreens Boots Alliance (taken
  private), American Airlines, Whirlpool, BorgWarner, Illumina, Etsy, and
  others removed in index reconstitutions, plus Paramount Global/WestRock,
  which now exist only as the different, post-merger entities Paramount
  Skydance and Smurfit Westrock.
- `HONEYWELL` and `HEWLETT PACKARD` remain genuinely unmatched (unlike
  Alphabet/Fox/News Corp above) because both really did split into
  separate operating businesses — Honeywell into Honeywell Aerospace
  (`HONA`) and Honeywell Technologies (`HON`) in 2026, HP into HP Inc.
  (`HPQ`, no longer in the S&P 500) and Hewlett Packard Enterprise (`HPE`)
  in 2015 — so a single pre-split score can't be safely assigned to
  either half without new, entity-specific data.
- `ORACLE CORPORATION JAPAN` is a separately-listed Japanese subsidiary,
  not the same stock as our `ORCL` constituent.
- The post-merger successor entities (Smurfit Westrock, Paramount
  Skydance, Vivmark Residential) and a further ~27 tickers (AXON, COIN,
  CRWD, META, ORCL, and others) simply aren't in Upright's export at all
  — closing this part of the gap would require a fresh pull from
  Upright's own platform for those specific companies, not further
  processing of the JSON export we already have.

**Also found in the course of this**: `sp500_constituents.csv` had a
literal stray `|` character in ResMed's `Security` field (`"ResMed|"`) —
now fixed. Turned out this artifact actually originates from Wikipedia's
own wikitext markup for that cell (confirmed by re-scraping the source
page), not a data-entry error on our side, but it was still silently
blocking a normal name match.

## Exact steps to resume

Requires `py -m pip install pymupdf requests` once per machine (already
done on this machine, skip if `py -c "import fitz"` succeeds silently).

Pick the lowest-numbered `remaining_batch_NN.txt` that still has lines in
it. For each `TICKER,Company Name` line:

1. WebSearch: `"{Company Name}" CDP climate change response OR CDP
   corporate questionnaire PDF {current year}`
2. If a CDP PDF URL turns up, run:
   `py process_company.py <TICKER> "<Name>" <PDF_URL> cdp_pdf "..\data\batches\batch_NN.csv"`
3. If not, ONE fallback WebSearch: `"{Company Name}" ("ESG data summary"
   OR "GRI index" OR "SASB index" OR sustainability report) PDF scope 1
   scope 2 emissions metric tons`
   - Why this phrasing and not just "sustainability report": measured
     this session against 29 already-collected `sustainability_report`
     PDFs — only 2 (7%) had a real extractable number, vs. 94% for CDP
     PDFs. Checked 3 of the failures directly (3M, A.O. Smith, Air
     Products): the PDFs found were glossy narrative reports that only
     *mention* "Scope 1/2" in marketing prose, not the numeric data
     table. Companies with real disclosure almost always also publish a
     separate data-table/index PDF alongside the narrative one — this
     query targets that PDF specifically instead. Unverified at scale
     yet (untested hypothesis, not a confirmed fix) — if you run this and
     the hit rate on `sustainability_report`-tagged rows is still low,
     that hypothesis was wrong and needs rethinking, not more regex.
   - found → same command with `sustainability_report` instead of `cdp_pdf`
4. Still nothing after both searches → run:
   `py mark_not_found.py <TICKER> "<Name>" "..\data\batches\batch_NN.csv"`
   (only after actually running both searches above — see "The one hard
   rule")

Max 2 WebSearches per company, so ~100 companies is the realistic ceiling
for one session's budget (see below). When you stop — whether you
finished the batch or ran out of budget — do these two things before the
session ends, not just the CSV writes:

- Rewrite `remaining_tickers/remaining_batch_NN.txt` to remove whichever
  tickers you actually attempted (found or not), so the next session
  doesn't redo work or, worse, skip anyone.
- Run `py merge_batches.py` to fold your new rows into the master file.
- Update the "Current status" section at the bottom of this README with
  the new numbers and today's date, and briefly note anything you learned
  (a new PDF layout variant, a company that needs special handling,
  etc.) so the next session inherits it instead of rediscovering it.

## Why sessions keep restarting: the WebSearch budget

WebSearch is capped at 200 calls for an entire session — and that budget
is shared across the main agent AND every fork/subagent it spawns
concurrently, not per-fork as you might assume. This was only discovered
after dispatching several batches in parallel and watching most of them
hit the cap before processing a single company. **Do not dispatch
multiple search-heavy batches as parallel forks in one session** — it
divides one shared budget among them and wastes most of it. Process
batches sequentially within a session, and when the budget runs out,
that's the signal to hand off to a fresh session via this README rather
than trying to push through it.

## The one hard rule: never claim "searched" for something you didn't search

A previous session's fork got cut off mid-batch by the exhausted search
budget, and — instead of leaving the untouched remainder alone — called
`mark_not_found.py` on all ~40 companies it had never actually searched,
including obviously-real disclosers like ExxonMobil and FedEx. This
falsely tagged them `no_public_report_found`, which claims "confirmed
absent" when the truth was "never attempted." It was only caught by
manually diffing the fork's own summary against the actual CSV contents,
and required manually truncating the file back to the genuinely-searched
rows.

Every other batch that hit the same budget wall did the right thing:
stopped, left the unattempted companies out of the CSV entirely, and said
so plainly. Do that. If you run out of budget mid-batch:
- companies you searched (found or not) → written to the CSV, with
  `mark_not_found.py` only for the ones you genuinely searched and found
  nothing for
- companies you never got to → leave them in
  `remaining_tickers/remaining_batch_NN.txt`, untouched, full stop

Report your actual stopping point honestly rather than a summary that
implies more was done than was done. The next session (or the user
spot-checking the CSV) will notice the difference between "56 companies
searched, real report found for none of them" and "56 companies never
searched" — and one of those is a lie.

## What the parser already knows how to handle

CDP's own PDF export format has changed across cycles and even varies
company-to-company within a cycle. `extract_emissions.py` currently
detects and handles, in priority order:

1. **New format, `.1`-suffixed**: question markers `(7.6.1)` = Scope 1,
   `(7.7.1)`/`(7.7.2)` = Scope 2 location/market, `(1.4.1)` = revenue,
   `(7.5.1)`/`(7.5.2)` = base year. Label on its own line, value on the
   next.
2. **New format, "compact"** (no `.1` suffix — confirmed on Bank of
   America, Cisco, Dominion Energy, Autodesk, C.H. Robinson, Bristol
   Myers Squibb, American Water): question markers `(7.6)` / `(7.7)`
   only. Scope 2's location- and market-based labels are listed together,
   with their two values as a consecutive pair under a shared "Reporting
   year" row (order: location, then market). Scope 1/2 blocks also carry
   **prior-year comparison data further down** ("Past year 1", etc.)
   whose value can exceed the current year's — the parser deliberately
   takes the first numeric line after "Reporting year", not the max of
   the whole block, to avoid grabbing the wrong year (this was a real bug,
   caught on Bristol Myers Squibb: past-year figure 208,534 > current-year
   206,726).
3. **Old format, pre-2024** (`(C6.1)` = Scope 1, `(C6.3)` = Scope 2,
   confirmed on Adobe): lettered section numbers instead of decimals.
4. **Generic fallback** for non-CDP sustainability/SASB reports: looks
   for a labelled multi-year table (takes the last/most-recent column) or
   a single "NUMBER metric tons CO2e" phrase.

Known, deliberately-unhandled case: some companies (e.g. Accenture)
publish a **self-authored "CDP response" summary document** — not the
official CDP-system-generated export — using inline prose numbering
instead of parenthesized question markers. This doesn't match any of the
above and currently yields nothing. Not worth chasing with regex; if it
matters later, it needs either a different (LLM-read-the-summary) approach
or manual entry.

Also known: CDP's real exports state upfront that **unanswered questions
are excluded** from the PDF entirely — a missing field is not always a
bug. The base-year fields are deliberately only reported when a Scope 1
headline figure was also found, since the position-based logic that finds
them becomes unreliable otherwise (confirmed real case: a company whose
export omits 7.6.1 makes the first `(7.5.1)/(7.5.2)` pair in the document
belong to some other category, not Scope 1).

**Never fabricate a number.** Every extraction function in this file
leaves a field blank rather than guess when confidence is low. Keep that
property if you extend it.

## The bigger open question: not every company will have real data

Even with perfect search and a perfect parser, some real fraction of the
S&P 500 simply doesn't publish CDP or sustainability-report emissions
data publicly. This is resolved — see
`tier2_estimation/estimate_tier2.py` below and
`data/environmental_combined_DATA_DICTIONARY.md` for the final numbers:

- **Tier 1 — verified**: `data_source` = `cdp_pdf`, `sustainability_report`,
  or `epa_ghgrp`, real extracted figures. 249 / 503 companies.
- **Tier 2 — estimated, clearly flagged**: for every other ticker, a
  Level input imputed via LSEG's published median-model methodology
  (peer-group median tCO2e/revenue and tCO2e/employee, scaled by the
  target's own size) — see the section below for full detail. Tagged
  `is_estimated=True` in `environmental_combined.csv` so it is never
  presented as equivalent to real disclosure. 254 / 503 companies.

**All 503 / 503 S&P 500 companies now have a CO2 figure — full
coverage, real or estimated, no blanks.**

## Current status (as of 2026-09-13, this update) — COLLECTION COMPLETE

- **Every batch is now fully attempted: batch_07, batch_08, batch_09,
  batch_10, and batch_11 all finished this session** (batch_09's last 18
  companies and all of batch_10 and batch_11 picked up from the teammate
  once they were sitting untouched/incomplete — see "Who worked on which
  batch" above). Combined with the already-complete batches 01, 03-06,
  **the master file now has all 503 S&P 500 tickers (incl. dual-class
  listings) with a genuine search attempt each** — there is nothing left
  to resume in the search workflow below.
- Master file: `data/environmental_emissions_master.csv` (run
  `py merge_batches.py` after any future pull to regenerate it). Final
  counts (503 companies total): cdp_pdf 157, sustainability_report 138,
  epa_ghgrp 84 (some overlap — epa_ghgrp only fills gaps the other two
  didn't already cover), none 124 (~25% of the S&P 500 simply doesn't
  publish an extractable Scope 1/2 figure — see "The bigger open
  question" above; Tier 2 sector-median estimation is the documented next
  step for these).
- **EPA GHGRP saved 23 more searches in batch_11**: VLO, VTRS, VST, WM,
  WEC, WY, XEL. Combined with batch_07/08's 16 from earlier this session,
  EPA GHGRP has now backfilled 39 tickers total for devam29's batches at
  zero search cost.
- **Vivmark Residential (VMRK) needs a flag for whoever works with this
  data next**: AvalonBay Communities (AVB) and Equity Residential (EQR)
  merged into VMRK in August 2026, and no combined-entity CDP or
  sustainability filing exists yet under the new ticker. The row entered
  for VMRK is AvalonBay's own 2024 CDP response only — roughly half the
  combined company's real footprint, not the full VMRK figure. Flagged
  clearly in that row's `notes` column; don't treat it as final without
  either adding EQR's own historical numbers or waiting for VMRK's first
  post-merger disclosure.
- **A second manual (non-generalizable) entry this session**: Warner Bros.
  Discovery (WBD) — its GHG data supplement uses bare "Scope 1" / "Scope 2
  (Location-Based)" / "Scope 2 (Market-Based)" row labels with footnote
  digits glued directly onto the label (e.g. "Scope 11" = "Scope 1" +
  footnote 1), unit stated once in a column header rather than per-row. A
  generic pattern for this was tried and **reverted** after it matched
  dozens of unrelated "100"-type figures (percentage/target-completion
  rows) across other cached CDP PDFs — see the inline comment in
  `extract_generic_fields`, don't re-attempt without reading it first.
  Entered manually instead, verified against the document's own combined
  totals: Scope 1 (80,650) + Scope 2 location (112,921) = 193,571 matches
  the stated "Total Scope 1 + 2 (Location-Based)" exactly, and 80,650 +
  Scope 2 market (116,285) = 196,935 matches the stated market-based total
  exactly.
- **Research leads surfaced by the user, checked and mostly ruled out**:
  (1) Harvard Law Forum "Corporate Climate Disclosures" article — narrative
  only, cites aggregate stats from The Conference Board's paid ESGAUGE
  platform, no per-company data. (2) S&P Global Marketplace's Trucost
  Environmental dataset — real company-level Scope 1/2/3 data exists but
  it's a paid/licensed institutional product, not accessible without a
  subscription. (3) `filofossati/NetZeroEmissionCommitment` GitHub repo —
  a research/ML project (net-zero-commitment prediction), not a raw
  dataset; underlying emissions data (from paid provider Entelligent) not
  included, companies anonymized in the public repo. (4) HuggingFace
  `danielrosehill/GHG-Emissions-Data` — explicitly LLM-derived and
  **not human-verified** (`human_verified: 0`), only 78 companies; skip it,
  using unverified LLM-generated numbers as ground truth would undercut
  the whole Integrity pillar. **(5) Worth a real look next**: Lynn
  LoPucki's Stakeholder Takeover Project
  (stakeholdertakeover.org/rankings/2020, and a 2021 version) ranks ALL
  S&P 500 companies by Scope 1+2 emissions ÷ revenue, sourced from
  voluntary GHG reports plus mandatory EPA data — real academic project,
  full S&P 500 coverage, exactly the kind of source this pipeline wants.
  The site is a JS-rendered SPA, so WebFetch only sees an empty shell —
  needs an actual browser (or view-source / network-tab inspection) to
  get at the underlying table data. Not yet integrated; flagging for
  whoever picks this up next.
- **EPA GHGRP saved 16 searches this session**: batch_07 had matches for
  LMT, L, MPC, MLM; batch_08 had matches for MRK, MGM, MCHP, MU, TAP, NEM,
  NI, NOC, NRG, NUE, OXY, OKE. All entered directly with real Scope 1
  figures, zero WebSearch cost.
- **New parser fallback added and verified** (`extract_emissions.py`,
  `mtco2e_labels` in `extract_generic_fields`): some "Key data and
  frameworks" tables abbreviate the unit to `(MTCO2e)` in the row label
  itself instead of spelling out "metric tons CO2e" — confirmed real case:
  Lam Research (LRCX). Caught a real ambiguity while adding this: Incyte
  (INCY) uses the identical `(MTCO2e)` label style but an oldest-year-first
  table, where naively taking the first number after the label would have
  silently grabbed 2019's figure instead of 2024's. Used
  `_last_of_number_run` instead of `_first_number_after` specifically
  because it resolves both conventions correctly (Lam Research's table
  still degenerates to one number since a "-52%" YoY line isn't numeric).
  Verified zero regressions via `rescan_all_cached.py` before trusting it.
- **One manual (non-generalizable) entry this session**: Nike (NKE) — its
  FY24 Sustainability Data report breaks emissions out by facility type
  (Air MI/Distribution/HQs/Retail/Corporate Jets/HQ Fleet) rather than a
  single labelled Scope 1/2 row, so not a parser-worthy pattern. Entered
  manually after cross-verifying the NIKE, Inc. totals across three
  independent tables in the same document (an explicit "FY24 Emissions
  Summary" table, the "Energy and Emissions by Business Function" table,
  and the "Fuel/Electricity Consumption" tables) — all agreed exactly:
  Scope 1 = 57,390, Scope 2 location-based = 211,322, market-based =
  12,120 tCO2e.
- Also noted, not fixed: `extract_emissions.py`'s `is_new_cdp` detection
  has a false-positive path — it flags a document as CDP-format on a bare
  mention of the phrase "CDP Corporate Questionnaire" anywhere in the
  text, which fired on LRCX's report (a GRI index citing "the 2024 CDP
  Corporate Questionnaire, Section C7" as a cross-reference, not an actual
  CDP export). Harmless here since `data_source` is set by the caller
  argument, not by this detection, and the true CDP-format extractors
  found nothing to conflict with — but the `is_cdp_format` column will
  read "new" on that row despite the document not actually being one.
  Not worth tightening without a second confirmed case, since the fix
  risks breaking legitimately-detected CDP PDFs whose title doesn't
  literally contain "CDP Corporate Questionnaire".
- Two more manual (non-generalizable) extractions this session, both
  cross-checked before entry rather than parser-automated: J.B. Hunt
  (current-year-first table with a footnote digit stuck to the label,
  opposite convention from other companies seen — automating risks wrong
  year elsewhere) and JPMorgan Chase (mixed table layouts in one PDF,
  verified via the document's own combined-total consistency check:
  100,024 + 6,806 = 106,830 matched exactly).
- **New root-level files discovered this session, not yet integrated,
  worth a look next**: `cdp_global500_2013.csv` (real 2013 CDP Scope 1/2
  data, ~500 global companies, **63 exact-ticker matches against our
  current gap** — Costco, AT&T, Allstate, JPMorgan, Target, ADP, Dollar
  General among them) and a smaller `cdp_industry_emission_ranking.csv`
  (35 companies, Food & Beverage sector, same 2013 vintage) — plan is to
  fold both in as a `data_source=cdp_2013_historical` tier, clearly aged.
  Also present but lower priority: `wikirate_coverage.csv` (a coverage
  audit only, no actual values, 31 tickers/1 year — low yield for the
  effort) and `environmental_data_clean.csv` / `preprocessed_content.csv`
  (the NLP-derived e/s/g **score** dataset from CLAUDE.md, 263 companies
  2014-2023 — a different pillar's input, not raw Scope 1/2 tonnage; ~2%
  of its rows are non-US-exchange tickers that collide with S&P 500
  symbols, e.g. ASX-listed "BSX" ≠ Boston Scientific — filter by exchange
  prefix before using).
- Checked several third-party aggregator platforms this session (CDP's
  own scores page, S&P Global CSA, Mycelium) as possible shortcuts to
  full coverage — none pan out; see git history / conversation for why
  (composite scores not raw emissions, or in Mycelium's case a confirmed
  wrong-entity risk: its "Apple" record was a small UK subsidiary, not
  the global parent). Not worth re-investigating without new information.
- **EPA GHGRP backfill** (`epa_ghgrp/`, see section above): real,
  government-reported Scope-1-only data used whenever CDP/sustainability-
  report search comes up empty. Check `epa_ghgrp/epa_ghgrp_matches.csv`
  before every `mark_not_found.py` call — saves a search AND gives real
  data instead of "not found." ~40 more not-yet-attempted tickers already
  have a match waiting.
- **Parser fixes this session** (each verified via `rescan_all_cached.py`
  against every cached PDF, zero regressions): new CDP 2025-cycle "Q7.6"
  question-marker format (no parentheses) — recovered FedEx; generic
  "Scope N GHG emissions: NUMBER metric tons CO2e" inline-colon pattern —
  recovered Humana. One attempted fix (loose Scope 2 table matching) was
  tested and reverted after it produced wrong data on other companies —
  see the inline comment in `extract_generic_fields`, don't re-attempt
  without reading it first.
- Two teammate-facing notes: (1) if a teammate runs a parallel session on
  a different batch, tell them to check the EPA lookup file too before
  marking anything not-found. (2) EPA parent-company name matching is
  exact-normalized only (no fuzzy matching) by design — a few real
  matches are missed by spacing/punctuation quirks (e.g. "ExxonMobil" vs
  EPA's "Exxon Mobil"); worth a manual glance at near-misses for large
  companies specifically, not worth automating further given the false-
  positive risk.
- **batch_09/10/11 completion pass, same session**: EPA GHGRP backfilled
  7 more tickers in batch_09/10 combined (RTX, RSG, SWKS, SO, STLD, TRGP,
  TSLA, TXN, TXT, TMO, TSN — some already counted above). Two more manual,
  cross-verified entries for one-off table layouts: Salesforce (CRM) —
  figures stated in thousands with the column header trailing the data in
  extraction order, verified via 6+293+1,155=1,454 (thousand tCO2e)
  matching the document's own "Total absolute emissions" row exactly —
  and J.M. Smucker (SJM) — an assurance-letter "Exhibit A" schedule,
  verified via 165,414+176,567=341,981 and 165,414+629=166,043 both
  matching the document's own stated LBM/MBM totals exactly. Teledyne
  (TDY) also entered manually after a label collision risk (a decoy
  "...Total Emissions from Perfluorinated Compounds (PFCs)" row shares
  the same label prefix as the real Scope 1 total) — took the first
  occurrence, verified via 58,970+51,971=110,941 matching the stated
  Scope 1+2 total exactly.

## What's next (once real-data collection is genuinely finished)

This file's original purpose — coordinating fresh sessions through an
in-progress WebSearch-limited collection effort — is done; every S&P 500
ticker has a real attempt behind it. Picking this up again means one of:

1. **Tier 2 sector-median estimation** for the ~124 `none` tickers, per
   "The bigger open question" section above — the confirmed next step,
   not yet built.
2. **Folding in the leads noted in this file but not yet integrated**:
   the `cdp_global500_2013.csv` / `cdp_industry_emission_ranking.csv`
   historical data (see the note above), and Lynn LoPucki's Stakeholder
   Takeover Project (full S&P 500 Scope 1+2/revenue rankings — real,
   free, but needs an actual browser session to extract since it's a
   JS-rendered SPA that WebFetch can't read).
3. **Using `data/environmental_combined.csv`** (Level + SBTi Velocity
   input already joined — see the SBTi section above) as the actual input
   to build `level_score`/`velocity_score`/`integrity_score`, which is a
   separate piece of work this pipeline was never scoped to do (see "What
   this is actually for" near the top).
4. **A periodic re-check**, if the constituent list or a company's
   disclosure status changes materially before the deliverable is due —
   this file's exact-match, no-fabrication conventions still apply.
