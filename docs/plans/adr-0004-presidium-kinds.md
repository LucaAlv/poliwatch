# ADR 0004 kinds: Ansprache, Sitzungsleitung, Fraktionsrede

Plan for TODOS.md roadmap Stage 1, item 2, "Tell official addresses and presidium Reden apart from Fraktionsreden (ADR 0004)". Written 2026-11-10 on `claude/correctness-gate-fixes-b22045` (main at 28799ac, v0.36.0.0). Steps 0 and 1 (census and measurement) ran on 2026-11-12, read-only; see "Census and measurements". Steps 2-6 were built on 2026-11-13; see "Build notes" at the end for where the build departs from this text.

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

TODOS.md "Coverage gate before the first data release" (`TODOS.md:69`) lists 18/178, 18/223, 18/245, 19/1, 19/9, 19/19 and 19/73 as waiting on this item. All seven **parse and raise no refusal**; they are kept out only by D2 (`a3-wp18-19-round2-result.md:229`). N1's withholding acts on refused `<rede>` units, so it does not reach them (`v1-scope-review.md:301`, outside finding 1). Admitting them today would stop the run on their unmapped presidium or guest roles. That holds for a Präsident(in) or Alterspräsident(in) printed with a Fraktion too: `mark_presidium_fraktionsreden` strips the role only on a `VIZEPRAESIDIUM_ROLE` full match (`validate_dip_protocol.py:913`, `:928`), so such an owner keeps "Präsident" and `check_sprechrollen` stops the run. Only a Vizepräsident(in) printed with a Fraktion is counted for that Fraktion, which round 2 reviewed (no address among the 24).

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
| **Procedural turn** (acceptance, consent to stand, oath) | "Ich nehme die Wahl an" nested (18/1) or as the elected person's `<rede>` (20/1, 21/1, …); the answer to an oath ("Ich schwöre es, so wahr mir Gott helfe.", or the whole formula) | nested: 6d, widened (P4); `<rede>`: the reviewed list (kind `procedural`), found by the P4/P5 detector, an unlisted candidate refuses | not stored; `procedural` diagnostic | none, not shown |

One kind for presidium and guest addresses, not two: their treatment is identical (shown, counted nowhere), the speaker and role on the card say who spoke, and CONTEXT.md's Gastansprache already decided a guest address counts toward nothing. The entry is folded into **Ansprache** (decision O1).

## Census and measurements (steps 0 and 1, run 2026-11-12)

Run on `worktree-agent-a3f8d0f08cdcbc466` (main 34a4615 plus this plan). Read-only throughout: no parser, schema, export or rule changed.

**Inputs.**
- The fresh reference store built on 28799ac (`.context/dip-pulse-site`, gate receipt `~/agent-runs/fresh/gate-receipt.json`): 718 sittings, 54,937 Reden, 42,724 Beiträge, and the cached XML of all 718.
- W1's XML of the excluded sittings (`~/agent-runs/w1/xml/`): 84 of the 85 sittings W1 fetched (complete at 19:12; `run.log` records 18/20 as "fetch failed", so 18/20 is not in this census; none of the seven nor 18/1 or 18/215 is missing). 13 of the 84 parse with today's parser, the same 13 round 2 listed; the other 71 refuse; only 18/1's refusal is at a unit of this item (the nested acceptance, P4).
- Python 3.13.18 (uv). The current parser (`parse_protocol_xml` on 34a4615) was run on every file to record what each unit is today.

**Tooling** (scratch, not shipped; under `docs/plans/adr-0004-census/`):
- `census.py` scans each XML for the seven groups of step 0 plus one more (group 8, an owner with neither role nor Fraktion), runs the parser, and reads the store read-only.
- `review.py` joins that scan with the reviewed decisions and writes [`adr-0004-census.tsv`](adr-0004-census.tsv) (one row per candidate unit, with sitting, rede id, marker, Redner-ID, speaker, role, Fraktion, length, TOP, what the parser and the store hold today, proposed kind, rule, hard flag, reason, first 200 characters) and [`adr-0004-reviewed-units.draft.json`](adr-0004-reviewed-units.draft.json). The draft is the content of `scripts/reviewed_units.json`; the code PR moves it there and adds the owner's answers. A row no rule or reviewed entry covers fails the script.
- `measure.py` takes the TSV and measures, on an in-memory copy of the store, every figure the proposed kinds move.

**Groups found** (rows of the TSV; one unit can sit in several groups):

| Group | Kept sittings | Excluded sittings | What it holds |
|---|---:|---:|---|
| 1 presidium owner `<rede>` | 20 | 19 | kept: all 20 Vizepräsident(in) with Fraktion (existing rule); excluded: 3 such, plus 16 presidium-owned `<rede>`s without Fraktion or of the Präsident |
| 2 owner role no rule maps | 0 | 7 | the guests of 18/223 and 19/9, and the Präsident printed with his name as role (18/178, 19/9, 19/73) |
| 3 nested presidium turn > 600 characters | 0 | 1 | 18/113 marker 3, a debate contribution (hard case) |
| 4 oath, acceptance, consent or nomination turn, or a turn after such a prompt | 88 | 35 | kept: 63 oath answers, 19 acceptances, 6 reviewed as unchanged (oath quotations over the cap, a GO statement, "ich nehme an"); the nominations are found by group 5 |
| 5 Reden in constituent, election, oath and Gedenk items | 131 | 12 | debate and GO Reden, plus group-4 turns |
| 6 nested turns in group 1/2/7 `<rede>`s | 2 | 2 | Zwischenfragen, correct today |
| 7 role-less chair owning a `<rede>` | 117 | 12 | debate contributions (and 2 kept acceptances) |
| 8 owner with neither role nor Fraktion | 0 | 0 | |

Annex `<rede>`s with a presidium owner: 0 in every file. No listed `<rede>` id is printed twice in its sitting.

**Proposed kinds** (TSV column `proposed_kind`):

| Proposed kind | Kept sittings | Excluded sittings | Rule |
|---|---:|---:|---|
| procedural (oath answer) | 63 | 16 | P5 detector + list entry |
| procedural (acceptance, `<rede>` form) | 19 | 12 | P4 detector + list entry |
| procedural (nested acceptance) | 0 | 2 | 6d, widened (no entry) |
| procedural (other, list only) | 0 | 3 | 18/1 Hintze, 18/1 Roth, 19/1 Schäuble's consent to stand |
| ansprache | 0 | 14 | list entry |
| sitzungsleitung | 0 | 9 | list entry |
| fraktionsrede (existing rule) | 20 | 3 | `mark_presidium_fraktionsreden` |
| nomination (hard, O13) | 2 | 2 | owner decides |
| deferred (hard) | 0 | 1 | 18/113 marker 3 |
| unchanged | 163 | 12 | listed for the record |

The draft list holds 136 entries: 113 procedural, 14 ansprache, 9 sitzungsleitung. Every entry is a whole `<rede>`; none needs a `marker`.

### What the census changes in this plan

