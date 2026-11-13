# A3 Phase 4: verify and document

Runs the steps of [a3-coverage.md](a3-coverage.md), "Phase 4: verify and document", as handed over in [a3-phase4-handoff.md](a3-phase4-handoff.md). The object is `~/agent-runs/a3/full` as built on 2026-10-28 (export commit 47649ad). `git diff 47649ad HEAD -- scripts/` is empty, so every step runs the code that built it.

`full` is not written in Phase 4. Steps 1 and 2 run on their own copies, so step 3 compares `baseline` against `full` exactly as Phase 3 left it.

## Step 1: gate, 2026-10-29 11:44–13:05 UTC (no DIP)

- **Command:** `validate_store_gate.py ~/agent-runs/a3/phase4/gate-full --today 2026-10-28`, under `/usr/bin/time -l`. `gate-full` is an APFS clone of `full`, so `full` itself stays as Phase 3 left it.
- **Receipt:** [a3-phase4-gate.json](a3-phase4-gate.json), with `$HOME` written as `~`. Logs are in `~/agent-runs/a3/phase4/gate-run.log` and `gate-scratch/*.log`.
- **Code:** the receipt reads commit 58d3a47. While the gate ran, the Daten scope line of step 5 was added to `build_dip_pulse_site.py` (committed in 5a76aa6). Gate subprocesses started after that edit render it. The edit only adds one paragraph to `database.html`: no link, no store value.
- **Result: `all_passed: false`.** 9 of the 10 checks pass. `replayed_store_groups_like_fresh` fails.

| Check | Result |
|---|---|
| `--offline --repersist` | exit 0, 716 reports, store replaced (1,650 s) |
| integrity / foreign keys | ok / 0 |
| fresh vs. half-then-full | identical fingerprint `0bb8a287…`, 4,165 persons, 481,087 bindings |
| **replayed vs. fresh, on the fresh store's bindings** | **fails: 4,168 vs. 4,165 groups** |
| unchanged replay | exit 0, store kept (same sha256, size, mtime, inode) |
| link audit | 6,750 pages, 558,408 links, 0 broken |
| export | `g-9e3ef1279dd7`, 29 files match; 716 protocols, 556 votes, 382,441 vote members |
| `--validate-publication` | passes |

Store counts are unchanged by the replay: 716 protocols, 54,718 speeches, 42,465 contributions, 556 votes, 1,908 facts (529 Fakten), 4,463 persons.

### Why the check fails (read-only diagnosis, nothing changed)

The replayed store (`gate-full`) and the fresh store (`gate-scratch/fresh`) were compared binding by binding.

1. **One person is split in the replayed store.** The fresh build joins four records into one person with 121 bindings, but the replayed store keeps them as four persons. This explains all of the 4,168 − 4,165 = 3 gap.
   - The person is Jan Krampe (formerly Jan Köstering), Die Linke, WP 21. Roll-call votes carry the Köstering URL from 2025-06-25 to 2026-07-10 and the Krampe URL from 2026-09-24 to 2026-10-15 (63 and 16 votes). Both URLs are `/biografien/` URLs of the same Wahlperiode.
   - `full` itself shows the same four persons. The split is in the store A3 built, not an artefact of the gate's replay.
   - The four records are `dip:8257` "Jan Krampe, MdB" (1 binding), `aw:178656` (41), profile `…/koestering_jan-1045564` (63) and profile `…/krampe_jan-1045564` (16).
   - The two bundestag.de profile URLs carry the same member number 1045564 and differ only in the name slug.
   - **Cause (corrected 2026-10-29, after the first report):** the URLs are not what splits him.
     - Pass 3 buckets voters by name and party, so the Köstering and Krampe voters never meet in one bucket.
     - DIP holds two person records for him: 8054 "Jan Köstering" (`aktualisiert` 2025-03-11) and 8257 "Jan Krampe" (2026-10-22, listing Köstering as an earlier name). Both are in `dip-person-cache.json`.
     - The store carries `dip:8054` forward as a roster record.
     - An in-memory rerun of `person_registry.match_rows` on `full`'s records joins all five records into one component under the current rule, once `dip:8054` is left out of the matching (stale). With `dip:8054` taking part, all five stay apart.
     - Why a replay still lets `dip:8054` take part has not been traced. That belongs with finding 2, not with the voter-link decision.
   - In `baseline`, `aw:178656` and the Köstering profile were one person. So on this store, A3 newly separates his speeches (`aw:178656`) from his roll-call votes (profile). The fresh build has the more correct grouping.
   - The replayed store does not heal: the registry carries its earlier grouping forward.
2. **295 persons hold only retired bindings.** The replayed store has 494 bindings that no fresh build produces.
   - 187 are `contribution-v1-…` ids. That is exactly the Zwischenfragen that speech rule v6 merged (1,433 → 1,246).
   - 307 are `roster-v1-…` ids of `dip:` records that the current roster inputs no longer produce. Examples: Nina Warken `dip:8131`, Philipp Amthor `dip:8154`, Jan Köstering `dip:8054`.
   - Carry-forward is by design, as in Phase 0 (10 bindings then). Here, though, it leaves 295 persons whose every binding is retired. That is why the store reports 4,463 persons against 4,165 in a fresh build.
   - 282 of these persons render an Abgeordnete page, and the index links to each of them. One example is the index entry "Jan Köstering", which links to `person-v1-6d527d…`. Its only binding is a retired roster binding. His speeches are on a different page.

The gate's own comparison excludes retired bindings, so finding 2 does not make the check fail. It is recorded because it moves the published person count and the Abgeordnete index. Neither is fixed here: both are registry behaviour, and the registry decision is still with the owner.

### Timing and memory

- Total 4,838 s (1 h 21 min). Phases:
  - repersist with render and export: 1,650 s;
  - fresh database-only persist: 724 s;
  - half: 333 s;
  - half then full: 783 s;
  - unchanged replay: 974 s;
  - publication check: 212 s.
- Memory:
  - Largest single process: 5.59 GB maxrss (`/usr/bin/time -l` reports the largest child).
  - During the first replay, the gate and its child together showed about 7 GB.
  - Phase 0 measured 2.59 GB on 290 reports, so memory grows about linearly with the store. Size a runner for at least 8 GB.
- `full` itself also has 295 orphan persons (4,463 persons).
- Disk: 19 GB free at the end. The gate scratch (7.4 GB) and `gate-full` (5.4 GB) are kept for the owner's inspection.

### Bundestag member numbers, measured for the identity decision (2026-10-29)

On `full`'s 2,148 bundestag.de voter profile records (WP 20/21; the WP 18/19 links are dropped today), with each URL's Wahlperiode taken from the dates of its votes:

- **No number is used in two Wahlperioden.** Every number votes in one WP only.
- **No person has two numbers within one Wahlperiode.** There are 0 name slugs with two numbers inside one WP.
- **A new Wahlperiode often brings a new number.** 390 name+party pairs have two numbers, a WP 20 one and a WP 21 one (Amthor 857086 / 1043428). Some numbers carry over: Akbulut's 857082 is in both his WP 19 archive link and his WP 20 link.
- **A name change keeps the number.** 5 numbers have two slugs: Köstering/Krampe, Benkstein/Lenk, Cademartori (Dujisin), (Glogowski-)Merten, Santos Firnhaber/Santos-Wintz.
- **The path does not give the Wahlperiode.** WP 20 votes link `/biografien/` (776 records) as well as `/biografien20/` (733). Only WP 21 votes are all `/biografien/` (639). Within WP 20 the same number appears under both paths (Warken 858188).

## Step 2: missing count. Purpose and cost, written before sending

