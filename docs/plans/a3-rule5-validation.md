# Speech rule 5 for WP 18/19 XML: validation record

This file records the check of sub-rules 6a–6d ([a3-rule5-wp18-19.md](a3-rule5-wp18-19.md)), which the owner approved on 2026-10-20. Each sub-rule was built test-first and is its own commit:

| Sub-rule | Commit | What it does |
|---|---|---|
| 6d | d2e33c2 | A nested marker with a presidium `rolle_lang` is Sitzungsleitung. Its text is read as chair text and kept as a `procedural` diagnostic. The elected Präsident's bare "ich nehme die Wahl an." is procedural too. |
| 6c | 918470d | A whole Rede printed inside the previous `<rede>` becomes a Rede of its own, `<outer id>:<marker>`. It is counted in the manifest as `coverage.split_rede_ids`. |
| 6a | 3f73d3f | Two kinds of grant evidence: the Redner's short consent after the chair's offer, and the asker's opening thanks for being allowed. The thanks count over a carried refusal. |
| 6b | 6ba5fa7 | When the chair gives the floor to an MdB whose turn says they were addressed, the turn is a Zwischenbemerkung (`zwischenfrage`). Not when the chair names a Kurzintervention or an Erwiderung. |

## Method

- **Harness:** `~/agent-runs/a3/tools/parse_audit.py` parses the 290 WP 20/21 XML files of the gate store and the 175 downloaded WP 18/19 files. For each file it records the status, the counts per kind and a hash over every unit (kind, rede id, speaker id, char count).
- **Runs:**
  - Baseline from the code before this work: `~/agent-runs/a3/parse-baseline.json`.
  - Final run: `~/agent-runs/a3/parse-rule5.json`.
  - Diff and count scripts: `~/agent-runs/a3/tools/rule5/`.
- **Suite:** 1397 tests, OK (2 skipped).
- **Source fixtures:** the blockers 18/70, 18/71 and 18/100, each trimmed to the one `<rede>`, in `tests/fixtures/a3-rule5/`. Provenance is in `a1-source-manifest.json`.

## WP 20/21: unchanged

Every one of the 290 files keeps its `units_sha` after each of the four commits. No count moved.

`scripts/audit_offline_turns.py` against the parser of 3f2bc97 (`--baseline-parser`, `--baseline-speech-kinds`):
- 290 of 290 files accepted on both sides, with `count_changes` empty.
- Every per-sitting field (counts, unresolved, turns, diagnostics, text hashes) is identical, and so is the committed record `offline-v5-audit.json`: 26267 Reden and 1433 Zwischenfragen.
- On the 175 WP 18/19 files the same audit runs without error: 155 accepted, 20 rejected. That includes 18/10 at the split locator `ID1801002600:2 marker 4`.

One existing test changed: `test_fresh_faction_authorization_requires_new_consent_after_refusal`.
- **What it did:** it removed 20/51's consent and expected a refusal at Ullrich.
- **Why it changed:** Ullrich opens "Vielen Dank, …, dass Sie die Zwischenfrage zulassen", which 6a part 2 reads as grant evidence over a carried refusal.
- **The fix:** the mutation now removes that clause too, so the test still checks that without consent and without thanks the turn is refused.
- The real 20/51 does not change.

## WP 18/19: refusals before and after

| | Files | Refused | Parse |
|---|---:|---:|---:|
| Before (baseline) | 175 | 37 (36 ValueError, 1 SprechrolleError) | 138 |
| After 6d | 175 | 35 | 140 |
| After 6c | 175 | 34 | 141 |
| After 6a | 175 | 22 | 153 |
| After 6b (final) | 175 | 20 | 155 |

- **Now parse (17):** 18/70, 18/71, 18/100, 19/1, 19/90, 19/104, 19/108, 19/118, 19/148, 19/169, 19/177, 19/190, 19/191, 19/199, 19/210, 19/216, 19/219.
- **Lost:** none. Every file that parsed before still parses.
- **Exclusion:** 19/1 is among those that parse, but stays excluded (see below).

**Counts per kind on the 138 files that parse in both runs.** No count changed, and every unit hash is identical:

| Kind | Before | After |
|---|---:|---:|
| rede | 10998 | 10998 |
| zwischenfrage | 529 | 529 |
| kurzintervention | 192 | 192 |
| erwiderung | 168 | 168 |
| zu_protokoll | 631 | 631 |
| befragung_frage | 1560 | 1560 |
| befragung_antwort | 1519 | 1519 |
| fragestunde_frage | 2235 | 2235 |
| fragestunde_antwort | 2220 | 2220 |

**The 17 newly parsing files add:**

