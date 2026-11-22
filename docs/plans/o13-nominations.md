# O13: a nomination printed as a `<rede>` is procedural

**Status (2026-11-22):** plan, not built. The owner decided O13 on 2026-11-21 (option B): a Fraktion's nomination for the Präsident's election that the protocol prints as the nominating MdB's own `<rede>` is procedural and no Rede (ADR 0004, "Amendment 2026-11-21: a nomination printed as a `<rede>` is procedural"; TODOS.md "ADR 0004 follow-ups", O13). Main is `49f4ec2`, v0.46.40.0: store schema 15, export format 21, speech rule 10.

Every figure below was measured on a `cp -cR` copy of the reference store (806 sittings, replayed on `49f4ec2`) after an `--offline --repersist` with the four entries of section 2 applied as an uncommitted scratch edit, against a second untouched copy (`scripts/compare_store_values.py`). The copies are deleted.

## 1. The four units

| Sitting | `<rede>` | Redner-ID | Speaker | TOP | Own text (chars) |
| --- | --- | --- | --- | --- | ---: |
| 18/1 | `ID1800100100` | 11001074 | Volker Kauder, CDU/CSU | Tagesordnungspunkt 2 | 125 |
| 19/1 | `ID19100900` | 11001074 | Volker Kauder, CDU/CSU | Tagesordnungspunkt 3 | 71 |
| 20/1 | `ID20100700` | 11003599 | Dr. Rolf Mützenich, SPD | Tagesordnungspunkt 3 | 99 |
| 21/1 | `ID21101200` | 11002735 | Friedrich Merz, CDU/CSU | Tagesordnungspunkt 3 | 179 |

The own text of each is the nomination sentence and nothing else (one paragraph, then applause). Only 18/1 prints more inside the element: after Kauder's sentence the Alterspräsident's `<name>` turns (no further nomination, the voting instructions, the ballot, the result, "Nehmen Sie die Wahl an?") and Lammert's nested acceptance "Herr Alterspräsident, lieber Kollege Riesenhuber, ich nehme die Wahl gerne an.", then Riesenhuber's congratulations. That is the H5 pattern (the Hintze case): text that is not the nomination, printed under the nominating MdB. None of it is a Rede or Beitrag today: the chair's turns are Sitzungsleitung, and Lammert's acceptance is dropped as procedural by the 6d rule (`validate_dip_protocol.py:1941`, `ELECTION_QUESTION` + `ELECTION_ACCEPTANCE`). So nothing else moves when the whole `<rede>` becomes procedural, and the listed-procedural guard (`:1986-1992`, any remaining nested turn withholds the `<rede>`) is not triggered: the replay withholds nothing new (section 3). The other three elements hold only the nomination.

## 2. Mechanism

No code changes the rule; the build is list data plus copy.