- **Purpose:** a fresh DIP catalog, to judge whether any WP 18–21 sitting is still missing from `full`. WP 21 is still running, so DIP may have listed sittings since 2026-10-28.
- **How:** `~/agent-runs/a3/phase4/missing_count.py` (outside the repo). It calls the build's own `fetch_catalog` and `incomplete_sitting_protocols`, with the backfill's settings and the exclusion list. It reads `full` and writes only into `~/agent-runs/a3/phase4/`.
  - An offline dry run on the 2026-10-28 catalog gives 0 to acquire in every Wahlperiode.
- **DIP cost:** 3–4 `/plenarprotokoll` requests.
  - The cached catalog was fully fetched on 2026-10-25, within the 7-day window. So `fetch_catalog` asks DIP for its total count, then lists WP 21 fresh, and takes WP 18–20 from the cache.
  - `DIP_REQUEST_LOG=~/agent-runs/a3/phase3-requests.log`, sleep 2 s.
- **Not sent:** the ~60 Politikfelder `/vorgang` batches the handoff budgets for. They come with a full online build. They are not part of the measurement, and a build would also write the output directory.

### Step 2 result, 2026-10-29 11:48–11:49 UTC

- **DIP: 3 requests, all answered (200), no Enodia page:** the total count, then two WP 21 list pages. WP 1–20 came from the cache. Output: `~/agent-runs/a3/phase4/missing-online.{json,log}`; the fresh catalog is beside them.
- **The catalog is unchanged:** 4,680 protocols. WP 21 still lists 103 sittings; the newest is 21/103 of 2026-10-16.

| WP | catalog | with XML | stored | excluded | missing | waiting for DIP XML |
|---|---:|---:|---:|---:|---:|---:|
| 18 | 245 | 245 | 194 | 51 | 0 | 0 |
| 19 | 239 | 239 | 206 | 33 | 0 | 0 |
| 20 | 214 | 214 | 213 | 1 | 0 | 0 |
| 21 | 103 | 103 | 103 | 0 | 0 | 0 |

- **The table reads 0 missing.** The 85 excluded are the reviewed D2 list (WP 18: 51, WP 19: 33) and 20/11 (source-errors E1).
- **Not missing, but not complete either.** These 42 stored sittings are left alone by the backfill, by design:
  - **41 sittings: roll-call votes that matched no agenda item.** The backfill cannot fix these by rescanning.
    - WP 18: 14 sittings, 18/30 … 18/240.
    - WP 19: 13 sittings, 19/4 … 19/236.
    - WP 20: 9 sittings, 20/28 … 20/210.
    - WP 21: 5 sittings, 21/14, 21/37, 21/40, 21/83, 21/99.
    - The lists are the handoff's. Step 4 checks them on the site.
  - **21/103 (2026-10-16): `votes partial (source_stale)`.**
    - When it was acquired on 2026-10-28, the bundestag.de roll-call list did not reach that date yet.
    - The backfill takes it again once the sitting is more than 14 days old (`ROLL_CALL_LIST_LAG_DAYS`), from 2026-10-31. This is the one sitting that is still waiting on a source.

## Step 3: value comparison, 2026-10-29

`compare_store_values.py ~/agent-runs/a3/baseline ~/agent-runs/a3/full`, read-only (`mode=ro`), once per cohort. Reports: [a3-phase4-compare-shared.txt](a3-phase4-compare-shared.txt) and [a3-phase4-compare-all.txt](a3-phase4-compare-all.txt). Each took under a minute, at about 110 MB RSS.

- `baseline` was built 2026-10-23 on 54875da. `full` was built 2026-10-28 on 47649ad.
- Besides coverage, two things separate them:
  - speech rule v6 (d803f96);
  - re-acquired WP 20/21 sittings, which now carry vote metadata.
- The shared cohort is exactly WP 20/21: 290 protocols in both stores (WP 20: 201, WP 21: 89). 426 are only in `full`, and 0 only in `baseline`.

### `--cohort shared`: value movement on the same 290 sittings

Unchanged:
- speech characters (109,984,442);
- unattributed characters (0);
- Reden per Sprechrolle;
- every Redeanteil;
- every contribution kind except Zwischenfrage.

What moved, and why:

| Figure (WP 20/21, shared sittings) | old | new | Why |
|---|---:|---:|---|
| Zwischenfragen | 1,433 | 1,246 | Code change, not coverage: speech rule v6 (d803f96, "one Zwischenfrage per exchange, not per marker"). It was measured when Phase 3 repersisted `full` (a3-phase3.md, "`full` repersisted and gated"). |
| Votes, WP 20 | 165 | 167 | **Vote metadata now complete.** Re-acquiring a sitting with today's vote scan found roll-call votes the base reports had not attached: 20/63 1 → 2, 20/115 3 → 4. |
| Votes, WP 21 | 52 | 60 | Same reason: 21/90 0 → 8. |
| Votes with a stored result (`result_raw`) | 0 of 217 | 214 of 217 | **Vote metadata now complete.** The base reports predate the stored vote result and the inversion check. All 217 base votes are in `full` with the same yes/no/abstain/absent counts. |
| Votes with `inverted` set | 0 of 217 (all NULL) | 217 of 217; 22 inverted | Same reason. |
| `vote_fractions.leading_vote` | yes 853, no 724, abstain 65, NULL 31 | 882, 750, 67, 36 | The 10 added votes. |
| Newest vote date | 2026-06-12 | 2026-07-10 | 21/90 (2026-07-10) now has its votes. |

**Whole-store votes per WP, as the handoff expected:**
- WP 20: 165 → 171. That is +2 on shared sittings and +4 from the newly stored 20/3 and 20/7.
- WP 21: 52 → 79. That is +8 on shared sittings and +19 from new sittings: 21/86, 21/88, 21/89, 21/96, 21/97, 21/99 and 21/102.

**Fakten, on the 710 (period, metric) rows both stores hold.** The script reports "492 of 710 shared (period, metric) moved". Broken down:

| Metric group | What moved | Why |
|---|---|---|
| all eight | the percentile in 489 rows, `baseline_count` in 528 | **Fakt percentiles with a longer baseline.** The WP 20/21 baselines now include periods that were not stored before (e.g. `laengste-rede` WP 20: 67 of 68 rows have a different baseline count). |
| `knappste-abstimmung`, `meiste-abweichler` | value and denominator, in 120 rows: from none to a value in every case; no existing value changed | **Vote metadata now complete.** Per metric, 59 WP 20 and 28 WP 21 periods went from incomplete to complete, because their votes now carry acquisition metadata. |
| `laengste-debatte`, `-rede`, `-sitzung`; `aktivste-abgeordnete`, `meistdiskutierter-vorgang` | 21 rows, from none to a value: week 2022-W04 and weeks 2026-W26, W28, W39, W41; months 2026-06, -07, -09 | **Coverage.** These periods were incomplete because a sitting was missing (20/12–13, and WP 21 sittings after 2026-06). They are complete now. |
| `erste-reden` | value in 46 rows, every one lower (WP 20: 40, WP 21: 6); 5 more from none to a value | **`erste-reden` numerators that change because earlier speeches are now covered.** A first WP 20 speech is no longer "first" when the MP spoke in WP 18/19 or in 20/1–20/13. |

Largest `erste-reden` moves (old → new):
- week 2022-W07: 176 → 60;
- 2022-W11: 136 → 49;
- 2022-W12: 105 → 28;
- 2022-W14: 43 → 10.

