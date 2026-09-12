"""
Shared, token-free extraction helper.

Given a local PDF (downloaded via requests), pull out Scope 1 / Scope 2
GHG figures using regex anchored to CDP question numbers (high confidence)
with a fallback to generic "Scope 1/2 ... metric tons" table patterns for
non-CDP sustainability reports (lower confidence).

Intentionally conservative: if a number can't be found with reasonable
confidence, the field is left blank rather than guessed. No numbers are
fabricated.
"""
import re
import fitz  # PyMuPDF


NUM = r"([\d,]+(?:\.\d+)?)"


def _to_float(s):
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def extract_pdf_text(path, max_pages=None):
    doc = fitz.open(path)
    pages = doc.page_count if max_pages is None else min(max_pages, doc.page_count)
    text = "\n".join(doc[i].get_text() for i in range(pages))
    doc.close()
    return text


def _value_after_label(text, label_pattern, window=400):
    """Find `label_pattern`, then look at the window of text up to the next
    CDP question number (or `window` chars, whichever is shorter) and
    return the LARGEST number found there.

    Why max-of-window instead of first-number-on-next-line: PDF text
    extraction sometimes interleaves a page-footer number (e.g. a lone
    "166") into the flow right at a page break, ahead of the real answer
    on the next line. A stray page number is always small; the real
    corporate emissions/revenue figure is not, so taking the max is a
    reliable way to skip the artifact without needing to special-case it.

    Why LAST match, not first: these CDP PDF exports open with a full
    table of contents that repeats every question's label text (often
    followed by dot-leaders and a page number, e.g. "...... 9"). The TOC
    always precedes the real answer section, so the last occurrence in
    the document is the actual answer."""
    matches = list(re.finditer(label_pattern, text, re.IGNORECASE))
    if not matches:
        return None
    m = matches[-1]
    tail = text[m.end():m.end() + window]
    next_q = re.search(r"\(\d+\.\d+(?:\.\d+)?\)", tail)
    if next_q:
        tail = tail[:next_q.start()]
    nums = [_to_float(n) for n in re.findall(NUM, tail)]
    nums = [n for n in nums if n is not None]
    return max(nums) if nums else None


def extract_cdp_fields(text):
    """High-confidence extraction anchored to CDP question numbers (7.6/7.7).
    Pattern confirmed against actual CDP PDF export layout: the question
    label is on its own line, and the numeric answer is on the next
    non-empty line (not inline with the label)."""
    out = {}

    v = _value_after_label(text, r"\(7\.6\.1\)\s*Gross global Scope 1 emissions \(metric tons CO2e\)")
    if v is not None:
        out["scope1_tco2e"] = v
        out["scope1_source_detail"] = "cdp_7.6.1"

    v = _value_after_label(text, r"\(7\.7\.1\)\s*Gross global Scope 2, location-based emissions \(metric tons CO2e\)")
    if v is not None:
        out["scope2_location_tco2e"] = v

    v = _value_after_label(text, r"\(7\.7\.2\)\s*Gross global Scope 2, market-based emissions \(metric tons CO2e\)")
    if v is not None:
        out["scope2_market_tco2e"] = v

    # Base year Scope 1 -- for velocity calc later. The label pair
    # "(7.5.1) Base year end" / "(7.5.2) Base year emissions (metric tons
    # CO2e)" recurs for EVERY category the company reports a base year
    # for -- Scope 1, Scope 2 location, Scope 2 market, and potentially
    # several Scope 3 categories -- in that order, so Scope 1's is
    # normally the first occurrence. But if a company's export doesn't
    # include an answer to 7.6.1 at all (CDP exports silently omit
    # unanswered questions), the first (7.5.1)/(7.5.2) pair in the
    # document then belongs to some OTHER category instead, and there is
    # no reliable way to tell from position alone. So: only trust this
    # first-match base year if we already found a Scope 1 headline
    # figure above -- otherwise leave it blank rather than risk
    # attributing the wrong category's base year to Scope 1.
    m = re.search(r"\(7\.5\.1\) Base year end", text, re.IGNORECASE) if out.get("scope1_tco2e") is not None else None
    if m:
        dm = re.search(r"\d{1,2}/\d{1,2}/\d{4}", text[m.end():m.end() + 200])
        if dm:
            out["scope1_base_year_end"] = dm.group(0)
    m = re.search(r"\(7\.5\.2\) Base year emissions \(metric tons CO2e\)", text, re.IGNORECASE) \
        if out.get("scope1_tco2e") is not None else None
    if m:
        tail = text[m.end():m.end() + 200]
        next_q = re.search(r"\(\d+\.\d+(?:\.\d+)?\)", tail)
        if next_q:
            tail = tail[:next_q.start()]
        nums = [n for n in (_to_float(x) for x in re.findall(NUM, tail)) if n is not None]
        if nums:
            out["scope1_base_year_tco2e"] = max(nums)

    # Annual revenue, question 1.4.1
    v = _value_after_label(text, r"\(1\.4\.1\) What is your organization.s annual revenue for the reporting period\?")
    if v is not None:
        out["revenue_usd"] = v

    return out


