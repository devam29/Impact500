# Emissions data collection pipeline — briefing for a new session

If you are a fresh Claude Code session picking this up: read this whole file
before doing anything. It exists because the WebSearch budget is capped
*per session* (see "Why sessions keep restarting" below), so this project
gets worked on across many short-lived sessions, and each one needs the
same context the last one had.

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
data publicly. The current plan (confirmed with the user) for the final
deliverable, once collection is as complete as it's going to get:

- **Tier 1 — verified**: `data_source` = `cdp_pdf` or
  `sustainability_report`, real extracted figures.
- **Tier 2 — estimated, clearly flagged**: for tickers with
  `data_source=none`, impute a Level-score input from sector-median
  emissions intensity (tCO2e / $ revenue, computed from Tier 1 companies
  in the same GICS sector) × that company's own revenue. Tag these rows
  `data_source=sector_median_estimate` so they are never presented as
  equivalent to real disclosure.

This estimation step hasn't been built yet — it's future work for once
real-data collection has run its course, not something to do instead of
searching. Keep searching for real data first; only fall back to Tier 2
for whatever's left after all 11 batches are genuinely attempted.

## Current status (as of 2026-09-12, this update)

- Batches 04, 05, and 06 are now fully attempted (150 companies).
  Remaining: batch_07 through batch_11 (~249 companies), untouched.
- Master file: `data/environmental_emissions_master.csv`, **254
  companies, 118 with real usable data** (cdp_pdf 84, sustainability_report
  62, epa_ghgrp 37 — some overlap since epa_ghgrp only fills the gap when
  the other two found nothing; 71 confirmed no public disclosure).
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