**Publishable Fakten on shared rows: 187 → 294.**
- 110 rows became publishable, mostly periods that are complete now.
- 3 stopped being publishable, all `erste-reden`, each 4 → 1 and now `below_floor`: weeks 2023-W25, 2023-W39 and 2024-W08. In each, three of the four "first speeches" came from MPs who had already spoken in WP 18/19. The old Fakt was wrong.
- Whole store: 187 → 529 publishable.

### `--cohort all`: coverage

| | `baseline` | `full` |
|---|---:|---:|
| protocols | 290 | 716 (WP 18 194, WP 19 206, WP 20 213, WP 21 103) |
| votes | 217 | 556 (127 / 179 / 171 / 79) |
| vote members | 154,078 | 382,441 |
| speeches (Reden) | 26,267 | 54,718 |
| contributions | 16,787 | 42,465 |
| speech characters | 109,984,442 | 253,280,655 |
| agenda items | 2,912 | 7,131 |
| documents | 8,117 | 20,557 |
| persons | 4,298 | 6,687 |
| Personen after Zusammenführung | 3,127 | 4,526 |
| bills/ pages | 562 | 1,381 |
| abgeordnete/ pages | 1,039 | 2,005 |
| publishable weeks / months | 75 / 29 | 182 / 60 |
| Daten recipe r3-abweichler rows | 363 | 1,328 |

**Two whole-store oddities that do not occur in WP 20/21.** Both are errors in the source XML (source-errors E2, E3):
- **Unattributed characters: 0 → 6,180, all in 19/2.**
  - Peter Altmaier's speech as Bundesminister der Finanzen (`ID19205800`) has `<redner id="">`, an empty person id.
  - The speech is stored with Sprechrolle `bundesregierung`, but its 6,180 characters count as unattributed, and its `char_count` is 0.
- **One Rede with no Zusammenschluss: 18/104 `ID1810402200`.**
  - Christian Kühn (BÜNDNIS 90/DIE GRÜNEN) has no `<p klasse="redner">`/`<redner>` element, only a bare `<name>Christian Kühn ( Tübingen) (BÜNDNIS 90/DIE GRÜNEN) : </name>`.
  - The parser reads no Fraktion from it, so Redeanteil lists one Rede under "(ohne Zuordnung)".

**Redeanteil shares across all four Wahlperioden** move as coverage would. Example: AfD 15.4 % → 12.3 %, because the AfD entered the Bundestag only in WP 19. The site does not show one blended share: the A3 stopgap gives every whole-store figure a Wahlperiode dimension.

## Step 4: spot checks, 2026-10-29

**Setup:**
- `full` was served read-only on 127.0.0.1 and opened in Chrome, at 1280 px.
- I used the Chrome DevTools MCP, because the Claude-in-Chrome extension was not connected.
- The theme comes from localStorage `bundestag-pulse-theme`, falling back to `prefers-color-scheme`. Each page was loaded with it set.

| Page | Theme | Result |
|---|---|---|
| 18/30 dossier | light, dark | Renders in both. The notice says roll-call votes were found that match no TOP. Two defects: "verteilt am" with no date, and Drucksachen 0 (below). |
| 19/29 dossier | dark | Renders. The notice says "1 von 4 namentlichen Abstimmungen … passten … zu keinem TOP". 3 votes are listed. Drucksachen 0. |
| Joachim Poß (`abgeordnete/p-004843.html`), WP 18 only | light | Renders: SPD, 6 Reden, 117 roll-call votes, Wahlperioden 18. The vote column overflows by 24 px (below). |
| `votes/index.html` | dark | Renders: 556 votes, months from Oktober 2026 back to Februar 2014, no overflow. It has no Wahlperiode filter (TODOS D8/D9 cover the overview and MP pages, not this archive). |
| Daten (`database.html`) | light | Renders. Manifest range "18/4 bis 21/103 · 2013-12-17 bis 2026-10-16". Every whole-store recipe says "Je Wahlperiode gezählt". |
| `overview.html` | dark | Catalog chips for WP 1–21, 716 dossiers, 1,381 Gesetzesvorhaben. The "Neueste API-Sitzung" card is unreadable in dark (below). |

### Findings

1. **Bundesrat members are counted as MdBs (P1, data).**
   - **Cause:** `_has_mdb_funktion` (`scripts/build_dip_pulse_site.py:7526`) tests `"mdb" in value.lower()`. That also matches DIP's `MdBR` and `Stellv. MdBR`. The test is from #33.
   - **Why it shows only now:** `baseline` has no roster rows, so A3 is the first build to ingest WP 18–21.
   - **The roster figure:** the Phase 3 figure "1,712 MdBs among 3,724 DIP persons" is 1,360 persons with role `MdB` plus 352 Bundesrat members (`MdBR` 158, `Stellv. MdBR` 194). All 352 are `is_mdb = 1`.
   - **What the site shows:** the Abgeordnete index lists them as MdBs.
     - Of 972 "former MdB" rows, 201 have no Fraktion, e.g. "Albert Füracker, Stellv. MdBR (Staatsminister …), Bayern" and Volker Bouffier.
     - Of the 740 current-MdB rows, at least 84 carry "MdBR" in the name. The store tags 151 Bundesrat persons with WP 21, against 589 MdB-role persons.
   - **Not fixed here.** It is a code change with its own old/new report, like the identity finding. It is in TODOS.
2. **The roll-call votes that matched no TOP are not on the site, though they are fetched (P1, bug).**
   - All 63 vote ids in the backfill warnings are absent from the store (WP 18: 22, WP 19: 19, WP 20: 16, WP 21: 6). Examples: 261 EUFOR RCA, 275 KFOR, 489 IS, 510 MINUSMA, 662 Hinweisgeber, 1008 Jahresemissionsgesamtmengen-Verordnung, 1034 Schienenausbaustrecke Hannover–Hamburg.
   - No page shows or links them. The only trace is the dossier notice, which gives a count and no titles.
   - **Cause:** `enrich_with_api` puts the fetched unmatched votes into both `api_records.sitting_votes` and its own `sitting_votes`. But the report dict assembled at `scripts/validate_dip_protocol.py:3520` never copies `enrichment["sitting_votes"]`. Persist and render read the top-level `report["sitting_votes"]`, so the votes are dropped.
     - In `full`: 63 votes sit in `api_records.sitting_votes` of the 41 cached reports, and 0 in `sitting_votes`.
     - In `baseline`: 0 in either. Its reports predate the field.
   - TODOS "Match roll-call votes to a TOP when Drucksache numbers fail" is marked completed in v0.10.0.0 ("They appear under 'TOP nicht zugeordnet'"). No commit ever wired the key into the report, so that section has never shown a vote.
   - **A fix needs no new requests.** The full vote details are in the cached reports. It is one copied key plus an offline repersist, and it would add up to 63 votes (556 → at most 619; unmeasured).
   - Not fixed here (a code change, after Phase 4).
3. **The "Drucksachen" card counts only Drucksachen tagged in the XML** (`validation_summary.xml_drucksache_count`).
   - It reads 0 on all 194 WP 18 and 206 WP 19 dossiers, and on 118 of 213 WP 20 dossiers. That includes 19/29, whose agenda items link 37 documents through DIP.
   - Pre-existing (20/100 reads 0 in `baseline` too), but WP 18/19 make it the common case.
4. **WP 18 dossiers print "verteilt am" with nothing after it.** DIP lists no `verteildatum` for any WP 18 sitting (194 of 194 empty in the store). WP 19+ have one.
5. **`overview.html`, dark: the "Neueste API-Sitzung" card keeps `background:white`.** The rule is hard-coded at `scripts/build_dip_pulse_site.py:9928` (also 9440, 10398), so the light text on it is close to invisible. Pre-existing.
6. **Profile vote column overflow.** Single-word titles such as "Asylverfahrensbeschleunigungsgesetz" push the right-hand column 24 px past the viewport at 1280 px, so the page scrolls sideways. Pre-existing CSS (no `overflow-wrap`); WP 18 titles bring it out.