- **Entry.** `scripts/reviewed_units.json` gets four entries of kind `procedural`, each `{"sitting", "rede_id", "redner_id", "kind": "procedural", "reason"}` with the values of the table above, placed in rede-id order inside each sitting's block (18/1 first in the file; 19/1 before `ID19101000`; 20/1 before `ID20100800`; 21/1 before `ID21101300`). Reason, the same for all four: "a Fraktion's nomination (Wahlvorschlag) for the Präsident's election, printed as the nominating MdB's own <rede>: a motion in the election, not a Rede (ADR 0004 amendment 2026-11-21, O13)".
- **Loader** (`scripts/reviewed_units.py`): `_check` accepts them as they are (`procedural` is in `PRESIDIUM_KINDS`, the ids are whole `<rede>` ids, the Redner-IDs are digits).
- **Parser** (`scripts/validate_dip_protocol.py`): `mark_reviewed_units` (`:960-985`) finds each `<rede>` once in the Sitzungsverlauf, checks the owner's first Redner-ID against the entry and sets `reviewed_kind="procedural"`; `speech_kinds.classify_reden` (`speech_kinds.py:481-484`) labels it `PROCEDURAL`; `reconcile` (`validate_dip_protocol.py:1901-1908`) puts it in `procedural_reden`, writes one `xml_turn_diagnostics` entry per own turn with treatment `procedural` and evidence "procedural (reviewed): <reason>", emits no speech (`:2095`) and records status `procedural`.
- **Persist**: a procedural `<rede>` has no row in `speeches`, `contributions` or `withheld_units`. Its text stays only in the report JSON's `xml_turn_diagnostics` (`data/plenarprotokoll-<sitting>.json`), as for the other reviewed procedural and Sitzungsleitung units.
- **No version bump.** The speech rule `VERSION` stays 10: `reviewed_digest` (`reviewed_units.sitting_digest`, stored per protocol in `speech_rule_inputs`) changes for exactly 18/1, 19/1, 20/1 and 21/1, so `stale_causes` (`build_dip_pulse_site.py:2125-2145`) marks those four reports `reviewed` and the persist guard (`persist_dip_pulse_store.py:120-132`) refuses facts, export and rendering until they are re-read. Store schema 15 and export format 21 stay: no column or table changes.
- **Dossier.** Each of the four TOPs held exactly one Rede, the nomination, and holds none afterwards (18/1 TOP 2, and TOP 3 of 19/1, 20/1, 21/1). With a reviewed procedural diagnostic and no card, `render_speech_details` shows `NO_REDEN_PROCEDURAL` (`render_dip_pulse_html.py:1946-1947`): "Keine Reden: Was das Protokoll hier als Rede druckt, sind Verfahrensschritte (Annahme einer Wahl, Eid, Sitzungsleitung), die nicht als Rede zählen." The parenthesis does not name a nomination; the build adds "Wahlvorschlag" there (section 4). The sitting ranking keeps its Reden from the other TOPs, so the "kein Ranking möglich" line (`:3201-3202`) does not appear for these sittings.

## 3. What moves (measured)

`compare_store_values.py`, shared cohort (806 protocols in both), and the generated pages and exports of both copies:

| | Before | After | |
| --- | ---: | ---: | --- |
| Reden (`speeches`) | 61,559 | 61,555 | −4 |
| CDU/CSU Reden (party, whole store) | 17,043 | 17,040 | −3 |
| SPD Reden (party, whole store) | 13,149 | 13,148 | −1 |
| Redeanteil CDU/CSU / SPD (Reden) | 16,858 / 13,021 | 16,855 / 13,020 | shares unchanged at one decimal (27.4 %, 21.2 %) |
| Sprechrolle `keine` | 58,262 | 58,258 | −4 |
| Speech characters | 289,425,346 | 289,424,872 | −474 (18/1 −125, 19/1 −71, 20/1 −99, 21/1 −179) |
| Own words of Reden by year (DATA.md coverage) | 2013 136,753; 2017 1,849,331; 2021 2,447,918; 2025 2,874,596 | 136,738; 1,849,323; 2,447,906; 2,874,572 | −59 words; withheld shares unchanged at two decimals |
| Reden by Wahlperiode (DATA.md) | 18: 12,950; 19: 19,982; 20: 19,165; 21: 9,462 | 12,949; 19,981; 19,164; 9,461 | −1 each |
| Reden per sitting (Dossier, API catalog) | 18/1 5, 19/1 7, 20/1 8, 21/1 12 | 4, 6, 7, 11 | −1 each, same on the Dossier, `api-sitzungen.html` and `sources.html` |
| Person pages (Reden) | Kauder 57, Mützenich 61, Merz 63 | 55, 60, 62 | the nomination leaves each list of Reden; on `abgeordnete/index.html` Merz (62) now sorts after Falko Mohrs (62) |
| Beiträge, withheld Reden, votes, links, persons, Personenseiten | 45,928; 102; 736; 676; 6,428; 1,675 | unchanged | |
| `fact_sources` | 3,014 | 3,011 | −3, explained below |

**Beyond the expected, and why.**

