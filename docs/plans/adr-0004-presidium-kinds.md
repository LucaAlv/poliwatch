# ADR 0004 kinds: Ansprache, Sitzungsleitung, Fraktionsrede

Plan for TODOS.md roadmap Stage 1, item 2, "Tell official addresses and presidium Reden apart from Fraktionsreden (ADR 0004)". Written 2026-11-10 on `claude/correctness-gate-fixes-b22045` (main at 28799ac, v0.36.0.0). Plan only: nothing here is built.

## Binding decisions

These are settled and not reopened by this plan:

- **ADR 0004** (owner, 2026-10-20): the presidium has no Sprechrolle; Sitzungsleitung is never a Rede; an official address is not counted as a Fraktionsrede automatically; until detection exists such a turn is refused, not counted.
- **Q13 A** (owner in chat, 2026-11-06, `docs/plans/v1-scope-review.md:160,200`): a `<rede>` with a presidium `rolle_lang` is one of three kinds. Sitzungsleitung is excluded. An official address is its own kind, shown on the Dossier and in no Fraktion's Reden count. A debate Rede counts for the Fraktion. "The build first lists every case in WP 18/19; hard cases return to the owner. Moved counts are reported old and new."
- **Round 2 decision 2** (owner, 2026-10-22, `docs/plans/a3-wp18-19-round2-result.md:176-187`): a Vizepräsident(in) who owns a `<rede>` and is printed with a `<fraktion>` gives that Fraktion's Rede (`mark_presidium_fraktionsreden`, 5cc5982). All 24 such cases were reviewed: 19 debate Reden, 5 Befragung questions, no address and no chair text.
- **Round 3 decision 1**: 18/62 and 18/90 (a Vizepräsidentin's Fragestunde Nachfrage outside any `<rede>`) stay excluded. Not this item.
- **ADR 0002 and CONTEXT.md "Beitrag"**: what is not a Rede is a Beitrag in `contributions`, typed by `kind`, counted on its own, adding to no figure defined over Reden.
- **N1, N7, N8, N9** and the withholding eng review D1-D10 (`docs/plans/v1-scope-review.md:491-1260`): bind the coverage gate, which this item feeds.

## Problem

Three facts about the code on main:

1. **Nothing reads a presidium-owned `<rede>` for what it is.** `mark_presidium_fraktionsreden` (`scripts/validate_dip_protocol.py:916-934`) handles only a Vizepräsident(in) printed with a Fraktion. Every other `<rede>` whose first marker carries Präsident, Vizepräsident(in) or Alterspräsident (`SITZUNGSLEITUNG_ROLE`, `:828`) is labelled a Rede by `speech_kinds.classify_reden` (`scripts/speech_kinds.py:368-451`) and keeps its role. No `SPRECHROLLE_RULES` entry maps that role (`scripts/derive.py:277-306`), so strict persist (`derive.check_sprechrollen`, `:376`) stops the whole run with one `ERROR [sprechrolle]` line.
2. **So those sittings cannot be in any store.** The D2 exclusion record keeps them out before acquisition (`data/coverage-exclusions.json`, round 3 decision 6). The current store therefore holds no presidium-owned Rede without a Fraktion, and no address counted for a Fraktion through this path.
3. **The guests of the same sittings fail the same way.** 18/223 (the joint sitting with the Bundespräsident and the Präsidentin des Bundesrates) and 19/9 (the Präsident der Assemblée nationale) carry roles no rule maps either (`a3-wp18-19-round2-result.md:148`). CONTEXT.md's "Gastansprache" entry says the XML never records a guest address; for WP 18/19 joint and ceremonial sittings that is false.

### Why seven sittings wait on this item

TODOS.md "Coverage gate before the first data release" (`TODOS.md:69`) lists 18/178, 18/223, 18/245, 19/1, 19/9, 19/19 and 19/73 as waiting on this item. All seven **parse and raise no refusal**; they are kept out only by D2 (`a3-wp18-19-round2-result.md:229`). N1's withholding acts on refused `<rede>` units, so it does not reach them (`v1-scope-review.md:301`, outside finding 1). Admitting them today would either stop the run on their unmapped presidium or guest roles, or, where a Präsident is printed with a Fraktion, count an address as that Fraktion's Rede.

| Sitting | What it holds (recorded) | Source |
|---|---|---|
| 18/178 | a Lammert address | round 2 result :148 |
| 18/223 | joint sitting: Bundespräsident, Präsidentin des Bundesrates, Lammert | round 2 result :148 |
| 18/245 | Bulmahn's farewell address `ID1824501400`, Singhammer's announcement of an election result `ID1824502300`, both without Fraktion | TODOS :498-501, rule-5 validation :145 |
| 19/1 | Alterspräsident `<rede>`s `ID19100100`, `ID19100200`, `ID19101000`, `ID19101200`; Schäuble's inaugural address `ID19101300`; his chairing `ID19101900` | TODOS :499, rule-5 validation :136-139 |
| 19/9 | Schäuble and the Präsident der Assemblée nationale | round 2 result :148 |
| 19/19 | the Präsident: oath and government formation | round 2 result :148 |
| 19/73 | a Schäuble address | round 2 result :148 |

Two more sittings touch this item without being among the seven:

- **18/1** is refused, not just listed: Lammert's nested "Herr Alterspräsident, lieber Kollege Riesenhuber, ich nehme die Wahl gerne an." at `ID1800100100` marker 2 is not the bare acceptance `ELECTION_ACCEPTANCE` (`validate_dip_protocol.py:831`) matches (`a3-wp18-19-blockers.tsv:2`). Behind it waits his inaugural address.
- **18/215** is refused for a recipients mismatch (`a3-wp18-19-blockers.tsv:148`) and has a presidium owner marker without a Fraktion (`a3-wp18-19-round2-result.md:184`). Once W3 withholds its refused Rede, that presidium `<rede>` would stop the run on its role unless it has a kind.

**What happens to them under this plan:** each presidium or guest `<rede>` in the seven gets a reviewed kind, so all seven parse into correct units with no unmapped role left. They leave the exclusion record in T4's fetch of the 85 (`--include-document-number`, online), then take the N8 merge-and-attribution review like every restored sitting. 18/1 additionally needs the acceptance rule (P4 below). 18/215 gets its entry now and leaves the list once W3 withholds its refused Rede. None of them leaves the list in this PR: no fetch and no repersist happen here.

## Scope

**In:**
- The three Q13 kinds for every `<rede>` whose first marker carries a presidium role, in WP 18-21.
- The guest and joint-sitting addresses of the same sittings, as the same kind.
- The two procedural turns the seven sittings and 18/1 need: the elected Präsident's acceptance with a salutation, and the oath answer.
- A presidium address printed as a marker inside another `<rede>` (18/1 if the inventory shows it there).
- Persist, export, site labels, CONTEXT.md, ADR 0004, `docs/data-methods.md`, the data dictionary, tests.

**Not in:**
- Fetching or admitting any sitting. T4 does that.
- The Fragestunde Nachfragen of 18/62 and 18/90 (round 3 decision 1).
- Addresses a WP 20/21 protocol prints as `<name>` chair text. They are already outside every count; showing them is a display gap (deferred, below).
- The known misses inside presidium markers of other speakers' Reden, 18/96 and 18/109 (`a3-pilot.md:202-216`): a separate rule (deferred, below).

## Decided kinds

| Kind | What it is | Assigned in | Stored | Counts |
|---|---|---|---|---|
| **Fraktionsrede** of a presidium MdB | A debate contribution of an MdB who holds the office | parser, `mark_presidium_fraktionsreden` (existing, Vizepräsident(in) printed with a Fraktion) | `speeches`, role removed, `sprechrolle` NULL | every Reden figure, for the printed Fraktion (ADR 0001) |
| **Ansprache** (new Beitrag kind `ansprache`) | An address that is no contribution to a debate: given for the Bundestag by its Präsident(in), Vizepräsident(in) or Alterspräsident(in) (opening of a constituent sitting, inaugural address, Gedenkworte, farewell, welcome to a guest), or by a guest or another constitutional organ at a ceremonial or joint sitting | parser, from the reviewed list (P1) | `contributions`, `kind = 'ansprache'`, `sprechrolle` NULL, `fraktion` as printed, `mp_id` bound | none: no Reden count, no Redeanteil, no per-person Reden, no fact, no recipe. Counted on its own by kind |
| **Sitzungsleitung** `<rede>` | Chairing printed as a `<rede>` of its own: giving the floor, election procedure, announcing results, administering an oath | parser, from the reviewed list (P1) | not stored; one `procedural` entry per own turn in the TOP's `xml_turn_diagnostics`, evidence `Sitzungsleitung (reviewed): <reason>` | none, and not shown, as for a nested presidium marker (6d) |
| **Procedural turn** (acceptance, oath) | "Ich nehme die Wahl an" with a salutation (18/1); the answer to an oath ("Ich schwöre es, so wahr mir Gott helfe.") | parser, regex sub-rules P4 and P5, same place as 6d's acceptance | not stored; `procedural` diagnostic | none, not shown |

One kind for presidium and guest addresses, not two: their treatment is identical (shown, counted nowhere), the speaker and role on the card say who spoke, and CONTEXT.md's Gastansprache already decided a guest address counts toward nothing. The entry is folded into **Ansprache** (decision O1).

## Design

### P1. A reviewed list, not a detector

Round 2 established that only the printed Fraktion separates a debate Rede from an address, and that the code cannot tell a debate item apart (`a3-wp18-19-round2-result.md:186`). Content heuristics would turn a detection error into a count change (ADR 0002, Consequences). WP 18/19 has a few dozen cases; WP 20/21 has none of the Vizepräsident kind (`a3-wp18-19-round2-result.md:185`). So the kind of each case is reviewed and stored as data, in the pattern of `scripts/person_corrections.json`, where an entry the source does not match refuses the build.

New file `scripts/reviewed_units.json`. W3 also plans "a new reviewed list in `scripts/`" for its withheld units (`v1-scope-review.md:1183`). One file with a `kind` field serves both, so one module owns every reviewed decision about a unit and a Rede cannot be listed twice under two policies (decision O11). This PR creates it with two kinds; W3 adds `withhold`.

```json
{
  "entries": [
    {"sitting": "19/1", "rede_id": "ID19101300", "redner_id": "<owner's id>", "kind": "ansprache",
     "reason": "Schäuble's address after accepting the election as Präsident"},
    {"sitting": "19/1", "rede_id": "ID19101900", "redner_id": "<id>", "kind": "sitzungsleitung",
     "reason": "chairs the election of the Vizepräsidenten"},
    {"sitting": "18/1", "rede_id": "ID1800100100", "marker": 3, "redner_id": "<Lammert's id>", "kind": "ansprache",
     "reason": "inaugural address printed inside the Alterspräsident's rede (only if the census shows it there)"}
  ]
}
```

- `rede_id` is the id the source prints under `sitzungsverlauf`, before `split_nested_reden`; annex `<rede>`s are not searched. The entry applies to the owner's part. A part that 6c splits off (`<id>:<n>`) is another speaker's Rede and is untouched. An id the sitting prints twice (the code already guards duplicates, e.g. `sum(r.get("id") == ...) == 1` at `validate_dip_protocol.py:1496`) cannot be listed: the entry refuses as ambiguous.
- `marker` (optional) names the raw marker ordinal inside the source `<rede>`, counted before any split, as `xml_turn_diagnostics.marker_ordinal` counts it for an unsplit Rede. Only `ansprache` takes a marker. The named marker must not be the owner's, must match `redner_id`, and must lie before any 6c split point of that `<rede>`; otherwise the entry refuses. It need not carry a presidium role: 18/1 prints Lammert's acceptance marker as "Norbert Lammert (CDU/CSU)" with no role (`a3-wp18-19-blockers.tsv:2`). Its segment becomes a nested Beitrag `nested:<rede_id>:<marker>` of kind `ansprache`, branched before the 6d `sitzungsleitung` check, the Zwischenfrage path and the strict side lookup (`side = derive.sprechrolle(segment["speaker"])`, `validate_dip_protocol.py:1594`, which would otherwise raise `SprechrolleError` on "Präsident", an exception the online `except (ET.ParseError, ValueError)` at `:4143` does not catch).
- `redner_id` is the proof of identity: the owner marker's (or the named marker's) `<redner id>`, first id per `derive.first_redner_id`.
- **Loaded and validated once at startup**, not inside a parse: `speech_kinds.load_reviewed_units()` is called by `build_dip_pulse_site.main`, `validate_dip_protocol.main` and `extract_demo_fixture`, and raises a dedicated `ReviewedUnitsError` that stops the run. Raised inside `parse_protocol_xml` as a `ValueError`, a malformed file would read as "protocol source rejected" for every sitting (`validate_dip_protocol.py:4143-4144`). Checks: an object with exactly `entries`; each entry with exactly the keys above; `sitting` matching `^\d{2}/\d{1,3}$`; `kind` in {`ansprache`, `sitzungsleitung`}; `marker` a positive int and only with `ansprache`; `reason` non-blank; no two entries with the same (sitting, rede_id, marker), and no Rede listed under two kinds. Each failure names the entry (checklist class 9).
- **Applied in a pre-pass** `mark_reviewed_units(root)`, the first tree edit after W2's inventory and before `mark_presidium_fraktionsreden`, so a listed Vizepräsident(in) Ansprache keeps its printed role for the card. `mark_presidium_fraktionsreden` skips a `<rede>` that carries `reviewed_kind`. The pre-pass sets `reviewed_kind` on the `<rede>` (or on the named marker's `<p klasse="redner">`). It refuses, naming the sitting and entry, when an entry of this sitting names a `<rede>` or marker the XML lacks, or a different `redner_id` (a stale or misapplied entry).
- An entry wins over the Fraktion rule. The review of the 24 Vizepräsident(in) Reden found no address among them; the order only makes the list authoritative.

