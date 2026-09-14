#!/usr/bin/env python3
"""Create a three-year S&P 500 FCF report from downloaded SimFin annual CSVs."""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


DATA_DIRECTORY = Path(__file__).parent
DEFAULT_INCOME_CSVS = [
    DATA_DIRECTORY / "us-income-annual.csv",
    DATA_DIRECTORY / "us-income-banks-annual.csv",
    DATA_DIRECTORY / "us-income-insurance-annual.csv",
]
DEFAULT_CASHFLOW_CSVS = [
    DATA_DIRECTORY / "us-cashflow-annual.csv",
    DATA_DIRECTORY / "us-cashflow-banks-annual.csv",
    DATA_DIRECTORY / "us-cashflow-insurance-annual.csv",
]
DEFAULT_OUTPUT_DIRECTORY = DATA_DIRECTORY / "output_simfin"
SP500_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "main/data/constituents.csv"
)
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def normalise_ticker(value: str) -> str:
    return value.strip().upper().replace(".", "-")


def read_simfin_csv(path: Path) -> list[dict[str, str]]:
    """Read SimFin's semicolon-delimited annual statement export."""
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file, delimiter=";"))


def read_simfin_csvs(paths: list[Path]) -> list[dict[str, str]]:
    """Combine normal, bank, and insurance statement exports."""
    rows: list[dict[str, str]] = []
    for path in paths:
        rows.extend(read_simfin_csv(path))
    return rows


