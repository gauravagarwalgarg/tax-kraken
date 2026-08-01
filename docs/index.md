# ITR Post Analyzer

ITR Post Analyzer is a folder-driven tool for Indian Income Tax Return PDF analysis. It turns a folder of year-wise ITR PDFs into local JSON, an interactive dashboard, a CSV, and a PDF report.

The tool is designed for private local use first. The generated data is intentionally ignored by Git.

## Core Workflow

1. Put PDFs in a folder with names like `2018-19.pdf`.
2. Run `tax-kraken-analysis --folder <folder>`.
3. The tool extracts data and writes JSON files.
4. The dashboard is generated from the JSON, not from hidden in-memory state.
5. Review `dashboard.html`, `json/summary.json`, and `output/itr_post_analysis_report.pdf`.
