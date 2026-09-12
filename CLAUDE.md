# S&P 500 Environmental Sustainability — Hackathon Project

## Competition context
[FILL IN: hackathon name, deadline, team size, submission format]

## The challenge question (verbatim)
> Build a data-driven framework to quantify and compare the sustainability of companies in the S&P 500. How you approach the problem is up to you. Define what sustainability means, identify and justify the most relevant indicators, source the necessary data, and develop a methodology to score, rank, or compare companies. Your solution may incorporate environmental, financial, operational, or other dimensions you consider relevant.
>
> Bonus question: Tomorrow, the world commits to reaching net-zero emissions as fast as possible. You manage a $1 billion investment fund. How do you allocate your portfolio under this new scenario, and why?
>
> We expect you to choose your own dataset, justify your choice, and show how it is suitable for the challenge.

## Scoring criteria
[FILL IN: paste the judges' scoring rubric here — e.g. weighting across methodology rigor, data justification, novelty, presentation, bonus question]

## Our team's approach
Agreed definition:
> Sustainability = a company's ability to continue creating economic value while reducing its environmental burden fast enough to operate in a net-zero economy.

Three pillars, owned separately by team members, merged at the end into one ranking:
1. **Environmental Sustainability** — my section, this workspace.
2. **Transition Readiness** — teammate's section (forward-looking capacity: green capex, R&D, energy pipeline).
3. **Economic Resilience** — teammate's section (balance sheet durability: FCF, debt capacity, margin).

Final deliverable: one `ticker`-keyed score per pillar, merged into a single S&P 500 ranking.

## My section: Environmental Sustainability = Level + Velocity + Integrity
Deliberately NOT a static carbon-intensity score — most competing teams will build that and stop. The word "fast enough" in our own definition is a rate claim, not a level claim.

- **Level** — current environmental burden, sector-relative (an oil major vs. a bank is an unfair comparison on raw numbers).
- **Velocity** — is the company decarbonizing fast enough, benchmarked against a real science-based pathway (SBTi's Absolute Contraction Approach).
- **Integrity** — is the self-reported number trustworthy, cross-checked against independent satellite-based emissions estimates.

Full reasoning and methodology detail live in the `environmental-thinking` skill — invoke it (or let it trigger automatically) for any strategy, indicator-selection, or scoring-design conversation.

## Hard scope constraint
Every company in any output MUST be a current, real S&P 500 constituent, cross-checked against the live constituent list — no exceptions, no other-exchange tickers slipping in.

## Reference materials (not authoritative — review before trusting)
I have earlier prototype work I'll share as it becomes relevant, not upfront:
- A real NLP-derived ESG dataset (263 companies, 2014–2023, e/s/g scores from actual sustainability reports)
- A Phase 1 scoring prototype (sector z-scoring, weight-sensitivity checks) — built and tested on synthetic data only
- A Phase 2 data ingestion pipeline (Wikipedia/yfinance/SEC EDGAR) — written but never run against live internet

Treat anything from these as a starting point to review and verify, not ground truth to build on unquestioned.

## How I want you to work
- Explain code more than usual — I'm comfortable with Python concepts but not an expert. Walk through *why*, not just *what*, especially for pandas idioms (`groupby`/`transform`, etc.). See the `deep-coding` skill for implementation conventions.
- Bullet points over long paragraphs. Real numbers over vague claims.
- Deliver complex tasks as structured, step-by-step output — tell me what you found at each step before moving to the next.
- Be honest about what doesn't work or is uncertain — no false confidence.
- I have a geomatics engineering / satellite EO background — no need to over-explain TROPOMI, Sentinel-5P, or satellite concepts generally.

## Definition of done for this section
`environmental_scores.csv` — one row per verified S&P 500 ticker, columns: `ticker, gics_sector, level_score, velocity_score, integrity_score, environmental_composite_score`, ready to merge with teammates' tables on `ticker`.
