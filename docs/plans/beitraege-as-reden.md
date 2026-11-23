# Beiträge stored as Reden

Plan of 2026-11-23 for the owner's decisions 1 to 3 of that day (TODOS.md, "Owner decisions of 2026-11-23"). **Built the same day;** section 6 says what came out and where the build departs from the plan.

Files: [`beitraege-as-reden.tsv`](beitraege-as-reden.tsv) (927 rows) and [`beitraege-as-reden/census.py`](beitraege-as-reden/census.py), which writes it read-only from a site output directory.

## 1. What is wrong

`speeches` holds contributions that `CONTEXT.md` says are not Reden. The detector reads the chair's wording and prefers precision (ADR 0002), so a grant it does not know leaves a Kurzintervention as a Rede. Two kinds were never ruled on: oral Erklärungen, and Reden zu Protokoll printed inside a Tagesordnungspunkt (TOP).

**Evidence.** DIP types each contribution (`aktivitaetsart`) with its person, page and quadrant, and every cached report keeps the list. The census matches each stored Rede, Kurzintervention and Erwiderung to it by person (DIP's person id, else the surname and a given name), page and quadrant, then, for what is left over, within one page. Store: the v0.46.47.0 replay clone `.context/qa-after`, 806 sittings, 61,660 Reden. 59,696 stored Reden match a DIP Rede. 1,055 match nothing (453 without a page, 602 with one). The census first matched the name the store shows and missed persons who have since changed theirs; it was corrected in the /ship review (end of section 6), and the figures here are the corrected ones.

The parser compares these counts per sitting today and only warns (`speech_kinds.dip_mismatches`). It never compares row by row.

## 2. The population

Rows the decisions cover, as `proposed` in the TSV. "Clear" means DIP and the surrounding text agree, and no flag is set. "Read" means the `read` column names a reason to read the row before it is listed.

| Proposed kind | Clear | Read | Where |
|---|---:|---:|---|
| `kurzintervention` | 106 | 18 | all four Wahlperioden |
| `erwiderung` | 122 | 23 | all four Wahlperioden |
| `erklaerung` (§ 30, § 31, § 32) | 99 | 12 | WP 18–20, two in WP 21 |
| `zu_protokoll` | 118 | 4 | 18/39, 18/46, 18/54, 18/60, 18/66 |
| **Together** | **445** | **57** | |

How sure the clear rows are:
- 126 of the 327 clear rows that are not `zu_protokoll` carry no grant wording in the XML before the turn, often because the chair's words are missing there. A random 30 of those were read (seed 3): all 30 were right by their opening words.
- A separate scan of the chair's wording, made before the DIP match, found 184 turns. 180 of them are in the TSV through DIP.
- DIP is wrong or the match slips in some flagged rows. Examples: 18/54 Tauber, 19/26 Rouenhoff and Jensen, all ordinary Reden whose Erwiderung is another row nearby.

**Also covered by the decisions, not in the table:** the seven § 31 Erklärungen that #213 stored as Reden (18/23 ×4, 18/91, 18/115, 18/2). They carry no page, so the census cannot match them and they are not in the TSV; the build lists all seven. Groth in 18/29 (`ID1802902700:2:2:2`, withheld by entry) is a § 31 Erklärung too and is released as `erklaerung`.

**The other way round:** 11 Beiträge DIP types otherwise (the rows whose `stored` is not `rede`). Read them in the build. From the excerpts, 19/59 Kühn, 19/61 Faber and 20/57 Eichwede are Reden wrongly stored as Kurzinterventionen.

## 3. Two more groups, answered by the owner on 2026-11-23: both stay Reden

1. **Wortmeldungen zur Geschäftsordnung: 287 rows** stored as Reden, DIP "Zur Geschäftsordnung BT". They stay Reden. They are speeches for and against a motion, held in turn by the Fraktionen. 21/43 `ID214301700`, a bare motion ruled procedural, stays as it is; motions as short as it (21/14 Latendorf, 126 characters) are read one by one.
2. **Erklärungen zum Vermittlungsverfahren: 62 rows** (§ 90 GO-BT, § 10 GO-VermA). They stay Reden. DIP names them Erklärungen, but the Fraktionen speak in turn on the result, as in a debate. They do not explain one Member's own vote or person, which is what decision 2 rests on.

`berichterstattung` (61 rows) stays a Rede: the Berichterstatter opens the debate. `erklaerung_plenarprotokoll` (2), `wortbeitrag` (1) and the one Rede DIP calls a Zwischenfrage (21/4 Mayer) are read in the build.

## 4. Build

**List** (`scripts/reviewed_units.py`): four kinds of a whole source `<rede>`, `rede_kurzintervention`, `rede_erwiderung`, `rede_erklaerung` and `rede_zu_protokoll`, plus `rede_rede` for the Beiträge that are Reden. Keys as today. `kurzintervention` and `erwiderung` entries also name their parent Rede. A `rede_*` entry on an `M<ordinal>` or `N<ordinal>` unit is how the seven of #213 change kind. Decide in the build whether their `loose_rede` entry becomes `loose_erklaerung` instead.

**Classifier** (`scripts/speech_kinds.py`): a listed kind wins over the wording rules in `classify_reden`. `VERSION` 12 → 13. New Kind `erklaerung` with labels, its `REDE_STATUS` row and its place in `CONTRIBUTION_KINDS`. A listed `erwiderung` must not move the running main Rede. Entries carry the decision; no wording rule is widened, so no unlisted row moves.

**Guard.** A store-gate check and a release check: every stored Rede that DIP types as Kurzintervention, Erwiderung or Erklärung nach § 30, § 31 or § 32 in an exact match is on the reviewed list, or listed as a Rede. Online runs warn by row. Without this, WP 21 adds new wrong rows every Sitzungswoche: 84 of the 228 clear Kurzinterventionen and Erwiderungen are in WP 21.

**Merged text.** A resumed Rede joins its speaker's previous Rede (`merged_rede`). Check each listed turn for text that now joins another row.

**`zu_protokoll`:** page and TOP come from the `<rede>`. The 18/46 and 18/54 TOPs with one delivered Rede among the written ones are read.

**Text to change:** `CONTEXT.md` (Rede, Beitrag, the new Kind, "Zu Protokoll gegebener Beitrag"), ADR 0002 amendment (Erklärungen, the reviewed list, the DIP guard), ADR 0004's § 31 sentence, `docs/data-methods.md`, the data dictionary (`contributions.kind`), DATA.md figures against CPP-BT, pages that label a Kind, and `CHANGELOG.md`. A new Kind value is a codebook change: export format 23 → 24.

**Replay:** one full `--offline --repersist` on a copy, `scripts/compare_store_values.py` with `--cohort all`, old and new figures per table, per person (largest moves) and for the Fakten. Expected: Reden 61,660 → about 61,150 to 61,215 (443 clear rows, up to 57 read ones and the seven of #213 leave; a few of the 11 come back), and that many more Beiträge, plus Groth. Every row moves from `speeches` to `contributions` with its text.

**Order:** list and classifier; read the 57 flagged rows and the 11 others twice, independently; entries; replay; guard; text. One PR.

## 5. Found on the way, not part of this build

**About 435 Reden zu Protokoll that DIP lists and the store lacks,** net, in 40 sittings with a difference, mostly WP 20 and 21 (21/83: DIP 38, stored 1; 20/178: 24 and 0; 21/99: 32 and 1). Three sittings were looked at: the Protokoll XML of 21/83, 20/178 and 21/99 has no annex that holds them, though DIP gives each a printed page. Likely the XML leaves the annex out and the PDF prints it, but no PDF was read. If so, it is a source gap DATA.md must name. See TODOS.md.

## 6. Outcome of the build

Measured on a clone of the 806-sitting store, v0.46.47.0 before, `--offline --repersist`, `compare_store_values.py --cohort all`:
- Reden 61,660 → 61,163 (−497). Beiträge 45,999 → 46,497 (+498): Erklärungen +119, zu Protokoll +120, Kurzinterventionen +113, Erwiderungen +146. Withheld 100 → 99 (Groth). Characters of all Reden 290.07 → 288.97 million. Votes and vote links unchanged.
- 510 entries: 145 Erwiderungen, 120 zu Protokoll, 119 Erklärungen, 118 Kurzinterventionen, 8 Reden. 505 of the rows change; the other 5 say that a turn DIP types otherwise is a Rede. Beside them one Erwiderung follows (20/210 Steiniger) and 29 Beiträge change their parent. No text changes, nothing is newly withheld.
- Sitting/kind differences against DIP 242 → 49. The guard names no row.
- Fakten: 38 of the 1,944 stored values move (`laengste-debatte` 18, `meistdiskutierter-vorgang` 9, `erste-reden` 5, `aktivste-abgeordnete` 4, `laengste-rede` and `laengste-sitzung` 1 each), and 329 (period, metric) pairs count as moved with their percentiles. With 18/29 no longer withholding a Rede, 2014-W15 becomes complete and joins the Vergleichsbasis. 20 rows change whether they are publishable, 34 winners change, publishable weeks 213 → 212 and months 63 → 62. Figures of the branch, the 23 bare motions included.
- CPP-BT: `only_ours` 0, shared ids 81,446 and Redner-ID figures as before (81,423 with the motions below).

**After the build (owner, 2026-11-23):** 23 bare Geschäftsordnung motions are `procedural` (ADR 0004 amendment): Reden 61,163 → 61,140. 21/43, named in section 3, was a narrower precedent than it reads: it interrupts another Rede. O13's nominations are the closer one.

**After the review (2026-11-23):** two Erklärungen given in a Befragung are listed (19/191 `ID1919108700`, 20/105 `ID2010504300`; the second by the owner), so there are 512 entries and 121 Erklärungen; Befragung questions 7,900 → 7,898. Section 1's census never compared Befragung turns. 20/196 `ID2019611800` names no parent: its Redner holds no Rede in the TOP and answers no Kurzintervention. Replayed on a clone: these three rows change and nothing else.

**After the /ship review (2026-11-23):** the census join by the shown name hid turns of persons who changed theirs. Corrected, it adds six rows: two Reden zu Protokoll of 18/46 (`ID1804611700`, `ID1804614900`; the chair says of both TOPs that the Reden go zu Protokoll), listed as such; 21/10 `ID211006000`, a bare motion (two blind readings), `procedural`; and 21/33, 21/95 and 21/97 of the same person, which stay Reden. So there are 514 entries and 24 motions: Reden 61,140 → 61,137, Beiträge 46,497 → 46,499, zu Protokoll 4,162 → 4,164.

**The readings.** Verdicts as given: [A](beitraege-as-reden/reading-A.tsv) and [B](beitraege-as-reden/reading-B.tsv) (doubtful rows), [C](beitraege-as-reden/reading-C.tsv) (clear rows). The rows the /ship review added (18/46 ×2 in C, 21/10 in A and B) stand at the end of the files and are not in the counts that follow. The 327 clear rows and the 116 clear `zu_protokoll` rows were read once, 106 doubtful ones (the 57, the 11, the odd types and the Geschäftsordnung rows under 400 characters) twice, independently. The two readers agreed on 95. The 11 others and the 13 rows the single reader doubted were read again. Where the chair's words name no kind, DIP's type stands.

**Departures from the plan:**
- The entry kinds are the Kind names themselves (`kurzintervention`, not `rede_kurzintervention`), and an entry names a unit as emitted, as `withhold` does, so a split part or an `M<ordinal>` can be listed.
- Entries name no parent. A listed Erwiderung takes its Redner's own last Rede in the TOP (with none, what the Kurzintervention before it answers), and the Kurzintervention before it follows. The replay showed why: 19/61's Hänsel and Möller pointed at Faber, who spoke in between.
- Three turns DIP does not list at their place were found by the text and added (19/32 von der Leyen, 19/161 Gottschalk, 20/80 Hilse).
- Online runs warn once with a pointer to `a1-classification-diagnostics.json`, not by row.
