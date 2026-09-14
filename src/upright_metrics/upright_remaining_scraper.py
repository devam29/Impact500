#!/usr/bin/env python3
"""Scrape detailed Upright profiles missing from the combined S&P 500 data."""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from upright_scraper import scrape_company

UPRIGHT_HOME = "https://uprightplatform.com/"
UUID_RE = re.compile(r"/company/([0-9a-f-]{36})(?:/|$)", re.I)
IGNORED_WORDS = {
    "a", "an", "and", "class", "co", "company", "corp", "corporation",
    "group", "holdings", "inc", "incorporated", "limited", "ltd", "nv",
    "plc", "sa", "se", "the",
}


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = value.lower().replace("&", " and ")
    value = re.sub(r"\([^)]*\)", " ", value)
    tokens = re.findall(r"[a-z0-9]+", value)
    return " ".join(token for token in tokens if token not in IGNORED_WORDS)


def name_score(expected: str, actual: str) -> float:
    left, right = normalized_name(expected), normalized_name(actual)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if min(len(left), len(right)) >= 5 and (left in right or right in left):
        return 0.96
    return SequenceMatcher(None, left, right).ratio()


def company_uuid(url: str) -> str:
    found = UUID_RE.search(url)
    return found.group(1).lower() if found else ""


def load_json_list(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError(f"{path} must contain a JSON array of objects")
    return data


def load_sp500(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))
    if not rows or not {"Ticker", "Company"}.issubset(rows[0]):
        raise ValueError(f"{path} must contain Ticker and Company columns")
    return rows


