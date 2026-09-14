#!/usr/bin/env python3
"""Export detailed public Upright net-impact data in batches of up to 10."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import Page, sync_playwright

SOURCE_URL = "https://uprightplatform.com/?companyPreset=SP500ESG"
MAX_COMPANIES_PER_RUN = 10
UNIT = "cents per dollar of revenue"
CATEGORY_METRICS = {
    "Society": ["Jobs", "Taxes", "Societal infrastructure",
                "Societal stability", "Equality & human rights"],
    "Knowledge": ["Knowledge infrastructure", "Creating knowledge",
                  "Distributing knowledge", "Scarce human capital"],
    "Health": ["Physical diseases", "Mental diseases", "Nutrition",
               "Relationships", "Meaning & joy"],
    "Environment": ["GHG emissions", "Non-GHG emissions",
                    "Scarce natural resources", "Biodiversity", "Waste"],
}
METRIC_CODES = {
    "S1": ("Society", "Taxes"),
    "S2": ("Society", "Jobs"),
    "S3": ("Society", "Societal infrastructure"),
    "S4": ("Society", "Equality & human rights"),
    "S5": ("Society", "Societal stability"),
    "K1": ("Knowledge", "Scarce human capital"),
    "K2": ("Knowledge", "Knowledge infrastructure"),
    "K3": ("Knowledge", "Creating knowledge"),
    "K4": ("Knowledge", "Distributing knowledge"),
    "H1": ("Health", "Physical diseases"),
    "H2": ("Health", "Mental diseases"),
    "H3": ("Health", "Nutrition"),
    "H4": ("Health", "Relationships"),
    "H5": ("Health", "Meaning & joy"),
    "E1": ("Environment", "GHG emissions"),
    "E2": ("Environment", "Non-GHG emissions"),
    "E3": ("Environment", "Scarce natural resources"),
    "E4": ("Environment", "Biodiversity"),
    "E5": ("Environment", "Waste"),
}
CATEGORY_CODES = {"S": "Society", "K": "Knowledge", "H": "Health",
                  "E": "Environment"}


def clean(value: str | None) -> str:
    return " ".join((value or "").split())


def match(pattern: str, text: str, flags: int = 0) -> str:
    found = re.search(pattern, text, flags)
    return clean(found.group(1)) if found else ""


def collect_company_links(
    page: Page, offset: int, limit: int
) -> list[dict[str, str]]:
    """Collect a zero-based slice, following the public table's pagination."""
    page.goto(SOURCE_URL, wait_until="domcontentloaded", timeout=60_000)
    table = page.locator(
        'table:has(th:has-text("Industry")):has(th:has-text("Net impact ratio"))'
    ).first
    table.wait_for(state="visible", timeout=60_000)

    output: list[dict[str, str]] = []
    seen = 0
    while len(output) < limit:
        rows = table.locator("tbody tr")
        row_count = rows.count()
        for i in range(row_count):
            if seen < offset:
                seen += 1
                continue

            cells = rows.nth(i).locator("td")
            link = cells.nth(0).locator("a").first
            impact = clean(cells.nth(5).inner_text())
            output.append({
                "company": clean(link.inner_text()),
                "industry": clean(cells.nth(1).inner_text()),
                "screener_revenue_musd": clean(cells.nth(2).inner_text()),
                "largest_cost": clean(cells.nth(3).inner_text()),
                "largest_benefit": clean(cells.nth(4).inner_text()),
                "screener_net_impact_ratio": match(
                    r"([+-]?\d+(?:\.\d+)?%)", impact
                ),
                "screener_percentile": match(
                    r"(\d+(?:st|nd|rd|th) percentile)", impact, re.I
                ),
                "upright_url": urljoin(
                    SOURCE_URL, link.get_attribute("href") or ""
                ),
            })
            seen += 1
            if len(output) == limit:
                break

        if len(output) == limit:
            break

        next_button = page.get_by_role("button", name="Next", exact=True)
        if not next_button.is_enabled():
            raise RuntimeError(
                f"Offset {offset} plus limit {limit} exceeds the displayed index"
            )
        old_href = rows.nth(0).locator("td a").first.get_attribute("href")
        next_button.click()
        page.wait_for_function(
            """oldHref => {
                const tables = [...document.querySelectorAll('table')];
                const companyTable = tables.find(t =>
                    [...t.querySelectorAll('th')].some(th =>
                        (th.textContent || '').includes('Industry')));
                const href = companyTable?.querySelector('tbody tr td a')
                    ?.getAttribute('href');
                return href && href !== oldHref;
            }""",
            arg=old_href,
            timeout=60_000,
        )
    return output


def extract_chart(page: Page) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    """Read Upright's public SVG labels; N means cost and P means benefit."""
    chart = page.locator("svg").filter(has_text="Scarce human capital").first
    chart.wait_for(state="visible", timeout=60_000)
    items = chart.locator('text[data-testid^="impact-bar-data-label-"]').evaluate_all(
        """elements => elements.map(e => ({
            id: e.getAttribute('data-testid'),
            value: (e.textContent || '').trim()
        }))"""
    )
    values = {}
    for item in items:
        found = re.fullmatch(r"impact-bar-data-label-([A-Z]\d?)-(N|P)", item["id"])
        if found:
            values[(found.group(1), found.group(2))] = item["value"]

    metrics = [{
        "category": category,
        "metric": name,
        "cost": values.get((code, "N"), ""),
        "benefit": values.get((code, "P"), ""),
        "unit": UNIT,
    } for code, (category, name) in METRIC_CODES.items()]
    totals = {category: {
        "cost": values.get((code, "N"), ""),
        "benefit": values.get((code, "P"), ""),
        "unit": UNIT,
    } for code, category in CATEGORY_CODES.items()}
    return metrics, totals


