from __future__ import annotations

import unittest

import _support  # noqa: F401
from python_version_guard import require_supported_python


class PythonVersionGuardTests(unittest.TestCase):
    def test_accepts_minimum_and_newer_python_versions(self) -> None:
        require_supported_python((3, 11, 0))
        require_supported_python((3, 13, 1))
        require_supported_python((4, 0, 0))

    def test_rejects_older_python_with_bilingual_message(self) -> None:
        for version, found in [((2, 7, 18), "2.7"), ((3, 9, 0), "3.9"), ((3, 10, 12), "3.10")]:
            with self.subTest(version=version), self.assertRaises(SystemExit) as raised:
                require_supported_python(version)
            self.assertEqual(
                str(raised.exception),
                f"error: Python 3.11 or newer is required (found {found}). / "
                f"Fehler: Python 3.11 oder neuer ist erforderlich (gefunden {found}).",
            )


if __name__ == "__main__":
    unittest.main()
