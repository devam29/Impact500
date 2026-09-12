# Environmental Sustainability Pillar — Working Notes

Status as of this session. Covers: approach confirmation, judging-rubric mapping, CSV audit + cleaning results, finalized indicator list, and open blockers. No scoring code written yet.

---

## 1. Confirmed approach

**Environmental Sustainability = Level + Velocity + Integrity** (not a single static score).

- **Level** — current emissions burden, sector-relative (GICS z-score). Necessary baseline, not the differentiator — most competing teams will stop here.
- **Velocity** — the actual differentiator: is the company's own historical trend closing fast enough against a real benchmark (SBTi Absolute Contraction Approach, **−4.2%/yr** required linear reduction, Scope 1+2, to stay 1.5°C-aligned)? Operationalizes the "fast enough" clause in our own sustainability definition.
- **Integrity** — trust layer: cross-check self-reported numbers against independent evidence. Flags companies that look good on Level+Velocity but have a credibility gap, instead of rewarding them.

**Differentiation vs. the field:**

| Precedent | Covers | Gap we close |
|---|---|---|
| TPI | Velocity-only, high-impact sectors | No verification layer |
| MSCI Implied Temp Rise | Level+Velocity compressed | Proprietary, not reproducible |
| Climate TRACE | Integrity-only (satellite) | Doesn't score trajectory-vs-pathway |
| CDP scores | Level (disclosure quality) | Full data now paywalled |

No one combines self-reported + independently-verified + pathway-benchmarked-trend into one transparent, reproducible score. That combination is the pitch.

**Pillar boundary:** this section is strictly backward-looking, realized-outcomes only. Green capex/R&D intent = teammate's Transition Readiness. Balance-sheet durability = teammate's Economic Resilience.

**Hard scope constraint:** every company in any output must be a verified, *current* S&P 500 constituent — not just a ticker-string match.

---

## 2. Judging rubric → what it demands of this pillar

| Criterion (0–5) | What it means for Level/Velocity/Integrity |
|---|---|
| **Innovation** | Earned by the L+V+I *combination*, not any single piece — Level alone is table stakes. The competitive-landscape table above is the evidence for "would a team have arrived here without thinking hard." |
| **Technical Execution** | Harshest constraint on this pillar — Integrity requires joining 2–3 heterogeneous data sources under a 2-day limit. Design has to be realistic, not ambitious. |
| **Feasibility** | Public/free data only; plan for partial coverage explicitly rather than assuming it away (esp. satellite matching, which is a hard entity-resolution problem even for well-funded teams). |
| **Impact** | Velocity = forward transition-risk signal, Integrity = greenwashing filter. Concrete "who benefits" story, ties directly into the bonus net-zero portfolio question. |
| **Presentation** | Explicitly rewards being honest about limitations — every coverage gap below is a talking point, not something to hide. |

---

## 3. CSV audit — `preprocessed_content.csv`

**Structure:** 866 rows, 263 unique tickers. Columns: `filename, ticker, year, preprocessed_content, ner_entities, e_score, s_score, g_score, total_score`. No nulls.

**Finding 1 — ticker collisions (confirmed by reading actual report content, not just the ticker string).** `filename` encodes source exchange: NYSE 576, NASDAQ 274, TSX 5, LSE 4, OTC 4, ASX 3. Of the 16 non-NYSE/NASDAQ rows, verified content for 7 distinct tickers:

| Ticker (tagged exchange) | Real company under that tag | Actual S&P 500 company it collides with |
|---|---|---|
| BSX (ASX) | Blackstone Minerals (AU nickel miner) | Boston Scientific |
| EXR (ASX) | Elixir Energy (AU/Mongolia gas explorer) | Extra Space Storage |
| ADM (LSE) | Admiral Group (UK insurer) | Archer-Daniels-Midland |
| ABT (TSX) | Absolute Software (CA cybersecurity) | Abbott Labs |
| EFX (TSX) | Enerflex (CA energy infra) | Equifax |
| MSI (TSX) | Morneau Shepell (CA HR) | Motorola Solutions |
| BBY (LSE) | Unidentified UK filer (generic template text) | Best Buy — likely collision, lower confidence |
| CHTR (OTC) | **Genuine Charter Communications** — content confirms real match despite mislabeled exchange tag | — kept |

