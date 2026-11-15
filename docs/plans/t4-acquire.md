# T4: acquire the excluded sittings

**Status:** plan, 2026-11-15. The owner accepted all nine recommended decisions on 2026-11-15 (see "Decisions" at the end). Nothing is fetched yet.
**Parent:** `TODOS.md` "Coverage gate before the first data release", steps 6 (acquire), 7 (measure) and 8 (gate), with N8 (review of restored sittings) and N10 (vote links).
**Base:** main fd4760d (v0.46.0.0): store schema 14, export format 20, speech rule 9. The reference store `.context/dip-pulse-site` (main checkout) is still at schema 12: it was last replayed on v0.41.0.0 (2026-11-14) and holds 718 sittings, 619 votes and 590 vote links.
**Read for this plan:** `CLAUDE.md`, `docs/agents/review-checklist.md`, ADR 0005, `docs/plans/withholding-preflight/report.md`, `docs/plans/withheld-before-t4.md`, `docs/plans/vote-links-and-figures.md`, `docs/release-review.md`, `docs/release-reviews/cpp-bt-first-run-2026-11-14.md`, `~/agent-runs/fresh/run.sh` and its `requests.log`.

## What T4 does

The 85 sittings of the first exclusion list were left out whole, so their votes, TOPs and DIP links were never acquired (decision 0, 2026-10-22). 21/106 joined the list on 2026-11-12. Since ADR 0005 a refused Rede is withheld and the rest of the sitting is kept, so 83 of the 86 entries can now come back:

| Group | Sittings | How they come back |
|---|---:|---|
| Parse once single Reden are withheld | 69 | located refusals, withheld by the parser |
| N7: known wrong units | 4 (18/2, 18/29, 18/83, 19/25) | `withhold` entries in `scripts/reviewed_units.json` |
| ADR 0004 presidium kinds | 10 (18/1 by its read acceptance; 18/173, 18/178, 18/193, 18/215, 18/223, 18/245, 19/1, 19/9, 19/19, 19/73) | presidium entries in the reviewed list, since v0.40.0.0 |
| 21/106 | 1 | one withheld split part, `ID2110609100:4` |
| **Back with T4** | **83** | |
| Wait for a rule | 2 (18/62, 18/90) | a Vizepräsidentin's Nachfrage in the Fragestunde, outside any `<rede>`; see D4 |
| Stay out | 1 (18/20) | `source_defect`: dserver's `18020.xml` holds sitting 21 |

The 69 is the TODOS figure of 68 plus 18/1, which TODOS counts with the ten ADR 0004 sittings. Either way the sum is 82 of the 85, plus 21/106.

### Re-measured at v0.46 on W1's XML (offline, 2026-11-15)

W1 fetched the 84 XML files on 2026-11-12 (`~/agent-runs/w1/xml`; 18/20 was rejected and not kept). This plan parsed all 84 again with the parser of fd4760d, offline, with the build's own `parse_protocol_xml` and the current reviewed list. Scratch scripts, not committed: `parse_w1.py`, `withheld_detail.py`, `n8_size.py`.

- **84 of 84 parse.** Every file's sha256 still equals the `xml_sha256` W1 recorded in `preflight.json`.
- **18/62 and 18/90 parse but cannot persist:** the persist role check stops on Pau's and Singhammer's unmapped presidium roles (`coverage-gate-pr2.md`, "Persist check for T4"). They stay on the record.
- **Withheld in the 82 sittings: 94 Reden in 74 sittings.** 89 are located refusals (`refused_nested_contribution`) and 5 are reviewed entries (N7: 18/2 one, 18/29 one, 18/83 two, 19/25 one). Own words 76,912; the other speakers' turns inside them hold 25,539 more, which go to `withheld_turns`.
- **Against W1's report:** W1 counted 90 Reden in 71 sittings, before the reviewed list existed. 18/1 no longer withholds anything, because ADR 0004 reads its election acceptance (90 − 1 = 89), and the reviewed list adds 5. W1's 94,707 words were own plus nested words; the store counts own words in `withheld_units.word_count` and nested words in `nested_word_count`.
- **Plus 21/106:** one more Rede, so **T4 expects 95 withheld Reden in 75 sittings**. The 21/106 XML has never been fetched, so its words are unknown.
- **Redner-IDs:** all 94 withheld Reden carry one: 78 distinct ids for 79 printed names. None is one of the 7 partitioned ids in `scripts/person_corrections.json`. Every one is held by an `mps` row of the reference store. So `every_withheld_rede_has_a_redner_id` should read true, and A4's two expected zeros of `withheld-before-t4.md` hold [measured on W1's XML].
- **Stored in the 82:** 1,021 TOPs and 6,451 Reden, 52 of them split parts. Beiträge: 498 Zwischenfragen, 482 zu Protokoll, 424/419 Fragestunde questions/answers, 143 Kurzinterventionen, 143/135 Befragung, 118 Erwiderungen, 14 Ansprachen. 102 pass-1 diagnostics: 55 `merged_zwischenfrage` and 47 `procedural`.
- **Own words withheld per year:** 2013 4,593; 2014 16,005; 2015 19,475; 2016 9,338; 2017 4,868; 2018 11,360; 2019 1,731; 2020 5,634; 2021 3,010; 2022 898. By Fraktion: CDU/CSU 51,961; Grüne 8,296; SPD 7,259; Linke 4,531; AfD 2,468; none 1,551; FDP 846. Three sittings withhold more than two Reden: 18/158 (4), 18/26 (3) and 19/13 (3).

