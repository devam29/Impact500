"""Regression check: re-run the current extractor against every PDF
already cached in pdfs/, with zero new network calls. Run this after any
change to extract_emissions.py, before trusting it at scale -- compare
the output to what you'd expect (or to a prior run) to confirm you fixed
what you meant to fix without breaking anything that already worked."""
import glob
import os

from extract_emissions import extract

pdf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdfs")
for path in sorted(glob.glob(os.path.join(pdf_dir, "*.pdf"))):
    ticker = os.path.basename(path).replace(".pdf", "")
    try:
        fields = extract(path)
        got = [k for k in ("scope1_tco2e", "scope2_location_tco2e", "scope2_market_tco2e") if fields.get(k)]
        print(f"{ticker}: fmt={fields.get('is_cdp_format')} found={got or 'NONE'}")
    except Exception as e:
        print(f"{ticker}: ERROR {e}")
