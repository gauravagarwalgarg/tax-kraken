# Example Folder Layout

Keep private ITR PDFs outside Git-tracked files. A typical local workspace can look like this:

```text
workspace/
  tax-kraken/
    analysis.py
    tax_routing_simulation.py
  sample-data/
    person-a/
      2013-14.pdf
      2014-15.pdf
    person-b/
      2013-14.pdf
      2014-15.pdf
```

Run from inside `tax-kraken`:

```powershell
python analysis.py --folder ..\sample-data\person-a
python analysis.py --folder ..\sample-data\person-b
python tax_routing_simulation.py --person-folder PersonA=..\sample-data\person-a --person-folder PersonB=..\sample-data\person-b
```