def extract_cdp_compact_fields(text):
    """Alternate 'new-generation' CDP export layout, confirmed against real
    2024/2025-cycle exports (Bank of America, Cisco, Dominion Energy,
    Autodesk, C.H. Robinson, Bristol Myers Squibb): the question headers
    omit the sub-part suffix -- "(7.6)" / "(7.7)" instead of "(7.6.1)" /
    "(7.7.1)"/"(7.7.2)" -- and Scope 2's location- and market-based labels
    are both listed together, with their two values appearing as a
    consecutive pair (in label order: location then market) beneath a
    shared "Reporting year" row, rather than as two separately-labeled
    sub-answers. Only used as a fallback when the (7.6.1)-anchored parse
    above finds nothing, so it never overrides the more specific format."""
    out = {}

    def _nums_after_reporting_year(m_end, span=800):
        """Bound to the next question marker, find the 'Reporting year'
        row, and collect the run of purely-numeric lines immediately
        following it. Deliberately NOT a max-of-window search here: these
        blocks also carry prior-year comparison data ('Past year 1', ...)
        further down, whose value can exceed the current reporting year's
        own figure (confirmed real case: Bristol Myers Squibb, where
        Past year 1 = 208,534 > current year 206,726) -- taking the max
        would silently grab the wrong year. The numbers immediately after
        'Reporting year' and before the next non-numeric line are always
        the current-year answer(s)."""
        tail = text[m_end:m_end + span]
        next_q = re.search(r"\(\d+\.\d+(?:\.\d+)?\)", tail)
        if next_q:
            tail = tail[:next_q.start()]
        ry = re.search(r"Reporting year", tail, re.IGNORECASE)
        window = tail[ry.end():] if ry else tail
        nums = []
        for line in window.split("\n"):
            s = line.strip()
            if not s:
                continue
            if re.fullmatch(r"[\d,]+(?:\.\d+)?", s):
                nums.append(_to_float(s))
            else:
                break
        return nums

    # Whitespace between words is \s+, not a literal space: PDF line-wrap
    # can break the question text mid-sentence at an arbitrary point
    # (confirmed real case: Devon Energy's 2024 CDP export wraps this
    # exact sentence as "...in metric tons \nCO2e?", which a literal-space
    # pattern never matches -- silently yielding nothing despite the
    # question being answered right there in the document).
    matches = list(re.finditer(
        r"\(7\.6\)\s+What\s+were\s+your\s+organization.s\s+gross\s+global\s+Scope\s+1\s+emissions\s+in\s+metric\s+tons\s+CO2e\?",
        text, re.IGNORECASE))
    if matches:
        nums = _nums_after_reporting_year(matches[-1].end())
        if nums:
            out["scope1_tco2e"] = nums[0]
            out["scope1_source_detail"] = "cdp_7.6_compact"

    matches = list(re.finditer(
        r"\(7\.7\)\s+What\s+were\s+your\s+organization.s\s+gross\s+global\s+Scope\s+2\s+emissions\s+in\s+metric\s+tons\s+CO2e\?",
        text, re.IGNORECASE))
    if matches:
        nums = _nums_after_reporting_year(matches[-1].end())
        if len(nums) >= 1:
            out["scope2_location_tco2e"] = nums[0]
        if len(nums) >= 2:
            out["scope2_market_tco2e"] = nums[1]

    return out