def value(row: dict[str, str], name: str) -> float | None:
    raw = row.get(name, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def fiscal_year(row: dict[str, str]) -> int | None:
    try:
        return int(row.get("Fiscal Year", ""))
    except ValueError:
        return None


def latest_statement_rows(rows: list[dict[str, str]]) -> dict[tuple[str, int], dict[str, str]]:
    """Keep the latest restatement for each ticker and fiscal year."""
    result: dict[tuple[str, int], dict[str, str]] = {}
    for row in rows:
        ticker = normalise_ticker(row.get("Ticker", ""))
        year = fiscal_year(row)
        if not ticker or year is None or row.get("Fiscal Period") != "FY":
            continue
        if row.get("Currency") != "USD":
            continue
        key = (ticker, year)
        current = result.get(key)
        if current is None or (
            row.get("Restated Date", ""), row.get("Publish Date", "")
        ) > (
            current.get("Restated Date", ""), current.get("Publish Date", "")
        ):
            result[key] = row
    return result


def download_sp500_constituents() -> dict[str, dict[str, str]]:
    request = Request(SP500_CSV_URL, headers={"User-Agent": "sp500-fcf-research"})
    with urlopen(request, timeout=45) as response:  # noqa: S310 - fixed HTTPS URL
        rows = csv.DictReader(response.read().decode("utf-8-sig").splitlines())
        return {
            normalise_ticker(row["Symbol"]): {
                "ticker": row["Symbol"],
                "company": row.get("Security", ""),
                "sector": row.get("GICS Sector", ""),
                "industry": row.get("GICS Sub-Industry", ""),
                "cik": row.get("CIK", "").zfill(10),
            }
            for row in rows
        }


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sec_latest_fact(
    company_facts: dict[str, Any], tags: list[str], annual: bool, quarterly: bool = False
) -> dict[str, Any] | None:
    """Return the latest USD annual-duration or year-end XBRL fact."""
    allowed_forms = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
    if quarterly:
        allowed_forms |= {"10-Q", "10-Q/A"}
    namespaces = company_facts.get("facts", {})
    for namespace in ("us-gaap", "ifrs-full"):
        concepts = namespaces.get(namespace, {})
        for tag in tags:
            values = concepts.get(tag, {}).get("units", {}).get("USD", [])
            candidates = []
            for fact in values:
                if fact.get("form") not in allowed_forms or not fact.get("end"):
                    continue
                if annual:
                    if not fact.get("start"):
                        continue
                    try:
                        duration = (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days
                    except ValueError:
                        continue
                    if not 300 <= duration <= 380:
                        continue
                candidates.append(fact)
            if candidates:
                return max(candidates, key=lambda fact: (fact.get("filed", ""), fact["end"]))
    return None


def sec_basic_financials(cik: str, user_agent: str) -> dict[str, Any]:
    request = Request(
        SEC_COMPANY_FACTS_URL.format(cik=cik),
        headers={"User-Agent": user_agent, "Accept-Encoding": "identity"},
    )
    with urlopen(request, timeout=45) as response:  # noqa: S310 - fixed SEC URL
        facts = json.loads(response.read().decode("utf-8"))
    revenue_tags = ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues", "Revenue"]
    net_income_tags = ["NetIncomeLoss", "ProfitLoss"]
    ocf_tags = ["NetCashProvidedByUsedInOperatingActivities", "CashFlowsFromUsedInOperatingActivities"]
    revenue = sec_latest_fact(facts, revenue_tags, True)
    net_income = sec_latest_fact(facts, net_income_tags, True)
    operating_cash_flow = sec_latest_fact(facts, ocf_tags, True)
    total_assets = sec_latest_fact(facts, ["Assets"], False)
    candidates = [fact for fact in (revenue, net_income, operating_cash_flow, total_assets) if fact]
    source = "SEC Company Facts"
    if not candidates:
        revenue = sec_latest_fact(facts, revenue_tags, False, quarterly=True)
        net_income = sec_latest_fact(facts, net_income_tags, False, quarterly=True)
        operating_cash_flow = sec_latest_fact(facts, ocf_tags, False, quarterly=True)
        total_assets = sec_latest_fact(facts, ["Assets"], False, quarterly=True)
        candidates = [fact for fact in (revenue, net_income, operating_cash_flow, total_assets) if fact]
        source = "SEC Company Facts (latest quarterly fallback)"
    latest_year = max((int(fact.get("fy", 0)) for fact in candidates), default=None)
    latest_fact = max(candidates, key=lambda fact: fact.get("filed", ""), default={})
    return {
        "latest_fiscal_year": latest_year,
        "revenue": revenue.get("val") if revenue else None,
        "net_income": net_income.get("val") if net_income else None,
        "operating_cash_flow": operating_cash_flow.get("val") if operating_cash_flow else None,
        "total_assets": total_assets.get("val") if total_assets else None,
        "source": source,
        "source_accession_number": latest_fact.get("accn", ""),
        "source_filed_date": latest_fact.get("filed", ""),
        "status": "ok" if candidates else "no standard USD annual SEC facts found",
    }


def sec_annual_series(cik: str, user_agent: str) -> dict[int, dict[str, float | None]]:
    """Fetch up to three annual revenue, income, and OCF observations from SEC."""
    request = Request(SEC_COMPANY_FACTS_URL.format(cik=cik), headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    with urlopen(request, timeout=45) as response:  # noqa: S310 - fixed SEC URL
        facts = json.loads(response.read().decode("utf-8"))

    def metric(tags: list[str]) -> dict[int, float]:
        result: dict[int, float] = {}
        for namespace in ("us-gaap", "ifrs-full"):
            for tag in tags:
                for fact in facts.get("facts", {}).get(namespace, {}).get(tag, {}).get("units", {}).get("USD", []):
                    if fact.get("form") not in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"} or not fact.get("start") or not fact.get("fy"):
                        continue
                    try:
                        duration = (date.fromisoformat(fact["end"]) - date.fromisoformat(fact["start"])).days
                        year, amount = int(fact["fy"]), float(fact["val"])
                    except (KeyError, TypeError, ValueError):
                        continue
                    if 300 <= duration <= 380:
                        result.setdefault(year, amount)
        return result

    revenues = metric(["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues", "Revenue"])
    incomes = metric(["NetIncomeLoss", "ProfitLoss"])
    cashflows = metric(["NetCashProvidedByUsedInOperatingActivities", "CashFlowsFromUsedInOperatingActivities"])
    return {year: {"revenue": revenues.get(year), "net_income": incomes.get(year), "operating_cash_flow": cashflows.get(year)} for year in set(revenues) | set(incomes) | set(cashflows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--income-csv", type=Path, nargs="+", default=DEFAULT_INCOME_CSVS)
    parser.add_argument("--cashflow-csv", type=Path, nargs="+", default=DEFAULT_CASHFLOW_CSVS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIRECTORY)
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument(
        "--sec-user-agent",
        default="sp500-data-research example@example.com",
        help="Contact identification used for SEC fallback requests.",
    )
    args = parser.parse_args()

    if args.years < 1:
        parser.error("--years must be at least 1.")
    for path in [*args.income_csv, *args.cashflow_csv]:
        if not path.is_file():
            parser.error(f"Input file not found: {path}")

    print("Reading SimFin annual income and cash-flow data...")
    income = latest_statement_rows(read_simfin_csvs(args.income_csv))
    cashflow = latest_statement_rows(read_simfin_csvs(args.cashflow_csv))
    print("Downloading the current S&P 500 constituent list...")
    constituents = download_sp500_constituents()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    yearly_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, str]] = []

    for ticker, company in constituents.items():
        available_years = sorted(
            {year for candidate, year in income if candidate == ticker}
            | {year for candidate, year in cashflow if candidate == ticker},
            reverse=True,
        )
        company_rows: list[dict[str, Any]] = []
        missing_reasons: set[str] = set()

        for year in available_years:
            income_row = income.get((ticker, year))
            cashflow_row = cashflow.get((ticker, year))
            if not income_row:
                missing_reasons.add("income statement")
                continue
            if not cashflow_row:
                missing_reasons.add("cash-flow statement")
                continue
            revenue = value(income_row, "Revenue")
            operating_cash_flow = value(cashflow_row, "Net Cash from Operating Activities")
            capex_cash_flow = value(cashflow_row, "Change in Fixed Assets & Intangibles")
            if revenue is None:
                missing_reasons.add("revenue")
                continue
            if operating_cash_flow is None:
                missing_reasons.add("operating cash flow")
                continue
            if capex_cash_flow is None:
                missing_reasons.add("capital expenditure")
                continue
            free_cash_flow = operating_cash_flow + capex_cash_flow
            company_rows.append(
                {
                    **company,
                    "fiscal_year": year,
                    "revenue_usd": revenue,
                    "operating_cash_flow_usd": operating_cash_flow,
                    "capex_usd": abs(capex_cash_flow),
                    "free_cash_flow_usd": free_cash_flow,
                    "fcf_margin": free_cash_flow / revenue if revenue else None,
                }
            )
            if len(company_rows) == args.years:
                break

        if not company_rows:
            reason = ", ".join(sorted(missing_reasons)) or "no USD annual SimFin records"
            error_rows.append({**company, "status": f"missing {reason}"})
            continue

        yearly_rows.extend(company_rows)
        margins = [row["fcf_margin"] for row in company_rows if row["fcf_margin"] is not None]
        latest = company_rows[0]
        summary_rows.append(
            {
                **company,
                "years_found": len(company_rows),
                "latest_fiscal_year": latest["fiscal_year"],
                "latest_fcf_usd": latest["free_cash_flow_usd"],
                "latest_fcf_margin": latest["fcf_margin"],
                "average_fcf_usd": sum(row["free_cash_flow_usd"] for row in company_rows) / len(company_rows),
                "average_fcf_margin": sum(margins) / len(margins) if margins else None,
                "status": "ok" if len(company_rows) == args.years else "partial data",
            }
        )

    base_fields = ["ticker", "company", "sector", "industry"]
    write_csv(
        args.output_dir / "sp500_fcf_by_year.csv",
        yearly_rows,
        base_fields + ["fiscal_year", "revenue_usd", "operating_cash_flow_usd", "capex_usd", "free_cash_flow_usd", "fcf_margin"],
    )
    write_csv(
        args.output_dir / "sp500_fcf_summary.csv",
        summary_rows,
        base_fields + ["years_found", "latest_fiscal_year", "latest_fcf_usd", "latest_fcf_margin", "average_fcf_usd", "average_fcf_margin", "status"],
    )
    write_csv(args.output_dir / "sp500_fcf_errors.csv", error_rows, base_fields + ["status"])

    # Produce exactly one basic-information row per company (CIK), rather than
    # one per listed security. SimFin supplies first-choice values; SEC fills
    # gaps for companies absent from the downloaded SimFin exports.
    simfin_basics: dict[str, dict[str, Any]] = {}
    for ticker in constituents:
        years = sorted(
            {year for candidate, year in income if candidate == ticker}
            | {year for candidate, year in cashflow if candidate == ticker},
            reverse=True,
        )
        for year in years:
            income_row = income.get((ticker, year), {})
            cashflow_row = cashflow.get((ticker, year), {})
            basic = {
                "latest_fiscal_year": year,
                "revenue": value(income_row, "Revenue"),
                "net_income": value(income_row, "Net Income"),
                "operating_cash_flow": value(cashflow_row, "Net Cash from Operating Activities"),
                "total_assets": None,
                "source": "SimFin annual CSV",
                "source_accession_number": "",
                "source_filed_date": income_row.get("Publish Date", cashflow_row.get("Publish Date", "")),
                "status": "ok",
            }
            if any(basic[field] is not None for field in ("revenue", "net_income", "operating_cash_flow")):
                simfin_basics[ticker] = basic
                break

    companies_by_cik: dict[str, list[dict[str, str]]] = defaultdict(list)
    for company in constituents.values():
        companies_by_cik[company["cik"] or company["ticker"]].append(company)

    basic_rows: list[dict[str, Any]] = []
    for index, (cik, members) in enumerate(sorted(companies_by_cik.items()), start=1):
        primary = members[0]
        basic = next((simfin_basics.get(normalise_ticker(member["ticker"])) for member in members if simfin_basics.get(normalise_ticker(member["ticker"]))), None)
        if basic is None:
            print(f"SEC fallback [{index}/{len(companies_by_cik)}] {primary['company']}")
            try:
                time.sleep(0.13)
                basic = sec_basic_financials(cik, args.sec_user_agent)
            except Exception as error:  # retain a row even if a public request fails
                basic = {
                    "latest_fiscal_year": None,
                    "revenue": None,
                    "net_income": None,
                    "operating_cash_flow": None,
                    "total_assets": None,
                    "source": "SEC Company Facts",
                    "source_accession_number": "",
                    "source_filed_date": "",
                    "status": f"SEC fallback failed: {error}",
                }
        basic_rows.append(
            {
                "cik": cik,
                "ticker_symbols": ",".join(member["ticker"] for member in members),
                "company": primary["company"],
                "sector": primary["sector"],
                "industry": primary["industry"],
                **basic,
            }
        )
    write_csv(
        args.output_dir / "sp500_basic_financials.csv",
        basic_rows,
        [
            "cik", "ticker_symbols", "company", "sector", "industry",
            "latest_fiscal_year", "revenue", "net_income", "operating_cash_flow",
            "total_assets", "source", "source_accession_number", "source_filed_date", "status",
        ],
    )

    simfin_series: dict[str, dict[int, dict[str, float | None]]] = defaultdict(dict)
    for ticker in constituents:
        for year in {year for candidate, year in income if candidate == ticker} | {year for candidate, year in cashflow if candidate == ticker}:
            income_row, cashflow_row = income.get((ticker, year), {}), cashflow.get((ticker, year), {})
            record = {
                "revenue": value(income_row, "Revenue"),
                "net_income": value(income_row, "Net Income"),
                "operating_cash_flow": value(cashflow_row, "Net Cash from Operating Activities"),
            }
            if any(amount is not None for amount in record.values()):
                simfin_series[ticker][year] = record

    three_year_rows: list[dict[str, Any]] = []
    for index, (cik, members) in enumerate(sorted(companies_by_cik.items()), start=1):
        primary = members[0]
        series: dict[int, dict[str, float | None]] = {}
        for member in members:
            for year, record in simfin_series.get(normalise_ticker(member["ticker"]), {}).items():
                series.setdefault(year, record)
        source = "SimFin annual CSV"
        if len(series) < 3:
            print(f"SEC three-year fallback [{index}/{len(companies_by_cik)}] {primary['company']}")
            try:
                time.sleep(0.13)
                for year, record in sec_annual_series(cik, args.sec_user_agent).items():
                    series.setdefault(year, record)
                source = "SimFin annual CSV + SEC Company Facts"
            except Exception:
                source = "SimFin annual CSV"
        years = sorted(series, reverse=True)[:3]
        row: dict[str, Any] = {
            "cik": cik,
            "ticker_symbols": ",".join(member["ticker"] for member in members),
            "company": primary["company"],
            "sector": primary["sector"],
            "industry": primary["industry"],
            "source": source,
        }
        profitable_years = 0
        for slot in range(1, 4):
            record = series.get(years[slot - 1], {}) if slot <= len(years) else {}
            row[f"fiscal_year_{slot}"] = years[slot - 1] if slot <= len(years) else None
            for field in ("revenue", "net_income", "operating_cash_flow"):
                row[f"{field}_{slot}"] = record.get(field)
            if record.get("net_income") is not None and record["net_income"] > 0:
                profitable_years += 1
        row["profitable_years_last_3"] = profitable_years
        three_year_rows.append(row)
    three_year_fields = ["cik", "ticker_symbols", "company", "sector", "industry", "source"]
    for slot in range(1, 4):
        three_year_fields += [f"fiscal_year_{slot}", f"revenue_{slot}", f"net_income_{slot}", f"operating_cash_flow_{slot}"]
    write_csv(args.output_dir / "sp500_three_year_financials.csv", three_year_rows, three_year_fields + ["profitable_years_last_3"])
    print(f"Finished: {len(summary_rows)} companies processed; {len(error_rows)} need review.")
    print(f"Basic company rows: {len(basic_rows)}")
    print(f"Output directory: {args.output_dir}")


if __name__ == "__main__":
    main()