1. **Live miscount in the kept store: 82 Reden are oath answers or election acceptances** (risk 3 and P4's `<rede>` form, now measured). In WP 18-21 the sworn person and the elected person are printed as a `<rede>` of their own, and the parser counts each as a Rede: 63 oath answers (Bundeskanzler(in), Bundesminister(innen), the Wehrbeauftragte, the Polizeibeauftragte; 59 for the Sprechrolle bundesregierung, 4 for weitere) and 19 acceptances (3 Bundeskanzler(in), 2 Präsidentinnen, 12 Vizepräsident(inn)en, the Wehrbeauftragter-elect Otte and Harbarth's election to the Bundesverfassungsgericht, all counted for their Fraktion). They sit in 24 kept sittings of all four Wahlperioden. Step 1 expected 0 for groups 1 and 2 (confirmed) and "can be non-zero" for groups 4, 5 and 7: group 4 is where the figures move.
2. **P4 and P5 as written would not fix them.** The first draft's P4 regex full-matches 0 of the 19 kept acceptances (3 of all 33 in the census), its P5 regex 6 of the 63 kept oath answers (12 of 79). Real turns add thanks ("Danke schön", "und bedanke mich für das Vertrauen"), a salutation of any form, "Ja.", "Ich nehme sie mit großer Freude an", or the whole Art. 56 formula (269-329 characters). Worse, `(?:Alters)?Präsident` cannot match "Alterspräsident" (lower-case p): the existing `ELECTION_ACCEPTANCE` (`validate_dip_protocol.py:831`) and the plan's widening both miss the salutation 18/1 actually prints. P4 and P5 are rewritten below: a text test with a length cap finds candidates, and a list entry decides each one (the outside voice showed that a prompt test cannot be extracted reliably and that a cap alone can swallow a short substantive sentence).
3. **Two kept sittings end with 0 Reden:** 18/4 (14 → 0) and 20/5 (18 → 0) hold nothing but the election, the acceptance and the oaths; after T4, 18/223 and 19/19 join them. A kept sitting with zero Reden is new (checklist class 5): The outside voice traced the paths: persist, facts, recipes r1/r2/r5 and the Redeanteil stacks already handle zero (`render_dip_pulse_html.py:2307`, `:2365`); the gap is wording: `percent()` returns 0.0 (`:618`), the TOP bars read "0 von 0" and the empty card says "Keine Reden im XML" (`:3053`, `:3145`, `:3239`), which reads as an extraction gap, not as "the XML's units here are no Reden". T21 asserts the exact output.
4. **A presidium role printed with the name:** 18/178, 19/9 and 19/73 print the role as "Präsident Dr. Norbert Lammert" / "Präsident Dr. Wolfgang Schäuble". `SITZUNGSLEITUNG_ROLE.fullmatch` misses it, so P2 would not see a presidium owner there; today it is "unmapped role" at persist. The reviewed list covers all three; P2 must test the role after removing the speaker's printed name (decision O15), else the next such sitting fails as an unmapped role instead of a located refusal.
5. **New cases the plan did not know:** 18/173 Lammert's statement opening the Armenia resolution debate (H4), 18/193 Lammert's farewell to Steinbrück, 18/1 Hintze's acceptance printed with the chair's announcement (H5), 18/1 Roth's acceptance without the words, 19/1 Schäuble's consent to stand, 19/1's empty `<rede>` before Solms's loose opening address (H2), and Schäuble's 19/1 `<rede>`s printed with Solms's Redner-ID (H1). The 18/x ones sit in sittings that refuse for other reasons; the list carries them so T4 and W3 do not stop on them.
6. **No nested presidium address exists.** The plan expected Lammert's inaugural address inside the Alterspräsident's `<rede>` in 18/1. 18/1 prints its chair as `<name>` elements (the WP 20/21 form), so Lammert's address is chair text, outside every count, like WP 20/21's constituent addresses. Group 3's only row (18/113 marker 3, below) is a debate contribution, not an address. So no list entry needs a `marker`, and the nested-Ansprache machinery of P1 and P3 has no case (decision O16).
7. **Nominations printed as `<rede>`** (Wahlvorschläge: "die SPD-Bundestagsfraktion schlägt die Kollegin Bärbel Bas vor") are counted as Reden in 20/1 and 21/1. They are neither presidium turns nor acceptances; decision O13.
8. **Names printed as `<name>` that are not the chair:** the WP 18/19 XML prints some speakers as a `<name>` element (Wanka 39 times, Maas 4, Schwesig 2, Wolf Biermann 2, Woidke, Ramelow as Ministerpräsident, Bentele and 40 MdBs once or a few times). The parser reads all of it as chair text. In 18/4 this is why the oath answers of Maas, Schwesig and Wanka are not counted. Pre-existing and outside this item (most are not presidium or oath turns); deferred to TODOS.md.
9. **Group 7 premise verified:** every one of the 117 kept `<rede>`s owned by a role-less chair is a debate contribution (debate salutation and content; Befragung questions; Kurzinterventionen), except the two acceptances 20/1 Bas and 21/1 Klöckner, which P4 covers. No list entry is needed for role-less chairs.

### Clear cases

