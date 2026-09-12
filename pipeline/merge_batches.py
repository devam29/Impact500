"""Merge seed + all available batch CSVs into one master dataset.
Skips duplicate tickers (keeps first occurrence). Prints a summary."""
import csv
import glob
import os
import sys

DATA_DIR = r"C:\ETH_Zurich\ETH Zurich\ETHack\data"
OUT_PATH = os.path.join(DATA_DIR, "environmental_emissions_master.csv")

FIELDNAMES = ["ticker", "security", "data_source", "report_url",
              "scope1_tco2e", "scope2_location_tco2e", "scope2_market_tco2e",
              "scope1_base_year_end", "scope1_base_year_tco2e", "revenue_usd",
              "is_cdp_format", "notes"]

sources = [os.path.join(DATA_DIR, "environmental_emissions_raw.csv")]
sources += sorted(glob.glob(os.path.join(DATA_DIR, "batches", "batch_*.csv")))

seen = {}
order = []
per_file_counts = {}

for src in sources:
    if not os.path.exists(src):
        continue
    n = 0
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = row["ticker"].strip()
            if not t:
                continue
            n += 1
            if t not in seen:
                seen[t] = row
                order.append(t)
    per_file_counts[os.path.basename(src)] = n

with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    writer.writeheader()
    for t in order:
        writer.writerow(seen[t])

print(f"Wrote {len(order)} unique companies to {OUT_PATH}")
print()
print("Per-source row counts:")
for k, v in per_file_counts.items():
    print(f"  {k}: {v}")

print()
by_source = {}
for t in order:
    ds = seen[t]["data_source"]
    by_source[ds] = by_source.get(ds, 0) + 1
print("By data_source:")
for k, v in sorted(by_source.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