def extract_cdp_2025_fields(text):
    """CDP's 2025-cycle 'Integrated Questionnaire' export layout,
    confirmed against a real export (FedEx): question markers drop the
    parentheses entirely -- "Q7.6" / "Q7.7" instead of "(7.6)" -- and the
    answer sits a further label-line below "Reporting year" rather than
    immediately after it:
        Q7.6 What were your organization's gross global Scope 1
        emissions in metric tons CO2e?
        Response 1: Reporting year
        Gross global Scope 1 emissions (metric tons CO2e)
        14842148
    Only used as a further fallback when neither the dot-suffixed nor
    compact parse above finds anything."""
    out = {}

    def _value_after(question_pattern, label_pattern, window=2000):
        qm = list(re.finditer(question_pattern, text, re.IGNORECASE))
        if not qm:
            return None
        tail = text[qm[-1].end():qm[-1].end() + window]
        m = re.search(label_pattern + r"\s*\n\s*" + NUM, tail, re.IGNORECASE)
        return _to_float(m.group(1)) if m else None

    v = _value_after(
        r"Q7\.6\s+What\s+were\s+your\s+organization.s\s+gross\s+global\s+Scope\s+1\s+emissions\s+in\s+metric\s+tons\s+CO2e\?",
        r"Gross global Scope 1 emissions \(metric tons CO2e\)")
    if v is not None:
        out["scope1_tco2e"] = v
        out["scope1_source_detail"] = "cdp_Q7.6_2025"

    scope2_question = r"Q7\.7\s+What\s+were\s+your\s+organization.s\s+gross\s+global\s+Scope\s+2\s+emissions\s+in\s+metric\s+tons\s+CO2e\?"
    v = _value_after(scope2_question, r"Gross global Scope 2, location-based emissions \(metric tons CO2e\)")
    if v is not None:
        out["scope2_location_tco2e"] = v
    v = _value_after(scope2_question, r"Gross global Scope 2, market-based emissions \(metric tons CO2e\)")
    if v is not None:
        out["scope2_market_tco2e"] = v

    return out


def extract_cdp_old_fields(text):
    """CDP's pre-2024 questionnaire cycle uses lettered section numbers
    (C6.1, C6.3, ...) instead of the current plain-decimal scheme (7.6.1,
    7.7.1). Layout confirmed against a real 2023-cycle export:
        (C6.1) What were your organization's gross global Scope 1
        emissions in metric tons CO2e?
        Reporting year
        Gross global Scope 1 emissions (metric tons CO2e)
        6,568
        ...
        (C6.3) What were your organization's gross global Scope 2
        emissions in metric tons CO2e?
        Reporting year
        Scope 2, location-based
        57,168
        Scope 2, market-based (if applicable)
        22,936
    Scoped to the C6.3 answer block specifically (up to the next C6.x
    question) so the location/market labels here can't accidentally match
    the unrelated "Scope 2, location-based" mention inside C6.2's
    free-text answer earlier in the document."""
    out = {}

    v = _value_after_label(text, r"Gross global Scope 1 emissions \(metric tons CO2e\)")
    if v is not None:
        out["scope1_tco2e"] = v
        out["scope1_source_detail"] = "cdp_old_C6.1"

    m = re.search(r"\(C6\.3\)", text)
    if m:
        end = text.find("(C6.4)", m.end())
        window = text[m.end(): end if end != -1 else m.end() + 800]
        lm = re.search(r"Scope 2, location-based\s*\n\s*" + NUM, window)
        if lm:
            out["scope2_location_tco2e"] = _to_float(lm.group(1))
        mm = re.search(r"Scope 2, market-based[^\n]*\n\s*" + NUM, window)
        if mm:
            out["scope2_market_tco2e"] = _to_float(mm.group(1))

    return out


def _last_of_number_run(text, label_pattern, window=300):
    """Non-CDP sustainability/SASB reports commonly present a multi-year
    table as: '<label>\\n<year1 value>\\n<year2 value>\\n...\\n<latest
    value>\\n<next label>'. The numbers run consecutively, one per line,
    immediately after the label, until a non-numeric line (the next row's
    label) ends the run. The LAST number in that run is the most recent
    year, since these tables are conventionally sorted oldest->newest."""
    m = re.search(label_pattern, text, re.IGNORECASE)
    if not m:
        return None
    tail = text[m.end():m.end() + window]
    nums = []
    for line in tail.split("\n"):
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"[\d,]+(?:\.\d+)?", s):
            nums.append(_to_float(s))
        else:
            break
    return nums[-1] if nums else None


