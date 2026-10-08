# Offline rule-5 validation (2026-10-06)

Completed on `fix/offline-preview-rule-v5`, based on PR #86 at `2842ec0`. Existing first-pass changes were preserved and extended. Schema 3, key version 1, speech rule version 5, native identities, raw marker ordinals, nested keys and the A1/A2 registry boundary are unchanged. Rule 5 remains an unpublished follow-up; rule-4 certification does not certify it. No fetching, cache deletion, actual repersistence, database replacement, promotion, publishing or pushing was performed.

**Final read-only audit: 290 accepted / 0 rejected files, 0 unresolved markers, across the same 290 cached XML snapshots.** The direct rule-4 baseline is 249 accepted / 41 rejected. The historical report's 257/33 was not reproduced on this cache. The first rule-5 pass was 277/13 with 17 unresolved markers; its counts, parser hash and unresolved evidence are retained under `first_pass` in [the machine audit](offline-v5-audit.json). Every input source hash was checked against that first pass.

## Source review and treatments

All 33 originally reported first failures, additional question cases, split replies and Frömming's resumption remain covered. The remaining 17 markers now have source-derived regressions. These inspect complete source exchanges and neighboring native turns, assert exact paragraphs and structured speakers, raw ordinals, nested keys, counts and diagnostics. Later Schrodi and Brandner segments, Kotré's later question and Piechotta's later question remain separately owned contributions.

| Sitting / source Rede / markers | Proven treatment |
| --- | --- |
| 20/113 `ID2011305000:3` | Brandner's negotiation stays procedural; adjacent native `ID2011305100` is one Kurzintervention and Rosenthal `ID2011305200` one Erwiderung. Rosenthal's refusal does not authorize a Zwischenfrage. |
| 20/119 `ID2011904400:5` | Fresh Union request and consent replace the earlier Linke refusal. |
| 20/144 `ID2014405100:3,4` | Meister accepts named Schrodi after refusing Beck; the chair's finish instruction preserves Schrodi's continuation and both keys. |
| 20/191 `ID2019101000:2` | Mützenich's delegation request stays procedural; explicit chair agreement authorizes native Scholz `ID2019101100` as one Erwiderung. No Mützenich text attaches to Scholz. |
| 20/208 `ID2020801600:3` | “Cademartori” selects the unique local structured Cademartori Dujisin identity; Donth consents. Native identity and registry matching stay unchanged. |
| 20/51 `ID205104600:4` | Fresh CDU/CSU request and affirmative answer replace the AfD refusal. |
| 20/57 `ID205710600:3` | Kersten's fresh named Auernhammer exchange requires the chair's floor grant; the old AfD request cannot authorize it. |
| 20/88 `ID208803700:3` | Trittin's explicit renewed consent and chair floor identify Gysi as asker, Trittin as addressee. |
| 20/91 `ID209106100:3` | Named Bünger request and contextual consent prove the indirect question without a final question mark. |
| 21/21 `ID212113300:5` | The name correction clears the mistaken request; the corrected Slawik request and fresh consent authorize Slawik. |
| 21/47 `ID214708400:3` | Independent Grünen and named Kotré permissions survive in order. Brugger's question and Kotré's later marker 5 stay valid; other AfD speakers are excluded. |
| 21/56 `ID215612200:4,5,6,7` | Müller's explicit consent precedes the chair's hopes/banter. “Nein. Genau.” responds to that banter; actual refusals still cancel. All four Brandner segments keep separate identities/keys. |
| 21/93 `ID219311800:5` | Chair identifies Sichert's response right; Aumer's fresh named consent replaces refusal. Later Piechotta marker 8 stays valid. |

The full audit also exposed six regressions, now covered by source-derived cases in 20/111, 20/116, 20/175, 21/15, 21/45 and 21/65. Surname particles such as “von” are never shortened aliases; all recipient-bearing question clauses are inspected. Administrative additions retain already authorized recipients, while substantive/banter responses beginning with “Nein” after consent are distinguished from bare or explicit question refusals.

