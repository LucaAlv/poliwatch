"""Runtime check for the Python version required by command line scripts."""

import sys
from typing import Sequence


MINIMUM_PYTHON = (3, 11)


def require_supported_python(version_info: Sequence[int] = sys.version_info) -> None:
    """Exit with an actionable bilingual message when Python is too old."""
    version = (version_info[0], version_info[1])
    if version < MINIMUM_PYTHON:
        found = f"{version[0]}.{version[1]}"
        raise SystemExit(
            "error: Python 3.11 or newer is required (found "
            f"{found}). / Fehler: Python 3.11 oder neuer ist erforderlich "
            f"(gefunden {found})."
        )
