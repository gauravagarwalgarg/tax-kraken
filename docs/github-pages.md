# GitHub Pages

This repo includes two workflows:

- `CI`: compiles Python and builds MkDocs on every pull request and push to `main`.
- `Publish Docs`: deploys MkDocs to GitHub Pages on push to `main` or manual dispatch.

## Enable Pages

In GitHub:

1. Open repository settings.
2. Go to **Pages**.
3. Select the `gh-pages` branch after the first docs deployment.

## Local Docs

```powershell
python -m pip install -e ".[docs]"
mkdocs serve
```

