# C1: Fraktion seat counts in the store

Roadmap item C1 (TODOS.md "Fraktion seat counts in the store"). Every per-seat or share-of-Zusammenschluss figure in track C (Zwischenrufe, Präsenz, Redeanteil, the term series) needs one denominator. The store has none.

- **Planned:** 2026-11-01 on `claude/c1-implementation-plan-970e85`, cut from main v0.27.0.0 (4705fb3).
- **Revised the same day:** the source changed to the Bundestag's MdB-Stammdaten (D1). The evidence for that change is in "History" at the end.
- **Effort:** M, not the TODO's S. The change adds a new acquisition, two tables and a cross-check gate.

## Source: the MdB-Stammdaten (D1, owner decision 2026-11-01)

The Bundestag publishes "Stammdaten aller Abgeordneten seit 1949 im XML-Format" on `https://www.bundestag.de/services/opendata`:
- the download is `https://www.bundestag.de/resource/blob/472878/MdB-Stammdaten.zip`
- the page states "Stand: 29.04.2026"
- no size is given
- no schema description is given (the page's DTD links cover only the Plenarprotokolle)
- there are no licence terms beyond "© Deutscher Bundestag" and the note that the data "können zur maschinellen Weiterverarbeitung genutzt werden"

The file holds each MdB's Mandat for each Wahlperiode (`MDBWP_VON/BIS`) and their Fraktion or Gruppe memberships (`INSTITUTION` with `INSART_LANG = "Fraktion/Gruppe"`, `MDBINS_VON/BIS`). The structure was verified in step 1b (S1).

**Why this source over the two others measured:**
- **The roster count (the TODO's proposal).**
  - It includes leavers: 740 WP 21 rows against 630 seats.
  - 151 rows have no party.
  - It keeps only one Fraktion per person, the newest.
  - It is missing the 48 government MdBs.
- **The roll-call totals.**
  - They date a change only at the next roll-call.
  - They have nothing before each WP's first roll-call.
  - They misattribute members on bundestag.de's own pages (`docs/source-errors.md` E4: the AfD shown up to 3 seats short for the last two months of WP 19).

  They stay in the plan, but as an independent cross-check, not the source.

**The Stammdaten's own limit (D6): it lags.** Its Stand is 29.04.2026, and the roll-calls show later changes: CDU/CSU 206 on 2026-05-22 and 208 on 2026-06-11. Changes after the Stand are missing until the Bundestag republishes the file.

## Design

### Tables (schema 8 → 9)

The source fields map as follows (S1): `mdb_id` ← `ID`, `name` ← the `NAME` valid on the interval, `party_id` ← `INS_LANG` via the closed map in S2.

```sql
-- One row per MdB, Wahlperiode and unbroken stretch of one Zugehörigkeit (or none).
CREATE TABLE IF NOT EXISTS mdb_zugehoerigkeiten (
  mdb_id TEXT NOT NULL,                 -- Stammdaten person id (the same number as the protocol XML Redner-ID)
  name TEXT NOT NULL,                   -- display name, for reading only
  wahlperiode INTEGER NOT NULL,
  party_id TEXT NOT NULL REFERENCES parties(id), -- the `fraktionslos` row on days without a Zugehörigkeit (D8)
  valid_from TEXT NOT NULL,             -- first day (inclusive)
  valid_until TEXT,                     -- first day no longer covered (exclusive); NULL = open at the Stand date
  PRIMARY KEY (mdb_id, wahlperiode, valid_from)
);

-- Derived from mdb_zugehoerigkeiten in the store: one row per Zusammenschluss and unbroken seat count.
CREATE TABLE IF NOT EXISTS party_seats (
  party_id TEXT NOT NULL REFERENCES parties(id), -- the `fraktionslos` row counts the members without one (D8)
  wahlperiode INTEGER NOT NULL,
  valid_from TEXT NOT NULL,
  valid_until TEXT,
  seats INTEGER NOT NULL CHECK (seats > 0),
  PRIMARY KEY (party_id, wahlperiode, valid_from)
);
```

- **Traceability.** A seat count resolves to the named members behind it: the `mdb_zugehoerigkeiten` rows that cover that day. That covers principle 1 without a vote id. A recipe can recount any figure from the export.
- **Personal fields:** the Stammdaten id and the display name only. No biography: birth dates, professions and the rest stay out.
- **fraktionslos** is the existing `fraktionslos` parties row, not NULL (D8, decided in step 3). CONTEXT.md says it is the absence of a Zugehörigkeit, not an organisation; the dictionary says so for both `party_id` columns.
- **Lookup rule (C2–C5 depend on it).** The seats of group G at date d are the row with `valid_from <= d` and (`valid_until IS NULL` or `d < valid_until`) in d's WP. No row means no seat count, shown as such. Dates after the Stand follow D6.
- **Not in C1:** linking `mdb_id` to `mps.xml_redner_id`, which would put Mandat dates on the MP pages.

### Interval rules (pure functions in `scripts/derive.py`, each pinned by a test)

0. **Merge function duplicates.** Rows with the same `(INS_LANG, MDBINS_VON, MDBINS_BIS)` are one membership (S2).
1. **End dates.** When the next membership starts on a membership's `MDBINS_BIS` (a handover day), that day belongs to the next one. Otherwise `valid_until` = `MDBINS_BIS` + 1 day (S2).
   **Mandat ends.** `MDBWP_BIS` is the Mandat's last day, so a Mandat ends on `MDBWP_BIS` + 1. When another Mandat of the same WP and Zusammenschluss starts on a leaver's `MDBWP_BIS`, that day belongs to the new Mandat, one new Mandat per leaver (S5).
2. **Clip to the Mandat.** A membership is clipped to its Mandat for the Wahlperiode. A membership that starts before the Mandat, for example from the Fraktion's founding, starts with the Mandat.
3. **Gaps are fraktionslos.** A Mandat day that no Fraktion or Gruppe membership covers is fraktionslos.
4. **No overlaps.** Two memberships covering the same day fail the build by name. CONTEXT.md allows at most one Zugehörigkeit per day.
5. **Closed name map.** A new map from Stammdaten names to Zusammenschluss names, for example "Fraktion DIE LINKE." → `Die Linke` and the Gruppe names → `Gruppe Die Linke` / `Gruppe BSW`. A name outside the map fails the build. `derive.zusammenschluss` passes unknown names through, which here would silently undercount.
6. **Size check.** Each day's total is at most the legal size of its WP (631, 709, 736, 630), and reaches it on some day in each WP.
7. **WP filter.** Only Wahlperioden from `V1_FIRST_WAHLPERIODE` (18) on.

### Acquisition

- **Enrichment.** A new entry `mdb-stammdaten` in `scripts/features/__init__.py`, beside `mp-roster`.
- **Online build with the enrichment:** fetch the zip with a conditional GET (ETag), validate it with the rebuild's own checks (zip opens, XML parses, the derivation and size check pass), then replace the cache in the store's private directory (`stammdaten.cache_path`, D9). A failed fetch or validation keeps the previous file and warns.
- **Every rebuild,** `--offline --repersist` included, parses the cached file. The tables are recomputed from the cache, so they survive a repersist without a roster-style preserve.
- **No cached file:** both tables are empty, R2's seat column is NULL, and the build prints a warning. The Daten page says "Sitzzahlen: keine (MdB-Stammdaten nicht geladen)" and the manifest's `stammdaten` is null. Never silent.
- **Provenance.** The file's Stand (its `VERSION` stamp) and its sha256 go into the store table `mdb_stammdaten_stand`, the export manifest (`stammdaten`) and the Daten page (D10). A release then says which file its seats came from.
- **Hook.** In `rebuild_database_from_entries`, after the `persist_report` loop and the roster block, and before `registry.reconcile` / `facts.compute_and_store` (`build_dip_pulse_site.py:~1606-1671`).

### Cross-check against the roll-call totals (the gate)

For every roll-call in the store, compare the Stammdaten seats of each group on that date with `vote_fractions.total_count`. The build writes the full list of disagreements (vote id, date, group, Stammdaten seats, roll-call total, difference) to a report file and a summary line.

**This measures how far E4 reaches.** The gate passes when every disagreement is explained by one of:
- **E4:** WP 19, from vote 750 on.
- **E5:** vote 440.
- **Vacancy or change timing:** a change dated on the vote's day, or a vacancy one source records and the other does not.
- **A new `docs/source-errors.md` entry,** quoted against the Bundestag's own pages or the Textarchiv, for whichever source is wrong.

**Acceptance pins** (Textarchiv `kw32-fraktionslose-1014020`):
- AfD 88, fraktionslos 8 on 2021-06-24
- AfD 87, fraktionslos 9 on 2021-08-25 (Hollnagel out on 25 June, Heßenkemper back on 24 August)
- Die Linke gone and fraktionslos at 44 from 2023-12-06 to 2024-02-01
- Gruppe Die Linke 28 and Gruppe BSW 10 from 2024-02-02

If the Stammdaten dates the Gruppen differently from 2024-02-02, D4 reopens, because the speech labels switch on that date.

After the Stand date, the comparison also catches drift. D6 = (a), as decided, so each roll-call after the Stand that disagrees gets a warning and a caveat line. Those disagreements are expected, and they never fail the gate.

### Recipe R2 (D2)

- **New column `sitzanteil_prozent`:** the group's mean seats over the WP's sitting dates (distinct `protocols.date`), divided by the mean Bundestag size over the same dates.
- **SQL:** a sitting-date CTE joined to `party_seats` by the lookup rule.
- **NULL cases:** the Sprechrollen (Bundesregierung, Bundesrat, weitere) and Unbekannt. fraktionslos gets its share.
- **A complete WP** has a Stammdaten row on every sitting date. Dates after the Stand follow D6.

### Export, licence and dictionary

- **Export format:** the two tables enter the export automatically. Format 11 → 12, CSVs 29 → 31.
- **Source tag:** both tables go into `_TABLE_SOURCE_BUNDESTAG`. `party_seats` is derived, so it may belong in `_TABLE_SOURCE_DERIVED` instead, if `_check_license_layers` wants that for a computed count. Decide in step 6.
- **Licence layer (D7):** the Stammdaten is a new source under ADR 0003, and the existing `bundestag-abstimmungen` layer names the roll-call pages, not this file. Add a layer `bundestag-stammdaten`, mapped to `{"bundestag.de"}` in `LICENSE_LAYER_SOURCES`. Its redistribution terms join the D-track legal items as a **release blocker, not an implementation blocker**.
- **Docs:** `scripts/data_dictionary.json` gets both tables, and `docs/data-methods.md` gets the interval rules, the lag and the cross-check.

## Steps

1. **1b. Get the file and read it (needs the owner's go to download).**
   - The sandbox's TLS proxy blocks bundestag.de for curl, so the owner runs the download into a fresh empty directory.
   - The file is then read with `python3 -I` from a script kept outside that directory.
   - Record in "Step 1b findings":
     - the file names in the zip and its size
     - the root and person element names
     - the Mandat and membership elements and their date format
     - how the Fraktion/Gruppe institution type is spelled
     - any Stand or version stamp
     - every distinct Fraktion or Gruppe name for WP ≥ 18
     - membership records without dates
     - overlaps and their count
   - Finalise the column names and the name map from this.
2. **Interval derivation, test-first (tdd).** Tests cover:
   - each of rules 1–7
   - the Linke split (Fraktion ends, fraktionslos gap, Gruppe starts)
   - a switcher (AfD → fraktionslos)
   - a rejoin (Heßenkemper-shaped)
   - a vacancy
   - an unknown name failing
   - an overlap failing
3. **Schema 9.**
   - `SCHEMA_VERSION` 8 → 9 and both `CREATE TABLE`s.
   - A sentinel in `require_current_schema`: `mps` present but `party_seats` absent.
   - The writers and the rebuild hook.
   - Tests: `tests/test_repersist.py` (identical rows after a second repersist, and both tables empty with a warning when there is no cached file) and the `tests/test_a1_followups.py:633` pin.
4. **Acquisition.**
   - The enrichment entry, the fetch, the validation, the keep-previous-on-failure rule, and the provenance.
   - Tests with a small fixture under `tests/fixtures/`, built from the step 1b structure. No network in tests.
   - Done (2026-11-01), see "Step 4 result".
5. **Cross-check.** The disagreement report and its summary line. A test with a fixture vote whose total disagrees.
6. **Export.**
   - Done in step 3 (the export refuses a table without a dictionary entry): the source tags, the `bundestag-stammdaten` layer, the dictionary entries, the captions, `EXPORT_FORMAT` 12 and the `tests/test_daten_export.py` pins.
   - A `column_source` test (beside `tests/test_build_dip_pulse_site.py:3182`).
   - `tests/_daten_fixture.py` with Stammdaten-derived rows.
7. **R2.**
   - `sitzanteil_prozent` and its definition.
   - The replay test.
   - A new test: the column sums to 100 over the groups with seats in each WP, and is NULL for the Sprechrollen.
   - Re-check `tests/test_daten_export.py:34, 1299, 1340, 1433` and `tests/test_sprechrolle.py:266`.
8. **Docs and TODOS.**
   - README and `docs/stable-ids.md`: schema 9, export format 12.
   - `docs/data-methods.md`.
   - Change the roadmap note "small" for C1.
   - Move C1 to Completed.
   - New TODOS, kept out of C1:
     - correct E4's `vote_members` / `vote_fractions` attribution for the affected WP 19 roll-calls, now possible from the Stammdaten
     - link `mdb_zugehoerigkeiten` to `mps.xml_redner_id`
     - the government-office MdBs TODO is now unblockable from the same file: add a note there
     - the `GRUPPE_DIE_LINKE_SINCE` naming note
     - the licence layer under D
9. **Replay on the real store, as part of the owed A3 post-merge rebuild** (disk: about 52 GB free, about 13 GB per gate).
   - Use a `cp -cR` clone, then `--enrich mdb-stammdaten` online (one fetch), then `--offline --repersist` twice, then export.
   - Report:
     - per WP: the number of `party_seats` rows, the maximum total, and the composition on the first and last sitting day
     - the cross-check's disagreement count by cause
     - R2's new column
   - No existing figure moves, so only R2 gains a column.
   - Apply `docs/agents/review-checklist.md`.

## Done when (replaces the TODO's criterion)

- Both tables exist after `--repersist` and are unchanged after a second one.
- Each day's total is at most the legal size, which is reached in each WP: 631, 709, 736, 630.
- The four Textarchiv pins hold.
- The cross-check has every disagreement explained (gate above). The count by cause is reported.
- No `party_seats` row exists for `Unbekannt` or the stray party rows ("Bremen", "CDU/CSU: Ich glaube…").
- A build with no cached file says so in the warning, the Daten page and the manifest.
- Both tables are in the Daten export with complete dictionary entries and the Stand and sha256 in the manifest. R2 shows `sitzanteil_prozent`.

## Step 2 result (2026-11-01)

The derivation lives in `scripts/derive.py`: `mdb_zugehoerigkeiten(mdbs, since_wahlperiode=...)`, `party_seats(rows)` and `check_seat_totals(seats)`, with `STAMMDATEN_ZUSAMMENSCHLUESSE`, `BUNDESTAG_SIZES` and `StammdatenError`. `tests/test_seat_counts.py` pins rules 0–7, the Linke split, a switcher, a rejoin, a vacancy and both failures. The input is one dict per `MDB` element, keyed by the XML element names, with dates as the file writes them, so the step-4 reader only turns XML into dicts.

### S5. The real file needed one more rule

Run against the real file through a throwaway reader, the first version failed rule 6: WP 20 had 737 seats on two days. `MDBWP_BIS` is a Mandat's last day: of the 41 successors who start within a day of a leaver, 39 start the day after (measured per WP: 5, 17, 17, 2 such cases). Two start on the leaver's last day itself:

| Day | Leaver | Successor | Group |
|---|---|---|---|
| 2023-08-07 | Alexander Graf Lambsdorff (NW list) | Katharina Willkomm (NW list) | FDP |
| 2024-03-04 | Nina Stahr (Berlin list) | Franziska Krumwiede-Steiner (NRW list) | Grüne |

The second case is the Berlin repeat election moving a Grünen seat to another Land's list, so the rule cannot require the same Land. **Rule (Mandat ends, under rule 1):** the day belongs to the new Mandat, as a handover day between groups does. Only the Bundestag total changes; no group count does, because both Mandate belong to the same group. The rule trims exactly these two Mandate in the file.

After the rule, the file gives 2,914 `mdb_zugehoerigkeiten` rows and 171 `party_seats` rows (WP 18: 29, WP 19: 66, WP 20: 62, WP 21: 14). The size check passes in all four WPs. Every S3 pin and first-day composition is reproduced exactly. The last WP 20 day is 733 (SPD 207, CDU/CSU 196, Grüne 117, FDP 90, AfD 76, Gruppe Die Linke 28, Gruppe BSW 10, fraktionslos 9). The Stand day 2026-04-29 is 630 (CDU/CSU 208, AfD 150, SPD 120, Grüne 85, Die Linke 64, fraktionslos 3).

## Step 3 result (2026-11-01)

Schema 9 is in, test-first. The owner settled four questions before the tests were written.

**What changed**
- **Schema.** `SCHEMA_VERSION` 8 → 9. Both tables are created in `persist_dip_pulse_store.initialize`, with `party_id NOT NULL` (D8). Neither table has `created_at`/`updated_at`: the rows are recomputed on every rebuild, and with no clock column a second repersist leaves the file byte-identical.
- **Sentinel.** `require_current_schema` refuses a store that has `mps` but no `party_seats`, so only `--offline --repersist` upgrades a schema 8 store.
- **Store writer.** `pulse_store.persist_seat_counts(conn, zugehoerigkeiten, seats, now)` replaces both tables and maps each `party` name, `"fraktionslos"` included, to its row through `upsert_party`.
- **Hook.** `build.rebuild_seat_counts(store, read_cached_stammdaten(database_path))` runs in `_rebuild_database_from_entries` after the roster block and before `require_current_speech_rules` / `registry.reconcile`. Every rebuild reaches it: online, `--repersist`, and every test caller.
  - **No Stammdaten (None):** both tables stay empty, and stderr gets `warning: [stammdaten] keine Sitzzahlen (MdB-Stammdaten nicht geladen)`.
  - **A `StammdatenError`:** an interval rule, the closed name map or the size check fails; the hook raises `DatabaseRebuildError` and the store is untouched. Without this wrapping, the CLI would have printed a traceback.
  - **Stammdaten with no Mandat from WP 18 on:** an empty file, or only older WPs, also raises `DatabaseRebuildError` (checklist class 5). `check_seat_totals` checks only the WPs present, so the tables would otherwise have come out empty with no warning.
- **Loader.** `read_cached_stammdaten(database_path)` returns None until step 4 reads the zip. It is the test seam: tests patch it with synthetic `MDB` dicts.
- **Export (brought forward from step 6, owner decision).** The export iterates every store table and refuses one with no dictionary entry, so step 3 needed these pieces:
  - dictionary entries for both tables
  - Daten-page captions
  - source tags: `mdb_zugehoerigkeiten` is `bundestag.de`, except `valid_from`/`valid_until`, which are `derived` because the interval rules cut them; `party_seats` is `derived`
  - the `bundestag-stammdaten` licence layer, mapped to `{"bundestag.de"}`
  - `EXPORT_FORMAT` 11 → 12, so 29 → 31 CSVs
  - the pins in `tests/test_daten_export.py` (CSV count, format, primary keys)
  - README, CONTEXT.md, `docs/stable-ids.md`, `docs/project-documentation.md` and `docs/data-license.md`, which stated schema 8 / format 11 / 29 CSVs and would otherwise be false

  Step 6 keeps the `column_source` test, the `_daten_fixture` rows and `docs/data-methods.md`.

**Tests** (`tests/test_repersist.py`; the `test_a1_followups` pin is now 9):
- no Stammdaten: both tables empty, warning on stderr
- 630 synthetic WP 21 MdBs plus a switcher (AfD → fraktionslos on a handover day): exact `party_seats` rows and the switcher's two Zugehörigkeit rows; a second repersist keeps the file and the rows
- 3 MdBs: the size check raises `DatabaseRebuildError`, store byte-identical
- empty / WP 17-only Stammdaten: `DatabaseRebuildError`, store byte-identical
- a schema 8 store: refused byte for byte by a non-upgrade rebuild, upgraded by repersist

Rule 6 needs each WP's legal size reached, so any fixture needs a whole Bundestag. Step 4's fixture zip has the same constraint.

**Real-file check.** A scratch reader ran the real file through `derive` and `persist_seat_counts` into an in-memory schema 9 store. The result was 2,914 / 171 rows (29 / 66 / 62 / 14 per WP), no PK, CHECK or FK failure, and the nine parties expected. The four Textarchiv pins and the Stand-day composition match step 2.

**Figures.** No existing figure moves. Production builds pass None until step 4, so both tables are empty and no other table is touched. The export gains two header-only CSVs and the format number.

**For step 4**
- `read_cached_stammdaten` gets only `database_path`, but the zip lives in `OUTPUT_DIR/data`. With `--database-path` elsewhere, that is not the store's directory. Step 4 either passes the output directory to the rebuild or keeps the file beside the store. **Resolved in step 4 (D9):** the cache is keyed off the store.
- `derive.mdb_zugehoerigkeiten` raises `KeyError`/`ValueError`, not `StammdatenError`, on an `MDB` without `ID` or a `WAHLPERIODE` with a non-numeric `WP`. The hook catches only `StammdatenError`. The reader must refuse such records, or derive must raise `StammdatenError` for them, so a malformed file ends in `DatabaseRebuildError` and not a traceback. No input reaches this today.
- `xml.etree` elements are falsy when they have no children, so `wp.find("INSTITUTIONEN") or []` is the wrong test. Use `is not None`.

### Step 3 review checklist (`docs/agents/review-checklist.md`, full pass: 379+ changed lines)

1. **Sibling path.**
   - **Sentinel:** it lives in `require_current_schema` (`persist_dip_pulse_store.py:57`), which every path calls: `initialize`, the non-upgrade rebuild (`build_dip_pulse_site.py:~1585`), the export (`:~4103`, before the dictionary loads; pinned in the schema 8 test), `facts.ensure_canonical`, and the offline render and pipeline checks (`:~13401`, `:~13627`, `:~13702`, `:~14028`).
   - **Hook:** it sits in `_rebuild_database_from_entries`, the one function behind the online persist, `--repersist` and every test rebuild. `--no-persist` and the facts engine never rebuild and never write the seat tables.
2. **Stale beats fresh.** Not touched. The tables are deleted and rewritten in a fresh staged store, with no carry-over.
3. **Order and history.** `derive.party_seats` sorts its output, and the S5 tie-break goes in id order. `_content_digests` is order-independent, and the second-repersist test pins a byte-identical file.
4. **One key, one function.** A party name becomes its id only through `upsert_party` (`stable_key("party", name)`), the same function `speeches`, `vote_fractions` and `vote_members` use. `mdb_id` is `derive._clean(ID)`. A missing `ID` is the step-4 item above.
5. **Absent vs zero.** None means no Stammdaten: warning, empty tables. An empty derivation is refused (`build_dip_pulse_site.py`, `rebuild_seat_counts`), with a test. A WP missing from an otherwise good file gives no rows for that WP. That is "no seat count" under the lookup rule, and step 5's cross-check flags it.
6. **Derived columns.** Not touched.
7. **Neighbour binding.** Not touched.
8. **Hostile text.** Not touched. No new scanner; the step-2 derivation is unchanged.
9. **Input shape.** No new flag, file or id reaches a path. Malformed `MDB` dicts are the step-4 item above.
10. **Interrupted run.** Both writes go into the staged store, inside the existing swap. A failure unlinks the staged file, and the published store is untouched (tests pin it byte for byte).
11. **Claims.**
    - The dictionary entries follow `derive._stammdaten_name` (the name on the first day), `_mandate_stretches` (clipping, handover day) and the S5 trim. "Ein Name außerhalb der Liste bricht den Build ab" is `StammdatenError` turned into `DatabaseRebuildError`. The size sentence is `check_seat_totals`.
    - The `mdb_id` = Redner-ID claim is checked on the real file: 11003516 is Alexander Dobrindt and 11004792 is Rainer Kraft, the Redner-IDs the protocol fixtures use.
    - README "31 CSV.gz" is pinned by `test_all_thirty_one_csvs_named_and_headered`.
    - The caption no longer calls `party_seats` a denominator, since no per-seat figure exists yet.
    - **Owed under D7:** the attribution short string in `docs/data-license.md` (embedded in DATA.md) and ADR 0003 name no MdB-Stammdaten. It changes with the layer's terms, before a release.
12. **Loop cost.** About 2,900 rows go in through `executemany`, with one `upsert_party` per party name (cached). That is negligible against a rebuild.
13. **Last commit.** Rechecked after the class 5 and class 11 fixes: the new guard has its test, and the wording fixes are covered by the export tests.

**Checks no diff review replaces**
- **Figures:** none moved. Production passes None until step 4, so no existing table is written differently. The only output change is format 12 and two header-only CSVs. The real file through the writer reproduces the step-2 numbers.
- **Fresh vs incremental:** the second-repersist test (same file, same rows).
- **Browser:** not opened. The Daten page gains two rows from the same `render_daten_schema` template, and the caption test covers both.
- **Python 3.13.12:** not reached; `html.parser` is untouched.
- **Adversarial lenses (red team, Codex):** owed once, on the C1 tip handed to `/gstack-ship`.

## Step 4 result (2026-11-01)

The acquisition is in, test-first. The owner settled three questions first: the cache location (D9), the provenance shape (D10), and the fetch staying opt-in.

**What changed**
- **`scripts/stammdaten.py` (new).**
  - `cache_path(database_path)`: the zip lives in `registry.private_dir(database_path)` as `mdb-stammdaten.zip`, beside the writer lock, never in the published OUTPUT tree (D9). It works with any `--database-path`.
  - `read_zip(path)` keeps only what the seat counts need: `ID`, `NAMEN` (name fields and `HISTORIE_VON`) and `WAHLPERIODEN` (`WP`, Mandat dates, the `INSTITUTIONEN` with type, name and dates). Biographies stay out.
    - It reads the top-level `MDB_STAMMDATEN.XML` in memory, skips the `__MACOSX/` fork and refuses a member over 64 MB.
    - The Stand is the decoded `VERSION` stamp; the sha256 is that of the zip.
    - A file that is no zip, lacks the XML or `VERSION`, does not parse, has the wrong root, or holds an `MDB` without `ID` or with a non-numeric `WP` raises `StammdatenError` (step 3 handover).
  - `seat_rows(records, since_wahlperiode)`: the derivation plus the size check, refusing an empty result. The rebuild and the fetch both call it, so a fetched file is checked exactly as the rebuild will check it.
  - `refresh(database_path, since_wahlperiode)`: the `--enrich mdb-stammdaten` fetch.
    - **Request:** a conditional GET with the ETag from the sidecar `mdb-stammdaten.json`, a body cap of 32 MB, and urllib's `HTTPError(304)` read as "unchanged".
    - **On a 200:** it writes a temp file in the same directory, checks it with `read_zip` and `seat_rows`, then calls `os.replace`, and only after that writes the ETag.
    - **On failure:** a failed request, a failed check, or a failed write or replace keeps the previous file and prints one warning naming the cause and the Stand kept. With no cached file, the warning says "keine Sitzzahlen".
    - **Cleanup:** temp files left by a killed refresh are removed first.
- **Rebuild.** `rebuild_seat_counts(store, database_path)` reads the cache. A cached file that cannot be read raises `DatabaseRebuildError`. It does not fall back to empty tables, because the fetch never stores a file that fails its checks.
- **Schema 9, amended in place (unpushed).** New one-row table `mdb_stammdaten_stand(sha256 PK, stand)` (D10). The fetch time and ETag stay in the sidecar, so a second repersist stays byte-identical.
- **Export.**
  - The provenance table is exported: 32 CSVs, with a dictionary entry. The `stand` column has layer `bundestag-stammdaten` and `sha256` has `eigene-metadaten`; the table's source tag is `bundestag.de`.
  - The manifest gains `stammdaten: {stand, sha256}`, or null.
  - The Daten page prints "Sitzzahlen: MdB-Stammdaten des Bundestages, Stand TT.MM.JJJJ · sha256 …", or "Sitzzahlen: keine (MdB-Stammdaten nicht geladen)".
- **Enrichment and wiring.** `mdb-stammdaten` is in `ENRICHMENTS`, opt-in like `mp-roster`. The online persist path calls `stammdaten.refresh` after the Vorgang cache refresh and before the staged rebuild. `--offline` and `--no-persist` never fetch.
- **Docs.** README (the enrichment table and `--enrich` rows, 32 CSVs, the format 12 note), `docs/stable-ids.md` and `docs/data-license.md`.

**Tests**
- `tests/test_stammdaten.py` (11):
  - **Reader:** fixture to records, records through the derivation, the bad-file cases, the size cap, the cache path.
  - **Refresh:** 200, 304, 304 without a cache, network error / 503 / non-zip / seat-rule failure each with and without a previous file, a failed cache write, the size cap.
- **Other test files:**
  - `tests/test_repersist.py`: provenance row, unreadable cache, the private-cache lookup.
  - `tests/test_daten_export.py`: manifest and Daten-page line, 32 CSVs, primary key.
  - `tests/test_backfill.py`: the refresh runs only with `--enrich mdb-stammdaten`, before the rebuild.
  - `tests/test_features.py`: four enrichments.
- **Fixture.** `tests/fixtures/mdb-stammdaten-mini.xml` holds three made-up MdBs in the file's element names. The tests zip it at run time instead of committing a binary zip. The fetch tests generate a whole 630-seat WP 21 zip, because the size check needs one.

**Real-file check.** `read_zip` on the real download (952,696 bytes) gives 4,614 `MDB` records, Stand 2026-04-29T08:03:03Z and sha256 `29ae4ba1…`, the same as step 1b. Through `seat_rows` that makes 2,914 / 171 rows in 1.5 s. The record keys are only the kept fields.

**Figures.** None moved. Without a cached file every build behaves as in step 3. The export gains the provenance CSV and the manifest key.

**Left open**
- `refresh` makes one attempt, with no retry and no line in the DIP request log (`DIP_REQUEST_LOG`). A failed fetch keeps the previous file, and the next build tries again.
- If writing the ETag sidecar fails after the replace, the warning names the old Stand although the new file is cached. The next fetch is then a full download. Cosmetic.
- A replay copy of the site must also copy `.OUTPUT.private/`, or the copy has no cached Stammdaten (step 9).

### Step 4 review checklist (full pass)

1. **Sibling path.** The fetch runs only on the online persist path (`build_dip_pulse_site.py`, after `refresh_vorgang_cache`). `--offline`, `--no-persist` and the facts engine never fetch. Every rebuild reads the cache through `rebuild_seat_counts`, one function. The export reads only the store.
2. **Stale beats fresh.** A failed fetch keeps the previous file by design (plan rule). A 304 is sent only when a readable cache exists. The ETag is written after the replace, so it is never newer than the file.
3. **Order and history.** The output depends on the cached bytes only. The fetch time and ETag stay out of the store, and the second-repersist test pins byte identity.
4. **One key, one function.** The cache location is `stammdaten.cache_path`, used by both the fetch and the rebuild. The Stand comes from `read_zip` only.
5. **Absent vs zero.** No file means a warning and empty tables. An unreadable file stops the build. An empty derivation is a `StammdatenError` in `seat_rows`, covering both the fetch and the rebuild. A 304 without a cache is a warning.
6. **Derived columns.** Not touched.
7. **Neighbour binding.** Not touched.
8. **Hostile text.** The zip member size is checked before reading, and the read is capped. ElementTree resolves no external DTD, and expat limits entity expansion. Malformed records raise `StammdatenError`. Timing: the real 15.3 MB file reads in 1.5 s.
9. **Input shape.** The URL is a constant. A sidecar that is not JSON, not an object, or has a non-string ETag is ignored. The body is capped.
10. **Interrupted run.** A temp file sits in the cache dir and `os.replace` is atomic. A killed refresh's temp file is removed on the next refresh. The ETag goes after the file, and a write failure warns and keeps the file. The staging cleanup glob (`<store>.*.tmp*`) never matches the refresh temp files.
11. **Claims.**
    - The README enrichment row matches `refresh` (conditional GET, validation, keep-previous) and `cache_path`.
    - The Daten-page line is pinned by its test.
    - The dictionary `stand` entry says "spätere Änderungen fehlen bis zur nächsten Veröffentlichung", which is D6.
    - The dictionary `sha256` entry says it is computed over the bytes of the downloaded file: `read_zip` hashes the cached file, which is the downloaded body written unchanged.
12. **Loop cost.** One request per build with the enrichment. Parsing takes 1.5 s, and the fetch parses the file a second time only on a 200.
13. **Last commit.** Re-run on the 304, stale-temp and write-failure fixes; each has its test.

**Checks no diff review replaces**
- **Figures:** none moved (above).
- **Browser:** not opened. The Daten page gains one `<p>` in `render_daten_datenstand`, and its test checks the text.
- **Live fetch:** not run. The sandbox blocks bundestag.de, so the first real `--enrich mdb-stammdaten` run belongs to step 9 or is yours.
- **Python 3.13.12:** not reached; `html.parser` is untouched.
- **Adversarial lenses:** owed once, on the C1 tip handed to `/gstack-ship`.

## Decisions

| | Question | Recommendation |
|---|---|---|
| D1 | Seat source | **Decided 2026-11-01 (owner): MdB-Stammdaten**; roll-call totals as the cross-check |
| D2 | R2 per-seat column | `sitzanteil_prozent`, mean seats over the WP's sitting dates |
| D3 | Same-day roll-call disagreements | No longer a seat rule. For the cross-check, compare each vote on its own; E4/E5 explain the known cases |
| D4 | WP 20 Linke boundary | Resolved (F4) unless the Stammdaten dates the Gruppen other than 2024-02-02 |
| D5 | Textanteil rename of R2 | Optional fold-in (same lines), otherwise its own TODO |
| D6 | Dates after the Stammdaten's Stand | **Decided 2026-11-01 (owner): (a).** Evidence in S4: 1 of 33 roll-calls after the Stand disagrees. (a) Carry the Stand composition forward, print the Stand date beside every seat figure and in the manifest, and flag later roll-call disagreements as drift. The alternatives: (b) no seats after the Stand, which leaves months of WP 21 with no denominator; (c) fill in from roll-calls after the Stand, which brings E4-type errors back into recent months. Decide after step 1b |
| D7 | Licence layer | New layer `bundestag-stammdaten`; terms settled under track D before a release. The layer exists since step 3 |
| D8 | How fraktionslos is stored | **Decided 2026-11-01 (owner): the existing `fraktionslos` parties row**, `party_id NOT NULL` in both tables. A NULL would let SQLite's composite primary key accept duplicate fraktionslos rows, since every NULL counts as distinct. It would also make the seat tables the only ones that do not spell fraktionslos the way `speeches`, `vote_fractions` and `vote_members` do (through `upsert_party`), and every join in steps 5 and 7 would need a COALESCE. A forgotten COALESCE drops the fraktionslos share with no error |
| D9 | Where the cached zip lives | **Decided 2026-11-01 (owner): the store's private directory** (`registry.private_dir`, beside the writer lock), not `OUTPUT/data`, which is published with the site while the file's redistribution terms are open (D7). Keyed off the store, so `--database-path` works too |
| D10 | How the Stand and sha256 reach the export | **Decided 2026-11-01 (owner): a one-row store table `mdb_stammdaten_stand`** (exported, 32 CSVs), the manifest key `stammdaten` and a Daten-page line. The fetch time and ETag stay in a sidecar beside the zip. The fetch is opt-in (`--enrich mdb-stammdaten`), like `mp-roster` |

## History: why the source changed

### Roll-call totals as first measured (reference store, schema 6, 2026-10-28)

| WP | roll-calls | dates | first | per-vote Bundestag size (count) |
|----|-----------:|------:|-------|---------------------------------|
| 18 | 127 | 48 | 2014-02-20 | 630 (74), 631 (46), 629 (6), 628 (1) |
| 19 | 179 | 76 | 2017-12-12 | 709 (157), 708 (22) |
| 20 | 171 | 82 | 2021-11-18 | 736 (124), 733–735 (44), 732 (3) |
| 21 | 79 | 36 | 2025-06-25 | 630 (75), 629 (3), 628 (1) |

The maximum sum in each WP is the legal size. The latest WP 21 composition (2026-10-15) was CDU/CSU 208, AfD 150, SPD 120, Grüne 85, Die Linke 64, fraktionslos 3.

### Step 1 findings (2026-11-01)

- **F1. Same-day disagreements.** Both are source defects.
  - 2016-11-09: vote 440 omits Bellmann and Grosse-Brömer (E5).
  - 2021-06-24 to the end of WP 19: Witt and Huber, and later Heßenkemper, are listed as fraktionslos while they were still in the AfD. Per the Textarchiv, Witt and Huber left only on 2021-12-31, and Heßenkemper rejoined on 2021-08-24 (E4).
  - No rule that uses only the roll-call data can fix E4. **This is what moved D1 to the Stammdaten.**
- **F2. Ordering key.** `votes.id` is the bundestag.de Abstimmung id, numeric in all 556 rows. It is not chronological across days, so ordering is `(date, CAST(id AS INTEGER))`. It still orders the cross-check report.
- **F3. `Unbekannt`.** It can arise via `derive.merge_fractions` and `persist_vote`, but none exists in the reference store. The cross-check skips such a vote with a warning.
- **F4. WP 20 Linke boundary.** The Textarchiv dates the Fraktion's end to 2023-12-06 and the Gruppen's recognition to 2024-02-02. The protocols label the 38 MdBs fraktionslos in between: 78 speeches, and no Linke or Gruppe label. The Gruppe labels start on 2024-02-02. `GRUPPE_DIE_LINKE_SINCE` never re-files anything in the interval, so speeches and seats agree. The constant's name is misleading (TODOS note).

## Step 1b findings (2026-11-01)

The file was downloaded with the owner's go: 952,696 bytes, sha256 `29ae4ba1…8bde460`, ETag `"6d9ec31bcde36989e29cc743ff3a285d"`, no `Last-Modified` header. It was read with `python3 -I` from scratch scripts. The survey and cross-check scripts live in the session scratchpad, not in the repo.

### S1. Structure (from `MDB_STAMMDATEN.DTD`, which ships in the zip)

**Zip contents:**
- `MDB_STAMMDATEN.XML` (15.3 MB)
- `MDB_STAMMDATEN.DTD`
- a `__MACOSX/` resource fork, which the reader must ignore

**Elements:**
- The root is `DOCUMENT(VERSION, MDB+)`.
- **Stand stamp:** `VERSION` is a Unix timestamp, here `1777449783` = 2026-04-29 08:03 UTC. The XML also carries the comment `Erstellt am: 29.04.2026 10:02:26`.
- **`MDB`:** `ID` (8 digits, e.g. `11000001`), `NAMEN/NAME+` (with `HISTORIE_VON/BIS` for name changes), `BIOGRAFISCHE_ANGABEN`, `WAHLPERIODEN/WAHLPERIODE+`.
- **`WAHLPERIODE`:** `WP`, `MDBWP_VON`, `MDBWP_BIS`, constituency fields, `MANDATSART`, `INSTITUTIONEN/INSTITUTION*`.
- **`INSTITUTION`:** `INSART_LANG`, `INS_LANG`, `MDBINS_VON`, `MDBINS_BIS`, `FKT_LANG`, `FKTINS_VON`, `FKTINS_BIS`.
- **Dates** are `TT.MM.JJJJ`.
- **Institution types:** for WP 18–20 only `INSART_LANG = "Fraktion/Gruppe"` occurs. WP 21 also lists committees, ministries and others, which the reader filters out.

### S2. Interval facts that change the rules

**Mandate records:** WP 18: 658, WP 19: 750, WP 20: 772, WP 21: 635.

**Duplicate rows.** One `INSTITUTION` row exists per Fraktion *function* (`FKT_LANG`), so a Fraktion leader has the same membership twice (Bartsch, Mützenich, Bas, Haßelmann, …). **Rule:** merge rows with the same `(INS_LANG, MDBINS_VON, MDBINS_BIS)` before anything else. Counted naively, WP 18 starts at 635 seats instead of 631.

**Handover day.** When an MdB changes group, the old membership's `MDBINS_BIS` equals the new one's `MDBINS_VON` (Gysi: Fraktionslos until 02.02.2024, Gruppe Die Linke from 02.02.2024; Nüßlein: CDU/CSU until 07.03.2021, Fraktionslos from 07.03.2021). **Rule:** the handover day belongs to the new group. A membership's `valid_until` is the next membership's `MDBINS_VON` when that equals its `MDBINS_BIS`, otherwise `MDBINS_BIS` + 1.

**Open memberships.** A membership with no `MDBINS_BIS` ends with the Mandat.

**Wahlperiode ends.** `MDBWP_BIS` of a whole Wahlperiode is the next Bundestag's constituent day: WP 18 ends 24.10.2017, WP 19 26.10.2021, WP 20 25.03.2025. That day therefore lies in two WPs. The lookup always matches `wahlperiode`, so sitting dates resolve by their protocol's WP. WP 21 mandates have no `MDBWP_BIS` (630 open).

**Explicit fraktionslos.** It is an `INS_LANG` value, "Fraktionslos". Every mandate in WP 18–21 has at least one Fraktion/Gruppe row, and no mandate day is uncovered. Rule 3 (an uncovered day counts as fraktionslos) stays as a fallback that today's file never reaches.

**No conflicts.** After merging, no two different groups overlap other than on a handover day. No membership lies outside its mandate, and none is undated.

**Seat totals.** The maximum totals are 631, 709, 736 and 630, reached on the first day of each WP. Vacancies show as mandate gaps, for example WP 20 ending at 733.

**Closed name map (10 names):**

| Stammdaten `INS_LANG` | Zusammenschluss | WPs |
|---|---|---|
| Fraktion der Christlich Demokratischen Union/Christlich - Sozialen Union | CDU/CSU | 18–21 |
| Fraktion der Sozialdemokratischen Partei Deutschlands | SPD | 18–21 |
| Fraktion BÜNDNIS 90/DIE GRÜNEN | BÜNDNIS 90/DIE GRÜNEN | 18–21 |
| Fraktion DIE LINKE. | Die Linke | 18–20 |
| Fraktion Die Linke | Die Linke | 21 |
| Fraktion Alternative für Deutschland | AfD | 19–21 |
| Fraktion der Freien Demokratischen Partei | FDP | 19–20 |
| Gruppe Die Linke | Gruppe Die Linke | 20 |
| Gruppe BSW - Bündnis Sahra Wagenknecht - Vernunft und Gerechtigkeit | Gruppe BSW | 20 |
| Fraktionslos | fraktionslos (NULL `party_id`) | 18–21 |

### S3. The Textarchiv pins all hold

| Date (WP) | Stammdaten | Pin |
|---|---|---|
| 2021-06-24 (19) | AfD 88, fraktionslos 8 | AfD 88, fl 8 |
| 2021-08-25 (19) | AfD 87, fraktionslos 9 | AfD 87, fl 9 |
| 2023-12-15 (20) | no Die Linke, fraktionslos 44 | fl 44 |
| 2024-02-02 (20) | Gruppe Die Linke 28, Gruppe BSW 10, fraktionslos 6 | Gruppen from 02.02.2024 |

**D4 stays resolved:** the Gruppen start on 2024-02-02, the same day the speech labels switch.

**First day of each WP:**

| Date (WP) | Composition |
|---|---|
| 2013-10-22 (18) | CDU/CSU 311, SPD 193, Linke 64, Grüne 63 |
| 2017-10-24 (19) | CDU/CSU 246, SPD 153, AfD 92, FDP 80, Linke 69, Grüne 67, fl 2 |
| 2021-10-26 (20) | SPD 206, CDU/CSU 197, Grüne 118, FDP 92, AfD 82, Linke 39, fl 2 |
| 2025-03-25 (21) | CDU/CSU 208, AfD 152, SPD 120, Grüne 85, Linke 64, fl 1 |

These are the stretches before each WP's first roll-call, which the roll-call source could not cover.

### S4. Cross-check against all 556 stored roll-calls (the gate, run by hand)

497 roll-calls agree exactly for every group. The 59 that disagree all have a cause:

| Cause | Roll-calls | Detail |
|---|---:|---|
| Roll-call page misattributes MdBs (E4, extended) | 47 | Kamann and Bülow (WP 19, 2017-12 to 2018-12), Pasemann (WP 19, 2020-11/12, the reverse direction), Witt and Huber (WP 19 votes 750–754 and WP 20 votes 756–757), Heßenkemper (753–754). The Textarchiv backs the Stammdaten in every case |
| Group change on the vote's day | 3 | 2024-02-02, votes 897, 898, 912: the roll-calls list the 38 as fraktionslos on the day the Gruppen were recognised; the Stammdaten counts the Gruppen from that day |
| Member missing from one list (E5) | 1 | vote 440, 2016-11-09 |
| One seat fewer on the roll-call, no member filed under another group | 7 | 639 (FDP 80/79, 2019-11-15); 779–784 and 802 (SPD 206/205, 2022-06-03 and 2022-09-30). A vacancy or a member missing from the list, not yet checked: **new source-errors candidates** |
| After the Stand date | 1 | vote 1004, 2026-05-22: CDU/CSU 208 vs 206 (back to 208 on 2026-06-11 in the roll-calls); 1 of the 33 roll-calls after the Stand disagrees |

**Consequences for the plan:**
- **The gate's causes become a closed list:** misattribution (E4), change on the vote's day, dropout (E5), a seat missing from the roll-call, and after the Stand. Any disagreement outside these fails the gate.
- **The 7 one-seat cases** get checked on their bundestag.de pages in step 5 and entered as candidates.
- **E4's existing-figure TODO grows:** 47 roll-calls, six MdBs, affecting the vote panel's group blocks and Abweichler for those votes. The fix can now use the Stammdaten.
- **D6, evidence for (a):** across five months after the Stand, one roll-call disagrees, by two seats that the roll-calls themselves show return three weeks later. Carrying the Stand composition forward with the drift flag costs little.
- **Acquisition can use a conditional GET** with `If-None-Match` and the ETag, because the server sends no `Last-Modified`. The Stand stored in `datenstand` is `VERSION` decoded, plus the sha256.
