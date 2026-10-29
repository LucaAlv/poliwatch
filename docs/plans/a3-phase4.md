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
