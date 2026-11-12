# Coverage gate: W1 (fetch and audit the 85) and W2 (PR 1, inventory and reconciliation)

**Status:** plan, 2026-11-10. Not built. Reviewed under `/plan-eng-review` below.
**Parent:** `TODOS.md` "Coverage gate before the first data release"; `docs/plans/v1-scope-review.md`, "Eng review: the withholding build, T3" (decisions D1-D10, tasks W1-W8). Those decisions are settled and are not reopened here unless the review names a new risk.
**Base:** main 28799ac (after #143, the Reden fix, and #145). Line numbers below are on that commit; the T3 review's numbers predate #141 and #143.

## Goal

Two independent lanes that together unblock PR 2 (W3-W8, withholding):

- **W1**: fetch only the Plenarprotokoll XML of the 85 excluded sittings (84 WP 18/19 plus 20/11) and audit it. The report answers the T3 plan's one unverified premise: once their located refusals are withheld, do the 69 sittings with refused markers parse?
- **W2 (PR 1)**: every `<rede>` in a sitting's XML ends up with exactly one status, and a sitting where one is left over is refused. No stored value changes.

## Environment findings (2026-11-10, this machine)

Research by three subagents, checked here:

| Fact | Receipt |
| --- | --- |
| Only Python on PATH is `/usr/bin/python3` 3.9.6; the scripts need 3.11+ (`str \| None` fails at `stable_ids.py:72`; `scripts/python_version_guard.py:7`). No uv, no pyenv, no conda; `/opt/miniconda3` that `AGENTS.md:9` names is absent. A Codex-bundled `~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3.12` exists and ran `fetch_and_audit.py --no-fetch` cleanly. | `which -a python3`, subagent probe |
| No A3 store anywhere on this machine: no `~/agent-runs`, no `.context/`, no `bundestag-pulse.sqlite`, no cached `plenarprotokoll-*.xml` (searched /Users, /private, /opt, /usr/local, /Volumes). The home directory dates from 2026-11-09: a new machine. The store (about 5.4 GB, 716 held sittings, cached XML) lives on the old one at `~/agent-runs/a3/full`. | subagent search; `docs/plans/reden-outside-tops.md:155` |
| `dserver.bundestag.de` is reachable from this shell (HEAD 200). The T3 review assumed the owner's terminal had to run the fetch because its sandbox blocked it. | `curl -sI` |
| 779 GB free disk. | `df -h ~` |
| A second worktree `claude/correctness-gate-fixes-b22045` exists at 28799ac with no commits yet. If it works on Stage 1's correctness P1s (ADR 0004 presidium kinds), it will touch `validate_dip_protocol.py` too. | `git worktree list` |

Consequences:
1. **E1, Python (R-PYTHON A).** uv 0.13.7 is now at `/opt/homebrew/bin/uv`, with CPython 3.13.18 and 3.11.18 installed (it appeared after the first probe). Every run uses `uv run --python 3.13.18 python …`, plus one test pass on 3.11.18.
2. **E2, the regression corpus (R-CORPUS A).** The owner copies the A3 store from the old machine to `~/agent-runs/a3/full`. PR 1's code and tests can be built before it arrives; PR 1 does not merge until the replay and the parse-level diff on it pass.

## W1: fetch and audit the 85

**Tool:** `docs/plans/withholding-preflight/fetch_and_audit.py` (in the repo, written before #143 landed). Every name it imports exists on main with the expected signature (subagent check, receipts in its report).

### Fixes before the run (same small PR as the report)

1. **B2, #143 drift.** `audit_offline_turns.audit` now calls `adopt_reden_outside_tops` (`audit_offline_turns.py:28`), but `edited_tree` (`fetch_and_audit.py:77-83`) does not. In a sitting with Reden outside a TOP, a split locator is never found and its words count silently as 0 (`:110`, `:114`). Fix: call `dip.adopt_reden_outside_tops(root)` first, in the order `parse_protocol_xml` uses (`validate_dip_protocol.py:1411-1425`).
2. **B3, crash on a sitting-wide refusal.** `edited_tree` runs outside the `try` (`fetch_and_audit.py:94`); `mark_roleless_chairs` can raise "conflicting roles" (`speech_kinds.py` `effective_role`). One such sitting aborts the run before the report is written. Fix: move tree building into the `try` and record the sitting as refused, not narrowable.
3. **Refusal class.** The report holds only the raw error string. Add a `refusal_class` field per sitting from a fixed map (`located_nested_contribution`, `located_nested_question_speaker`, `befragung`, `fragestunde_marker`, `conflicting_roles`, `nested_needs_source_id`, `outside_top`, `fetch_rejected`, `other`) and a tally per class. When an unnarrowable refusal follows located ones, keep the located list too, instead of replacing it.
4. **Compare with the blockers file.** Read `docs/plans/a3-wp18-19-round2-blockers.tsv` (69 sittings, 103 markers [measured: 104 lines less the header]; 86 distinct Rede ids in its `rede` column [measured], where the T3 review cites 87: the report states which count is right and why) and report per sitting: expected located refusals vs found; any sitting that parses although listed, or refuses for a different class.
5. **Name the two unexplained sittings.** The T3 review's finding 8 counted one sitting outside the 69/13/18-20 groups. The subagent found two, 18/124 and 18/173 (`a3-wp18-19-round2-result.md:211`: "unresolved nested contribution" after their role conflict was fixed). Flag them in the report rather than leaving them as ordinary rows.
6. **N9 denominators.** Report each sitting's total words (all Reden, as the audit counts them) beside its words withheld, so the share per sitting is computable now. The share per year and Fraktion needs the held sittings' words too; that comes with the corpus (R-CORPUS) or T4, and the report says so.

### The run

- Sittings: the 84 listed at `docs/plans/a3-wp18-19-round2-result.md:234`, plus 20/11, passed with `--only` (which never reads `<store_dir>`, so the missing store does not block W1). The fix PR adds a `--only-file` reading that list, so the command does not carry 85 ids by hand.
- Pacing: `XmlPacer`, 2 s apart, a 60-minute pause after 50, stop on an answer slower than 10 s. About 65-70 minutes. A rerun skips XML already on disk.
- 18/20 is rejected by design (dserver's 18020.xml is sitting 21, `a3-wp18-19-round2-result.md:136`): it appears as `fetch_rejected` and is refetched on each rerun. At most 68 of the 69 can pass.
- Work dir outside the repo (`~/agent-runs/w1/`): XML in `xml/`, the result in `preflight.json`. Copy `preflight.json` and a short `report.md` (the table per sitting, the tallies, the two flagged sittings, the words) into `docs/plans/withholding-preflight/`.
- Run from this shell in the background (network works), not the owner's terminal, with `uv run --python 3.13.18 python -I …`.

### W1 deliverable

One PR, data and docs only: the script fixes 1-6, `preflight.json`, `report.md`, and a line in TODOS.md's coverage gate step 6 recording the result. Its result feeds PR 2's design (which refusal classes are narrowable in practice, the words withheld for N9, pass-1 moves for D7). The fallback trigger of the coverage gate ("release WP 20 and 21 first … if the first of the proofs above fails") is read from this report.

## W2: PR 1, inventory and reconciliation

### Where things are today (main 28799ac)

```
parse_protocol_xml(xml_text)                         validate_dip_protocol.py:1410
  root = ET.fromstring                               :1411
  >>> NEW: inventory = raw_rede_inventory(root)      (before any tree edit)
  adopt_reden_outside_tops(root)   edits tree        :1412 (wraps Reden under sitzungsverlauf in a TOP; ids kept)
  parse_toc, rid_pages                               :1413-1416
  mark_presidium_fraktionsreden    edits tree        :1420 (drops <rolle>; ids kept)
  mark_roleless_chairs             edits tree        :1425 (sets an attribute; ids kept)
  per TOP (direct children of sitzungsverlauf)       :1426
    split_nested_reden(top)        edits tree        :1449 (rid -> rid, rid:m, rid:m:n ...)
    redes = top.findall("rede")                      :1450
    classify_reden; pass 1 merges                    :1456, :1478-1558
    pass 2: speech | Beitrag | nested | procedural   :1560-1634
    fragestunde_turns (Fragestunde TOPs only)        :1636-1662
  written_contributions(root, ...)                   :1688 (annex blocks matching ZU_PROTOKOLL_ANNEX)
  >>> NEW: reconcile(inventory, report) -> raise on leftover
  return report                                      :1689-1703
```

The callers that reach `parse_protocol_xml`, so all get the check with no further wiring (review checklist class 1): the online build (`validate_dip_protocol.py:4142`, a `ValueError` becomes `DipError(source_rejected=True)`), the offline reparse/repersist (`build_dip_pulse_site.py:1985`, a `ValueError` becomes `CachedReportError`), `audit_offline_turns.py:35`, `extract_demo_fixture.py:49`, and W1's `fetch_and_audit.py`.

### Places a `<rede>` can vanish today without a record

From the subagent's map, each with a receipt:

1. A `<rede>` that is neither a direct child of a TOP (after adoption) nor of `anlagen/anlage/anlagen-text`: under `sitzungsbeginn` or `sitzungsende`, wrapped in another element, or inside another Rede. Never read (`:1426`, `:1450`, `:1367`).
2. Annex blocks whose `anlagen-typ` fails `ZU_PROTOKOLL_ANNEX`: the bare `continue` at `:1354-1355`. §31 and Neudruck stay out on purpose (comment `:1351-1353`, `docs/data-methods.md:21-23`); an unknown title vanishes the same way, unrecorded.
3. A resumed Rede (`:1497-1503`, `:1629`): kept out of `speeches` by `procedural_reden`; its only trace is "procedural" turn diagnostics that do not say "resumed".
4. Duplicate raw ids: `by_id` keeps the last (`:1467`) and nothing checks uniqueness. The `sum(...) == 1` guards at `:1496`, `:1501`, `:1521` suggest the authors expected duplicates.
5. Fragestunde turns with no paragraphs (`speech_kinds.py:610`), and the dead `unplaced` counter (`speech_kinds.py:573`, `speaker` is never `"unplaced"`, so `unplaced_turn_count` is always 0).
6. Marker-level losses inside a stored Rede (other speakers' segments in an annex Rede, `_nested` at `:1385`; empty segments, `:1324`). These are below the Rede grain and out of PR 1's scope (see NOT in scope).

### Design

**Inventory (new, `raw_rede_inventory(root)`).** Called right after `ET.fromstring`, before `adopt_reden_outside_tops`. It walks `root.iter("rede")` over the whole tree (not only `sitzungsverlauf` and `anlagen`: walking everything is what catches vanish 1) and records, per element in document order: the raw `id` (or `None`), and its location class: `top` (direct child of a TOP), `sitzungsverlauf` (direct child, to be adopted), `annex` (direct child of an `anlagen-text`, with its `anlagen-typ`), or `elsewhere` (with the parent tag). It refuses the sitting at once on a duplicate raw id and on a `<rede>` without an id outside an annex (annex Reden without an id are keyed `annex:{i}:{seq}` today, `:1384`, and reconcile on that key).

**Status ledger (R-SHAPE A).** A small in-memory ledger, a plain dict from unit id to status plus a set of the post-split ids created (no new class), is local to `parse_protocol_xml` and passed to the helpers that record into it. Statuses are recorded where the parser decides, not re-derived from report lists:
- `split_nested_reden` records each part `rid:m` it creates (so a part created and later dropped is visible as a leftover);
- pass 2 records `speech` or `beitrag` at the emission point (`:1628-1634`), and `procedural` for a Rede in `procedural_reden` (the resumed case, `:1503`, `:1629`);
- `written_contributions` records `zu_protokoll` for each annex Rede it reads (keyed by id or `annex_rede_key`), and `excluded_annex` with the rule name for every `<rede>` of a block it skips by a named title.

Nothing is added to the report or the store (R-TRACE settled: in memory only). `fragestunde_turns` additionally returns its count of turns dropped empty, for the Fragestunde tally. The dead `unplaced` path stays (TODOS.md entry, R-UNPLACED).

**Statuses (the registry).** One module-level mapping from the emitted unit kind to a status. The ADR 0004 PR extends it with its kinds, and test 9 fails on a kind without a row:

| Status | Recorded at |
| --- | --- |
| `speech` | pass 2, `label.kind is None` and not procedural |
| `beitrag` | pass 2, a Rede-based contribution kind (Kurzintervention, Erwiderung, Befragung Frage/Antwort) |
| `procedural` | pass 2, a Rede in `procedural_reden` (resumed) |
| `zu_protokoll` | `written_contributions`, an annex Rede read (in a TOP or in `sitting_contributions`) |
| `excluded_annex` | `written_contributions`, a block skipped by a **named** exclusion rule: §31 (ADR 0002), the 19/115 second block, "Neudruck eines Redebeitrages" (19/35, 19/45). The rules become a module-level table with the reason each one cites, replacing the comment at `:1351-1353` |

At the end, the ledger is checked against the raw inventory: every raw id, and every split part `rid:…` that `split_nested_reden` recorded, carries exactly one status. The structural checks stay inside this (the outside voice's shape B and the Sonnet reviewer's condition): each raw `<rede>` has a location class, raw ids are unique, and `len(labels) == len(redes)` per TOP (guarding the silent `zip` truncation at `:1631`). Refusal message: `"{wp}/{nr}: rede reconciliation: {rid} ({location}) has no status"`, raised as `ValueError` so both paths above turn it into the existing refusal. Split parts are found by prefix against the post-split ids, using the same `partition(":")[0]` rule the parser uses at `:1452` (one key, one function: a helper `raw_rede_id(unit_id)` used by both).

**Fragestunde.** The inventory also counts, per TOP of the raw tree, the `<p klasse="redner">` markers that are direct children of the TOP (no tree edit moves those: `split_nested_reden` works inside a `<rede>`, adoption wraps only children of `sitzungsverlauf`). For each Fragestunde TOP: raw markers = turns `fragestunde_turns` opened from a marker. Today every such marker either opens a turn or raises (`speech_kinds.py:554-566`), so the check guards later parser changes (PR 2) rather than catching a present loss. Turns dropped for having no paragraphs (`speech_kinds.py:610`) are counted as `empty` in a per-TOP Fragestunde tally, not a refusal: the source printed a marker with no words. Fragestunde turns have no `rede_id` (`validate_dip_protocol.py:1645-1649`), so this tally is separate from the status table keyed on raw rede ids. Chair-read question blocks open turns with no marker (`speech_kinds.py:574-584`) and are not part of the marker count. The count of direct-child markers in TOPs that are **not** Fragestunde is reported by the corpus run, not checked (see NOT in scope).

**Error type.** A subclass `ReconciliationError(ValueError)` so PR 2's typed located refusal and this one can be told apart by type, not by message (T3 review, Section 2 item 1). Existing `ValueError` handlers catch it unchanged. On the offline path the existing message would mislead ("… is not the Plenarprotokoll XML of … delete corrupt XML and run --fetch-xml again", `build_dip_pulse_site.py:1989`): `reparse_cached_xml` catches `ReconciliationError` first and says "rede reconciliation failed for {document_number}: {exc}; the parser left a <rede> without a status, see docs/data-methods.md". Note that on that path one refusal stops the whole repersist and keeps the previous store (`:14785-14795`); that is today's behaviour for every parser refusal, and it is why the corpus run must pass before PR 1 merges.

**One key, one function, for annex Reden too.** An annex Rede without an id is keyed `annex:{i}:{seq}`, where `i` counts every `anlagen-text` block, skipped ones included, and `seq` counts only its direct `<rede>` children (`validate_dip_protocol.py:1350`, `:1384`). A helper `annex_rede_key(block_index, sequence)` builds it for both `written_contributions` and the inventory.

**No version bump.** No stored value changes, so `speech_kinds.VERSION` (7), `SCHEMA_VERSION` (11) and `EXPORT_FORMAT` (16) stay. Consequence, stated in the PR: the plain online build reparses only reports with a stale rule (`build_dip_pulse_site.py:14786`), so held sittings are checked by the replay (R-CORPUS) and every new acquisition, not by the weekly online run.

### Docs

- `docs/data-methods.md:45`: "Rede-/Beitragszuordnungen sind keine Vollständigkeitsbescheinigung" becomes a statement of the reconciliation: every `<rede>` of the XML is stored as Rede, Beitrag or Zu-Protokoll-Rede, marked procedural, or excluded by a named annex rule, otherwise the sitting is refused. Marker-level losses (vanish 6) are named as not covered.
- `docs/data-methods.md:21-23`: the annex rule points to the named table.
- `AGENTS.md:9` names `/opt/miniconda3/bin/python3.13`; it becomes the uv command above.
- The generated DATA.md sentence at `build_dip_pulse_site.py:4304` ("keine Erwerbs- oder Vollständigkeitsbescheinigung") concerns acquisition, not parsing; it stays, checked under review checklist class 11.

### Tests (new file `tests/test_rede_reconciliation.py`, inline XML helpers modelled on `tests/test_a3_rule5.py:9-22` and `tests/test_written_top_association.py:7-22`)

1. A plain sitting reconciles: every status row once (speech, Beitrag, split part, resumed/procedural, zu_protokoll, excluded §31 annex, Fragestunde with an empty turn).
2. A `<rede>` under `sitzungsbeginn` (vanish 1) refuses with its id and location.
3. A `<rede>` in an annex with an unknown title refuses (vanish 2); the same Rede under a §31 title reconciles as `excluded_annex`.
4. A duplicate raw id refuses (vanish 4); a `<rede>` without id outside an annex refuses.
5. `reconcile` called directly with a hand-built inventory and parse result: a split part `rid:2` with no status refuses although `rid` itself is stored; a raw id stored only through its parts reconciles. (No real XML makes today's parser drop a split part, so this is tested at the function boundary, the one PR 2 will extend with `withheld`.)
6. `reconcile` called directly: a Fragestunde TOP with more raw markers than opened turns refuses; an empty turn reconciles as `empty`.
7. Every fixture under `tests/fixtures/` whose root is `dbtplenarprotokoll` reconciles (75 of 77 files [measured]; the other two are an MdB-Stammdaten file and a fragment). Most are excerpts, and only 2 hold `<anlagen>` [measured], so this guards known-good shapes and says nothing about the held sittings; the corpus run does that.
9. Every Rede-based unit kind the parser can emit (`speech_kinds.CONTRIBUTION_KINDS` and the speech kind) has a row in the status registry; a kind without a row fails the test. This is where the ADR 0004 PR registers Sitzungsleitung and Ansprache.
8. Both refusal paths: the online `build_report` raises `DipError(source_rejected=True)`; the offline `reparse_cached_xml` raises `CachedReportError`. One test each, reusing existing harnesses (`tests/test_repersist.py`).
`.gstack/pregate.json` maps `validate_dip_protocol.py` and `speech_kinds.py` to the new file plus `test_reden_outside_tops.py`, `test_written_top_association.py`, `test_speech_kinds.py`.

### Verification (D6 for PR 1, subject to R-CORPUS)

- `uv run --python 3.13.18 python -m unittest discover -s tests`, and once on 3.11.18.
- Regression corpus: every held sitting's XML parsed at main 28799ac and at the PR 1 tip, comparing `json.dumps(parse_protocol_xml(xml), sort_keys=True)` (the parse result carries no timestamp; `build_report`'s fetch metadata is outside it). Required: no sitting refused; the parse result identical except for any trace fields R-TRACE admits. The corpus is the copied A3 store's cached XML (R-CORPUS A). The run also prints a histogram of parent paths for every `<rede>` and the count of direct-child markers in non-Fragestunde TOPs. The approved store replay runs too, and is required (`cp -cR` clones of the untouched copy, repersist at 28799ac and at the PR 1 tip with the same pinned `--today`, `compare_store_values.py --cohort shared`, and "store content unchanged, file kept"). Both pass before PR 1 merges.
- Also parse W1's 85 with the PR 1 parser and record which ones the reconciliation refuses and why. They are refused today anyway; this tells PR 2 whether any vanish case hides among them.
- Record the run in `docs/plans/coverage-gate-w1-w2.md` (this file) under "PR 1 validation".

## Decisions (settled 2026-11-10; full records in the decision ledger below)

- **R-CORPUS: A.** Copy the A3 store from the old machine; the store replay and the parse-level diff both pass before PR 1 merges.
- **R-SHAPE: A.** A status ledger recorded where the parser decides, in memory, with the structural checks inside it. **R-TRACE** is moot: no report field changes.
- **R-SCOPE-WALK: A.** The whole tree, on the unedited root; the refusal rule is final only after the corpus run.
- **R-PYTHON: A.** uv with CPython 3.13.18 (and one 3.11.18 pass), already installed.
- **R-UNPLACED:** left for TODOS.md under CLAUDE.md's rule.

## NOT in scope

- Withholding of any kind (PR 2, W3-W8).
- Marker-level losses inside a stored Rede (vanish 6): below the Rede grain the gate is defined on; a TODO if the review wants it.
- Markers that stand directly in a non-Fragestunde TOP: they belong to no `<rede>`; recorded as a count only if the review asks.
- T4's DIP metadata and votes for the 85; the N8 and T7 reviews.
- `derive.SprechrolleError` escaping `build_report` without `source_rejected` (it subclasses `Exception`, `derive.py:309`): predates this change; a TODO.

## Parallel lanes

| Step | Modules touched | Depends on |
| --- | --- | --- |
| W1 fixes, run, report | `docs/plans/withholding-preflight/` | E1 |
| W2 PR 1 | `scripts/validate_dip_protocol.py`, `scripts/speech_kinds.py`, `tests/`, `docs/data-methods.md`, `.gstack/pregate.json` | E1; corpus per R-CORPUS for verification |

Lane A: W1, run by a subagent in its own worktree (its own branch and PR; the fetch runs about 70 minutes in the background). Lane B: W2 in this worktree. Disjoint files.

Conflict flag: the `claude/correctness-gate-fixes-b22045` worktree plans ADR 0004 presidium kinds (`docs/plans/adr-0004-presidium-kinds.md` on that branch) in the same function, with speech rule 7 → 8. Its plan orders "W2's PR 1 first, then this PR, then W3's PR 2" and registers two statuses (Sitzungsleitung → procedural, Ansprache → stored as its own kind) in W2's reconciliation (its T20). So the status table is one module-level mapping that a later PR extends by adding a row, and `reconcile` reads kinds from it rather than from hard-coded branches. That branch's plans also assume the A3 store (`$A3/gate-v036`), which this machine lacks (R-CORPUS applies to it too).

## W1 status (2026-11-10)

- **First run fetched nothing.** All 50 requests of its first window failed client-side with `CERTIFICATE_VERIFY_FAILED`: uv's CPython reads `/etc/ssl/cert.pem`, which lacks the root of bundestag.de's chain. It was stopped during its window pause. Fix: `SSL_CERT_FILE=/Users/luca/agent-runs/fresh/system-roots.pem` (macOS system roots; one dserver fetch with it answered 200).
- **Script fixes 1-6 and `--only-file` are built,** uncommitted, on branch `worktree-agent-ad36903a450a80b08`, and checked with `--no-fetch` on edited fixtures; not yet on real XML (18/43 `ID1804301900:6` is the real B2 case). The 85-sitting list is `docs/plans/withholding-preflight/sittings-85.txt` there.
- **86, not 87** [measured]: the blockers file lists `ID1802102900` under both 18-20 and 18-21 (dserver's 18020.xml is sitting 21), so it holds 102 real markers in 68 real sittings.
- **Rerun after the fresh store rebuild (owner, 2026-11-10).** The rebuild (`~/agent-runs/fresh/run.sh`) downloads XML from dserver in its backfill steps, and dserver's window budget (~50 XML per 60 minutes) is shared by both runs, so the 85 are fetched only once the rebuild's `05-backfill-21` is done. The rebuild excludes the 85, so its cache holds none of their XML.
- **W1b done (2026-11-12).** Run after the rebuild's downloads ended (15:17Z), 85 of 85, no network failure. 71 sittings parse once withheld, all `located_nested_contribution` (107 markers, 90 Reden, 94,707 words); 13 parse with no refusal; 18/20 rejected by design. 18/124 and 18/173 refuse only located nested contributions. B2's 18/43 `ID1804301900:6` counts 2,389 words. 18/89 has two markers more than the blockers file (`ID1808901500` 3 and 4). No pass-1 moves out of a withheld Rede. `preflight.json`, `report.md` and the TODOS step 6 line are on branch `worktree-agent-ad36903a450a80b08`, uncommitted.

## PR 1 build notes (2026-11-10)

Built in this worktree, uncommitted. Where the build departs from the plan above:
- **Files:** 8 changed plus 2 new (this plan, `tests/test_rede_reconciliation.py`). `scripts/build_dip_pulse_site.py` carries the offline message; `tests/test_a1_followups.py` had two tests that inject a duplicate `<rede>` id, which the raw inventory now refuses before the reply rule reads it, so their expected message changed for that mutation only.
- **Fragestunde:** `fragestunde_turns(…, counts)` reports `markers` only. The planned `empty` tally had no reader once R-TRACE was settled in memory, so it was dropped; data-methods states the rule ("ein Beitrag ohne Text entfällt").
- **`tests/test_written_top_association.py`** is unchanged. It asserts what the written-submission reader skips; the new tests assert which titles reconcile and which refuse. Deriving its cases from `ANNEX_EXCLUSIONS` would make it test the table against itself.
- **`ANNEX_EXCLUSIONS`:** §31 is matched as a prefix (`erklärung(en) nach § 31 …`), because real titles may continue. "Technisch bedingter Neudruck …" and "Zu Protokoll gegebene Ergänzung" get no rule: #143 found no `<rede>` under them in the 716 files (`reden-outside-tops.md:53`), so one appearing later refuses.
- **Checks run:** the suite passes on 3.13.18 and 3.11.18 (2,219 tests, 2 skipped); `py_compile scripts/*.py`; all 75 protocol fixtures reconcile. **W2d:** run 2026-11-12, see "PR 1 validation".

## PR 1 validation (2026-11-12)

**Corpus: the fresh store, not the A3 copy.** The A3 store never arrived on this machine. The fresh rebuild (`~/agent-runs/fresh/run.sh`, finished 2026-11-12 15:22Z, store gate rc=0 on 28799ac) holds 718 sittings with cached XML in `.context/dip-pulse-site/data/xml`, built at the pinned base commit. That meets D6's contract better than the 716-sitting A3 copy, so P0 is dropped. The store was not touched: every run used `cp -cR` clones under `~/agent-runs/w2/`, with `--today 2026-11-12`.

- **Parse-level diff** (`~/agent-runs/w2/corpus_parse.py`): all 718 XML parsed at 28799ac and at the PR 1 tip. 0 refused on either side, 0 differing `json.dumps(parse_protocol_xml(xml), sort_keys=True)` hashes.
- **`<rede>` parent paths** (raw tree): `sitzungsverlauf/tagesordnungspunkt` 72,071; `anlagen/anlage/anlagen-text` 5,017; `sitzungsverlauf` 29 (adopted by #143). None in sitzungsbeginn or sitzungsende, none nested in a `<rede>`. The refusal rule hits no held sitting, so it stands as built.
- **Direct-child markers:** 16,389 in Fragestunde TOPs, 50 in 25 other sittings. The ones checked were short replies outside any `<rede>` ("Ja, gerne.", 19/114, 20/9, 21/24). These are recorded in TODOS ("Rede reconciliation", item 3); the list per sitting is in `~/agent-runs/w2/tip-histograms.json`.
- **Store replay:** `--offline --repersist` at 28799ac (rc=0, 438 s) and at the tip (rc=0). `compare_store_values.py --cohort shared`: 718 protocols in both, 0 changed, 0 vote totals changed, 0 of 1,922 Fakt values moved. Tip code over a clone of the base result: "718 cached reports persisted; store content unchanged, file kept".

- **W1's sittings:** the 84 XML W1 fetched (18/20 rejected) parsed at 28799ac and at the tip: the same 71 refuse at both with the existing located refusal, the other 13 parse with identical results, and none refuses for reconciliation.

**Result:** D6 passes. PR 1 is clear to merge once committed and shipped.

## Eng review (2026-11-10)

**Target:** this file, named by the owner ("plan carefully and review the plans using the appropriate gstack skills"). `/plan-eng-review` read from `~/.claude/skills/gstack/plan-eng-review/` (installed, but not in this session's invocable list, so its SKILL.md and sections were followed by hand). Session: interactive. Codex is not installed, so the outside voice is the native fallback. Design doc check: none for this branch; the T3 review is the design input.

### Reality rows

| Premise | Receipt | Verdict |
| --- | --- | --- |
| 84 WP 18/19 sittings on the exclusion list | `a3-wp18-19-round2-result.md:234`, counted 84 | true [measured] |
| 69 sittings and 103 markers in the blockers file | `a3-wp18-19-round2-blockers.tsv`: 70 distinct sitting values and 104 lines, each less the header | true [measured] |
| 87 refused Reden | same file: 86 distinct values in the `rede` column | **false as cited, 86** [measured]; W1 reports which is right |
| 15 listed sittings are outside the blockers file: the 13 that parse plus 18/124 and 18/173 | `comm` of the list against the file | true [measured]; T3 finding 8 said one |
| 77 real-sitting XML fixtures | `ls tests/fixtures/*.xml tests/fixtures/*/*.xml` | true [measured] |
| No stored value changes in PR 1, so no version bump | persist reads `speeches`, `contributions` and diagnostics, none of the new fields | true by design; proven by the corpus run |
| No held sitting has a duplicate raw `<rede>` id, a `<rede>` without id outside annexes, a `<rede>` outside the read locations, or an annex Rede under an unknown title | no corpus on this machine; fixtures: none (subagent scan of 611 Reden) | **unverified** |
| Every direct-child marker in a Fragestunde TOP opens a turn or raises | `speech_kinds.py:554-566` | true |
| Every `<rede>` in a TOP's `redes` becomes a speech, a Beitrag or a procedural Rede | `validate_dip_protocol.py:1628-1634` | true |

REALITY: premise-table finding 9 premises, unverified=1 (no held sitting hits a new refusal), false=1 (87 vs 86) `docs/plans/a3-wp18-19-round2-blockers.tsv:1`
REALITY: already-done pass origin/main = local main 28799ac; since 2026-11-09 only #143 touched the parser, and this plan is based on it `scripts/validate_dip_protocol.py:1412`
REALITY: surface-check pass `fetch_and_audit.py --help` starts (subagent, Python 3.12); `--only` and `--no-fetch` exist; `compare_store_values.py OLD NEW --cohort shared` (`:787-805`); `build_dip_pulse_site.py --offline --repersist` (`:13649`, `:13666`) `docs/plans/withholding-preflight/fetch_and_audit.py:1`
REALITY: binding-decisions pass decision search empty; T3 D1-D10 bind (two PRs, D6 regression contract, D8 fetch first); the ADR 0004 plan's ordering is compatible `docs/plans/v1-scope-review.md:1170`
REALITY: numbers finding 87 vs 86 Reden; durations 65-70 min [estimated from XmlPacer], about 15 h for 716 sittings [estimated, 50 per hour] `docs/plans/a3-wp18-19-round2-blockers.tsv:1`
REALITY: deferred-asks pass no linked issue; T3's W2 Verify line kept, its store replay subject to R-CORPUS `docs/plans/v1-scope-review.md:1177`
REALITY: pr-count pass no `.gstack/ship-policy.json`; two PRs (W1 data, W2 code), as T3 laid out the lanes; W1 is docs-only, so its ship gate is the small-diff path `docs/agents/review-checklist.md:13`

### Scope Challenge

**What already exists:** the parse path and both refusal paths (`validate_dip_protocol.py:4141-4144`, `build_dip_pulse_site.py:1984-1991`); the location logic of `adopt_reden_outside_tops`; `tests/test_reden_outside_tops.py:49` (every raw id stored, for two sittings); `fetch_and_audit.py` and `audit_offline_turns.audit`; `compare_store_values.py`; the inline XML test helpers. All reused, none rebuilt.

**Complexity:** W2 changes 7 files (`validate_dip_protocol.py`, `speech_kinds.py`, a new test file, `docs/data-methods.md`, `.gstack/pregate.json`, `AGENTS.md`, `TODOS.md`; the last three after the decisions) and adds 1 class (`ReconciliationError`; the ledger is a plain dict). W1 changes 4 (`fetch_and_audit.py`, `preflight.json`, `report.md`, `TODOS.md`). Each PR is under 8 files and 2 classes, so the complexity selectors are skipped. **Scope accepted as-is.**

**Findings:**
1. [CRITICAL] (confidence: 9/10) No A3 store and no corpus on this machine; D6's approved replay cannot run. → R-CORPUS.
2. [CRITICAL] (confidence: 9/10) Python 3.9 only; nothing runs. → R-PYTHON.
3. [CRITICAL] (confidence: 8/10) The one unverified premise: if a held sitting has a duplicate id, an unread `<rede>` or an annex Rede under an unknown title, PR 1 refuses it and breaks D6. Required proof: the corpus run lists every such hit before the refusal rules are final. A hit becomes a named rule with the owner's review, never a silent pass. Recorded as required work.
4. [INFORMATIONAL] (confidence: 9/10) Inside a TOP the reconciliation is near-tautological today (premise row above). Its catches are the location walk, duplicates and annex titles, plus a net for PR 2 and the ADR 0004 PR. Stated so the PR body does not oversell it. Factual correction, recorded.
5. [INFORMATIONAL] (confidence: 8/10) The Fragestunde count as first drafted compared a function's output with itself. Corrected in the plan above: raw markers from the inventory against opened turns. Required proof of the approved "Fragestunde markers are counted against emitted turns", recorded.

### Section 1: Architecture

The design fits inside `parse_protocol_xml`, its existing owner; no new module. Second shape, sketched: a separate `reconcile_report(xml_text, report)` pass that callers run after parsing. Rejected: it would re-parse the tree, it would need the post-split ids the parser already holds, and all five callers would have to remember to call it (red flag 6, two ways to do one task). The chosen shape hides the inventory and the status table behind the one function every caller already uses.

Red flags screened: (4) one key, one function: `raw_rede_id(unit_id)` replaces the inline `partition(":")[0]` at `:1452`; (8) hand-synced list: the annex exclusion titles move from a comment and `tests/test_written_top_association.py:26-45` into one table that the test imports; the status table is one mapping that ADR 0004 extends. No other flag applies.

Failure per new path: a held sitting hits a new refusal (finding 3, corpus run); a future parser change drops a split part (test 5, refusal); an ADR 0004 kind lands without a status row (its T20 test; the refusal names the id).

1. [INFORMATIONAL] (confidence: 8/10) `scripts/validate_dip_protocol.py:1351-1355` — the annex exclusion is a comment plus a `continue`; it becomes the named table. Required by the plan's `excluded_annex` status, recorded.
2. [INFORMATIONAL] (confidence: 7/10) With no version bump, the weekly online run never rechecks held sittings (`build_dip_pulse_site.py:14786`). Accepted: the corpus run checks them once, every new acquisition is checked, and the ADR 0004 PR's rule bump forces a full repersist. Recorded.

Dispositions: 1 and 2 recorded, as required work or accepted fact.

### Section 2: Code quality

1. [INFORMATIONAL] (confidence: 8/10) `fetch_and_audit.py:77-83,94` — B2 and B3 are correctness defects of the W1 tool (silent 0 words, aborted run); fixed in the W1 PR. Required, recorded.
2. [INFORMATIONAL] (confidence: 7/10) `speech_kinds.py:573` — the `unplaced` path is dead (`speaker` is never `"unplaced"`). It predates this change and changes no figure. CLAUDE.md sends "defects that predate the change" to TODOS.md, so PR 1 leaves it and TODOS.md gets an entry. That standing rule settles R-UNPLACED.
3. [INFORMATIONAL] (confidence: 7/10) `derive.py:309` — `SprechrolleError` subclasses `Exception` and escapes `build_report` without `source_rejected`. Predates this change; TODOS.md entry.

Dispositions: 1 required; 2 and 3 deferred to TODOS.md under CLAUDE.md's rule.

### Section 3: Tests

Framework: `unittest`, `python -m unittest discover -s tests` (`AGENTS.md:5`), 71 files.

```
CODE PATHS (PR 1)                                         STATUS
raw_rede_inventory
  ├── <rede> in TOP / under sitzungsverlauf / annex       [GAP] test 1
  ├── <rede> elsewhere (sitzungsbeginn)                   [GAP] test 2 -> refuse
  ├── duplicate raw id                                    [GAP] test 4 -> refuse
  ├── <rede> without id outside annex                     [GAP] test 4 -> refuse
  └── direct-child markers per TOP                        [GAP] test 6
reconcile
  ├── speech / beitrag / split parts                      [GAP] tests 1, 5
  ├── procedural (resumed)                                [GAP] test 1
  ├── zu_protokoll (TOP and sitting level)                [GAP] test 1
  ├── excluded_annex (named titles) / unknown title       [GAP] test 3 -> refuse
  ├── Fragestunde raw markers vs opened turns, empty      [GAP] test 6
  └── leftover id -> ReconciliationError                  [GAP] tests 2-6
refusal surfaces
  ├── online build_report -> DipError(source_rejected)    [GAP] test 8
  └── offline reparse -> CachedReportError                [GAP] test 8
all 77 fixtures reconcile                                 [GAP] test 7
held sittings unchanged, none refused                     [GAP] [→E2E] corpus run (R-CORPUS)
USER FLOWS
  operator repersists a store: a dropped <rede> stops     [GAP] test 8 + corpus run
    the run, naming the id and location
  researcher reads data-methods: the completeness claim   [GAP] checklist class 11
COVERAGE: 0/16 tested today | GAPS: 16, 1 E2E (the corpus run)
```

Value cards:
- T1 Value: protects=every status row reconciles once; fails_when=a status mapping is dropped or a kind double-counted; why_new=no test reconciles units today; seam=none; no_claim=real sittings (inline XML)
- T2 Value: protects=an unread <rede> refuses; fails_when=the walk is narrowed to TOPs; why_new=vanish 1 is silent today; seam=none; no_claim=none beyond protects
- T3 Value: protects=unknown annex titles refuse, named ones reconcile; fails_when=the title table loses a row or the bare continue returns; why_new=vanish 2 is silent today; seam=none; no_claim=titles not yet seen
- T4 Value: protects=duplicate and id-less Reden refuse; fails_when=by_id dedup goes silent again; why_new=nothing checks uniqueness (:1467); seam=none; no_claim=none beyond protects
- T5 Value: protects=a split part without status refuses; fails_when=PR 2 or ADR 0004 drops a part; why_new=no XML shape triggers it today; seam=reconcile() called directly, a real function; no_claim=parser behaviour
- T6 Value: protects=Fragestunde markers balance; fails_when=a turn is dropped beyond empty; why_new=the empty drop is silent (speech_kinds.py:610); seam=none; no_claim=non-Fragestunde markers
- T7 Value: protects=all real fixtures reconcile; fails_when=a rule refuses a known-good sitting; why_new=test_reden_outside_tops.py:49 covers two sittings; seam=none; no_claim=the 716 held sittings (corpus run)
- T8 Value: protects=a reconciliation failure is a source refusal on both paths; fails_when=the error stops being a ValueError; why_new=no reconciliation error exists; seam=none; no_claim=none beyond protects

Regression rule: PR 1 changes the parser behind all 716 held sittings. The approved contract is D6 (T3 review); how it is met without the store is R-CORPUS.

Tests made obsolete: none. `tests/test_written_top_association.py:26-45` keeps its cases but reads the titles from the new table.

### Section 4: Performance

1. [INFORMATIONAL] (confidence: 7/10) One extra `root.iter("rede")` walk and one pass over a sitting's units: linear in the units of one sitting (largest about 300 Reden) [estimated]. Negligible.
2. [INFORMATIONAL] (confidence: 7/10) The corpus run parses 716 sittings twice; the A3 parse audit took about 8 minutes per pass (`a3-pilot-rerun2-handoff.md:117`) [measured there]. Run before ship, not in the suite.

No issues that need a decision.

### Failure modes

| New path | Realistic failure | Test or handling | What users see |
| --- | --- | --- | --- |
| Inventory walk | A held sitting has a `<rede>` in an unread place | corpus run before the rule is final; refusal names id and location | the run stops loudly |
| Annex titles | A new title appears in a new sitting | refusal | the run stops loudly; the owner names the rule |
| Duplicate ids | The source repeats an id | refusal | the run stops loudly |
| W1 fetch | dserver slow or down | `XmlPacer` stops; a rerun resumes | "fetch failed" rows, rerun |
| W1 audit | A sitting-wide refusal | B3 fix: recorded, the run continues | a `refusal_class` row |

Critical gaps: 0 (each failure is loud or tested).

### Outside voice (2026-11-10)

Codex is not installed (`command -v codex` empty), so the native fallback ran: one Plan subagent with a five-minute timer. It reported in 122 s and the timer was stopped. It is not outside coverage.

OUTSIDE VOICE (Claude subagent), condensed; each item checked here:

| # | Severity | Finding | Checked | Disposition |
| --- | --- | --- | --- | --- |
| 1 | High | Offline, one reconciliation refusal stops the whole repersist (`build_dip_pulse_site.py:1984-1991`, `:14785-14795`), with a misleading "corrupt XML" message; without a corpus, the ADR 0004 rule bump becomes the first full test | Confirmed; the message read at `:1989` | Own message added to the design. "Corpus run passes before PR 1 merges" was already D6's approved contract; it is now written as a merge precondition. How the corpus is obtained: R-CORPUS |
| 2 | High | The "77 real-sitting fixtures" are not a corpus: 75 are protocols, mostly excerpts; 2 have `<anlagen>` | Confirmed [measured: root tags, `<anlagen` grep] | Test 7 corrected; its no-claim stated |
| 3 | Medium | The Fragestunde check compared a function with itself, and question blocks open turns without markers | Confirmed; already corrected before this report to raw markers vs marker-opened turns | `empty` moved to a separate Fragestunde tally; question blocks excluded from the marker count |
| 4 | Medium | Re-deriving statuses from report lists mostly re-proves pass 2's loop; a structural post-parse walk catches the same present-day vanishes with no trace fields; and `reconcile(inventory, report)` cannot see a split part the parser created and dropped | Confirmed (`:1631-1634`) | **R-SHAPE** (absorbs R-TRACE) |
| 5 | Medium | Refusing duplicate ids at once is unproven on held data | Same as Scope Challenge finding 3 | Refusal rules are final only after the corpus run lists every hit |
| 6 | Medium | No defined place for ADR 0004 to register statuses | Partly addressed by the registry note | Test 9 added: every unit kind has a registry row |
| 7 | Low | `annex:{i}:{seq}` must be built by one helper | Confirmed (`:1350`, `:1384`) | `annex_rede_key` added to the design |
| 8 | Low | Python is not a blocker: CI tests 3.12, and the Codex 3.12 runtime runs the tools | Confirmed (`.github/workflows/ci.yml`) | **R-PYTHON** offers it as option B |

Cross-model tension: the outside voice recommends (A) for R-CORPUS and the structural walk for R-SHAPE. This review agrees on R-CORPUS and recommends a middle shape for R-SHAPE (below), because PR 2 needs a per-id status ledger anyway.

### Decision ledger (this review)

Process note: the skill asks one question per tool call. The four choices below are independent (no option of one changes another's columns), so they were sent together in one AskUserQuestion call with four questions, to keep the owner's interruptions to one.

#### R-CORPUS: how PR 1 meets D6 without the A3 store here
Finding: Scope Challenge 1 and outside voice 1, CRITICAL, 9/10
Plan baseline: D6 A (T3 review, 2026-11-09): replay the A3 store before and after the PR, 0 moved values, no held sitting refused
Runtime evidence: no store, no cached XML on this machine [searched]; dserver reachable

| Choice | Current | A | B | C |
| --- | --- | --- | --- | --- |
| Corpus | none here | copy `~/agent-runs/a3/full` (about 5.4 GB) from the old machine; run the approved replay plus the parse-level diff | fetch the 716 held sittings' XML (about 15 h at 50 per hour, or an open-data archive if one matches), parse-level diff only | B now, A when the store arrives |
| Merge precondition | — | replay and diff pass | diff passes | diff passes; replay before PR 2 |

State: approved
Actual answer: A, 2026-11-10. The owner's rule ("run each question past a sonnet subagent; if it agrees with your recommendation, go with that"); the Sonnet reviewer answered AGREE.
Accepted scope: the owner copies `~/agent-runs/a3/full` from the old machine to `~/agent-runs/a3/full` here. Before use: count 716 held sittings and their cached XML, checksum a sample against the report JSON's `xml_sha256`, and keep the copy untouched (`cp -cR` clones for every replay, `a3-push-handoff.md:33`). Pin the base commit (28799ac), the store snapshot and `--today`. Then run the approved store replay (repersist at both commits, `compare_store_values.py --cohort shared`, "store content unchanged, file kept") plus the parse-level diff on the store's cached XML. Both pass before PR 1 merges. The reviewer's extra condition: if the copy is not expected within a day or two, fall back to C (refetch now, replay before PR 2); that change goes back to the owner.
History: none

#### R-SHAPE: how statuses are established (absorbs R-TRACE)
Finding: outside voice 4, Medium, 8/10
Plan baseline: T3 "smallest change" step 4: each inventoried id gets one status; leftover refuses. Shape not fixed
Runtime evidence: pass 2 gives every element of `redes` a unit or a procedural mark (`:1628-1634`); the real present-day vanishes are structural

| Choice | Current | A | B |
| --- | --- | --- | --- |
| Shape | draft: statuses re-derived from report lists plus new report trace fields | a status ledger filled where the parser decides (pass 2 emission, `procedural_reden`, annex reading and skipping, split creation), in memory only, checked against the raw inventory at the end; no report field changes | a structural walk only: every raw `<rede>` sits in a read TOP or a read or named-excluded annex block, raw ids unique, `len(labels) == len(redes)`; no per-id ledger |
| PR 2 | — | adds `withheld` as one more ledger status | must build the ledger itself |
| Report bytes | changed | unchanged | unchanged |

State: approved
Actual answer: A, 2026-11-10, by the same rule; the Sonnet reviewer answered AGREE, on the condition that B's structural checks stay inside A.
Accepted scope: a status ledger in memory, filled where the parser decides: pass 2 emission (speech, Beitrag), `procedural_reden` (resumed), split-part creation in `split_nested_reden`, annex Reden read by `written_contributions`, and annex blocks skipped by a named rule. It is checked at the end against the raw inventory, which also enforces the structural checks: location class per `<rede>`, unique raw ids, and `len(labels) == len(redes)` per TOP. A leftover refuses. Report JSON and store are unchanged, so R-TRACE is settled: no new report fields. Notes from the reviewer, checked: pass 1's `merged_rede` and `merged_erwiderung` move marker segments, not whole Reden (`validate_dip_protocol.py:1544`, `:1552`), so no raw id needs a `merged_into` status in PR 1. The whole-Rede case is the resumed Rede, which is `procedural`. PR 2 adds `merged_into` only if D7's withheld path needs it. The drift risk of record calls beside emission sites is covered by test 5 (`reconcile` called directly with a missing status) and test 9 (every kind has a registry row). `annex_rede_key` is shared by the ledger and the inventory.
History: R-TRACE was a separate pending choice; option A makes it moot (in memory only).

#### R-SCOPE-WALK: where the inventory looks
Finding: Section "Places a rede can vanish", vanish 1
Plan baseline: T3: "every `<rede id>` under `sitzungsverlauf` and in the annexes"

| Choice | Current | A | B |
| --- | --- | --- | --- |
| Walk | draft: whole tree | `root.iter("rede")` over the whole tree; a `<rede>` anywhere else refuses (after the corpus run shows the held hits) | only `sitzungsverlauf` and `anlagen`, as T3 wrote; vanish 1 stays silent |

State: approved
Actual answer: A, 2026-11-10, by the same rule; the Sonnet reviewer answered AGREE (fixture scan: all 611 `<rede>` are in a TOP (581), directly under `sitzungsverlauf` (29) or in an `anlagen-text` (1); none in the table of contents or nested).
Accepted scope: walk `root.iter("rede")` on the unedited root, before `adopt_reden_outside_tops`. A `<rede>` nested inside another `<rede>` in the raw XML counts as `elsewhere`. `split_nested_reden` creates parts from markers, not from nested `<rede>` elements, so such an element is never read today. The refusal rule is final only after the corpus run, which prints a histogram of parent paths for every `<rede>`, not just the refusals. Every held hit goes to the owner as a named rule.
History: none

#### R-PYTHON: interpreter for both lanes
Finding: Scope Challenge 2 and outside voice 8

| Choice | Current | A | B |
| --- | --- | --- | --- |
| Interpreter | 3.9.6, nothing runs | `brew install uv`, `uv python install 3.13`; run with `uv run --python 3.13` (also gives the checklist's current-patch run) | the Codex-bundled 3.12 at `~/.cache/codex-runtimes/…/python3.12` (in CI's matrix; not a project-managed interpreter) |

State: approved
Actual answer: A, 2026-11-10, by the same rule; the Sonnet reviewer answered AGREE.
Accepted scope: since this ledger row was drafted, uv 0.13.7 has appeared at `/opt/homebrew/bin/uv`, with CPython 3.13.18 and 3.11.18 installed under `~/.local/share/uv/python/` [checked: `uv python list --only-installed`]. Nothing needs to be downloaded. Runs pin the patch: `uv run --python 3.13.18 python -m unittest discover -s tests`, plus one pass on 3.11.18 (the supported floor, CI's lowest leg). `AGENTS.md:9` names `/opt/miniconda3/bin/python3.13`, which is absent here; PR 1 updates that line to the uv command (docs only).
History: none

Approval readiness: PASS. Checked R-CORPUS (A), R-SHAPE (A, absorbing R-TRACE), R-SCOPE-WALK (A), R-PYTHON (A). Each cites the owner's delegation rule of 2026-11-10 and a Sonnet AGREE. R-UNPLACED is settled by CLAUDE.md's standing rule. Every other accepted item is required proof of these or of the T3 review's approved D1-D10.

#### R-UNPLACED (settled, no question)
The dead `unplaced` path predates this change and moves no figure; CLAUDE.md "Review findings: fix now or defer" sends it to TODOS.md. Same for `SprechrolleError` escaping `build_report`.

### NOT in scope (after the review)

- Withholding (PR 2, W3-W8); `merged_into` statuses, unless PR 2's D7 path needs them.
- Marker-level losses inside a stored Rede (vanish 6), and markers that stand directly in a non-Fragestunde TOP: the corpus run reports their count; a TODO if the count is not zero.
- The dead `unplaced` path and `SprechrolleError` outside `source_rejected`: TODOS.md entries in PR 1.
- T4's DIP metadata and votes for the 85; the N8 and T7 reviews; the N9 minimum.

### Implementation Tasks

- [ ] **P0 (owner)** — copy `~/agent-runs/a3/full` from the old machine to `~/agent-runs/a3/full` here. Blocks PR 1's merge, not its build.
- [ ] **W1a (P1, human ~2 h / CC ~30 min)** — W1 tool fixes 1-6 and `--only-file`. Files: `docs/plans/withholding-preflight/fetch_and_audit.py`. Verify: `--no-fetch` on fixtures; a B3 sitting records a class instead of aborting.
- [ ] **W1b (P1, ~70 min unattended)** — fetch and audit the 85 from this shell. Files: `docs/plans/withholding-preflight/{preflight.json,report.md}`, `TODOS.md` step 6. Verify: W1's Verify line in `v1-scope-review.md`, plus the 18/124 and 18/173 flags and the 86/87 count.
- [ ] **W2a (P1, human ~1 d / CC ~2 h)** — inventory, ledger, registry, `annex_rede_key`, `raw_rede_id`, `ReconciliationError`, and the offline message. Files: `scripts/validate_dip_protocol.py`, `scripts/speech_kinds.py`.
- [ ] **W2b (P1, human ~1 d / CC ~1.5 h)** — tests 1-9. Files: `tests/test_rede_reconciliation.py`, `tests/test_written_top_association.py` (imports the title table), `.gstack/pregate.json`. Verify: the suite on 3.13.18 and 3.11.18.
- [ ] **W2c (P2, CC ~20 min)** — docs. Files: `docs/data-methods.md`, `AGENTS.md:9`, `TODOS.md` (two deferred entries). Verify: review checklist class 11.
- [ ] **W2d (P1, about 1 h of run time, after P0)** — corpus run (parse-level diff plus histograms) and store replay at 28799ac and at the tip. Any held hit goes to the owner before the refusal rule is final. Record under "PR 1 validation" here.

### Completion summary

- Step 0 scope challenge: scope accepted as-is; 5 findings (2 critical environment gaps, both resolved by decision).
- Architecture: 2 informational findings; second shape considered and rejected.
- Code quality: 3 findings (1 required, 2 deferred to TODOS.md).
- Tests: diagram produced, 16 gaps, 9 tests specified with value cards, 1 E2E (the corpus run).
- Performance: no issues.
- Outside voice: native fallback (Codex not installed), 8 findings: 6 applied, 2 turned into decisions.
- Decisions: 4 asked, all settled A by the owner's Sonnet-agreement rule; 1 settled by CLAUDE.md.
- Unverified premises: 1 (no held sitting hits a new refusal), discharged by W2d before merge.
- Critical gaps: 0.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | covered by the v1 scope review (`v1-scope-review.md`) |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | Codex not installed |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR | 18 findings, 0 critical gaps; 4 decisions, all A |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | no UI in scope |
| Outside Voice | native fallback | Independent plan challenge | 1 | issues_found | 8 findings, resolved above |

- **OUTSIDE COVERAGE:** none from another model. The native Plan subagent (same model family) reported in 122 s; four Sonnet subagents gave second opinions on the four decisions, all AGREE.
- **VERDICT:** ENG CLEARED. W1 and W2a-c can start; PR 1 merges only after P0 and W2d.

NO UNRESOLVED DECISIONS
