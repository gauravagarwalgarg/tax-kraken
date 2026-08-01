# Tax Kraken 🦑

[![Docs](https://github.com/gauravagarwalgarg/tax-kraken/actions/workflows/docs.yml/badge.svg)](https://github.com/gauravagarwalgarg/tax-kraken/actions/workflows/docs.yml)
[![Docs Live](https://img.shields.io/badge/docs-live-brightgreen.svg)](https://gauravagarwalgarg.github.io/tax-kraken/)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Tax Kraken is a local-first Indian Income Tax Return post-analysis toolkit. It extracts year-wise ITR PDF data, generates private JSON datasets, builds interactive dashboards, estimates forward trends, and simulates tax saved by routing business income as salary/remuneration to related individuals.

## What It Does

- Accepts any folder containing FY-named ITR PDFs such as `2019-20.pdf`.
- Generates local JSON first, then reloads that JSON to build analysis outputs.
- Extracts salary, gross salary, business income, other-source income, STCG, LTCG, interest, dividend, deductions, gross total income, total income, tax payable, and total tax paid.
- Produces an interactive dashboard with tabs for overview, trends, forecast, tax/net-worth proxy, and data quality.
- Creates a PDF report and CSV export.
- Simulates tax saved from salary/remuneration routing using FY-wise Indian individual slabs and configurable business tax profiles.
- Keeps generated JSON and reports out of Git by default.

## Quick Start

```powershell
python -m pip install -e ".[docs]"
tax-kraken-analysis --folder "..\sample-data\person-a"
tax-kraken-analysis --folder "..\sample-data\person-b"
```

Open the generated `dashboard.html` inside the target folder.

## Salary Routing Simulation

After generating JSON for each ITR folder:

```powershell
tax-kraken-routing --person-folder PersonA="..\sample-data\person-a" --person-folder PersonB="..\sample-data\person-b" --business-profile company_25 --individual-regime old --fetch-rate-sources
```

Open `tax_routing_dashboard.html` for the graphical reassessment.

The package entry points are defined in the installed project metadata and can be invoked through the console scripts `tax-kraken-analysis` and `tax-kraken-routing` after installing the package.
For repeated runs, write routing outputs into an ignored folder such as `runs/`.

## Outputs

Each analyzed folder receives:

- `json/YYYY-YY.json` - one JSON file per financial year.
- `json/all_years.json` - consolidated dataset.
- `json/summary.json` - analytics, forecasts, tax planning, and net-worth proxy.
- `output/itr_dataset.csv` - flat export.
- `output/itr_post_analysis_report.pdf` - printable report.
- `dashboard.html` - interactive local dashboard.

The routing simulator also creates:

- `tax_routing_simulation.csv`
- `tax_routing_dashboard.html`
- `tax_routing_rate_assumptions.json`
- `official_tax_rate_sources_snapshot.json`

## Privacy

This tool is local-first. Generated JSON, dashboards, reports, CSV files, and source PDFs are ignored in `.gitignore` because they can contain sensitive personal financial data.

## Documentation

Build docs locally:

```powershell
python -m pip install -e ".[docs]"
mkdocs serve
```

## GitHub CI/CD

The repo includes GitHub Actions for:

- Python compile checks.
- Strict MkDocs build.
- GitHub Pages deployment from `main` via the Pages workflow.

For the Pages workflow to work, GitHub repository settings must have Pages enabled with the source set to GitHub Actions.

## Disclaimer

Tax Kraken is an analytical aid, not a substitute for a Chartered Accountant or formal tax opinion. Verify all extracted values, assumptions, related-party rules, TDS treatment, and business-structure implications before using outputs for tax decisions.
