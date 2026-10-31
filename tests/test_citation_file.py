"""CITATION.cff stays valid CFF 1.2.0 at the top level (no YAML dependency: the file is flat)."""

from __future__ import annotations

import re
import unittest

import _support  # noqa: F401
from _support import ROOT

# Top-level keys CFF 1.2.0 allows (https://citation-file-format.github.io/).
CFF_1_2_0_KEYS = {
    "abstract", "authors", "cff-version", "commit", "contact", "date-released", "doi", "identifiers", "keywords",
    "license", "license-url", "message", "preferred-citation", "references", "repository", "repository-artifact",
    "repository-code", "title", "type", "url", "version",
}


class CitationFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.keys = re.findall(r"^([A-Za-z][A-Za-z0-9-]*):", self.text, re.M)

    # Value: protects=CITATION.cff has the required CFF 1.2.0 keys and no key the format does not define (a stray `note:` would fail GitHub's citation parser); fails_when=a required key is dropped or an unknown top-level key is added; why_new=the file did not exist; seam=none; no_claim=full schema validation
    def test_required_keys_present_and_no_unknown_top_level_key(self) -> None:
        for required in ("cff-version", "message", "title", "authors"):
            self.assertIn(required, self.keys)
        self.assertEqual(sorted(set(self.keys) - CFF_1_2_0_KEYS), [])
        self.assertEqual(len(self.keys), len(set(self.keys)), "a top-level key is given twice")
        self.assertRegex(self.text, r'(?m)^cff-version: 1\.2\.0$')

    # Value: protects=the file names the author, the code licence and the layered data licences, and claims no DOI or version before one exists; fails_when=a DOI, version or date-released is invented, or the layered-licence note is dropped; why_new=a DOI per release is still open (needs a Zenodo account); seam=none; no_claim=wording
    def test_content_matches_what_is_decided(self) -> None:
        self.assertIn("license: MIT", self.text)
        self.assertIn('family-names: "Veh"', self.text)
        self.assertIn("ADR 0003", self.text)
        self.assertIn("layers", self.text)
        for key in ("doi", "version", "date-released", "identifiers", "repository-code"):
            self.assertNotIn(key, self.keys)


if __name__ == "__main__":
    unittest.main()