| Kind | Count |
|---|---:|
| rede | 1448 |
| zwischenfrage | 124 |
| kurzintervention | 20 |
| erwiderung | 17 |
| zu_protokoll | 103 |
| befragung_frage | 97 |
| befragung_antwort | 95 |
| fragestunde_frage | 102 |
| fragestunde_antwort | 101 |

19/1 is part of these totals. Its Reden are the case described under "Exclusions".

## Review of the units the new rules admit

The harness shows that nothing regressed. It does not show that the units the new rules let through are right. So an instrumented copy of the parser logged every unit that exists only because of 6a–6d. For a Zwischenfrage, that means it fails the old test ("?", the old `announced`, continuation). The run covered all 465 files, and a second pass logged instead of refusing, so later turns in refused files were reached too. Every logged unit was read in the source.

- **WP 20/21:** 0 new-rule units in 290 files.
- **WP 18/19:** 23 new-rule units:

| Rule | Units | Verdict |
|---|---:|---|
| 6a | 17 | correct (consent or opening thanks after a visible offer; a cancelled carried refusal was right in every case) |
| 6b | 2 decided by 6b alone (19/210 m5, 19/216 m6), and 1 with 6a (19/148 m5) | correct |
| 6c | 2 (18/70 Binder, 18/10 Bartz) | correct |
| 6d | 1 Sitzungsleitung (18/100 m3, Lammert) and 1 election acceptance (19/1) | correct; no Präsident or Vizepräsident asking as an MdB was caught |

Four are fragments. The kind is right, but one Zwischenfrage exchange yields two units, because nested turns are counted per marker, as they already are in WP 20/21:
- 19/210 ID1921006100 m3: only a thanks line; the question is m5.
- 19/190 ID1919001300 m7: only a name correction; the question is m8.
- 19/148 ID1914809900 m6: the answer to the chair's "Was war jetzt die Frage?".
- 19/104 ID1910406900 m6: restates the question after the chair's "die Frage ist angekommen".

Whether a Zwischenfrage counts per exchange or per marker is a counting question for both encodings, not a defect of 6a. These four were left as they are.

## Remaining blockers (20)

Each entry is the parser's first blocker in its file. Fixing one can expose the next.

| Sitting | Locator | Group | Why it is still refused |
|---|---|---|---|
| 18/1 | ID1800100100 m2 | exclusion | "Herr Alterspräsident, lieber Kollege Riesenhuber, ich nehme die Wahl gerne an." is not the bare acceptance. The sitting is excluded anyway. |
| 18/10 | ID1801002600:2 m4 | new | 6c splits Bartz's Rede out of Lindner's. Inside it, the chair Bulmahn appears as a marker without a role (18/10 has no `rolle_lang` at all). Liebich's Kurzintervention and Bartz's Erwiderung follow inside the same `<rede>`. Needs a rule for role-less chair markers and for a nested Kurzintervention/Erwiderung. |
| 18/50 | ID1805001800 m4 | 6e | Ministerin Hendricks answers inside the Fuchs exchange. |
| 19/13 | ID191304800 m2 | 6e | In the Befragung, the minister hands a question to a Staatssekretär. |
| 19/32 | ID193207500 m3 | 6f | A Kurzintervention, as the chair named it. |
| 19/92 | ID199211200 m11 | 6f | The addressee answers the Redner's question. |
| 19/102 | ID1910206000 m2 | 6f | The answer to the chair's Rückfrage for the record. |
| 19/189 | ID1918907900 m2 | 6f | Arranging two Kurzinterventionen (procedural). |
| 19/193 | ID1919306300 m2 | 6f | The mask (procedural). |
| 19/101 | ID1910104500 m3 | new (near 6a) | The offer "Gestatten Sie? – Okay." names no question, and "Ja, denn meine Redezeit ist gerade zu Ende." is not a closed-list consent. |
| 19/127 | ID1912711500 m3 | new (near 6a) | The first exchange is fixed. The second has the consent "Sicherlich, Herr Kollege.", and "Sicherlich" is not on the list. |
| 19/158 | ID1915809200 m2 | new | The Redner asks the chair, the chair says "Sie dürfen", and no consent turn follows. |
| 19/170 | ID1917006200 m3 | new (near 6a) | "Ja, gerne." is followed in the same turn by "– Nein, nein, …", and the asker says "dass Sie mir die Frage ermöglichen" ("ermöglichen" is not "zulassen"). |
| 19/173 | ID1917304200 m11 | new | The chair adds a second asker, and the Redner never consents. |
| 19/192 | ID1919201800 m3 | new (recipients) | The chair names "Dr. Höcke"; the asker is Hocker, so `recipient_mismatch`. |
| 19/201 | ID1920109100 m6 | new (near 6a/6b) | The chair asks "Mögen Sie?" without a question word. "Gerne." follows, then "Herr Weiß, Sie haben was zu mir gesagt." The Redner, not the chair, spoke last before the turn. |
| 19/215 | ID1921513700 m4 | new (near 6b) | "– Herr Kollege." is the Redner's own text, not the chair's, so 6b (the chair gives the floor) does not apply. |
| 19/225 | ID1922500300 m3 | new (near 6a) | "Och ja." then "Ich danke für diese Großzügigkeit". |
| 19/227 | ID1922705300 m4 | new | The first Rede is fixed. The second has "Der ist wieder da, ja." and "Danke schön, lieber Hans". |
| 19/239 | ID1923903200 m6 | new (recipients) | The chair names Kubicki before "Frage oder Bemerkung", and only Kleinwächter is parsed as a recipient, so `recipient_mismatch`. "Das schaffe ich." would be a consent. |

