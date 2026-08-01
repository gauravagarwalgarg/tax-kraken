from __future__ import annotations

import argparse
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


OFFICIAL_TAX_RATE_SOURCES = {
    "traces_slab_archive": "https://traces61contents.tdscpc.gov.in/en/personal-income-tax.html",
    "fy_2013_14_example": "https://traces61contents.tdscpc.gov.in/en/incometax-2013-2014.html",
    "individual_ay_2025_26": "https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-3",
    "individual_ay_2026_27": "https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1",
    "domestic_company_ay_2026_27": "https://www.incometax.gov.in/iec/foportal/help/company/return-applicable",
}


# Historical old-regime individual slabs for below-60 resident individuals.
# The TRACES archive lists FY-wise slabs from FY 2013-14 through FY 2025-26.
# Papa/Mummy DOBs from the PDFs indicate both remain below 60 across this span.
INDIVIDUAL_OLD_REGIME_BY_FY: dict[str, dict[str, Any]] = {
    "2013-14": {"slabs": [(200000, 0.00), (300000, 0.10), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 2000, "cess_rate": 0.03},
    "2014-15": {"slabs": [(250000, 0.00), (250000, 0.10), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 2000, "cess_rate": 0.03},
    "2015-16": {"slabs": [(250000, 0.00), (250000, 0.10), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 2000, "cess_rate": 0.03},
    "2016-17": {"slabs": [(250000, 0.00), (250000, 0.10), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 5000, "cess_rate": 0.03},
    "2017-18": {"slabs": [(250000, 0.00), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 350000, "rebate_max": 2500, "cess_rate": 0.03},
    "2018-19": {"slabs": [(250000, 0.00), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 350000, "rebate_max": 2500, "cess_rate": 0.04},
    "2019-20": {"slabs": [(250000, 0.00), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
    "2020-21": {"slabs": [(250000, 0.00), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
    "2021-22": {"slabs": [(250000, 0.00), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
    "2022-23": {"slabs": [(250000, 0.00), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
    "2023-24": {"slabs": [(250000, 0.00), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
    "2024-25": {"slabs": [(250000, 0.00), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
    "2025-26": {"slabs": [(250000, 0.00), (250000, 0.05), (500000, 0.20), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
}

INDIVIDUAL_NEW_REGIME_BY_FY: dict[str, dict[str, Any]] = {
    "2020-21": {"slabs": [(250000, 0.00), (250000, 0.05), (250000, 0.10), (250000, 0.15), (250000, 0.20), (250000, 0.25), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
    "2021-22": {"slabs": [(250000, 0.00), (250000, 0.05), (250000, 0.10), (250000, 0.15), (250000, 0.20), (250000, 0.25), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
    "2022-23": {"slabs": [(250000, 0.00), (250000, 0.05), (250000, 0.10), (250000, 0.15), (250000, 0.20), (250000, 0.25), (float("inf"), 0.30)], "rebate_limit": 500000, "rebate_max": 12500, "cess_rate": 0.04},
    "2023-24": {"slabs": [(300000, 0.00), (300000, 0.05), (300000, 0.10), (300000, 0.15), (300000, 0.20), (float("inf"), 0.30)], "rebate_limit": 700000, "rebate_max": 25000, "cess_rate": 0.04},
    "2024-25": {"slabs": [(300000, 0.00), (400000, 0.05), (300000, 0.10), (200000, 0.15), (300000, 0.20), (float("inf"), 0.30)], "rebate_limit": 700000, "rebate_max": 25000, "cess_rate": 0.04},
    "2025-26": {"slabs": [(400000, 0.00), (400000, 0.05), (400000, 0.10), (400000, 0.15), (400000, 0.20), (400000, 0.25), (float("inf"), 0.30)], "rebate_limit": 1200000, "rebate_max": 60000, "cess_rate": 0.04},
}

BUSINESS_TAX_PROFILES = {
    "company_25": {"base_rate": 0.25, "cess_rate": 0.04, "label": "Company 25% + cess"},
    "company_30": {"base_rate": 0.30, "cess_rate": 0.04, "label": "Company 30% + cess"},
    "firm_30": {"base_rate": 0.30, "cess_rate": 0.04, "label": "Firm 30% + cess"},
}


@dataclass(frozen=True)
class PersonFolder:
    name: str
    folder: Path


def money(value: float | int) -> str:
    return f"Rs {value:,.0f}"


def assessment_year(fy: str) -> str:
    start = int(fy[:4]) + 1
    return f"{start}-{str(start + 1)[-2:]}"


def compute_slab_tax(income: float, fy: str, regime: str) -> float:
    if regime == "old":
        profile = INDIVIDUAL_OLD_REGIME_BY_FY[fy]
    else:
        profile = INDIVIDUAL_NEW_REGIME_BY_FY.get(fy, INDIVIDUAL_OLD_REGIME_BY_FY[fy])
    remaining = max(float(income), 0.0)
    tax = 0.0
    for width, rate in profile["slabs"]:
        in_slab = min(remaining, width)
        if in_slab <= 0:
            break
        tax += in_slab * rate
        remaining -= in_slab
    if income <= profile["rebate_limit"]:
        tax = max(0.0, tax - min(tax, profile["rebate_max"]))
    return round(tax * (1 + profile["cess_rate"]), 0)


def compute_business_tax(profit: float, profile_name: str) -> float:
    profile = BUSINESS_TAX_PROFILES[profile_name]
    return round(max(profit, 0) * profile["base_rate"] * (1 + profile["cess_rate"]), 0)


def load_itr_rows(folder: Path) -> list[dict[str, Any]]:
    json_path = folder / "json" / "all_years.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Missing {json_path}. Run analysis.py --folder {folder} first.")
    return json.loads(json_path.read_text(encoding="utf-8"))


def parse_person_folder(value: str) -> PersonFolder:
    if "=" not in value:
        folder = Path(value)
        return PersonFolder(folder.name, folder)
    name, folder = value.split("=", 1)
    return PersonFolder(name.strip(), Path(folder.strip()))


def routed_amount(person: str, itr_row: dict[str, Any]) -> float:
    name = person.lower()
    if name.startswith("father") or name.startswith("papa"):
        return float(itr_row.get("gross_salary") or itr_row.get("salary") or 0)
    if name.startswith("mother") or name.startswith("mummy"):
        return float(itr_row.get("business_income") or itr_row.get("gross_salary") or itr_row.get("salary") or 0)
    return float(itr_row.get("gross_salary") or itr_row.get("salary") or itr_row.get("business_income") or 0)


def build_year_matrix(person_folders: list[PersonFolder], business_profile: str, regime: str) -> dict[str, dict[str, Any]]:
    rows_by_person = {person.name: load_itr_rows(person.folder) for person in person_folders}
    years = sorted(
        fy
        for fy in {row["financial_year"] for rows in rows_by_person.values() for row in rows}
        if fy in INDIVIDUAL_OLD_REGIME_BY_FY
    )
    matrix = {}
    for fy in years:
        routed = {}
        actual_tax = {}
        total_income = {}
        for person, rows in rows_by_person.items():
            row = next((item for item in rows if item["financial_year"] == fy), {})
            routed[person] = routed_amount(person, row)
            actual_tax[person] = float(row.get("total_income_tax_paid") or 0)
            total_income[person] = float(row.get("total_income") or 0)
        matrix[fy] = {
            "assessment_year": assessment_year(fy),
            "business_profit_after_parent_routing": 0,
            "business_net_profit_before_parent_routing": sum(routed.values()),
            "salary_or_remuneration_routed_by_person": routed,
            "actual_tax_paid_by_person": actual_tax,
            "actual_total_income_by_person": total_income,
            "business_tax_profile": business_profile,
            "individual_regime": regime,
        }
    return matrix


def simulate(matrix: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for fy, config in sorted(matrix.items()):
        business_profile = config["business_tax_profile"]
        regime = config["individual_regime"]
        routed_by_person = config["salary_or_remuneration_routed_by_person"]
        total_income_by_person = config["actual_total_income_by_person"]
        actual_tax_by_person = config["actual_tax_paid_by_person"]

        total_routed = sum(routed_by_person.values())
        profit_before = float(config["business_net_profit_before_parent_routing"])
        profit_after = float(config["business_profit_after_parent_routing"])
        business_tax_without = compute_business_tax(profit_before, business_profile)
        business_tax_with = compute_business_tax(profit_after, business_profile)
        business_tax_saved = business_tax_without - business_tax_with

        incremental_parent_tax = {}
        tax_with = {}
        tax_without = {}
        for person, amount in routed_by_person.items():
            actual_total_income = total_income_by_person[person]
            tax_with[person] = compute_slab_tax(actual_total_income, fy, regime)
            tax_without[person] = compute_slab_tax(max(actual_total_income - amount, 0), fy, regime)
            incremental_parent_tax[person] = max(tax_with[person] - tax_without[person], 0)

        parent_incremental_tax_total = sum(incremental_parent_tax.values())
        actual_parent_tax_total = sum(actual_tax_by_person.values())
        rows.append(
            {
                "Financial Year": fy,
                "Assessment Year": config["assessment_year"],
                "Business Profile": business_profile,
                "Individual Regime": regime,
                "Business Profit Before Routing": profit_before,
                "Business Profit After Routing": profit_after,
                "Total Routed": total_routed,
                "Business Tax Without Routing": business_tax_without,
                "Business Tax With Routing": business_tax_with,
                "Business Tax Saved": business_tax_saved,
                "Estimated Parent Incremental Tax": parent_incremental_tax_total,
                "Actual Parent Tax Paid": actual_parent_tax_total,
                "Estimated Net Tax Saved": business_tax_saved - parent_incremental_tax_total,
                "Net Saved Using Actual Tax Paid": business_tax_saved - actual_parent_tax_total,
                **{f"Routed To {p}": v for p, v in routed_by_person.items()},
                **{f"Incremental Tax {p}": v for p, v in incremental_parent_tax.items()},
                **{f"Actual Tax Paid {p}": v for p, v in actual_tax_by_person.items()},
            }
        )
    return pd.DataFrame(rows)


def format_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = out[col].map(money)
    return out


def build_dashboard(df: pd.DataFrame, output_path: Path, source_snapshot_path: Path | None) -> None:
    records = df.to_dict(orient="records")
    payload = json.dumps(
        {
            "records": records,
            "sources": OFFICIAL_TAX_RATE_SOURCES,
            "sourceSnapshot": "" if source_snapshot_path is None else str(source_snapshot_path),
        },
        separators=(",", ":"),
    )
    output_path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Salary Routing Tax Savings Dashboard</title>
  <style>
    :root {{ --bg:#f6f7f9; --panel:#fff; --text:#18212b; --muted:#657385; --line:#d9e0e7; --a:#0f766e; --b:#2563eb; --c:#b45309; --d:#be123c; --e:#7c3aed; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text); font-family:Inter,ui-sans-serif,system-ui,Segoe UI,sans-serif; }}
    header {{ padding:22px 28px 14px; background:var(--panel); border-bottom:1px solid var(--line); position:sticky; top:0; z-index:5; }}
    h1 {{ margin:0; font-size:24px; }} h2 {{ margin:0 0 12px; font-size:17px; }} p {{ margin:0; color:var(--muted); }}
    main {{ display:grid; gap:16px; padding:20px 28px 36px; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }}
    .two {{ display:grid; grid-template-columns:1.35fr .9fr; gap:16px; }}
    .card {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:15px; }}
    .label {{ color:var(--muted); font-size:12px; letter-spacing:.05em; text-transform:uppercase; }}
    .value {{ margin-top:6px; font-size:24px; font-weight:750; }}
    .sub {{ margin-top:5px; color:var(--muted); font-size:13px; }}
    svg {{ width:100%; height:auto; display:block; }} .gridline {{ stroke:var(--line); stroke-width:1; }}
    .legend {{ display:flex; flex-wrap:wrap; gap:10px 16px; margin-top:10px; color:var(--muted); font-size:13px; }}
    .legend span {{ display:inline-flex; align-items:center; gap:6px; }} .swatch {{ width:10px; height:10px; border-radius:99px; display:inline-block; }}
    .table-wrap {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; min-width:1100px; font-size:13px; }}
    th,td {{ border-bottom:1px solid var(--line); padding:8px; text-align:right; white-space:nowrap; }} th:first-child,td:first-child {{ text-align:left; }} th {{ color:var(--muted); }}
    .notes {{ display:grid; gap:8px; color:var(--muted); line-height:1.45; }}
    button {{ border:1px solid var(--line); border-radius:7px; background:var(--a); color:white; padding:8px 10px; margin-top:12px; cursor:pointer; }}
    @media print {{ header {{ position:static; }} button {{ display:none; }} body {{ background:white; }} .card {{ break-inside:avoid; }} }}
    @media (max-width:900px) {{ .grid,.two {{ grid-template-columns:1fr 1fr; }} header,main {{ padding-left:16px; padding-right:16px; }} }}
    @media (max-width:620px) {{ .grid,.two {{ grid-template-columns:1fr; }} h1 {{ font-size:20px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Salary Routing Tax Savings Dashboard</h1>
    <p>FY 2013-14 to FY 2025-26. Compares business tax avoided against estimated incremental individual tax in Papa/Mummy ITRs.</p>
    <button onclick="window.print()">Export dashboard to PDF</button>
  </header>
  <main>
    <section class="grid" id="stats"></section>
    <section class="two">
      <div class="card"><h2>Tax Saved Trend</h2><svg id="line" viewBox="0 0 1120 430"></svg><div class="legend" id="lineLegend"></div></div>
      <div class="card"><h2>Interpretation</h2><div class="notes" id="notes"></div></div>
    </section>
    <section class="card"><h2>Business Tax Saved vs Parent Tax Cost</h2><svg id="bars" viewBox="0 0 1120 430"></svg><div class="legend" id="barLegend"></div></section>
    <section class="card"><h2>Year-wise Reassessment Matrix</h2><div class="table-wrap"><table id="table"></table></div></section>
  </main>
  <script>
    const payload = {payload};
    const data = payload.records;
    const fmt = new Intl.NumberFormat("en-IN", {{maximumFractionDigits:0}});
    const money = v => "Rs " + fmt.format(Math.round(v || 0));
    const colors = ["#0f766e","#2563eb","#b45309","#be123c","#7c3aed"];
    function path(points) {{ return points.map((p,i)=>`${{i?"L":"M"}} ${{p.x.toFixed(2)}} ${{p.y.toFixed(2)}}`).join(" "); }}
    function drawLine() {{
      const metrics = ["Business Tax Saved","Estimated Parent Incremental Tax","Estimated Net Tax Saved"];
      const W=1120,H=430,L=82,R=24,T=24,B=76,max=Math.max(...data.flatMap(r=>metrics.map(m=>r[m])),1),yMax=Math.ceil(max*1.12/100000)*100000 || 1;
      const x=i=>L+i*((W-L-R)/(data.length-1)), y=v=>T+(H-T-B)*(1-v/yMax);
      let html="";
      [0,.25,.5,.75,1].forEach(t=>{{ const val=yMax*t, yy=y(val); html += `<line class="gridline" x1="${{L}}" y1="${{yy}}" x2="${{W-R}}" y2="${{yy}}"></line><text x="${{L-10}}" y="${{yy+4}}" text-anchor="end" fill="#657385" font-size="11">${{(val/100000).toFixed(1)}}L</text>`; }});
      data.forEach((r,i)=>{{ const xx=x(i); html += `<text x="${{xx}}" y="${{H-38}}" text-anchor="middle" fill="#657385" font-size="11" transform="rotate(-35 ${{xx}} ${{H-38}})">${{r["Financial Year"]}}</text>`; }});
      metrics.forEach((m,idx)=>{{ const pts=data.map((r,i)=>({{x:x(i),y:y(r[m]),v:r[m],fy:r["Financial Year"]}})); html += `<path d="${{path(pts)}}" fill="none" stroke="${{colors[idx]}}" stroke-width="2.6"></path>`; pts.forEach(p=>html+=`<circle cx="${{p.x}}" cy="${{p.y}}" r="4" fill="${{colors[idx]}}"><title>${{m}} ${{p.fy}}: ${{money(p.v)}}</title></circle>`); }});
      document.getElementById("line").innerHTML=html;
      document.getElementById("lineLegend").innerHTML=metrics.map((m,i)=>`<span><i class="swatch" style="background:${{colors[i]}}"></i>${{m}}</span>`).join("");
    }}
    function drawBars() {{
      const metrics=["Business Tax Saved","Estimated Parent Incremental Tax","Estimated Net Tax Saved"], W=1120,H=430,L=82,R=24,T=24,B=76;
      const max=Math.max(...data.flatMap(r=>metrics.map(m=>r[m])),1), yMax=Math.ceil(max*1.12/100000)*100000 || 1, gw=(W-L-R)/data.length, bw=Math.max(8,gw*.18), y=v=>T+(H-T-B)*(1-v/yMax);
      let html="";
      [0,.25,.5,.75,1].forEach(t=>{{ const val=yMax*t, yy=y(val); html += `<line class="gridline" x1="${{L}}" y1="${{yy}}" x2="${{W-R}}" y2="${{yy}}"></line><text x="${{L-10}}" y="${{yy+4}}" text-anchor="end" fill="#657385" font-size="11">${{(val/100000).toFixed(1)}}L</text>`; }});
      data.forEach((r,i)=>{{ const cx=L+i*gw+gw/2; metrics.forEach((m,j)=>{{ const yy=y(r[m]); html+=`<rect x="${{cx+(j-1)*(bw+3)}}" y="${{yy}}" width="${{bw}}" height="${{H-B-yy}}" fill="${{colors[j]}}"><title>${{m}} ${{r["Financial Year"]}}: ${{money(r[m])}}</title></rect>`; }}); html += `<text x="${{cx}}" y="${{H-38}}" text-anchor="middle" fill="#657385" font-size="11" transform="rotate(-35 ${{cx}} ${{H-38}})">${{r["Financial Year"]}}</text>`; }});
      document.getElementById("bars").innerHTML=html;
      document.getElementById("barLegend").innerHTML=metrics.map((m,i)=>`<span><i class="swatch" style="background:${{colors[i]}}"></i>${{m}}</span>`).join("");
    }}
    function renderStats() {{
      const totals = {{
        routed: data.reduce((s,r)=>s+r["Total Routed"],0),
        businessSaved: data.reduce((s,r)=>s+r["Business Tax Saved"],0),
        parentTax: data.reduce((s,r)=>s+r["Estimated Parent Incremental Tax"],0),
        net: data.reduce((s,r)=>s+r["Estimated Net Tax Saved"],0),
      }};
      const cards=[["Total Routed",money(totals.routed),"Across available ITR years"],["Business Tax Saved",money(totals.businessSaved),"At selected business tax profile"],["Parent Tax Cost",money(totals.parentTax),"Incremental slab tax"],["Net Tax Saved",money(totals.net),"Business saved minus parent tax"]];
      document.getElementById("stats").innerHTML=cards.map(c=>`<article class="card"><div class="label">${{c[0]}}</div><div class="value">${{c[1]}}</div><div class="sub">${{c[2]}}</div></article>`).join("");
    }}
    function renderNotes() {{
      const peak=data.reduce((a,b)=>a["Estimated Net Tax Saved"]>b["Estimated Net Tax Saved"]?a:b);
      document.getElementById("notes").innerHTML=[
        `Peak estimated saving: ${{money(peak["Estimated Net Tax Saved"])}} in FY ${{peak["Financial Year"]}}.`,
        `The model uses FY-wise old-regime individual slabs and the selected business tax profile.`,
        `If you have actual books profit after routing, enter it in the matrix or use the CSV as the base for adjustment.`,
        `Sources: TRACES slab archive and Income Tax Department company/individual rate pages.`
      ].map(x=>`<div>${{x}}</div>`).join("");
    }}
    function renderTable() {{
      const cols=["Financial Year","Business Profile","Individual Regime","Total Routed","Business Tax Without Routing","Business Tax Saved","Estimated Parent Incremental Tax","Estimated Net Tax Saved","Net Saved Using Actual Tax Paid"];
      let html=`<thead><tr>${{cols.map(c=>`<th>${{c}}</th>`).join("")}}</tr></thead><tbody>`;
      data.forEach(r=>{{ html+="<tr>"; cols.forEach(c=>{{ const v=r[c]; html+=`<td>${{typeof v==="number"?money(v):v}}</td>`; }}); html+="</tr>"; }});
      document.getElementById("table").innerHTML=html+"</tbody>";
    }}
    renderStats(); drawLine(); drawBars(); renderNotes(); renderTable();
  </script>
</body>
</html>""",
        encoding="utf-8",
    )


def fetch_rate_source_snapshot(output_folder: Path) -> Path:
    output_folder.mkdir(exist_ok=True)
    path = output_folder / "official_tax_rate_sources_snapshot.json"
    snapshots = {}
    for key, url in OFFICIAL_TAX_RATE_SOURCES.items():
        try:
            with urllib.request.urlopen(url, timeout=12) as response:
                text = response.read(12000).decode("utf-8", errors="ignore")
            snapshots[key] = {"url": url, "fetched": True, "preview": text[:2000]}
        except Exception as exc:
            snapshots[key] = {"url": url, "fetched": False, "error": str(exc)}
    path.write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
    return path


def print_outputs(df: pd.DataFrame) -> None:
    cols = ["Financial Year", "Business Profile", "Total Routed", "Business Tax Saved", "Estimated Parent Incremental Tax", "Estimated Net Tax Saved"]
    print("\nYEAR-WISE ROUTING TAX SAVINGS")
    print(format_df(df[cols]).to_string(index=False))
    print("\nTOTALS")
    print(f"Total routed: {money(df['Total Routed'].sum())}")
    print(f"Business tax saved: {money(df['Business Tax Saved'].sum())}")
    print(f"Incremental parent tax: {money(df['Estimated Parent Incremental Tax'].sum())}")
    print(f"Estimated net tax saved: {money(df['Estimated Net Tax Saved'].sum())}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Graphical tax-routing reassessment simulator.")
    parser.add_argument("--person-folder", action="append", required=True, help="Example: Father=PapaITR")
    parser.add_argument("--business-profile", default="company_25", choices=sorted(BUSINESS_TAX_PROFILES))
    parser.add_argument("--individual-regime", default="old", choices=["old", "new"])
    parser.add_argument("--csv", default="tax_routing_simulation.csv")
    parser.add_argument("--dashboard", default="tax_routing_dashboard.html")
    parser.add_argument("--fetch-rate-sources", action="store_true")
    args = parser.parse_args()

    people = [parse_person_folder(item) for item in args.person_folder]
    matrix = build_year_matrix(people, args.business_profile, args.individual_regime)
    df = simulate(matrix)
    print_outputs(df)

    csv_path = Path(args.csv)
    df.to_csv(csv_path, index=False)
    snapshot_path = fetch_rate_source_snapshot(csv_path.parent) if args.fetch_rate_sources else None
    build_dashboard(df, Path(args.dashboard), snapshot_path)
    (csv_path.parent / "tax_routing_rate_assumptions.json").write_text(
        json.dumps(
            {
                "sources": OFFICIAL_TAX_RATE_SOURCES,
                "business_tax_profiles": BUSINESS_TAX_PROFILES,
                "individual_old_regime_by_fy": INDIVIDUAL_OLD_REGIME_BY_FY,
                "individual_new_regime_by_fy": INDIVIDUAL_NEW_REGIME_BY_FY,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved CSV: {csv_path.resolve()}")
    print(f"Saved dashboard: {Path(args.dashboard).resolve()}")
    print(f"Saved assumptions: {(csv_path.parent / 'tax_routing_rate_assumptions.json').resolve()}")
    if snapshot_path:
        print(f"Saved source snapshot: {snapshot_path.resolve()}")


if __name__ == "__main__":
    main()
