import unittest

import _support
import validate_dip_protocol as dip


def _rede(rid, words):
    return f'''<rede id="{rid}">
      <p klasse="redner"><redner id="{rid}"><name><vorname>Test</vorname><nachname>{rid}</nachname><fraktion>SPD</fraktion></name></redner></p>
      <p klasse="J">{words}</p>
    </rede>'''


def _parse(block_body, tops):
    xml = f'''<dbtplenarprotokoll><anlagen><anlage><anlagen-text anlagen-typ="Zu Protokoll gegebene Reden">
      {block_body}
    </anlagen-text></anlage></anlagen></dbtplenarprotokoll>'''
    return dip.written_contributions(dip.ET.fromstring(xml), tops, {})


def _tops(*top_ids):
    return [{"top_id": f"Tagesordnungspunkt {n}", "contributions": []} for n in top_ids]


class WrittenTopAssociationTests(unittest.TestCase):
    def test_submissions_follow_local_top_context_in_one_annex(self):
        tops = _tops(1, 2)
        unassigned = _parse(
            f'''<p klasse="Anlage_3">(Tagesordnungspunkt 1)</p>
            {_rede("R1", "Beitrag eins")}
            <p klasse="Anlage_3">Weitere Reden zu einer anderen Beratung</p>
            {_rede("R2", "Beitrag ohne TOP")}
            <p klasse="Anlage_3">(Tagesordnungspunkt 2)</p>
            {_rede("R3", "Beitrag zwei")}''', tops)

        self.assertEqual([c["rede_id"] for c in tops[0]["contributions"]], ["R1"])
        self.assertEqual([c["rede_id"] for c in unassigned], ["R2"])
        self.assertEqual([c["rede_id"] for c in tops[1]["contributions"]], ["R3"])
        self.assertEqual(tops[0]["contributions"][0]["top_association_evidence"], "(Tagesordnungspunkt 1)")
        self.assertEqual(tops[1]["contributions"][0]["top_association_evidence"], "(Tagesordnungspunkt 2)")

    def test_submission_before_later_reference_stays_unassigned(self):
        tops = _tops(2)
        unassigned = _parse(
            f'''<p klasse="Anlage_3">Reden zu einer Beratung</p>
            {_rede("R1", "Noch ohne TOP")}
            <p klasse="Anlage_3">(Tagesordnungspunkt 2)</p>
            {_rede("R2", "TOP zwei") }''', tops)

        self.assertEqual([c["rede_id"] for c in unassigned], ["R1"])
        self.assertEqual(unassigned[0]["top_association_evidence"], "Reden zu einer Beratung")
        self.assertEqual([c["rede_id"] for c in tops[0]["contributions"]], ["R2"])

    def test_multiple_references_remain_ambiguous(self):
        tops = _tops(1, 2)
        unassigned = _parse(
            f'''<p klasse="Anlage_3">(Tagesordnungspunkt 1) und (Tagesordnungspunkt 2)</p>
            {_rede("R1", "Mehrdeutiger Beitrag")}''', tops)

        self.assertEqual([c["rede_id"] for c in unassigned], ["R1"])
        self.assertEqual([top["contributions"] for top in tops], [[], []])


if __name__ == "__main__":
    unittest.main()