The 6e and 6f cases stay refused as decided. Each needs a review: an exclusion or a later rule. The "new" cases are not covered by an approved sub-rule. None of them was widened to fit.

## Exclusions: 18/1 and 19/1

The owner decided on 2026-10-20 that the constituent sittings are exclusions for now. They go through the reviewed exclusion list (`--exclude-document-number 18/1 --exclude-document-number 19/1`, D2), not through parser code.
- **18/1:** still refused (above).
- **19/1:** parses after 6d, but its units are not what ADR 0004 wants:
  - The Alterspräsident's Sitzungsleitung is printed as `<rede>` elements of his own (ID19100100, ID19100200, ID19101000, ID19101200).
  - Schäuble's inaugural address as the new Präsident is its own `<rede>` (ID19101300, role Präsident), and so is his later Sitzungsleitung (ID19101900).
  - All of them are counted as Reden. The acceptance itself (ID19101200 m2) is procedural, as 6d intends.
- **Follow-up:** the TODO "Tell official addresses and presidium Reden apart from Fraktionsreden (ADR 0004)" in TODOS.md covers official addresses.

## Findings outside 6a–6d

1. **Presidium-owned `<rede>` elements are counted as Reden.** This happens in 18/245, which already parsed before this work:
   - Vizepräsidentin Bulmahn's farewell address (ID1824501400);
   - Vizepräsident Singhammer announcing an election result (ID1824502300).

   It happens in 19/1 too (above). 6d covers only nested markers. These counts did not move, and the same TODO lists them.
2. **A chair printed as a marker without a role.**
   - In 18/10 the chair (Bulmahn, SPD) is a `<p klasse="redner">` with no `rolle_lang`. Her question "gestatten Sie eine Zwischenfrage …?" has a question mark, so it would pass as her own Zwischenfrage. 18/10 stays refused, so nothing is counted.
   - A scan of every parsing file (`tools/rule5/chair_scan.py`: a nested unit whose speaker's surname is a chair's in the same sitting) finds 5 units, none moved by this work; one is a real miscount:
     - 21/17 `nested:ID211701400:3`: Ortleb's "Herr Kollege Renner, erlauben Sie eine Zwischenfrage …", chair text counted as a Zwischenfrage in WP 21;
     - 20/102 (Kubicki, 2 units): read as his own MdB turn ("ich bin jetzt dran");
     - 19/120 (Pau, 2 units: "Die Entwaffnung der Szene.", "Ja."): not a chair. Pau asks as an MdB in a Befragung with Seehofer while Schäuble chairs. "Ja." is her answer to the chair's "Nachfrage?", counted as before this work.

   21/17 is a miscount in published-scope data and needs its own fix.

## Next steps

Steps 1 and 2 are done: the full audit of all 484 files, the 6c DIP cross-check (7 of 7 splits confirmed) and the grouped blockers are in [a3-wp18-19-audit.md](a3-wp18-19-audit.md); the rule candidates are in [a3-rule5-wp18-19-round2.md](a3-rule5-wp18-19-round2.md).

1. The full WP 18/19 download (about 310 files) at a gentle rate, once dserver and DIP answer again. Then the counting audit on every file (step 3 of "How it gets checked").
   - Still open: the DIP Aktivitäten cross-check for 6c (ADR 0002). It should list Binder's Rede in 18/70 as a Rede of its own. DIP did not answer in this session, and no cached Aktivitäten for 18/70 were found under `~/agent-runs/a3`.
2. Owner review of the remaining blockers: exclusion or a later rule.
3. The pilot re-run.
4. Phase 3, which needs the owner's go.
