# N8: review of the 82 restored sittings, on W1's XML

**Status:** done offline, 2026-11-15, before the T4 fetch (decision D3). Code: main fd4760d, speech rule 9, `scripts/reviewed_units.json` as committed there. **Result: N8 does not pass yet.** It found 10 wrong units that withhold entries fix (branch `claude/t4-reviewed-units`). It also found two sitting-level defects, 94 units in all, that need an owner decision before the fetch. It found one store-wide class that the T4 fetch neither causes nor fixes.
**Row record:** [`n8-review.tsv`](n8-review.tsv), one row per item (sitting, unit, set, reader verdict, final verdict, class, action, reason).

## Method

- **Input:** W1's 84 XML files (`~/agent-runs/w1/xml`), without 18/62 and 18/90. All 82 files still match W1's `xml_sha256` in `docs/plans/withholding-preflight/preflight.json`. Each was parsed with the build's `parse_protocol_xml`. Each `<rede>` was rendered as the parser sees it after its tree edits (`adopt_reden_outside_tops`, the reviewed marks, `split_nested_reden`), with markers numbered as `speech_segments` numbers them.
- **The parse reproduces the plan's figures:** 94 withheld Reden (89 `refused_nested_contribution`, 5 `reviewed`), 6,451 Reden, 52 split parts, 55 `merged_zwischenfrage` and 47 `procedural` diagnostics, 14 Ansprachen. The 82 hold no `merged_rede` or `merged_erwiderung`. In the code, both are written straight into the TOP's diagnostics (`diagnostic()` in `parse_protocol_xml`) and survive a withheld Rede, so their absence is real.
- **Readers:** 10 Sonnet batches with one brief (the counting rules of ADR 0002, 0004 and 0005, the swap shape, a verdict scale). Every non-`right` verdict was read again by me in the source. The final verdicts are mine.
- **Scans beyond the plan's sets** (all offline, over the 82 and, for comparison, the 718 stored sittings' XML):
  1. Every stored Rede under 2,500 characters that opens without a salutation (68 in the 82, outside 19/13's Befragung). This finds Beiträge stored as Reden.
  2. Every Rede whose `<rede>` holds a turn of the previous `<rede>`'s owner. This finds the swap shape of 19/25.
  3. Every `<rede>` the chair had just offered as a Zwischenfrage to its owner, in all 802 files.
  4. TOPs whose `<rede>`s mostly open without a salutation, in all 802 files.
  5. Broken Befragung and Fragestunde headings, in all 802 files.
- **Sample seed:** 20261115 (40 Zwischenfragen, 20 Kurzinterventionen, 20 Erwiderungen).
- The scratch tooling is in this session's scratchpad (`extract.py`, `merge.py`, `BRIEF.md`) and is not committed.

## Counts per set

| Set | Items | Right | Wrong | Borderline | Withheld but admissible |
|---|---:|---:|---:|---:|---:|
| a. Withheld Reden | 94 | 49 | 0 | 0 | 45 |
| b. Merges (all 55) | 55 | 48 | 7 (3 units) | 0 | |
| c. Split parts | 52 | 52 | 0 | 0 | |
| c. Procedural turns | 47 | 46 | 1 | 0 | |
| c. Ansprachen | 14 | 14 | 0 | 0 | |
| c. Sample: Zwischenfragen / Kurzinterventionen / Erwiderungen | 40 / 20 / 20 | 80 | 0 | 0 | |
| e. Short Reden without salutation | 68 | 24 | 40 | 4 | |
| f. Found by the scans, outside the sets | 94 | 1 | 93 | 0 | |

**a. Withheld.** Every record names the owner of the `<rede>`'s first marker, and the owner's words are theirs. The 5 N7 entries were each checked against their reason and hold: 18/2, 18/29, 18/83 (two entries) and 19/25. In 45 of the 94, the refused turn is plainly admissible: an ordinary granted Zwischenfrage, or a Kurzintervention the chair announced in words the rules do not read. Withholding them costs coverage (own words), and no figure is wrong. A future rule could release them.

**b. Merges.** The search of the untruncated between-text of every merge for "Kurzintervention", "Erwiderung" and "erwidern" has hits in one exchange only: 18/158 `ID1815830200`, three merges. There Bulmahn tells Lange "Sie können sich zu einer Kurzintervention melden … aber bitte keine Erwiderungen auf eine Antwort". That is a reminder, not a grant. The merges are still wrong, for the swap below.

## Wrong units fixed by withhold entries (10)

All are the N7 kind: a whole Rede counted as a Zwischenfrage, or a Zwischenfrage counted as a Rede with the Redner's Rede nested in it.

- **18/158: Zwischenfragen printed as their own `<rede>` (9 entries).** In 18/158 the XML starts a new `<rede>` for 11 Zwischenfragen. Four of those are already withheld (Krellmann, Liebich, Weiler, Haßelmann). The other 7 are stored as Reden of the asker:
  - `ID1815821700` Hänsel;
  - `ID1815822100` Vogler;
  - `ID1815824500` Beck;
  - `ID1815830200` Lange;
  - `ID1815831300` Kurth;
  - `ID1815832200` Klein-Schmeink;
  - `ID1815832700` Pfeiffer.

  In five of them (Beck, Lange, Kurth, Klein-Schmeink, Pfeiffer), the Redner's answer and the rest of their Rede sit nested inside the asker's `<rede>` and are stored as a Zwischenfrage: the swap shape of 19/25. For Hänsel and Vogler, the Redner's answer and the rest of the Rede are a further `<rede>`, stored as a second Rede of the same Redner: `ID1815821800` Gall and `ID1815822200` Warken. Scan 3 shows this XML shape at this density only in 18/158. In the other 801 files the matches are chair hand-overs ("keine Zwischenfragen mehr … nächster Redner") or Kurzinterventionen the parser already reads.
- **19/18 `ID191802600` (1 entry):** Katharina Dröge's whole Rede is printed inside Klaus Ernst's `<rede>`. Kubicki says "Als Nächstes für Bündnis 90/Die Grünen die Kollegin Katharina Dröge", and the turn opens "Sehr geehrter Herr Präsident!". It is stored as one Zwischenfrage of Ernst's Rede, with three merged turns. `split_nested_reden` did not split it because `NESTED_REDE_FLOOR` has no "Als Nächstes" form. The entry withholds Ernst's Rede too (the unit as emitted). A floor rule for "Als Nächste(s) …" would keep both Reden instead. That rule would apply to all 801 sittings, so it is the owner's call; it is not proposed here.

Effect on T4's expectations: withheld Reden in the 82 go from 94 to 104 (105 with 21/106), and stored Reden from 6,451 to 6,441. The entries' commit gives the exact replay.

## Sitting-level defects: owner decision before the fetch (94 units)

- **18/158: 37 § 31 declarations stored as Reden.** The XML prints the "Erklärungen nach § 31 GO" to the Asylpaket II vote as 37 `<rede>`s in the Sitzungsverlauf, under a last TOP `Geschaeftsordnung` with no heading, not in an annex. The Inhaltsverzeichnis names them "Erklärungen nach § 31 GO". The build excludes § 31 declarations by rule, but these are stored as 37 Reden. Scan 4 finds the shape in no other file. A withhold entry would wrongly count them as withheld Reden in the coverage shares, because they are no Reden at all. **Recommended:** a narrow rule, or a new reviewed kind, that reads them as § 31 declarations, excluded as the annex ones are. Record it in `docs/source-errors.md`.
- **19/13: the Befragung is not recognised.** TOP 1's heading is printed "Befr agung der Bundesregierung", so `speech_kinds.top_format` finds no format. Every Frage and Antwort (57) is stored as a Rede, beside the opening report, and 3 Befragung turns are withheld as refused Zwischenfragen (`ID191304800`, `ID191305000`, `ID191306000`). Scan 5 finds the broken heading in no other file. **Recommended:** a parser rule that reads the heading with the break removed, test-first. That turns 57 Reden into Befragung-Beiträge, releases the 3 withheld turns, and drops 19/13 from the "more than two withheld" list. Withhold entries cannot fix this.

## Store-wide classes: not an N8 entry, filed in TODOS.md

- **Beiträge stored as Reden (33 in the 82):** Kurzinterventionen and Erwiderungen the chair announced in words the detector does not read, Erklärungen nach § 30 and § 32, and one procedural exchange (19/192 Thomae). This is ADR 0002's precision-over-recall detector, which applies to all 801 sittings. In the 718 stored sittings, 0.6 % (WP 18) and 0.9 % (WP 19) of stored Reden are short and open without a salutation, against about 1 % in the 82. Fixing it for the 82 alone would make them unlike the 718, so it needs a store-wide rule and a replay.
- **Reden zu Protokoll printed inside a TOP are stored as Reden:** 18/60 TOPs 17 and 18, as in the kept 18/39, 18/46 and 18/54.
- **A presidium member's own Zwischenfrage read as the chair:** 18/113 `ID1811302500`. Petra Pau, printed with her Vizepräsidentin role, asks Castellucci a question, and it is ruled `procedural`. Her words count nowhere and are filed under no one. This is the class of D4's rule for 18/62 and 18/90, which should cover it.
- **Nominations** (18/1 Kauder, 19/1 Kauder) stay Reden under the open decision O13 (`adr-0004-presidium-kinds.md`), as 20/1 and 21/1 do in the kept store.

## Left for after the fetch

- **The DIP Aktivitäten check of the 52 split parts** (round 2's check, ADR 0002) needs DIP data that T4 fetches. The readers found all 52 right from the source.
- **Set d, attribution:** M4's surname and Fraktion comparison against CPP-BT runs after T4. The CPP-BT file is not on this machine. The presidium Reden of the ten ADR 0004 sittings and the Ansprachen were read here (all right). 18/89's Reden outside a TOP were not singled out.
- **V3:** every fetched XML's sha256 is checked against W1's. A sitting whose file changed is reviewed again on the new file.

## Pass rule

N8 passes once (1) the 10 withhold entries are on main, (2) the owner has decided the 18/158 § 31 declarations and the 19/13 Befragung and the decision is on main, and (3) the store-wide classes are filed. Until (2), T4's fetch would store 37 + 57 wrong Reden in two sittings. Running the fetch first would then cost one more `--offline --repersist` of 801 sittings, which D3 was meant to avoid.
