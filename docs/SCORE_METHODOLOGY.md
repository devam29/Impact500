# Environmental Sustainability Score — Explained Simply

This document explains how we turned all our collected data into one
final score per company, in `data/environmental_scores.csv`. No jargon
without an explanation — if you're confused by anything, that's a bug in
this doc, not in you.

## The big idea

We're not just asking "how much pollution does this company make." A
company can be low-polluting today just because it's a small
office-based business (like a bank), not because it's actually trying.
So we ask **three separate questions** about every company, and combine
the answers:

1. **Level** — How clean or dirty is this company *right now*, compared
   to similar companies (not compared to every company in the world)?
2. **Velocity** — Is this company *actually getting cleaner*, and fast
   enough to matter?
3. **Integrity** — Can we actually *trust* the numbers we have for this
   company?

Each question gets a score from 0 (worst) to 100 (best). We average the
three into one final number, `environmental_composite_score`.

## Why we didn't just copy a big-name rating agency (MSCI, S&P, etc.)

Companies like MSCI have one giant, constantly-updated database with
almost every company's data. We're a small team that had to go find and
scrape data ourselves from five different places (CDP reports,
sustainability reports, a government database, SBTi's target tracker,
and a teammate's separate dataset), and a lot of that data has gaps.

So instead of pretending we have what they have, we:
- **Borrowed a couple of specific, well-tested ideas** from real
  organizations where they genuinely fit our data (explained below,
  with links to where those ideas come from).
- **Built something new** for the one part where we simply don't have
  what a big agency would use (explained in the Integrity section) —
  turning our "we have two independent datasets, not one" situation into
  an advantage instead of a limitation.

## Part 1: Level — "how clean is this company right now?"

**The comparison has to be fair.** An oil company and a bank can't be
judged on the same scale — of course an oil company produces more
pollution, that's the nature of the business. So we only ever compare a
company to *other companies in the same sector* (e.g. we compare Apple
only to other Information Technology companies, not to oil companies).

**Step 1 — measure pollution per dollar earned**, not just total
pollution. A giant company will always pollute more in total than a tiny
one; what matters is how much pollution it takes to make a dollar of
revenue. We call this "emissions intensity":

> emissions intensity = (company's total tonnes of CO2) ÷ (company's revenue in dollars)

**Step 2 — grade on a curve, within the sector.** Imagine lining up every
Information Technology company from cleanest to dirtiest. We look at
where a company falls in that lineup and turn it into a 0–100 score,
where 100 = as clean as it gets, 0 = as dirty as it gets *for that
sector*.

We specifically use the same curve-grading method MSCI (a major real ESG
rating company) publishes for this exact purpose, rather than something
we invented: take the sector's typical range (technically, the values
between the 5th-percentile-cleanest and 5th-percentile-dirtiest company,
so a couple of extreme freak outliers don't skew everyone else's grade),
then place the company on a 0–100 scale within that range.

**In formula terms**:
```
intensity = (scope1_tco2e + scope2_tco2e) / revenue_usd

p5, p95  = the 5th and 95th percentile of intensity among companies
           in the same GICS Sector
clipped  = intensity, but pulled inward if it's beyond p5 or p95
           (clipped = min(max(intensity, p5), p95))
level_score = (1 - (clipped - p5) / (p95 - p5)) * 100
```
`scope1_tco2e`/`scope2_tco2e` use the real disclosed value when we have
one, otherwise our own peer-based estimate (Scope 1 and Scope 2 are each
decided independently — see `pipeline/tier2_estimation/estimate_tier2.py`).
`revenue_usd` is real `yfinance` revenue (`financials_cache.csv`), not
the sparse in-document revenue field (only 87/503 companies stated their
own revenue in the source document).