def _first_number_after(text, label_pattern, window=100):
    """Some non-CDP reports state the unit ('MTCO2e') once in a table's
    column header instead of repeating 'metric tons CO2e' next to every
    row label (confirmed real case: CoStar Group's 2024 ESG report
    appendix, which reads 'Sub-Total Scope 1 \\n 3,139 \\n 2.4% \\n 3,025 \\n
    3.1%' -- current year then prior year, with no unit text anywhere near
    the label). _last_of_number_run's same-line unit requirement misses
    this entirely, and its number-RUN approach doesn't apply either since
    the run breaks after one value (the very next line is a '%', not
    another bare number). This just takes the first number immediately
    after the label -- correct here because these tables are always
    current-year-first, and matches the existing bug-fixed convention
    elsewhere in this file of preferring 'first after label' over 'max of
    window' specifically to avoid grabbing a prior-year figure."""
    matches = list(re.finditer(label_pattern, text, re.IGNORECASE))
    if not matches:
        return None
    tail = text[matches[-1].end():matches[-1].end() + window]
    m = re.search(NUM, tail)
    return _to_float(m.group(1)) if m else None


def extract_generic_fields(text):
    """Best-effort fallback for non-CDP sustainability/SASB reports. Lower
    confidence than the CDP path -- caller tags these rows accordingly.
    Tries, in order: (1) a labelled multi-year table row (unit given on
    the same line), (2) a labelled table row where the unit is only given
    once in a column header ('Sub-Total Scope N' style), (3) a lone
    'NUMBER metric tons CO2e' phrase (single-value SASB-style disclosure)."""
    out = {}

    table_labels = [
        (r"Scope\s*1[^\n]{0,40}?(?:Metric Tons|metric tons)\s*CO2e", "scope1_tco2e"),
        (r"Scope\s*2[^\n]{0,25}?location-based[^\n]{0,25}?(?:Metric Tons|metric tons)\s*CO2e", "scope2_location_tco2e"),
        (r"Scope\s*2[^\n]{0,25}?market-based[^\n]{0,25}?(?:Metric Tons|metric tons)\s*CO2e", "scope2_market_tco2e"),
    ]
    for pattern, key in table_labels:
        v = _last_of_number_run(text, pattern)
        if v is not None:
            out[key] = v

    sub_total_labels = [
        (r"Sub-Total Scope 1\b", "scope1_tco2e"),
        (r"Sub-Total Scope 2\s*\(Location-based\)", "scope2_location_tco2e"),
        (r"Sub-Total Scope 2\s*\(Market-based\)", "scope2_market_tco2e"),
    ]
    for pattern, key in sub_total_labels:
        if key not in out:
            v = _first_number_after(text, pattern)
            if v is not None:
                out[key] = v

    # Some "Key data and frameworks" / performance-summary tables abbreviate
    # the unit to "(MTCO2e)" right in the row label instead of spelling out
    # "metric tons CO2e" -- confirmed real case: Lam Research's 2024 Impact
    # Frameworks report, e.g. "Scope 1 emissions (MTCO2e) \n 91,681 \n -52%
    # \n 189,537 \n 457,174" (current year, YoY%, then two prior years).
    # Deliberately using _last_of_number_run, NOT _first_number_after, even
    # though Lam's own table is current-year-first: tested against every
    # cached PDF and found a second company (Incyte) using the exact same
    # "(MTCO2e)" label style for a table that is oldest-year-first instead
    # ("Scope 1 emissions (MTCO2e) Total \n 4,775 \n 8,062 \n 9,351 \n
    # 9,576" for 2019/2022/2023/2024) -- first-number would have silently
    # grabbed 2019's figure there. _last_of_number_run gets both right: for
    # Incyte's plain ascending run it correctly returns the last (most
    # recent) value, and for Lam's table the run still terminates after
    # just one number anyway, since "-52%" isn't a bare numeric line -- so
    # the "last of the run" is the same single current-year value either
    # way. No way to tell the two table orderings apart from the label
    # alone, so lean on the run-termination behavior instead of guessing.
    mtco2e_labels = [
        (r"Scope\s*1 emissions\s*\(MTCO2e\)", "scope1_tco2e"),
        (r"Scope\s*2 emissions location-based\s*\(MTCO2e\)", "scope2_location_tco2e"),
        (r"Scope\s*2 emissions market-based\s*\(MTCO2e\)", "scope2_market_tco2e"),
    ]
    for pattern, key in mtco2e_labels:
        if key not in out:
            v = _last_of_number_run(text, pattern)
            if v is not None:
                out[key] = v

    # Inline colon-sentence form, e.g. "Scope 1 Direct GHG Emissions:
    # 4,259,842 Metric Tons CO2 Eq" -- confirmed real case: CSX's 2024
    # Sustainability Data Supplement. Highest confidence of the generic
    # patterns since the value sits right next to its label with no
    # positional guessing involved.
    colon_labels = [
        (r"Scope\s*1[^\n:]{0,40}:\s*" + NUM + r"\s*Metric Tons\s*CO2\s*Eq", "scope1_tco2e"),
        (r"Scope\s*2[^\n:]{0,60}Location-Based:\s*" + NUM + r"\s*Metric Tons\s*CO2\s*Eq", "scope2_location_tco2e"),
        (r"Scope\s*2[^\n:]{0,60}Market-Based:\s*" + NUM + r"\s*Metric Tons\s*CO2\s*Eq", "scope2_market_tco2e"),
    ]
    for pattern, key in colon_labels:
        if key not in out:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                out[key] = _to_float(m.group(1))

    # Same inline-colon idea, different real-world phrasing -- "Scope 1
    # GHG emissions: 41,913 metric tons CO2e" / "Scope 2 (location-based)
    # GHG emissions: 56,377 metric tons CO2e" -- confirmed real case:
    # Humana's 2025 Impact Report Appendix. Unit is lowercase "metric
    # tons CO2e" (not "Metric Tons CO2 Eq" like the CSX pattern above),
    # and the location/market qualifier sits in parentheses BEFORE "GHG
    # emissions" rather than right before the colon, so needs its own
    # pattern rather than reusing colon_labels above.
    ghg_colon_labels = [
        (r"Scope\s*1\s*GHG emissions:\s*" + NUM + r"\s*metric tons\s*CO2e", "scope1_tco2e"),
        (r"Scope\s*2\s*\(location-based\)\s*GHG emissions:\s*" + NUM + r"\s*metric tons\s*CO2e", "scope2_location_tco2e"),
        (r"Scope\s*2\s*\(market-based\)\s*GHG emissions:\s*" + NUM + r"\s*metric tons\s*CO2e", "scope2_market_tco2e"),
    ]
    for pattern, key in ghg_colon_labels:
        if key not in out:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                out[key] = _to_float(m.group(1))

    # NOTE: a table-form fallback using _last_of_number_run_after_unit_line
    # (skip one non-numeric "unit" line below the label, then take the
    # last of the following number run) was tried here and reverted --
    # tested against every cached PDF, it also matched incidental prose
    # mentions of "Scope 2 ... location-based/market-based" in OTHER
    # companies' reports (BAX, BLK, BNY, C, CNC) with no reliable way to
    # tell a real data-table row from a sentence in the general case, and
    # separately, reports that state units as "thousands of metric tons"
    # in a column header far above the row (confirmed real case: Baxter)
    # would silently extract a value 1000x too small since this approach
    # never inspects the unit text itself. Left unhandled rather than
    # risk a wrong number -- see the file-level "never fabricate" note.

    if "scope1_tco2e" not in out:
        m = re.search(r"Gross global Scope 1 emissions[^\n]{0,80}\n+\s*" + NUM
                       + r"\s*metric tons\s*CO₂?e", text, re.IGNORECASE)
        if m:
            out["scope1_tco2e"] = _to_float(m.group(1))

    # GRI content indices commonly cite the standardized GRI-305-1 /
    # GRI-305-2 codes (GRI's own fixed numbering for Scope 1 / Scope 2
    # emissions disclosures -- not company-specific phrasing, so this is
    # expected to recur widely) with the row's value ending in a bare
    # "MT" unit shortly after -- confirmed real case: Darden Restaurants'
    # 2023 Environmental Disclosure Table, e.g. 'GRI-305-1 \n Scope 1
    # CO2e Emissions \n FY22 \n 345,316 \n MT'. Anchoring on "<number> MT"
    # rather than position alone avoids matching a stray page number in
    # a table-of-contents mention of the same code. GRI-305-2 doesn't
    # distinguish location- vs market-based here (Darden's table gives
    # one combined figure, no market-based mention anywhere in the doc),
    # so it's recorded as location-based per GRI's baseline/mandatory
    # disclosure requirement.
    gri_codes = [
        (r"GRI-305-1\b", "scope1_tco2e"),
        (r"GRI-305-2\b", "scope2_location_tco2e"),
    ]
    for pattern, key in gri_codes:
        if key not in out:
            matches = list(re.finditer(pattern, text))
            if matches:
                tail = text[matches[-1].end():matches[-1].end() + 200]
                m = re.search(NUM + r"\s*\n?\s*MT\b", tail)
                if m:
                    out[key] = _to_float(m.group(1))

    if "scope1_tco2e" not in out:
        # SASB cross-reference indices commonly fill in the "Reference"
        # column for the Scope 1 accounting metric (EM-CM-110a.1 and
        # equivalents in other SASB industry standards) with an
        # auto-generated sentence of the exact form "Total Gross global
        # Scope 1 emissions reported are <N> tonnes" -- confirmed real
        # case: CRH plc's 2025 Sustainability Performance Report SASB
        # table. Precise (not rounded/abbreviated like the "26.9m" figures
        # in this same report's multi-year table), so preferred when
        # present. Deliberately not extending this to Scope 2: SASB's
        # Construction-Materials-style standards only mandate this exact
        # phrasing for Scope 1, so there's no equivalent Scope 2 sentence
        # to anchor to, and guessing one risks a false match.
        m = re.search(r"Total Gross global Scope 1 emissions reported are\s*" + NUM + r"\s*tonnes",
                       text, re.IGNORECASE)
        if m:
            out["scope1_tco2e"] = _to_float(m.group(1))

    return out


