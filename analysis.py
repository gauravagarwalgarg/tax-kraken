import argparse
import csv
import html
import json
import math
import re
import statistics
from pathlib import Path


try:
    import pdfplumber
except Exception:  # pragma: no cover - handled at runtime
    pdfplumber = None


ROOT_DIR = Path(__file__).resolve().parent

METRICS = [
    "salary",
    "gross_salary",
    "business_income",
    "other_sources_income",
    "short_term_capital_gains",
    "long_term_capital_gains",
    "interest_income",
    "dividend_income",
    "special_income",
    "gross_total_income",
    "deductions",
    "total_income",
    "tax_payable_on_total_income",
    "total_income_tax_paid",
]

DISPLAY_NAMES = {
    "salary": "Salary",
    "gross_salary": "Gross Salary",
    "business_income": "Business Income",
    "other_sources_income": "Other Sources",
    "short_term_capital_gains": "STCG",
    "long_term_capital_gains": "LTCG",
    "interest_income": "Interest",
    "dividend_income": "Dividend",
    "special_income": "Special Income",
    "gross_total_income": "Gross Total Income",
    "deductions": "Deductions",
    "total_income": "Total Income",
    "tax_payable_on_total_income": "Tax Payable",
    "total_income_tax_paid": "Tax Paid",
}

CORE_CHART_METRICS = [
    "gross_total_income",
    "total_income",
    "business_income",
    "gross_salary",
    "interest_income",
    "short_term_capital_gains",
    "long_term_capital_gains",
    "dividend_income",
    "total_income_tax_paid",
]


def inr(value):
    return f"Rs {int(round(value or 0)):,.0f}"


def parse_amount(value):
    if value is None:
        return None
    cleaned = str(value).replace(",", "").replace("Rs.", "").replace("Rs", "").strip()
    cleaned = re.sub(r"[^\d\-.]", "", cleaned)
    if cleaned in {"", "-", "."}:
        return None
    try:
        return int(round(float(cleaned)))
    except ValueError:
        return None


def normalize_space(text):
    return " ".join((text or "").replace("\u2013", "-").replace("\u2014", "-").split())


def amount_pattern():
    return r"(-?[\d,]+)"


def first_amount(text, patterns, flags=re.I):
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            value = parse_amount(match.group(1))
            if value is not None:
                return value
    return None


def last_amount(text, patterns, flags=re.I):
    values = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags):
            value = parse_amount(match.group(1))
            if value is not None:
                values.append((match.start(), value))
    if not values:
        return None
    return sorted(values)[-1][1]


def line_amount(lines, include, exclude=None, lookahead=1, first=False):
    exclude = exclude or []
    found = None
    for idx, line in enumerate(lines):
        low = line.lower()
        if all(token.lower() in low for token in include) and not any(token.lower() in low for token in exclude):
            nums = re.findall(r"-?[\d,]+", line)
            if not nums and lookahead:
                window = " ".join(lines[idx + 1 : idx + lookahead + 1])
                nums = re.findall(r"-?[\d,]+", window)
            parsed = [parse_amount(num) for num in nums]
            parsed = [num for num in parsed if num is not None]
            if parsed:
                if first:
                    return parsed[-1]
                found = parsed[-1]
    return found


def line_amount_any(lines, rules, first=False):
    for include, exclude, lookahead in rules:
        value = line_amount(lines, include, exclude, lookahead, first=first)
        if value is not None:
            return value
    return None


def extract_pdf_text(pdf_path):
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is required. Install dependencies with `pip install -r requirements.txt`.")
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def financial_year_from_path(pdf_path):
    match = re.search(r"(20\d{2})-(\d{2})", pdf_path.stem)
    if not match:
        raise ValueError(f"PDF name must contain a financial year like 2024-25: {pdf_path.name}")
    return match.group(0)


def assessment_year_from_fy(financial_year):
    start = int(financial_year[:4]) + 1
    return f"{start}-{str(start + 1)[-2:]}"