- **Fraktionsrede (existing rule, no entry):** the 23 Vizepräsident(in) `<rede>`s printed with a Fraktion (20 kept, 3 excluded: 18/62, 18/110, 18/113), already reviewed in round 2. The kept 20 are unchanged.
- **Procedural, P5 oath answer:** 63 kept `<rede>`s (18/4, 18/17, 18/106, 18/216, 18/238, 19/107, 19/109, 19/163, 20/5, 20/30, 20/79, 20/159, 20/197, 21/2, 21/10, 21/91, 21/101); in excluded sittings 16 more (19/19 Merkel and 15 Minister).
- **Procedural, P4 acceptance:** 19 kept (18/4 Merkel, 18/212 Noll, 19/65 Harbarth, 19/195 Ziegler, 20/1 ×6, 20/5 Scholz "Ja.", 20/6 Göring-Eckardt, 21/1 ×5, 21/2 Merz, 21/6 Otte); in excluded sittings 12 more `<rede>`s (18/1 ×4, 19/1 ×5, 19/19 Merkel, 19/68 Kelber, 19/158 Högl) and 2 nested (18/1 Lammert, 19/1 Schäuble, 6d). Plus 19/1 Schäuble's "Ja, Herr Präsident." consenting to stand (list entry).
- **Ansprache (list entry):** 18/178 Lammert (Gedenkworte opening the debate on the invasion of the Soviet Union); 18/193 Lammert's farewell to Steinbrück; 18/215 Bulmahn's thanks to Steinmeier; 18/223 Lammert, Dreyer, Gauck, Steinmeier (joint sitting); 18/245 Bulmahn's farewell; 19/9 Schäuble and de Rugy (joint debate with the Assemblée nationale); 19/73 Schäuble's statement on the attack on Magnitz. 11 entries.
- **Sitzungsleitung (list entry):** 19/1 Solms `ID19100100` (GO procedure, AfD motion, seniority), `ID19101000` (candidacy question), `ID19101200` (election procedure and result); 19/19 Schäuble `ID191900100` (result), `ID191900300` (letter and oath call), `ID191900500` (the Bundespräsident's letter on the government), `ID191900600` (oath formula). 7 entries.
- **Unchanged (listed for the record):** group 5's debate and GO Reden, group 6's two Zwischenfragen, group 7's debate contributions, and 20/154 Erndl (a Kurzintervention saying "ich nehme an, …", a false positive of the loose scan).

### Hard cases for the owner

Each names the TSV row; the XML excerpt is the row's `first_200` plus the file named in it.

| # | Row (sitting, rede id) | Excerpt (TSV `first_200`; XML in `~/agent-runs/w1/xml/`) | Options (proposed first) |
|---|---|---|---|
| H1 | 19/1 `ID19101300`, `ID19101900` | Schäuble's inaugural address (15,343 characters) and his chairing, both printed with `<redner id="11002190">`, which is Solms's id; the name says Schäuble (11001938) | Ansprache with `redner_id` 11002190 as printed, plus a `person_corrections.json` entry so the Ansprache binds to Schäuble / the entry carries 11001938 and P1's identity check is relaxed for it (rejected: the check is the proof) |
| H2 | 19/1 `ID19100200` | an empty `<rede>` of Solms; his opening address (about 14,000 characters) follows as loose `<p>` elements under the TOP, read as chair text | sitzungsleitung for the empty `<rede>`, the address stays unshown (display gap, deferred) / a tree rule adopting the loose paragraphs as an Ansprache (O7) |
| H3 | 18/245 `ID1824502300` | Singhammer: the Verfassungsrichter election result (about 600 characters), then the closing address of the 18th Wahlperiode, then closes the sitting | ansprache (the address is most of it) / sitzungsleitung (the plan's first guess) |
| H4 | 18/173 `ID1817301900` | Lammert welcomes the Armenian and Turkish embassies, states the Bundestag's position on threats, opens the Aussprache | ansprache / sitzungsleitung (O14) |
| H5 | 18/1 `ID1800100600` | Hintze: "Ich bedanke mich. Ich nehme die Wahl an." followed by the chair's announcement of Singhammer's result, printed under Hintze | procedural (entry drops the misattributed chair text with it; check the PDF page) / split at the chair sentence (new rule, no figure) |
| H6 | 20/1 `ID20100700`, 21/1 `ID21101200` (kept); 18/1 `ID1800100100`, 19/1 `ID19100900` | nominations: "die SPD-Bundestagsfraktion schlägt die Kollegin Bärbel Bas vor" | O13: keep as Reden (status quo) / procedural by list entry (2 kept Reden leave) |
| H7 | 18/113 `ID1811302500` marker 3 | Pau, printed Vizepräsidentin, speaks 1,897 characters as the Antrag's author inside another Redner's `<rede>`; 6d drops it as Sitzungsleitung | defer to the 18/96 / 18/109 rule (TODOS.md) / a list kind that restores it as her Beitrag (new scope) |

### Measured figure moves (replace the estimates under Figures)

Measured by `measure.py` on the 718-sitting store, for the 82 kept Reden the clear cases take out of `speeches` (they become `procedural`: not stored, one diagnostic each). The nominations (O13) are shown separately.

| Figure | Old | New | Why the new value is more correct |
|---|---:|---:|---|
| Reden, all kept sittings | 54,937 | 54,855 | an oath answer or an acceptance is no contribution to a debate (ADR 0002) |
| Sprechrolle bundesregierung | 2,849 | 2,790 | 59 oath answers of Bundeskanzler(in) and Minister(innen) |
| Sprechrolle weitere | 22 | 18 | the oaths of Bartels, Högl, Otte (Wehrbeauftragte) and Grötsch (Polizeibeauftragter) |
| CDU/CSU | 14,882 | 14,874 | 8 acceptances |
| SPD | 11,555 | 11,550 | 5 acceptances |
| BÜNDNIS 90/DIE GRÜNEN | 7,670 | 7,667 | 3 acceptances |
| Die Linke | 5,639 | 5,637 | 2 acceptances |
| FDP | 4,374 | 4,373 | 1 acceptance |
| AfD, BSW, fraktionslos | unchanged | unchanged | |
| Kept sittings with 0 Reden | 0 | 2 (18/4, 20/5) | finding 3 |
| Person records whose Reden count moves | | 75 (−1 each; −2 for Merkel, Merz, Scholz, Bas, Lambrecht, Otte, Dobrindt) | none drops to 0 Reden; the list is in `measure.py`'s output |
| erste-reden: persons | 1,577 | 1,577 | nobody loses their only Rede |
| erste-reden: debut Rede moved | | 25 persons | the debut was an oath or acceptance (13 in 18/4, 6 in 20/5, 3 in 21/2, 18/17, 19/109, 20/197); it moves to the person's first real Rede |

With the two nominations (O13 option B) as well: Reden 54,855 → 54,853, CDU/CSU 14,874 → 14,873, SPD 11,550 → 11,549; 20/1 then holds 7 Reden and 21/1 11.

**Per sitting** (Reden old → new; shares are Redeanteil by count, Textanteil by characters, per Zusammenschluss or Sprechrolle):

| Sitting | Reden | What moves (old → new) |
|---|---|---|
| 18/4 | 14 → 0 | bundesregierung 13 → 0, CDU/CSU 1 → 0; three TOPs lose all their Reden |
| 18/17 | 110 → 109 | bundesregierung 6 → 5 (share 5.45 → 4.59 %) |
| 18/106 | 108 → 107 | weitere 1 → 0 |
| 18/212 | 85 → 84 | CDU/CSU 28 → 27 (32.94 → 32.14 %) |
| 18/216 | 41 → 40 | bundesregierung 4 → 3 (9.76 → 7.50 %); CDU/CSU share 31.71 → 32.50 % |
| 18/238 | 52 → 51 | bundesregierung 7 → 6 (13.46 → 11.76 %) |
| 19/65 | 83 → 82 | CDU/CSU 19 → 18 (22.89 → 21.95 %) |
| 19/107 | 172 → 171 | bundesregierung 12 → 11 |
| 19/109 | 12 → 11 | bundesregierung 2 → 1 (16.67 → 9.09 %); every other share up (CDU/CSU 25.00 → 27.27 %) |
| 19/163 | 137 → 136 | weitere 1 → 0 |
| 19/195 | 132 → 131 | SPD 26 → 25 (19.70 → 19.08 %) |
| 20/1 | 14 → 8 | SPD 4 → 2, CDU/CSU, Grüne, FDP, Linke 2 → 1; AfD share 14.29 → 25.00 % |
| 20/5 | 18 → 0 | bundesregierung 17 → 0, SPD 1 → 0 |
| 20/6 | 56 → 55 | Grüne 9 → 8 (16.07 → 14.55 %) |
| 20/30 | 49 → 48 | bundesregierung 5 → 4 |
| 20/79 | 147 → 146 | bundesregierung 6 → 5 |
| 20/159 | 59 → 58 | weitere 1 → 0 |
| 20/197 | 36 → 35 | bundesregierung 2 → 1 (5.56 → 2.86 %) |
| 21/1 | 17 → 12 | CDU/CSU 5 → 3, Grüne, Linke, SPD 3 → 2; AfD share 11.76 → 16.67 % |
| 21/2 | 24 → 5 | bundesregierung 18 → 0, CDU/CSU 2 → 1; each of the 5 remaining Reden is 20 % |
| 21/6 | 39 → 38 | CDU/CSU 12 → 11 (30.77 → 28.95 %) |
| 21/10 | 144 → 143 | weitere 1 → 0 |
| 21/91 | 93 → 91 | bundesregierung 8 → 6 (8.60 → 6.59 %) |
| 21/101 | 60 → 59 | bundesregierung 9 → 8 (15.00 → 13.56 %) |

Textanteil moves by under 0.1 points except in 18/4, 20/5 and 21/2, where the oath answers were most of the sitting's Reden (21/2: bundesregierung Textanteil 8.76 % → 0).

**erste-reden by week** (the facts.py debut rule, count of debutants per ISO week, old → new): 2013-W51 34 → 22, 2014-W03 37 → 38, 2014-W05 35 → 37, 2014-W07 86 → 91, 2014-W11 5 → 6, 2014-W12 54 → 55, 2014-W15 53 → 54, 2017-W13 1 → 2, 2021-W49 10 → 4, 2021-W50 19 → 20, 2022-W02 24 → 25, 2022-W04 42 → 43, 2022-W07 60 → 61, 2022-W12 28 → 29, 2023-W06 1 → 2, 2024-W45 1 → 0, 2024-W46 2 → 3, 2025-W19 3 → 0, 2025-W20 43 → 46.

**Excluded sittings** (no old value in the store; the move lands with T4):

| Sitting | Reden as parsed today | Under the proposed kinds | Beiträge today → proposed | What changes |
|---|---:|---:|---|---|
| 18/178 | 10 | 9 | 204 → 205 | Lammert's address becomes an Ansprache |
| 18/223 | 4 | 0 | 0 → 4 | four Ansprachen (Lammert, Dreyer, Gauck, Steinmeier); a sitting with 0 Reden |
| 18/245 | 21 | 19 | 4 → 6 | Bulmahn and Singhammer become Ansprachen (H3) |
| 19/1 | 19 | 7 (6 with O13 B) | 0 → 1 | 1 Ansprache (H1), 5 Sitzungsleitung (incl. H2), 6 procedural (5 acceptances, the consent); Kauder's nomination O13 |
| 19/9 | 16 | 14 | 0 → 2 | Schäuble and de Rugy become Ansprachen |
| 19/19 | 21 | 0 | 0 → 0 | 4 Sitzungsleitung, 17 procedural (Merkel's acceptance and oath, 15 Minister); a sitting with 0 Reden |
| 19/73 | 2 | 1 | 151 → 152 | Schäuble's statement becomes an Ansprache |
| 18/1, 18/173, 18/193, 18/215 | refused (unrelated turns) | refused until W3 or a rule | | their entries wait; 18/1 also needs the widened 6d |
| 18/2, 18/29, 18/83, 19/25, 18/62, 18/90 | as parsed | unchanged | | no case of this item (18/62's Pau Rede stays a Fraktionsrede) |

The five address sittings: 53 Reden as parsed (round 2's figure, reproduced) → 24 Reden, 8 Ansprachen, 4 Sitzungsleitung, 17 procedural. D2's six that parse: 172 Reden (reproduced) → 158; 18/245 and 19/1 lose 14 parser Reden, not 8.

**Where the plan's estimates differed:**
- "Kept store unchanged, unless step 1 finds counted oath answers …" → 82 Reden move in 24 kept sittings (above). The estimate's caveat was the case.
- "Speech rule version bump: no kept sitting is expected to change" → 24 kept sittings change; the bump is now a figure change, reported old and new in the PR and in `CHANGES.md`.
- 19/1: "6 presidium `<rede>`s → 1 Ansprache, the Alterspräsident's opening `ID19100100` proposed Ansprache, the other three Sitzungsleitung" → the 6 are 1 Ansprache and 5 Sitzungsleitung: `ID19100100` is chair work; the actual opening address is loose text after the empty `ID19100200` (H2). 19/1 also holds 6 procedural `<rede>`s the first draft did not count: 19 → 7 Reden, not 19 → 13.
- 18/245: "1 Ansprache, 1 Sitzungsleitung" → 2 Ansprachen proposed (H3).
- 18/1: "behind the acceptance waits his inaugural address" → there is no presidium address inside a `<rede>` in 18/1; the address is `<name>` chair text. 18/1 holds 6 acceptances, 1 nomination and the widened-6d nested acceptance.
- "WP 20/21 has none of the Vizepräsident kind" holds; WP 20/21 has 0 presidium-owned `<rede>`s of any kind and 0 guest `<rede>`s.

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
- ~~`marker`~~ **Cut (O16): the census found no nested presidium address.** The first draft's text follows for the record. `marker` (optional) named the raw marker ordinal inside the source `<rede>`, counted before any split, as `xml_turn_diagnostics.marker_ordinal` counts it for an unsplit Rede. Only `ansprache` takes a marker. The named marker must not be the owner's, must match `redner_id`, and must lie before any 6c split point of that `<rede>`; otherwise the entry refuses. It need not carry a presidium role: 18/1 prints Lammert's acceptance marker as "Norbert Lammert (CDU/CSU)" with no role (`a3-wp18-19-blockers.tsv:2`). Its segment becomes a nested Beitrag `nested:<rede_id>:<marker>` of kind `ansprache`, branched before the 6d `sitzungsleitung` check, the Zwischenfrage path and the strict side lookup (`side = derive.sprechrolle(segment["speaker"])`, `validate_dip_protocol.py:1594`, which would otherwise raise `SprechrolleError` on "Präsident", an exception the online `except (ET.ParseError, ValueError)` at `:4143` does not catch).
- `redner_id` is the proof of identity: the owner marker's (or the named marker's) `<redner id>`, first id per `derive.first_redner_id`.
- **Loaded and validated once at startup**, not inside a parse: `speech_kinds.load_reviewed_units()` is called by `build_dip_pulse_site.main`, `validate_dip_protocol.main` and `extract_demo_fixture`, and raises a dedicated `ReviewedUnitsError` that stops the run. Raised inside `parse_protocol_xml` as a `ValueError`, a malformed file would read as "protocol source rejected" for every sitting (`validate_dip_protocol.py:4143-4144`). Checks: an object with exactly `entries`; each entry with exactly the keys above; `sitting` matching `^\d{2}/\d{1,3}$`; `kind` in {`ansprache`, `sitzungsleitung`, `procedural`} (O17); `marker` a positive int and only with `ansprache`; `reason` non-blank; no two entries with the same (sitting, rede_id, marker), and no Rede listed under two kinds. Each failure names the entry (checklist class 9).
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
parse_protocol_xml(xml)                                  validate_dip_protocol.py:1550
  raw_rede_inventory              (#147: every source <rede> id, before any tree edit)
  adopt_reden_outside_tops
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

### P4. The election acceptance (revised after the census and the outside voice)

The census found 33 acceptances: 19 kept and 12 excluded printed as the elected person's own `<rede>` (counted as a Fraktion's Rede today), 2 nested (18/1 Lammert, 19/1 Schäuble). The first draft's full-match regex covered 0 of the 19 kept ones (finding 2).

- **Nested form: 6d stays a full match, widened.** `(?:(?:Herr|Frau) (?:Alters)?[Pp]räsident(?:in)?(?:, [^.!?]{1,60})?, )?[Ii]ch nehme die Wahl (?:sehr )?(?:gerne? )?an\.` after `ELECTION_QUESTION`. The `[Pp]` fixes the case bug that refuses 18/1 today; the salutation clause and "gern(e)" are 18/1's printed form. "… ich nehme die Wahl an. Meine Antrittsrede." still refuses (`tests/test_a3_rule5.py:71-73` unchanged). Decision O3.
- **`<rede>` form: detector plus list.** A `<rede>` whose owner text is at most 200 characters and contains `\b[Nn]ehme\b[^.!?]{0,40}\b(?:[Ww]ahl|sie)\b[^.!?]{0,30}\ban\b` (lower-case "sie" only: "Ich nehme an, dass Sie …" in 18/90 is no acceptance), or is exactly "Ja." under an acceptance prompt or an election heading, is a **candidate**. A listed candidate (kind `procedural`) goes to `procedural_reden` with one diagnostic; an unlisted candidate is refused, located, like P2 (typed, so W3 can withhold it). No prompt test decides: the census found the chair's question printed in many shapes ("Nehmen Sie die Wahl an, Frau Kollegin?", "ob er die Wahl annimmt", inside the previous Redner's text in 18/1), and a cap alone would also take "Ich nehme die Wahl an. Meine Antrittsrede." out of the counts.
- **Measured** (`sweep.py`): over every stored Rede and Beitrag of the 718 sittings, the text test hits 18 units, all census acceptances (the 19th kept one is Scholz's "Ja."); 0 would refuse wrongly. Three acceptance-like `<rede>`s no test reads are list entries only: 18/1 Roth (no "nehme"), 18/1 Hintze (H5), 19/1 Schäuble's "Ja, Herr Präsident." to "Sind Sie bereit, zu kandidieren?".
- A future WP 21 election in this form refuses its sitting until the entry is added (or W3 withholds the unit), instead of being counted. That is the fail-closed stance of P2, and the census script names the row (Verification 7).

### P5. The oath answer (revised after the census and the outside voice)

The census found 79 oath answers, every one a `<rede>` of the sworn person: 63 in 17 kept sittings (counted for the Sprechrolle bundesregierung, 59, or weitere, 4) and 16 in 19/19. WP 18/19 Minister without a Redner-ID (18/4 Maas, Schwesig, Wanka) are printed as `<name>` and already outside every count.

- **Detector plus list, as P4.** A `<rede>` that `classify_reden` would label a Rede, whose owner text is at most 400 characters and contains `\b(?:Amts)?[Ee]id(?:es(?:formel|leistung)?)?\b|\b[Ss]chw(?:ör|ur)` (revised after review, 2026-11-13: it also reads "Amtseid", "Eidesformel" and "Schwur"; checked against 7 positive strings, among them "Ich schwöre es.", the whole Art. 56 formula and "Ich leiste den Amtseid ohne religiöse Beteuerung.", and 3 negative ones, "Ich nehme die Wahl an.", "Eidgenossenschaft"/"Leidenschaft" and "beschwören"), is a candidate; listed (kind `procedural`) it is dropped with a diagnostic, unlisted it refuses, located. The cap covers the whole Art. 56 formula (269-329 characters) and keeps out debate Reden that quote an oath (20/57, 20/131, 21/62, all over 2,500 characters) and 21/52 Koçak's "Ich schwöre." at the end of a 1,129-character Erwiderung. The Bundespräsident's oath inside his 23,362-character address (18/223) stays inside that Ansprache.
- **Measured:** the first text test (`\b[Ii]ch schwöre\b`) hit 63 stored units in the 718 sittings, all 63 census oath answers. The revised regex hits the same 63 plus one Befragung Frage (19/94 `ID199400400`, "Würden Sie auch unter Eid bestreiten …", 286 characters). That unit is no Rede, so testing only `<rede>`s labelled Rede keeps it out: 0 would refuse wrongly. The first draft's full-match regex matched 6.
- **Only whole `<rede>`s, not nested turns** (revised 2026-11-13). No list entry can name a nested marker (O16), so a nested candidate could only ever refuse; the census found no nested oath answer, and a nested acceptance is 6d's. P4's `<rede>` form is tested the same way.
- No longer conditional ("written only if the inventory shows …"): the inventory shows 63 counted units (decision O4).

### P3 additions from the outside voice

- **A listed `procedural` `<rede>` is labelled in `classify_reden`, not later**, with the same state rule as a Sitzungsleitung `<rede>`: it leaves `previous`, `previous_rede`, `main_id` and `opening` alone, and its trailing chair text is carried into `between`. Dropping it only in the per-Rede loop would leave `main_id` pointing at an oath answer, so a following Kurzintervention would be parented to a unit that is not stored (`speech_kinds.py:442-451`). T10 gains a procedural subTest.
- **Nested turns of another speaker inside a listed `procedural` `<rede>`** refuse unless 6d covers them, as for a Sitzungsleitung `<rede>`: no Zwischenfrage may point at a dropped unit. Of the 136 draft entries only one holds another speaker's turn: 19/1 `ID19101200` (Sitzungsleitung) with Schäuble's nested acceptance, which 6d covers (`nested_check` run on the draft). T11 keeps that half.

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

- **Speech rule `speech_kinds.VERSION` 7 → 8.** The rule changes what a presidium `<rede>`, an oath answer and an acceptance become. 24 kept sittings change (82 Reden leave `speeches`, measured above), so the bump is a figure change: the PR reports old and new, and the bump makes every store prove it was persisted under the new rule (`require_current_speech_rules`, `persist_dip_pulse_store.py:81`). The full `--offline --repersist` it forces is owed anyway for E4. Checked 2026-11-13 on main 36bfd08: #147 (W2 PR 1, v0.37.0.0), #149 and #150 left `speech_kinds.VERSION` at 7, so this PR takes 8; re-check right before merge.
- **Export format 16 → 17.** `contributions.kind` gains a code: a meaning change of an exported column (precedent: format 16 for E4's meaning change). Take the next free number at merge time; no pending slice has claimed 17 (`render-layer-and-order.md` and `a4-site-from-release.md` only say "the numbers after" schema 11 / format 16; W4 takes its numbers "after both fix branches land", `v1-scope-review.md:1196`).
- **Store schema stays 11.** No column or table changes; `contributions.kind` has no CHECK constraint (`persist_dip_pulse_store.py:334-353`).
- **Repersist:** one `--offline --repersist` of the reference store after merge, combined with the owed E4 repersist (whichever agent runs it).

## Steps

**Step 0 (prerequisite, data). The census. Done 2026-11-12 for the kept store; see "Census and measurements".** Q13 says the build first lists every case. A read-only script under `docs/plans/adr-0004-census/` (scratch tooling, not shipped) scans every cached Plenarprotokoll XML: the reference store's 716 stored sittings (`data/xml/`) and W1's fetched XML of the 85. It lists, as `docs/plans/adr-0004-census.tsv`:
1. every `<rede>` whose first marker carries a presidium role, with Fraktion printed or not, after `mark_presidium_fraktionsreden`;
2. every `<rede>` whose owner role no Sprechrolle rule maps (guests);
3. every nested presidium marker inside another speaker's `<rede>` whose turn is longer than 600 characters (a candidate nested address);
4. every turn, nested or `<rede>`, matching the oath answer or the acceptance with any wording;
5. in WP 20/21, every `<rede>` in the constituent sittings (20/1, 21/1) and in the chancellor election and swearing-in sittings, with speaker, role, Fraktion and length: an Alterspräsident or Präsident address printed as an ordinary MdB `<rede>` (Fraktion, no role) would be counted for that Fraktion today;
6. every nested turn of another speaker inside each `<rede>` of groups 1, 2 and 7, with what the parser does with it today;
7. every `<rede>` whose owner chairs that sitting by `mark_roleless_chairs`'s test (a `<name>` chair element ending with the owner's first and last name), printed with no role.

Columns: sitting, rede_id, marker, redner_id, role, fraktion, chars, first 200 characters, proposed kind, reason. Each proposed kind is read against the PDF page. Hard cases go to the owner before step 2: any presidium `<rede>` printed with a Fraktion whose content is not debate, any `<rede>` mixing an address and chairing, any guest who is an MdB.

**Step 1. Measure the live store. Done 2026-11-12: 82 Reden move in 24 kept sittings.** On a `cp -cR` copy of the reference store: count step 0's rows that are in kept sittings. Expected 0 for groups 1 and 2 (they would have stopped persist). Groups 4, 5 and 7 can be non-zero in kept sittings; any such unit is a figure that moves, reported old and new.

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
| T6 | A stale entry refuses: missing `<rede>`, wrong `redner_id`, an id printed twice, an id found only in an annex; an entry with a `marker` key is malformed (O16) | synthetic |
| T7 | Malformed list stops the run at startup with `ReviewedUnitsError`, never as "protocol source rejected": null, list instead of object, unknown key, unknown kind, `marker` on sitzungsleitung, duplicate entry, a Rede under two kinds, blank sitting, blank reason | synthetic, one subTest each |
| T8 | An entry for another sitting is not applied | synthetic |
| T9 | 6c: the split-off part of a listed Ansprache stays its speaker's Rede; a debate Rede printed inside a listed Sitzungsleitung `<rede>` splits off with the owner's text as chair text | synthetic |
| T10 | Running state: a Kurzintervention announced inside a Sitzungsleitung `<rede>` is still a Kurzintervention of the last real Rede; an Erwiderung after a listed `<rede>` still pairs; a listed `<rede>` in a Befragung does not end the opening reports | synthetic, three subTests |
| T11 | A nested presidium marker stays `procedural` (6d); another MdB's nested turn in a listed Sitzungsleitung or procedural `<rede>` refuses unless 6d covers it (19/1 `ID19101200`'s nested acceptance passes) | 19/1 excerpt + synthetic |
| T12 | P4: 18/1's nested "Herr Alterspräsident, lieber Kollege Riesenhuber, …" (lower-case p) is procedural by 6d; "… Meine Antrittsrede." still refuses (existing test kept); listed `<rede>` forms of 20/1 (Kubicki's extra sentence), 20/5 ("Ja."), 21/1 (Ramelow) and 19/65 are procedural; the same text unlisted refuses, located; "Ich nehme an, dass Sie …" is no candidate | extends `tests/test_a3_rule5.py:56-80`, real excerpts |
| T13 | P5, one subTest per form: listed "Ich schwöre es.", "Ich schwöre, so wahr mir Gott helfe.", thanks after it, and the full Art. 56 formula (21/2 Merz, 329 characters) are procedural; the same unlisted refuses, located; a Befragung Frage saying "unter Eid" is no candidate; an oath quoted in a Rede over 400 characters is no candidate; the Bundespräsident's oath inside his address stays in the Ansprache | 18/4, 20/5, 21/2, 18/223 excerpts + synthetic |
| T14 | A guest `<rede>` listed as Ansprache passes `check_sprechrollen`; an unlisted guest role still fails it | extends `tests/test_sprechrolle.py:314` |
| T15 | A presidium role on a Rede unit raises the ADR 0004 error | `tests/test_sprechrolle.py` |
| T16 | Persist: an Ansprache row has `sprechrolle` NULL, `fraktion` as printed, `mp_id` set; Reden counts and the r2 shares are unchanged by it | `tests/test_persist_dip_pulse_store.py`, `tests/test_sprechrolle.py:266` pattern |
| T17 | Dossier shows "1 Ansprache" and the card label with role; person panel lists Ansprachen | `tests/test_build_dip_pulse_site.py` |
| T18 | Every `CONTRIBUTION_KINDS` member has a `KIND_LABELS` entry and appears in CONTEXT.md's Beitrag kind list | `tests/test_speech_kinds.py` (derive the check, no hand-synced list) |
| T19 | `docs/data-methods.md` quotes the changed CONTEXT entries verbatim | existing `tests/test_daten_export.py:104` |
| T20 | Reconciliation (#147's `raw_rede_inventory` and `reconcile_reden`): a listed Sitzungsleitung or procedural `<rede>` takes the status `procedural`, an Ansprache `beitrag` (`REDE_STATUS`); a refused presidium `<rede>` leaves no status behind it | this PR (W2 PR 1 landed first, as #147) |
| T21 | A kept sitting whose every `<rede>` is procedural (18/4, 20/5) persists with 0 Reden: no share shown (not "0 %" or "0 von 0"), the Dossier says the units are no Reden instead of "Keine Reden im XML", facts and recipes skip it | `tests/test_persist_dip_pulse_store.py`, `tests/test_build_dip_pulse_site.py` |
| T22 | P2 sees a presidium role printed with the speaker's name ("Präsident Dr. Norbert Lammert", 18/178) and refuses it located when unlisted; a guest role ("Präsidentin des Bundesrates") is not a presidium role | synthetic |
| T23 | Census replay: every procedural row of `docs/plans/adr-0004-census.tsv` in a kept sitting reads procedural under the branch parser, every other row keeps its unit (one test over the cached XML, skipped when the store is absent, like the replay checks; the PR copies the row list into a fixture) | new, with Verification 2 |

## Verification

1. `python -m unittest discover -s tests` on Python 3.11+ (this machine has only `/usr/bin/python3` 3.9; the miniconda path AGENTS.md names is absent, checked 2026-11-10), and on a current 3.13 patch (checklist).
2. Replay (README "Validate a data correction"): baseline copy, `--offline --repersist` with the branch on a second copy, `scripts/compare_store_values.py --cohort shared`. Expected: exactly the moves measured above (Reden 54,937 → 54,855; the per-sitting table; contributions by kind unchanged), and nothing else; the speech rule version moves 7 → 8 on every protocol. Any other moved value is a defect of the branch.
3. Parse the seven sittings, 18/1 and 18/215 from W1's XML with the branch parser: the seven and 18/1 parse with no unmapped role; 18/215 still refuses only for recipients. Report per sitting: Reden, Ansprachen, procedural turns, against round 2's counts.
4. Fresh vs incremental: deferred to T4, which is the first run that admits these sittings.
5. Browser: the 19/1 Dossier and Schäuble's person page from a scratch store holding 19/1, at 375 px and in dark mode.
6. Red team and a Codex review on the tip if the diff passes 200 lines (checklist).
7. Census re-run: `docs/plans/adr-0004-census/census.py` and `review.py` over the replayed store's XML (and W1's) before T4 and before each data release; a row `review.py` cannot place (exit 1) is a new case for the owner, not a pass.

## Figures

**Measured 2026-11-12** (see "Census and measurements" above for the per-sitting table and the method). The first draft measured nothing; its rows are kept here with the measured value beside them.

| Figure | First draft (recorded or estimated) | Measured |
|---|---|---|
| Kept store (718 sittings): Reden | "unchanged, unless step 1 finds counted oath answers or an address printed as an MdB `<rede>` in WP 20/21" [estimated] | 54,937 → 54,855: 63 oath answers and 19 acceptances in 24 kept sittings (WP 18-21); no address printed as an MdB `<rede>` |
| Kept store: Beiträge, contributions by kind | unchanged [estimated] | unchanged (oath answers and acceptances become `procedural`, not stored) |
| Kept store: Redeanteil, Textanteil, per person, erste-reden | unchanged [estimated] | move in the 24 sittings, 75 person records, 25 debuts (tables above) |
| 19/1 presidium `<rede>`s | 6 counted as Reden by the parser [recorded] | 6 → 1 Ansprache, 5 Sitzungsleitung; plus 6 procedural and 1 nomination: 19 → 7 Reden |
| 18/245 presidium `<rede>`s | 2 [recorded] | 2 → 2 Ansprachen (H3): 21 → 19 Reden |
| The five address sittings (18/178, 18/223, 19/9, 19/19, 19/73) | 53 Reden as round 2 parsed them [recorded] | 53 reproduced → 24 Reden, 8 Ansprachen, 4 Sitzungsleitung, 17 procedural |
| D2's six that parse | 172 Reden; 18/245 and 19/1 lose 8 parser Reden [recorded] | 172 reproduced → 158: 18/245 and 19/1 lose 14 |
| Store totals after T4 admits the seven | measured in T4 | unchanged: the move lands with T4's run |

The "old" for every restored sitting is **absent**, not a wrong value in the store: that move is in coverage and lands with T4's run. The 82 kept Reden are different: they are wrong values in today's store and move with this PR's repersist.

## Sequencing with W1/W2/W3

The coverage-gate work builds what `v1-scope-review.md` calls W1 (fetch and audit the 85's XML), W2 (PR 1: raw XML inventory before the tree edits, and reconciliation of every `<rede>` id) and W3 (PR 2: withholding of located refusals).

**What landed (checked 2026-11-13, main 36bfd08):** W1's XML is in `~/agent-runs/w1/xml/` (84 of 85). W2 PR 1 is #147 (v0.37.0.0): `raw_rede_inventory` reads every source `<rede>` id as the first step of `parse_protocol_xml`, `record_status` gives each one exactly one status (`speech`, `beitrag`, `zu_protokoll`, `procedural`, `excluded_annex:<rule>`), `speech_kinds.REDE_STATUS` maps each Kind to its status, and `reconcile_reden` refuses a sitting where a `<rede>` or a split part has none. #149 rebuilt the withholding preflight test and W1's figures on it; #150 read 19/36's Anlage 2. None of them bumped `speech_kinds.VERSION` (still 7) or `EXPORT_FORMAT` (still 16). W3 has not landed.

| This plan touches | Landed (#147) or pending (W3) | Consequence |
|---|---|---|
| `parse_protocol_xml` start: `mark_reviewed_units` before `mark_presidium_fraktionsreden`; a skip inside it | #147's `raw_rede_inventory` is the first statement | the pre-pass runs after the inventory and after `adopt_reden_outside_tops`; it sets attributes, never ids, so the inventory is unaffected |
| `split_nested_reden`: owner's text as chair text in a listed Sitzungsleitung `<rede>` | #147 passes `split_parts` and requires a status for each part | a part split off a listed `<rede>` carries no `reviewed_kind` and takes its own status like any part |
| per-Rede loop: Sitzungsleitung and procedural `<rede>`s into `procedural_reden`; the P2/P4/P5 raises | #147's `record_status` at the end of the loop | Sitzungsleitung and procedural `<rede>`s record `procedural` (existing branch); `ANSPRACHE` gets a `REDE_STATUS` row `beitrag`; the internal labels `SITZUNGSLEITUNG`/`PROCEDURAL` need none because they record `procedural`. T20 is in this PR |
| P2's located refusal | W3 withholds located classes by a typed exception | decision O6: P2 raises a typed `UnreviewedUnitError(ValueError)` carrying sitting, TOP and `rede_id`; W3 decides whether to withhold it |
| `scripts/reviewed_units.json` | W3 plans a reviewed list for withheld units | decision O11: one file; W3 adds `withhold` entries |
| `speech_kinds.VERSION`, `EXPORT_FORMAT` | unchanged by #147/#149/#150 | 7 → 8 and 16 → 17 here; whoever lands second re-picks |
| `docs/data-methods.md`, CONTEXT.md | W7 writes ADR 0005 and the same docs | different sections; rebase |

**Order:** W2 PR 1 has landed, so this PR goes next, then W3's PR 2, then T4. W3 then sees P2's typed refusal when it writes its withholding; T4 must parse the seven with the kinds in place. Do not edit `validate_dip_protocol.py` in parallel branches without rebasing at each step.

## Risks

1. **The census needs data this machine lacks.** Step 0 depends on W1's network run and the reference store's XML. Mitigation: nothing in steps 2-6 can be finalized without it; the list entries are the census output.
2. **A `<rede>` mixing an address and chairing.** Whole-`<rede>` kinds put the chairing into the Ansprache's text, or drop the address with the chairing. Neither moves a count (an Ansprache counts nowhere). Decision O2 takes the whole-`<rede>` grain and records the text limit.
3. **Live miscounts outside the presidium path.** Realised: 82 kept Reden in WP 18-21 are oath answers and acceptances (measured). P4 and P5 fix them; figures are reported old and new. No address printed as an MdB `<rede>` was found. Future WP 21 sittings: a swearing-in or by-election in a shape the P4/P5 text tests catch refuses its sitting until listed (or W3 withholds it); a shape they miss is counted as a Rede, so the census script is re-run before each release (Verification 7).
4. **Guests get person rows.** A guest bound by Redner-ID gets an `mps` row and a profile page, as Bundesrat members already do. Accepted; deferred note below.
5. **Merge conflicts with W2/W3** in `validate_dip_protocol.py`. Mitigation: the order above.
7. **Kept sittings with zero Reden** (18/4, 20/5): no page or fact has met one. T21.
6. **List drift.** A list entry for a sitting nobody parses is never checked. The loader cannot know which sittings exist; the census TSV and T6 keep entries honest, and a parse of a listed sitting checks every entry of it.

## Deferred to TODOS.md (non-correctness, or another item)

The implementer adds these to TODOS.md (this plan writes no other file):
- **Addresses printed as `<name>` chair text in WP 20/21** (constituent sittings, Gedenkworte) are excluded from every count but not shown as Ansprachen. Display gap, not a figure.
- **Text grain of a mixed `<rede>`** (O2): an Ansprache's `char_count` and text may include chairing.
- **Guest person pages** (risk 4): decide whether a non-MdB guest gets a page under `abgeordnete/`.
- **18/96 and 18/109** (`a3-pilot.md:207-208`): a Vizepräsidentin's Befragung Nachfrage dropped inside de Maizière's answer, and Bulmahn's closing text after another chair's marker. Pre-existing correctness misses on kept sittings, outside this item; they need their own rule proposals (a)/(b) and owner decision. Check first whether 5cc5982 already restored 18/109's closing text.
- **Solms's 19/1 opening address** is printed as loose `<p>` elements after an empty `<rede>` (H2) and stays unshown under the proposed kind; showing it needs a tree rule. Display gap, no figure.
- **18/20 is not in the census**: W1's fetch failed for it (`~/agent-runs/w1/run.log`). Re-run `census.py` and `review.py` on its XML before T4 admits it.
- **Speakers printed as `<name>` who are not the chair** (census finding 8): Wanka 39 turns, Maas 4, Schwesig 2, Biermann 2, Woidke, Ramelow, Bentele, and about 40 MdBs once or a few times in WP 18/19 kept sittings are read as chair text and counted nowhere. Pre-existing correctness gap, outside ADR 0004; needs its own measurement (which of them are Reden, Antworten or Zwischenfragen) and rule.
- **AGENTS.md interpreter path** `/opt/miniconda3/bin/python3.13` does not exist on this machine.
- **A stored role for Ansprachen** (O10): the A4 slice that moves the Dossier onto the store must either persist the printed role of an Ansprache (schema bump) or drop the card's role suffix. Add this to the slice's requirements in `docs/plans/a4-site-from-release.md` when that slice is planned.

## Decisions for the owner to confirm

Taken under CLAUDE.md's accuracy rule and ADR 0004, since no owner was available:

- **O1. One kind `ansprache` for presidium and guest addresses**, with CONTEXT.md's Gastansprache folded into a new **Ansprache** entry. Alternative: two kinds (`ansprache`, `gastansprache`). Picked because treatment is identical and the role on the card names the speaker's capacity.
- **O2. Whole-`<rede>` grain**, plus a `marker` for a nested presidium address; no split of one speaker's own text. Alternative: an `until_marker` split. Picked because no count depends on it.
- **O3. Acceptances (revised 2026-11-12).** Nested: 6d stays a full match, widened by 18/1's salutation clause, "gern(e)" and the `[Pp]räsident` case fix. `<rede>` form: a capped text test finds candidates and the list decides each one (31 entries today); an unlisted candidate refuses, located. Measured: 19/19 kept acceptances, 0 wrong hits in the store. Alternative: an automatic rule (cap plus prompt), rejected because the prompt cannot be read reliably and a cap alone swallows a short substantive sentence (outside voice).
- **O4. Oath answers are procedural** (P5), like the acceptance. ADR 0002's definition of Rede (a contribution to the debate) excludes them. Revised 2026-11-12: detector plus list as for P4 (at most 400 characters, "ich schwöre"; 79 entries). Measured: 63/63 kept oath answers, 0 wrong hits in the store; 59 Reden leave the Sprechrolle bundesregierung and 4 leave weitere.
- **O5. A reviewed list over a detector** (P1), fail-closed for unlisted presidium `<rede>`s (P2).
- **O6. W3 treats P2's refusal, and the unlisted P4/P5 candidate, as a third withholdable located class.** An unreviewed presidium `<rede>` or oath answer withheld is outside every count and flagged, which is what ADR 0004 asks. Alternative: refuse its sitting. W3's owner decides; recommended: withhold.
- **O7. The Alterspräsident's opening speech of a constituent sitting is an Ansprache**, his election procedure Sitzungsleitung (19/1 `ID19100100` proposed Ansprache). The census returns each to the owner.
- **O8. Speech rule version bump 7 → 8 and export format 16 → 17** (next free numbers), schema unchanged.
- **O9. `contributions.fraktion` of an Ansprache keeps the printed Fraktion** (the column means "as printed"), `sprechrolle` is NULL. No reader counts Beiträge by Fraktion.
- **O10. The card's role suffix comes from the report, and the schema stays 11.** Alternative: add `contributions.role` now (schema 12), which collides with W4's schema bump. The A4 requirement is deferred to TODOS.md.
- **O11. One reviewed-units file** shared with W3's withheld-unit list, with a `kind` field. Alternative: two files plus a cross-check that refuses a Rede listed in both.
- **O12. P4's `<rede>` form** (an acceptance printed as an MdB's own `<rede>`) is procedural, like the nested form. The census found 19 in kept sittings and 12 in excluded ones; plus 19/1 Schäuble's consent to stand, by list entry.
- **O13. Nominations printed as a `<rede>`** (20/1 Mützenich, 21/1 Merz, 18/1 Kauder): A) keep them as Reden (status quo, no figure moves; recommended only if the owner reads a Wahlvorschlag as a contribution to the election debate); B) procedural like the acceptance, by list entry (2 kept Reden leave: SPD 11,550 → 11,549, CDU/CSU 14,874 → 14,873). Recommended: B, by ADR 0002's definition (a nomination is a motion, not a contribution to a debate) — but it is outside ADR 0004's wording, so the owner decides. Not auto-decided.
- **O14. 18/173: Lammert's statement opening the Armenia debate is an Ansprache** (welcome of two embassies, the Bundestag's position on threats against its members, then the floor). Alternative: Sitzungsleitung. Either way no figure moves today (18/173 refuses for an unrelated turn). Owner confirms.
- **O15. P2 tests the owner role after removing the speaker's printed name** ("Präsident Dr. Norbert Lammert" → "Präsident"), so a presidium role printed with the name is a presidium role. A guest role ("Präsidentin des Bundesrates") still does not match. Alternative: rely on the list entry and `check_sprechrollen` for such a sitting (fails closed, unlocated).
- **O16. No `marker` field.** The census found no presidium address printed inside another Redner's `<rede>` (group 3: one row, a debate contribution). The `marker` key, its refusals in P1, the nested Ansprache branch before `:1594` (P3) and T11's nested-Ansprache half are cut. Entries name whole `<rede>`s only. A future nested address would be dropped by 6d as Sitzungsleitung: no figure, a display gap.
- **O18. 19/1 `ID19101300` (Schäuble's inaugural address) is listed with the Redner-ID the source prints, 11002190 (Solms's), and its binding is corrected through `scripts/person_corrections.json`** so the Ansprache is Schäuble's. Alternative: write Schäuble's id into the entry and relax P1's identity check for it, which removes the proof the check exists for (H1).
- **O17. The reviewed list takes a third kind `procedural`** for every `<rede>`-form acceptance and oath answer (110 entries the P4/P5 detector finds) and the three no test reads (18/1 Roth's acceptance without the words; 18/1 Hintze's, printed with the chair's next announcement, which the entry drops with it; 19/1 Schäuble's consent to stand). Same treatment as Sitzungsleitung (not stored, one diagnostic), different evidence text. Alternative: list them as `sitzungsleitung`, which mislabels an acceptance.

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

