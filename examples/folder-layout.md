# Example Folder Layout

Keep private ITR PDFs outside Git-tracked files. A typical local workspace can look like this:

```text
workspace/
  tax-kraken/
    analysis.py
    tax_routing_simulation.py
  PapaITR/
    2013-14.pdf
    2014-15.pdf
  MummyITR/
    2013-14.pdf
    2014-15.pdf
```

Run from inside `tax-kraken`:

```powershell
python analysis.py --folder ..\PapaITR
python analysis.py --folder ..\MummyITR
python tax_routing_simulation.py --person-folder Father=..\PapaITR --person-folder Mother=..\MummyITR
```