def detect_form(text):
    one = normalize_space(text)
    patterns = [
        r"\bITR[- ]?([1-7])\b",
        r"\bITR([1-7])\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, one, re.I)
        if match:
            suffix = " SUGAM" if re.search(r"SUGAM", one, re.I) else ""
            return f"ITR-{match.group(1)}{suffix}"
    return "Not clearly visible in extracted text"


def detect_taxpayer(text):
    one = normalize_space(text)
    name_match = re.search(r"(?:Name|First Name Middle Name Last Name)\s+([A-Z][A-Z ]{5,80}?)\s+(?:PAN|Permanent Account|AFZP|ADAP)", one)
    pan_match = re.search(r"\b([A-Z]{5}\d{4}[A-Z])\b", one)
    return {
        "taxpayer_name": name_match.group(1).strip() if name_match else "",
        "pan_masked": mask_pan(pan_match.group(1)) if pan_match else "",
    }


def mask_pan(pan):
    if not pan or len(pan) != 10:
        return ""
    return f"{pan[:3]}XXXX{pan[-1]}"


def extract_metric_values(text):
    one = normalize_space(text)
    lines = [normalize_space(line) for line in text.splitlines() if normalize_space(line)]
    amount = amount_pattern()

    gross_salary = line_amount_any(
        lines,
        [
            (["Gross Salary"], [], 0),
            (["B2", "Gross Salary"], [], 0),
        ],
    )
    if gross_salary is None:
        gross_salary = last_amount(
        one,
        [
            rf"Gross Salary(?:\s*\([^)]*\))?\s*(?:i|1|B2)?\s*{amount}",
            rf"B2\s+i\s+Gross Salary(?:\s*\([^)]*\))?\s+i\s*{amount}",
        ],
        )
    salary = line_amount_any(
        lines,
        [
            (["Salaries", "Schedule S"], [], 0),
            (["Income from Salary", "Pension"], [], 0),
            (["Income chargeable under the head", "Salaries"], [], 0),
            (["Net Salary"], [], 0),
        ],
    )
    if salary is None:
        salary = last_amount(
        one,
        [
            rf"Income chargeable under the head ['\u2018]?Salaries['\u2019]?\s*(?:\(.*?\))?\s*B2\s*{amount}",
            rf"Salaries\s*\([^)]*Schedule S[^)]*\)\s*1\s*{amount}",
            rf"Income from Salary\s*/\s*Pension.*?(?:B2|1)?\s*{amount}",
            rf"B1Income from Salary\s*/\s*Pension.*?1\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    if salary is None:
        salary = gross_salary or 0
    if gross_salary is None:
        gross_salary = salary

    business_income = line_amount_any(
        lines,
        [
            (["Income from Business", "Profession"], [], 0),
            (["B1Income from Business"], [], 0),
            (["Income chargeable", "Business", "Profession"], [], 0),
        ],
    )
    if business_income is None:
        business_income = last_amount(
        one,
        [
            rf"Income from Business\s*&\s*Profession(?:\s*\([^)]*\))?\s*(?:B1)?\s*{amount}",
            rf"Income from Business\s*\(.*?\)\s*1\s*{amount}",
            rf"B1Income from Business.*?1\s*{amount}",
            rf"Income chargeable under (?:the head )?['\u2018]?Business or Profession.*?(?:E8)?\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    business_income = business_income or 0

    other_sources_income = line_amount_any(
        lines,
        [
            (["Income from Other Sources"], [], 0),
            (["Net Income from Other sources"], [], 1),
            (["from sources other than from owning race horses"], [], 1),
            (["Gross amount chargeable to tax at normal applicable rates"], [], 0),
        ],
    )
    if other_sources_income is None:
        other_sources_income = last_amount(
        one,
        [
            rf"Income from Other Sources\s*(?:\(.*?\))?\s*(?:B4|4a|5a|3a)?\s*{amount}",
            rf"Net Income from Other sources chargeable to tax at Normal Applicable rates.*?(?:4a|5a)\s*{amount}",
            rf"from sources other than from owning race horses.*?(?:4a|5a|3a)\s*{amount}",
        ],
        flags=re.I | re.S,
        )

    stcg = line_amount_any(
        lines,
        [
            (["Total Short", "term"], [], 0),
            (["Total short-term"], [], 0),
        ],
    )
    if stcg is None:
        stcg = last_amount(
        one,
        [
            rf"Total Short[- ]?term.*?(?:3av|4av|4aiv|3aiv|3aiii|A7|A8|A9|av)\s*{amount}",
            rf"Total short-term.*?(?:3av|4av|4aiv|3aiv|3aiii|av)\s*{amount}",
            rf"Short[- ]term chargeable @\s*15%.*?(?:ai|4ai|3ai)\s*{amount}",
            rf"Short-term Capital Gain \(15%\).*?(?:3ai)\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    stcg = stcg or 0

    ltcg = line_amount_any(
        lines,
        [
            (["Total Long", "term"], [], 0),
            (["Total long term capital gain"], [], 0),
        ],
    )
    if ltcg is None:
        ltcg = last_amount(
        one,
        [
            rf"Total Long[- ]term.*?(?:3biv|4biv|4biii|3biii|B9|B10|B13|biv)\s*{amount}",
            rf"Total long term capital gain.*?(?:B9|B10|B13)\s*{amount}",
            rf"Long-term chargeable @\s*10%.*?(?:bi|4bi|3bi)\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    ltcg = ltcg or 0

    interest_income = line_amount_any(
        lines,
        [
            (["Interest", "Gross"], [], 0),
            (["Interest Gross"], [], 0),
        ],
    )
    if interest_income is None:
        interest_income = last_amount(
        one,
        [
            rf"Interest,?\s*Gross.*?(?:1b|B)?\s*{amount}",
            rf"Interest Gross.*?(?:1b)?\s*{amount}",
            rf"Interest from Saving Account.*?{amount}",
            rf"Interest from Saving Bank\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    dividend_income = line_amount_any(
        lines,
        [
            (["Dividend", "Gross"], [], 0),
            (["Dividends", "Gross"], [], 0),
        ],
    )
    if dividend_income is None:
        dividend_income = last_amount(
        one,
        [
            rf"Dividends?,?\s*Gross.*?(?:1a|A)?\s*{amount}",
            rf"Dividend Gross.*?(?:1a)?\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    dividend_income = dividend_income or 0

    gross_total_income = line_amount_any(
        lines,
        [
            (["Gross Total Income"], ["PART B"], 2),
            (["Gross Total income"], ["PART B"], 2),
        ],
        first=True,
    )
    if gross_total_income is None:
        gross_total_income = last_amount(
        one,
        [
            rf"Gross Total Income.*?(?:B5|4|5|8|9|10)?\s*{amount}",
            rf"Gross Total income.*?(?:B5|4|5|8|9|10)?\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    deductions = line_amount_any(
        lines,
        [
            (["Total deductions"], [], 0),
            (["Total Deductions"], [], 0),
            (["Deductions under Chapter VI-A"], [], 0),
        ],
        first=True,
    )
    if deductions is None:
        deductions = last_amount(
        one,
        [
            rf"Total deductions.*?(?:C18|C19|C20|B6)?\s*{amount}",
            rf"Total Deductions.*?(?:C18|C19|C20|B6)?\s*{amount}",
            rf"Deductions under Chapter VI-A.*?(?:10|11|12a|12c)?\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    deductions = deductions or 0
    total_income = line_amount_any(
        lines,
        [
            (["Taxable Total Income"], [], 0),
            (["Total income"], ["Gross", "included", "outside", "deemed", "Tax payable"], 0),
        ],
        first=True,
    )
    if total_income is None:
        total_income = last_amount(
        one,
        [
            rf"Taxable Total Income.*?(?:C19|C20|C21|B7)?\s*{amount}",
            rf"Total income\s*\(.*?\)\s*(?:11|12|13|14)?\s*{amount}",
            rf"Total Income as per item.*?\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    tax_payable = line_amount_any(
        lines,
        [
            (["Tax payable on total income"], [], 0),
            (["Tax Payable on Total Income"], [], 0),
        ],
        first=True,
    )
    if tax_payable is None:
        tax_payable = last_amount(
        one,
        [
            rf"Tax payable on total income.*?(?:D1|1d|2d)?\s*{amount}",
            rf"Tax Payable on Total Income.*?(?:D1|1d|2d)?\s*{amount}",
        ],
        flags=re.I | re.S,
        )
    tax_payable = tax_payable or 0
    tax_paid = line_amount_any(
        lines,
        [
            (["Total Taxes Paid"], ["outside", "foreign"], 0),
            (["Total taxes paid"], ["outside", "foreign"], 0),
        ],
        first=True,
    )
    if tax_paid is None:
        tax_paid = last_amount(
        one,
        [
            rf"Total Taxes Paid.*?(?:D17|8d|10e|11d|15e|D18)?\s*{amount}",
            rf"Total taxes paid.*?{amount}",
        ],
        flags=re.I | re.S,
        )
    tax_paid = tax_paid or 0

    if other_sources_income is None:
        other_sources_income = interest_income or 0
    if interest_income is None:
        interest_income = other_sources_income
    component_total = salary + business_income + stcg + ltcg + other_sources_income
    if gross_total_income is None or (gross_total_income < 10000 and component_total > 100000):
        gross_total_income = component_total
    residual_salary = gross_total_income - (business_income + stcg + ltcg + other_sources_income)
    if gross_salary < 1000 and residual_salary > 10000:
        salary = residual_salary
        gross_salary = residual_salary
    if total_income is None:
        total_income = max(gross_total_income - deductions, 0)
    if total_income < 10000 and gross_total_income > 100000:
        total_income = max(gross_total_income - deductions, 0)

    special_income = stcg + ltcg

    return {
        "salary": salary,
        "gross_salary": gross_salary,
        "business_income": business_income,
        "other_sources_income": other_sources_income,
        "short_term_capital_gains": stcg,
        "long_term_capital_gains": ltcg,
        "interest_income": interest_income,
        "dividend_income": dividend_income,
        "special_income": special_income,
        "gross_total_income": gross_total_income,
        "deductions": deductions,
        "total_income": total_income,
        "tax_payable_on_total_income": tax_payable,
        "total_income_tax_paid": tax_paid,
    }


def extraction_warnings(row):
    warnings = []
    component_total = (
        row["salary"]
        + row["business_income"]
        + row["short_term_capital_gains"]
        + row["long_term_capital_gains"]
        + row["other_sources_income"]
    )
    if row["gross_total_income"] and abs(component_total - row["gross_total_income"]) > 1000:
        warnings.append(
            "Income components do not fully reconcile to gross total income; inspect source PDF."
        )
    if row["gross_total_income"] == 0 and row["total_income"] == 0:
        warnings.append("No income values found.")
    if row["tax_payable_on_total_income"] > 0 and row["total_income_tax_paid"] == 0:
        warnings.append("Tax payable is positive but total taxes paid is zero in extracted fields.")
    return warnings


def extract_folder(folder):
    folder = Path(folder).resolve()
    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDFs found in {folder}")

    rows = []
    for pdf_path in pdfs:
        text = extract_pdf_text(pdf_path)
        financial_year = financial_year_from_path(pdf_path)
        row = {
            "financial_year": financial_year,
            "assessment_year": assessment_year_from_fy(financial_year),
            "form": detect_form(text),
            "source_pdf": pdf_path.name,
        }
        row.update(detect_taxpayer(text))
        row.update(extract_metric_values(text))
        row["notes"] = []
        row["extraction_warnings"] = extraction_warnings(row)
        rows.append(row)

    rows.sort(key=lambda item: int(item["financial_year"][:4]))
    return rows


def safe_pct(change, previous):
    if previous in (None, 0):
        return None
    return change / previous * 100


def cagr(first, last, periods):
    if first <= 0 or last <= 0 or periods <= 0:
        return None
    return (last / first) ** (1 / periods) - 1


def add_change_analysis(data):
    enriched = []
    previous = None
    for row in data:
        item = dict(row)
        changes = {}
        drivers = []
        for metric in METRICS:
            if previous is None:
                changes[metric] = {
                    "absolute_change": None,
                    "percent_change": None,
                    "direction": "baseline",
                }
                continue
            delta = item[metric] - previous[metric]
            pct = safe_pct(delta, previous[metric])
            changes[metric] = {
                "absolute_change": delta,
                "percent_change": None if pct is None else round(pct, 2),
                "direction": "up" if delta > 0 else "down" if delta < 0 else "flat",
            }
            if abs(delta) >= 50000:
                drivers.append(
                    {
                        "metric": metric,
                        "metric_label": DISPLAY_NAMES[metric],
                        "change": delta,
                        "change_percent": None if pct is None else round(pct, 2),
                    }
                )
        item["year_over_year_changes"] = changes
        item["large_change_drivers"] = drivers
        item["income_spike_over_5_lakh"] = (
            False
            if previous is None
            else item["gross_total_income"] - previous["gross_total_income"] > 500000
        )
        enriched.append(item)
        previous = item
    return enriched


def linear_forecast(values, steps=3):
    n = len(values)
    if n == 0:
        return []
    if n == 1:
        return [values[0]] * steps
    xs = list(range(n))
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(values)
    denom = sum((x - mean_x) ** 2 for x in xs)
    slope = 0 if denom == 0 else sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / denom
    intercept = mean_y - slope * mean_x
    return [max(0, intercept + slope * (n + idx)) for idx in range(steps)]


def moving_forecast(values, steps=3):
    if not values:
        return []
    recent = values[-3:] if len(values) >= 3 else values
    avg_delta = statistics.mean([b - a for a, b in zip(recent, recent[1:])]) if len(recent) > 1 else 0
    out = []
    current = values[-1]
    for _ in range(steps):
        current = max(0, current + avg_delta)
        out.append(current)
    return out


def forecast_metric(data, metric, years=3):
    values = [row[metric] for row in data]
    lin = linear_forecast(values, years)
    mov = moving_forecast(values, years)
    residuals = []
    if len(values) >= 4:
        fitted = linear_forecast(values[:-3], 3)
        residuals = [actual - pred for actual, pred in zip(values[-3:], fitted)]
    spread = statistics.pstdev(residuals) if len(residuals) > 1 else max(statistics.pstdev(values[-5:]) if len(values) >= 2 else 0, 1000)
    last_year = int(data[-1]["financial_year"][:4])
    rows = []
    for idx in range(years):
        blended = (lin[idx] * 0.55) + (mov[idx] * 0.45)
        fy_start = last_year + idx + 1
        rows.append(
            {
                "financial_year": f"{fy_start}-{str(fy_start + 1)[-2:]}",
                "metric": metric,
                "metric_label": DISPLAY_NAMES[metric],
                "estimate": int(round(blended)),
                "low": int(round(max(0, blended - 1.25 * spread))),
                "high": int(round(blended + 1.25 * spread)),
                "method": "linear trend blended with recent moving delta",
            }
        )
    return rows


def estimate_tax(total_income, special_income=0):
    normal_income = max(total_income - special_income, 0)
    tax = 0
    slabs = [(250000, 0.0), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)]
    remaining = normal_income
    for width, rate in slabs:
        taxable = min(remaining, width)
        if taxable <= 0:
            break
        tax += taxable * rate
        remaining -= taxable
    if normal_income <= 500000:
        tax = max(0, tax - min(tax, 12500))
    tax += max(special_income, 0) * 0.10
    tax *= 1.04
    return int(round(tax))


def compute_tax_planning(data):
    latest = data[-1]
    estimated_tax_before_deductions = estimate_tax(
        latest["gross_total_income"], latest["special_income"]
    )
    estimated_tax_after_deductions = estimate_tax(
        latest["total_income"], latest["special_income"]
    )
    deduction_tax_saved = max(0, estimated_tax_before_deductions - estimated_tax_after_deductions)
    effective_rate = (
        latest["total_income_tax_paid"] / latest["gross_total_income"] * 100
        if latest["gross_total_income"]
        else 0
    )
    estimated_80c_gap = max(0, 150000 - latest["deductions"])
    estimated_80c_tax_saving_room = int(round(estimated_80c_gap * 0.052))
    return {
        "latest_year": latest["financial_year"],
        "estimated_tax_before_deductions": estimated_tax_before_deductions,
        "estimated_tax_after_deductions": estimated_tax_after_deductions,
        "estimated_tax_saved_by_deductions": deduction_tax_saved,
        "effective_tax_rate_percent": round(effective_rate, 2),
        "estimated_80c_gap": estimated_80c_gap,
        "estimated_80c_tax_saving_room": estimated_80c_tax_saving_room,
        "caveat": "Tax saving estimates are approximate and use simplified slab logic; verify before filing.",
    }


def compute_networth_proxy(data):
    latest = data[-1]
    avg_income = statistics.mean([row["gross_total_income"] for row in data[-3:]])
    passive_income = latest["interest_income"] + latest["dividend_income"]
    income_capitalization = avg_income * 8
    liquid_capital_proxy = passive_income / 0.055 if passive_income > 0 else 0
    conservative = max(income_capitalization * 0.45, liquid_capital_proxy)
    base = max(income_capitalization * 0.65, liquid_capital_proxy)
    optimistic = max(income_capitalization, liquid_capital_proxy * 1.25)
    return {
        "method": "Income-capacity proxy, not actual balance-sheet net worth.",
        "latest_year": latest["financial_year"],
        "three_year_average_gross_total_income": int(round(avg_income)),
        "latest_passive_income": passive_income,
        "conservative_estimate": int(round(conservative)),
        "base_estimate": int(round(base)),
        "optimistic_estimate": int(round(optimistic)),
        "caveat": "Actual net worth needs assets, liabilities, bank balances, demat holdings, real estate, gold, loans, and insurance surrender values.",
    }


def summarize_metric(data, metric):
    values = [row[metric] for row in data]
    first = values[0]
    last = values[-1]
    change = last - first
    peak_index = max(range(len(values)), key=lambda idx: values[idx])
    low_index = min(range(len(values)), key=lambda idx: values[idx])
    yoy = [
        row["year_over_year_changes"][metric]["absolute_change"]
        for row in data[1:]
        if row["year_over_year_changes"][metric]["absolute_change"] is not None
    ]
    return {
        "metric": metric,
        "metric_label": DISPLAY_NAMES[metric],
        "first_value": first,
        "last_value": last,
        "absolute_change": change,
        "percent_change": safe_pct(change, first),
        "cagr_percent": None if cagr(first, last, len(values) - 1) is None else round(cagr(first, last, len(values) - 1) * 100, 2),
        "positive_years": sum(1 for value in values if value > 0),
        "peak_year": data[peak_index]["financial_year"],
        "peak_value": values[peak_index],
        "lowest_year": data[low_index]["financial_year"],
        "lowest_value": values[low_index],
        "average": int(round(statistics.mean(values))),
        "volatility": int(round(statistics.pstdev(yoy))) if len(yoy) > 1 else 0,
    }


def generate_narrative(data, profile_name):
    summaries = [summarize_metric(data, metric) for metric in METRICS]
    by_metric = {item["metric"]: item for item in summaries}
    latest = data[-1]
    main_income_metric = max(
        ["gross_salary", "business_income", "interest_income", "special_income"],
        key=lambda metric: latest[metric],
    )
    forecast = {
        metric: forecast_metric(data, metric, 3)
        for metric in [
            "gross_total_income",
            "total_income",
            "business_income",
            "gross_salary",
            "interest_income",
            "total_income_tax_paid",
        ]
    }
    tax_planning = compute_tax_planning(data)
    networth_proxy = compute_networth_proxy(data)
    lines = [
        (
            f"{profile_name} gross total income moved from "
            f"{inr(data[0]['gross_total_income'])} in FY {data[0]['financial_year']} "
            f"to {inr(latest['gross_total_income'])} in FY {latest['financial_year']}."
        ),
        (
            "The strongest gross-total-income year was "
            f"FY {by_metric['gross_total_income']['peak_year']} at "
            f"{inr(by_metric['gross_total_income']['peak_value'])}."
        ),
        (
            f"The latest dominant income source is {DISPLAY_NAMES[main_income_metric]} "
            f"at {inr(latest[main_income_metric])}."
        ),
        (
            "No year crossed the sharp-rise threshold of Rs 5 lakh over the previous year."
            if not any(row["income_spike_over_5_lakh"] for row in data)
            else "At least one year crossed the sharp-rise threshold of Rs 5 lakh over the previous year."
        ),
        (
            "The three-year look-ahead uses a simple statistical blend of linear trend and recent moving delta; "
            "treat it as planning guidance, not a tax filing position."
        ),
    ]
    return {
        "profile_name": profile_name,
        "metric_summaries": summaries,
        "executive_summary": lines,
        "forecast": forecast,
        "tax_planning": tax_planning,
        "networth_proxy": networth_proxy,
    }


def save_jsons(folder, data, summary):
    json_dir = folder / "json"
    json_dir.mkdir(exist_ok=True)
    for row in data:
        (json_dir / f"{row['financial_year']}.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
    (json_dir / "all_years.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (json_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return json_dir


def load_generated_json(folder):
    json_dir = folder / "json"
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(json_dir.glob("20??-??.json"))]
    summary = json.loads((json_dir / "summary.json").read_text(encoding="utf-8"))
    return rows, summary


def save_csv(folder, data):
    out_dir = folder / "output"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / "itr_dataset.csv"
    fields = ["financial_year", "assessment_year", "form"] + METRICS
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in data:
            writer.writerow({field: row.get(field, "") for field in fields})
    return path


def build_dashboard_html(data, summary):
    payload = json.dumps({"data": data, "summary": summary, "names": DISPLAY_NAMES}, separators=(",", ":"))
    checkboxes = "\n".join(
        f'<label><input type="checkbox" value="{metric}" {"checked" if metric in ["gross_total_income", "total_income", "gross_salary", "business_income", "interest_income"] else ""}> {DISPLAY_NAMES[metric]}</label>'
        for metric in CORE_CHART_METRICS
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(summary["profile_name"])} ITR Post Analyzer</title>
  <style>
    :root {{
      --bg:#f5f7f9; --panel:#ffffff; --text:#18212b; --muted:#617081; --line:#d9e0e7;
      --a:#0f766e; --b:#2563eb; --c:#b45309; --d:#7c3aed; --e:#be123c; --f:#4d7c0f;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter, ui-sans-serif, system-ui, Segoe UI, sans-serif; color:var(--text); background:var(--bg); }}
    header {{ background:var(--panel); border-bottom:1px solid var(--line); padding:20px 26px 14px; position:sticky; top:0; z-index:5; }}
    h1 {{ margin:0; font-size:24px; font-weight:700; }}
    h2 {{ margin:0 0 12px; font-size:17px; }}
    p {{ margin:0; color:var(--muted); }}
    main {{ padding:20px 26px 36px; display:grid; gap:16px; }}
    .tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }}
    .tab {{ border:1px solid var(--line); background:var(--panel); border-radius:7px; padding:8px 11px; cursor:pointer; }}
    .tab.active {{ background:var(--a); color:white; border-color:var(--a); }}
    .view {{ display:none; gap:16px; }}
    .view.active {{ display:grid; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
    .two {{ display:grid; grid-template-columns:1.35fr .9fr; gap:16px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:15px; }}
    .stat-label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.05em; }}
    .stat-value {{ margin-top:5px; font-size:23px; font-weight:750; }}
    .stat-sub {{ margin-top:5px; color:var(--muted); font-size:13px; }}
    .controls {{ display:flex; flex-wrap:wrap; gap:10px 16px; align-items:center; }}
    .checks {{ display:flex; flex-wrap:wrap; gap:9px 13px; }}
    label {{ font-size:14px; }}
    button, select {{ border:1px solid var(--line); background:var(--panel); color:var(--text); border-radius:7px; padding:8px 10px; font:inherit; }}
    button {{ cursor:pointer; }}
    .primary {{ background:var(--a); color:white; border-color:var(--a); }}
    svg {{ width:100%; height:auto; display:block; }}
    .gridline {{ stroke:var(--line); stroke-width:1; }}
    .legend {{ display:flex; flex-wrap:wrap; gap:10px 15px; margin-top:10px; }}
    .legend span {{ display:inline-flex; align-items:center; gap:6px; color:var(--muted); font-size:13px; }}
    .swatch {{ width:10px; height:10px; border-radius:99px; display:inline-block; }}
    .summary-list {{ display:grid; gap:8px; color:var(--muted); line-height:1.45; }}
    .heatmap {{ display:grid; grid-template-columns:150px repeat(13,1fr); gap:2px; align-items:stretch; }}
    .heatcell {{ min-height:30px; padding:6px; font-size:11px; border-radius:4px; background:rgba(15,118,110,.08); overflow:hidden; }}
    .heathead {{ color:var(--muted); font-size:11px; padding:6px 2px; }}
    .table-wrap {{ overflow-x:auto; }}
    table {{ border-collapse:collapse; width:100%; min-width:1120px; font-size:13px; }}
    th,td {{ border-bottom:1px solid var(--line); padding:8px; text-align:right; white-space:nowrap; }}
    th:first-child,td:first-child,th:nth-child(2),td:nth-child(2) {{ text-align:left; }}
    th {{ color:var(--muted); font-weight:700; }}
    .positive {{ color:#047857; }} .negative {{ color:#b91c1c; }}
    .warn {{ color:#b45309; }}
    .small {{ font-size:12px; color:var(--muted); }}
    @media print {{ header {{ position:static; }} .tabs,.controls,button {{ display:none; }} .view {{ display:grid !important; }} body {{ background:white; }} .card {{ break-inside:avoid; }} }}
    @media (max-width:980px) {{ .grid,.two {{ grid-template-columns:1fr 1fr; }} .heatmap {{ grid-template-columns:120px repeat(13,54px); overflow-x:auto; }} }}
    @media (max-width:640px) {{ header,main {{ padding-left:14px; padding-right:14px; }} .grid,.two {{ grid-template-columns:1fr; }} h1 {{ font-size:20px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(summary["profile_name"])} ITR Post Analyzer</h1>
    <p>Folder-driven analysis, local JSON generation, trend diagnostics, tax planning estimates, net-worth proxy, and statistical look-ahead.</p>
    <div class="tabs" id="tabs">
      <button class="tab active" data-view="overview">Overview</button>
      <button class="tab" data-view="trends">Trends</button>
      <button class="tab" data-view="forecast">Forecast</button>
      <button class="tab" data-view="tax">Tax & Net Worth</button>
      <button class="tab" data-view="data">Data Quality</button>
      <button class="primary" onclick="window.print()">Export PDF</button>
    </div>
  </header>
  <main>
    <section id="overview" class="view active">
      <div class="grid" id="stats"></div>
      <div class="two">
        <div class="card"><h2>Income Composition</h2><svg id="stackChart" viewBox="0 0 1120 430"></svg><div class="legend" id="stackLegend"></div></div>
        <div class="card"><h2>Executive Analysis</h2><div class="summary-list" id="summaryText"></div></div>
      </div>
    </section>
    <section id="trends" class="view">
      <div class="card">
        <div class="controls"><strong>Metrics</strong><div class="checks" id="metricChecks">{checkboxes}</div>
          <label>Scale <select id="scaleMode"><option value="auto">Auto</option><option value="lakhs">Lakhs</option><option value="thousands">Thousands</option><option value="raw">Raw INR</option></select></label>
        </div>
      </div>
      <div class="card"><h2>Multi-Metric Trend</h2><svg id="lineChart" viewBox="0 0 1120 460"></svg><div class="legend" id="lineLegend"></div></div>
      <div class="card"><h2>Year-over-Year Change Heatmap</h2><div class="heatmap" id="heatmap"></div></div>
    </section>
    <section id="forecast" class="view">
      <div class="grid" id="forecastStats"></div>
      <div class="card"><h2>Three-Year Look Ahead</h2><svg id="forecastChart" viewBox="0 0 1120 450"></svg><div class="legend" id="forecastLegend"></div><p class="small">Forecasts blend linear trend and recent moving delta. Bands are heuristic uncertainty ranges.</p></div>
    </section>
    <section id="tax" class="view">
      <div class="grid" id="taxStats"></div>
      <div class="two">
        <div class="card"><h2>Tax Payable And Paid</h2><svg id="taxChart" viewBox="0 0 1120 420"></svg><div class="legend" id="taxLegend"></div></div>
        <div class="card"><h2>Planning Notes</h2><div class="summary-list" id="planningText"></div></div>
      </div>
    </section>
    <section id="data" class="view">
      <div class="card"><h2>Extracted Data And Deltas</h2><div class="table-wrap"><table id="dataTable"></table></div></div>
      <div class="card"><h2>Extraction Warnings</h2><div class="summary-list" id="warningText"></div></div>
    </section>
  </main>
  <script>
    const payload = {payload};
    const data = payload.data;
    const summary = payload.summary;
    const names = payload.names;
    const colors = ["#0f766e","#2563eb","#b45309","#7c3aed","#be123c","#4d7c0f","#0891b2","#9333ea","#c2410c"];
    const fmt = new Intl.NumberFormat("en-IN", {{maximumFractionDigits:0}});
    const money = v => "Rs " + fmt.format(Math.round(v || 0));
    const deltaFmt = v => v === null || v === undefined ? "-" : (v >= 0 ? "+" : "") + money(v).replace("Rs ","Rs ");
    const years = data.map(d => d.financial_year);

    document.querySelectorAll(".tab").forEach(btn => btn.addEventListener("click", () => {{
      document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.view).classList.add("active");
    }}));

    function scaleValue(value, mode, maxValue) {{
      const active = mode === "auto" ? (maxValue >= 100000 ? "lakhs" : maxValue >= 10000 ? "thousands" : "raw") : mode;
      if (active === "lakhs") return {{value:value/100000, suffix:"lakh"}};
      if (active === "thousands") return {{value:value/1000, suffix:"thousand"}};
      return {{value, suffix:"INR"}};
    }}
    function path(points) {{ return points.map((p,i)=>`${{i?"L":"M"}} ${{p.x.toFixed(2)}} ${{p.y.toFixed(2)}}`).join(" "); }}
    function selectedMetrics() {{ return Array.from(document.querySelectorAll("#metricChecks input:checked")).map(i=>i.value); }}

    function drawLine() {{
      const svg = document.getElementById("lineChart"), metrics = selectedMetrics(), mode = document.getElementById("scaleMode").value;
      const W=1120,H=460,L=82,R=24,T=26,B=76;
      const maxRaw = Math.max(...metrics.flatMap(m => data.map(r => r[m] || 0)), 1);
      const yMax = Math.ceil(scaleValue(maxRaw, mode, maxRaw).value * 1.15) || 1;
      const suffix = scaleValue(maxRaw, mode, maxRaw).suffix;
      const x = i => L + i*((W-L-R)/(data.length-1));
      const y = v => T + (H-T-B)*(1-v/yMax);
      let html = `<text x="${{L}}" y="16" fill="#617081" font-size="12">Scale: ${{suffix}}</text>`;
      [0,.25,.5,.75,1].forEach(t => {{ const val=yMax*t, yy=y(val); html += `<line class="gridline" x1="${{L}}" y1="${{yy}}" x2="${{W-R}}" y2="${{yy}}"></line><text x="${{L-10}}" y="${{yy+4}}" text-anchor="end" fill="#617081" font-size="11">${{fmt.format(Math.round(val))}}</text>`; }});
      years.forEach((fy,i)=>{{ const xx=x(i); html += `<text x="${{xx}}" y="${{H-38}}" text-anchor="middle" fill="#617081" font-size="11" transform="rotate(-35 ${{xx}} ${{H-38}})">${{fy}}</text>`; }});
      metrics.forEach((m,idx)=>{{ const pts=data.map((r,i)=>{{ const sv=scaleValue(r[m]||0,mode,maxRaw).value; return {{x:x(i),y:y(sv),raw:r[m]||0,fy:r.financial_year}}; }}); html += `<path d="${{path(pts)}}" fill="none" stroke="${{colors[idx%colors.length]}}" stroke-width="2.5"></path>`; pts.forEach(p=> html += `<circle cx="${{p.x}}" cy="${{p.y}}" r="4" fill="${{colors[idx%colors.length]}}"><title>${{names[m]}} ${{p.fy}}: ${{money(p.raw)}}</title></circle>`); }});
      svg.innerHTML = html;
      document.getElementById("lineLegend").innerHTML = metrics.map((m,i)=>`<span><i class="swatch" style="background:${{colors[i%colors.length]}}"></i>${{names[m]}}</span>`).join("");
    }}

    function drawStack() {{
      const svg=document.getElementById("stackChart"), W=1120,H=430,L=78,R=24,T=26,B=76;
      const metrics=["gross_salary","business_income","interest_income","dividend_income","short_term_capital_gains","long_term_capital_gains"];
      const maxVal=Math.max(...data.map(r=>metrics.reduce((s,m)=>s+(r[m]||0),0)),1);
      const yMax=Math.ceil(maxVal*1.12/100000)*100000 || 1, groupW=(W-L-R)/data.length, barW=Math.max(18,groupW*.56);
      const y=v=>T+(H-T-B)*(1-v/yMax);
      let html="";
      [0,.25,.5,.75,1].forEach(t=>{{ const val=yMax*t, yy=y(val); html += `<line class="gridline" x1="${{L}}" y1="${{yy}}" x2="${{W-R}}" y2="${{yy}}"></line><text x="${{L-10}}" y="${{yy+4}}" text-anchor="end" fill="#617081" font-size="11">${{(val/100000).toFixed(1)}}L</text>`; }});
      data.forEach((r,i)=>{{ let bottom=H-B; const x=L+i*groupW+groupW/2-barW/2; metrics.forEach((m,idx)=>{{ const h=(H-T-B)*((r[m]||0)/yMax); bottom-=h; html += `<rect x="${{x}}" y="${{bottom}}" width="${{barW}}" height="${{Math.max(0,h)}}" fill="${{colors[idx]}}"><title>${{names[m]}} ${{r.financial_year}}: ${{money(r[m])}}</title></rect>`; }}); const cx=x+barW/2; html += `<text x="${{cx}}" y="${{H-38}}" text-anchor="middle" fill="#617081" font-size="11" transform="rotate(-35 ${{cx}} ${{H-38}})">${{r.financial_year}}</text>`; }});
      svg.innerHTML=html;
      document.getElementById("stackLegend").innerHTML=metrics.map((m,i)=>`<span><i class="swatch" style="background:${{colors[i]}}"></i>${{names[m]}}</span>`).join("");
    }}

    function drawTax() {{
      const svg=document.getElementById("taxChart"), W=1120,H=420,L=78,R=24,T=24,B=72;
      const metrics=["gross_total_income","tax_payable_on_total_income","total_income_tax_paid"], cols=["#0f766e","#b45309","#be123c"];
      const maxVal=Math.max(...data.map(r=>Math.max(...metrics.map(m=>r[m]||0))),1), yMax=Math.ceil(maxVal*1.12/100000)*100000 || 1;
      const groupW=(W-L-R)/data.length, barW=Math.max(8,groupW*.2), y=v=>T+(H-T-B)*(1-v/yMax);
      let html="";
      [0,.25,.5,.75,1].forEach(t=>{{ const val=yMax*t, yy=y(val); html += `<line class="gridline" x1="${{L}}" y1="${{yy}}" x2="${{W-R}}" y2="${{yy}}"></line><text x="${{L-10}}" y="${{yy+4}}" text-anchor="end" fill="#617081" font-size="11">${{(val/100000).toFixed(1)}}L</text>`; }});
      data.forEach((r,i)=>{{ const cx=L+i*groupW+groupW/2; metrics.forEach((m,idx)=>{{ const yy=y(r[m]||0); html += `<rect x="${{cx+(idx-1)*(barW+3)}}" y="${{yy}}" width="${{barW}}" height="${{H-B-yy}}" fill="${{cols[idx]}}"><title>${{names[m]}} ${{r.financial_year}}: ${{money(r[m])}}</title></rect>`; }}); html += `<text x="${{cx}}" y="${{H-38}}" text-anchor="middle" fill="#617081" font-size="11" transform="rotate(-35 ${{cx}} ${{H-38}})">${{r.financial_year}}</text>`; }});
      svg.innerHTML=html;
      document.getElementById("taxLegend").innerHTML=metrics.map((m,i)=>`<span><i class="swatch" style="background:${{cols[i]}}"></i>${{names[m]}}</span>`).join("");
    }}

    function drawForecast() {{
      const svg=document.getElementById("forecastChart"), W=1120,H=450,L=82,R=24,T=24,B=76;
      const hist=data.map(r=>({{fy:r.financial_year,v:r.gross_total_income,type:"actual"}}));
      const fc=summary.forecast.gross_total_income.map(r=>({{fy:r.financial_year,v:r.estimate,low:r.low,high:r.high,type:"forecast"}}));
      const all=hist.concat(fc), maxVal=Math.max(...all.map(r=>r.high||r.v),1), yMax=Math.ceil(maxVal*1.12/100000)*100000 || 1;
      const x=i=>L+i*((W-L-R)/(all.length-1)), y=v=>T+(H-T-B)*(1-v/yMax);
      let html="";
      [0,.25,.5,.75,1].forEach(t=>{{ const val=yMax*t, yy=y(val); html += `<line class="gridline" x1="${{L}}" y1="${{yy}}" x2="${{W-R}}" y2="${{yy}}"></line><text x="${{L-10}}" y="${{yy+4}}" text-anchor="end" fill="#617081" font-size="11">${{(val/100000).toFixed(1)}}L</text>`; }});
      const actualPts=hist.map((r,i)=>({{x:x(i),y:y(r.v)}})), fcPts=fc.map((r,i)=>({{x:x(i+hist.length),y:y(r.v)}}));
      html += `<path d="${{path(actualPts)}}" fill="none" stroke="#0f766e" stroke-width="2.5"></path>`;
      html += `<path d="${{path([actualPts[actualPts.length-1]].concat(fcPts))}}" fill="none" stroke="#b45309" stroke-width="2.5" stroke-dasharray="7 5"></path>`;
      fc.forEach((r,i)=>{{ const xx=x(i+hist.length); html += `<line x1="${{xx}}" y1="${{y(r.low)}}" x2="${{xx}}" y2="${{y(r.high)}}" stroke="#b45309" stroke-width="4" opacity=".35"><title>Range ${{r.fy}}: ${{money(r.low)}} - ${{money(r.high)}}</title></line>`; }});
      all.forEach((r,i)=>{{ const xx=x(i); html += `<circle cx="${{xx}}" cy="${{y(r.v)}}" r="4" fill="${{r.type==="actual"?"#0f766e":"#b45309"}}"><title>${{r.fy}}: ${{money(r.v)}}</title></circle><text x="${{xx}}" y="${{H-38}}" text-anchor="middle" fill="#617081" font-size="11" transform="rotate(-35 ${{xx}} ${{H-38}})">${{r.fy}}</text>`; }});
      svg.innerHTML=html;
      document.getElementById("forecastLegend").innerHTML=`<span><i class="swatch" style="background:#0f766e"></i>Actual GTI</span><span><i class="swatch" style="background:#b45309"></i>Forecast GTI</span>`;
    }}

    function renderStats() {{
      const first=data[0], last=data[data.length-1], maxGti=data.reduce((a,b)=>a.gross_total_income>b.gross_total_income?a:b);
      const cards=[
        ["Latest GTI",money(last.gross_total_income),last.financial_year],
        ["Latest Total Income",money(last.total_income),last.financial_year],
        ["Peak GTI",money(maxGti.gross_total_income),maxGti.financial_year],
        ["Tax Paid Total",money(data.reduce((s,r)=>s+r.total_income_tax_paid,0)),"All years"]
      ];
      document.getElementById("stats").innerHTML=cards.map(c=>`<article class="card"><div class="stat-label">${{c[0]}}</div><div class="stat-value">${{c[1]}}</div><div class="stat-sub">${{c[2]}}</div></article>`).join("");
    }}
    function renderForecastStats() {{
      const g=summary.forecast.gross_total_income[0], t=summary.forecast.total_income[0], tax=summary.forecast.total_income_tax_paid[0];
      const cards=[["Next GTI Estimate",money(g.estimate),`${{g.financial_year}} range ${{money(g.low)}} - ${{money(g.high)}}`],["Next Total Income",money(t.estimate),t.financial_year],["Next Tax Paid",money(tax.estimate),tax.financial_year],["Method","Trend + moving delta","Heuristic ML/stat model"]];
      document.getElementById("forecastStats").innerHTML=cards.map(c=>`<article class="card"><div class="stat-label">${{c[0]}}</div><div class="stat-value">${{c[1]}}</div><div class="stat-sub">${{c[2]}}</div></article>`).join("");
    }}
    function renderTaxStats() {{
      const tx=summary.tax_planning, nw=summary.networth_proxy;
      const cards=[["Effective Tax Rate",`${{tx.effective_tax_rate_percent}}%`,tx.latest_year],["Estimated Tax Saved",money(tx.estimated_tax_saved_by_deductions),"Approx deduction benefit"],["Net Worth Proxy",money(nw.base_estimate),"Base income-capacity estimate"],["80C Room",money(tx.estimated_80c_gap),`Potential saving about ${{money(tx.estimated_80c_tax_saving_room)}}`]];
      document.getElementById("taxStats").innerHTML=cards.map(c=>`<article class="card"><div class="stat-label">${{c[0]}}</div><div class="stat-value">${{c[1]}}</div><div class="stat-sub">${{c[2]}}</div></article>`).join("");
    }}
    function renderText() {{
      const changes=data.slice(1).map(r=>r.large_change_drivers.length?`FY ${{r.financial_year}}: `+r.large_change_drivers.map(d=>`${{d.metric_label}} ${{d.change>=0?"rose":"fell"}} by ${{money(Math.abs(d.change))}}`).join("; ")+".":`FY ${{r.financial_year}}: no metric moved by Rs 50,000 or more.`);
      document.getElementById("summaryText").innerHTML=summary.executive_summary.concat(changes).map(x=>`<div>${{x}}</div>`).join("");
      const tx=summary.tax_planning,nw=summary.networth_proxy;
      document.getElementById("planningText").innerHTML=[tx.caveat,nw.caveat,`Net-worth proxy range: ${{money(nw.conservative_estimate)}} to ${{money(nw.optimistic_estimate)}}.`, `Estimated tax before deductions: ${{money(tx.estimated_tax_before_deductions)}}; after deductions: ${{money(tx.estimated_tax_after_deductions)}}.`].map(x=>`<div>${{x}}</div>`).join("");
      const warnings=data.flatMap(r=>(r.extraction_warnings||[]).map(w=>`FY ${{r.financial_year}}: ${{w}}`));
      document.getElementById("warningText").innerHTML=(warnings.length?warnings:["No extraction warnings generated."]).map(x=>`<div class="${{x.includes("warning")?"warn":""}}">${{x}}</div>`).join("");
    }}
    function renderHeatmap() {{
      const metrics=["gross_total_income","total_income","gross_salary","business_income","interest_income","special_income","total_income_tax_paid"];
      const maxAbs=Math.max(...data.slice(1).flatMap(r=>metrics.map(m=>Math.abs(r.year_over_year_changes[m].absolute_change||0))),1);
      let html=`<div class="heathead">Metric</div>`+years.map(y=>`<div class="heathead">${{y}}</div>`).join("");
      metrics.forEach(m=>{{ html += `<div class="heathead">${{names[m]}}</div>`; data.forEach((r,i)=>{{ const d=r.year_over_year_changes[m].absolute_change; const alpha=d===null?0:Math.min(.85,Math.abs(d)/maxAbs*.85+.08); const col=d>0?`rgba(4,120,87,${{alpha}})`:d<0?`rgba(185,28,28,${{alpha}})`:"rgba(97,112,129,.08)"; html += `<div class="heatcell" style="background:${{col}}"><title>${{names[m]}} ${{r.financial_year}} delta: ${{deltaFmt(d)}}</title>${{i===0?"-":deltaFmt(d)}}</div>`; }}); }});
      document.getElementById("heatmap").innerHTML=html;
    }}
    function renderTable() {{
      const cols=["financial_year","form","gross_salary","business_income","interest_income","short_term_capital_gains","long_term_capital_gains","gross_total_income","deductions","total_income","tax_payable_on_total_income","total_income_tax_paid"];
      const heads=["FY","Form","Gross Salary","Business","Interest","STCG","LTCG","GTI","Deductions","Total Income","Tax Payable","Tax Paid"];
      let html=`<thead><tr>${{heads.map(h=>`<th>${{h}}</th>`).join("")}}<th>GTI Delta</th><th>Total Income Delta</th></tr></thead><tbody>`;
      data.forEach(r=>{{ html+="<tr>"; cols.forEach(c=>{{ html += `<td>${{c==="financial_year"||c==="form"?r[c]:money(r[c])}}</td>`; }}); ["gross_total_income","total_income"].forEach(m=>{{ const d=r.year_over_year_changes[m].absolute_change; html += `<td class="${{d>0?"positive":d<0?"negative":""}}">${{deltaFmt(d)}}</td>`; }}); html+="</tr>"; }});
      document.getElementById("dataTable").innerHTML=html+"</tbody>";
    }}
    function renderAll() {{ renderStats(); renderForecastStats(); renderTaxStats(); renderText(); renderHeatmap(); renderTable(); drawStack(); drawLine(); drawTax(); drawForecast(); }}
    document.querySelectorAll("#metricChecks input").forEach(i=>i.addEventListener("change",drawLine));
    document.getElementById("scaleMode").addEventListener("change",drawLine);
    renderAll();
  </script>
</body>
</html>"""


def save_pdf_report(folder, data, summary):
    out_dir = folder / "output"
    out_dir.mkdir(exist_ok=True)
    pdf_path = out_dir / "itr_post_analysis_report.pdf"
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception as exc:
        fallback = out_dir / "itr_post_analysis_report.txt"
        fallback.write_text("PDF export skipped because reportlab is unavailable.\n\n" + str(exc), encoding="utf-8")
        return fallback
    doc = SimpleDocTemplate(str(pdf_path), pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"{summary['profile_name']} ITR Post Analysis", styles["Title"])]
    for line in summary["executive_summary"]:
        story.append(Paragraph(line, styles["BodyText"]))
        story.append(Spacer(1, 5))
    story.append(Paragraph("Tax and net-worth estimates are indicative only.", styles["Italic"]))
    table_data = [["FY", "Form", "Gross Salary", "Business", "Interest", "GTI", "Deductions", "Total Income", "Tax Paid"]]
    for row in data:
        table_data.append([row["financial_year"], row["form"], inr(row["gross_salary"]), inr(row["business_income"]), inr(row["interest_income"]), inr(row["gross_total_income"]), inr(row["deductions"]), inr(row["total_income"]), inr(row["total_income_tax_paid"])])
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef3")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c7d0d9")), ("FONT", (0, 0), (-1, -1), "Helvetica", 7), ("ALIGN", (2, 1), (-1, -1), "RIGHT")]))
    story.append(Spacer(1, 12))
    story.append(table)
    doc.build(story)
    return pdf_path


def validate(data):
    if not data:
        raise ValueError("No rows extracted.")
    for row in data:
        for metric in METRICS:
            if metric not in row:
                raise ValueError(f"{row.get('financial_year', '?')} missing {metric}")
            if not isinstance(row[metric], int):
                raise ValueError(f"{row.get('financial_year', '?')} invalid {metric}: {row[metric]}")


def analyze_folder(folder, no_pdf=False):
    folder = Path(folder).resolve()
    profile_name = folder.name
    data = add_change_analysis(extract_folder(folder))
    validate(data)
    summary = generate_narrative(data, profile_name)
    save_jsons(folder, data, summary)
    data_from_json, summary_from_json = load_generated_json(folder)
    validate(data_from_json)
    (folder / "dashboard.html").write_text(build_dashboard_html(data_from_json, summary_from_json), encoding="utf-8")
    csv_path = save_csv(folder, data_from_json)
    pdf_path = None if no_pdf else save_pdf_report(folder, data_from_json, summary_from_json)
    return {
        "folder": str(folder),
        "years": len(data_from_json),
        "json": str(folder / "json" / "all_years.json"),
        "summary": str(folder / "json" / "summary.json"),
        "dashboard": str(folder / "dashboard.html"),
        "csv": str(csv_path),
        "pdf": None if pdf_path is None else str(pdf_path),
    }


def main():
    parser = argparse.ArgumentParser(description="Folder-driven ITR post analyzer.")
    parser.add_argument("--folder", default=".", help="Folder containing year-wise ITR PDFs.")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF report generation.")
    args = parser.parse_args()
    result = analyze_folder(args.folder, no_pdf=args.no_pdf)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