### P2. Fail closed

A `<rede>` whose owner marker still carries a presidium role after `mark_presidium_fraktionsreden` and has no `reviewed_kind` is refused per Rede, located:

`<wp>/<nr> <top-id>: presidium Rede at <rede_id> has no reviewed kind (scripts/reviewed_units.json, ADR 0004)`

That covers a Präsident(in) or Alterspräsident(in) printed with a Fraktion, which the Vizepräsident rule does not reach, and any presidium `<rede>` a future WP 21 sitting prints. Today such a `<rede>` reaches persist and stops the whole run; afterwards the parser refuses its sitting with the Rede named.

**Where it is raised.** Not in `classify_reden`: the withholding eng review counts a classification refusal as one that cannot be narrowed to a Rede (`v1-scope-review.md:499`). `classify_reden` returns a placeholder label `UNREVIEWED_PRESIDIUM` that does not touch its running state (P3), and the per-Rede loop raises. W3 identifies a withholdable refusal by a typed `ValueError` subclass carrying `rede_id` and marker, not by the message text (`v1-scope-review.md:799`). If W2/W3 has introduced that type when this PR lands, P2 raises it; otherwise P2 raises a plain `ValueError` and W3 adopts it (decision O6).

Guest roles stay with the existing check: an unlisted guest `<rede>` still fails `check_sprechrollen` with the role named.

