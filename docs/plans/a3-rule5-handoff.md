# Handoff: speech rule 5 for WP 18/19 XML (A3, next session)

Read this whole file first, then [a3-rule5-wp18-19.md](a3-rule5-wp18-19.md) (sub-rules and owner decisions) and [ADR 0004](../adr/0004-presidium-counts-for-the-fraktion.md). Do not re-read the A3 plan or pilot record unless a step below needs them.

## State (2026-10-20)

- **Worktree:** `/Users/Luca/Projects/poliwatch/.claude/worktrees/a3-plan`, branch `worktree-a3-plan`, pushed. Tip 89fed71 plus this file.
- **Done:**
  - Phase 0 gate ([a3-gate-validation.md](a3-gate-validation.md)); see also the pilot record [a3-pilot.md](a3-pilot.md).
  - Lanes A–D of the plan.
  - Issue #94.
- **Not started:** the rule-5 implementation, the pilot re-run, Phase 3.
- **Your task:** implement sub-rules **6a, 6b, 6c, 6d**, all approved by the owner, test-first (tdd skill), until the WP 18/19 blockers they cover parse and WP 20/21 does not move.
- **Exclusions instead of rules:**
  - 18/1 and 19/1 become exclusions (owner decision; official addresses get their own TODO, so write that TODO).
  - 6e and 6f cases stay refused; list them, do not add rules.

## Work efficiently (owner's request)

The previous session ran out of context by reading large code regions and dumping long outputs.
- **Delegate by the CLAUDE.md tiers:**
  - `sonnet` subagent: read a group of blocker exchanges and propose the narrowest regex or state change in `speech_segments` (`scripts/validate_dip_protocol.py` ~560–800) or the classification near ~1040.
  - `haiku` subagent: run the suite and the harness, and report pass/fail plus the diff only.
- **Keep the main context small:**
  - Read only the lines you edit.
  - Filter every command to failures and counts.
  - Never print whole files or the blocker list.
- **One sub-rule at a time:** test → change → harness diff → commit.

## Tools (`~/agent-runs/a3/tools/`)

**`parse_audit.py SCRIPTS_DIR OUT.json`**
- Parses all 290 WP 20/21 XML files (`~/agent-runs/a3/gate/data/xml`) and the 175 downloaded WP 18/19 files (`~/agent-runs/a3/wp18-19-xml`).
- Records per file: status, counts per kind and a unit hash. Takes about 2.5 min.
- Baseline from the current code: `~/agent-runs/a3/parse-baseline.json` (428 ok, 36 ValueError, 1 SprechrolleError).
- Diff a new run against it with a few lines of Python.
- **The target:** every WP 20/21 key keeps its `units_sha`, and the WP 18/19 refusals drop.

**`instrumented_validate_dip_protocol.py`**
- A copy of the parser whose "unresolved nested contribution" error appends the refusing flags.
- To use it, copy it as `validate_dip_protocol.py` into an empty directory. Put that directory first on `sys.path` and the real `scripts/` second.
- It is stale once you edit the parser. Re-create it by adding the same flags line at the raise.
- Flag results for the current code: `~/agent-runs/a3/wp18-19-flags.txt`.

**`dump_rede.py STEM REDE_ID [FROM TO]`**
- The element sequence of one `<rede>` (markers, chair `<name>`, paragraphs) between two marker numbers.
- In zsh, pass multi-word args with `${=var}`.

**`trim_fixture.py SRC OUT NEEDLE...`**
- Trims an XML to the TOPs that contain a needle, for test fixtures.
- Record provenance in `tests/fixtures/a1-source-manifest.json`; source sha256 with `shasum -a 256`.

**Other files:**
- `counted_build.py` wraps a build and counts HTTP requests. It is for the pilot re-run, not this task.
- Blockers with context: [a3-rule5-wp18-19-blockers.txt](a3-rule5-wp18-19-blockers.txt).

## What is already known about the blockers

- **18/71:** the chair's request "darf Ihnen der Kollege Burkert eine Zwischenfrage stellen?" is not in `request_wording`, so `pending_request` stays empty and the consent "Aber ja." is never read.
- **19/127:** the consent "Aber gern." fails `(?:Aber )?(?:Sehr )?Gerne\b` (it says "gern").
- **19/104 and other `refused: True` cases:** a refusal carried over from an earlier exchange in the same Rede blocks a later turn that thanks for being allowed ("Vielen Dank, dass Sie die Zwischenbemerkung zulassen"). Per 6a, an opening thank-you that is not negated (`speech_kinds.NOT_GRANTED`) counts as grant evidence over a carried refusal.
- **19/192 and 19/239:** the refusing flag is `recipient_mismatch`. Check them before deciding whether 6a covers them.
- **6c (18/10, 18/70):** a whole Rede printed after "Als nächste Rednerin spricht …" or "gebe das Wort an …", opening with a salutation, inside the previous `<rede>`. It becomes a Rede of its own, with an id derived from the outer Rede id and the marker (follow the existing synthetic-id convention and its manifest count). The outer Rede ends at the marker.
- **6d:** a nested marker whose `<rolle_lang>` is (Vize|Alters)Präsident(in) is Sitzungsleitung: excluded, with a `procedural` diagnostic. It must never reach `derive.sprechrolle`. The same goes for the elected Präsident's "ich nehme die Wahl an".
  - In WP 18 the chair is sometimes a `<p klasse="redner">` marker with that role, not a `<name>`. Treating it like `<name>` (chair text) probably also lets later requests be read.
  - Presidium roles stay out of `SPRECHROLLE_RULES` (ADR 0004).

## Rules of the project

- The tdd skill applies to every change.
- Pre-release: change in place.
- Report old and new values for any moved count.
- Commit per sub-rule with the harness result in the message.
- Python `/opt/miniconda3/bin/python3.13`. Tests: `-m unittest discover -s tests` from the worktree.
- Never mutate `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site`.
- **dserver.bundestag.de and DIP** stopped answering after a few hundred requests on 2026-10-20. Do not download more XML in this task; work on the 175 files.

## Done when

- 6a–6d are implemented with tests.
- The harness shows every WP 20/21 `units_sha` unchanged; any change is a bug or is reported with old and new values.
- There is a record `docs/plans/a3-rule5-validation.md` with:
  - WP 18/19 refusals before and after;
  - counts per kind before and after on the files that parse in both;
  - the remaining blockers with their group (6e, 6f, or new);
  - the 18/1 and 19/1 exclusions.
- The TODO for official addresses is written.
- Then tell the owner. The next steps are the full WP 18/19 download at a gentle rate, the pilot re-run and Phase 3. Phase 3 needs the owner's go.