- **One debut moves.** Volker Kauder's first Rede in the store was the 18/1 nomination (2013-10-22, the store's first sitting); it becomes his 18/2 Rede `ID1800200500` (2013-11-18). The `erste-reden` fact for 2013-W43 drops from 5 to 4 (it cited `ID1800100100`); neither week is eligible or publishable (2013-W43 is the store's first week, 2013-W47 has no value because 18/2 holds a withheld Rede). The 2014-W39 `erste-reden` percentile moves 0.125 → 0.25 because its baseline loses 2013-W43's 5. TODOS.md's "no debut moves" is wrong for Kauder; Mützenich's and Merz's first stored Reden are earlier ones.
- **`meistdiskutierter-vorgang` loses two months.** In 2017-10 (19/1 the only sitting) and 2025-03 (21/1, the only sitting that month), the month's most discussed Vorgang was the Präsident's election with 1 Rede, the nomination. Both become unavailable ("diesen Monat nicht messbar" instead of "nicht ungewöhnlich genug"; neither was publishable). 2021-10 keeps its value 1 from another TOP of 20/1. With two values fewer in the comparison sets, 29 later months' percentiles move (largest: 2019-02 0.833 → 0.722, 2019-07 0.111 → 0, 2017-11 0.071 → 0) and 6 more change only their comparison window; `compare_store_values` counts 33 of 1,944 fact values moved (these 31 and the two `erste-reden` weeks). No published flag, rank or winner changes. 2019-02's comparison window becomes "18 Monate (2014-02 bis 2019-01)" instead of "6 Monate (2017-10 bis 2019-01)": without 2017-10 it reaches back into WP 18. 46 files under `fakt/` change (month pages, their SVGs and the index). The three `fact_sources` rows gone are these two months' agenda-item sources and Kauder's 2013-W43 debut source.
- **CPP-BT** (`compare_cpp_bt.py`, CPP-BT 2026-09-19): `ids_both` 81,448 → 81,444, `ids_only_theirs` 2,311 → 2,315 (all four `in_top_other`, `read_by_hand` until the TSV rows are added), `surname_compared` 81,442 → 81,438, Fraktion compared 71,350 → 71,346. The 18/1 ratio outlier `ID1800100100` (ratio 0.019: CPP-BT counts the chair's 772 words) leaves the outliers, 1,862 → 1,861.
- **Dossier.** The four TOPs show the `NO_REDEN_PROCEDURAL` line; the attention row of 18/1 TOP 2 reads "0 Reden · 0,0 % der Sitzung", and the other TOPs' shares rise (19/1 TOP 2 85.7 % → 100 %).

## 4. Places that state the old figures or the old rule (same PR)

Generated text needs nothing: DATA.md's row counts, coverage tables and per-Wahlperiode figures come from the store at export. Static text:

| File:line | Says | Change |
| --- | --- | --- |
| `docs/adr/0004-presidium-counts-for-the-fraktion.md:56` | "all four are stored as Reden until the build. Measured …: Reden 61,559 → 61,555, CDU/CSU −3, SPD −1" | built in vX; add Kauder's debut (18/1 → 18/2) and the two `meistdiskutierter-vorgang` months |
| `docs/adr/0004-presidium-counts-for-the-fraktion.md:29` | `procedural` "covers the acceptance of an election and the answer to an oath" | add the nomination (amendment 2026-11-21) |
| `CONTEXT.md:104` (Rede) | "Nor are an Ansprache, the acceptance of an election, the answer to an oath or Sitzungsleitung" | add "a Fraktion's nomination in an election" |
| `docs/data-methods.md:21` | "Ebenso die Annahme einer Wahl und die Antwort auf einen Eid …" | add "der Wahlvorschlag einer Fraktion, den das Protokoll als eigene `<rede>` des vorschlagenden Abgeordneten druckt" |
| `docs/data-methods.md:55` | status list "(wie der Antrag in 21/43, eine Wahlannahme, ein Eid oder …)" | add "ein Wahlvorschlag" |
| `docs/data-methods.md:160` | "Verfahrensschritte …: Eidesantworten, Wahlannahmen, Sitzungsleitung (ADR 0004) \| 121" | add "Wahlvorschläge"; 121 → 125 |
| `docs/data-methods.md:155` | "81.354 Rede-IDs auf beiden Seiten … 2.311 führt CPP-BT" | 2,311 → 2,315; restate 81.354 from the run (below) |
| `docs/data-methods.md:153`, `:169` | "81.280 von 81.338", "320 von 81.348", "1 von 71.257" | restate from the run (below) |
| `scripts/render_dip_pulse_html.py:1946-1947`, `:3201-3202` | "(Annahme einer Wahl, Eid, Sitzungsleitung)" | "(Wahlvorschlag, Annahme einer Wahl, Eid, Sitzungsleitung)" |
| `tests/test_presidium_kinds.py:632`, `:635` | the two strings above | follow the copy |
| `scripts/build_dip_pulse_site.py:11151`, `:12947` | "ebenso wenig die Annahme einer Wahl und die Antwort auf einen Eid" | "ebenso wenig der Wahlvorschlag einer Fraktion, die Annahme einer Wahl und die Antwort auf einen Eid" |
| `scripts/cpp_bt_known_differences.tsv` | 18/1 block `:98-103`, 19/1 `:141-155`, 20/1 `:40-45`, 21/1 `:69-73` | four `only_theirs` rows (section 6, step 4) |
| `TODOS.md:897` (O13) | "B now moves four Reden … no debut moves. Build: …" | close as built, with the measured figures and the debut correction |

**A stale paragraph found on the way.** `docs/data-methods.md:153-169` (the CPP-BT comparison) gives 81.354 shared Rede-IDs, 81.338 with a Redner-ID, 81.348 surnames compared and 71.257 Fraktionen compared; today's report on the same store gives `ids_both` 81,448, `surname_compared` 81,442 and Fraktion compared 71,350, while 2,311 only-theirs matches. The paragraph's shared counts predate a later store state (probably 18/62 and 18/90, restored on 2026-11-20 with 94 Rede-IDs; its "789 Sitzungen" and "CPP-BT führt 18/62 und 18/90 …, die hier ausgeschlossen sind" say the same). The build touches these lines anyway, so it restates the whole paragraph from its own `compare_cpp_bt.py` run rather than subtracting 4 from stale numbers.

Not changed: `TODOS.md:57` and `:1691` are dated records ("13 of 61,559 stored Reden" was true on 2026-11-21; none of the four prints "(Beifall" inline, so the 13 stand); `scripts/publish_dip_pulse_data.py:524` uses `18/1:ID1800100100` only as an example id in `--confirm-withheld` help (cosmetic; replace it with a real withheld id or leave, TODOS). The data dictionary names no procedural kind. No fixture or test pins the four units or a store-wide Reden count (`tests/fixtures/shared-redner-ids/19-1-schaeuble.xml` holds only `ID19101300`).

## 5. Other nominations and election motions in the 806 sittings

Searched: every stored Rede of at most 1,500 characters whose text proposes someone ("schlägt/schlage … vor", "Wahlvorschlag", "vorschlagen", "nominier", "benenn"); every stored Rede of at most 600 characters under a TOP whose heading names a Wahl; every `<rede>` in the 806 cached XML files whose own text (up to the first chair or other marker) is at most 700 characters and proposes someone; `withheld_units` and `contributions` for the same words. Beyond the four, no other nomination is printed as a `<rede>`. The Vizepräsidenten, the Wehrbeauftragte and the Bundeskanzler are elected on a Wahlvorschlag printed as a Drucksache, not spoken; the Bundeskanzler's is the Bundespräsident's.

Two Reden in a Vizepräsident election come close and are listed for the owner, not built here:

| Sitting | `<rede>` | Speaker | Chars | TOP | What it is |
| --- | --- | --- | ---: | --- | --- |
| 19/124 | `ID1912404500` | Fabian Jacobi, AfD | 4,515 | Zusatzpunkt 4, Wahlvorschlag der Fraktion der AfD, Wahl eines Stellvertreters (2. Wahlgang) | Opens "Wird dieser Wahlvorschlag zugelassen, brauche ich das Wort nicht", then a full Rede zur Geschäftsordnung arguing that every MdB may nominate |
| 20/44 | `ID204406300` | Stephan Brandner, AfD | 603 | Tagesordnungspunkt 11, Wahlvorschlag der Fraktion der AfD, Wahl eines Stellvertreters (2. Wahlgang) | Reports the rejected second nomination and moves, under the Geschäftsordnung, that further proposals be allowed |

Neither nominates anyone in the election: both are speeches on the procedure, which the dataset counts as Reden like every other Rede zur Geschäftsordnung (the one procedural GO unit, 21/43 `ID214301700`, is a summons request inside another speaker's `<rede>`, not a GO speech of its own).

## 6. Build, test-first

1. **Red.** In `tests/test_presidium_kinds.py`, a fixture sitting shaped like 19/1 TOP 3 (an MdB's `<rede>` "Die CDU/CSU-Bundestagsfraktion schlägt Herrn Dr. Wolfgang Schäuble vor.", then the Alterspräsident's `<rede>`) with a `procedural` entry installed by `reviewed_units.use`: no speech, one `procedural` diagnostic with the reason, status `procedural`. And one shaped like 18/1 TOP 2: the nomination, the chair's `<name>` turns, a nested "Nehmen Sie die Wahl an?" / "ich nehme die Wahl gerne an." under another MdB's marker; no speech, nothing withheld, no Beitrag. These pass on today's code once the entry is installed (the mechanism exists); the red step is the shipped-list test below and the copy tests.
2. **Shipped list.** A test that reads `scripts/reviewed_units.json` and asserts the four `(sitting, rede_id, redner_id)` entries are `procedural` (fails before the entries are added). Add the four entries.
3. **Copy.** Update the two `NO_REDEN_PROCEDURAL` / ranking strings in `render_dip_pulse_html.py` and their assertions at `tests/test_presidium_kinds.py:632` and `:635` (test first), the two site copies in `build_dip_pulse_site.py`, and the docs of section 4.
4. **`scripts/cpp_bt_known_differences.tsv`.** Four `only_theirs` rows, after the 18/1 block (`:98-103`) and the 19/1, 20/1 and 21/1 groups: `only_theirs<TAB>ID…<TAB><TAB><TAB>ADR 0004, reviewed procedural unit (nomination for the Präsident's election, O13): CPP-BT lists it as a Rede, we do not (scripts/reviewed_units.json)`.
5. **Replay and compare** (README "Validate a data correction"): `cp -cR` baseline and after copies of `.context/dip-pulse-site` with their private siblings, `--offline --repersist --output-dir <after>`, then `scripts/compare_store_values.py <baseline> <after>` and `--cohort all`. The result must match section 3 exactly; any other moved value stops the build. Then `scripts/compare_cpp_bt.py` on both (CPP-BT 2026-09-19 zip, `--xml-dir <store>/data/xml`): only-theirs Rede-IDs +4, every new one marked `known`.
6. **Suite** on a current 3.13 patch (`uv run --python 3.13.12 python -m unittest discover -s tests`), then the review checklist (the diff is small: classes 11 and 13).

**Store gate afterwards.** After the merge the reference store holds reports and `speech_rule_inputs.reviewed_digest` for 18/1, 19/1, 20/1 and 21/1 under the old list; facts, export and rendering refuse until one `--offline --repersist` of `.context/dip-pulse-site` (the four sittings re-read, the rest unchanged). Then `scripts/validate_store_gate.py` on it. No re-fetch.

## 7. Owner questions

1. **The two Geschäftsordnung speeches in a Vizepräsident election** (19/124 `ID1912404500` Jacobi, 4,515 characters; 20/44 `ID204406300` Brandner, 603 characters, section 5): do they stay Reden? **Recommendation: yes, keep them as Reden, no entry.** Neither is a nomination: each argues a point of order before the House, which is a contribution to a debate on the procedure, like every other Rede zur Geschäftsordnung the dataset counts. O13's reason (a Wahlvorschlag is a motion, not a contribution) does not reach them.

No other question: the debut and the two Fakt months follow from the decision, and the wording changes in section 4 only bring the copy in line with it.
