# Features

## Dashboard

The generated dashboard includes:

- KPI cards for latest income, peak income, tax paid, and total income.
- Income composition stacked bars.
- Multi-metric trend lines with selectable metrics.
- Year-over-year heatmap.
- Three-year statistical forecast with uncertainty bands.
- Tax payable versus tax paid comparison.
- Net-worth proxy and tax-saving estimates.
- Data quality warnings from extraction checks.

## Export

The browser dashboard can be printed to PDF. The script also creates a report PDF through ReportLab and a CSV file for spreadsheet analysis.

## Data Quality

The analyzer adds warnings when:

- Components do not reconcile to Gross Total Income.
- Income values are missing.
- Tax payable is positive but taxes paid is zero in extracted fields.

