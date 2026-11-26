# E17: the ten WP 18 Reden zu Protokoll printed without a `<rede>` of their own

From TODOS.md, "WP 18: ten Reden zu Protokoll printed without a `<rede>` of their own", and `docs/source-errors.md` E17. P1 (owner, 2026-11-24): fixed before the first release, because two rows credit text to the wrong person. Base: main 88d83d3 (v0.46.53.0), store clone `.context/e17-after` of `.context/roster-after-52` (806 sittings).

## What is wrong

A written Rede is a `<rede>` in an annex block titled "Zu Protokoll gegebene Rede(n)", opened by the writer's speaker marker. `written_contributions` stores each such `<rede>` as one `zu_protokoll` Beitrag of the owner of its first marker. Ten WP 18 Reden do not stand that way:

- **A second writer's marker inside the previous writer's `<rede>`.** `speech_segments` reads the second writer's words as a nested segment, which `written_contributions` drops. Stored nowhere.
- **A second writer's text inside the previous `<rede>` as plain text,** opened by the printed label but no marker. Stored as the first writer's words.
- **No `<rede>` around the text.** Nothing reads text that stands in the block outside a `<rede>`. Stored nowhere.
- **A `<rede>` without a marker** (18/63 Freudenstein, 18/76 Böhmer): stored as a row with no speaker and no text (the label paragraph is read as unattributed).

## The ten cases and the evidence

Every case names the writer in the XML where the text begins. Every one is a DIP Aktivität "Rede (zu Protokoll gegeben)" of that person in that sitting, at the page given; the page is the Plenarprotokoll PDF's, `https://dserver.bundestag.de/btp/18/<file>.pdf#P.<page>` (DIP `fundstelle`). The PDFs were not opened: the XML prints each writer's label at the place, and DIP's page agrees with the XML's page anchor.

| Sitting | Writer (Redner-ID) | Where the XML prints it | What names the writer there | DIP Aktivität, page | Today |
|---|---|---|---|---|---|
| 18/17 | Charles M. Huber (11004308) | Anlage 10, inside `ID1801712700` (Fabritius), marker | the marker; the Inhaltsverzeichnis lists `ID1801712800` for him | 357647, 1365C | nowhere |
| 18/23 | Ralph Lenkert (11004091) | Anlage 3, inside `ID1802308800` (Thews), `<p klasse="J_Abstand">` | "Ralph Lenkert (DIE LINKE): Elf Duale Systeme …"; Inhaltsverzeichnis `ID1802308900` | 360758, 1889B | under Thews |
| 18/34 | Christian Petry (11004605) | Anlage 2, no `<rede>` | heading "des Abgeordneten Christian Petry (SPD) zur Beratung … (33. Sitzung, Tagesordnungspunkt 17)" | 364615, 2931D | nowhere |
| 18/46 | Armin Schuster (Weil am Rhein) (11004149) | Anlage 16, marker directly in the block, before `ID1804618000` | the marker | 372039, 4325C | nowhere |
| 18/47 | Hartmut Koschyk (11001186) | Anlage 4, no `<rede>` | heading "des Abgeordneten Hartmut Koschyk (CDU/ CSU) zur Beratung … (Tagesordnungspunkt 28)" | 371849, 4412B | nowhere |
| 18/63 | Michaela Engelmeier (11004266) | Anlage 9, inside `ID1806311300` (Steiniger), `<p klasse="N_Anlage">` | "Michaela Engelmeier (SPD) : Wir beraten heute also …" | 381193, 5949B | under Steiniger |
| 18/63 | Dr. Astrid Freudenstein (11004277) | Anlage 6, `ID1806309700`, no marker | "Astrid Freudenstein (CDU/CSU) : Wir haben uns …"; the Inhaltsverzeichnis lists `ID1806309700` under her `<redner>` | 381071, 5932C | no speaker, no text |
| 18/66 | Gabriele Schmidt (Ühlingen) (11004402) | Anlage 5, inside `ID1806614200` (Pätzold), marker | the marker | 382230, 6317C | nowhere |
| 18/76 | Dr. Maria Böhmer (11002630) | Anlage 11, `ID1807611000`, no marker | "Dr. Maria Böhmer (Staatsministerin AA) : Lassen Sie mich …"; the Inhaltsverzeichnis lists `ID1807611000` under her `<redner>` | 386806, 7366D | no speaker, no text |
| 18/112 | Gabriele Schmidt (Ühlingen) (11004402) | Anlage 7, inside `ID1811211800` (Strebl), marker | the marker | 403352, 10849A | nowhere |
| 18/115 | Özcan Mutlu (11004360) | Anlage 17, inside `ID1811515000` (Hein), marker | the marker | 405115, 11240B | nowhere |
| 18/155 | Metin Hakverdi (11004289) | Anlage 2, no `<rede>` | "Metin Hakverdi (SPD): Im Rahmen des Gesetzgebungsverfahrens …" | 425443, 15339C | nowhere |