### Size

| | `baseline` | `full` |
|---|---:|---:|
| output dir | 2.3 GB | 5.4 GB |
| `data/` (store, XML, caches, exports) | 1.7 GB | 4.1 GB |
| SQLite store | 359 MB | 848 MB |
| `data/exports` | 178 MB | 426 MB |
| Download in the export: `.sqlite.gz` | — | 240.3 MB packed, 804.0 MB unpacked |
| rendered pages (output dir without `data/`) | 616 MB | 1,351 MB |
| HTML files outside `data/` | 3,290 | 6,750 |
| `protocols/` | 240 MB | 519 MB |
| `bills/` | 299 MB | 664 MB |
| `abgeordnete/` | 57 MB | 139 MB |

## Step 5: docs, 2026-10-29

- **README:** a "Covered range (v1)" paragraph under the intro gives the per-WP counts and why the 85 are excluded.
- **PRODUCT.md:80** ("Evidence on Hand") now names the A3 store: 716 Sitzungen, 18/4 to 21/103, 556 Abstimmungen, 0 missing.
- **Daten page:** `render_daten_datenstand` prints a static scope line above the coverage line: "Umfang (v1): jede Sitzung ab der 18. Wahlperiode, für die der DIP-Katalog ein XML-Protokoll führt …".
  - It is built from `V1_FIRST_WAHLPERIODE`, beside the manifest range ("18/4 bis 21/103 · …").
  - New test: `test_datenstand_states_the_v1_scope`. Full suite: 1,626 tests, OK (2 skipped).
  - `full` was not re-rendered, so its `database.html` does not have the line yet. It appears on the next build.
- **TODOS:**
  - A3 moved to Completed with the measured table, and roadmap item A3 marked done.
  - The hosting item has the post-A3 sizes.
  - Four new items from step 4:
    - unmatched roll-call votes never reach the report (P1);
    - Bundesrat members ingested as MdBs (P1);
    - the dossier header's Drucksachen card and empty "verteilt am" (P2);
    - dark-mode card and profile overflow (P3).
- **source-errors.md:** E2 (19/2, empty person id) and E3 (18/104, no `<redner>` element), both verified with quotes.
- **CONTEXT.md:** unchanged, since no term changed.

## Identity rule C: member numbers, conflicting only within one Wahlperiode (owner decision 2026-10-29)

The owner chose option C from the step 6 report.

- **Rule:** committed in 415a8a6, with tests.
  - Pass 3 now compares bundestag.de voter links (`/biografien/`, `/biografien20/`, `/redirect/<n>`) by their member number.
  - Two voters conflict only when they hold different numbers in one Wahlperiode of their roll calls. The Wahlperiode comes from `protocols.document_number`.
  - WP 19 web-archive links are no evidence: 449 of the 731 pilot members are linked under two numbers.
  - Other links compare as before.
- **Premises measured beforehand (offline):**
  - WP 20/21, 2,148 voter links: no number spans two Wahlperioden, and no member has two numbers in one.
  - WP 18 `/redirect/N`, 642 pilot members: no member has two numbers, and no number appears in WP 19.
- **CONTEXT.md:** the Namensabgleich entry names the rule ("two biography numbers in one Wahlperiode"). `docs/stable-ids.md` follows.

### Measurement: fresh `--persist-only` stores, old code against new (2026-10-29 22:12–23:59 UTC, no requests)

Fresh stores were used, so the carried-forward registry (Step 1, finding 2) is kept out of the comparison. Every pair shares all of its bindings, so joins and splits are traced occurrence by occurrence. Raw output: [a3-rule-c-diff.txt](a3-rule-c-diff.txt).

| Store | Code | Persons | Voter-only persons | Persons with a DIP roster record |
|---|---|---:|---:|---:|
| `full` | old rule | 4,165 | 2,306 | 1,561 |
| `full` | rule C | **1,942** | **83** | 1,561 |
| pilot | old rule | 4,066 | 2,507 | 1,345 |
| pilot | old rule + link patch | 4,645 | 3,086 | 1,345 |
| pilot | rule C | 1,830 | — | — |
| pilot | rule C + link patch | 1,872 | 313 | 1,345 |

- **Why so many persons move (4,165 → 1,942 on `full`).**
  - Under the old rule, a name+party bucket holding an MdB's WP 20 and WP 21 voter records (two numbers) was ambiguous. So none of its voters attached, not even the WP 18/19 name+party voters.
  - On `full`, 722 persons of rule C each absorb several old persons, 2,947 old persons in all. Examples: Lauterbach, Mihalic and Hofreiter each go from 6 records in 6 persons to 1 person.
  - The 2,306 voter-only persons were mostly real MdBs whose votes sat on a separate page from their speeches and biography.
- **Why the new count is more correct, and what guards against wrong joins.**
  - The number of persons holding a DIP roster record stays at 1,561, so no two roster MdBs were merged.
  - No person holds two DIP ids or two trusted abgeordnetenwatch ids, before or after.
  - No name+party bucket on `full` holds two different DIP ids. So the WP 18–21 roster has no same-name, same-party MdB pair that the looser rule could merge.
  - The remaining risk is a namesake who has no roster or speaker record of their own. They would join the one anchor of their name and party. The roster covers every MdB of WP 18–21, so this is limited to voters the roster misses.
- **Splits on `full`: 2 old persons.** Both are party switchers: Melis Sekmen (Greens → CDU/CSU) and Jan Wenzel Schmidt (AfD → fraktionslos).
  - Neither is whole before or after: Sekmen 4 → 3 persons, Schmidt 5 → 3.
  - Larger groups now reach pass 3's all-or-none check for switchers (TODOS, A.2 follow-ups (6)).
- **Voter records per Wahlperiode** are unchanged by the rule (711 / 761 / 1,558 / 639). The rule changes grouping, not keys.
- **Run cost:** fresh persist of `full` 857–887 s, max RSS 2.8–3.2 GB; pilot 284–345 s.

### The voter-link patch (not applied)

`full`'s reports were written after #107 dropped the WP 18/19 links, so the patch changes nothing on `full` until the WP 18/19 roll-call lists are fetched again.

- **Hybrid measurement:** a `full` clone with the pilot's 5 linked reports (18/154, 18/200, 18/244, 19/200, 19/238), rule C plus the patch, against `full` with rule C.
  - Persons 1,942 → 1,956 (+14): 16 persons split, 2 join (Fabritius and Weiler: their WP 18 title variants become one record).
  - WP 18 voter records go 711 → 1,350, because those 5 reports key WP 18 members by `/redirect/N` while every other WP 18 report still keys them by name+party.
  - Every split is such a pair without a speaker or roster anchor: Lammert, Bulmahn, Erler, von der Leyen, Warken (WP 18), and others. Pass 3 never joins two voters to each other.
- **What a full refetch would change:** a store with every WP 18 roll call fetched again would key each WP 18 member by one redirect record, so the hybrid's mixed state, and most of its splits, would not exist. Its result can only be measured after that refetch.
- **Cost:** about 306 roll-call lists (WP 18 127, WP 19 179) from bundestag.de.
- **Gain:**
  - WP 18/19 voter pages link to the archived biography;
  - WP 18 title variants become one voter record;
  - WP 19 is otherwise unchanged (archive links key nothing).

