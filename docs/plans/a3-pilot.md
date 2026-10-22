# A3 Phase 1: WP 18/19 pilot (2026-10-19/20)

Plan: [a3-coverage.md](a3-coverage.md), Phase 1. Status: **stopped early**. Two findings break the plan's assumptions and need decisions before Phase 3 (end of this file).

## What ran

- Clone `~/agent-runs/a3/pilot` of the gate-validated `~/agent-runs/a3/gate` ([gate record](a3-gate-validation.md)).
- Batch 1, code 43ab74d (= v0.20.0.0 plus the gate script): the 11 WP 18 sittings of the sample, `--vote-scan-pages 90 --sleep 0.5`. 5 acquired (18/245, 18/217, 18/200, 18/154, 18/150), then 18/100 stopped the run with `SprechrolleError: no Sprechrolle rule maps the role "Präsident"`. Nothing was persisted.
- Batch 2, code e547eae (lanes A–D), `--sleep 1.0`, the other 18 sittings: DIP timed out on the very first catalog request for 32 minutes. I stopped it; no data.
- Census without DIP: the 23 sample XML files plus the budget weeks 18/68–71 (Nov 2014) and 19/63–66 (Nov 2018), downloaded once from dserver.bundestag.de (public, 1 s apart), parsed with the current parser and read for roles, Fraktion strings and Einzelplan headings.

## Finding 1: the parser rejects a fifth to a third of WP 18/19 sittings (D4)

**Measured** on 175 WP 18/19 XML files: the 31 sample and budget-week files, plus a download of the newest WP 19 sittings, which dserver.bundestag.de stopped serving us after about 150 files. Census: `~/agent-runs/a3/wp18-19-census.json`. The current parser (speech rule 5) refuses:

| | Files | Refused | Share |
|---|---:|---:|---:|
| WP 19 (19/79–19/239 and the sample) | 160 | 31 | 19% |
| WP 18 (sample and budget weeks only) | 15 | 6 | 40% |

The WP 18 share comes from a biased sample: the A1 picks favour question formats. Extrapolated:
- WP 19: about 45 of 239 sittings;
- WP 18: somewhere between 50 and 100 of 245;
- together, roughly 100–150 sittings that stop the backfill.

The A3 TODO recorded that 18/1, 18/100, 19/1 and 19/239 parsed on 2026-09-30. They are refused now, so the refusals arrived with speech rules 3–5. Their audit ([offline-v5-validation.md](offline-v5-validation.md)) covered only the 290 WP 20/21 files.

**What blocks.** In every refusal, a member's turn is nested inside another member's `<rede>` and rule 5 cannot classify it (`unresolved nested contribution at <Rede> marker <n>`). The blocking turn is an ordinary MdB in 34 of the 37 cases, and a presidium or government role in the other 3. Read from the XML, four kinds:
1. **A whole Rede printed inside the previous one**, after the chair's "Als nächste Rednerin spricht …" (18/10 Bartz, 18/70 Binder). These are Reden with no `<rede>` of their own, so counting them is a structural decision.
2. **Zwischenfragen and Zwischenbemerkungen whose grant rule 5 does not read.** The grant reads "Ja.", "Aber ja.", "Immer, ja.", or is a thank-you afterwards ("dass Sie die Zwischenbemerkung zulassen"), often with no question mark (18/50, 18/71, 19/101, 19/104, 19/108, 19/118).
3. **A minister answering inside such an exchange** (18/50 Hendricks).
4. **Chair and election turns.** The elected Präsident's "ich nehme die Wahl an" (18/1, 19/1), the Präsident's own floor-giving encoded as a nested `<redner>` with `<rolle_lang>Präsident` (18/100), and an answer to a Rückfrage from the chair (19/102).

The reviewed exclusion list (D2) was designed for rare refusals. Listing 100–150 sittings would leave a large part of WP 18/19 uncovered. The fix is an extension of rule 5 to the WP 18/19 encodings, with its own audit record like offline-v5-validation.md, showing whether the 290 WP 20/21 files stay unchanged. That is a counting-rule change (A1 territory), so it is a decision.

**Unmapped presidium roles.** Präsident (18/100, 19/1), Vizepräsident(in) (18/245) and Alterspräsident (19/1) occur in this census only on nested chair markers (kind 4). A first mapping of them to "weitere Sprechrolle" (2532c59) was reverted in 806a2f1: chairing is never a Rede (CONTEXT.md, Sitzungsleitung), and a Präsident speaking from the lectern speaks "like any other Redner". They stay unmapped (fail-fast) until rule 5 is extended.

## Finding 2: unexplained DIP timeouts