## Eng review re-run of the open items (`/plan-eng-review`, 2026-11-12)

**Target:** this file, after steps 0 and 1. Spawned session, no owner present: every choice is auto-decided under CLAUDE.md's accuracy rule and listed under "Decisions for the owner to confirm"; nothing was asked. Scope: the items the 2026-11-10 run left open (census, figures, the two unverified premises) and whatever the census changes. The architecture accepted on 2026-11-10 (A: reviewed list plus fail-closed refusal) is not reopened.

### Scope Challenge (re-run)

| Premise (2026-11-10) | Receipt (2026-11-12) | Verdict |
|---|---|---|
| WP 20/21 prints no presidium owner `<rede>` | census group 1: 0 in the 318 kept WP 20/21 sittings (all 20 kept rows are WP 18) | true, measured |
| Oath answers are not counted in kept sittings | 63 counted (`speeches`, sprechrolle bundesregierung/weitere) in 17 kept sittings | **false**: live miscount, now in scope |
| No kept sitting holds a presidium-owned Rede with its role | group 1 kept: only the 20 Vize+Fraktion Reden, role removed by the existing rule | true, measured |
| The seven sittings parse and are kept out only by D2 | W1 XML, current parser: all seven parse | true, measured |
| 18/1's acceptance marker carries no presidium role | 18/1 `ID1800100100` marker 2 "Dr. Norbert Lammert (CDU/CSU)", no role | true; also refused by the `(?:Alters)?Präsident` case bug |
| Lammert's 18/1 inaugural address is a nested marker | 18/1 prints the chair as `<name>` | **false**: no nested address case; `marker` cut (O16) |
| The plan's P4/P5 regexes cover the turns | 3 of 33 acceptances, 12 of 79 oath answers | **false**: P4/P5 redesigned |