`full` itself was not repersisted with rule C. Phase 4 does not write it, so the rule reaches the store on its next build.

## Gate at the branch tip, 2026-10-31 (no DIP, partial)

The gate was run again on a fresh APFS clone of `full` (`~/agent-runs/a3/phase4/gate-tip`) at commit 7238045. That tip holds rule C (415a8a6), the exact MdB rule (9d05427), the replay fixes 0f59729 and a508cfa, and main up to v0.23.7.0. The command was `validate_store_gate.py … --today 2026-10-28`, run by `~/agent-runs/a3/phase4/gate-tip.sh`. `full` was not written.

- **Stopped early.** At 16:30 UTC the disk watchdog stopped the gate at 3 GB free, during the half-then-full replay. Other worktrees were using the same disk.
- **Steps that finished:**
  - replay: `--offline --repersist`, 716 reports, site rendered;
  - fresh persist-only.
- **Steps not run:**
  - half-then-full;
  - unchanged replay;
  - link audit;
  - export;
  - `--validate-publication`.
- **No receipt was written.** The replay-against-fresh check was computed separately, with the gate's own `grouping_fingerprint` and `binding_ids`.
- **Before shipping,** the merged tree needs a full gate run.

| Figure | Phase 4 (`full`, 2026-10-29) | Tip (2026-10-31) |
|---|---:|---:|
| `replayed_store_groups_like_fresh` | fails: 4,168 vs. 4,165 | **passes:** 1,942 = 1,942, fingerprint `f0c2d7d9…` |
| Persons, fresh store | 4,165 | 1,942 |
| Persons, replayed store | 4,463 | 2,244 |
| Bindings, fresh | 481,087 | 523,968 |
| Retired bindings (roster / contribution) | 494 (307 / 187) | 494 (307 / 187) |
| Persons holding only retired bindings | 295 | 302 |
| … of them with a rendered page | 282 | 289 |
| … of them linked from the Abgeordnete index | 282 | **8** |
| `mps` rows with `is_mdb = 1` | 1,712 | **1,360** |
| Index section "Frühere Abgeordnete" | 972 | 771 |
| Index links | 1,712 | 1,653 |
| Person pages (non-redirect) | 2,005 | 2,005 |
| Votes in the Abstimmungen archive | 556 | 619 |
| SQLite integrity / foreign-key violations | ok / 0 | ok / 0 (both stores) |

What each change does:

- **Fresh grouping (1,942):**
  - It equals the rule-C measurement at 415a8a6 (`rule-c/runs/full-new`), so 9d05427, 0f59729 and a508cfa leave fresh grouping unchanged.
  - The fresh store has 42,881 more bindings: 63 more votes are kept after main's merges, and the archive grows from 556 to 619 (the TODO "63 votes in 41 sittings are fetched and then dropped").
- **Replayed equals fresh on live bindings.** The replayed store no longer holds a grouping that a fresh build would not make.
- **Köstering/Krampe (part 1 of the registry TODO): healed.**
  - The replayed store holds him as one live person, `p-001037`, with 5 records: `dip:8257`, `aw:178656`, `xml:11005511` and both bundestag.de profiles.
  - The retired roster record `dip:8054` "Jan Köstering" sits alone on `person-v1-6d527d…`. Its page still renders (0 Reden, 0 Abstimmungen) but is no longer linked from the index.
- **Bundesrat (9d05427):**
  - The repersist alone drops the 352 Bundesrat roster rows (1,712 → 1,360); no roster refetch was needed.
  - "Frühere Abgeordnete" goes from 972 to 771 (−201, the 201 rows without a Fraktion found in step 4).
- **Retired-only persons (part 2 of the registry TODO): still open, and changed in kind.**
  - 281 of the 302 are Bundesrat members (`display_name` contains "MdBR"); the rest are retired roster records such as `dip:8054`.
  - 289 still render a page with no Reden and no votes, e.g. "Tilo Kummer, Stellv. MdBR (…), Thüringen".
  - Only 8 are linked from the index, so the pages can be reached only by a direct URL.
  - The TODO "Registry `ever_mdb` evidence still marks 151 Bundesrat members as former MdBs" is the likely cause.
- **Roster refetch not run.** The Bundesrat effect is measured without it, so the ~101 DIP requests it would cost are not spent.
- **Tools:**
  - count script: `~/agent-runs/a3/phase4/registry_counts.py`, read-only; it reproduces the Phase 4 figures 295 and 282 on `full`;
  - logs: `gate-tip-run.log` and `gate-tip-scratch/*.log`.

## Gate on the merged tree, 2026-10-31/11-01 (no DIP, complete)

