from __future__ import annotations

import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import _support  # noqa: F401
import build_dip_pulse_site
import persist_dip_pulse_store as pulse_store
from features import all_selection, default_selection


class DossierProgressTests(unittest.TestCase):
    def test_reports_new_cached_and_completed_dossiers(self) -> None:
        protocols = [
            {"id": "5805", "dokumentnummer": "21/87", "datum": "2026-06-25"},
            {"id": "5806", "dokumentnummer": "21/88", "datum": "2026-06-26"},
        ]
        cached_report = {"protocol": protocols[1]}
        built: list[tuple[str, dict[str, Any] | None]] = []

        def load_existing(protocol: dict[str, Any]) -> dict[str, Any] | None:
            return cached_report if protocol["id"] == "5806" else None

        def build_dossier(
            protocol: dict[str, Any], existing: dict[str, Any] | None
        ) -> dict[str, Any]:
            built.append((protocol["id"], existing))
            return {"report": {"protocol": protocol}}

        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr):
            entries = build_dip_pulse_site.build_dossiers_with_progress(
                protocols,
                load_existing=load_existing,
                build_dossier=build_dossier,
            )

        output = stderr.getvalue()
        self.assertIn("[dossiers] Processing 2 dossier(s).", output)
        self.assertIn("[1/2] Downloading new dossier: BT-PlPr 21/87 (ID 5805) from 2026-06-25.", output)
        self.assertIn("[2/2] Refreshing cached dossier: BT-PlPr 21/88 (ID 5806) from 2026-06-26.", output)
        self.assertIn("[dossiers] Completed 2/2 dossier(s)", output)
        self.assertEqual(built, [("5805", None), ("5806", cached_report)])
        self.assertEqual(len(entries), 2)