That is the TODO's ten (eight stored nowhere, Lenkert and Engelmeier under another writer) and the two empty rows. Each text runs to the end of the `<rede>` or block it stands in, or in 18/46 to Özdemir's `<rede>`. No case needs a product decision: every text has one writer, named in the XML and by DIP.

**Census** (`/private/tmp/claude-501/todo-stores/e17/census.py`, all 806 cached XML files, zu-Protokoll blocks only): a `<rede>` with markers of two Redner-IDs: 4 (the four above); a `<rede>` without a marker: 2; a marker directly in the block: 1; a paragraph inside a `<rede>` after its first that opens with "Name (…):": 9, of which Lenkert and Engelmeier are labels and seven are sentences that end in a colon; text paragraphs directly in a block: 74 in 12 sittings, Petry, Koschyk, Hakverdi and Schuster's own paragraphs, and 31 headings and list items. Those list items are another defect (below). The three other `<rede>`s without a `<redner>` (18/46 `ID1804617400`, 18/117 `ID1811703000`, 18/118 `ID1811802900`) are Erklärungen nach § 31 GO, kept out by `ANNEX_EXCLUSIONS`, and 18/104 `ID1810402200` is Kühn's spoken Rede under `<name>` (E3, ADR 0004).

Not part of this fix: 18/136, 18/206, 18/209, 18/243 and 19/104 print the bullet points of a written Rede as paragraphs directly in the block, between two `<rede>`s, so those words are stored nowhere (6, 3, 8, 4 and 3 paragraphs). The writer is the one of the `<rede>` before, but where in it the list belongs is not marked. TODOS.md gets an entry.

## Build

**Reviewed list.** A new kind `annex_rede` in `scripts/reviewed_units.json`, in the pattern of `name_*` and `loose_*`. Keys: the common five plus `name` and `label`.
- `rede_id`: where the text stands: the annex `<rede>` that holds it, or `A<n>` for annex block `n` when it stands in no `<rede>`, counted as `annex_rede_key` counts blocks (every `anlagen-text` of the sitting, 1-based).
- `label`: the words that name the writer where the text begins, as printed: a marker's label, the start of the paragraph up to its colon, or for Petry and Koschyk the words of the block heading. Each must occur once in its place.
- `name`: the tag the unit's marker carries, as for `name_*` entries (`name_tag_marker`). For an existing marker it must equal the marker's label. For Böhmer it is "Dr. Maria Böhmer, Staatsministerin im Auswärtigen Amt", the role as 121 of her markers in the WP 18 Sitzungsverläufe print it, so her Beitrag counts for the Bundesregierung like her other turns. The printed "(Staatsministerin AA)" maps to no Sprechrolle.
- `redner_id`: the writer's Redner-ID. An existing marker must carry it.