T4 measures these figures again on the fetched XML (V3). A difference means bundestag.de changed a file, or the code moved since this plan.

## Step 0: before the online run

All of these are offline except 0.4.

**0.1 Order against the vote-link work (D1).** Run T4 on main **before PR C** of `vote-links-and-figures.md`, so the 83 sittings are linked by the rule that linked the 718. Then run the N10 review once over all 801 sittings, and let PR C change the rule for all of them. PR C before T4 would hit a known trap (TODOS "Check that vote links are right", deferred item 1). An online run hands kept reports to persist without re-attributing them, and the replay fixes a placement only in memory, never in the cached JSON. So after a rule change, `placement_errors` would refuse every one of the 718 kept reports and stop T4's online build.

**0.2 N8 on W1's XML, before the fetch (D3).** Units depend only on the XML and the parser. W1's 82 files are byte-identical to what W1 audited, and bundestag.de rarely changes a published protocol. So the N8 merge and attribution review (below) can run now, offline. Any wrong unit it finds is added to `reviewed_units.json` and lands on main before T4. Then the online run stores the reviewed result once. Otherwise every N8 finding would cost another reviewed-list change and another `--offline --repersist` of 801 sittings. V3 checks the fetched files' sha256 against W1's. A sitting whose file changed is reviewed again on the new file.