def titled_value(page: Page, title: str) -> str:
    item = page.locator(f'[title="{title}"]').first
    return clean(item.text_content()) if item.count() else ""


def scrape_company(page: Page, seed: dict[str, str]) -> dict:
    page.goto(seed["upright_url"], wait_until="domcontentloaded", timeout=60_000)
    page.locator("h1").first.wait_for(state="visible", timeout=60_000)
    metrics, totals = extract_chart(page)
    body = page.locator("body").inner_text(timeout=30_000)

    ratio = ""
    for text in page.locator("svg").all_text_contents():
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?%", clean(text)):
            ratio = clean(text)
            break

    negative = match(
        r"Top negative impacts\s+(.*?)\s+Top positive impacts", body, re.I | re.S
    )
    positive = match(
        r"Top positive impacts\s+(.*?)\s+Upright model release", body, re.I | re.S
    )
    return {
        **seed,
        "company": clean(page.locator("h1").first.inner_text()),
        "country_of_hq": titled_value(page, "Country of HQ"),
        "revenue": titled_value(page, "Revenue"),
        "employee_count": titled_value(page, "Employee count"),
        "net_impact_ratio": ratio or seed["screener_net_impact_ratio"],
        "rank_top_percent": match(
            r"Ranks in the\s+top\s+(\d+(?:\.\d+)?%)", body, re.I
        ),
        "benchmark_percent_lower": match(
            r"(\d+(?:\.\d+)?)\s*% have a lower\s+net impact ratio", body, re.I
        ),
        "model_release": match(r"Upright model release\s+([\d.]+)", body, re.I),
        "top_negative_impact_explanation": negative,
        "top_positive_impact_explanation": positive,
        "category_totals": totals,
        "metrics": metrics,
        "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_index": "S&P 500 ESG",
        "source_url": SOURCE_URL,
    }


def write_outputs(records: list[dict], prefix: Path, append: bool) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = prefix.with_suffix(".json")
    summary_path = prefix.parent / f"{prefix.name}_summary.csv"
    metrics_path = prefix.parent / f"{prefix.name}_metrics.csv"
    if append and json_path.exists():
        previous = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(previous, list):
            raise RuntimeError(f"Existing {json_path} does not contain a JSON list")
        combined = {row["upright_url"]: row for row in previous}
        combined.update({row["upright_url"]: row for row in records})
        records = list(combined.values())
    elif append and (summary_path.exists() or metrics_path.exists()):
        raise RuntimeError(
            f"Cannot append safely because {json_path} is missing; use a new prefix"
        )

    json_path.write_text(json.dumps(records, indent=2, ensure_ascii=False),
                         encoding="utf-8")

    summary_fields = ["company", "industry", "country_of_hq", "revenue",
                      "employee_count", "net_impact_ratio", "rank_top_percent",
                      "benchmark_percent_lower", "largest_cost", "largest_benefit",
                      "model_release", "upright_url", "scraped_at_utc"]
    with summary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in summary_fields}
                         for row in records)

    metric_fields = ["company", "row_type", "category", "metric", "cost",
                     "benefit", "unit", "model_release", "upright_url"]
    with metrics_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=metric_fields)
        writer.writeheader()
        for record in records:
            for category, values in record["category_totals"].items():
                writer.writerow({"company": record["company"],
                                 "row_type": "category_total",
                                 "category": category, "metric": category,
                                 **values, "model_release": record["model_release"],
                                 "upright_url": record["upright_url"]})
            for metric in record["metrics"]:
                writer.writerow({"company": record["company"],
                                 "row_type": "submetric", **metric,
                                 "model_release": record["model_release"],
                                 "upright_url": record["upright_url"]})

    print(f"Dataset now contains {len(records)} detailed profiles:")
    print(f"  {summary_path.resolve()}")
    print(f"  {metrics_path.resolve()}")
    print(f"  {json_path.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offset", type=int, default=312,
                        help="Zero-based number of companies to skip")
    parser.add_argument("--limit", type=int, default=1,
                        help="Companies to scrape in this run (1-10)")
    parser.add_argument("--output-prefix", type=Path,
                        default=Path("upright_Marketaxess_esg"))
    parser.add_argument("--append", action="store_true",
                        help="Merge into existing outputs and remove duplicates")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= MAX_COMPANIES_PER_RUN:
        parser.error(f"--limit must be between 1 and {MAX_COMPANIES_PER_RUN}")
    if args.offset < 0:
        parser.error("--offset cannot be negative")
    if args.delay < 0:
        parser.error("--delay cannot be negative")

    with sync_playwright() as pw:
        # Reuse the locally installed Google Chrome, avoiding a separate
        # Playwright browser download on this Mac.
        browser = pw.chromium.launch(channel="chrome", headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        try:
            seeds = collect_company_links(page, args.offset, args.limit)
            records = []
            for number, seed in enumerate(seeds, 1):
                print(f"[{number}/{len(seeds)}] {seed['company']}")
                records.append(scrape_company(page, seed))
                if number < len(seeds):
                    page.wait_for_timeout(int(args.delay * 1000))
        finally:
            browser.close()
    write_outputs(records, args.output_prefix, args.append)


if __name__ == "__main__":
    main()