**Presidium owners printed without a role.** P2 sees only a `<rolle>`. A chair printed as a plain MdB owner (the role-less chair of 18/10 and 21/17, `mark_roleless_chairs`, `validate_dip_protocol.py:877-913`) who gives an address would be counted for their Fraktion silently. Census group 7 lists every `<rede>` whose owner chairs that sitting by the same test `mark_roleless_chairs` uses; each such `<rede>` that is not a debate Rede gets a list entry. No code rule is added for them.

### P3. Where each label is set and how it flows

```
load_reviewed_units()             NEW, at startup: malformed file -> ReviewedUnitsError, run stops
parse_protocol_xml(xml)                                  validate_dip_protocol.py:1410
  adopt_reden_outside_tops                               (W2 inventories ids here, before any edit below)
  mark_reviewed_units             NEW: list -> reviewed_kind on <rede> / marker; stale or ambiguous entry refuses
  mark_presidium_fraktionsreden   Vize + Fraktion -> role removed, Fraktionsrede; skips listed <rede>s
  mark_roleless_chairs
  per TOP:
    split_nested_reden            in a listed sitzungsleitung <rede> the owner's own turns count as chair
                                  text, so a debate Rede printed inside it splits off (6c); split parts
                                  carry no reviewed_kind
    classify_reden                NEW: ansprache -> RedeLabel(ANSPRACHE); sitzungsleitung ->
                                  RedeLabel(SITZUNGSLEITUNG); unlisted presidium owner -> placeholder.
                                  None of them changes previous, previous_rede, main_id or opening;
                                  a sitzungsleitung <rede>'s own text joins `between` (it is chair text)
    per-Rede loop                 placeholder -> P2 refusal (typed, located)
                                  sitzungsleitung -> procedural_reden + one diagnostic per own turn;
                                  any other nested turn in it refuses unless P4, P5 or 6d covers it
                                  marker named ansprache -> nested ansprache unit (before 6d, Zwischen-
                                  frage path and the strict side lookup at :1594)
                                  acceptance with salutation (P4), oath answer (P5) -> procedural
    emit (:1628-1634)             ansprache -> contributions; sitzungsleitung -> nothing (the else
                                  branch must drop it: procedural_reden filters only speeches)
persist_contributions             kind ansprache: sprechrolle NULL, fraktion as printed, mp bound
find_unmapped_sprechrollen        skips the role of an ansprache unit; a presidium role on a Rede is an error
```

**Why the running state matters.** `classify_reden` carries `between`, `previous`, `previous_rede`, `main_id` and `opening` across `<rede>`s (`speech_kinds.py:379-451`). A presidium `<rede>` has no `<name>`: its chair words are the owner's own paragraphs, so `trailing_sitzungsleitung_text` returns nothing for it (`:446`). If it simply took a turn in the loop, a Kurzintervention announced inside a Sitzungsleitung `<rede>` would lose its announcement and count as a Rede, an Erwiderung after one would fail `previous == KURZINTERVENTION`, and in a Befragung a listed `<rede>` would end the opening reports. So a listed `<rede>` is invisible to that state, and a Sitzungsleitung `<rede>`'s own text is added to `between`.