- REALITY: premise-table finding: 7 premises, 3 false; all three folded into the plan (P4, P5, O16) `docs/plans/adr-0004-presidium-kinds.md` Census and measurements
- REALITY: numbers finding: every figure in Figures is now measured on the 718-sitting store or W1's XML; round 2's 53 and 172 Reden reproduced exactly `docs/plans/adr-0004-census/measure.py`
- REALITY: already-done pass: main 34a4615 has no commit on the presidium, oath or acceptance path since 28799ac `git log 28799ac..34a4615` (docs only)
- REALITY: surface-check pass: `facts.REGISTRY` erste-reden SQL, `facts.ensure_canonical`, `compare_store_values._redeanteil_group_sql` reused by `measure.py` unchanged `scripts/facts.py:373`
- **Complexity:** unchanged file count (14) plus two data files' worth of content (the list grows from a few dozen to 136 entries, data not code). The `marker` cut removes the nested-Ansprache branch, so the diff shrinks. Scope accepted.

### 1. Architecture (new findings)

1. [CRITICAL] (confidence 10/10) **Live miscount, 82 kept Reden** (finding 1). **Accepted:** P4 `<rede>` form and P5 now in scope as list entries; figures reported old and new; speech rule bump is a figure change.
2. [CRITICAL] (confidence 9/10, outside voice) `speech_kinds.py:442-451` — a `procedural` `<rede>` dropped only in the per-Rede loop leaves `main_id` on a unit that is not stored. **Accepted:** labelled in `classify_reden`, state-neutral (P3 additions); T10 subTest.
3. [INFORMATIONAL] (confidence 10/10, outside voice) a prompt test cannot be read reliably for whole `<rede>`s (`speech_kinds.py:286` reads only `<name>`), and a cap alone swallows "… Meine Antrittsrede.". **Accepted:** detector plus list; nested 6d keeps its full match (P4).
4. [INFORMATIONAL] (confidence 9/10) role printed with the name (18/178, 19/9, 19/73) escapes `SITZUNGSLEITUNG_ROLE.fullmatch`. **Accepted:** O15; T22.
5. [INFORMATIONAL] (confidence 9/10) 19/1 Schäuble's `<rede>`s carry Solms's Redner-ID. **Accepted:** O18 (entry as printed plus a person correction); H1 to the owner.
6. [INFORMATIONAL] (confidence 9/10, outside voice) zero-Reden sittings: wording, not arithmetic. **Accepted:** T21 with exact output.
7. [INFORMATIONAL] (confidence 8/10, outside voice) nested turns inside a listed `procedural` `<rede>`. **Accepted:** refuse unless 6d (P3 additions); census: 0 cases.
8. [INFORMATIONAL] (confidence 10/10, outside voice) the draft list carried an `owner_confirms` key the loader would refuse. **Fixed:** the draft has the loader's keys only; the hard flag lives in the TSV.