**Why does this matter over a simpler method?** We tested a simpler
approach too (just "what rank is this company, 1st place, 50th place,
etc.") and it gives worse answers. Example from our real data: in the
Information Technology sector, the exact-middle company by rank is HPE.
Under simple "what rank are you" scoring, HPE would get a mediocre score
of 50 out of 100, just because it happens to be in the middle of the
pack. But when you actually look at the NUMBERS, HPE is almost as clean
as the very best companies in the sector — it's only "middle of the
pack" because a couple of really dirty companies are dragging the
average up front. The curve-grading method correctly gives HPE a 95.8,
recognizing it's actually very clean, not just "average." Simple ranking
would have hidden that.

**Where the pollution numbers come from**: if we have a company's real,
disclosed number, we use that. If we don't, we use our own
best-estimate (see `pipeline/tier2_estimation/`, and the earlier data
dictionary) built from what similar companies report. Scope 1 (direct
emissions) and Scope 2 (electricity-related emissions) are each
estimated separately — a company can have a real Scope 1 number and an
estimated Scope 2 number side by side. Every company has both numbers
one way or another, so this score computes for all 503 companies.

## Part 2: Velocity — "is this company actually getting cleaner, fast enough?"

This one is harder than it sounds, because to know if a company is
"getting cleaner," you need to see its pollution numbers from *several
years*, not just one snapshot. **We mostly don't have that.** Out of 503
companies, only 72 gave us a real "here's what we emitted years ago, and
here's what we emit now" comparison.

So we score this in three honest tiers, and every company's row tells
you which tier it's in (`velocity_basis`), so you never mistake a
guess for a measurement:

**Tier A — we can actually measure it (72 companies).** For these, we
compute how fast the company's real emissions have actually been
shrinking per year, and compare that to the pace scientists say is
needed to keep warming to 1.5°C (a well-known standard from the Science
Based Targets initiative: emissions need to shrink about **4.2% every
year**, or 2.5%/year for a slightly less strict "well below 2°C" goal).
A company shrinking exactly at that required pace scores 100. A company
whose emissions are going *up* instead of down scores 0.

**In formula terms**:
```
observed_annual_rate = (base_year_value - current_value) / base_year_value / years_elapsed

benchmark = 4.2%/yr  if SBTi classification is "1.5°C" (or no classification at all)
            2.5%/yr  if SBTi classification is "Well-below 2°C"

velocity_score = clamp(0, 100,  100 * observed_annual_rate / benchmark)
```
`years_elapsed` assumes every company's "current" figure is from 2024
(see the caveat on this below) minus the stated base year.

*Honest caveat*: our real trend data only ever covers Scope 1 (direct
emissions), not Scope 2. So a company that's making real progress mainly
by switching to renewable electricity (a Scope 2 improvement) won't get
credit for that here. Apple is a real example in our data — its direct
Scope 1 emissions have actually gone up since 2011 even though the
company has made big renewable-energy moves elsewhere, so it scores 0 on
this specific measure. Don't read a low Tier A score as "this company
is doing nothing" — read it as "this specific measurement doesn't
capture what this company is actually doing."

**Tier B — no real trend, but they've made a public promise (181
companies).** These companies have a validated climate target through
SBTi (a well-respected third party that checks whether corporate climate
targets are legitimate) but we don't have enough data to see if they're
actually on pace. So we score the *ambition* of the promise instead.

**A note on where these specific numbers come from, since this is the
one place in our whole methodology without a clean external formula to
point to** (unlike Level's MSCI method, or Tier A's SBTi pathway rates).
We looked for one — CDP does publish a real points-based system for
scoring climate targets (e.g. extra points for a validated target, extra
points for a longer time horizon), and Transition Pathway Initiative
has a real 0–5 "Management Quality" scale — but neither is a clean,
standalone "turn an SBTi status into a 0–100 number" formula we could
lift directly; both are one small piece of much larger, mostly
proprietary systems. So instead of inventing an arbitrary lookup table
(which is what an earlier version of this methodology did), we built
this the same *shape* CDP uses — points awarded per specific, named
criterion, summed up — even though the specific point values are still
our own choice, not CDP's literal numbers:

| Criterion | Points |
|---|---|
| Target is SBTi-**validated** ("Targets set"), not just self-declared | 2 |
| Target is only **declared/committed**, not yet validated | 1 |
| Target is classified **1.5°C** (the strictest ambition level) | 2 |
| Target is classified **Well-below 2°C** (one step down) | 1 |
| Company also has a validated or declared **net-zero** target | +1 |

```
score = 100 * (points earned) / 5   [5 = the maximum possible points]
```

