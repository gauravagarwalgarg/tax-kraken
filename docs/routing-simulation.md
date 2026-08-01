# Salary Routing Simulation

The routing simulator estimates tax saved when business income is paid out as salary or remuneration to related individuals and taxed in their ITRs.

## Command

```powershell
tax-kraken-routing --person-folder PersonA=..\sample-data\person-a --person-folder PersonB=..\sample-data\person-b --business-profile company_25 --individual-regime old --fetch-rate-sources
```

From a source checkout, `python tax_routing_simulation.py ...` is also supported as a compatibility launcher.

## Outputs

- `tax_routing_simulation.csv`
- `tax_routing_dashboard.html`
- `tax_routing_rate_assumptions.json`
- `official_tax_rate_sources_snapshot.json`

These files are ignored by Git because they can reveal private financial data.
For repeated experiments, use output paths under an ignored folder such as `runs/`.

## Interpretation

The model compares:

- Scenario A: business keeps the routed amount and pays business tax.
- Scenario B: business deducts salary/remuneration and related individuals pay incremental individual tax.

Net saving is:

```text
business tax saved - estimated incremental individual tax
```

## Caveat

The simulation is an analytical estimate. Actual tax treatment depends on business structure, books of account, reasonableness of remuneration, TDS compliance, related-party rules, and the applicable regime for each taxpayer.