Failure modes added: an unlisted oath or acceptance in a future WP 21 sitting → located refusal (W3 may withhold, O6); a shape the detector misses → counted, caught by the census re-run (Verification 7). Critical gaps after the fixes: 0.

### 2. Code quality

1. [INFORMATIONAL] (confidence 9/10) `ELECTION_ACCEPTANCE` `(?:Alters)?Präsident` cannot match "Alterspräsident" (`validate_dip_protocol.py:831`). **Accepted:** `[Pp]` in the widened 6d (P4). This is a defect on main, but no kept sitting reaches it (18/1 is excluded), so it is fixed here, not separately.

### 3. Tests

T6, T11, T12, T13 revised; T21-T23 added (zero-Reden sitting, role with name, census replay). The existing `test_more_than_the_acceptance_is_not_procedural` now stays as is (nested 6d keeps its full match). T3/T4 still replace two round-2 tests by design.

### 4. Performance

The list grows to 136 entries, a dict lookup per `<rede>`; the detector adds two regex searches per turn under a length cap. No issue.

### Outside voice

Codex (`codex exec`, read-only, 2026-11-12) on the revised plan and census tooling: 9 findings (2 rated 10/10 on the design, 3 on the census method). Folded in: the procedural `<rede>` state rule, the prompt and cap critique (design changed to detector plus list), the census's shared blind spots (discovery widened to turns up to 3,000 characters, by wording or by the chair's prompt, nested turns included: the 88 kept candidates are the 82 procedural units plus 6 reviewed as unchanged: four Reden quoting an oath over the cap, a GO statement on a Wahlvorschlag, a Kurzintervention saying "ich nehme an"; no new procedural unit appeared), zero-Reden paths, nested turns in procedural `<rede>`s, the draft's schema. Not adopted: lowering group 3 below 600 characters, because a nested presidium turn is never counted (6d) and a missed nested address is a display gap, not a figure.

