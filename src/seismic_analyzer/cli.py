"""Command-line entry point."""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Launch the local Streamlit workstation."""
    app = Path(__file__).resolve().parents[2] / "app.py"
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app), *sys.argv[1:]]))
