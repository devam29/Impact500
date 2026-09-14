# Impact 500

*Impact 500* is a data-driven framework for scoring, ranking, and
exploring S&P 500 companies on sustainability. It has two parts: a web
app for browsing and comparing companies, and an **Environmental
Sustainability** scoring pipeline (real emissions data, gap-filled and
scored end to end). This README explains how the pieces fit together
and where to find the detail on each.

## What's in this repository

| Part | Where | What it is |
|---|---|---|
| **Web app** | `src/` | The SvelteKit application: a ranked, searchable, filterable company list with drag-and-drop side-by-side comparison. |
| **Upright Net Impact data** | `src/upright_metrics/`, `data/upright_final_esg.json` | A monetized cost/benefit dataset (Environment, Health, Knowledge, Society categories) currently powering the web app's ranking. |
| **Environmental Sustainability pillar** | `pipeline/`, `data/`, `docs/` | A full pipeline: real emissions disclosures extracted from CDP/sustainability report PDFs, gap-filled with a documented peer-estimation methodology, merged with the Upright data, and scored into Level/Velocity/Integrity plus one composite score per company. See **[`ENVIRONMENTAL_PILLAR_README.md`](ENVIRONMENTAL_PILLAR_README.md)** for the full writeup, or [`docs/SCORE_METHODOLOGY.md`](docs/SCORE_METHODOLOGY.md) for every formula. |

## Sustainability, defined

Rather than a single static carbon-intensity number, the Environmental
pillar's score is built from three independently-measured factors,
combined into one `environmental_composite_score` per company:

- **Level** — current emissions burden, benchmarked only against
  companies in the same industry.
- **Velocity** — pace of decarbonization against a real,
  published science-based pathway (SBTi's Absolute Contraction
  Approach), not just a stated ambition.
- **Integrity** — how trustworthy the underlying number is, checked
  wherever possible against something independent of the company's own
  disclosure.

Real disclosures were extracted directly from 250+ companies' CDP
climate questionnaires and sustainability reports, supplemented with
government (EPA GHGRP), third-party validation (SBTi), and
satellite-based (Climate TRACE) data. Every company still missing a real
figure is filled in using a documented, industry-standard peer
estimation methodology (modeled on LSEG's published carbon-estimate
approach) rather than left blank or guessed — and every estimated value
is explicitly flagged, never presented as equivalent to a real
disclosure. Full detail, every formula, and the literature each piece is
based on: **[`ENVIRONMENTAL_PILLAR_README.md`](ENVIRONMENTAL_PILLAR_README.md)**.

## The web app

A ranked list of companies (search + rank by category), a
drag-and-drop comparison view (drop any two companies side by side to
compare their category cost/benefit breakdown), and a per-company detail
view. Currently ranks by the Upright dataset's own Net Impact categories
(Overall / Society / Knowledge / Health / Environment). The
Environmental Sustainability pillar's own data
(`data/sp500_metrics.json` — CO2, SBTi, Climate TRACE, and the full
Level/Velocity/Integrity score per company) is merged into this
repository's data directory and ready to wire into the same ranking and
comparison components as a further ranking metric.

## The bonus question

The challenge's bonus question — *"the world commits to net-zero
tomorrow, allocate a $1B fund"* — is answered quantitatively using this
project's own computed scores (not just theory), with real company
examples and a chart: **[`docs/BONUS_QUESTION.md`](docs/BONUS_QUESTION.md)**.

## Further reading

- [`ENVIRONMENTAL_PILLAR_README.md`](ENVIRONMENTAL_PILLAR_README.md) — the Environmental pillar's own overview and pipeline walkthrough.
- [`docs/SCORE_METHODOLOGY.md`](docs/SCORE_METHODOLOGY.md) — every scoring formula, worked examples, and literature citations.
- [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) — every column in every data file.
- [`docs/UPRIGHT_DATA_VERIFICATION.md`](docs/UPRIGHT_DATA_VERIFICATION.md) — independent verification of which S&P 500 company list is current.
- [`docs/RESEARCH_LOG.md`](docs/RESEARCH_LOG.md) and [`research/rejected_sources/`](research/rejected_sources/) — data sources investigated and rejected, with the evidence kept.
- [`pipeline/README.md`](pipeline/README.md) — technical reference for every pipeline stage.