class CollectAbgeordneteTests(unittest.TestCase):
    def test_offline_main_migrates_legacy_database_before_collecting_mps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            database_path = output_dir / "data" / "bundestag-pulse.sqlite"
            conn = pulse_store.connect(database_path)
            try:
                conn.executescript(
                    """
                    CREATE TABLE parties (
                      id INTEGER PRIMARY KEY,
                      name TEXT NOT NULL UNIQUE,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    );

                    CREATE TABLE mps (
                      id INTEGER PRIMARY KEY,
                      identity_key TEXT NOT NULL UNIQUE,
                      dip_person_id TEXT UNIQUE,
                      xml_redner_id TEXT,
                      display_name TEXT NOT NULL,
                      title TEXT,
                      function TEXT,
                      wahlperiode TEXT,
                      profile_url TEXT,
                      party_id INTEGER,
                      created_at TEXT NOT NULL,
                      updated_at TEXT NOT NULL
                    );
                    """
                )
            finally:
                conn.close()

            args = SimpleNamespace(
                output_dir=output_dir,
                database_path=None,
                offline=True,
                no_persist=False,
            )
            with (
                mock.patch.object(build_dip_pulse_site, "parse_args", return_value=args),
                mock.patch.object(build_dip_pulse_site, "load_cached_protocols", return_value=[{"id": "cached"}]),
                mock.patch.object(build_dip_pulse_site, "rebuild_cached_detail_pages", return_value=[]),
                mock.patch.object(
                    build_dip_pulse_site,
                    "render_site",
                    return_value=output_dir / "index.html",
                ),
            ):
                self.assertEqual(build_dip_pulse_site.main(), 0)

            conn = pulse_store.connect(database_path)
            try:
                columns = {row["name"] for row in conn.execute("PRAGMA table_info(mps)")}
            finally:
                conn.close()
            self.assertIn("birth_year", columns)

    def test_write_report_reuses_catalog_protocol_metadata(self) -> None:
        protocol = {
            "id": "5805",
            "dokumentnummer": "21/87",
            "fundstelle": {"xml_url": "https://example.test/protocol.xml"},
        }
        report = {"protocol": {"id": "5805"}, "agenda_items": []}
        expected_entry = {"report": report}

        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.object(build_dip_pulse_site.dip, "build_report", return_value=report) as build_report,
            mock.patch.object(
                build_dip_pulse_site,
                "write_report_files",
                return_value=expected_entry,
            ),
        ):
            entry = build_dip_pulse_site.write_report_and_page(
                protocol=protocol,
                output_dir=Path(tmp),
                api_key="test-key",
                sleep=0,
                person_limit=0,
                vote_scan_pages=0,
                roll_call_list_id=None,
                summary_mode="off",
                summary_provider="auto",
                anthropic_api_key=None,
                gemini_api_key=None,
                summary_model=None,
                existing_report=None,
            )

        self.assertIs(entry, expected_entry)
        self.assertIs(build_report.call_args.kwargs["protocol"], protocol)

    def test_collect_abgeordnete_groups_rows_sharing_external_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            conn = pulse_store.connect(Path(tmp) / "pulse.sqlite")
            try:
                pulse_store.initialize(conn)
                now = pulse_store.utc_now()
                with conn:
                    party_id = pulse_store.upsert_party(conn, "SPD", now)
                    roster_mp_id = pulse_store.upsert_mp(
                        conn,
                        now=now,
                        display_name="Ada Lovelace, MdB, SPD",
                        party_id=party_id,
                        identity_key=pulse_store.mp_identity(dip_person_id="dip-ada"),
                        dip_person_id="dip-ada",
                        aw_politician_id=77,
                        profession="Mathematician",
                        is_mdb=True,
                    )
                    speaker_mp_id = pulse_store.upsert_mp(
                        conn,
                        now=now,
                        display_name="Ada Lovelace",
                        party_id=party_id,
                        identity_key=pulse_store.mp_identity(xml_redner_id="11001"),
                        xml_redner_id="11001",
                        aw_politician_id=77,
                    )
                    conn.execute(
                        """
                        INSERT INTO protocols(id, document_number, date, title, xml_header_json, created_at, updated_at)
                        VALUES ('pp-test', '20/999', '2024-05-15', 'Test protocol', '{}', ?, ?)
                        """,
                        (now, now),
                    )
                    conn.execute(
                        """
                        INSERT INTO agenda_items(protocol_id, item_index, top_id, heading, created_at, updated_at)
                        VALUES ('pp-test', 1, 'T1', 'TOP 1 Test', ?, ?)
                        """,
                        (now, now),
                    )
                    agenda_item_id = conn.execute("SELECT id FROM agenda_items").fetchone()["id"]
                    conn.execute(
                        """
                        INSERT INTO speeches(
                          protocol_id, agenda_item_id, rede_id, sequence, mp_id, page,
                          paragraph_count, char_count, text, paragraphs_json, snippet,
                          created_at, updated_at
                        )
                        VALUES ('pp-test', ?, 'R1', 1, ?, 101, 1, 24, 'Rede text', '[]', 'Rede text', ?, ?)
                        """,
                        (agenda_item_id, speaker_mp_id, now, now),
                    )

                mps, lookup = build_dip_pulse_site.collect_abgeordnete(conn)

                self.assertEqual(len(mps), 1)
                mp = mps[0]
                self.assertEqual(mp["id"], roster_mp_id)
                self.assertEqual(mp["name"], "Ada Lovelace")
                self.assertEqual(mp["profession"], "Mathematician")
                self.assertEqual(mp["speech_count"], 1)
                self.assertEqual(mp["speeches"][0]["rede_id"], "R1")
                self.assertEqual(lookup["aw:77"], roster_mp_id)
                self.assertEqual(lookup["dip:dip-ada"], roster_mp_id)
                self.assertEqual(lookup["xml:11001"], roster_mp_id)
            finally:
                conn.close()


