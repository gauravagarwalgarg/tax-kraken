"""Compatibility launcher for the Tax Kraken ITR analyzer."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from tax_kraken.analysis import main


if __name__ == "__main__":
    main()