`origin/main` at 265e407 (v0.26.0.0: #120, #121, #122, #123) was merged into the branch as 09b7c5d.
- **Owner decisions at the merge:**
  - recipe r3 groups per person, Wahlperiode and Fraktion;
  - export format 11 (main's 10 is the codebook layout, 11 adds the recipes' `wahlperiode` column).
- **Command:** `validate_store_gate.py ~/agent-runs/a3/phase4/gate-merged --receipt … --scratch … --today 2026-10-28`, run by `~/agent-runs/a3/phase4/gate-merged.sh`.
  - The script is a copy of `gate-tip.sh`. Only the output, scratch, log and receipt names differ.
  - It ran on a fresh APFS clone of `full`; `full` was not written.
- **Receipt:** [a3-merged-gate.json](a3-merged-gate.json), with `$HOME` written as `~`.
- **Result: `all_passed: true`.** All 11 checks pass.

| Step | Result |
|---|---|
| `--offline --repersist` | exit 0, 716 reports, store replaced (3,640 s) |
| integrity / foreign keys | ok / 0 |
| fresh vs. half-then-full | identical fingerprint `f0c2d7d9…`, 1,942 persons, 523,968 bindings |
| replayed vs. fresh, on the fresh store's bindings | **passes:** 1,942 = 1,942, the same fingerprint |
| unchanged replay | exit 0, store kept (same sha256, size, mtime, inode) |
| link audit | 8,970 pages, 874,930 links, 0 broken |
| export | `g-b7fae38b7bfa`, format 11, 37 files match; 716 protocols, 619 votes, 425,322 vote members |
| `--validate-publication` | passes |

- **Timing:** 8,466 s in total (2 h 21 min). Largest process 4.8 GB maxrss.
- **Disk:** 47 GB free at the start, 30 GB at the end. The watchdog never came near its 4 GB limit.

### Against the tip table

| Figure | Tip (2026-10-31) | Merged tree | |
|---|---:|---:|---|
| `replayed_store_groups_like_fresh` | passes: 1,942 = 1,942 | passes: 1,942 = 1,942 | same fingerprint `f0c2d7d9…` |
| Persons, fresh store | 1,942 | 1,942 | |
| Persons, replayed store | 2,244 | 2,244 | |
| Bindings, fresh | 523,968 | 523,968 | |
| Retired bindings (roster / contribution) | 494 (307 / 187) | 494 (307 / 187) | |
| Persons holding only retired bindings | 302 | 302 | |
| … of them with a rendered page | 289 | 289 | |
| … of them linked from the Abgeordnete index | 8 | 8 | |
| `mps` rows with `is_mdb = 1` | 1,360 | 1,360 | |
| Index section "Frühere Abgeordnete" | 771 | 771 | |
| Index links | 1,653 | 1,653 | |
| Person pages (non-redirect) | 2,005 | 2,005 | |
| Votes in the Abstimmungen archive | 619 | 619 | |
| SQLite integrity / foreign-key violations | ok / 0 | ok / 0 | |

**No tip figure moves.** main's merges from v0.24.1.0 to v0.26.0.0 leave identity, the roster and the vote archive as they were. Köstering/Krampe stays healed: `p-001037` holds 5 records, and the retired `dip:8054` sits alone. `registry_counts.py` reproduces every registry row.

### Figures the tip did not record (against `full`, Phase 4)

The tip gate stopped before the link audit and the export and recorded no Fakten, so these are compared with `full` as Phase 4 measured it.

| Figure | `full` (Phase 4) | Merged tree | Why |
|---|---:|---:|---|
| Votes / vote members | 556 / 382,441 | 619 / 425,322 | The 63 roll-call votes that matched no TOP are now kept, through main's merges up to v0.23.7.0 (already at the tip: 619 in the archive). |
| Documents | 20,557 | 20,596 | +39, all linked only to those 63 votes. |
| Publishable Fakten | 529 | 530 | Metric version 3 of `meistdiskutierter-vorgang` (v0.24.1.0, in the branch since 7238045): a TOP counts only when it debates exactly one Vorgang. 44 monthly rows change value; 12 become publishable and 11 stop, mostly `below_floor` (e.g. 2025-03: 63 → 4 Reden under the one-Vorgang rule). No other metric moves; 35 more rows change only their percentile. |
| Pages in the link audit | 6,750 | 8,970 | +2,219 redirect pages under `abgeordnete/` (4,443 against 2,224): every person rule C folded into another keeps its old URL as a redirect. +1 `bundestag.html`, from main. |
| Export files | 29 | 37 | Format 10/11: 1 SQLite, 29 table CSVs, 6 recipe CSVs and `DATA.md` (#121). |
| Recipes | pooled | per Wahlperiode | Format 11: every recipe carries `wahlperiode`. With `LIMIT 5` and the newest WP first, r1, r2, r3, r5 and r6 show WP 21; r4 ranks across all WPs, and its top row is 20/209 (348:344). |

**Extractor 9 moves nothing on this store** (the handoff expected the `forderung` passages and the 196/217 description count to move). The A3 store has no Drucksache text cache (`data/dip-drucksache-text-cache.json.gz` is absent from `full`):
- every `documents.forderung` is empty and `vote_passages` holds 0 rows;
- `votes.passage_state` is `not_applicable` for 505 votes and `not_fetched` for 114 (WP 19: 15, WP 20: 63, WP 21: 36).

So no vote panel on the A3 site quotes an Antrag passage. Filling the cache is an online B4 stage with DIP requests, and needs the owner's go. The extractor change itself is covered by #122's tests and offline corpus.

### Kept

`~/agent-runs/a3/phase4/gate-merged` (the replayed clone) and `gate-merged-scratch` are kept for the owner's inspection: 5.6 GB and 7.5 GB by `du` (the clone shares unchanged blocks with `full`, so less is actually used). Delete them only with the owner's OK.

## Fresh reference store on main 28799ac, 2026-11-10 to 11-12 (online)

This store replaces `~/agent-runs/a3/full` as the reference store. `full` was never moved to the machine set up on 2026-11-09, so the repersist planned in [e4-repersist.md](e4-repersist.md) did not run. The owner built a new store online instead, from main at 28799ac. Its data equals v0.36.0.0, because #144 and #145 are docs only. So it holds #138 (E4), #140, #141 and #143 by construction.

- **Where:** `.context/dip-pulse-site` in the main checkout (5.5 GB; the SQLite store is 885 MB). Its private directory `.context/.dip-pulse-site.private` holds the MdB-Stammdaten zip: VERSION 1777449783, Stand 29.04.2026, sha256 `29ae4ba1…68bde460`, fetched 2026-11-10. This is the Stand every E4 figure was measured with. The 290-Sitzungen store that had this path on the old machine is retired (decision D7).
- **Recipe:** `~/agent-runs/fresh/run.sh`, which follows steps 3 to 4.6 of [a3-phase3.md](a3-phase3.md): catalog and exclusions, bulk prefetch, backfill per Wahlperiode, then `--enrich mp-roster`. 21/106 was added to the exclusion list during step 5 (TODOS.md, "Coverage gate before the first data release"). Logs are in `~/agent-runs/fresh/logs/`, about 12,200 lines in `requests.log`.
- **Interpreter:** uv's CPython 3.13.18.
- **Revision:** the export manifest records `28799ac90af8-dirty-c595c5e5`, so tracked files in the main checkout differed from 28799ac when the export ran. Its codebook inputs (`data_dictionary.json`, `data-methods.md`) have the same sha256 as at 28799ac. What differed is not recorded. The owner should confirm it was docs only, for example the TODOS.md lines #146 committed later that day.
- **Backfill time:**
  - WP 18: two runs. The first lost 45 sittings to a DNS outage while the Mac slept; the re-run fetched them in 662 s.
  - WP 19: 19,250 s.
  - WP 20: 21,039 s, 8.0 GB maxrss.
  - WP 21: 14,044 s, 10.2 GB maxrss.
  - Roster: 283 s.

### Gate, 2026-11-12 15:24–15:47 UTC (no DIP)

- **Command:** `~/agent-runs/fresh/gate.sh`, which runs `validate_store_gate.py` with `--today 2026-11-12` on an APFS clone of the store and of its private directory. The clone therefore had the Stammdaten.
- **Receipt:** [fresh-store-gate.json](fresh-store-gate.json), with `$HOME` written as `~`.
- **Result: `all_passed: true`.** All 11 checks pass. `replay.log` has `refile: 100 Stimmen in 55 Abstimmungen from the MdB-Stammdaten`. It has no `warning: [refile]` and no `keine Sitzzahlen` line. The only Redner-ID lines are the known `11005217 999990074` merged record in 21/18 to 21/45, which is used, not refused. The `fresh` and `half` clones warn that they have no Stammdaten, as designed (TODOS.md, "E4 /gstack-review: deferred findings", item 5).

| Step | Result |
|---|---|
| `--offline --repersist` | exit 0, 718 reports, store replaced (356 s) |
| integrity / foreign keys | ok / 0 |
| fresh vs. half-then-full | identical fingerprint `9326f153…`, 1,948 persons, 524,446 bindings |
| replayed vs. fresh, on the fresh store's bindings | passes: 1,948 = 1,948, the same fingerprint |
| unchanged replay | exit 0, store kept (same sha256, size, mtime, inode) |
| link audit | 8,626 pages, 880,627 links, 0 broken |
| export | `g-d3c392383c24`, format 16, schema 11, 41 files match; 718 protocols, 619 votes, 425,322 vote members |
| `--validate-publication` | passes |

- **Timing:** 1,355 s in total. The largest process used 7.8 GB maxrss. The machine is an M5 Pro, so these times can't be compared with the 8,466 s of the merged-tree gate above.

### Reconciliation against the recorded figures (read-only, 2026-11-12)

The queries ran on the store itself, opened with `mode=ro`. The A3 store ended at 21/103. This store also holds 21/104 and 21/105, dated 2026-11-04 and 2026-11-05. So each per-sitting figure is given on the 716 sittings both stores hold and on all 718. No roll-call vote falls in those two sittings: the newest vote is dated 2026-10-15.

| Figure | Recorded | Fresh, 716 shared | Fresh, all 718 | Source of the record |
|---|---:|---:|---:|---|
| Reden | 54,747 | **54,747** | 54,937 | #143 |
| Beiträge | 42,484 | **42,484** | 42,724 | #143 |
| zu Protokoll / Zwischenfragen | 3,342 / 3,061 | **3,342 / 3,061** | 3,345 / 3,085 | #143 |
| agenda items / Politikfeld rows | 7,135 / 11,465 | **7,135 / 11,465** | 7,160 / 11,509 | #143 |
| Reden per Fraktion: CDU/CSU, SPD, Grüne, Linke | 14,963, 11,620, 7,643, 5,616 | **the same** | 15,014, 11,652, 7,670, 5,639 | #143 |
| `speeches.char_count` sum | 253,528,378 | **253,528,378** | 254,296,521 | #143 |
| 18/49, 18/44 Reden; 18/133, 18/134 zu Protokoll | 51, 44; 32, 11 | **51, 44; 33, 11** | | #143; see below |
| speech rule version 7 | 716 of 716 | | 718 of 718 | #143 |
| votes / vote members | 619 / 425,322 | | **619 / 425,322** | merged gate, E4 |
| E4 moves: Stimmen / roll-calls | 100 / 55 | | **100 / 55** | E4 |
| `vote_members` with `listed_party_id` ≠ `party_id` | 100 | | **100** (and 100 non-NULL in all) | E4 |
| `vote_fractions` rows that differ from the page | 146 | | **146**, the committed TSV byte for byte | E4 |
| Abweichungen / r3 rows | 3,720 / 1,390 | | **3,720 / 1,390** | E4 |
| seat cross-check: agree / `shift_between_groups` | 606 / 0 | | **606 / 0** | E4 |
| names with no Stammdaten match: none / only another WP | 27 names, 3,073 rows / 10, 927 | | **the same** | TODOS.md, "E4 re-filing", item 2 |
| `votes.inverted` = 1 | 95 | | **95**; 638, 695, 774, 777, 801, 990 among them | #140 |
| `result_scope = application` | 24 | | **34**: does not match | #140 |
| vote 990 `result_scope` | proposition | | **proposition** | #140 |
| #141 per person (Reden, Beiträge, Stimmen) | `shared-redner-ids-old-new.tsv`, rows `neu` | **all 15 rows equal** | equal | #141 |
| `erste-reden` 2014-W23, 2015-W12, 2022-W11, 2022-W27, 2023-W50 | 26, 2, 50, 2, 1 | | **26, 2, 50, 2, 1** | #141 |

How each row was checked:
- **E4, by group.** The script rebuilt `e4-refiled-votes-old-new.tsv` over all 619 votes. The old columns are the page's own rows, `derive.merge_fractions` on the cached reports' `fractions`, with `derive.majority_vote` for the Mehrheit. The new columns are `vote_fractions`. A row is written wherever the two differ. `diff` against the committed file is empty.
- **E4, by member.** `vote_members` joined to `mps` where `listed_party_id IS NOT party_id`, with the group named in each direction:
  - Kamann, 38, fraktionslos → AfD, 2017-12-12 to 2018-12-13;
  - Bülow, 36, fraktionslos → SPD, 2017-12-12 to 2018-11-23;
  - Pasemann, 10, AfD → fraktionslos, 2020-11-18 to 2020-12-11;
  - Witt and Huber, 7 each, fraktionslos → AfD, votes 750–754 and 756–757;
  - Heßenkemper, 2, fraktionslos → AfD, votes 753–754.

  That is 100, with no other name, and matches `docs/source-errors.md` E4 window by window.
- **Unmatched names:** `derive.person_name_key` through `derive.refiling_source`, the build's own lookup, over every member row of the cached reports.
- **#141:** the person's `mps` rows grouped by `person_id`, by name, on the 716 sittings and on all 718. The two new sittings add nothing to these 15 rows. Person ids are issued anew, as expected. The records column has no `aw:` ids because this build ran no `--enrich aw-profiles` (A3 plan item 1.5).
- **18/133 zu Protokoll: 33, not a mismatch.** #143's 27 → 32 is the sum of its four Fraktion columns (`reden-outside-tops.md`: CDU/CSU 10, SPD 8, Grüne 7, Linke 7). The fresh store has the same 32, plus Iris Gleicke's submission. She speaks with no Fraktion, so none of those columns counts her. The totals match the record too: 3,342 `zu_protokoll` on the 716, and a `speeches.char_count` sum of 253,528,378, which equals #143's new value.

**Finding: `result_scope = application` is 34, not 24.** The scope is read when the roll-call detail page is fetched (`validate_dip_protocol.official_vote_result`). A replay keeps it. This store fetched every page afresh, while the A3 store's reports were older. The 34 are 710, 712, 750, 753, 754, 760, 763, 768–771, 780–782, 802, 813, 842, 846, 848, 849, 851, 864, 865, 870, 877, 878, 891, 900, 919, 921, 938, 981, 996 and 1011.
- In 33 of the 34, the official word agrees with the Ja or Nein majority.
- 996 reads "rejected" on a Ja majority. It is an inverted Beschlussempfehlung to reject ("Ablehnung eines Antrags zur Reform der Einbürgerungspolitik"), so the word is right. It is a second such vote beside 990, whose box gave the right word.

Without the old store it is unknown which 10 are new, and whether bundestag.de changed its pages or the old reports predated the scope rule. `docs/source-errors.md` E6's scale sentence is dated to the A3 store. TODOS.md, "Vote direction: what the 2026-11-07 fix left open", records the open question.

### Registry and site figures: a fresh build has no carried-forward history

These figures depend on the registry the A3 store carried forward from earlier builds, so they are re-measured here, not matched:

| Figure | A3 lineage (record) | Fresh store |
|---|---:|---:|
| `mps` rows | 7,451 (#141) | 6,387 |
| `persons` in the store (distinct `person_records.person_id`) | 2,244 (merged gate) | 1,952; 1,956 after the gate's replay |
| persons on fresh bindings | 1,942 | 1,948 |
| bindings of retired occurrences | 494 | 13 |
| Personen after Zusammenführung (`compare_store_values`) | 2,287 (#141) | 2,042 |
| Personenseiten (non-redirect, `abgeordnete/`) | 1,999 (#141) | 1,661; 4,435 redirect pages |
| pages / links in the link audit | 8,970 / 874,930 | 8,626 / 880,627 |
| documents | 20,596 | 20,678 |
| Fakten rows / publishable | 1,908 / 530 | 1,922 / 532 |
| export files | 37 (format 11) | 41 (format 16) |
| `vote_passages` / votes with an extracted passage | 0 / 0 (no Drucksache text cache) | 104 / 88 |

The gate's replay raises `persons` from 1,952 to 1,956, while grouping on fresh bindings stays 1,948 on both sides. That belongs to "The carried-forward registry diverges from a fresh build after A3" and to the registry-split plan (`docs/plans/registry-split-koestering-krampe.md`), not to E4.

Not re-measured: `docs/stable-ids.md`'s "five ids out of 2,364 records with a Redner-ID". That count was taken on the A3 store's registry, and this store's reconcile passed with the five reviewed entries in place.

## Plan item 1.5: abgeordnetenwatch match share (2026-11-12)

Plan: [a3-item-1-5-aw-match-share.md](a3-item-1-5-aw-match-share.md). Receipt: [a3-aw-match-share.json](a3-aw-match-share.json), with `$HOME` written as `~` and every review verdict.

- **Object:** an APFS clone (`~/agent-runs/aw-match/site`, with `.site.private`) of the fresh online store built on 28799ac (`.context/dip-pulse-site`): 400 WP 18/19 sittings (194 + 206), 0 of them excluded by the record, all 400 re-parsed from their cached XML. Store sha256 `aa245957…`, the same as the reference store's; nothing under the clone or the reference was written (`find -newer` is empty, the sha256 is unchanged).
- **Code:** the requests were sent by bb5519c (`scripts/measure_aw_match_share.py`, `lookup_ext_id` and the `_request` fix; run before a rebase onto v0.37.0.0, under an id that no longer exists, with the same four files). The receipt was then regenerated on 0641dc6, the review and ship fixes on top (rebased onto #150), from that run's cache and answers with the network blocked: 0 requests, every figure and verdict identical. 0641dc6 also re-parses all 400 sittings with the parser of #147 and #150, so the speaker set holds under it. (An earlier regeneration on fab68ca, before the rebase, gave the same figures; that id is on no remote branch.) `person_corrections.json` sha256 `2c99fe2c…`.
- **MdB source:** `mdb_zugehoerigkeiten` for the Mandat rule; names and Stammdaten membership from the store's cached zip (Stand 2026-04-29). The table and the zip agree on every WP 18/19 Mandat (0 disagreements).
- **Commands**, all through `~/agent-runs/aw-match/run.sh` (`SSL_CERT_FILE` set, scratch cache `~/agent-runs/aw-match/scratch/aw-cache.json`):
  1. `--offline`: 1,021 distinct Redner-IDs, 0 merged raw values, so 1,021 requests announced; 86 s, 0.3 GB maxrss.
  2. online `--name-fallback`, 2026-11-12 17:59:57–18:35:53Z: 1,032 requests (1,021 ext_id + 11 name searches), 0 HTTP 429, 5 isolated failures (`11003646`, `11003854`, `11004260`, `11004842`, `999990102`; exit 1); 36 min.
  3. online rerun, 18:36:10–18:37:44Z: asked only the 5 failed ids, 5 requests, 0 failures (exit 0).
  4. the receipt run with `--verdicts`, 18:41:27Z: 0 requests. Regenerated on 0641dc6 on 2026-11-13 (above), from copies of the cache and answers in `~/agent-runs/aw-match/regen2/`: 0 requests; this is the committed receipt. It adds `reden_unresolved` and `bounds` to each M2 row (0 and equal to the share here, since every id has an answer).
  - Hand review outside the script: 33 requests. Altogether about 1,070 abgeordnetenwatch requests, 0 DIP requests, 0 store writes.
- **Pace:** the API page (read 2026-11-12, still CC0 1.0, no key) now asks for at most 30 requests a minute per IP and at most one a second, 60 s after a 429. The resolver's 0.5 s spacing broke that, so item 1.5 raises the default to 2.0 s (and the 429 wait to 60 s) for every build, not only this script.
- **No store cache:** the fresh store holds no `abgeordnetenwatch-cache.json` and no `aw_match` on any of its 6,387 `mps` rows, because it was built without `--enrich aw-profiles`. The scratch cache therefore started empty: M3 flag 4 (cache disagrees) had nothing to compare and is vacuous here, and M6 is 0.

### Figures

A Redner-ID is counted per Wahlperiode it speaks in; the union counts it once, as M1 when it holds a Mandat in a Wahlperiode it spoke in.

| | WP 18 | WP 19 | Union |
|---|---:|---:|---:|
| **M1:** MdB ids with a Mandat in the WP, ext_id hit | **640 / 640 (100%)** | **719 / 727 (98.9%)** | **937 / 945 (99.2%)** |
| M1a: in the Stammdaten, no Mandat in the WP | 1 / 1 | 8 / 11 | 4 / 7 |
| M1b: not in the Stammdaten (government, Bundesrat, guests) | 0 / 30 | 0 / 43 | 0 / 69 |
| **M2:** Reden whose speaker's id hit | **9,720 / 9,862 (98.6%)** | **16,531 / 16,852 (98.1%)** | **26,251 / 26,714 (98.3%)** |
| Reden without a Redner-ID | 1 | 1 | 2 |
| Failures | 0 | 0 | 0 |

- **M3 precision:** 8 name-rule flags, 0 multi-candidate replies, 0 profiles returned for two Redner-IDs, 0 M1b hits (so no role id of an MdB), flag 4 vacuous (above).
- **M4 name fallback:** 11 MdB-Stammdaten misses searched by name, 11 linked, 0 unlinked, 0 failed. All 11 reviewed.
- **M5:** 4 partitioned Redner-IDs speak in WP 18/19 (`999990108`, `999990124`, `999990127`, `10000`); none hits, so a fresh WP 18/19 enrichment creates no `aw:` record under a shared id ("Shared Redner-IDs" item 8 stays unreached). 0 merged raw values in WP 18/19.
- **M6:** 0 WP 18/19 Reden hold a trusted profile in this store; all 640 + 727 WP 18/19 MdB ids hold none. On this store "the leavers" are every WP 18/19 speaker, not only those who left by 2021, because no aw data reached the store at all.

### Review

- **The 8 name-rule flags are all the right person.** Each profile carries the Redner-ID as its `ext_id_bundestagsverwaltung` (that is how it was found), and the abgeordnetenwatch birth year equals the Stammdaten `GEBURTSDATUM` year in all 8. The labels differ only in spelling: a hyphen (Franz-Josef Jung, Hans Joachim Schabedoth), a diacritic (Zaklin Nastić), an added name (Gehrcke-Reymann, Jensen-Bornhöft, Bernd-Bernhard Fabritius), a civil name beside the stage name (Karl-Heinz (Charles M.) Huber), Armin Paul / Armin-Paulus Hampel. The two-word rule is strict by design; no rule change follows.
- **The 11 name-found links are all the right person**, by full name and birth year (Stammdaten against abgeordnetenwatch, read with `politicians?id=`). The plan's mandate check on the profile was not possible through the API: `candidacies-mandates?politician=` returns no WP 18/19 Bundestag mandate for these profiles (Franz-Josef Jung: 0 rows; Manja Schüle: only Brandenburg 2024-2029). The birth year stood in for it, at no request cost.
- **Why the 8 M1 ids miss (all WP 19):** abgeordnetenwatch holds a four-digit `ext_id_bundestagsverwaltung` for them, not the Bundestag id: Danyal Bayaz `2028` (ours `11004664`), Nicola Beer `2031`, Axel Gehrke `2085`, Martin Hebner `2100`, Christian Jung `2130`, Thomas L. Kemmerich `2136`, Nikolas Löbel `2165`, Manja Schüle `2239`. All eight left the Bundestag during WP 19. Our key is the Stammdaten `ID`, which 937 other hits confirm, so this is class (c) on abgeordnetenwatch's side, not a defect of our key. `docs/source-errors.md` lists Bundestag sources only, so it is recorded here and in TODOS.md.
- **Why the 3 M1a ids miss:** Horst Seehofer, Annegret Kramp-Karrenbauer and Andreas Pinkwart (WP 19, speaking as ministers or for a Land) have no `ext_id_bundestagsverwaltung` on abgeordnetenwatch at all: class (b), a source gap.
- **M1b:** none of the 69 ids outside the Stammdaten (`9999…` and `10000`) is an abgeordnetenwatch ext id; expected.

**No confirmed defect.** No Redner-ID is linked to the wrong person, by ext_id or by name.

### What it triggers

- M3 clean, M1 high: the ext_id join holds for WP 18/19. Nothing to fix before coverage-gate step 8.
- The 11 misses would get a name-found link from a build (match `name`, untrusted, but linked on the person page as fact). All 11 are right today; the deferred item "Person pages link name-found profiles" stays open in TODOS.md.
- The store enrichment decision stays with the owner, now with M6 = every WP 18/19 MdB id (1,367 per-WP ids, 945 distinct MdBs) on this store.
- Coverage-gate step 7 re-runs the same command on the step 6 output directory; only Redner-IDs new in the 85 sittings cost requests, unless the answers file is deleted to ask every id again.
