# Approach

## Extraction

The analyzer reads the PDF text layer with `pdfplumber`. It uses label-aware patterns for common ITR layouts across ITR-1, ITR-2, ITR-3, and ITR-4/Sugam style returns.

The script looks for recurring fields such as:

- Gross Salary and Salary
- Business and profession income
- Income from other sources
- STCG and LTCG
- Interest and dividend income
- Gross Total Income
- Deductions
- Total Income or Taxable Total Income
- Tax payable and total taxes paid

## Generation Order

The pipeline deliberately writes year-wise JSON first, then reloads those JSON files before building the dashboard and reports. This makes the JSON the auditable intermediate layer.

## Local-First

No cloud APIs are required. Financial documents stay local. Generated outputs are ignored by Git.

