# S&P 500 Environmental Sustainability Score

A data-driven score for how sustainable each S&P 500 company actually
is on the environmental dimension — built from real company disclosures,
government emissions data, and independent third-party sources, with
every gap in that data filled by a documented estimate instead of left
blank or guessed at.

This is the **Environmental** pillar of a larger team submission (the
other two pillars — Transition Readiness and Economic Resilience — are
separate teammates' work and live elsewhere).

## The three questions this score actually answers

A company's total pollution number on its own doesn't say much — a bank
will always look "cleaner" than an oil company regardless of how well
either is actually run. So instead of one static number, every company
gets three independent scores:

1. **Level** — how clean is this company *right now*, compared only to
   other companies in its own industry, not the whole market.
2. **Velocity** — is this company *actually getting cleaner*, and fast
   enough to matter, benchmarked against the pace climate science says
   is required (not just "does it have a nice-sounding pledge").
3. **Integrity** — can the number be trusted, checked against
   independent evidence rather than taken purely on the company's own
   word.

These three are averaged into one final `environmental_composite_score`.
The full reasoning and every formula — including a plain-language
walkthrough with real company examples — is in
[`docs/SCORE_METHODOLOGY.md`](docs/SCORE_METHODOLOGY.md).

## How the pipeline flows

Each stage lives in its own `pipeline/` subfolder and produces a real,
inspectable intermediate file. Nothing is fabricated at any stage — a
value that couldn't be found or verified is left blank and flagged,
never guessed.

| Stage | Folder | What it does |
|---|---|---|
| 1. Report extraction | [`pipeline/pdf_extraction/`](pipeline/pdf_extraction/) | Finds and parses each company's real CDP climate disclosure or sustainability report for Scope 1/2 emissions. |
| 2. Supplemental sources | [`pipeline/epa_ghgrp/`](pipeline/epa_ghgrp/), [`pipeline/sbti/`](pipeline/sbti/), [`pipeline/climate_trace/`](pipeline/climate_trace/) | Fills in more real data from a US government emissions registry, a third-party climate-target validator, and satellite-based asset ownership data. |
| 3. Gap-filling (CO2) | [`pipeline/tier2_estimation/`](pipeline/tier2_estimation/) | For any company still missing a real Scope 1 or Scope 2 figure, estimates it from real peer companies' data using a published industry methodology (see `docs/references/`). |
| 4. Teammate data merge | [`pipeline/upright/`](pipeline/upright/) | Merges in an independently-collected teammate dataset and fills its remaining gaps the same way. |
| 5. Scoring | [`pipeline/scoring/`](pipeline/scoring/) | Computes Level, Velocity, Integrity, and the final composite score. |
| 6. Website export | `pipeline/build_website_json.py` | Packages everything into one JSON file for a website to consume. |

See [`pipeline/README.md`](pipeline/README.md) for the full technical
detail on every stage — the exact parser logic, every manually-verified
edge case, and how to re-run any part of it.

## The outputs

- **[`data/environmental_scores.csv`](data/environmental_scores.csv)** —
  the final score, one row per company, sorted best to worst. Start here
  if you just want the ranking.
- **[`data/sp500_metrics.json`](data/sp500_metrics.json)** — everything
  (raw emissions data, SBTi/Climate TRACE/Upright data, and the scores)
  in one JSON file, shaped for a website.
- **[`data/environmental_combined.csv`](data/environmental_combined.csv)** —
  every raw input the score was built from, if you want to inspect or
  recompute anything yourself.

Every column in every one of these is documented in
[`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md).

## Real data vs. estimated data

Roughly half of the S&P 500 doesn't publish a usable Scope 1/2 emissions
figure anywhere public. Rather than exclude those companies or leave
them blank, this project estimates their figures from real peer-company
data, using the same industry-standard methodology (LSEG's published
carbon-estimate model) a real financial data provider uses for the same
problem — and **every single estimated value is flagged**, never mixed
in silently with a real one:

- `scope1_is_estimated` / `scope2_is_estimated` — is this specific
  emissions figure real or estimated.
- `velocity_basis` — was Velocity computed from a real measured trend or
  from a target-ambition proxy.
- `integrity_basis` — did Integrity get a real independent cross-check
  or fall back to disclosure quality alone.
- `upright.is_estimated` — is a company's Upright-sourced data real or
  our own peer-median proxy.

If you're building anything on top of this data (a chart, a ranking, a
color-coded table), key any visual distinction off these flags — a real
number and an estimate should never look the same.

## Reproducing this

```
py -m pip install pymupdf requests openpyxl yfinance

py pipeline/pdf_extraction/merge_batches.py
py pipeline/tier2_estimation/fetch_financials.py
py pipeline/tier2_estimation/estimate_tier2.py
py pipeline/upright/match_upright.py
py pipeline/upright/estimate_upright_gaps.py
py pipeline/build_combined_dataset.py
py pipeline/scoring/compute_environmental_scores.py
py pipeline/build_website_json.py
```

## Further reading

- [`docs/SCORE_METHODOLOGY.md`](docs/SCORE_METHODOLOGY.md) — every
  formula, worked examples with real companies, and exactly which parts
  are backed by a published external methodology (MSCI, SBTi, CDP) vs.
  our own judgment calls, stated plainly.
- [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) — every column in
  every output file.
- [`docs/UPRIGHT_DATA_VERIFICATION.md`](docs/UPRIGHT_DATA_VERIFICATION.md) —
  an independent, third-party verification of which S&P 500 company list
  is actually current, resolving a real disagreement between two team
  datasets.
- [`docs/RESEARCH_LOG.md`](docs/RESEARCH_LOG.md) — why several
  free/public emissions datasets (2013-era CDP exports, an NLP-derived
  ESG dataset) were investigated and rejected before this pipeline was
  built. The rejected sources themselves are kept in
  [`research/rejected_sources/`](research/rejected_sources/) for anyone
  who wants to check that reasoning against the actual data.
- [`pipeline/README.md`](pipeline/README.md) — the technical reference
  for every pipeline stage.