class CurrentPulseOrderTests(unittest.TestCase):
    """The site treats entries[0]/protocols[0] as the current pulse."""

    @staticmethod
    def _protocol(document_number: str, protocol_id: str, datum: str) -> dict[str, Any]:
        return {
            "id": protocol_id,
            "dokumentnummer": document_number,
            "datum": datum,
            "titel": f"Protokoll der Sitzung {document_number}",
        }

    @staticmethod
    def _entry(output_dir: Path, protocol: dict[str, Any]) -> dict[str, Any]:
        report_path, page_path, slug = build_dip_pulse_site.report_paths(
            output_dir, protocol["dokumentnummer"]
        )
        return {
            "report": {"protocol": protocol, "agenda_items": [], "validation_summary": {}},
            "report_path": report_path,
            "page_path": page_path,
            "slug": slug,
        }

    @staticmethod
    def _output_dir(tmp: str) -> Path:
        output_dir = Path(tmp) / "site"
        for name in ("data", "protocols", "bills", "abgeordnete"):
            (output_dir / name).mkdir(parents=True, exist_ok=True)
        return output_dir

    @staticmethod
    def _agenda_item(
        index: int,
        speech_count: int,
        fractions: tuple[str, ...],
        heading: str | None = None,
    ) -> dict[str, Any]:
        return {
            "index": index,
            "top_id": f"TOP {index}",
            "heading": f"Beratung des Antrags {index}" if heading is None else heading,
            "xml_speech_count": speech_count,
            "xml_speakers": [
                {"speaker": {"fraktion": fraction}, "char_count": 1000}
                for fraction in fractions
            ],
        }

    def _render_pulse(
        self,
        sittings: list[tuple[dict[str, Any], list[dict[str, Any]]]],
        features: Any = None,
    ) -> str:
        """Render a whole site for the given (protocol, agenda_items) sittings.

        Returns puls.html, whose hero lede is an aggregate over entries[0].
        """
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            entries = []
            for protocol, items in sittings:
                entry = self._entry(output_dir, protocol)
                entry["report"]["agenda_items"] = items
                entries.append(entry)
            kwargs: dict[str, Any] = dict(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol for protocol, _ in sittings],
                entries=entries,
                abg_mps=[],
                mp_lookup={},
            )
            if features is not None:
                kwargs["features"] = features
            build_dip_pulse_site.render_site(**kwargs)
            return (output_dir / "puls.html").read_text(encoding="utf-8")

    def _lede_panel(self, markup: str) -> str:
        """The hero's left panel only, sliced out of puls.html.

        Lede assertions must be scoped to it: fraction badges like "FDP 1" and
        "#top-" anchors also render in the attention cards further down the page,
        so a whole-document assertIn cannot tell the sitting-wide lede aggregate
        apart from the per-item ranking and would pass for the wrong reason.
        """
        match = re.search(
            r'<div class="latest-panel pulse-lede">(.*?)<div class="context-panel',
            markup,
            re.S,
        )
        self.assertIsNotNone(match, "puls.html has no hero lede panel")
        return match.group(1)

    @staticmethod
    def _lede_rows(lede: str) -> list[tuple[str, str, str]]:
        """(href, TOP id, speech share) per row of the "Meiste Aufmerksamkeit" block."""
        return [
            (href, top_id, share)
            for href, top_id, _heading, share in re.findall(
                r'<a class="lede-top" href="([^"]+)"><span>([^<]+)</span>'
                r"<strong>([^<]*)</strong><em>([^<]+)</em></a>",
                lede,
            )
        ]

    @staticmethod
    def _lede_badges(lede: str) -> list[str]:
        return re.findall(r'<span class="badge">([^<]+)</span>', lede)

    def test_render_site_puts_newest_sitting_first(self) -> None:
        # Cached dossiers reach render_site in glob order, where the slug "20-100"
        # sorts before "21-84" even though its sitting is three years older.
        old = self._protocol("20/100", "4200", "2023-04-27")
        new = self._protocol("21/84", "5799", "2026-06-12")
        protocols = [old, new]

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            entries = [self._entry(output_dir, old), self._entry(output_dir, new)]

            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=protocols,
                entries=entries,
                abg_mps=[],
                mp_lookup={},
            )

            for page in ("puls.html", "index.html", "overview.html", "sources.html"):
                markup = (output_dir / page).read_text(encoding="utf-8")
                self.assertIn("21/84", markup, msg=page)

            pulse_markup = (output_dir / "puls.html").read_text(encoding="utf-8")
            self.assertIn("2026-06-12", pulse_markup)
            self.assertNotIn("2023-04-27", pulse_markup)

    def test_pulse_lede_summarises_the_newest_sitting(self) -> None:
        # The hero's left panel is a summary of entries[0], not a nav bar: it
        # aggregates item_stats() across the sitting into a fraction stack and the
        # three busiest agenda items. It must never link #abstimmungen, whose
        # target only exists when the votes Baustein is built.
        pulse_markup = self._render_pulse(
            [
                (
                    self._protocol("21/84", "5799", "2026-06-12"),
                    [
                        self._agenda_item(1, 3, ("SPD", "CDU/CSU", "AfD")),
                        self._agenda_item(2, 2, ("SPD", "GRÜNE")),
                        self._agenda_item(3, 1, ("DIE LINKE",)),
                        self._agenda_item(4, 1, ("FDP",)),
                    ],
                )
            ]
        )
        lede = self._lede_panel(pulse_markup)

        self.assertIn("Zusammenfassung der aktuellsten Sitzung", pulse_markup)
        self.assertIn("Redeanteile nach Fraktion", lede)
        # Only the three busiest agenda items reach the lede.
        self.assertEqual(lede.count('class="lede-top"'), 3)
        self.assertIn("protocols/plenarprotokoll-21-84.html#top-1", lede)
        self.assertNotIn("#top-4", lede)
        # The fraction stack is built from every item, not just the ranked
        # three. Asserted on the stack's own title attribute inside the lede:
        # FDP is 6th by most_common(5) so it never earns a badge here, and
        # the bare string "FDP 1" would otherwise match the attention card
        # for TOP 4 further down the page.
        self.assertIn('title="FDP: 1"', lede)
        # #abstimmungen only exists when the votes Baustein is built.
        self.assertNotIn("#abstimmungen", pulse_markup)

    def test_lede_fraction_split_counts_agenda_items_outside_the_top_three(self) -> None:
        # The stack aggregates every item's party_counts, but only the five
        # loudest fractions get a badge; the rest collapse into "+N weitere".
        # Scoped to the lede because the attention card for TOP 4 renders its own
        # "FDP 1" badge and would satisfy a whole-page assertion by itself.
        lede = self._lede_panel(
            self._render_pulse(
                [
                    (
                        self._protocol("21/84", "5799", "2026-06-12"),
                        [
                            self._agenda_item(1, 3, ("SPD", "CDU/CSU", "AfD")),
                            self._agenda_item(2, 2, ("SPD", "GRÜNE")),
                            self._agenda_item(3, 1, ("DIE LINKE",)),
                            self._agenda_item(4, 1, ("FDP",)),
                        ],
                    )
                ]
            )
        )

        # TOP 4 never reaches the ranking rows, but its speaker still counts.
        self.assertIn('title="FDP: 1"', lede)
        # SPD spoke in two separate items and is summed, not overwritten.
        self.assertIn('title="SPD: 2"', lede)
        self.assertEqual(
            self._lede_badges(lede),
            ["SPD 2", "CDU/CSU 1", "AfD 1", "GRÜNE 1", "DIE LINKE 1", "+1 weitere"],
        )

    def test_lede_omits_the_overflow_badge_at_five_fractions(self) -> None:
        # Boundary of `len(sitting_party_counts) > 5`: five fractions all fit.
        lede = self._lede_panel(
            self._render_pulse(
                [
                    (
                        self._protocol("21/84", "5799", "2026-06-12"),
                        [
                            self._agenda_item(
                                1,
                                5,
                                (
                                    "SPD",
                                    "CDU/CSU",
                                    "AfD",
                                    "BÜNDNIS 90/DIE GRÜNEN",
                                    "Die Linke",
                                ),
                            )
                        ],
                    )
                ]
            )
        )

        self.assertEqual(
            self._lede_badges(lede),
            ["SPD 1", "CDU/CSU 1", "AfD 1", "BÜNDNIS 90/DIE GRÜNEN 1", "Die Linke 1"],
        )
        self.assertNotIn("weitere", lede)

    def test_lede_rows_are_the_three_busiest_tops_in_order(self) -> None:
        # Agenda order is deliberately not speech order, so a lost sort cannot
        # pass by accident of arrival. Shares are counted against the sitting.
        lede = self._lede_panel(
            self._render_pulse(
                [
                    (
                        self._protocol("21/84", "5799", "2026-06-12"),
                        [
                            self._agenda_item(1, 1, ("SPD",)),
                            self._agenda_item(2, 5, ("CDU/CSU",)),
                            self._agenda_item(3, 3, ("AfD",)),
                            self._agenda_item(4, 2, ("SPD",)),
                        ],
                    )
                ]
            )
        )

        self.assertEqual(
            [(top_id, share) for _href, top_id, share in self._lede_rows(lede)],
            [("TOP 2", "45.5%"), ("TOP 3", "27.3%"), ("TOP 4", "18.2%")],
        )

    def test_lede_lists_every_top_when_the_sitting_has_fewer_than_three(self) -> None:
        # `ranked_items[:3]` must not pad or index past the end of a short sitting.
        lede = self._lede_panel(
            self._render_pulse(
                [
                    (
                        self._protocol("21/84", "5799", "2026-06-12"),
                        [
                            self._agenda_item(1, 2, ("SPD", "AfD")),
                            self._agenda_item(2, 1, ("CDU/CSU",)),
                        ],
                    )
                ]
            )
        )

        self.assertEqual(
            [(top_id, share) for _href, top_id, share in self._lede_rows(lede)],
            [("TOP 1", "66.7%"), ("TOP 2", "33.3%")],
        )

    def test_lede_falls_back_to_an_empty_state_without_agenda_items(self) -> None:
        # A dossier whose extraction found no TOPs still has to render a hero:
        # the `else` arm replaces both blocks with one explanatory line rather
        # than leaving an empty fraction stack and a headerless ranking.
        markup = self._render_pulse([(self._protocol("21/84", "5799", "2026-06-12"), [])])
        lede = self._lede_panel(markup)

        self.assertIn("noch keine Tagesordnungspunkte extrahiert", lede)
        self.assertEqual(markup.count('class="lede-top"'), 0)
        self.assertNotIn("Redeanteile nach Fraktion", markup)
        # No closing quote: render_party_stack() emits `class="stack empty"` for
        # an empty counter, which the quoted form would silently miss.
        self.assertNotIn('<div class="stack', lede)
        self.assertNotIn('class="party-labels"', lede)
        # The panel's own heading survives the empty state.
        self.assertIn("Zusammenfassung der aktuellsten Sitzung", lede)
        self.assertIn("Redeanteile und Schwerpunkte", lede)

    def test_lede_survives_a_sitting_whose_tops_have_no_speeches(self) -> None:
        # total_speeches == 0 divides the share; percent() and render_party_stack()
        # must both take their zero guard instead of raising ZeroDivisionError.
        lede = self._lede_panel(
            self._render_pulse(
                [(self._protocol("21/84", "5799", "2026-06-12"), [self._agenda_item(1, 0, ())])]
            )
        )

        self.assertIn('<div class="stack empty"></div>', lede)
        self.assertEqual(self._lede_badges(lede), [])
        self.assertEqual(
            [(top_id, share) for _href, top_id, share in self._lede_rows(lede)],
            [("TOP 1", "0.0%")],
        )

    def test_lede_stack_widths_are_shares_of_the_whole_sitting(self) -> None:
        # The bar widths are the sitting-wide denominator made visible. Without
        # this, sitting_party_total can be wrong (or the wrong variable) and
        # every other lede assertion still passes — the counts in the title
        # attributes are independent of it.
        lede = self._lede_panel(
            self._render_pulse(
                [
                    (
                        self._protocol("21/84", "5799", "2026-06-12"),
                        [
                            self._agenda_item(1, 3, ("SPD", "CDU/CSU", "AfD")),
                            self._agenda_item(2, 2, ("SPD", "GRÜNE")),
                            self._agenda_item(3, 1, ("DIE LINKE",)),
                            self._agenda_item(4, 1, ("FDP",)),
                        ],
                    )
                ]
            )
        )

        stack = re.search(r'<div class="stack">(.*?)</div>', lede, re.S)
        self.assertIsNotNone(stack, "lede has no fraction stack")
        widths = re.findall(
            r'width:([\d.]+)%;background:[^"]*" title="([^:]+):', stack.group(1)
        )
        # Seven speakers across the whole sitting: SPD 2/7, everyone else 1/7.
        self.assertEqual(widths[0], ("28.57", "SPD"))
        self.assertTrue(all(width == "14.29" for width, _party in widths[1:]), widths)

    def test_lede_escapes_top_ids_from_the_protocol(self) -> None:
        # top_id is read verbatim out of the XML protocol, exactly like heading,
        # so the row has to escape it too. Every other fixture uses the safe
        # literal "TOP {index}", which cannot catch a dropped esc().
        item = self._agenda_item(1, 1, ("SPD",))
        item["top_id"] = "TOP <1> & 2"
        lede = self._lede_panel(
            self._render_pulse([(self._protocol("21/84", "5799", "2026-06-12"), [item])])
        )

        self.assertIn("TOP &lt;1&gt; &amp; 2", lede)
        self.assertNotIn("<1>", lede)

    def test_lede_escapes_and_shortens_top_headings(self) -> None:
        # Headings come from the XML protocol verbatim, so the row has to escape
        # them and clip them to 72 characters or the hero grid breaks.
        heading = (
            "Beratung des Antrags der Fraktion <B> & Co. zur Änderung des "
            "Gesetzes über die Feststellung des Bundeshaushaltsplans"
        )
        lede = self._lede_panel(
            self._render_pulse(
                [
                    (
                        self._protocol("21/84", "5799", "2026-06-12"),
                        [self._agenda_item(1, 1, ("SPD",), heading=heading)],
                    )
                ]
            )
        )

        self.assertNotIn("<B>", lede)
        self.assertIn("&lt;B&gt; &amp; Co.", lede)
        self.assertIn("…</strong>", lede)
        self.assertNotIn("Bundeshaushaltsplans", lede)

    def test_lede_summarises_only_the_newest_sitting(self) -> None:
        # entries[0] is the current pulse; an older dossier in the same build must
        # not leak its fractions or its dossier anchors into the hero.
        lede = self._lede_panel(
            self._render_pulse(
                [
                    (
                        self._protocol("20/100", "4200", "2023-04-27"),
                        [self._agenda_item(9, 7, ("AfD",))],
                    ),
                    (
                        self._protocol("21/84", "5799", "2026-06-12"),
                        [self._agenda_item(1, 1, ("SPD",))],
                    ),
                ]
            )
        )

        self.assertEqual(
            self._lede_rows(lede),
            [("protocols/plenarprotokoll-21-84.html#top-1", "TOP 1", "100.0%")],
        )
        self.assertEqual(self._lede_badges(lede), ["SPD 1"])
        self.assertNotIn("plenarprotokoll-20-100", lede)
        self.assertNotIn("AfD", lede)

    def test_pulse_hero_never_links_the_votes_panel(self) -> None:
        # The hero used to carry a "#abstimmungen" action link that dangled
        # whenever the votes Baustein was off. Neither Baustein state may bring
        # it back, and the retired .pulse-actions styling must stay retired.
        sitting = [
            (
                self._protocol("21/84", "5799", "2026-06-12"),
                [self._agenda_item(1, 1, ("SPD",))],
            )
        ]

        for label, features in (("votes off", default_selection()), ("votes on", all_selection())):
            with self.subTest(features=label):
                markup = self._render_pulse(sitting, features=features)
                self.assertEqual(markup.count("#abstimmungen"), 0)
                self.assertNotIn("pulse-actions", markup)
                self.assertNotIn("primary-link", markup)

        built = self._render_pulse(sitting, features=all_selection())
        # The panel itself still renders as an anchor target when votes is built.
        self.assertIn('id="abstimmungen"', built)
        self.assertIn('data-feature="votes"', built)
        self.assertNotIn('id="abstimmungen"', self._render_pulse(sitting, features=default_selection()))

    def test_lede_row_anchors_resolve_in_the_generated_dossier(self) -> None:
        # The retired hero link pointed at #abstimmungen, a target that only
        # existed when the votes Baustein was built. Its replacement rows must
        # not repeat that: every lede href has to land on a real anchor in the
        # dossier page this same build wrote.
        protocol = self._protocol("21/84", "5799", "2026-06-12")

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            # Written through write_report_files() so the dossier page really
            # exists on disk, the way it does in a production build.
            entry = build_dip_pulse_site.write_report_files(
                report={
                    "protocol": protocol,
                    "validation_summary": {},
                    "agenda_items": [
                        self._agenda_item(1, 3, ("SPD", "CDU/CSU")),
                        self._agenda_item(2, 2, ("AfD",)),
                        self._agenda_item(3, 1, ("SPD",)),
                    ],
                },
                output_dir=output_dir,
            )

            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol],
                entries=[entry],
                abg_mps=[],
                mp_lookup={},
            )

            rows = self._lede_rows(
                self._lede_panel((output_dir / "puls.html").read_text(encoding="utf-8"))
            )
            self.assertEqual(len(rows), 3)
            for href, top_id, _share in rows:
                with self.subTest(top=top_id):
                    page, _, anchor = href.partition("#")
                    target = output_dir / page
                    self.assertTrue(target.exists(), msg=href)
                    self.assertIn(f'id="{anchor}"', target.read_text(encoding="utf-8"), msg=href)

    def test_render_site_writes_catalog_newest_first(self) -> None:
        # The DIP API orders by aktualisiert, so a corrected old protocol can arrive
        # ahead of the newest sitting; the cached catalog must still be date-ordered.
        protocols = [
            self._protocol("20/100", "4200", "2023-04-27"),
            self._protocol("21/84", "5799", "2026-06-12"),
            self._protocol("21/9", "5010", "2025-07-10"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=protocols,
                entries=[],
                abg_mps=[],
                mp_lookup={},
            )

            catalog = json.loads(
                (output_dir / "data" / "plenarprotokoll-catalog.json").read_text(encoding="utf-8")
            )

        self.assertEqual([item["dokumentnummer"] for item in catalog], ["21/84", "21/9", "20/100"])

    def test_entry_sort_key_tolerates_incomplete_reports(self) -> None:
        # A truncated or hand-edited dossier JSON must sort last, not crash the build.
        complete = {"report": {"protocol": self._protocol("21/84", "5799", "2026-06-12")}}
        self.assertEqual(build_dip_pulse_site.entry_sort_key(complete), ("2026-06-12", "5799"))

        for label, entry in (
            ("no report", {"slug": "21-84"}),
            ("null report", {"report": None}),
            ("no protocol", {"report": {"agenda_items": []}}),
            ("null protocol", {"report": {"protocol": None}}),
            ("no datum", {"report": {"protocol": {"id": "5799"}}}),
        ):
            with self.subTest(entry=label):
                key = build_dip_pulse_site.entry_sort_key(entry)
                self.assertEqual(key[0], "")
                self.assertLess(key, build_dip_pulse_site.entry_sort_key(complete))

    def test_reduced_render_skips_addon_pages_and_dangling_links(self) -> None:
        protocol = self._protocol("21/84", "5799", "2026-06-12")
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol],
                entries=[self._entry(output_dir, protocol)],
                abg_mps=[],
                mp_lookup={},
                features=default_selection(),
            )
            self.assertFalse((output_dir / "bills" / "index.html").exists())
            self.assertFalse((output_dir / "abgeordnete" / "index.html").exists())
            self.assertIn("--no-persist", (output_dir / "database.html").read_text(encoding="utf-8"))
            rendered = "\n".join(path.read_text(encoding="utf-8") for path in output_dir.rglob("*.html"))
            self.assertNotIn('href="bills/index.html"', rendered)
            self.assertNotIn('href="../bills/index.html"', rendered)

    def test_reduced_render_removes_stale_addon_pages(self) -> None:
        protocol = self._protocol("21/84", "5799", "2026-06-12")
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            kwargs = dict(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol],
                entries=[self._entry(output_dir, protocol)],
                abg_mps=[],
                mp_lookup={},
            )
            build_dip_pulse_site.render_site(**kwargs, features=all_selection())
            self.assertTrue((output_dir / "bills" / "index.html").exists())
            self.assertTrue((output_dir / "abgeordnete" / "index.html").exists())
            build_dip_pulse_site.render_site(**kwargs, features=default_selection())
            self.assertFalse((output_dir / "bills" / "index.html").exists())
            self.assertFalse((output_dir / "abgeordnete" / "index.html").exists())
            self.assertFalse((output_dir / "data" / "bills.json").exists())
            self.assertFalse((output_dir / "data" / "abgeordnete.json").exists())

    def test_feature_manifest_and_bootstrap_are_written_everywhere(self) -> None:
        protocol = self._protocol("21/84", "5799", "2026-06-12")
        selection = all_selection()
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = self._output_dir(tmp)
            build_dip_pulse_site.render_site(
                output_dir=output_dir,
                database_path=output_dir / "data" / "bundestag-pulse.sqlite",
                no_persist=True,
                protocols=[protocol],
                entries=[],
                abg_mps=[],
                mp_lookup={},
                features=selection,
            )
            manifest = json.loads((output_dir / "data" / "features.json").read_text(encoding="utf-8"))
            available = {item["id"] for item in manifest["features"] if item["available"]}
            self.assertEqual(available, selection.ids)
            for page in output_dir.rglob("*.html"):
                markup = page.read_text(encoding="utf-8")
                self.assertIn("bundestag-pulse-features", markup, msg=str(page))
                self.assertIn("data-feature-", markup, msg=str(page))
                self.assertIn("settings-toggle", markup, msg=str(page))

    def test_settings_page_distinguishes_core_and_unbuilt_features(self) -> None:
        markup = build_dip_pulse_site.render_settings_page(default_selection())
        self.assertIn("is-unavailable", markup)
        self.assertIn("--enable votes", markup)
        self.assertRegex(markup, r'data-feature-toggle="dip-fetch"[^>]*checked disabled')
        self.assertRegex(markup, r'data-feature-toggle="votes"[^>]*disabled')