Of the 7 collision tickers, only **ABT** had legitimate NYSE-tagged rows elsewhere (2019–2021) — so Abbott survives with real data. The other 6 (BSX, EXR, ADM, EFX, MSI, BBY) have **zero valid rows** once the imposters are removed.

**Finding 2 — year coverage thinner than the "2014–2023" framing suggested.**

| Years of data per ticker | # tickers |
|---|---|
| 1 | 16 |
| 2 | 19 |
| 3 | 101 |
| 4 | 126 |
| 5 | 1 |

Real volume sits in 2019–2022 (607 of 866 rows); 2014–2017 combined = 13 rows; 2023 = 19. Effectively a 2018–2022 window, 3–4 points per company for most, 1–2 for 35 tickers — too thin for a reliable CAGR without a floor.

**Finding 3 — e/s/g/total_score are text-derived, not physical measurements.** No documented methodology in the file itself; these scores reflect how a report *talks about* ESG topics (keyword/entity density or similar), not measured tCO2e, energy, or water use. Confirmed by inspecting `ner_entities` — noisy NER output (locations, dates, ordinal-number artifacts), not a clean structured feature set.

**Cleaning performed:**
- Dropped 12 rows confirmed as ticker collisions (table above, excluding CHTR which was verified genuine).
- Result: 866 → 854 rows, 263 → 257 unique tickers.
- Saved to `environmental_data_clean.csv` in the project root.

---

## 4. Decision: NLP dataset shelved for scoring

**Call made this session:** don't use `e_score`/`s_score`/`total_score` as inputs to Level, Velocity, or Integrity. Reasoning — text-derived (not measured), incomplete coverage (257/503 even after cleaning), and doesn't meet the bar of "trustworthy and covers everything" needed for a scoring pillar built around trust.

**Consequence:** the disclosure-consistency idea for Integrity's universal fallback (which was going to be built from this dataset's text) is also out. Replaced — see §5.

---

## 5. Finalized indicator list (dataset-independent)

### Level — current burden, sector z-scored
- **Primary:** Scope 1+2 GHG emissions intensity (tCO2e / $M revenue)
- **Secondary, flagged not core:** Scope 3 intensity, where disclosed
- **Needs:** Scope 1/2 tonnage + revenue + GICS sector, per company — not present in the audited CSV