- Batch 1 sent 487 requests in 9,269 s:
  - `/person/{id}` 301 (196 distinct);
  - bundestag.de 66 (roll-call list and votes);
  - `/vorgangsposition` 54;
  - `/plenarprotokoll` 48 (the whole catalog);
  - `/aktivitaet` 12;
  - dserver 6.
- After about 250 requests at 0.5 s spacing, every `/person` lookup timed out: 26 persons × 3 attempts × 60 s. As a result, 18/154 took 3,058 s and 18/150 took 1,857 s, against 27–45 s for the three sittings before.
- Spot probes of two of the failed ids later answered in 0.1–0.35 s.
- Batch 2, hours later at 1.0 s spacing, stalled on its very first catalog request, right after curl probes had answered quickly. A rate limit does not explain a stall on the first request.
- On 2026-10-20 one request through the project's `ApiClient` and one through curl both answered in under 0.2 s, so it is not the request's shape: DIP itself stopped answering for periods, for a reason not visible from here.
- So a safe sustained rate is not known, and 0.5 s is not shown to be safe.

Changes made from this:
- **e547eae:** after 3 consecutive `/person` failures, a sitting stops looking up persons.
- **D5 cache:** it removes the 35% repeat lookups (301 vs 196).
- The backfill default sleep stays 0.5 s in code until a rate is measured.

### DIP `/person` probe, 2026-10-22 (pilot re-run, step 1)

The planned measurement was small bursts of `/person/{id}` at 2 s and then 1 s spacing, with a stop on the first failure or answer over 10 s and no retry (`~/agent-runs/a3/round2/person_probe.py`, log `person-probe.log`).
- dserver answered the first probe: `19/19001.xml`, 200 in 0.39 s.
- DIP did not. The first request, `/person?f.wahlperiode=18` at 14:01 UTC, timed out after 30 s, so no `/person/{id}` request was sent.
- The same API had answered all 17 `/aktivitaet` sittings of the 6c check, at 2 s spacing and at most 0.25 s, about an hour earlier.
- That makes 63 DIP requests that day before the timeout, all with the project key.

So DIP stopped answering after a few dozen requests at 2 s, not after hundreds. As in batch 2 (2026-10-19), a rate limit does not explain it. The pilot re-run stopped here, as its brief says, and nothing was retried. A sustainable DIP rate is still not known.

### DIP `/person` probe, 2026-10-22 evening (pilot re-run)

The probe ran at 18:26 UTC, about 4.5 h after the timeout above.
- **Single probes:**
  - dserver `19/19001.xml`: 200 in 0.39 s.
  - DIP `/plenarprotokoll?f.dokumentnummer=19/1`: 200 in 0.32 s.
- **`person_probe.py`:**
  - 1 `/person` list request;
  - 20 `/person/{id}` at 2 s spacing (18:26);
  - after a pause of about 1 min, 20 more at 1 s spacing (18:27).
- **Result:** all 41 answered 200. The slowest took 0.21 s and the mean was 0.10 s. There were no failures and nothing was retried.

So at this hour DIP answered `/person` normally at 1 s spacing. The pilot run that followed timed out on its first request (see "Result" below), so this probe does not settle the question of a request-count limit.

### Rate measurement, 2026-10-20 (dserver.bundestag.de)

The WP 18/19 XML download (`~/agent-runs/a3/tools/fetch_wp18_19.py`; one line per request in `~/agent-runs/a3/wp18-19-fetch.log`, probes in `dserver-probes.log`). Each request is one plenary XML of about 0.7 MB.

| Window (CEST) | Spacing | Requests answered | Then |
|---|---:|---:|---|
| 15:52–15:53 | 3 s | 20 of 20, ≤ 0.36 s | burst ended as planned |
| 15:53–15:57 | 2 s | 73 of 73; the last one took 35 s | 3 timeouts of 60 s; stopped |
| 16:20 | probe | none | still blocked (30 s timeout) |
| 18:51–18:59 | 5 s | 70 (one stop was a bug in my script, the UTF-8 BOM check); the last three took 19–35 s | 1 timeout; stopped |
| 19:15 | probe | none | still blocked |
| 20:39–20:45 | 5 s | 63; the last one took 19 s | stopped on the slow answer, before a timeout |
| 21:11, 21:31 | probe | none | still blocked |
| 21:52–21:58 | 5 s | 61, no slow answer first | 1 timeout; stopped |
| 22:18 | probe | none | still blocked |
| 22:38–22:39 | 5 s | 2; the second took 36 s | stopped on the slow answer |
| 22:59–23:01 | 5 s | 20 of 20 | download complete (484 files) |