**Nested turns of other speakers in a listed `<rede>`.** In a Sitzungsleitung `<rede>` there is no Rede to interrupt, so a nested MdB turn cannot be a Zwischenfrage whose `parent_rede_id` points at it. It is either split off as a Rede (6c, with the owner's text as chair text), procedural (P4, P5, 6d), or refused. In an Ansprache `<rede>` the existing nested rules apply unchanged; census group 6 lists every such turn so the review sees them.

`SITZUNGSLEITUNG` and `UNREVIEWED_PRESIDIUM` are internal label values, not `CONTRIBUTION_KINDS` members: `validate_kind` keeps refusing them if they ever reach persist.

### P4. The acceptance with a salutation (18/1)

Widen `ELECTION_ACCEPTANCE` to one optional salutation clause and "gerne": `(?:(?:Herr|Frau) (?:Alters)?Präsident(?:in)?(?:, [^.!?]{1,60})?, )?[Ii]ch nehme die Wahl (?:sehr )?(?:gerne )?an\.` It still needs the chair's `ELECTION_QUESTION` before it and a full match of the turn, so "Ich nehme die Wahl an. Meine Antrittsrede." keeps refusing (`tests/test_a3_rule5.py:72`). This is a widening of an owner-approved sub-rule (6d) by one source-backed form (decision O3).

**A `<rede>` form too.** An acceptance printed as an MdB's own `<rede>` (the elected Vizepräsidenten of a constituent sitting may be printed so) is labelled a Rede today. If census group 4 finds one, the same full-match rule applies to a `<rede>` whose whole own text is the acceptance and whose preceding chair text ends with `ELECTION_QUESTION`: it is procedural. If that form sits in a kept sitting (20/1, 21/1), it is a live miscount: those Reden leave the counts, reported old and new.

### P5. The oath answer (19/19, and wherever the inventory finds it)

A turn whose whole text is `Ich schwöre es(?:, so wahr mir Gott helfe)?\.` (with "Ja," allowed before it), after a chair turn naming the Eid (`\b(?:Amts)?[Ee]id\b|schwören`), is procedural, nested or as a `<rede>` of its own. The full Art. 56/64 formula spoken as part of an address stays inside that Ansprache's text. Written only if the inventory shows oath answers that would otherwise refuse or count (decision O4). If the inventory finds oath answers already counted as Reden in kept WP 20/21 sittings, that is a live miscount and its figures move (step 1 measures it).

### Labels

| Where | Change |
|---|---|
| `speech_kinds.KIND_LABELS` | `ANSPRACHE: ("Ansprache", "Ansprachen")` |
| Dossier, TOP line (`render_dip_pulse_html.py:1910`) | unchanged code; reads "Weitere Beiträge, keine Reden und nicht mitgezählt: 1 Ansprache." |
| Dossier, Beitrag card (`render_dip_pulse_html.py:1868`) | for `ansprache` the label adds the printed role from the report: "Ansprache · Präsident", "Ansprache · Präsident der Assemblée nationale". No Fraktion colour on the dot (unchanged: contribution dots carry none). The store keeps no role, so when an A4 slice moves the Dossier onto the store (Q12) the suffix needs a stored role; recorded as an A4 requirement (decision O10) |
| Dossier, TOP with only an Ansprache (`render_dip_pulse_html.py:3054`) | unchanged: "Keine Reden; weitere Beiträge siehe oben" |
| Person page panel (`build_dip_pulse_site.py:9643-9645`) | intro gains "Ansprachen": "Zwischenfragen, schriftliche Beiträge, Kurzinterventionen, Erwiderungen, Ansprachen sowie Fragen und Antworten zählen gesondert." |
| Methodik "Was als Rede zählt", both places (`build_dip_pulse_site.py:10613` and `:12399`) | adds: "Ansprachen des Präsidiums oder von Gästen, etwa bei Gedenkstunden oder zur Eröffnung einer Wahlperiode, sind keine Reden und zählen für keine Fraktion. Sitzungsleitung zählt nie, auch wenn das Protokoll sie als eigene Rede druckt." |
| DESIGN.md "Reading a speech" (`DESIGN.md:377`) | one sentence for the restyle: an Ansprache is its own slip in document order, with origin line and name, no Fraktion bar, under a small heading "Ansprache" with the printed role and the note that it is not counted as a Rede; in the speaker list above the slips it shows "Ansprache" where a Rede shows the Fraktion |
| Table description `contributions` (`build_dip_pulse_site.py:157`) | adds "Ansprache (ansprache)" |
| `scripts/data_dictionary.json` `contributions.kind`, `.sprechrolle` | kind unit lists `ansprache`; sprechrolle says "bei ansprache immer NULL" |
| DATA.md | generated from the two above and `docs/data-methods.md` |

## Counts by kind

| Figure | Fraktionsrede (presidium MdB) | Ansprache | Sitzungsleitung `<rede>` | Procedural turn |
|---|---|---|---|---|
| Reden per Fraktion, Redeanteil, r2 Textanteil (`derive.ZUSAMMENSCHLUSS_SQL`) | yes, printed Fraktion | no | no | no |
| Reden per Person, r1, person page Reden | yes | no | no | no |
| TOP Reden count and Zeichen, r5 | yes | no | no | no |
| Facts (Reden metrics, erste Reden, `facts.py:382-424`) | yes | no | no | no |
| Beiträge by kind (TOP line, person panel, `compare_store_values` per kind, `validate_store_gate` kinds) | no | yes, as `ansprache` | no | no |
| Dossier | Rede slip | Beitrag card | not shown | not shown |

Every recipe (r1-r6, `build_dip_pulse_site.py:3460-3724`) reads `speeches`, and `facts.py` never reads `contributions`, so no recipe or fact SQL changes. Verified by grep on 28799ac.

## Versions

- **Speech rule `speech_kinds.VERSION` 7 → 8.** The rule changes what a presidium `<rede>` becomes. No kept sitting is expected to change, but the bump makes every store prove it was persisted under the new rule (`require_current_speech_rules`, `persist_dip_pulse_store.py:81`), and the full `--offline --repersist` it forces is owed anyway for E4. If W2 or W3 lands first with its own bump, this PR takes the next number.
- **Export format 16 → 17.** `contributions.kind` gains a code: a meaning change of an exported column (precedent: format 16 for E4's meaning change). Take the next free number at merge time; no pending slice has claimed 17 (`render-layer-and-order.md` and `a4-site-from-release.md` only say "the numbers after" schema 11 / format 16; W4 takes its numbers "after both fix branches land", `v1-scope-review.md:1196`).
- **Store schema stays 11.** No column or table changes; `contributions.kind` has no CHECK constraint (`persist_dip_pulse_store.py:334-353`).
- **Repersist:** one `--offline --repersist` of the reference store after merge, combined with the owed E4 repersist (whichever agent runs it).

## Steps

**Step 0 (prerequisite, data). The census.** Q13 says the build first lists every case. A read-only script under `docs/plans/adr-0004-census/` (scratch tooling, not shipped) scans every cached Plenarprotokoll XML: the reference store's 716 stored sittings (`data/xml/`) and W1's fetched XML of the 85. It lists, as `docs/plans/adr-0004-census.tsv`:
1. every `<rede>` whose first marker carries a presidium role, with Fraktion printed or not, after `mark_presidium_fraktionsreden`;
2. every `<rede>` whose owner role no Sprechrolle rule maps (guests);
3. every nested presidium marker inside another speaker's `<rede>` whose turn is longer than 600 characters (a candidate nested address);
4. every turn, nested or `<rede>`, matching the oath answer or the acceptance with any wording;
5. in WP 20/21, every `<rede>` in the constituent sittings (20/1, 21/1) and in the chancellor election and swearing-in sittings, with speaker, role, Fraktion and length: an Alterspräsident or Präsident address printed as an ordinary MdB `<rede>` (Fraktion, no role) would be counted for that Fraktion today;
6. every nested turn of another speaker inside each `<rede>` of groups 1, 2 and 7, with what the parser does with it today;
7. every `<rede>` whose owner chairs that sitting by `mark_roleless_chairs`'s test (a `<name>` chair element ending with the owner's first and last name), printed with no role.

Columns: sitting, rede_id, marker, redner_id, role, fraktion, chars, first 200 characters, proposed kind, reason. Each proposed kind is read against the PDF page. Hard cases go to the owner before step 2: any presidium `<rede>` printed with a Fraktion whose content is not debate, any `<rede>` mixing an address and chairing, any guest who is an MdB.

**Step 1. Measure the live store.** On a `cp -cR` copy of the reference store: count step 0's rows that are in kept sittings. Expected 0 for groups 1 and 2 (they would have stopped persist). Groups 4, 5 and 7 can be non-zero in kept sittings; any such unit is a figure that moves, reported old and new.

**Step 2. Parser and list.** `scripts/speech_kinds.py` (constants, label, loader and `ReviewedUnitsError`, `classify_reden` branches that leave the running state alone), `scripts/validate_dip_protocol.py` (pre-pass before `mark_presidium_fraktionsreden`, the skip in that function, the owner-as-chair case in `split_nested_reden`, the P2 refusal in the per-Rede loop, the nested Ansprache branch before `:1594`, the emit else-branch, P4 nested and `<rede>` forms, P5), `scripts/reviewed_units.json` (entries from step 0, owner-confirmed), the loader call in `build_dip_pulse_site.main`, `validate_dip_protocol.main` and `scripts/extract_demo_fixture.py`.

**Step 3. Persist and the role check.** `scripts/derive.py` `find_unmapped_sprechrollen`: skip an `ansprache` unit's role; a presidium role on an `xml_speakers` unit raises a dedicated error naming ADR 0004. `scripts/persist_dip_pulse_store.py` `persist_contributions`: for `ansprache` pass `sprechrolle` NULL (no strict lookup of the presidium or guest role).

**Step 4. Labels and versions.** The label table above; `speech_kinds.VERSION` and the version it records in `tests/fixtures/demo-report-21-84.json:860` (read by `tests/test_demo_site.py:271`); `EXPORT_FORMAT`; README's version history line (`README.md:301`).

**Step 5. Docs.** ADR 0004 amendment (the three kinds, the list, fail-closed, the procedural turns, one kind for guests); CONTEXT.md (new **Ansprache** entry, Gastansprache folded into it, the Beitrag kind list, Rede's "neither are" clause, Sitzungsleitung's "including a whole `<rede>`"); `docs/data-methods.md` (the verbatim CONTEXT quotes updated, and a German paragraph on the list and its cases); DESIGN.md "Reading a speech" (design review D1 below).

**Step 6. Tests** (next section) and the checks in Verification.

## Tests

New `tests/test_presidium_kinds.py`, plus updates where noted. Fixtures: real excerpts of 19/1 (`ID19101300`, `ID19101900`), 18/245 (`ID1824501400`, `ID1824502300`), 18/1 (`ID1800100100`), 18/223 and one 19/19 oath turn, with provenance in `tests/fixtures/a1-source-manifest.json`; synthetic XML for the edges.

| # | Behaviour | Test |
|---|---|---|
| T1 | A listed Ansprache `<rede>` is one `ansprache` Beitrag, no Rede | 19/1 `ID19101300`, 18/245 `ID1824501400` |
| T2 | A listed Sitzungsleitung `<rede>` stores nothing and leaves one `procedural` diagnostic per own turn | 19/1 `ID19101900`, 18/245 `ID1824502300` |
| T3 | An unlisted presidium `<rede>` without Fraktion refuses with the located message | replaces `test_without_a_fraktion_the_role_stays_unmapped` (`tests/test_a3_round2.py:359`) |
| T4 | An unlisted Präsident or Alterspräsident printed with a Fraktion refuses | replaces `test_the_praesident_is_not_covered` (`:368`) |
| T5 | An unlisted Vizepräsident(in) with a Fraktion is still that Fraktion's Rede; a listed one is an Ansprache | existing `:336` kept; one new |
| T6 | A stale entry refuses: missing `<rede>`, missing marker, wrong `redner_id`, an id printed twice, a marker after a 6c split point, a marker that is the owner's, an id found only in an annex | synthetic |
| T7 | Malformed list stops the run at startup with `ReviewedUnitsError`, never as "protocol source rejected": null, list instead of object, unknown key, unknown kind, `marker` on sitzungsleitung, duplicate entry, a Rede under two kinds, blank sitting, blank reason | synthetic, one subTest each |
| T8 | An entry for another sitting is not applied | synthetic |
| T9 | 6c: the split-off part of a listed Ansprache stays its speaker's Rede; a debate Rede printed inside a listed Sitzungsleitung `<rede>` splits off with the owner's text as chair text | synthetic |
| T10 | Running state: a Kurzintervention announced inside a Sitzungsleitung `<rede>` is still a Kurzintervention of the last real Rede; an Erwiderung after a listed `<rede>` still pairs; a listed `<rede>` in a Befragung does not end the opening reports | synthetic, three subTests |
| T11 | A marker named with `marker` becomes `nested:<rid>:<n>` `ansprache`, also with no role on the marker (18/1 form) and without reaching the strict side lookup; an unnamed presidium marker stays `procedural`; another MdB's nested turn in a Sitzungsleitung `<rede>` refuses | 18/1 if the census puts the address there, else synthetic |
| T12 | P4: 18/1's exact acceptance is procedural; acceptance plus a sentence still refuses; the `<rede>` form after `ELECTION_QUESTION` is procedural, without it a Rede | extends `tests/test_a3_rule5.py:56-80` |
| T13 | P5: the oath answer after an Eid prompt is procedural; the same words with no Eid prompt are not | 19/19 fixture + synthetic |
| T14 | A guest `<rede>` listed as Ansprache passes `check_sprechrollen`; an unlisted guest role still fails it | extends `tests/test_sprechrolle.py:314` |
| T15 | A presidium role on a Rede unit raises the ADR 0004 error | `tests/test_sprechrolle.py` |
| T16 | Persist: an Ansprache row has `sprechrolle` NULL, `fraktion` as printed, `mp_id` set; Reden counts and the r2 shares are unchanged by it | `tests/test_persist_dip_pulse_store.py`, `tests/test_sprechrolle.py:266` pattern |
| T17 | Dossier shows "1 Ansprache" and the card label with role; person panel lists Ansprachen | `tests/test_build_dip_pulse_site.py` |
| T18 | Every `CONTRIBUTION_KINDS` member has a `KIND_LABELS` entry and appears in CONTEXT.md's Beitrag kind list | `tests/test_speech_kinds.py` (derive the check, no hand-synced list) |
| T19 | `docs/data-methods.md` quotes the changed CONTEXT entries verbatim | existing `tests/test_daten_export.py:104` |
| T20 | Withholding interplay (after W3 exists): a Sitzungsleitung `<rede>` and an Ansprache reconcile as `procedural` and `stored` in W2's inventory | added in whichever PR lands second |

## Verification

1. `python -m unittest discover -s tests` on Python 3.11+ (this machine has only `/usr/bin/python3` 3.9; the miniconda path AGENTS.md names is absent, checked 2026-11-10), and on a current 3.13 patch (checklist).
2. Replay (README "Validate a data correction"): baseline copy, `--offline --repersist` with the branch on a second copy, `scripts/compare_store_values.py --cohort shared`. Expected: 0 moved values except anything step 1 found; the speech rule version moves 7 → 8 on every protocol.
3. Parse the seven sittings, 18/1 and 18/215 from W1's XML with the branch parser: the seven and 18/1 parse with no unmapped role; 18/215 still refuses only for recipients. Report per sitting: Reden, Ansprachen, procedural turns, against round 2's counts.
4. Fresh vs incremental: deferred to T4, which is the first run that admits these sittings.
5. Browser: the 19/1 Dossier and Schäuble's person page from a scratch store holding 19/1, at 375 px and in dark mode.
6. Red team and a Codex review on the tip if the diff passes 200 lines (checklist).

## Figures

**Measured on this machine: none.** There is no `.context/`, no store and no cached XML in either worktree or the main checkout (checked 2026-11-10), and no online fetch is allowed. Every figure below is recorded from earlier runs and must be re-measured in steps 1 and 3.

| Figure | Old | New (expected) | Basis |
|---|---|---|---|
| Kept store (716 sittings): Reden, Beiträge, Redeanteil, facts | as is | unchanged, unless step 1 finds counted oath answers or an address printed as an MdB `<rede>` in WP 20/21 | [estimated] from P2's reasoning: an unmapped role cannot be persisted |
| 19/1 presidium `<rede>`s counted as Reden by the parser | 6 | 0 Reden; Schäuble `ID19101300` 1 Ansprache; `ID19101900` Sitzungsleitung; the Alterspräsident's four: opening address `ID19100100` proposed Ansprache, the other three Sitzungsleitung (owner confirms) | [recorded: a3-rule5-validation.md:136-139] |
| 18/245 presidium `<rede>`s | 2 counted as Reden by the parser, unmapped at persist | 1 Ansprache (Bulmahn), 1 Sitzungsleitung (Singhammer) | [recorded: TODOS.md:501] |
| The five address sittings (18/178, 18/223, 19/9, 19/19, 19/73) | 53 Reden as round 2 parsed them, addresses included; 0 in the store | 53 minus their addresses and chair `<rede>`s, plus that many Ansprachen | [recorded: a3-wp18-19-round2-result.md:170] |
| D2's six that parse (18/2, 18/29, 18/83, 18/245, 19/1, 19/25) | 172 Reden as parsed | 18/245 and 19/1 lose 8 parser Reden, as above | [recorded: round 2 result :169] |
| Store totals after T4 admits the seven | absent | + their debate Reden; + their Ansprachen as Beiträge | measured in T4 |

The "old" for every restored sitting is **absent**, not a wrong value in the store: the move is in coverage, and it lands with T4's run, not with this PR's merge. Old and new go into that run's report and the release's `CHANGES.md` coverage section.

## Sequencing with W1/W2/W3

The coverage-gate agent builds what `v1-scope-review.md` calls W1 (fetch and audit the 85's XML), W2 (PR 1: raw XML inventory before the tree edits, and reconciliation of every `<rede>` id) and W3 (PR 2: withholding of located refusals). Overlap with this plan:

| This plan touches | W2/W3 touches | Conflict |
|---|---|---|
| `parse_protocol_xml` start: new pre-pass before `mark_presidium_fraktionsreden`; a skip inside it | W2's inventory runs before `mark_presidium_fraktionsreden` | textual only; the pre-pass sets attributes, never ids, and must run after W2's inventory |
| `split_nested_reden`: owner's text as chair text in a listed Sitzungsleitung `<rede>` | W2/W3 write rules for split-off units | semantic: a new split-off source; W2's reconciliation already accounts split parts |
| per-Rede loop: Sitzungsleitung `<rede>` into `procedural_reden` with diagnostics; nested Ansprache units; the P2 raise | W2 gives each id a status at the end; W3 catches located refusals in the same loop and commits each Rede's output only when it finishes | semantic: W2's statuses must count a Sitzungsleitung `<rede>` as `procedural` and an Ansprache as `stored`; W3's per-Rede commit must cover nested Ansprache units |
| P2's located refusal | W3 withholds exactly two located classes, by a typed exception | decision O6: whether the third class is withheld or refuses its sitting |
| `scripts/reviewed_units.json` | W3 adds a reviewed list for withheld units | decision O11: one file; W3 adds `withhold` entries to it |
| `speech_kinds.VERSION`, `EXPORT_FORMAT` | W3/W4 bump both | next free number, whoever lands second |
| `docs/data-methods.md`, CONTEXT.md | W7 writes ADR 0005 and the same docs | different sections; rebase |

**Order:** W1 (data) can run now and is step 0's input. Land **W2's PR 1 first**, then **this PR**, then **W3's PR 2**, then T4. Reasons: W2 is already in flight in the same function; landing after it lets this PR register its two statuses in W2's reconciliation directly instead of W2 discovering a new path; W3 then sees P2's refusal and the nested Ansprache units when it writes its undo and withholding; T4 must parse the seven with the kinds in place. If W2 slips past step 2 of this plan, this PR may land first, and W2 adds the two statuses (T20 moves to W2). Do not edit `validate_dip_protocol.py` in parallel branches without rebasing at each step.

## Risks

1. **The census needs data this machine lacks.** Step 0 depends on W1's network run and the reference store's XML. Mitigation: nothing in steps 2-6 can be finalized without it; the list entries are the census output.
2. **A `<rede>` mixing an address and chairing.** Whole-`<rede>` kinds put the chairing into the Ansprache's text, or drop the address with the chairing. Neither moves a count (an Ansprache counts nowhere). Decision O2 takes the whole-`<rede>` grain and records the text limit.
3. **WP 20/21 live miscounts outside the presidium path.** An Alterspräsident's address printed as an ordinary MdB `<rede>`, or oath answers printed as government `<rede>`s, would already be counted. Step 1 measures; P5 and a list entry fix them; figures are reported old and new.
4. **Guests get person rows.** A guest bound by Redner-ID gets an `mps` row and a profile page, as Bundesrat members already do. Accepted; deferred note below.
5. **Merge conflicts with W2/W3** in `validate_dip_protocol.py`. Mitigation: the order above.
6. **List drift.** A list entry for a sitting nobody parses is never checked. The loader cannot know which sittings exist; the census TSV and T6 keep entries honest, and a parse of a listed sitting checks every entry of it.

## Deferred to TODOS.md (non-correctness, or another item)

The implementer adds these to TODOS.md (this plan writes no other file):
- **Addresses printed as `<name>` chair text in WP 20/21** (constituent sittings, Gedenkworte) are excluded from every count but not shown as Ansprachen. Display gap, not a figure.
- **Text grain of a mixed `<rede>`** (O2): an Ansprache's `char_count` and text may include chairing.
- **Guest person pages** (risk 4): decide whether a non-MdB guest gets a page under `abgeordnete/`.
- **18/96 and 18/109** (`a3-pilot.md:207-208`): a Vizepräsidentin's Befragung Nachfrage dropped inside de Maizière's answer, and Bulmahn's closing text after another chair's marker. Pre-existing correctness misses on kept sittings, outside this item; they need their own rule proposals (a)/(b) and owner decision. Check first whether 5cc5982 already restored 18/109's closing text.
- **AGENTS.md interpreter path** `/opt/miniconda3/bin/python3.13` does not exist on this machine.
- **A stored role for Ansprachen** (O10): the A4 slice that moves the Dossier onto the store must either persist the printed role of an Ansprache (schema bump) or drop the card's role suffix. Add this to the slice's requirements in `docs/plans/a4-site-from-release.md` when that slice is planned.

## Decisions for the owner to confirm

Taken under CLAUDE.md's accuracy rule and ADR 0004, since no owner was available:

- **O1. One kind `ansprache` for presidium and guest addresses**, with CONTEXT.md's Gastansprache folded into a new **Ansprache** entry. Alternative: two kinds (`ansprache`, `gastansprache`). Picked because treatment is identical and the role on the card names the speaker's capacity.
- **O2. Whole-`<rede>` grain**, plus a `marker` for a nested presidium address; no split of one speaker's own text. Alternative: an `until_marker` split. Picked because no count depends on it.
- **O3. Widen the 6d acceptance** to 18/1's salutation and "gerne".
- **O4. Oath answers are procedural** (P5), like the acceptance. ADR 0002's definition of Rede (a contribution to the debate) excludes them.
- **O5. A reviewed list over a detector** (P1), fail-closed for unlisted presidium `<rede>`s (P2).
- **O6. W3 treats P2's refusal as a third withholdable located class.** An unreviewed presidium `<rede>` withheld is outside every count and flagged, which is what ADR 0004 asks. Alternative: refuse its sitting. W3's owner decides; recommended: withhold.
- **O7. The Alterspräsident's opening speech of a constituent sitting is an Ansprache**, his election procedure Sitzungsleitung (19/1 `ID19100100` proposed Ansprache). The census returns each to the owner.
- **O8. Speech rule version bump 7 → 8 and export format 16 → 17** (next free numbers), schema unchanged.
- **O9. `contributions.fraktion` of an Ansprache keeps the printed Fraktion** (the column means "as printed"), `sprechrolle` is NULL. No reader counts Beiträge by Fraktion.
- **O10. The card's role suffix comes from the report, and the schema stays 11.** Alternative: add `contributions.role` now (schema 12), which collides with W4's schema bump. The A4 requirement is deferred to TODOS.md.
- **O11. One reviewed-units file** shared with W3's withheld-unit list, with a `kind` field. Alternative: two files plus a cross-check that refuses a Rede listed in both.
- **O12. P4's `<rede>` form** (an acceptance printed as an MdB's own `<rede>`) is procedural, like the nested form, if the census finds one.

## Effort

M. Step 0 census and review: human ~1 day / CC ~1-2 h, plus the owner's hard cases. Steps 2-4: human ~2 days / CC ~3 h. Step 5-6: human ~1-2 days / CC ~2 h. Total human ~4-5 days / CC ~6-7 h [estimated]. Files: 14 changed or new (`speech_kinds.py`, `validate_dip_protocol.py`, `scripts/reviewed_units.json` (new), `derive.py`, `persist_dip_pulse_store.py`, `render_dip_pulse_html.py`, `build_dip_pulse_site.py`, `extract_demo_fixture.py`, `data_dictionary.json`, README, CONTEXT.md, ADR 0004, `docs/data-methods.md`, DESIGN.md) plus `tests/test_presidium_kinds.py` (new), five updated test files and new fixtures; one new exception class (`ReviewedUnitsError`), no new service. One PR.

## Eng review (`/plan-eng-review`, 2026-11-10)

**Target:** this file, reviewed in a spawned session with no owner present. Every choice a review would put to the owner was auto-decided by the option CLAUDE.md's accuracy rule and ADR 0004 support best, and is listed under "Decisions for the owner to confirm". Design doc check: none for this branch; the binding inputs are ADR 0004, Q13 and the round 2/3 records.

### Scope Challenge

- **What already exists:** `mark_presidium_fraktionsreden` (the Fraktionsrede kind), `procedural_reden` and the `procedural` diagnostic (the Sitzungsleitung treatment, used by 6d and the 21/43 summons), `nested_units` with `nested:<rid>:<marker>` ids (the nested Ansprache), `contributions` typed by `kind` with generic rendering by `KIND_LABELS` on the Dossier and the person page (the Ansprache display needs no new component), the `person_corrections.json` reviewed-list pattern, `require_current_speech_rules` (the version gate).
- **Minimum change:** one new kind, one data file, one pre-pass, two regex widenings, label strings, docs. The census is scratch tooling under `docs/plans/`, not shipped code.
- **Complexity:** 14 files and 1 new exception class [counted from Steps 2-5]. The 8-file gate trips. Structure question auto-decided: **original arrangement**. A smaller one (labels and docs in a follow-up PR) would ship a kind the site cannot name and a CONTEXT.md that contradicts the store; no smaller arrangement keeps the approved scope. Scope accepted as-is.
- **Search check:** no new infrastructure, concurrency or framework pattern; standard library only. Search not run.
- **TODOS cross-reference:** blocks the seven listed sittings of "Coverage gate before the first data release" (`TODOS.md:69`); shares `validate_dip_protocol.py` with W2/W3; the 18/96 and 18/109 misses are adjacent and stay out of scope.

**Reality rows:**

| Premise | Receipt | Verdict |
|---|---|---|
| Only a Vizepräsident(in) with Fraktion is handled today | `validate_dip_protocol.py:916-934` | true |
| An unmapped role stops persist for the whole run | `derive.py:376-380`, `:346-360` | true |
| No kept sitting holds a presidium-owned Rede with its role | follows from the row above; the store persisted | true (inferred) |
| The seven sittings parse and are kept out only by D2 | `a3-wp18-19-round2-result.md:229` | true [recorded] |
| No recipe or fact reads `contributions` | grep of `facts.py`, `build_dip_pulse_site.py:3460-3724` | true |
| `contributions.kind` has no CHECK constraint | `persist_dip_pulse_store.py:334-353` | true |
| 18/1's acceptance marker carries no presidium role | `a3-wp18-19-blockers.tsv:2` | true [recorded] |
| WP 20/21 prints no presidium owner `<rede>` | round 2 scan, `a3-wp18-19-round2-result.md:185`, Vizepräsident only | unverified for Präsident and role-less chairs (census groups 5, 7) |
| Oath answers are not counted in kept sittings | none | unverified (census group 4) |

- REALITY: premise-table finding 9 premises, unverified=2 (WP 20/21 addresses and oath answers; both measured by step 1) `docs/plans/adr-0004-presidium-kinds.md` Steps
- REALITY: already-done pass: no commit since 28799ac touches the presidium path; `git log --grep` for presidium/ADR 0004/Ansprache finds only docs `scripts/validate_dip_protocol.py:916`
- REALITY: surface-check pass: `--include-document-number`, `--exclude-document-number`, `--offline`, `--repersist`, `--fetch-xml` exist (`build_dip_pulse_site.py:13649-13704`); `compare_store_values.py --cohort` exists (`:790`)
- REALITY: binding-decisions pass: ADR 0004, Q13 A, round 2 decision 2, round 3 decision 1, N1/N7/N8 bind; `gstack-decision-search` returned nothing `docs/plans/v1-scope-review.md:200`
- REALITY: numbers finding: every figure is [recorded] from earlier runs or [estimated]; none could be re-measured here (no store, no XML, no Python 3.11) `docs/plans/a3-wp18-19-round2-result.md:170`
- REALITY: deferred-asks pass: no linked issue; the TODO's asks (detect, decide each kind, release 18/1 and 19/1, move 18/245) are all covered `TODOS.md:496-508`
- REALITY: pr-count pass: no `.gstack/ship-policy.json`; one PR `TODOS.md:20`

**Scope Challenge findings:** none beyond the two unverified premises, which step 1 turns into measurements.

### 1. Architecture

**Two shapes.** A: a reviewed data file plus a fail-closed refusal (picked). B: a content detector in `speech_kinds` (address vs chair text by length, salutation, floor wording). A hides the policy behind one lookup and one refusal and cannot misclassify silently; B spreads the policy over regexes whose errors change no test but change units (ADR 0002 Consequences). WP 18/19 is closed and small; WP 21 prints the chair as `<name>`. Pick A.

Findings (most severe first; sources: this review and the outside voice, see below):

1. [CRITICAL] (confidence: 7/10) `speech_kinds.py:446` — `between = trailing_sitzungsleitung_text(child)`: a presidium `<rede>` has no `<name>`, so a listed `<rede>` taking a normal turn would erase a Kurzintervention announcement and break Erwiderung pairing and the Befragung opening. **Accepted:** a listed `<rede>` leaves the running state alone and a Sitzungsleitung `<rede>`'s own text joins `between` (P3); T10.
2. [CRITICAL] (confidence: 6/10) `validate_dip_protocol.py:1022-1024` — `split_nested_reden` sets `chair` only for presidium markers other than the owner's, so a debate Rede printed inside a presidium-owned `<rede>` never splits off, and other MdBs' nested turns would become Zwischenfragen of a non-Rede. **Accepted:** the owner's text is chair text in a listed Sitzungsleitung `<rede>`; other nested turns there refuse unless P4, P5 or 6d covers them; census group 6 lists them; T9, T11.
3. [INFORMATIONAL] (confidence: 8/10) `v1-scope-review.md:499,799` — raising P2 in `classify_reden` makes it a TOP-wide, unnarrowable refusal, and W3 recognises withholdable refusals by type, not text. **Accepted:** placeholder label, raise in the per-Rede loop, W3's typed exception (P2).
4. [INFORMATIONAL] (confidence: 7/10) `validate_dip_protocol.py:1594` — `side = derive.sprechrolle(segment["speaker"])` is strict and raises `SprechrolleError`, which the online path does not catch (`:4143`). **Accepted:** the nested Ansprache branch runs first (P1).
5. [INFORMATIONAL] (confidence: 7/10) the list key: attributes on a marker travel into a split part; ids can repeat (`:1496`); annex `<rede>`s; 18/1's marker has no role. **Accepted:** the refusals in P1; T6.
6. [INFORMATIONAL] (confidence: 7/10) `validate_dip_protocol.py:4143-4144` — a malformed list raised inside the parse would read as "protocol source rejected" for every sitting. **Accepted:** load and validate at startup, `ReviewedUnitsError`; T7.
7. [INFORMATIONAL] (confidence: 7/10) `validate_dip_protocol.py:916-934` — running the pre-pass after `mark_presidium_fraktionsreden` strips the role a listed Vizepräsident(in) Ansprache shows. **Accepted:** pre-pass first, the Fraktion rule skips listed `<rede>`s.
8. [INFORMATIONAL] (confidence: 7/10) `v1-scope-review.md:1183` — W3 plans its own reviewed list. **Accepted:** one file (O11).
9. [INFORMATIONAL] (confidence: 5/10, medium confidence: verify) role-less chairs and an acceptance printed as an MdB `<rede>` would be counted today in kept constituent sittings. **Accepted:** census groups 4 and 7, P4's `<rede>` form (O12).

Red-flag screen: no shallow module (one loader, one pre-pass); no leakage (the presidium policy lives in `speech_kinds` and the list; `derive` only skips `ansprache`); one way per task (P2 replaces the persist-time failure for presidium roles, guests keep the existing check); hand-synced list risk in `CONTRIBUTION_KINDS` vs CONTEXT.md, answered by T18 deriving the check.

Failure modes:

| New path | Realistic failure | Handling | What users see |
|---|---|---|---|
| Reviewed list | stale entry after a source correction | refusal naming the entry (T6) | the run stops, loudly |
| Reviewed list | malformed file | `ReviewedUnitsError` at startup (T7) | the run stops before any fetch |
| P2 | a new WP 21 sitting prints a presidium `<rede>` | located refusal; W3 may withhold (O6) | the sitting is refused or the unit withheld, named |
| Ansprache | counted by a future recipe joining `contributions` | `sprechrolle` NULL and docs; no current reader | nothing today |
| Sitzungsleitung `<rede>` | a Kurzintervention inside it lost | running-state rule (T10) | nothing |
| P4/P5 regexes | over-match | full-match plus chair prompt; hostile-string tests | nothing |

Critical gaps: 0 after the accepted fixes.

Dispositions: 1-9 accepted, folded into P1-P4, Steps and Tests above.

### 2. Code quality

1. [INFORMATIONAL] (confidence: 9/10) wrong references in the first draft: `classify_reden` is at `speech_kinds.py:368-451`; a second "Was als Rede zählt" sits at `build_dip_pulse_site.py:10613`; `tests/fixtures/demo-report-21-84.json:860` records `speech_kinds_version` 7. **Accepted,** fixed above.
2. [INFORMATIONAL] (confidence: 8/10) `validate_dip_protocol.py:1628-1634` — the emit else-branch appends every labelled unit to `contributions`; `procedural_reden` filters only `speeches`. **Accepted:** drop `SITZUNGSLEITUNG` there (P3).
3. Shared code: the list loader reuses `person_corrections.json`'s pattern, not its code (different keys and checks); no extraction proposed.

Dispositions: 1-2 accepted.

### 3. Tests

The test table above (T1-T20) maps each changed behaviour to a test; it now covers the running state (T10), the 6c owner-as-chair split (T9), the startup loader (T7), the list-key refusals (T6), the role-less nested marker (T11) and P4's `<rede>` form (T12). Regression rule: T3 and T4 replace two existing tests whose asserted behaviour this plan deliberately changes (`tests/test_a3_round2.py:359,368`); the old assertions encoded "stays unmapped", which ADR 0004 itself calls the interim state. Hostile text (checklist 8): P4 and P5 get a 10,000-character run and an unbalanced-quote string, timed. No E2E or eval scope.

### 4. Performance

The list is a dict keyed by (sitting, rede_id); the pre-pass walks `<rede>` elements once per sitting, as the existing `mark_*` passes do. No loop over votes or persons is added (checklist 12). No issues found.

### Outside voice

Codex is not installed here. A fresh Claude subagent read the code with only this file and pointers, and reported 10 findings: 2 critical (the running state, nested turns and the 6c split), 8 informational. All were checked against the code and folded in (Sections 1-2). It confirmed: no recipe or fact reads `contributions`, no schema bump is needed, the repersist path catches both error types (`build_dip_pulse_site.py:1987`), and `upsert_mp` keeps a party on a NULL. Not outside-model coverage.

### Review checklist (`docs/agents/review-checklist.md`), applied to the plan

| Class | Answer |
|---|---|
| 1 Sibling path | every caller goes through `parse_protocol_xml` (online `:4142`, `reparse_cached_xml` `build_dip_pulse_site.py:1985`, `extract_demo_fixture.py:49`, `audit_offline_turns.py:35`, the preflight script); the loader is called at each entry point; `find_unmapped_sprechrollen` is the one role check for acquisition and persist |
| 3 Order | list lookup by key; output independent of entry order; duplicate keys refused |
| 4 One key | (sitting, source `rede_id`, raw marker ordinal) defined once in the loader; `redner_id` through `derive.first_redner_id` |
| 5 Absent vs zero | a sitting with only Ansprachen has 0 Reden, a real zero; an Ansprache's `fraktion` NULL means "none printed" |
| 6 Derived columns | TOP Reden counts and Zeichen, person contribution counts, `compare_store_values` per kind, `validate_store_gate` kinds: all derived from units at persist; none stored separately |
| 7 Neighbour binding | the proof of identity is `redner_id`; a mismatch refuses |
| 8 Hostile text | P4/P5 tests above |
| 9 Input shape | T7 |
| 10 Interrupted run | no new write path; persist's staged swap is unchanged |
| 11 Claims | every new doc sentence (CONTEXT.md, ADR amendment, data-methods, Methodik, dictionary) cites the code in the PR body; T19 guards the quotes |
| 12 Loop cost | none added |
| 13 Last commit | for the build |
| Figures, fresh vs incremental, browser, Python patch, adversarial lenses | Verification 2-6 |

## Design review (`/plan-design-review`, 2026-11-10)

**Rating:** 6/10 before review: the plan said which strings change but not how an Ansprache reads in the DESIGN.md restyle, and it missed the second Methodik text. 9/10 after. A 10 would include a rendered 19/1 Dossier, which needs the census data. DESIGN.md exists and is the reference. No mockups: the change is copy and one slip variant; the existing contribution card renders it.

| Pass | Finding | Disposition |
|---|---|---|
| 1 Information architecture | An Ansprache belongs beside the Reden of its TOP, in document order, not in a Rede ("Reading a speech", `DESIGN.md:377`, puts Zwischenfragen inside a Rede) | DESIGN.md sentence added to the label table (Step 5) |
| 2 States | A TOP holding only an Ansprache reads "Keine Reden; weitere Beiträge siehe oben": true and adequate | kept |
| 3 Journey | A reader of 19/1 must see why Schäuble's address is not a CDU/CSU Rede: the card says "Ansprache · Präsident" and the TOP line says "keine Reden und nicht mitgezählt" | accepted |
| 4 Slop risk | none: no new component, colour or icon | none |
| 5 Design system | no Fraktion colour on an Ansprache, because it counts for none ("Do show every Fraktion colour with the Fraktion's name"; a colour would imply the Fraktion) | accepted, unchanged code |
| 6 Responsive and a11y | label is text, not colour; card unchanged at 375 px | browser check in Verification 5 |
| 7 Unresolved | the role suffix needs a stored role once the Dossier reads the store | O10, deferred to TODOS.md |

## Completion summary

- Step 0: Scope Challenge: scope accepted as-is (original arrangement, auto-decided)
- Reality rows: 7/7 tier 1 rows; 2 unverified premises, both measured by step 1
- Architecture: 9 findings (2 critical), all accepted
- Code quality: 2 findings, accepted
- Tests: 20 mapped tests; 2 existing tests replaced by design
- Performance: no issues
- Outside voice: Claude subagent, 10 findings, all folded in; Codex unavailable
- Design review: 7 passes, 3 changes, 1 deferral
- Failure modes: 0 critical gaps after fixes
- Decisions for the owner: O1-O12

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| CEO Review | `/plan-ceo-review` | Scope and strategy | 0 | not run | scope set by Q13; not warranted |
| Outside Review | Claude subagent (Codex not installed) | Independent 2nd opinion | 1 | issues found, folded in | 10 (2 critical) |
| Eng Review | `/plan-eng-review` | Architecture and tests (required) | 1 | ISSUES OPEN | 11 accepted fixes folded into the plan; unbuilt; census and figures owed |
| Design Review | `/plan-design-review` | UI and UX gaps | 1 | CLEAR (PLAN) | 3 accepted, 1 deferred (O10) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | none |

- **OUTSIDE COVERAGE:** no outside-model review: Codex is not installed. The Claude subagent challenge does not count as cross-model coverage.
- **REVIEW LOG:** not persisted to `~/.gstack`: this spawned session may write only this file.
- **VERDICT:** the eng review mapped every finding into the plan. Its status stays ISSUES OPEN because step 0's census and step 1's measurement need data this machine lacks, and O1-O12 wait on the owner's confirmation. Build after W2's PR 1 lands and W1's XML exists.

**UNRESOLVED DECISIONS:**
- O1-O12 above were auto-decided in a spawned session and need the owner's confirmation; O6 and O11 also need W3's agreement.
