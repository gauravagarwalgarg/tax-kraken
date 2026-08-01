# Example Folder Layout

Keep private ITR PDFs outside Git-tracked files. A typical local workspace can look like this:

```text
workspace/
  tax-kraken/
    analysis.py
    tax_routing_simulation.py
    src/
      tax_kraken/
        analysis.py
        routing_simulation.py
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
tax-kraken-analysis --folder ..\sample-data\person-a
tax-kraken-analysis --folder ..\sample-data\person-b
tax-kraken-routing --person-folder PersonA=..\sample-data\person-a --person-folder PersonB=..\sample-data\person-b
```
