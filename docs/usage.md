# CLI Usage

## Analyze A Folder

```powershell
tax-kraken-analysis --folder "..\sample-data\person-a"
```

## Analyze Without PDF Report

```powershell
tax-kraken-analysis --folder "..\sample-data\person-b" --no-pdf
```

From a source checkout, `python analysis.py --folder <folder>` is also supported as a compatibility launcher.

## Expected File Naming

PDF names should include the financial year:

```text
2013-14.pdf
2014-15.pdf
2025-26.pdf
```

The assessment year is inferred from the financial year.