def atomic_write(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    temporary.replace(path)


def best_local_match(company: str, existing: list[dict]) -> tuple[float, dict | None]:
    choices = [(name_score(company, clean(row.get("company"))), row)
               for row in existing]
    return max(choices, key=lambda item: item[0], default=(0.0, None))


def search_upright(page: Page, query: str, wait_ms: int) -> tuple[str, str]:
    """Search the rendered public UI and open its top result."""
    page.goto(UPRIGHT_HOME, wait_until="domcontentloaded", timeout=60_000)
    box = page.get_by_role("searchbox").first
    box.wait_for(state="visible", timeout=60_000)
    box.fill(query)
    page.wait_for_timeout(wait_ms)
    try:
        page.wait_for_function(
            """query => [...document.querySelectorAll('[role="log"]')].some(e =>
                (e.textContent || '').toLowerCase().includes(
                    'results available for search term ' + query.toLowerCase()))""",
            arg=query,
            timeout=15_000,
        )
    except PlaywrightTimeoutError:
        return page.url, ""

    logs = page.get_by_role("log").all_text_contents()
    log_text = clean(" ".join(logs))
    if "0 results available" in log_text.lower():
        return "", ""

    box.press("Enter")
    try:
        page.wait_for_url(re.compile(r"uprightplatform\.com/company/"), timeout=20_000)
    except PlaywrightTimeoutError:
        return page.url, ""
    page.locator("h1").first.wait_for(state="visible", timeout=30_000)
    return page.url, clean(page.locator("h1").first.inner_text())


def seed(row: dict[str, str], url: str) -> dict[str, str]:
    return {
        "company": row["Company"], "industry": "",
        "screener_revenue_musd": "", "largest_cost": "",
        "largest_benefit": "", "screener_net_impact_ratio": "",
        "screener_percentile": "", "upright_url": url,
    }


def ratio_from_page_text(page: Page) -> str:
    body = clean(page.locator("body").inner_text(timeout=30_000))
    less = re.search(
        r"Creates on average\s+(\d+(?:\.\d+)?)%\s+less negative impact",
        body, re.I,
    )
    if less:
        return f"+{less.group(1)}%"
    more = re.search(
        r"Creates on average\s+(\d+(?:\.\d+)?)%\s+more negative impact",
        body, re.I,
    )
    return f"-{more.group(1)}%" if more else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sp500", type=Path, default=Path("sp500_companies.csv"))
    parser.add_argument("--combined", type=Path,
                        default=Path("upright_combined_esg.json"))
    parser.add_argument("--output", type=Path,
                        default=Path("remaining_companies_esg.json"))
    parser.add_argument("--status", type=Path,
                        default=Path("remaining_companies_esg_status.json"))
    parser.add_argument("--ticker", action="append",
                        help="Only process this ticker; may be repeated")
    parser.add_argument("--limit", type=int, default=0,
                        help="Maximum searches this run; 0 means all")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--search-wait-ms", type=int, default=1200)
    parser.add_argument("--local-match", type=float, default=0.92)
    parser.add_argument("--search-match", type=float, default=0.72)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--retry-failures", action="store_true")
    args = parser.parse_args()
    if args.limit < 0 or args.delay < 0 or args.search_wait_ms < 0:
        parser.error("--limit, --delay and --search-wait-ms cannot be negative")

    combined = load_json_list(args.combined)
    sp500 = load_sp500(args.sp500)
    selected = {ticker.upper() for ticker in args.ticker or []}
    if selected:
        sp500 = [row for row in sp500 if row["Ticker"].upper() in selected]

    remaining = load_json_list(args.output) if args.output.exists() else []
    status = (json.loads(args.status.read_text(encoding="utf-8"))
              if args.status.exists() else {"companies": {}})
    status.setdefault("companies", {})
    combined_ids = {company_uuid(clean(row.get("upright_url"))) for row in combined}
    remaining_ids = {company_uuid(clean(row.get("upright_url"))) for row in remaining}
    combined_ids.discard("")
    remaining_ids.discard("")
    final_states = {"already_in_combined", "scraped", "no_results", "ambiguous"}

    searches = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        try:
            for position, row in enumerate(sp500, 1):
                ticker, expected = row["Ticker"].upper(), row["Company"]
                prior = status["companies"].get(ticker, {}).get("state")
                if prior in final_states and not args.retry_failures:
                    continue

                score, local = best_local_match(expected, combined)
                if local is not None and score >= args.local_match:
                    status["companies"][ticker] = {
                        "state": "already_in_combined", "sp500_company": expected,
                        "matched_company": local.get("company", ""),
                        "upright_url": local.get("upright_url", ""),
                        "match_score": round(score, 4), "match_method": "local_name",
                    }
                    atomic_write(args.status, status)
                    continue

                if args.limit and searches >= args.limit:
                    break
                searches += 1
                print(f"[{position}/{len(sp500)}] Search {ticker}: {expected}")

                try:
                    url, actual = search_upright(page, expected, args.search_wait_ms)
                    uuid, score = company_uuid(url), name_score(expected, actual)
                    if not uuid:
                        status["companies"][ticker] = {
                            "state": "no_results" if not url else "ambiguous",
                            "sp500_company": expected, "selected_url": url,
                            "reason": "No Upright company detail result was selected",
                        }
                    elif score < args.search_match:
                        status["companies"][ticker] = {
                            "state": "ambiguous", "sp500_company": expected,
                            "matched_company": actual, "upright_url": url,
                            "match_score": round(score, 4),
                        }
                    elif uuid in combined_ids:
                        status["companies"][ticker] = {
                            "state": "already_in_combined", "sp500_company": expected,
                            "matched_company": actual, "upright_url": url,
                            "match_score": round(score, 4), "match_method": "upright_uuid",
                        }
                    elif uuid in remaining_ids:
                        status["companies"][ticker] = {
                            "state": "scraped", "sp500_company": expected,
                            "matched_company": actual, "upright_url": url,
                            "match_score": round(score, 4),
                            "reason": "Already present in remaining output",
                        }
                    else:
                        record = scrape_company(page, seed(row, url))
                        if not record.get("net_impact_ratio"):
                            record["net_impact_ratio"] = ratio_from_page_text(page)
                        record.update({
                            "source_index": "S&P 500 ESG",
                            "source_url": (
                                "https://uprightplatform.com/"
                                "?companyPreset=SP500ESG"
                            ),
                        })
                        remaining.append(record)
                        remaining_ids.add(uuid)
                        atomic_write(args.output, remaining)
                        status["companies"][ticker] = {
                            "state": "scraped", "sp500_company": expected,
                            "matched_company": actual, "upright_url": url,
                            "match_score": round(score, 4),
                        }
                        print(f"  scraped {actual}")
                except Exception as error:
                    status["companies"][ticker] = {
                        "state": "error", "sp500_company": expected,
                        "error": f"{type(error).__name__}: {error}",
                    }
                    print(f"  ERROR: {type(error).__name__}: {error}")

                status["updated_at_utc"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                )
                atomic_write(args.status, status)
                if args.delay:
                    page.wait_for_timeout(int(args.delay * 1000))
        finally:
            browser.close()

    atomic_write(args.output, remaining)
    counts: dict[str, int] = {}
    for item in status["companies"].values():
        state = item.get("state", "unknown")
        counts[state] = counts.get(state, 0) + 1
    print(f"Wrote {len(remaining)} profiles to {args.output.resolve()}")
    print(f"Status counts: {counts}")


if __name__ == "__main__":
    main()
