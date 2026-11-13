"""Tests that pinned a located refusal ("unresolved nested contribution at R
marker 2") now pin that the parser withholds that Rede with the same message
(ADR 0005): the rule that decides is unchanged, only its consequence moved from
refusing the sitting to withholding one Rede."""

import contextlib
import re
from unittest import mock

import validate_dip_protocol as dip


@contextlib.contextmanager
def assert_withheld(test, pattern):
    """In place of ``assertRaisesRegex(ValueError, pattern)`` around a parse:
    every ``parse_protocol_xml`` call in the block is observed, and some Rede
    must be withheld for a located refusal whose message matches ``pattern``."""
    original = dip.parse_protocol_xml
    withheld = []

    def observed(*args, **kwargs):
        parsed = original(*args, **kwargs)
        withheld.extend(w for top in parsed["agenda_items"] for w in top["withheld"])
        return parsed

    with mock.patch.object(dip, "parse_protocol_xml", observed):
        yield withheld
    located = [w for w in withheld if w["reason"] != "reviewed"]
    test.assertTrue(any(re.search(pattern, w["reason_detail"]) for w in located),
                    f"no Rede withheld for a refusal matching {pattern!r}; withheld: {[w['reason_detail'] for w in located]}")
