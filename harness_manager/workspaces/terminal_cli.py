"""Run the bundled stack CLI in the terminal's project directory.

The caller uses Python's isolated mode. Resolve the bundled implementation here
so a same-named module in a project cannot shadow a command launched by the UI.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from harness_manager.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