**0.3 Baseline store.** In the main checkout, on main's tip:
1. `--offline --repersist --output-dir .context/dip-pulse-site` (schema 12 → 14; this applies PR A's persisted vote figures and PR B's `basis`). No figure should move: PR A's and PR B's replays showed none. Compare against `.context/vf-b-after` (PR B's replay, schema 14) with `compare_store_values.py`. Report any difference before going on.
2. `cp -cR .context/dip-pulse-site .context/dip-pulse-site.pre-t4`, and copy `.context/.dip-pulse-site.private/mdb-stammdaten.*` to `.context/.dip-pulse-site.pre-t4.private/`, as in the README recipe "Validate a data correction". This clone is the "before" of every comparison and the rollback.

T4 then writes into `.context/dip-pulse-site` itself (D8), as the fresh build did.

**0.4 DIP caches.**
- **Persons.** The bulk person lists were fetched on 2026-11-10 and expire after `PERSON_MAX_AGE_DAYS = 30`, on 2026-12-10. Before that date nothing is needed. After it, re-run `prefetch_dip_bulk.py --wahlperiode N --persons` for 18 to 21 first (about 40 DIP requests in all, measured on 2026-11-10). Without it every speaker costs one `/person/{id}`.
- **Vorgang positions:** WP 18, 19 and 20 are bulk-merged and do not expire. WP 21 is open, so 21/106 pays one at a time.
- **Catalog:** fully fetched on 2026-11-10, and `CATALOG_FULL_FETCH_DAYS = 7`. The first T4 run fetches it whole (48 requests); later runs merge.

**0.5 Code and environment.** Run from a detached worktree at main's tip, not from the shared main checkout, which parallel sessions switch (`git -C /Users/luca/Projects/poliwatch worktree add --detach ~/agent-runs/t4/tree main`). Then the export records a clean revision; the fresh build recorded `28799ac90af8-dirty-…`. `--output-dir` points at the main checkout's store. Interpreter: uv's CPython 3.13 (`~/.local/share/uv/python/cpython-3.13-macos-aarch64-none/bin/python3.13`). `SSL_CERT_FILE` must point at the macOS system roots, as `fresh/run.sh` exports it. `DIP_API_KEY` comes from the owner's environment, and `DIP_REQUEST_LOG=~/agent-runs/t4/requests.log` records every request.

## Step 1: the online run (TODOS step 6)

### What it acquires

For each of the 83 sittings: the DIP Plenarprotokoll record, Aktivitäten and Vorgangspositionen (TOP ↔ Vorgang ↔ Drucksache), the Politikfelder `/vorgang` step, the XML from dserver, and the roll-call votes from bundestag.de (list pages, detail page and name list per vote). Then the build re-parses, attributes votes (`vote_links.attribute_votes`), persists every cached report into a staged store, and swaps it in. Last it writes the exclusion record, the facts, the export and the site.

Not acquired: abgeordnetenwatch profiles (`--enrich aw-profiles` stays off: the reference store has none, and item 1.5's question is open), the roster (kept: `preserve_roster`), and the MdB-Stammdaten (the cached zip in the private directory is read for the E4 re-filing).

### The options

`--include-document-number N` takes N off the record for the run. It needs an online run and refuses `--offline` and `--fetch-xml`. Three properties of the code decide how it is used:
- `update_coverage_exclusions` drops **every** included number from the record after the store swap, **whether or not the sitting was acquired**. A sitting included but not acquired is then neither stored nor excluded: it is "missing". A later `--backfill-incomplete` picks it up again, because a missing sitting is acquirable.
- `--backfill-incomplete` selects the catalog's missing or incomplete v1 sittings that are not on the record. Dry-computed on today's store with the build's own `incomplete_sitting_protocols` (scratch `backfill_scope.py`), with the 83 off the record: WP 18 selects exactly its 48, WP 19 its 33, WP 20 only 20/11. WP 21 selects 21/106 but would also take 21/107 to 21/109 once DIP lists their XML, so 21/106 gets its own `--document-number` run. The structural gaps (14, 13, 9 and 7 sittings) are not selected.
- A backfill defaults to `--sleep 2` and `--vote-scan-pages 200`. A `--document-number` run defaults to `--sleep 0` and 30 list pages, so the 21/106 run passes `--sleep 2`; 30 pages reach 2026-11-06 easily.

`--fetch-xml` and `--offline --repersist` are not part of the online run. `--fetch-xml` downloads XML only for cached reports without it, and the online path fetches and caches the XML itself. `--offline --repersist` follows only if a reviewed-list change lands after T4 (an N8 or N10 finding).

### The runner (D2)

`~/agent-runs/t4/run.sh`, written by the implementing session from `~/agent-runs/fresh/run.sh`. It reuses that script's step markers, logs, `/usr/bin/time -l`, its DIP-silence detection, the 6-hour wall-clock rest, and its stop on anything else. The steps:

```bash
BUILD=("$PY" scripts/build_dip_pulse_site.py --output-dir "$OUT")
# INC18 / INC19: arrays of "--include-document-number N" pairs, built from coverage-exclusions.json (see below)
# 00 only after 2026-12-10: for wp in 18 19 20 21: prefetch_dip_bulk.py --wahlperiode $wp --persons --sleep 1
step 01-wp20 build "${BUILD[@]}" --backfill-incomplete --protocol-wahlperiode 20 --sleep 2 --include-document-number 20/11
step 02-wp18 build "${BUILD[@]}" --backfill-incomplete --protocol-wahlperiode 18 --sleep 2 "${INC18[@]}"   # 48 numbers
sleep_until 3600                                     # dserver: about 50 XML per 60 minutes, and 48 + 33 > 50
step 03-wp19 build "${BUILD[@]}" --backfill-incomplete --protocol-wahlperiode 19 --sleep 2 "${INC19[@]}"   # 33 numbers
step 04-21-106 build "${BUILD[@]}" --document-number 21/106 --include-document-number 21/106 --sleep 2
```

- **WP 20 first, as the pilot.** One sitting, about 15 minutes, about 10 DIP requests. It shows the whole path working: the record shrinks by one, `withheld_units` gets 1 row (`ID201100900`), votes are acquired, and the facts read 20/11's week as "unvollständig erfasst: Sitzung 20/11: 1 Rede zurückgehalten". The implementing session checks this before the runner goes on (V1 to V3 on one sitting).
- **Each run includes only the sittings it acquires.** Naming a WP 19 number in the WP 18 run would drop it from the record, unacquired, until the WP 19 run.
- **The 48 and 33 numbers** come from `coverage-exclusions.json`, filtered by Wahlperiode and by reason `awaiting_acquisition` (18/62 and 18/90 read `awaiting_rule`). The runner checks the counts 48 / 33 / 1 / 1 before it starts, as `fresh/run.sh` checks its 85.
- **A failed run** (exit 1 after DIP stops) has already swapped in what it acquired and dropped all its included numbers from the record. Re-running the same step is correct: the backfill finds the missing sittings, and an `--include-document-number` for a number no longer on the record changes nothing. For 21/106, re-run the same command.
- **A refusal on any included sitting** (a parse or persist error not seen on W1's XML) stops the build before the swap. The store and the record are untouched, and the runner stops for a human. That sitting goes back on the record with `--exclude-document-number N --exclusion-reason awaiting_rule --exclusion-detail "…"`, or gets a reviewed entry, and the step re-runs.
- **The owner runs it** in their own terminal, under `caffeinate -i`: `bash ~/agent-runs/t4/run.sh`. No step runs from an agent session, by the standing rule for online fetches.

### Request budget

| Source | Estimate | Basis |
|---|---:|---|
| DIP catalog | about 50 | 48 for the first run's full fetch, then about 2 per run |
| DIP, 48 WP 18 sittings | about 250 to 330 | fresh WP 18 backfill: 982 DIP requests for 194 sittings, 5.1 each, × 1.0 to 1.3 for the longer days |
| DIP, 33 WP 19 sittings | about 270 to 360 | fresh WP 19 backfill: 1,686 for 206, 8.2 each (834 of them `/vorgang`) |
| DIP, 20/11 | about 11 | fresh WP 20: 2,345 for 213 |
| DIP, 21/106 | about 25 | fresh WP 21: 2,620 for 105; the open WP pays per Vorgang |
| DIP persons | 0, or about 40 | bulk lists valid until 2026-12-10 |
| **DIP total** | **about 600 to 800** | not 2,200: that figure was the pre-option-B 26 per sitting (`a3-pilot.md`). Phase 3 measured 5.2 per sitting with the bulk caches |
| bundestag.de list pages | about 170 | per run, to the oldest sitting's date: the fresh WP 18 runs read 73 and 62, WP 19 52, WP 20 28; 21/106 about 2 |
| bundestag.de vote pages | about 150 to 300 | 2 per vote; how many votes is unknown (the store has 0 on these dates). At the stored rate (0.77 votes per sitting in WP 18, 0.96 in WP 19) the 82 hold about 70; the long days likely hold more, so 75 to 150 votes |
| dserver XML | 83 | about 50 per 60-minute window (`XmlPacer`) |
| abgeordnetenwatch | 0 | not enabled |

**Time:** about 3.5 to 4.5 hours wall clock [estimated]. WP 18: about 1 to 1.5 h (about 70 s per sitting plus one staged rebuild of about 800 sittings). The dserver wait: 1 h. WP 19: about 1 h. WP 20 and 21/106: about 15 minutes each. The fresh build peaked at 10.2 GB maxrss for WP 21.

**DIP behaviour:** since 2026-10-24 DIP has answered runs of 450 to 1,000 requests without a block. The largest T4 run is about 400. The breaker, the request log and the 6-hour rest stay on anyway.

### Verify the run (V1 to V5)

- **V1, record:** `coverage-exclusions.json` holds exactly three entries: 18/20 `source_defect`, 18/62 and 18/90 `awaiting_rule`.
- **V2, coverage:** 801 protocols (718 + 83), 801 reports, 801 files in `data/xml/`. No v1 catalog sitting with an XML URL is missing: rerun `backfill_scope.py` on the new store, which must select none. Its 75 withheld-only sittings land in the fifth list (`withheld`), not in `acquirable`.
- **V3, the parse equals the prediction:** each fetched XML's sha256 equals W1's `xml_sha256` (82 files; 21/106 has none). `withheld_units` has 95 rows in 75 sittings: 90 `refused_nested_contribution` and 5 `reviewed`, own words 76,912 plus 21/106's. Every row has a Redner-ID. The run summary names the 95 as newly withheld (ADR 0005, D5).
- **V4, requests:** totals per host and endpoint from `requests.log`, against the budget above, in the outcome section.
- **V5, the store gate** (`validate_store_gate.py`, as in `~/agent-runs/fresh/gate.sh`, on an APFS clone with its private directory): `all_passed: true`, including `no_withheld_rede_counted`, `every_withheld_rede_has_a_redner_id` and `abweichler_count_matches_members`. This is step 8's gate run. Step 8 passes only once N8 has passed too (N8 A).

**A known false console line.** After T4 the build's incomplete report will end with "Fix: none available now; run an online update once DIP publishes the missing protocols", because the only gaps left are withheld Reden and structural vote gaps (TODOS "Withheld-Reden PRs A and B: deferred review findings", item A1). The line above it names the real remedy. It is not a T4 failure.

## Step 2: measure (TODOS step 7)

Every figure is reported old → new against `.context/dip-pulse-site.pre-t4`, with the reason the new one is right (CLAUDE.md pre-release rule). Receipts go to `docs/plans/t4-acquire/`; the figures go into an "Outcome" section of this file.

### M1. Votes against the roll-call list, date by date

1. **Per restored sitting, from its report:** `roll_call_vote_candidate_count` (the list's entries dated that day) equals the matched votes, plus `sitting_votes` for those no TOP claims. `roll_call_vote_detail_fetch_error_count` is 0, and `roll_call_scan_end` is `date_passed` (the scan reached the date, not the page budget). Today the 718 reports read 619 candidates = 619 votes, 0 fetch errors, 718 × `date_passed`.
2. **The whole list (D5).** Step 1 reads only the list entries dated on our sittings. An entry dated on a day we hold no sitting, or under a shifted date, is invisible to it. The store's vote ids run from 252 to 1037 with 167 gaps. 133 gaps fall between two stored votes with an excluded date between them, and T4 should fill them. **34 do not.** Examples: 272 and 273 sit between two votes of 2014-05-23; 568 to 570 between 2018-11-30 and 2018-12-13. None of the 34 was ever a candidate in any report. They may be ids the list never shows, or votes we miss. The way to tell is one read of the whole list (about 110 pages from bundestag.de, no DIP), comparing every entry's id and date with `votes`. It is a throwaway script under `~/agent-runs/t4/` that uses the build's own list reader; its TSV receipt is committed. After T4: every list entry from 2013-10-22 on is in `votes` or dated on 18/20, 18/62 or 18/90, and every gap left has a reason.
3. **Figures:** `votes` 619 → N, `vote_members` 425,322 → N, `agenda_item_votes` 590 → N, unlinked votes 63 → N, and by Wahlperiode (149 / 198 / 187 / 85 today). Also `agenda_item_votes.basis` (174 / 401 / 15 today).
4. **E4 re-filing:** the replay line `refile: 100 Stimmen in 55 Abstimmungen` and `vote_members` with `listed_party_id != party_id` (100 today). Kamann's and Bülow's windows (2017-12-12 to 2018-12-13) cover 19/12 to 19/68, so restored votes may add Stimmen. Each new one is checked against `docs/source-errors.md` E4's windows.
5. **Seat cross-check** (`log_seat_crosscheck`): agree / `shift_between_groups`, 606 / 0 today. **Outcomes:** `result_scope = application` (34 today), `votes.inverted`, and the persisted `application_result` and `abweichler_count` for the new votes.

### M2. TOPs restored

- `agenda_items` 7,160 → N. Per restored sitting, stored TOPs equal the XML's TOP count, 1,021 in the 82 by the offline parse. A per-sitting difference is read.
- `agenda_item_documents` (by source: `xml` / `api`), `agenda_item_politikfelder`, and the share of restored TOPs with a DIP Vorgang link, next to the same share for the 718. A clearly lower share in the 83 points at a matching gap, not at the source.
- Reden outside a TOP (18/89's 15 adopted Reden, `docs/plans/reden-outside-tops.md`).

### M3. abgeordnetenwatch match share

Re-run `scripts/measure_aw_match_share.py` on the T4 store with the **same scratch cache**, `~/agent-runs/aw-match/scratch/aw-cache.json`. Its `.answers.json` holds the 2026-11-12 answers, so only Redner-IDs new with the 83 are asked.
1. **`--offline` first** (an agent may run it): it prints the bounds and the number of requests the online run sends. Expected: a few dozen at most. The 2026-11-12 run read 1,021 Redner-IDs from 400 sittings; the 82 add speakers who spoke only on these days.
2. **Online** in the owner's terminal (abgeordnetenwatch, 2 s pace). The command is `~/agent-runs/aw-match/run.sh`'s, pointed at the T4 store. The script writes nothing under OUTPUT_DIR.
3. **Receipt** `docs/plans/t4-acquire/aw-match-share.json`, cited beside the first, `docs/plans/a3-aw-match-share.json`: M1 937 / 945 (0.9915), M2 26,251 / 26,714 Reden (0.9827), M3 flags 8 (`name_rule`), M4 11 of 11 linked. A new M3 flag is read by hand, as item 1.5 did.
4. Check TODOS "A3 item 1.5 review", item 9 first: the store must hold `mdb_zugehoerigkeiten` rows for WP 18 and 19. Without them the script falls back to the zip.

### M4. CPP-BT, per sitting

```bash
uv run --python 3.13 python -I scripts/compare_cpp_bt.py --export .context/dip-pulse-site/data/bundestag-pulse.sqlite \
  --xml-dir .context/dip-pulse-site/data/xml --cpp-bt <CPP-BT_2026-09-19 zip> --out docs/plans/t4-acquire/cpp-bt.tsv
```

Use the same CPP-BT file as the first run (SHA-256 `d40cd969…`, version 2026-09-19; check Zenodo for a newer one, and download only with the owner's OK). Expected against the first run:
- **Sittings both hold:** WP 18 194 → up to 242 (CPP-BT lists 244 of the catalog's 245), WP 19 206 → 239, WP 20 213 → 214, WP 21 94 (21/106 is newer than CPP-BT's file). CPP-BT's 8,235 ids in the sittings we excluded become shared ids, except those of 18/20, 18/62 and 18/90.
- **`ids_only_ours` stays 0.** A Rede-ID of ours missing from CPP-BT in a restored sitting is a finding.
- **Only theirs** grows by the restored sittings' § 31 declarations, the 94 withheld Reden (class `withheld`, which passes), and the presidium units of the ten ADR 0004 sittings (`in_top_presidium`). Those are read by hand and, once confirmed, added to `scripts/cpp_bt_known_differences.tsv`, as the 81 were.
- **Surname and Fraktion** on shared ids: every new pair is read, then listed or fixed.
- **Ratio rows:** read the 20 largest that fall in restored sittings.

### M5. `erste-reden` v3 and the persons with no Redner-ID record

From TODOS step 7 and `withheld-before-t4.md` A4:
1. **Withheld Reden with a partitioned Redner-ID:** expected 0, measured 0 on W1's XML. Each one would drop every sharer from the debut count.
2. **Withheld Reden whose Redner-ID no `mps` row holds:** expected 0, measured 0 against today's store. Such a Rede binds no one.
3. **Persons who have Reden but no record with a Redner-ID.** Today's store has 8 persons with 11 Reden: Unbekannt; Maika Friemann-Jennert; Peter Altmaier (filed by name and party); Mehmet Daimagüler; Judith Gerlach (2); Peter Beuth (3); Andreas Bovenschulte; Lena Kreck. Re-count on the T4 store with:

   ```sql
   SELECT m.person_id, m.display_name, COUNT(*) FROM speeches s JOIN mps m ON m.id = s.mp_id
   WHERE m.person_id NOT IN (SELECT person_id FROM mps WHERE xml_redner_id IS NOT NULL AND xml_redner_id <> '')
   GROUP BY m.person_id;
   ```

   For each person on that list, old and new, check whether a withheld Rede belongs to the same human under a Redner-ID. If one does, that person's next stored Rede would post as a false debut. No withheld speaker in the 82 carries any of the 8 names [measured on W1's XML], so none is expected. Any new person on the list is read before the gate passes.
4. **`erste-reden`** values for the weeks that hold a restored sitting, old → new. A person whose first Rede in our coverage is now in a restored sitting moves their debut earlier, or drops out when that Rede is withheld. Both are the intended correction.

### M6. Figures moved

Run `compare_store_values.py` between `.pre-t4` and the T4 store, once with `--cohort shared` and once with `--cohort all`.
- **Shared cohort:** only cross-sitting values may move: person totals, registry groupings, facts of periods that gain a sitting. Every move is named.
- **All:** protocols 718 → 801; Reden 54,855 → about 61,300 (+6,451 in the 82, plus 21/106); Beiträge; `withheld_units` 0 → 95; votes; `vote_members`; Personenseiten (1,658); Abweichungen (3,720); r3 rows (1,390); publishable facts; incomplete periods (102 weeks / 73 months).
- **Facts:** periods that held only excluded sittings had every domain `not_persisted`. After T4 their votes facts may publish, and their speech facts stay *unvollständig erfasst*, now with the note naming the withheld Reden (ADR 0005, "Facts").

### M7. Coverage by year, for N9

The export's `coverage.withheld` (`by_year`, `by_fraktion`, `by_sitting`) and DATA.md "Abdeckung nach Jahr und zurückgehaltene Reden". Today every withheld figure is 0 and 2013 holds two sittings. T4 adds 18/1, 18/2, 18/3 and 18/6 to 2013, so 2013 will show the highest share. N9 is decided: no bar on sittings, and each analysis declares a minimum coverage. **The owner sets that number from these tables**, a decision T4 hands on (D9).

## Step 3: the N8 review of the restored sittings

**Decided (N8 A, 2026-11-07):** the restored sittings get the merge and attribution review the kept sittings had in round 2 (`a3-wp18-19-round2-result.md`, "Review of what the new rules admit"). Any wrong unit goes on the reviewed list with a reason, and the gate in step 8 does not pass until the review has. It runs on W1's XML before the online run (D3, step 0.2).

**Sets** (counts from the offline parse of the 82):

| Set | Items | Read for |
|---|---:|---|
| a. Withheld Reden | 94 | The refusal is right (no rule should have admitted the turn), and the record holds the printed words and the right speaker. The 5 N7 entries are checked against their reasons |
| b. Merges | 55 `merged_zwischenfrage` (the 82's pass-1 diagnostics hold no `merged_rede` or `merged_erwiderung`; the reader confirms this from the code before relying on it) | All with question or grant wording between the turns, all spanning more than one Redner turn, and 30 random. Then round 2's search, run over the untruncated between-text of **every** merge: "Kurzintervention", "Erwiderung", "erwidern". That kind proved wrong once (18/83) |
| c. Admitted Beiträge and splits | 52 split parts; 47 `procedural`; 14 Ansprachen; Zwischenfragen, Kurzinterventionen and Erwiderungen sampled (498 / 143 / 118 in all) | Each split part: the parent Rede and the part belong to who the protocol names. Procedural turns: really Sitzungsleitung or an election acceptance. Ansprachen: the ADR 0004 kind |
| d. Attribution | 6,451 Reden | Speaker and Fraktion against the printed name: automated after T4 by M4's surname and Fraktion compare, by hand for the presidium Reden of the ten ADR 0004 sittings and for 18/89's Reden outside a TOP |

**Method.** As in round 2: Sonnet readers, one batch per set, with a brief and the source excerpts; a second pass on every "wrong" and "borderline"; the owner on each disagreement. Results go to `docs/plans/t4-acquire/n8-review.tsv` (one row per item: sitting, unit, set, verdict, reason) and a summary in the outcome section. **Pass rule:** every wrong unit is either a `withhold` entry in `reviewed_units.json` (N8 A) or a parser rule the owner approves. Every set reports right / wrong / borderline counts.

**Effort:** CC about half a day plus the owner's disagreements; human about 3 days [estimated, N8].

**If the review finds wrong units:** the entries land in one PR before the online run. If the run has already happened, they land after it, and `--offline --repersist` on the T4 store applies them; the store refuses to render until it has (ADR 0005, "The list and the store"). A withheld count above 95 is then expected and named in the outcome.

## Step 4: N10, the vote-link review with the restored sittings

`vote-links-and-figures.md` "The 85 sittings after T4" planned the 83 as an appended batch, run after the 718's review. The review has not run yet ("The review and PR C wait for the coordinating session"). So with D1 it runs **once, after T4, over all 801 sittings**:
- **The sheet:** `scripts/vote_link_review.py` on the T4 store. The whole store needs no `--protocols`, which comes only with PR C. Fix deferred items 2 and 6 of TODOS "Check that vote links are right" first: the sheet's `shared` column should mark printed numbers, and it should read evidence by `top_id` and occurrence, not `item_index`. Otherwise both reviewers get misleading evidence.
- **The sample** keeps decision 4's rules and widens them to the restored sittings. S1: every vote linked to more than one TOP. S2: every TOP with more than one vote. S3: every title link. S4: the 50 recorded plain links of the 718 plus 16% (at least 10) of the 83's plain links, with the seed recorded. The restored rows carry `batch = t4`, so the 718's figures stay comparable with the plan's 329.
- **Evidence:** protocol text and DIP caches offline. Online checks of the bundestag.de vote page only for links still unsure, with a stated count and the owner's OK (decision 5).
- **Then PR C** (pattern rules, reviewed list, oracle fixtures for every reviewed sitting including the 83, the store gate). Its replay reports old → new over all 801. Its gate makes every release refuse a vote linked to two or more TOPs without a review row (decision 6), so the 83's multi-TOP votes must be reviewed before the first release in any case.

N8 and N10 can share one batch of reader work over the restored sittings, but they keep separate sheets: N8 reads speech units, N10 reads vote-to-TOP links. N8 runs before the fetch (D3), N10 after it, because the links need DIP data.

## Step 5: the release bar

**What refuses today.** `publish_dip_pulse_data.run_release` refuses `--publish` while any `coverage.excluded` row has a reason outside `FINAL_EXCLUSION_REASONS = ("source_defect", "not_narrowable")`, the first release included. Dry runs stay allowed (#159, D6). Today 85 of 86 entries await. After T4 two do: 18/62 and 18/90.

**What clears it.** 18/20 stays `source_defect` and passes. For 18/62 and 18/90 (D4):
- **Recommended: a rule, then a two-sitting online run.** Round 2 found 5 presidium markers that print a Fraktion outside any `<rede>`, in all WP 18/19 files and only in these two sittings: Pau's Nachfragen (3 in 18/62, 1 in 18/90) and Singhammer's chair turn in 18/62. Round 2 already has an owner-approved rule for "a Vizepräsident(in)'s own Fraktionsrede printed with the presidium `rolle_lang`" (17 sittings). The rule reads such a Fragestunde Nachfrage as the MdB's question for her Fraktion, and Singhammer's turn as Sitzungsleitung, with a reviewed entry naming each of the 5 markers. Test-first, with one replay. Then `--document-number 18/62 --document-number 18/90 --include-document-number 18/62 --include-document-number 18/90 --vote-scan-pages 200 --sleep 2` (about 20 DIP requests). The two sittings bring 24 Reden and 281 Befragung and Fragestunde units, at the cost of 5 units. Round 2 kept them out when the rule was the only tool. Under ADR 0005 a parser gap no longer justifies leaving a sitting out.
- **Alternative: reclassify both as `not_narrowable`.** It is true of the current build: withholding works on `<rede>` units, and a Fragestunde turn has none. But it keeps 305 correct units out to hide 5. No CLI changes the reason of an existing entry (`update_coverage_exclusions` adds only absent numbers), so it means a hand edit of the record, reviewed in a commit.

**A gap in the bar (found here).** The release check reads only `coverage.excluded`. A v1 catalog sitting with an XML URL that is neither stored nor excluded passes `--publish`, and an interrupted `--include-document-number` run leaves exactly that, because the include drops the number before acquisition is known (step 1). T4's V2 check covers T4 itself. For every later release: refuse `--publish` while any v1 catalog sitting with XML is neither in the store nor on the record (the manifest already carries `catalog_count` and `dossier_count`), or have the include drop only sittings the run stored. A small PR before the first release (decision 6), filed in TODOS.md as "Refuse a release while a v1 sitting is neither stored nor excluded".

**What else the first release needs from T4.** The withheld list in the manifest lists all 95, and the first release has no cap (ADR 0005, D5). The release review's step 1 stops on any "Wartet auf …" reason. N8 passed (step 3). PR C's multi-TOP review gate (step 4). And step 8's gate on the final store.

## The review checklist applied to this plan

T4 is a data run, not a diff. The classes that apply are answered for the run and for the code paths it drives.

| Class | Answer |
|---|---|
| 1 Sibling path | The 83 enter by the online path only, the one path that writes the record (`update_coverage_exclusions`). `--offline` and `--fetch-xml` refuse `--include-document-number` (`parse_args`). A later reviewed-list change reaches them by `--offline --repersist`. The facts engine, the export and the release read the store and the record after the swap |
| 2 Stale beats fresh | Kept reports are not re-attributed online (step 0.1); harmless while the rule is unchanged, which is why T4 runs before PR C. The 718's cached reports were written at 28799ac; the T4 runs re-parse every stale one (`unparsed_reports`) |
| 3 Order and history | Four runs in sequence, each a full staged rebuild from every cached report. The gate's fresh vs half-then-full and replay vs fresh checks (V5) prove the result does not depend on that order |
| 5 Absent vs zero | A sitting included but not acquired is absent, not excluded: V2 and the bar gap (D6). A report without `withheld_rede_count` is unknown, not complete (ADR 0005) |
| 7 Neighbour binding | Vote ↔ TOP: N10 over all 801. Withheld Rede ↔ person: exact Redner-ID, 0 partitioned (M5) |
| 9 Input shape | The include lists are built from the record, filtered by Wahlperiode and reason, and counted (48 / 33 / 1 / 1) before the runner starts |
| 10 Interrupted run | Reports and XML are written per sitting before the rebuild. The store and record change only after the swap. A run that stops before the swap leaves the old store and the old record. One that stops after leaves the new store, with every included number off the record; the rerun's backfill takes any missing one. The dserver wait and DIP rest are wall-clock waits |
| 11 Claims | DATA.md and the Daten page regenerate from the store; no hand-written figure changes in T4. The outcome section cites store values |
| 12 Loop cost | The fresh build's maxrss was 7.8 to 10.2 GB; 801 sittings is 11% more than 718 |

**Checks no diff review replaces:** the figures replay is M6. Fresh vs incremental is V5's gate. The browser check: the Daten page coverage tables, one restored sitting's dossier, 20/11's week on the facts pages and a vote panel on a restored day, at 375 px and in dark mode.

## TODOS.md after T4

- Step 6 of the coverage gate entry: done, with the outcome figures and this file.
- Step 7: done, with M1 to M7's receipts.
- The two `erste-reden` measurements (partitioned ids, ids without an `mps` row): answered by M5.
- "Shared Redner-IDs: what the fix leaves open", item 2 (the 85 not scanned): the name check in `reconcile` scanned them during T4's rebuilds. Any shared id it found has an entry or stopped the run.
- "Check that vote links are right": the review runs over 801 sittings (step 4).
- The bar gap (decision 6): its own TODOS.md entry, closed by its PR.
- 18/62 and 18/90: the rule PR (D4), or their reclassification.

## Decisions (owner, 2026-11-15: all nine recommendations accepted)

1. **Order against the vote-link fix.** Decided: T4 before PR C, with the N10 review run once over all 801 sittings after T4. PR C first would make T4's online run refuse every kept report (step 0.1).
2. **Shape of the online run.** Decided: four runs, one per Wahlperiode by `--backfill-incomplete` (WP 20 first as the pilot, then 18, then 19 after a 60-minute dserver wait), and 21/106 by `--document-number`. Each run includes only its own sittings. Rejected: one `--document-number` run naming all 83, which reads the list pages once (about 100 fewer requests) but re-acquires every sitting on a retry after DIP stops.
3. **N8 before the fetch.** Decided: review W1's XML now, land any reviewed-list entries on main, then fetch, and check every fetched file's sha256 against W1's. Reviewing after the fetch costs an extra repersist of 801 sittings for every finding.
4. **18/62 and 18/90.** Decided: an owner-approved rule for the 5 presidium markers outside any `<rede>`, then a two-sitting online run, before the first release. Rejected: reclassifying both as `not_narrowable` by a hand edit of the record.
5. **Read the whole roll-call list once.** Decided: yes. About 110 bundestag.de pages, no DIP, in the owner's terminal, to settle the 34 vote-id gaps that no exclusion explains and to make "votes against the list, date by date" a full check, not a check on our own dates only.
6. **The bar gap.** Decided: a small PR before the first release that makes `--publish` refuse while any v1 catalog sitting with XML is neither stored nor excluded. Filed in TODOS.md, "Refuse a release while a v1 sitting is neither stored nor excluded".
7. **Raw vote pages.** Decided: do not hold T4 for "Keep the raw vote pages and DIP sitting records". That item is unspecced. The 83's vote pages can be re-fetched once it lands (2 requests per vote).
8. **Where T4 writes.** Decided: into `.context/dip-pulse-site` itself, after the schema-14 repersist and an APFS clone `.context/dip-pulse-site.pre-t4` (with its private directory) as baseline and rollback.
9. **The N9 minimum coverage.** Decided: not now. T4's M7 tables are its input. The owner sets the number per analysis afterwards.