def extract(path):
    """Returns dict with whatever fields were found, plus 'extraction_method'.

    Format detection is deliberately broad: many companies re-title their
    CDP export (e.g. "Aon CDP Climate Change Questionnaire Responses"
    instead of literally "CDP Corporate Questionnaire"), so relying on
    that one phrase alone under-detects. The presence of the
    question-number markers themselves ("(7.6.1)" for the current cycle,
    "(C6.1)" for pre-2024 cycles) is a much more specific and reliable
    signal, since arbitrary non-CDP reports essentially never contain
    those exact tokens."""
    text = extract_pdf_text(path)

    is_new_cdp = bool(re.search(r"CDP Corporate Questionnaire", text, re.IGNORECASE)
                       or "(7.6.1)" in text
                       or re.search(r"\(7\.6\) What were your organization.s gross global Scope 1", text, re.IGNORECASE))
    is_old_cdp = "(C6.1)" in text

    if is_new_cdp:
        fields = extract_cdp_fields(text)
        fields["extraction_method"] = "cdp_pdf"
        if not fields.get("scope1_tco2e") or not fields.get("scope2_location_tco2e"):
            fields.update({k: v for k, v in extract_cdp_compact_fields(text).items() if not fields.get(k)})
        if not fields.get("scope1_tco2e") or not fields.get("scope2_location_tco2e"):
            fields.update({k: v for k, v in extract_cdp_2025_fields(text).items() if not fields.get(k)})
        if not fields.get("scope1_tco2e"):
            fields.update({k: v for k, v in extract_generic_fields(text).items() if k not in fields})
    elif is_old_cdp:
        fields = extract_cdp_old_fields(text)
        fields["extraction_method"] = "cdp_pdf_old_format"
        if not fields.get("scope1_tco2e"):
            fields.update({k: v for k, v in extract_generic_fields(text).items() if k not in fields})
    else:
        fields = extract_generic_fields(text)
        fields["extraction_method"] = "sustainability_report"

    fields["is_cdp_format"] = "new" if is_new_cdp else ("old" if is_old_cdp else False)
    return fields


if __name__ == "__main__":
    import sys
    result = extract(sys.argv[1])
    for k, v in result.items():
        print(f"{k}: {v}")
