# A3 plan item 1.5: the abgeordnetenwatch match share of WP 18/19 Redner

Plan, 2026-11-10, after `/plan-eng-review` (report at the end). **Ran 2026-11-12** on the fresh store of 28799ac; result and deviations in [a3-phase4.md](a3-phase4.md), "Plan item 1.5". Deviations from this plan: requests are paced at 2 s (the API page's fair-use limit of 30 a minute, not 0.5 s); `lookup_ext_id` returns a five-field `ExtIdLookup` (the cached answer beside the fresh one); an answers file beside the scratch cache lets a rerun ask only unanswered ids; the store had no aw cache to seed from, so M3 flag 4 was vacuous; the profile-page mandate check was replaced by the birth year, because the API's `candidacies-mandates` holds no WP 18/19 Bundestag mandate for the reviewed profiles; the abgeordnetenwatch id errors went to TODOS.md, since `docs/source-errors.md` lists Bundestag sources only.

Sources of the item:
- TODOS.md, "A3 /gstack-ship review: deferred findings", last bullet (P1);
- roadmap Stage 1 item 2.

The same measurement is also:
- step 7 of "Coverage gate before the first data release" ("the abgeordnetenwatch match share of WP 18/19 Redner");
- Q1 item 3 of `docs/plans/v1-scope-review.md`.

## Goal

[a3-coverage.md](a3-coverage.md) Phase 1 asked for "the share of WP 18/19 Redner whose redner-id finds an abgeordnetenwatch `ext_id_bundestagsverwaltung`". It was never measured:
- the pilot did not enable `aw-profiles` ([a3-pilot.md](a3-pilot.md), "abgeordnetenwatch: not measured");
- Phase 3 ran no `aw-profiles` either ([a3-phase3.md](a3-phase3.md) 4.6: "0 abgeordnetenwatch-enriched").

The measurement answers three questions:
1. **Reach.** How many WP 18/19 speakers can carry a trusted profile at all, meaning the `aw:` identity key and the profile link.
   - A speaker hit persists only `aw_politician_id`, `aw_match` and `profile_url` (`persist_dip_pulse_store.py:1222-1248`).
   - The biography columns come only from the roster's name search (`build_dip_pulse_site.py:8897-8913`), which is a deferred item below.
2. **Precision.** Whether the Redner-ID lookup ever returns the wrong person. This is the correctness question: a trusted `aw:` key is a Personenkennung and merges records durably.
3. **Fallback.** How many speakers would fall through to the name search. The person page links that result as if it were certain.

## What the number means for correctness

Code facts the plan rests on, all read on 28799ac:

- **The lookup.** `enrich_report_with_profiles` (`scripts/build_dip_pulse_site.py:1072`) calls `resolver.resolve(ext_id=speaker["xml_redner_id"], first_name, last_name, fraktion)`.
  - It does this for every speaker in `xml_speakers`, `xml_speakers_first` and `xml_contributions`.
  - It skips a Beitrag without a Redner-ID, and any speaker that already holds an `abgeordnetenwatch` key (`:1088-1089`).
  - `resolve` (`scripts/abgeordnetenwatch.py:337`) asks `/politicians?ext_id_bundestagsverwaltung=<id>` and takes `data[0]` (`:311-314`).
  - On a miss it searches by name. It accepts a unique result, or a unique party match.
  - Roll-call members get the name search only.
- **Trust.** Only `match == "ext_id"` is trusted (`derive.TRUSTED_AW_MATCH`, `derive.trusted_aw_id`).
  - Such a speaker's identity key becomes `aw:<id>` (`persist_dip_pulse_store.mp_identity`).
  - `person_registry.match_rows` pass 1 merges every record that shares this key. Pass 1b joins a name-found record holding the same id under a shared printed name.
  - A wrong ext_id hit is therefore a **false merge**, and a durable one (`docs/stable-ids.md`, "Durable and recomputed merges").
  - It can also **remove a correct profile.** A record holding two different trusted ids becomes `aw_match = 'conflicting'` and shows no profile (`person_registry.py:498-503`).
  - One person can hold two Redner-IDs, an MdB id and a government-role id (pass 1b comment, `person_registry.py:923-931`). One abgeordnetenwatch id under two Redner-IDs can therefore be legitimate.
- **Name-found profiles are shown as fact.**
  - `render_abgeordnete_detail` (`build_dip_pulse_site.py:9658`) links `mps.profile_url` as "abgeordnetenwatch.de-Profil" whatever `aw_match` says.
  - Persist writes a speaker's `profile_url` from any match kind (`persist_dip_pulse_store.py:1224-1248`).
  - Roll-call links were restricted to trusted matches on 2026-10-31 (TODOS B4 item 8); person pages were not.
  - The 2026-10-31 codebook audit counted 91 `mps` rows with `aw_match = 'name'` against 933 with `ext_id`, in the reference store of that day (`docs/research/codebook-dictionary-audit-2026-10-31.md:25`).
- **Shared Redner-IDs.** A Redner-ID printed for two people returns the profile owner's profile for both speakers.
  - Reviewed partitions (`scripts/person_corrections.json`) set `aw_match = 'partitioned'`, so the id joins nothing.
  - `registry.profile_follows_redner_id` stops the reparse carry-over.
  - An unreviewed shared id makes `reconcile` refuse (`require_reviewed_redner_ids`).
  - TODOS "Shared Redner-IDs" item 8: an `aw:`-keyed record that holds a shared id keeps a dip-only rebind, so a replay differs from a fresh build. "None exists in the A3 store", because WP 18/19 was never enriched.
- **What the A3 store already holds.** Without `aw-profiles`, WP 18/19 speakers get a profile only through `reparse_cached_xml`'s `by_redner_id` carry-over (`build_dip_pulse_site.py:1965-1993`).
  - The carry-over copies the profile that any other cached report (WP 20/21) resolved for the same Redner-ID.
  - So MdBs who sat on into WP 20 have profiles. Those who left by 2021 have none.
  - Counting the store's `aw_match` would measure that carry-over, not what the lookup finds.
- **Merged records (source-errors C2).** `resolve` gets the raw attribute, for example "11005217 999990074" (Svenja Schulze, WP 21), and asks with both ids as one value.
  - The reparse carry-over uses `derive.first_redner_id`, so the two paths key one speaker differently (review-checklist class 4).
  - C2 and Phase 3's ten warnings are WP 21. The WP 18/19 count is unknown, and M5 counts it.
  - Her other Reden carry the single id, so her record still gets a trusted profile through the fold. Nothing read here shows a wrong link from it.
- **Site claim.** The Daten source card (`build_dip_pulse_site.py:12390`) says speakers are linked "primär über die Bundestags-Redner-ID". For WP 18/19 leavers in a store built without `aw-profiles`, no lookup ran. The measured share is the figure a coverage statement needs.

## Metric definition

The unit is a **distinct Redner-ID**, taken with `derive.first_redner_id`, from the ext_id lookups a fresh enrichment would make. The script obtains them by running the build's own code (see Procedure, step 2):
- **Which reports.** The reports of the WP 18/19 sittings the store holds, loaded as the offline build loads them (`load_existing_detail_entries`, then `without_recorded_exclusions`). An excluded sitting therefore does not count.
- **Re-parsed first.** Each report is re-parsed from its cached XML with `reparse_cached_xml`, in memory, as `--offline --repersist` does.
  - `repersist_cached_reports` (`build_dip_pulse_site.py:2529`) does not write the JSON, but the render that follows an `--offline --repersist` does (`write_report_files`, `build_dip_pulse_site.py:1200`). The JSON can still be older than the store after a repersist that stopped before or during its render, so re-parsing is the safe source.
  - The re-parsed speaker set is the store's.
- **Then enriched with a recorder.** `enrich_report_with_profiles` is called with a recording resolver.

Reported per Wahlperiode (18, 19) and for their union. An id that speaks in both Wahlperioden counts once in the union.

**MdB split, per Wahlperiode.** An id counts as "MdB in WP n" when the MdB-Stammdaten give its `ID` a Mandat (`WAHLPERIODEN`) in WP n. The same rule applies whatever the source, in this order:
1. `mdb_zugehoerigkeiten` in the store, which holds WP ≥ 18 only (`derive.py:1013`), enough for this rule;
2. the store's cached `mdb-stammdaten.zip`, read with `stammdaten.read_zip`;
3. `--stammdaten PATH`.

Membership alone is not enough, because the zip keeps every Wahlperiode. A speaker with an old MdB id but no seat in WP 18/19, such as a minister, would then count as an MdB under the zip and not under the table.

`~/agent-runs/a3/full` predates schema 9, so it has no table. Without any source, the receipt says `mdb_source: none` and M1 is not reported. A number-range proxy would be a guess presented as a figure.

| Figure | Definition |
|---|---|
| **M1, headline** | Of the Redner-IDs with a Mandat in WP n, the share for which the lookup returns exactly one politician |
| M1a | The same share for ids in the Stammdaten with no Mandat in WP n, for example former or later MdBs speaking as ministers |
| M1b | The same share for ids not in the Stammdaten: government members who are not MdBs, Bundesrat members, guests. A low share is expected. Each M1b hit whose name matches an MdB is marked: a second, role id of an MdB |
| M2, Reden-weighted | The share of Reden (`xml_speakers` entries, counted per entry, never per recorded call) whose speaker's id hit: how much of the WP 18/19 text a trusted profile can reach. Also the count of Reden without a Redner-ID, which the build searches by name only |
| M3, precision | Each flag below gets a review by hand, with a verdict per id in the receipt |
| M4, name fallback | Of the MdB-Stammdaten misses, how many the name search would link with match `name`, and the review of those links |
| M5, shared and merged | Hits on Redner-IDs that `person_corrections.json` partitions, with and without a `profile_owner`; and speakers whose raw attribute holds two ids, with how many of them hit by the first id but not by the raw value |
| M6, today's carry-over | Read from the store (read-only): WP 18/19 Reden whose `mps` row has `aw_match = 'ext_id'`. The figure gives the ids that hold a profile today through the A3 carry-over, and the WP 18/19 MdB ids that hold none, that is, the leavers the store enrichment decision is about |
| Failures | Ids not answered: a network failure, the resolver's 8-failure cut-off, or a non-`ok` API reply. They are not misses (review-checklist class 5). A run with failures is not a result |

M3 flags:
1. **Name check.**
   - For a Stammdaten id, the hit's abgeordnetenwatch `label` must contain a given-name word and a surname word from that `ID`'s `NAMEN`. `read_zip` keeps every name, the historical ones included (`HISTORIE_VON`), so a name change like Köstering/Krampe passes without a manual note.
   - For any other id, compare against the printed `first_name` and `last_name`, with the same two-word rule.
   - Words come from the registry's normaliser (`person_registry._name_words`, `:835`: titles and particles dropped).
   - Requiring both words stops a namesake who shares only the surname, or only the given name.
2. **More than one politician.** A lookup that returns more than one politician. The build takes `data[0]` today.
3. **One profile, two ids.** One abgeordnetenwatch id returned for two or more Redner-IDs. Each case is classified by name before it is called a defect, because an MdB with a role id is legitimate.
4. **Cache disagrees.** A cached positive (in the store's cache) whose id differs from the fresh answer (review-checklist class 2). The online run asks again about every id, not only the cached negatives, so this flag can fire at all.

Optional, at no request cost: compare the abgeordnetenwatch `year_of_birth` with the Stammdaten `GEBURTSDATUM`. This needs `read_zip` to keep one more field. It is recorded as a decision below.

**Not measured:**
- **A per-person share.** A Redner-ID stands for one person, apart from the shared ids M5 lists. The registry holds 0 records with more than one Redner-ID (TODOS A.2 follow-up (5)). A per-person figure would also depend on the concurrently changing registry (the Köstering/Krampe split) without adding information.
- **A mandate check per hit.** It costs one request each. The name check in M3 is the precision gate.

## Why not `--enrich aw-profiles` on a clone, as TODOS says

- **The enrichment runs only when a sitting is rebuilt online.** It runs in `write_report_and_page` for the sittings an online run selects. The resolver exists only on the online path (`build_dip_pulse_site.py:14604`, after the offline branch returns).
  - `--offline --repersist` resolves nothing.
  - `--detail-limit -1 --enrich aw-profiles` resolves only the roster, by name (that is how Phase 3 4.6 ran the roster).
- **So it costs a re-acquisition.** Enriching the 400 stored WP 18/19 sittings (194 + 206 [measured: a3-phase3.md, store after WP 21]) means acquiring them again:
  - about 26 DIP requests per sitting, about 10,400 in all;
  - at the 2 s pace about 6 h, plus the dserver XML limits [estimated from A3, coverage-gate step 6].
- **It would blur the result.** Re-fetched DIP data would land in the same clone.
- **The lookup does not depend on the store.** It depends only on the Redner-ID and on abgeordnetenwatch. A read-only script that drives the same code measures the same thing, with no DIP request.

Putting profiles into the store for WP 18/19 is a separate decision, taken on this result (see "What each outcome triggers").

## Procedure

### 1. `abgeordnetenwatch.py`: one public lookup, and API errors are not misses

- **`_request` (`:304-305`).** It returns `None` for a reply whose `meta.status` is not `ok` without setting `_call_failed`. `resolve` then caches that as "no match", and a later build runs the name search instead. Set `_call_failed` there.
  - This is a correctness fix for the measurement, which would otherwise count an API error as a miss.
  - It also fixes the build: no false negative gets cached.
  - Test: a non-`ok` reply caches nothing and leaves `stats["errors"]` at +1.
- **New public method:**

  ```
  AbgeordnetenwatchResolver.lookup_ext_id(ext_id, *, network=True, refresh=False)
      -> (state, profile, candidates)
  ```

  - `state` is one of `hit`, `miss`, `failed` or `not_cached` (`not_cached` only with `network=False`);
  - `candidates` is the number of politicians returned;
  - it reads and writes the existing cache, so the cache format stays owned by this module.
  - `resolve`'s ext_id branch calls it: one way to do the lookup (`hit` → the profile, `miss` → the name search as today). The behaviour is unchanged except for the `_request` fix.
  - The `data[0]` choice stays as it is until M3 shows a multi-candidate case. That is decided then, as a correctness fix.
- **Tests** in `tests/test_abgeordnetenwatch.py`:
  - each state;
  - `refresh` asks again about a cached hit and a cached negative, and reports the cached value beside the fresh one;
  - `network=False` sends nothing;
  - the 8-failure cut-off gives `failed`, not `miss`.

### 2. Script: `scripts/measure_aw_match_share.py` (committed, with a test)

```
python3 scripts/measure_aw_match_share.py OUTPUT_DIR --cache SCRATCH/aw-cache.json \
    [--stammdaten ZIP] [--offline] [--name-fallback] [--json RECEIPT]
```

Inputs:
- Opens `OUTPUT_DIR/data/bundestag-pulse.sqlite` read-only (`?mode=ro`). It writes nothing under `OUTPUT_DIR`.
- Reads the stored WP 18/19 protocol numbers and loads those reports through `load_existing_detail_entries` and `without_recorded_exclusions`, as the offline build does.
- Handles the reports **one at a time**. `full` is 5.4 GB with the XML [measured: a3-phase3.md, after WP 21], so no list of every re-parsed report is held in memory.

Collecting the lookups. For each report the script:
1. calls `reparse_cached_xml(output_dir, [entry], profiles_from=[])`. This re-parses from the cached XML in memory and writes nothing. No carry-over runs, since the profiles are removed next anyway;
2. removes the `abgeordnetenwatch` keys from the speakers of `SPEAKER_LISTS`. The build skips a speaker that holds one (`:1088-1089`);
3. calls `build_dip_pulse_site.enrich_report_with_profiles(entry["report"], recorder)`. `recorder.resolve` records each call's `ext_id`, names and Fraktion, and returns `None`;
4. keeps the calls that carry an `ext_id`. Roll-call members and Reden without a Redner-ID carry none: the latter are counted for M2.

Speaker objects shared between `xml_speakers` and `xml_speakers_first` are separate after the JSON round trip, so one speaker can be recorded twice. Distinct ids are unaffected. M2 counts `xml_speakers` entries, not calls.

The speaker set is therefore the build's own, with no second copy of the selection rule to drift. M6 comes from the store, not from the reports.

For each Redner-ID it then has:
- the Wahlperioden;
- the Reden count;
- the printed names;
- the Fraktion;
- whether the raw value held two ids.

Doing the lookups:
- **Scratch cache.** On the first run it copies `OUTPUT_DIR/data/abgeordnetenwatch-cache.json` to `--cache` byte for byte. The store's own cache is never written.
- **`--offline`.** `lookup_ext_id(id, network=False)` for each id:
  - prints lower and upper bounds for M1, plus the exact number of requests an online run will send;
  - sends nothing. Run it first.
- **Online.** `lookup_ext_id(id, refresh=True)` for every id, cached hits included.
  - A cached negative may be months old, and abgeordnetenwatch fills in ext ids later.
  - A cached hit must be asked again so that M3 flag 4 can compare the cached and the fresh answer.
  - Each id costs one request.
- **`--name-fallback`.** For each MdB-Stammdaten miss, `resolve(first_name, last_name, fraktion)` with no ext_id. The profile is recorded for the M4 review.

Output and exit codes:
- **Receipt.** Prints the table and writes `--json` with:
  - commit, date, store path (`$HOME` written as `~`, like `a3-phase4-gate.json`) and store sha256;
  - the sha256 of `scripts/person_corrections.json`, which M5 and `profile_follows_redner_id` read and which the Köstering/Krampe split edits;
  - `mdb_source` and the Stammdaten Stand;
  - M1 to M6 per Wahlperiode, and failures;
  - the resolver's `stats` (`api_calls`, `throttled`, `errors`);
  - the review lists (M3, M4, M5) with ids, printed names, and the abgeordnetenwatch labels and URLs.
- **Exit 0** on a complete result.
- **Exit 1** if any id failed. Rerun: the cache keeps what was answered.
- **Exit 2** on a usage error: no store, no WP 18/19 sittings, a stored sitting without a report, or an unreadable `--stammdaten`.

Test `tests/test_measure_aw_match_share.py` runs offline, like the suite. It uses fixture reports, a small store and a stub resolver. It checks:
- the denominators per Wahlperiode and in the union;
- the per-Wahlperiode MdB split: an id with a Mandat only in WP 17 is M1a, not M1, from the table and from the zip alike;
- that speakers holding a cached profile are still counted (the stripped key);
- that a report whose JSON differs from its XML is counted as re-parsed;
- a merged raw id ("A B") counts once under A, and the raw-miss counter;
- `failed` is not a miss and gives exit 1;
- the M3 name rule: a title, an umlaut, a historical surname (`HISTORIE_VON`), a namesake sharing only the surname, a namesake sharing only the given name, and a multi-candidate reply;
- a cached hit that differs from the fresh one raises flag 4;
- `--offline` sends nothing;
- a sitting the store does not hold is not counted;
- no MdB source gives `mdb_source: none` and no M1.

### 3. Run now, on the A3 cache

- **Object.** The reports, `abgeordnetenwatch-cache.json` and Stammdaten of the newest store built on current main from the A3 data (716 sittings). Otherwise use `~/agent-runs/a3/full`, read-only, with `--stammdaten` pointing at a current zip.
  - The ids come from the reports re-parsed with the commit's code, and none of the concurrent items changes which Redner-IDs a sitting prints. Any of these stores therefore gives the same set of ids.
  - The receipt names the path and the sha256.
  - **No store or clone was on this machine when the plan was written** (`.context/` and `~/agent-runs/` were absent), so the operator locates it first.
- **Before the run:** read the abgeordnetenwatch API page again. ADR 0003 read it on 2026-09-28: CC0, no key. Check that nothing changed.
- **Order:**
  1. `--offline`: bounds and the request count;
  2. online, repeated until there are 0 failures;
  3. `--name-fallback`.
- **Review:**
  - every M3 flag;
  - the M4 links: all of them up to 50, otherwise a random 50 with a fixed seed;
  - each one checked against its abgeordnetenwatch profile page: a Bundestag mandate in WP 18 or 19, and the name;
  - the verdict per id goes into the receipt.

### 4. Re-run in coverage-gate step 7

After step 6 has fetched the 85 sittings, run the same command on that output directory. Only Redner-IDs new in the 85 cost requests; the scratch cache answers the rest. Step 7's record cites both receipts.

**One measurement, run twice, serves both items.**

## Cost and time

- **abgeordnetenwatch requests:**
  - one request per distinct WP 18/19 Redner-ID, cached hits included: about 1,000 to 1,300 [estimated: about 660 + 740 MdBs with successors, about 420 in both, plus about 150 to 250 non-MdB speakers];
  - plus one request per M4 miss.

  That is at most about 1,800 requests: about 15 min at the resolver's 0.5 s spacing, and up to about 35 min with 429 backoffs [estimated]. The `--offline` step replaces this with the exact count before anything is sent. The step 7 re-run asks again only about ids new in the 85 sittings, unless their cache entries are older than the first run.
- **DIP:** 0 requests. **Store writes:** none.
- **Effort:**
  - code and tests (step 1 and the script): human ~1–1.5 days / CC ~2 h;
  - run: ~30 min wall time;
  - M3/M4 review: human ~1–2 h / CC ~30 min, plus the owner's look at flagged cases;
  - record: ~30 min.
- **One PR:** the lookup method and the `_request` fix, the script, the tests, the receipt and the record.

## What each outcome triggers

| Finding | Meaning | Action |
|---|---|---|
| M3 confirmed wrong person, or a multi-candidate reply | A trusted `aw:` key would merge two people | Correctness defect. Fix before coverage-gate step 8, either with a reviewed partition with `profile_owner` or with a reviewed ignore entry for that abgeordnetenwatch id; for multi-candidate replies, trust only a single candidate. Each fix gets a test. Check whether the id already carries a profile in the A3 store through the carry-over: if so, the defect is live today, and its PR reports the old and new values |
| M3 flags all explained (a name change, as with Köstering/Krampe) | No wrong merge | The explanation per id goes in the receipt |
| M1 high | The ext_id join holds for WP 18/19 | Record it. What remains open is the store enrichment decision below |
| M1 lower | abgeordnetenwatch lacks the ext ids, or our key does not match theirs | Look up the first 20 misses on abgeordnetenwatch by name and classify each: (a) no profile; (b) a profile without an ext id; (c) a different id. A (c) or a pattern points at our key, and is fixed as a defect. (a) and (b) are a source gap, recorded in `docs/source-errors.md` and in the coverage statement. No percentage threshold: the classification decides |
| M4 review finds a wrong link | Name-found profiles would put another person's link on a person page | Evidence for the deferred item "Person pages link name-found profiles". It becomes a correctness fix before any WP 18/19 store enrichment |
| M5 merged-record raw misses > 0 | The lookup keys a merged speaker by the raw attribute | The one-key fix (`first_redner_id` in `enrich_report_with_profiles`) is filed in TODOS: the defect predates this item and no WP 18/19 profile is persisted from it today. It is promoted to a fix if any affected speaker ends with a wrong name-found link (M4) |
| M5 hits on partitioned ids | Shared-Redner-ID item 8 becomes reachable once WP 18/19 is enriched | Note it under that TODO, with the ids |

**Store enrichment decision**, taken on the result and not in this item:
- **For:** with a clean M3 and M4, the WP 18/19 leavers M6 counts could carry profiles.
- **Against:** they need either the 6 h re-acquisition or new code, such as an offline attach of cached ext_id profiles in `reparse_cached_xml`, gated by `profile_follows_redner_id`.
- **Recorded:** as a follow-up for the owner, with M6's count.

## Where it is recorded

- **`docs/plans/a3-phase4.md`**, a new section "Plan item 1.5: abgeordnetenwatch match share (date)", with:
  - the command, commit, store path and sha256, and `mdb_source`;
  - the M1–M6 table per Wahlperiode, with failures at 0;
  - the request count and time;
  - the review verdicts;
  - what was triggered.
- **`docs/plans/a3-aw-match-share.json`**: the receipt.
- **TODOS.md:**
  - the item 1.5 bullet is struck through, with the headline figure and a link;
  - the coverage gate's step 7 notes that its abgeordnetenwatch part is this script's re-run;
  - new items as triggered above, plus the three deferred items below.
- **No store, site or export figure moves.** The store is not touched, and `_request`'s fix changes only what a future build caches. A fix triggered by M3 reports its own old and new values in its PR.

## Sequencing with the concurrent work

The script writes no store. It reads the cached reports and XML (re-parsed with the code of the commit it runs on), the `protocols` list, the Stammdaten and `person_corrections.json`. None of these is changed by the concurrent items, except as noted below:
- E4 repersist: votes and `vote_members`;
- the Köstering/Krampe registry split: the registry, WP 21;
- ADR 0004 presidium kinds: the speech kind of stored Reden;
- W1/W2: inventory and withholding.

It can run before, during or after any of them. Two qualifications:
- M2 counts the report's `xml_speakers`. If ADR 0004 or W2 later move units out of the Reden counts, step 7's re-run reflects that.
- The Köstering/Krampe split may edit `person_corrections.json`, which M5 reads. The receipt records the file's sha256. Step 7's re-run uses the file as it then stands.
- A confirmed M3 defect would touch `person_corrections.json` or the registry. That fix comes after the Köstering/Krampe split, which edits the same area, and before step 8's rebuild.

## What stays deferred (to file in TODOS.md with the result)

- **Enriching WP 18/19 in the store**, as above.
- **Person pages link name-found profiles.** `render_abgeordnete_detail`, and persist writes `profile_url` for `aw_match = 'name'`. 91 such rows exist in the reference store, so this is already live for WP 20/21. It predates this item, and no TODOS entry names it.
- **The merged-record lookup key**, as above.
- **The roster's abgeordnetenwatch lookup** is a name search only (`ingest_mdb_roster`, `build_dip_pulse_site.py:8898`), so its biography columns are unverified in the same way. Not measured here.
- **A mandate check per hit** (one request each) and **the birth-year check** (no requests; `read_zip` keeps one more field), if M3's name check proves too weak.

## Decisions for the owner to confirm

None of these could be asked during planning. Each is picked by CLAUDE.md's accuracy-only rule.

1. **A read-only script that drives the build's own enrichment code, not `--enrich aw-profiles` on a clone.** It makes the same lookups with 0 DIP requests instead of about 10,400, and mixes no re-fetched data in.
2. **Commit the script and its test, not a one-off.** Step 7 re-runs it, and the committed receipt makes the figure reproducible.
3. **The denominator is distinct Redner-IDs, per Wahlperiode and in the union.** The headline counts MdB-Stammdaten ids. Non-MdB ids and the Reden-weighted share are shown beside it. There is no per-person figure, and no number-range proxy when the Stammdaten are missing.
4. **Every id is asked again, cached hits included** (outside voice finding 3). The figure is as of the run date, and a stale cached hit shows up as M3 flag 4. This costs about 500 extra requests.
5. **One measurement serves item 1.5 and gate step 7:** run now on the A3 cache, run again at step 7.
6. **No percentage threshold.** Precision has zero tolerance. Recall triggers a classification of misses.
7. **The store enrichment of WP 18/19 is decided after the result.**
8. **(Review, structure)** Keep the original arrangement: a lookup method in `abgeordnetenwatch.py` plus the script. The smaller arrangement, a script reading the cache JSON directly, would duplicate the cache format and keep miscounting API errors.
9. **(Review)** Fix `_request`'s non-`ok` branch in this PR. It is a correctness defect for this measurement (an error counted as a miss) and a latent false negative in every build's cache.
10. **(Review)** The build's `data[0]` choice for a multi-candidate reply stays until M3 shows a case. The measurement flags it, and the fix follows the evidence.
11. **(Outside voice 1)** "MdB" means a Mandat in that Wahlperiode, by one rule for all three Stammdaten sources. Ids that are MdBs only in other Wahlperioden form their own row, M1a. Without this, M1 would move with `mdb_source`.
12. **(Outside voice 2)** The reports are re-parsed in memory from the cached XML before recording, as `--offline --repersist` does. The JSON on disk can be older than the store, and the speaker set must be the store's.
13. **(Outside voice 4)** The M3 name check needs a given-name word and a surname word, against all of the Stammdaten `NAMEN` of an MdB id (historical surnames included), instead of the surname alone.
14. **(Outside voice 4, optional part)** The birth-year check (abgeordnetenwatch `year_of_birth` against the Stammdaten `GEBURTSDATUM`) is **deferred**. It needs `read_zip` to keep one more field, and the two-word name rule plus a manual review of every flag already gates precision. Take it up if the review finds a same-name wrong hit.
15. **(Outside voice 5)** The Reach goal no longer claims biography columns. A speaker hit carries only the id and the link. The roster's name-only biography stays a deferred item.

## Eng review record (2026-11-10)

Run by a spawned planning agent. The owner could not be asked, so each review question was decided by CLAUDE.md's accuracy-only rule and listed under "Decisions for the owner to confirm" (8 to 15).

**Scope Challenge.**
- **Changed files:**
  - `abgeordnetenwatch.py` and its test;
  - the new script and its test;
  - the `a3-phase4.md` record, the JSON receipt and TODOS.md.

  That is 7 files and no new class, under the complexity gate, so it was not tripped. A first draft also changed `build_dip_pulse_site.py` (a speaker iterator) and `person_registry.py` (a public `name_words`); the recorder resolver and a direct import made both unnecessary.
- **What already exists:**
  - `enrich_report_with_profiles` (the speaker set);
  - `reparse_cached_xml` and `load_existing_detail_entries` (the build's own report loading);
  - `AbgeordnetenwatchResolver` and its cache;
  - `stammdaten.read_zip`;
  - `person_registry._name_words`;
  - `validate_store_gate.py`'s receipt shape.
- **TODOS cross-reference:**
  - "Shared Redner-IDs" item 8 is reachable only after enrichment (M5);
  - no entry names the person-page link of name-found profiles, so it is to be filed.
- **Result:** scope accepted as-is (FULL_REVIEW).

**Findings, folded in.**

| # | Section | Severity, confidence | Evidence | Disposition |
|---|---|---|---|---|
| 1 | Code quality | CRITICAL for the measurement, 9/10 | `abgeordnetenwatch.py:304-305`: `if not isinstance(payload, dict) or payload.get("meta", {}).get("status") != "ok": return None` leaves `_call_failed` False, and `resolve` caches a negative | Fix in this PR (decision 9) |
| 2 | Architecture | INFORMATIONAL, 9/10 | `:313-314`: `return _profile_from_politician(data[0], "ext_id")` takes the first of several | Flag in M3; fix on evidence (decision 10) |
| 3 | Architecture (hand-synced list) | INFORMATIONAL, 8/10 | The script would have copied the speaker selection of `build_dip_pulse_site.py:1083-1095` | A recorder resolver drives the build's own function |
| 4 | Architecture (split ownership) | INFORMATIONAL, 7/10 | The script would have read and written the `by_ext_id` cache JSON that `abgeordnetenwatch.py` owns | Public `lookup_ext_id` (decision 8) |
| 5 | Plan accuracy | INFORMATIONAL, 8/10 | The draft placed the merged ids in WP 18/19; `docs/source-errors.md` C2 and Phase 3's ten warnings are WP 21 (Svenja Schulze) | Corrected; M5 counts WP 18/19 |
| 6 | Code quality | INFORMATIONAL, 8/10 | The registry's any-word rule (`person_registry.py:850-852`) lets a namesake through | Two-word rule against the Stammdaten `NAMEN` (with outside voice 4) |
| 7 | Tests | INFORMATIONAL, 7/10 | The A3 `full` store predates schema 9 (no `mdb_zugehoerigkeiten`) | Three MdB sources; `mdb_source: none` reports no M1; tested |
| 8 | Performance | INFORMATIONAL, 6/10 | `full` is 5.4 GB; all re-parsed reports at once would cost memory like a repersist (2.6 GB at 290 sittings, a3-pilot.md) | One report at a time |

`issues_found` is 8 across Sections 1 to 4.

**Failure modes.**
- **A 429 storm:** the resolver backs off.
- **A connection outage:** after 8 consecutive failures the resolver stops sending, and the remaining ids are `failed`, giving exit 1.
- **A non-ok reply:** `failed`, after fix 1.
- **A changed API shape:** `failed`, or `miss` with 0 candidates. The receipt's `stats` and the review show it.

0 critical gaps remain after fix 1.

**Test diagram.**

```
lookup_ext_id ── hit / miss / failed / not_cached ── refresh ── network=False ── 8-failure cut-off
_request non-ok ── no cache entry, errors+1
script ── re-parse ── strip ── recorder ── per-WP MdB split (table, zip) ── M1/M1a/M1b
       ── merged id ── failed≠miss, exit 1 ── M3 rules (title, umlaut, HISTORIE_VON, namesakes, multi)
       ── cached≠fresh flag 4 ── --offline sends nothing ── excluded sitting ── mdb_source none
```

**Outside voice.**
- **Who ran it:** Codex is not installed (`CODEX_MODE: not_installed`), so the native fallback ran: a Claude Plan subagent, read-only. This is not external coverage.
- **Verdict:** approve with changes. 8 findings:

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | High | The MdB split depended on the source, because the zip covers every WP and the table WP ≥ 18 | Accepted: per-WP Mandat rule, M1a (decision 11) |
| 2 | Medium | Reports on disk are not re-parsed (`repersist_cached_reports` works in memory) | Accepted: re-parse in memory (decision 12) |
| 3 | Medium | M3 flag 4 was blind, because only negatives were re-asked | Accepted: re-ask every id (decision 4) |
| 4 | Medium | The surname-only rule passes namesakes | Accepted: two-word rule against `NAMEN` (decision 13); the birth year is deferred (decision 14) |
| 5 | Medium | Goal 1 claimed biography columns | Accepted (decision 15) |
| 6 | Low | `AW_CONFLICT` removes a correct profile; role ids make flag 3 legitimate | Accepted: stated, and flag 3 classified by name |
| 7 | Low | Repeated calls after the JSON round trip; Reden without a Redner-ID | Accepted: M2 counts entries; the id-less Reden are counted |
| 8 | Low | `person_corrections.json` changes under the registry split | Accepted: its sha256 goes in the receipt |

**Not persisted.**
- The gstack Review Log was not written: this branch carries other agents' work, and a branch-level review entry would misstate its state for `/ship`. Command for the owner to run if wanted:

  ```
  ~/.claude/skills/gstack/bin/gstack-review-log '{"skill":"plan-eng-review","timestamp":"2026-11-10T00:00:00Z","status":"issues_open","unresolved":0,"critical_gaps":0,"issues_found":8,"mode":"FULL_REVIEW","commit":"28799ac"}'
  ```

- gstack's own prompts were left unanswered, because they are the owner's consent: the upgrade from 1.98 to 1.99, the telemetry opt-in, and cross-project learnings.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run | — |
| Outside Review | native fallback (Claude Plan subagent; Codex not installed) | Independent 2nd opinion | 1 | unavailable (native completed: issues_found) | 8 findings, 8 accepted |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 (not persisted) | ISSUES OPEN (all folded into the plan) | 8 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | not run (no UI) | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | — |

- **OUTSIDE COVERAGE:** Codex unavailable (not installed). The native Claude fallback completed with 8 findings, all accepted. There is no external-model coverage.
- **VERDICT:** Eng review findings are all folded into the plan, and decisions 8 to 15 await the owner's confirmation. Ready to implement once the owner confirms them. Eng review is not logged as CLEAR.

NO UNRESOLVED DECISIONS
