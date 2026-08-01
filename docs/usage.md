# CLI Usage

## Analyze A Folder

```powershell
python analysis.py --folder "..\sample-data\person-a"
```

## Analyze Without PDF Report

```powershell
python analysis.py --folder "..\sample-data\person-b" --no-pdf
```

## Expected File Naming

PDF names should include the financial year:

```text
2013-14.pdf
2014-15.pdf
2025-26.pdf
```

The assessment year is inferred from the financial year.