**Parser.** `validate_dip_protocol.mark_annex_texts`, called once before `written_contributions`, after every TOP is parsed, on annex blocks only (no TOP, no `<name>` ordinal and no loose-marker ordinal is touched):
1. It finds the place of the label. A label paragraph loses the label, and a marker built from `name` goes before it. After a heading, the marker goes before the first paragraph that is not a heading. An existing marker is kept.
2. In a `<rede>` of another writer, everything from the marker to the end of the `<rede>` becomes `<rede id="<id>:<marker ordinal>">`, right after it: the split-part form of `split_nested_reden`, put in `split_parts` so the reconciliation demands a status. In a `<rede>` without a marker whose text the label opens, the `<rede>` keeps its id and gets the marker. In a block, the marker and its paragraphs up to the next `<rede>`, annex heading or block end become `<rede id="annex:<n>:<m>">`, the form `written_contributions` already gives an annex Rede without id.
3. Guard: afterwards, a zu-Protokoll block where a `<rede>` holds markers of two Redner-IDs or none, or a marker stands outside any `<rede>`, refuses the sitting (`UnlistedAnnexTextError`, a `ValueError`, handled like `UnlistedLooseMarkerError` in the online parse and the re-parse). Today those words are dropped or credited to nobody without a sign. Plain text with no marker (the other four) has no structural sign, and the census above is its record.

An entry whose label is not found once, whose marker carries another Redner-ID, whose `name` differs from an existing marker's label, or that names a `<rede>` or block that is no zu-Protokoll annex stops the run (`ReviewedUnitsError`). `check_withhold_one.py` applies the new entries in both parses, as it does the `name_*` and `loose_*` ones.

The new units go through `written_contributions` unchanged: kind `zu_protokoll`, the TOP from the block's `(Tagesordnungspunkt …)` heading, the page from the block's page anchors. Petry's heading names the 33rd sitting's TOP 17 and Hakverdi's "11 a und 11 b", so both stay without a TOP, as any such written Rede does today. Ids:

| Unit | Id |
|---|---|
| Huber, Lenkert, Engelmeier, Schmidt (18/66, 18/112), Mutlu | `<host>:2` |
| Freudenstein, Böhmer | their `<rede>` id, as today |
| Petry, Schuster, Koschyk, Hakverdi | `annex:2:1`, `annex:16:1`, `annex:5:1`, `annex:2:1` |

No speech-rule bump: the parse changes only where an entry applies, and the reviewed digests of the ten sittings force their replay. No new export format or schema: no column changes.

## Figures expected to move

- `zu_protokoll` Beiträge 4,164 → 4,174 (+10, all WP 18). Freudenstein's and Böhmer's rows get a speaker and text. Thews's and Steiniger's rows lose Lenkert's and Engelmeier's words.
- Reden per WP: none (a Rede zu Protokoll is a Beitrag, ADR 0002). Characters of Reden: none.
- Rows without a person: the two empty `zu_protokoll` rows go.
- Personenseiten of the eleven writers each gain one Beitrag.

The replay gives the real values. The report lists each with old and new value.

## Tests (first, red before the build)

- Synthetic XML for each shape: a marker inside another `<rede>`, a label paragraph inside another `<rede>`, a `<rede>` without a marker, a marker directly in a block, a heading-named text without a `<rede>`, a label paragraph without a `<rede>`. Each yields the unit with its id, writer, text and page, and the host keeps only its own words.
- The guard: each structural shape without an entry refuses with `UnlistedAnnexTextError`.
- List errors: a label not found, found twice, another Redner-ID on the marker, a `name` that differs from the marker's label, a `rede_id` or block that is no zu-Protokoll annex, malformed keys.
- `reviewed_units._check` accepts the kind and refuses a bad `rede_id`.
- Real XML (skipped without the reference store): the ten sittings under the shipped list give the twelve units with writer, id, page and text start, and the hosts no longer hold the other writer's text.
- Every `annex_rede` entry's `name` reads as a person with a Fraktion or a side, as the `name_*` test does.

## Docs

`docs/source-errors.md` E17 (effect, "Our side") and E3's scale (six `<rede>`s without a `<redner>` in the 806); `docs/data-methods.md`: the paragraph on the ten, the reconciliation paragraph's "Abschnitte anderer Redner innerhalb einer zu Protokoll gegebenen Rede", the `ID…:N` and `annex:<n>:<m>` counts and the DIP comparison (4,599 / 4,164); `reviewed_units.py`'s docstring; TODOS.md: entry closed, new entry for the list items.