## Completion summary

- 2026-11-10: Scope Challenge, architecture (9 findings, 2 critical), code quality (2), tests (20), performance, outside voice (Claude subagent, 10), design review (7 passes). Decisions O1-O12.
- 2026-11-12: census of 718 kept + 84 excluded sittings (18/20 not fetched); 341 candidate rows, 136 draft list entries; figures measured (82 kept Reden move in 25 sittings). Re-run: 7 premises checked (3 false, folded in), 8 architecture findings (2 critical) and 1 code-quality finding accepted, tests T6/T11-T13 revised and T21-T23 added, outside voice Codex (9 findings). Critical gaps: 0. New decisions O13-O18; hard cases H1-H7.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|---|---|---|---|---|---|
| CEO Review | `/plan-ceo-review` | Scope and strategy | 0 | not run | scope set by Q13; not warranted |
| Outside Review | Claude subagent (2026-11-10); Codex (2026-11-12) | Independent 2nd opinion | 2 | issues found, folded in | 10 (2 critical); 9 |
| Eng Review | `/plan-eng-review` | Architecture and tests (required) | 2 | ISSUES OPEN | census and figures done; 9 new findings accepted into the plan; 0 critical gaps; owner decisions open |
| Design Review | `/plan-design-review` | UI and UX gaps | 1 | CLEAR (PLAN) | 3 accepted, 1 deferred (O10); T21's zero-Reden wording is new copy for the design pass |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | none |

