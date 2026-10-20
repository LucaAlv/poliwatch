# A3 Phase 1: WP 18/19 pilot (2026-10-19/20)

Plan: [a3-coverage.md](a3-coverage.md), Phase 1. Status: **stopped early**. Two findings break the plan's assumptions and need decisions before Phase 3 (end of this file).

## What ran

- Clone `~/agent-runs/a3/pilot` of the gate-validated `~/agent-runs/a3/gate` ([gate record](a3-gate-validation.md)).
- Batch 1, code 43ab74d (= v0.20.0.0 plus the gate script): the 11 WP 18 sittings of the sample, `--vote-scan-pages 90 --sleep 0.5`. 5 acquired (18/245, 18/217, 18/200, 18/154, 18/150), then 18/100 stopped the run with `SprechrolleError: no Sprechrolle rule maps the role "Präsident"`. Nothing was persisted.
- Batch 2, code e547eae (lanes A–D), `--sleep 1.0`, the other 18 sittings: DIP timed out on the very first catalog request for 32 minutes. I stopped it; no data.
- Census without DIP: the 23 sample XML files plus the budget weeks 18/68–71 (Nov 2014) and 19/63–66 (Nov 2018), downloaded once from dserver.bundestag.de (public, 1 s apart), parsed with the current parser and read for roles, Fraktion strings and Einzelplan headings.

## Finding 1: the parser rejects about a third of WP 18/19 sittings (D4)

The current parser (speech rule 5) rejects **10 of 31** WP 18/19 XML files with `unresolved nested contribution`:

| Sitting | Locator |
|---|---|
| 18/1 | TOP 2, ID1800100100 marker 2 |
| 18/10 | TOP 3, ID1801002600 marker 2 |
| 18/50 | TOP 1 (Fortsetzung), ID1805001800 marker 4 |
| 18/70 | TOP I (Fortsetzung), ID1807005100 marker 2 |
| 18/71 | TOP I (Fortsetzung), ID1807101000 marker 3 |
| 18/100 | TOP 3, ID1810000300 marker 3 |
| 19/1 | TOP 3, ID19101200 marker 2 |
| 19/13 | TOP 1, ID191304800 marker 2 |
| 19/32 | Einzelplan 23, ID193207500 marker 3 |
| 19/239 | TOP 2, ID1923903200 marker 6 |

Accepted (21): 18/13, 18/68, 18/69, 18/84, 18/150, 18/154, 18/200, 18/217, 18/245, 19/10, 19/50, 19/63–66, 19/79, 19/100, 19/145, 19/150, 19/200, 19/208.

**Cause, read from the XML.** WP 18/19 protocols encode the chair inside another member's `<rede>` as a `<p klasse="redner"><redner …>` marker whose `<rolle_lang>` is Präsident, Vizepräsident(in) or Alterspräsident. Examples:
- 18/100: Präsident Lammert's "Herr Kollege." inside Carsten Schneider's Rede;
- 18/1: Alterspräsident Riesenhuber running the election inside Kauder's Rede;
- 19/13: in the Befragung, the minister hands a question to a Staatssekretär.

WP 20/21 encode the chair as a `<name>` element, which the parser already treats as Sitzungsleitung. The nested-marker rule therefore meets a turn it cannot classify and refuses the sitting, as D4 says it must.

**Extrapolated:** about 32% of 484 WP 18/19 sittings, so roughly 155, would stop the backfill. The reviewed exclusion list (D2) was designed for rare refusals. Listing about 155 sittings would leave a third of WP 18/19 uncovered. The fix belongs in the parser (a rule 6 for presidium markers nested in a Rede), with its own counting record like [offline-v5-validation.md](offline-v5-validation.md).

**The same encoding explains the unmapped roles.** The presidium roles Präsident (18/100, 19/1), Vizepräsident(in) (18/245) and Alterspräsident (19/1) occur in this census only as these nested chair markers. A first mapping of them to "weitere Sprechrolle" (2532c59) was reverted in 806a2f1. Chairing is never a Rede (CONTEXT.md, Sitzungsleitung), and a Präsident speaking from the lectern speaks "like any other Redner". So they stay unmapped (fail-fast) until the rule-6 decision.

## Finding 2: DIP throttles the pilot's request rate

- Batch 1 sent 487 requests in 9,269 s:
  - `/person/{id}` 301 (196 distinct);
  - bundestag.de 66 (roll-call list and votes);
  - `/vorgangsposition` 54;
  - `/plenarprotokoll` 48 (the whole catalog);
  - `/aktivitaet` 12;
  - dserver 6.
- After about 250 requests at 0.5 s spacing, every `/person` lookup timed out: 26 persons × 3 attempts × 60 s. As a result, 18/154 took 3,058 s and 18/150 took 1,857 s, against 27–45 s for the three sittings before.
- Spot probes of two of the failed ids later answered in 0.1–0.35 s.
- Batch 2, hours later at 1.0 s spacing, stalled on its first catalog request.
- So the safe rate is not known yet. 0.5 s is not safe for a sustained run.

Changes made from this:
- **e547eae:** after 3 consecutive `/person` failures, a sitting stops looking up persons.
- **D5 cache:** it removes the 35% repeat lookups (301 vs 196).
- The backfill default sleep stays 0.5 s in code until a rate is measured.

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

## What is open before Phase 3

1. **Parser rule for presidium markers nested in a Rede** (Finding 1). Without it, D4 stops about a third of WP 18/19 sittings (10 of 31 sampled). This is a counting-rule change (A1 territory) and needs a decision.
2. **A sustainable DIP request rate** (Finding 2). Re-measure with a smaller burst before choosing the backfill default.
3. **Pilot re-run** with 1 and 2 settled, to measure seconds per sitting, peak RSS of persist and render, and the abgeordnetenwatch share.