The grant tracker remains the only nested classification path. Names before question wording require an asker predicate; question addressees and unrelated chair addresses cannot become recipients. Named/faction permissions stay separate, and a faction attached to a named recipient does not authorize its other members. Shortened surnames require one local structured source identity. Explicit refusals cancel authorization and remembered continuation; question marks and acknowledgements cannot reverse them. Unsupported procedural exchanges and ambiguous attachments remain rejected.

## Counts and text ownership

The audit checks every one of 1,552 classified nested source segments against its contribution or diagnostic, including later segments after former blockers. It checks source text and owning structured speaker. Diagnostics preserve 17 excluded/merged segments: {'merged_erwiderung': 3, 'merged_rede': 3, 'procedural': 11}. Chair words and comments remain excluded.

Counts below compare the same 290 XML snapshots. Rule-4 counts are partial for its rejected sittings: unresolved segments are blanked only in an in-memory audit copy to expose later blockers. Final rule-5 counts use the original accepted XML. These are audit counts, not a database promotion forecast.

| Kind | Rule-4 audit | Final rule-5 audit | Change |
| --- | ---: | ---: | ---: |
| `befragung_antwort` | 3,901 | 3,901 | +0 |
| `befragung_frage` | 3,961 | 3,961 | +0 |
| `erwiderung` | 596 | 598 | +2 |
| `fragestunde_antwort` | 2,687 | 2,687 | +0 |
| `fragestunde_frage` | 2,701 | 2,701 | +0 |
| `kurzintervention` | 646 | 647 | +1 |
| `rede` | 26,271 | 26,267 | -4 |
| `zu_protokoll` | 859 | 859 | +0 |
| `zwischenfrage` | 1,401 | 1,433 | +32 |

Compared with the first rule-5 pass, 15 previously unresolved segments become Zwischenfragen; the other two become procedural diagnostics. Brandner's adjacent native turn changes from Rede to Kurzintervention; Rosenthal's subsequent reply and Scholz's reply each change from Rede to Erwiderung. Split replies and Frömming's resumption retain one native count each.

## Every remaining unresolved locator

None: every original cached XML parses without in-memory omissions.

## Validation and limits

**1,143 unittest tests pass** with `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`. The focused follow-up suite has 50 tests; the source suite has 10. Negative regressions cover unrelated recipients, addressee/asker confusion, mixed named/faction grants, contextual versus actual “Nein”, missing fresh consent/floor, ambiguous shortened surnames, unsupported procedural requests, mismatched identities, duplicate targets and native Rede/TOP boundary leakage.

Fresh report construction and temporary cached XML reparse preserve diagnostics, structured speakers, contribution units and occurrence IDs for the new procedural exchanges and existing split/resumption cases. Existing tests verify missing/stale provenance rejection, rule-5 provenance acceptance and rejection before replacement in temporary stores. Script compilation, the zero-network demo/publication validation, capability/config commands and rejection of development-marked publication artifacts pass.

This certifies parser behavior on these cached inputs only. It does not certify an existing database, unseen exchanges or a production replay/promotion. The source-backed grant wording remains deliberately conservative; unsupported exchanges must be reviewed rather than authorized by punctuation.

## Reproduce without persistence

```bash
git show 2842ec0:scripts/validate_dip_protocol.py > /tmp/poliwatch-parser-v4.py
git show 2842ec0:scripts/speech_kinds.py > /tmp/poliwatch-speech-kinds-v4.py
/opt/miniconda3/bin/python3.13 scripts/audit_offline_turns.py \
  .context/dip-pulse-site/data/xml \
  --baseline-parser /tmp/poliwatch-parser-v4.py \
  --baseline-speech-kinds /tmp/poliwatch-speech-kinds-v4.py \
  --output /tmp/poliwatch-offline-v5-audit.json
```

Both historical classifier files are loaded for the baseline, so new native-turn corrections cannot alter historical counts. The audit writes only its requested JSON artifact, never fetches or opens a database, and retains raw markers in its in-memory copies. Parser/classifier hashes and every XML source hash are recorded. Repeated/unisolatable failures stop the audit.