- **OUTSIDE COVERAGE:** cross-model: Codex reviewed the 2026-11-12 revision (read-only `codex exec`, completed).
- **REVIEW LOG:** not persisted to `~/.gstack`: this spawned session writes only its worktree.
- **VERDICT:** the items the first run left open are closed: the census and every figure are measured, and every finding is mapped into the plan with 0 critical gaps. The status is ISSUES OPEN, not CLEAR, only because the owner decisions below are open. The code waits for W2's PR 1 (sequencing unchanged).

**UNRESOLVED DECISIONS:**
- O1-O12 (2026-11-10, auto-decided) still need the owner's confirmation; O3, O4, O12 were revised by the census; O6 and O11 also need W3's agreement.
- O13 nominations printed as `<rede>` (H6): keep as Reden or procedural; not auto-decided because it is outside ADR 0004's wording (2 kept Reden).
- O14-O18 (auto-decided 2026-11-12) need confirmation: 18/173 as Ansprache (H4), P2's name-stripped role test, no `marker`, the `procedural` list kind, Schäuble's 19/1 binding (H1).
- Hard cases H2 (19/1's empty `<rede>` and Solms's loose opening address), H3 (18/245 Singhammer: Ansprache or Sitzungsleitung), H5 (18/1 Hintze, check the PDF page), H7 (18/113 Pau, deferred).

## Build notes (2026-11-13)

Built on `claude/dreamy-rosalind-cec12d` (main 36bfd08 plus this plan). Where the build departs from the text above:

- **O13 built as option A** (nominations stay Reden): the owner has not decided, and A moves no figure. B is two list entries.
- **O18's person correction is not written.** The list entry carries 11002190 as printed. A `person_corrections.json` partition of Solms's id puts every Solms record under review (`person_registry._on_shared_id`), a figure move in the kept store that belongs with the step that admits 19/1. TODOS.md "ADR 0004 follow-ups".
- **P4 and P5 test whole `<rede>`s only** (see P5), never nested turns: no entry can name a nested marker.
- **An empty listed `<rede>`** (19/1 `ID19100200`) leaves no diagnostic: `speech_segments` drops a turn without words. Its reconciliation status is still `procedural`.
- **Tests use synthetic XML** modelled on the real excerpts, plus T23's replay over the reference store's cached XML (skipped when absent); no new XML fixtures. Test XML reuses real sitting numbers, so `tests/_support.py` installs an empty reviewed list and a test of a real listed sitting installs the shipped one (`shipped_reviewed_units`).
- **The loader is `speech_kinds.reviewed_units()`**, called first by `build_dip_pulse_site.main`, `validate_dip_protocol.main` and `extract_demo_fixture.main` (`ERROR [reviewed-units]`, exit 1), and again by the parser per sitting (cached), so `audit_offline_turns.py` and the preflight script get the same list.
- **P2's typed refusal** is `validate_dip_protocol.UnreviewedUnitError(ValueError)` with `rede_id`; the unlisted P4/P5 candidate raises it too (O6 is W3's).
- **A presidium role on a Rede at persist** raises `derive.PresidiumRoleError`, a `SprechrolleError`, so every caller that stops on an unmapped role stops on it.

### Replay (Verification 2 and 3, 2026-11-13)

Both sides repersisted from the reference store's cached XML (`--offline --repersist` on two clones): the baseline with `origin/main` 36bfd08, the branch on the other, then `scripts/compare_store_values.py` (shared cohort, 718 protocols in both). Every move is one the census measured; nothing else moved.

- Reden 54,937 → 54,855 (−82); `contributions` 42,724 → 42,724, every kind unchanged.
- Sprechrolle bundesregierung 2,849 → 2,790, weitere 22 → 18; CDU/CSU 14,882 → 14,874, SPD 11,555 → 11,550, Grüne 7,670 → 7,667, Die Linke 5,639 → 5,637, FDP 4,374 → 4,373; AfD, BSW, fraktionslos unchanged.
- 24 sittings move (the census text said 25; its per-sitting table has the 24): exactly the per-sitting table above. 18/4 and 20/5 now hold 0 Reden. Characters of all Reden 254,296,521 → 254,287,191.
- Facts: 50 of 1,922 rows move (`docs/plans/adr-0004-facts-old-new.tsv`, old and new per period and metric): erste-reden values in 13 weeks, as in the table above where the store has the week (2014-W07 86 → 91, 2021-W49 10 → 4, 2025-W19 3 → 0, 2025-W20 43 → 46, …); meistdiskutierter-vorgang 2021-10 5 → 1, 2025-03 4 → 1, 2025-05 17 → 15 (the constituent and chancellor sittings); aktivste-abgeordnete 2019-07 2 → 1 (19/109); the rest are percentiles of the same baselines. Publishable weeks 182 → 181: 2025-W19 has no erste-reden fact once 21/2's three oath answers are no debut.
- Excluded sittings, W1's XML, branch parser and shipped list: 18/178 9 Reden + 1 Ansprache, 18/223 0 + 4, 18/245 19 + 2, 19/1 7 + 1 (10 procedural diagnostics; the empty `ID19100200` leaves none), 19/9 14 + 2, 19/19 0 Reden and 21 procedural, 19/73 1 + 1; all seven pass the Sprechrolle check. 18/1 now parses (5 Reden, 6 procedural; Kauder's nomination is one of the 5, O13 A). 14 of the 84 parse (13 before); no sitting refuses on an unreviewed unit or a stale entry.