class PeriodOrderTests(unittest.TestCase):
    """Wahlperiode buckets are keyed by string, so they need a numeric sort."""

    @staticmethod
    def _protocol(wahlperiode: int | None, number: int) -> dict[str, Any]:
        protocol: dict[str, Any] = {
            "id": f"{number}",
            "dokumentnummer": f"{wahlperiode or 0}/{number}",
            "datum": "2026-06-12",
            "titel": f"Protokoll {number}",
        }
        if wahlperiode is not None:
            protocol["wahlperiode"] = wahlperiode
        return protocol

    def test_period_sort_key_orders_numerically_with_fallback_last(self) -> None:
        periods = ["9", "21", "1", "unbekannt", "10", "2"]
        self.assertEqual(
            sorted(periods, key=build_dip_pulse_site.period_sort_key),
            ["1", "2", "9", "10", "21", "unbekannt"],
        )

    def test_catalog_page_orders_periods_lowest_first(self) -> None:
        # Shuffled input so the assertion cannot pass by accident of arrival order.
        protocols = [
            self._protocol(9, 1),
            self._protocol(21, 2),
            self._protocol(1, 3),
            self._protocol(None, 4),
            self._protocol(10, 5),
            self._protocol(2, 6),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "site"
            markup = build_dip_pulse_site.render_catalog_page(
                protocols,
                [],
                output_dir / "data" / "katalog.json",
                output_dir,
            )

        expected = ["1", "2", "9", "10", "21", "unbekannt"]
        # The clickable badges in div.periods and the Wahlperiode dropdown render
        # from the same list, so both must read lowest period first.
        self.assertEqual(re.findall(r'data-wp-filter="([^"]+)"', markup), expected)
        self.assertEqual(re.findall(r'<option value="([^"]+)">WP ', markup), expected)

    def test_overview_page_orders_periods_lowest_first(self) -> None:
        protocols = [
            self._protocol(9, 1),
            self._protocol(21, 2),
            self._protocol(1, 3),
            self._protocol(10, 4),
        ]

        markup = build_dip_pulse_site.render_overview(protocols, [])

        self.assertEqual(re.findall(r'class="badge">WP ([^ ]+) ', markup), ["1", "9", "10", "21"])


class FeatureArgumentCompatibilityTests(unittest.TestCase):
    def test_legacy_flags_map_with_sparse_namespaces(self) -> None:
        args = SimpleNamespace(no_roster=True, no_abgeordnetenwatch=True, summary_mode="off")
        with tempfile.TemporaryDirectory() as tmp:
            selection = build_dip_pulse_site.resolve_from_args(args, root=Path(tmp))
        self.assertNotIn("mp-roster", selection)
        self.assertNotIn("aw-profiles", selection)
        self.assertNotIn("summaries", selection)

    def test_cli_enable_overrides_file_disable_and_cli_disable_wins(self) -> None:
        args = SimpleNamespace(enable=["votes"], disable=["bills"], features=None, features_file=None)
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "features.json").write_text('{"disable":["votes"]}', encoding="utf-8")
            with mock.patch.dict("os.environ", {"BUNDESTAG_PULSE_FEATURES": "+bills"}):
                selection = build_dip_pulse_site.resolve_from_args(args, root=Path(tmp))
        self.assertIn("votes", selection)
        self.assertNotIn("bills", selection)


if __name__ == "__main__":
    unittest.main()