A company with a validated 1.5°C target *and* a net-zero commitment gets
full marks (5/5 → 100). A company that's only informally committed, with
no classification yet, scores low (1/5 → 20). And — importantly — a
company that had a validated target and then **withdrew it** bypasses
this points system entirely and gets a fixed, very low score (**10**,
below even Tier C's baseline). That's a real, deliberate red flag, not a
missing-data placeholder. Tesla and Amazon are both in this "withdrew
their commitment" bucket in our current data.

**Tier C — no public climate target at all (250 companies).** We give
these a flat, low score (20). This is a judgment call, not a measured
fact, and we're saying it plainly: staying silent about climate targets
isn't neutral, it's itself worth penalizing a bit — real rating agencies
like CDP do the same thing (a company that doesn't respond to their
survey scores worse than one that responds imperfectly).

## Part 3: Integrity — "can we actually trust this number?"

**The original plan** was to check every company's self-reported
pollution number against an independent measurement from satellites
(a project called Climate TRACE). That would have let us catch a company
that's, say, under-reporting. **We weren't able to get that specific
data this project** — we only got which physical facilities a company
owns from that source, not an independent pollution estimate to compare
against.

**So we built something else instead — using data we already had.**
Here's the insight: we ended up with *two separate, independently-built*
measurements of roughly the same thing for many companies:
1. Our own emissions-intensity score (Part 1, above), built from real
   government/company disclosures plus our own estimates.
2. A teammate's separately-collected dataset from a company called
   Upright, which independently estimates each company's environmental
   cost using its own completely different method.

Neither of these two was built with the other in mind — they're
genuinely independent. So we can ask: **do they roughly agree?** We
checked this on real data before building anything on top of it: for the
467 companies where we have both, the two rankings agree about 71% of
the time (technically, a statistical measure called a rank correlation
of 0.71) — related, since they're measuring similar things, but far
from identical. That gap between two honest, unrelated methods is
useful information nobody would get from either dataset by itself.

**How we use it**: for each company, we check how it ranks in *our* data
versus how it ranks in *Upright's* data. If a company ranks similarly
clean (or dirty) in both, it gets a high "agreement" score. If it looks
clean in one dataset but dirty in the other, that's suspicious, and it
gets a lower score — flagging exactly the kind of "something doesn't add
up here" signal the original satellite-comparison idea was meant to
catch, just built from data we actually had access to.

**In formula terms**:
```
our_percentile     = this company's percentile rank in our own intensity distribution
upright_percentile = this company's percentile rank in Upright's real GHG-cost distribution
                      (only the 467 companies with a REAL Upright record --
                      Upright's own proxy-estimated rows are excluded, since
                      checking our estimate against another estimate proves nothing)

agreement_score = 100 - |our_percentile - upright_percentile|
```

**This is combined with a simpler "how good is the disclosure itself"
check**, looking at:
- *Where did the number come from?* A number from an official CDP
  climate survey is trusted more than one from a company's own glossy
  sustainability report, which is trusted more than our own guess.
- *How complete is it?* Did they report both Scope 1 and Scope 2? Did
  they tell us their starting point (a base year) so progress can be
  tracked? Not disclosing counts against a company here too, same logic
  as Velocity's Tier C.

**In formula terms**:
```
source_tier_score(scope) = 100 if the number came from an official CDP filing
                             70 if from the company's own sustainability report
                             60 if from the EPA government database
                             20 if it's our own estimate (no real disclosure)

source_component = average(source_tier_score(scope1), source_tier_score(scope2))

completeness = 100 * (checks passed / 4), where the 4 checks are:
    real (non-estimated) Scope 1 reported
    real (non-estimated) Scope 2 reported
    a base year is stated
    BOTH location-based and market-based Scope 2 are reported

disclosure_quality = 0.6 * source_component + 0.4 * completeness
```

For most companies (467 of 503), we blend this with the Upright
cross-check:
```
if this company has a REAL Upright record:
    integrity_score = 0.6 * disclosure_quality + 0.4 * agreement_score
else:
    integrity_score = disclosure_quality   # no cross-check to blend in -- never faked
```

**Worked example — 3M (`MMM`)**: real Scope 1 from EPA GHGRP (source
score 60) but an estimated Scope 2 (score 20) → source component = 40.
Only 1 of the 4 completeness checks passes (real Scope 1) →
completeness = 25. `disclosure_quality = 0.6×40 + 0.4×25 = 34`.
Agreement score = 87.8 (our data and Upright's broadly agree on 3M).
`integrity_score = 0.6×34 + 0.4×87.8 = 55.5`.

## Why our Level score and Upright's own numbers can look like they disagree

If you ever compare our `level_score` directly against Upright's own
`upright_environment_cost_cents_per_dollar` for a specific company, don't
be surprised if they seem to tell different stories. This is expected,
and it's not a data quality problem on either side — it's because the
two numbers are answering two different questions on purpose.

**Our Level score is "best-in-class within your industry."** An oil
company can score well on Level if it's clean *compared to other oil
companies* — exactly what CLAUDE.md's own original brief asked for
("an oil major vs. a bank is unfair on raw numbers").

**Upright's raw cost figure is "compared to literally every company,
regardless of industry."** On that measure, an oil company will almost
always look worse than a bank, no matter how well-run it is, simply
because extracting oil is inherently more emissions-intensive per dollar
than managing investments.

We checked this concretely: our raw pollution-per-dollar numbers and
Upright's raw cost numbers actually agree well when compared on the same
(no industry adjustment) basis — about 71% rank agreement. But once we
turn our number into an industry-adjusted score, agreement with
Upright's un-adjusted number drops a lot (to about 27%), and it drops in
exactly the pattern you'd expect: companies in inherently dirty
industries that are well-run for their industry (e.g. EOG Resources,
Atmos Energy, PSEG, Schlumberger) score better on our measure than on
Upright's; companies in inherently clean industries that happen to look
a little worse than their (very clean) peers (e.g. BlackRock, Truist,
Quest Diagnostics) score worse on our measure than on Upright's.

**Neither measure is "wrong," and we haven't changed either one to force
them into agreement** — doing that would throw away one of the two
genuinely different, useful answers ("who's well-run for their
industry" vs. "who has the smallest absolute footprint"). If you want
both lenses side by side for a specific company, `level_score` gives you
the first, `upright_environment_cost_cents_per_dollar` (in
`data/sp500_metrics.json`) gives you the second.

(Note: this is separate from the Cross-Source Agreement check inside
Integrity above, which deliberately compares both companies' rankings on
the *same*, non-industry-adjusted basis for exactly this reason — that
comparison doesn't have this issue.)

## Putting it all together

The final score is simply the average of the three:

```
environmental_composite_score = (level_score + velocity_score + integrity_score) / 3
```

**We double-checked that this "average everything equally" choice is
actually reasonable**, rather than just assuming it. We recomputed the
final ranking twice more, with different weights, and measured how much
the overall order of companies changed (a statistic called Spearman
rank correlation — 1.0 would mean "identical ranking," 0 would mean
"no relationship at all"):

| Alternate weighting (Level / Velocity / Integrity) | How similar the ranking is to equal-thirds |
|---|---|
| 50% / 25% / 25% (Level matters most) | 0.933 |
| 25% / 50% / 25% (Velocity matters most) | 0.951 |

Both above 0.9 — the ranking barely moves no matter which of these
weightings you pick. That tells us equal-thirds isn't secretly doing all
the work; the ranking is solid either way.

## Being upfront about the weak spots

We'd rather you know these than find them yourself:

- **Velocity's "real trend" measurement only looks at Scope 1.** A
  company progressing mainly on Scope 2 (like Apple) can look
  artificially stuck.
- **We assumed every company's "current" number is from 2024** when
  calculating how many years have passed since their baseline. We don't
  actually know the exact year for each company — this is a
  simplification.
- **The "no climate target = score of 20" rule, the specific point
  values in Tier B's table (2/2/1), and the "withdrawn commitment = 10"
  floor are all our own judgment calls**, not scientific formulas. The
  *shape* of Tier B (sum points per named criterion) is inspired by
  CDP's real scoring approach; the specific point values are ours. If you
  disagree with any of these numbers, this is the easiest and most
  defensible place to change them.
- **The cross-checking-against-Upright idea only works for 467 of 503
  companies** — the rest fall back to a less complete check.
- **We group companies by broad sector** (11 groups) rather than
  narrower sub-industries, because the narrower groups are too small
  (sometimes under 5 companies) to compare fairly.
- Every score comes with a label telling you whether it's based on real
  data or our own estimate (`scope1_is_estimated`, `scope2_is_estimated`,
  `velocity_basis`, `integrity_basis` in the CSV) — always check these
  before repeating a specific number as fact.
- **Our Level score and Upright's own raw numbers will sometimes point in
  different directions for the same company** — see "Why our Level score
  and Upright's own numbers can look like they disagree" above before
  assuming either one is wrong.

## Where the specific numbers in our method came from

- The "4.2% per year for 1.5°C" pace requirement: [Science Based Targets initiative's own published standard](https://greencalculus.com/methodology/sbti-absolute-contraction-approach/)
- The "grade on a curve within your sector" scoring method: [MSCI's published carbon-emissions scoring approach](https://www.msci.com/documents/1296102/34424357/MSCI+ESG+Ratings+Methodology+-+Carbon+Emissions+Key+Issue.pdf)
- Confirming that it's normal/accepted practice for real rating agencies to score (not ignore) companies with missing data, as long as it's clearly labeled: [academic research on missing-data handling in ESG scoring](https://www.sciencedirect.com/science/article/pii/S1544612325010761)
- The "sum points per named criterion" shape for Tier B's target-ambition score: inspired by [CDP's published Climate Change scoring methodology](https://guidance.cdp.net/en/guidance?cid=46&ctype=theme&idtype=ThemeID&incchild=1&microsite=0&otype=ScoringMethodology&page=1&tags=TAG-605%2CTAG-646), which awards points per specific target-related criterion (validation status, target horizon, etc.) rather than a single arbitrary number. We also checked [Transition Pathway Initiative's Management Quality methodology](https://www.transitionpathwayinitiative.org/methodology) (a real, published 0–5 climate-governance scale) as a second reference point, though its broader scope didn't map cleanly onto our specific SBTi fields.

## How to regenerate this score if the underlying data changes

```
py pipeline/tier2_estimation/estimate_tier2.py
py pipeline/build_combined_dataset.py
py pipeline/scoring/compute_environmental_scores.py
```
