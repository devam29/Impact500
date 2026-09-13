# Rejected data sources

Before building the PDF/report-extraction pipeline in `pipeline/pdf_extraction/`,
several free emissions data sources were tried first and rejected for
concrete, checked reasons — not assumed bad, actually queried and
inspected. The full write-up (including the judging-rubric reasoning and
the finalized Level/Velocity/Integrity indicator list this investigation
led to) is in `docs/RESEARCH_LOG.md`. This folder keeps the actual
evidence files behind that write-up, so the "why" is checkable, not just
asserted.

None of these files are read by any script in `pipeline/`. They're kept
for provenance only.

| File | What it is | Why it wasn't used |
|---|---|---|
| `cdp_global500_2013.csv` | CDP's free Open Data Portal export, "2013 Global 500 Emissions" (`data.cdp.net`, dataset `marp-zazk`) | Single year, 2013, `data_updated_at: 2016-06-01`. Confirmed via the portal's own metadata, not assumed — the free CDP data ecosystem bottoms out here regardless of query. |
| `cdp_industry_emission_ranking.csv` | A smaller CDP-derived industry ranking export, same 2013 vintage | Same staleness problem as above. |
| `wikirate_coverage.csv` | Full 503-ticker coverage check against Wikirate's public API (which republishes CDP submissions) | Verified real (e.g. Abbott Laboratories' 2014 Scope 1 figure traced to an actual CDP submission file), but every company checked bottomed out at **2014** — one year, over a decade old. Confirms the staleness is structural to free/open CDP-sourced data, not a Wikirate-specific gap. |
| `preprocessed_content.csv` | An NLP-derived ESG dataset: 866 rows, 263 tickers, with `e_score`/`s_score`/`g_score`/`total_score` columns | Two independent problems, both confirmed by inspection: (1) the scores are text-derived (keyword/entity density from report prose), not measured tCO2e/energy/water figures — confirmed by inspecting the raw `ner_entities` output; (2) 12 rows were ticker collisions with non-US, non-S&P-500 companies sharing a ticker string (e.g. `BSX` tagged ASX = an Australian nickel miner, not Boston Scientific) — real content was checked per row, not just the ticker text. |
| `environmental_data_clean.csv` | `preprocessed_content.csv` after removing the 12 confirmed ticker collisions (866→854 rows, 263→257 tickers) | Still shelved even after cleaning — the underlying scores are still text-derived, and a second independent check found only 233 of the 257 tickers are still current S&P 500 constituents (24 left the index since the data was collected). |
| `IlhanSautnerVilkovRFS2021_data.xlsx` | Public replication data from Ilhan, Sautner & Vilkov (2021), *Review of Financial Studies* — an academic paper on climate risk disclosure | Reviewed as a candidate reference dataset; not company-level current emissions data, so not usable as a Level/Velocity input. |
| `sp_esg_stock_data.csv` | A general public S&P 500 ESG/stock dataset | Reviewed as a candidate; didn't provide current, verifiable Scope 1/2 emissions figures at the granularity this project needed. |

**The actual conclusion this investigation led to**: every free/open route to
CDP-sourced emissions data converges on the same 2013–2016 window — this
isn't one bad source, it's a property of the free data ecosystem as a
whole. The only route to genuinely current (2022–2025) figures turned out
to be extracting them directly from companies' own published CDP
responses and sustainability reports, which is what
`pipeline/pdf_extraction/` does.
