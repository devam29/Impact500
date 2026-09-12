---
name: environmental-thinking
description: Reasoning about environmental sustainability strategy, definitions, indicator selection, scoring methodology, or competitive differentiation for the S&P 500 hackathon project. Use for brainstorming, evaluating an idea's novelty, or designing/justifying any part of the Level-Velocity-Integrity framework. Not for implementation — see the deep-coding skill for that.
---

# Environmental Sustainability: Domain Thinking

Act as an expert Data Scientist and Corporate Sustainability Analyst for this specific project. Every idea gets tested against three questions before it's good enough:

1. Does it operationalize our own definition ("reducing environmental burden fast enough"), or does it quietly slide back into a static footprint score?
2. Has something with real institutional backing already done this, and if so, what's genuinely different about our version?
3. Does it work with data that's actually reachable in a hackathon timeline, or is it a nice idea we can't execute?

## Core framework: Level + Velocity + Integrity
- **Level** — current environmental burden, sector-relative z-score. Necessary baseline, not the differentiator — almost every competing team will stop here.
- **Velocity** — the actual differentiator. Is the company's own historical emissions/e-score trend keeping pace with a science-based pathway? Benchmark: SBTi's Absolute Contraction Approach, **4.2%/year required linear reduction for Scope 1+2** (2.5%/year Scope 3) to be 1.5°C-aligned. Note SBTi loosened some near-term requirements in 2026 for some companies — state explicitly which benchmark vintage is being used, never mix silently.
- **Integrity** — trust layer. Cross-check self-reported emissions against an independent, satellite-based estimate (Climate TRACE). A company that looks great on Level and Velocity but has a large reporting gap should be flagged, not rewarded.

## Why sector-relative normalization is non-negotiable
Raw carbon intensity makes an oil major look catastrophically worse than a bank, which just re-encodes "which sector are you in" as "how sustainable are you." Every Level indicator must be z-scored within GICS sector. A good sanity check: sector-average composite scores should land close to each other (not systematically favor or punish one sector) — if they don't, the normalization has failed.

## Competitive landscape (know this before claiming something is new)
| Precedent | Resembles | Real gap we can exploit |
|---|---|---|
| Transition Pathway Initiative (TPI) | Velocity — compares emissions trajectory to IPCC/IEA pathways | Only covers high-impact sectors, no verification layer |
| MSCI Implied Temperature Rise | Level + Velocity compressed to one number | Paid, proprietary, not reproducible/transparent |
| Climate TRACE | Integrity — independent satellite-based emissions | Doesn't score trajectory-vs-pathway itself |
| CDP scores | Level (disclosure-quality) | Full response data is now licensed, not free |
| SBTi validation | Sets the Velocity benchmark, doesn't score realized performance against it | — |

Nobody combines self-reported + independently-verified + pathway-benchmarked-trend into one transparent, reproducible score. That combination — not any single component — is the actual differentiation. Say so explicitly when presenting the approach.

## Scope discipline
Every company scored must be a verified, current S&P 500 constituent. A methodology that's "S&P 500" in name but includes non-member tickers undercuts the whole pitch the moment a judge checks.

## Pillar boundaries (don't duplicate teammates' work)
- Environmental Sustainability (this pillar) = realized outcomes — actual emissions, actual measured trend. Backward-looking, evidence-based.
- Transition Readiness (teammate) = stated intent/capacity — green capex, R&D, energy pipeline. Forward-looking, plan-based.
- Economic Resilience (teammate) = balance sheet durability — FCF, debt capacity, margin.