DIP (`search.dip.bundestag.de`) and `www.bundestag.de` answered normally (0.2–0.3 s) whenever dserver was blocked.

What it shows:
- **The block is a budget, not a rate.** dserver stops answering after about 60–90 requests, roughly 45–65 MB, within a few minutes. That holds at 2 s and at 5 s spacing. Slower spacing did not buy more requests per window.
- **Warning sign:** answers usually slow to 19–36 s just before the cutoff, though not always (21:58). Stopping at the first answer over 10 s (`--slow-stop 10`) ended two windows before a timeout.
- **Block length:** 20 to about 65 min. Probes were still blocked 33 and 46 min after the 20:45 stop, and dserver answered again at 66 min. After the 21:58 cutoff it answered at 40 min, but only 2 files went through before it slowed. The budget seems to refill gradually, not reset all at once. 20 more files went through after another 20 min.

**Proposal for the backfill `--sleep` (not changed in code):** keep spacing at 2 s for dserver, because spacing does not matter within a window. What matters is a per-window cap: about 50 XML downloads, then a pause of about 60 min, and a stop on the first answer over 10 s. For DIP, nothing in today's runs re-measures Finding 2's `/person` timeouts. The 6c cross-check sent 6 DIP requests at 2 s, all under 0.2 s. A WP 18/19 backfill of ~484 sittings needs about 10 such windows for the XML alone, so it spans hours, not minutes.

## Census

**Roles** (`<rolle_lang>`, 31 files): 46 mapped, plus:
- the presidium roles above, deliberately left unmapped;
- "B undesministerin für Bildung und Forschung" (19/100 Karliczek, a typo in the XML), now mapped to the Bundesregierung (2532c59).

**Fraktion strings** and what `derive.zusammenschluss` makes of them:
- Mapped already: AfD, CDU/CSU, DIE LINKE → Die Linke, FDP, SPD, fraktionslos / Fraktionslos → fraktionslos, `BÜNDNIS\xa090/DIE GRÜNEN` (no-break space).
- New, added in 2532c59: `BÜNDNIS 90/DIE GRÜNE N` (19/100) and `BÜNDNIS 90/ DIE GRÜNEN`. The second occurs in 8 WP 18 files, but in the samples only in the Inhaltsverzeichnis.
- None unknown after that.
- No dotted "DIE LINKE." was seen.

**Einzelplan tables:**
- Taken from the Einzelplan headings of the two budget weeks; now in `EINZELPLAN_TO_POLITIKFELDER` (2532c59).
- Ministry cuts that differ from WP 20/21:
  - WP 18: Bau sits in Einzelplan 16 (Umwelt, Naturschutz, Bau und Reaktorsicherheit);
  - WP 19: Bau sits in 06 (Innern, für Bau und Heimat);
  - both WPs: 12 is Verkehr und digitale Infrastruktur.
- WP 18 Einzelplan 21 (BfDI, its own plan from 2016) is not in the Nov 2014 evidence and stays `einzelplan_unknown`.
- A3 Phase 4 checks the full store against the table (the real-store test now reads every WP).

**Roll-call votes:**
- In the 5 acquired sittings, each scan ended `date_passed` at a budget of 90 pages, and 2 votes matched 2 TOPs.
- No vote-page Fraktion strings beyond the ones above.

**abgeordnetenwatch:** not measured. `aw-profiles` is not a default enrichment, and the pilot did not enable it.

**Identity:** in 19/1 Schäuble's chair markers carry Solms's Redner-ID 11002190. That is another shared-id case like 11005304; it is to be checked when 19/1 is acquired.

## Time and memory

- Not measurable as planned: nothing reached persist or render.
- Batch 1 peak RSS was 1.33 GB, from acquisition only.
- From the gate run on 290 Sitzungen ([gate record](a3-gate-validation.md)):
  - `--offline --repersist` 453 s and 2.6 GB;
  - a plain `--offline` render 335 s and 1.5 GB.
- At about 800 Sitzungen and linear growth that is about 21 min and 7 GB for a repersist. This is an estimate, and above the plan's 3.6 GB.
- Disk: 22 GB free on 2026-10-20. A full store and site is estimated at 8 GB, plus clones.

## Known limit of the exclusion list (D2)

Superseded. Since 27a93d5 a listed sitting is skipped before acquisition, whatever the parser says, so an unmapped role in it no longer ends the run. Since the commit after abd3ddf, offline runs and `--fetch-xml` also leave out every sitting `data/coverage-exclusions.json` lists, so a report cached before its sitting was listed stays out of the store.

## What is open before Phase 3

