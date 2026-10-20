"""Run the complete offline unit suite and browser checks for any selected lane."""

from pathlib import Path
import subprocess
import sys
import unittest


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    if Path.cwd() != root:
        raise SystemExit("Run tests/run_pregate.py from the repository root")
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required")
    # Run the full suite: Python's scripts/ imports are invisible to lane selection.
    print("Selected paths:", ", ".join(sys.argv[1:]), flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover("tests")
    )
    if not result.wasSuccessful():
        raise SystemExit(1)
    subprocess.run(
        ["node", "tests/run_bills_browser_check.mjs", sys.executable], check=True
    )
    print(f"Ran {result.testsRun + 1} tests across unit suite and browser integration", flush=True)
