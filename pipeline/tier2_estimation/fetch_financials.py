"""
Fetch revenue, employee count, and sector/industry classification for
every S&P 500 ticker, via yfinance (Yahoo Finance). This is the
normalization data the Tier 2 median-model estimate (estimate_tier2.py)
needs -- both for computing sector-median emissions intensity from Tier 1
(real-data) companies, and for scaling that intensity up to a Tier 2
company's own size.

Deliberately a separate, cacheable step: yfinance is a live network call
per ticker (503 of them), slow and occasionally flaky, so this writes
one row per ticker to financials_cache.csv as it goes and can be safely
re-run -- already-fetched tickers are skipped on a re-run unless
--refresh is passed.

Usage: py fetch_financials.py [--refresh]
Writes: financials_cache.csv (ticker, revenue_usd, employees, sector,
industry, market_cap, fetch_error)
"""
import csv
import os
import sys
import time

import yfinance as yf

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(HERE))
CONSTITUENTS_PATH = os.path.join(REPO_DIR, "sp500_constituents.csv")
OUT_PATH = os.path.join(HERE, "financials_cache.csv")

FIELDS = ["ticker", "revenue_usd", "employees", "sector", "industry", "market_cap", "fetch_error"]


def load_tickers():
    tickers = []
    with open(CONSTITUENTS_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tickers.append(row["Symbol"])
    return tickers


def load_existing():
    existing = {}
    if os.path.isfile(OUT_PATH):
        with open(OUT_PATH, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                existing[row["ticker"]] = row
    return existing


def fetch_one(ticker):
    # yfinance wants "BRK-B" style, not "BRK.B"
    yf_ticker = ticker.replace(".", "-")
    try:
        info = yf.Ticker(yf_ticker).info
        return {
            "ticker": ticker,
            "revenue_usd": info.get("totalRevenue") or "",
            "employees": info.get("fullTimeEmployees") or "",
            "sector": info.get("sector") or "",
            "industry": info.get("industry") or "",
            "market_cap": info.get("marketCap") or "",
            "fetch_error": "",
        }
    except Exception as e:
        return {
            "ticker": ticker, "revenue_usd": "", "employees": "",
            "sector": "", "industry": "", "market_cap": "",
            "fetch_error": str(e)[:200],
        }


def main():
    refresh = "--refresh" in sys.argv
    tickers = load_tickers()
    existing = {} if refresh else load_existing()
    print(f"Tickers: {len(tickers)}, already cached: {len(existing)}")

    file_exists = os.path.isfile(OUT_PATH) and not refresh
    mode = "a" if file_exists else "w"
    with open(OUT_PATH, mode, newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if not file_exists:
            w.writeheader()

        fetched = 0
        errors = 0
        for i, ticker in enumerate(tickers):
            if ticker in existing:
                continue
            row = fetch_one(ticker)
            w.writerow(row)
            f.flush()
            fetched += 1
            if row["fetch_error"]:
                errors += 1
                print(f"  [{i+1}/{len(tickers)}] {ticker}: ERROR {row['fetch_error']}")
            else:
                print(f"  [{i+1}/{len(tickers)}] {ticker}: revenue={row['revenue_usd']} "
                      f"employees={row['employees']} sector={row['sector']}")
            time.sleep(0.15)  # be polite to Yahoo's endpoint

    print(f"\nFetched this run: {fetched} ({errors} errors)")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