1. **Extend speech rule 5 to the WP 18/19 encodings** (Finding 1, four kinds). Without it, D4 stops roughly 100–150 WP 18/19 sittings. This is a counting-rule change (A1 territory) and needs a decision.
2. **A sustainable request rate** (Finding 2). Both DIP and dserver.bundestag.de stopped answering us after a few hundred requests: dserver after about 150 XML downloads at 1 s spacing on 2026-10-20. Re-measure with a smaller burst before choosing the backfill default, and finish the WP 18 census when dserver answers again.
3. **Pilot re-run** with 1 and 2 settled, to measure seconds per sitting, peak RSS of persist and render, and the abgeordnetenwatch share.

## Pilot re-run, 2026-10-22

### Setup

- **Clone:** `~/agent-runs/a3/pilot` is a copy-on-write clone (`cp -c`, APFS) of `.context/dip-pulse-site`. It costs almost no disk until files change. Free disk was 8–9 GB before the run and 5.1 GB after the repersist.
- **Repersist:** `--offline --repersist` with speech rules v6, at 5cc5982.
  - Exit 0, 290 reports persisted, store replaced.
  - **Time:** 665 s (the gate took 453 s).
  - **Peak RSS:** 2.36 GB (the gate took 2.6 GB).
- **Probes:** see Finding 2, 2026-10-22 evening.
- **Sample (27 sittings):**
  - the 21 of `a1-turn-investigation.md:17`;
  - first and last of each WP: 18/1, 18/245, 19/1, 19/239;
  - the nearest that parse with mapped roles: 18/4, 18/244, 19/2, 19/238.
  - 8 of the 27 are on the 84-number list and test the D2 skip: 18/1, 18/10, 18/50, 18/245, 19/1, 19/13, 19/32, 19/239.
  - Befragung, Fragestunde and Aktuelle Stunde occur in each WP: 18/154, 18/217, 19/10, 19/79, 19/100, 19/145.
- **Settings:** `--sleep 2`, `--vote-scan-pages 90`, the 84 numbers via `--exclude-document-number`, and the default enrichment. A disk watchdog stops the run below 1.5 GB free. The argument list is `~/agent-runs/a3/pilot-args.txt` and the log is `~/agent-runs/a3/pilot-run.log`.

### Result: stopped by DIP before the first sitting

- The run started at 18:37:21 UTC. Its first DIP request was the catalog (`/plenarprotokoll`, page 1). It timed out three times (60 s each, with the client's 2 built-in retries) and the run ended at 18:40:41 with exit 1.
- **Nothing was acquired.** No sitting was fetched and the store was not touched; it is still the repersisted v6 store. The run took 185 s with a peak RSS of 97 MB.
- **What DIP answered before:**
  - 41 `/person` requests at 18:26–18:27, at 2 s and 1 s spacing, all fast;
  - one curl `/plenarprotokoll` at 18:26.
  - About 10 minutes later the first request of the run did not answer.
- **This is the third time,** with the same shape each time:

| When | Requests answered first | Spacing | Then |
|---|---:|---|---|
| 2026-10-19, batch 2 | many earlier in batch 1 | 1 s | the first catalog request stalled |
| 2026-10-22, 14:01 | 63 | 2 s | the first `/person` list request timed out |
| 2026-10-22, 18:37 | 43 | 2 s and 1 s, then a pause of about 10 min | the first catalog request timed out |

- **A hypothesis, not established:** DIP stops answering this key or IP for a while after roughly 40–60 requests in a window of unknown length. Batch 1's ~250 requests at 0.5 s before its timeouts do not fit a plain count. The window and the recovery time are both still unmeasured.
- **What a re-run needs:**
  1. Leave DIP idle for several hours.
  2. Start the pilot directly, with no probe burst that spends the budget first.
  3. Log every DIP request with its time, so the point where DIP stops is known exactly.
- **Not a local fault:** at 18:43 UTC, three minutes after the timeout, dserver answered `19/19002.xml` with 200 in 0.29 s.
- The full catalog fetch opens every run, so it counts against any DIP budget.
- **Open before Phase 3:** the scan found 9 Vizepräsident(in) markers with a Fraktion inside someone else's `<rede>`. They are read as Sitzungsleitung. Five are in sittings that will be counted: 18/79, 18/85, 18/91, 18/96 and 18/109. In 18/62 and 18/90 the same presidium reading misclassified a Vizepräsidentin acting as an MdB, so these 9 need one read: if any is her own Zwischenfrage, it is silently dropped.
- **Not done:** the Phase 1 measurements (Sprechrollen, Fraktion strings, Einzelplan, abgeordnetenwatch share, roll-call match rate, rate and seconds per sitting, render RSS, extrapolation) and the identity check.
