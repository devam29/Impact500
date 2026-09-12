---
name: deep-coding
description: Writing, reviewing, or debugging any code for the S&P 500 hackathon project — data fetching, scoring formulas, merges, anything that runs. Use for implementation work. Not for strategy or methodology discussion — see the environmental-thinking skill for that.
---

# Deep Coding: Implementation Discipline

Devam is comfortable with Python concepts but not an expert — explain *why*, not just *what*, especially for pandas idioms (`groupby`/`transform`, vectorized operations, etc.) and anything non-obvious. Don't just hand over working code silently.

## Before writing any data-related code
- **Ticker normalization is mandatory, everywhere.** Wikipedia writes multi-class tickers with a dot (`BRK.B`); Yahoo Finance and most financial APIs expect a dash (`BRK-B`). Normalize on ingestion, once, in one shared function — never assume a ticker column is already clean.
- **S&P 500 membership must be validated, not assumed.** Cross-check every ticker against the live constituent list before it enters any output. A ticker from another dataset or another exchange doesn't get scored just because it showed up in a CSV.
- **Never trust a fetcher until it's actually run against live data once.** Written-but-untested code is not the same as working code — say so explicitly if something hasn't been verified end-to-end yet, don't imply it works because it looks correct.

## Common failure modes to design around
- yfinance and similar APIs don't have perfectly consistent row/field labels across tickers — match by keyword-contains rather than hardcoding one exact string, or a subset of tickers silently returns `None`.
- One bad ticker (delisted, renamed, rate-limited) should never kill a batch of hundreds — wrap per-item fetches in try/except, return a status flag, keep going.
- No bulk endpoint typically exists for per-company financial statement data — batch with threading (`concurrent.futures.ThreadPoolExecutor`), and pick a worker count that won't trip informal rate limits.
- SEC EDGAR and similar APIs require a descriptive `User-Agent` header (not auth — just contact info) or requests get silently rejected.

## Verification habit
After writing a fetcher or transformation, actually run it and show real output — a row count, a sample, a sanity-check number (e.g. "sector averages cluster near 50, confirming normalization worked") — rather than describing what it should do. If something can't be run in the current environment (no network, missing credential), say that plainly instead of presenting untested code as done.

## Code style
- Modular functions with docstrings explaining intent, not just mechanics.
- Prefer clarity over cleverness — a slightly longer, obvious implementation beats a dense one-liner Devam would have to reverse-engineer.
- Flag any placeholder, mock, or simulated data explicitly in both the code (comments, a boolean column like `is_simulated`) and in your response — never let synthetic output pass as real without saying so.