### Velocity — rate vs. pathway
- CAGR of **absolute** Scope 1+2 emissions (not intensity — SBTi's ACA target is on absolute tons; an intensity metric is gameable by revenue growth alone) vs. required **−4.2%/yr**
- Hard floor: ≥3 consecutive years of data to compute a trend; below that, flag and exclude rather than force a number
- **Needs:** same multi-year absolute-emissions series as Level, same source, for internal consistency

### Integrity — trust layer, two components
1. **Satellite cross-check** (Climate TRACE) where facility-level coverage exists — power, oil & gas, cement, steel, etc. The actual novelty claim; partial coverage by design.
2. **Self-consistency check** on the reported time series itself (same data as Velocity) — flags implausible jumps/drops with no disclosed cause. Universal coverage, no new data source needed — reuses what Level/Velocity already require.
- Composite Integrity score explicitly labeled by which sub-check backed it per company — never mixed silently.

---

## 6. S&P 500 constituent list + sector mapping — DONE

Fetched live from Wikipedia, verified (not from memory — caught a real ticker rename, MMC→MRSH, via web search cross-check rather than assuming a parser bug). Saved to `sp500_constituents.csv`: 503 rows, columns `Symbol, Security, GICS Sector, GICS Sub-Industry, Headquarters Location, Date added, CIK, Founded`. No duplicates. Sector counts: Industrials 83, Financials 76, Info Tech 73, Health Care 59, Consumer Discretionary 47, Consumer Staples 34, Utilities 31, Real Estate 30, Materials 25, Communication Services 24, Energy 21.

Cross-checked the shelved NLP dataset's 257 tickers against this list: only 233 are current constituents — 24 are stale (left the index since 2018–2022, e.g. ANSS/Ansys, likely absorbed into Synopsys). Second, independent reason that dataset wasn't fit to build on.

---

## 7. Emissions data sourcing — extensive search results

Every candidate checked, with real access verification (not just search-summary trust):

| Source | Access | Coverage/currency | Verdict |
|---|---|---|---|
| **CDP direct (licensed)** | Paid license for comprehensive data | High | Access-blocked |
| **CDP Open Data Portal (free)** | Free, no login, real CSV export confirmed working (`data.cdp.net`, dataset `marp-zazk`, "2013 Global 500 Emissions") | 501 companies, **single year: 2013**, `data_updated_at: 2016-06-01` | ❌ Rejected — stale |
| **Wikirate** (CDP republished) | Free, public REST API, verified working, CIK-cross-referenced against real submissions | Full 503-ticker check run: see below | ❌ Rejected — stale (see below) |
| **EPA GHGRP** | Free, official, no clean API | US industrial facilities only | Structural gap — supplement only, not checked further |
| **Carbon Majors** | CSV download links exist but gated behind a Terms & Conditions consent flow (direct link returns an HTML page, not the file) | 178 companies globally, fossil fuel/cement only | Access friction + narrow scope — not pursued |
| **SBTi target dashboard** | Free `.xlsx`, no login | 14,000+ companies, target *status* only | Not emissions data — usable later as a Velocity-eligibility flag |
| **Climate TRACE** | Free, public API + CSV | Ownership data: 32% of global emissions (full) + 14% (partial) across 18 point-source subsectors | ✅ Confirmed usable for Integrity |
| **SEC EDGAR XBRL company-facts** | Free, official, no key, keyed by CIK (already have it) | All US public companies | ✅ Confirmed usable for revenue (Level's intensity denominator) |
| **Kaggle "S&P 500 ESG and Stocks Data 2023-24"**, **"Public Company ESG Ratings Dataset"** | Kaggle pages are JS-rendered SPAs — not inspectable via fetch tools without an account/API token | Unknown | Untested — blocked by tooling, not confirmed bad |
| **Company reports directly** (via `responsibilityreports.com`, `sustainabilityreports.com`) | Free, no login. Spot-checked Apple (38 reports, 2006–2025) and ExxonMobil (2024 report, issued 2026, explicit Scope 1+2 = 98M tonnes CO2e) | Current — 2024/2025 data confirmed for large caps | ✅ **Primary path going forward** |

### Wikirate full 503-ticker check — result

Ran twice: first attempt (10 parallel workers) tripped Wikirate's rate limit (`HTTP 429`) and silently misreported 0% coverage — caught before reporting it as a finding, not a real result. Re-ran single-threaded with proper backoff; confirmed via direct API queries (e.g. `CDP+Scope_1_Emissions+Abbott_Laboratories+2014.json` → real value, 471,000 tonnes, sourced from an actual CDP submission file) that the underlying data is genuine, just old. Companies checked so far (3M, Abbott) show exactly **one year each: 2014**. Full run left going in the background for the record but **not used** — decision made not to build on data this stale regardless of final coverage %.

### Decision: Wikirate and CDP's free/open data both rejected — too old

Both free CDP-sourced routes independently bottom out in the same 2013–2016 window. Not a search problem — the free/open CDP data ecosystem as a whole is frozen there; current data requires a paid license. Confirms company-report extraction is the **only** free route to genuinely current (2022–2025) numbers.

---

## 8. Current plan: direct company report extraction

- **Where to find reports:** `responsibilityreports.com` (26,000+ reports, 4,488 companies) and `sustainabilityreports.com` (335,000+ reports, 50,000+ companies, filterable) — both free, both confirmed to have current-year reports for large caps.
- **Why this is more tractable than it sounds:** large companies (the ones that matter most for portfolio weight too) tend to publish dedicated "metrics & data" pages, not just PDFs — e.g. ExxonMobil's `corporate.exxonmobil.com/publications/metrics-and-data`. Extraction risk is concentrated in smaller/mid-cap names with less structured disclosure.
- **Scope decision:** targeted subset first (not all 503 at once) — prove extraction accuracy on a manageable batch, then decide whether to scale with remaining time. Full 503 coverage is not assumed or promised.
- **Next concrete step:** build a small extraction test (~10 companies across sectors) to confirm we can reliably pull a real Scope 1/2 figure + multi-year trend before committing further build time.

---

## 9. Open items

1. **257-ticker cleaned NLP CSV cross-check — done** (§6): 233/257 are current constituents. Dataset remains shelved regardless (see §4).
2. **BBY/LSE collision — lower confidence, single-row sample.** Worth a second look if it ends up mattering.
3. **Kaggle datasets — still unverified**, blocked by tooling access, not yet a ruled-out option.
4. **Report-extraction accuracy — unproven at scale.** Apple/ExxonMobil spot checks are promising but n=2; the ~10-company test batch is the next real test.
