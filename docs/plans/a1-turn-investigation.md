# A1: investigate missing question-format classification

Date: 2026-10-05. Base: `4818b4c`. Read-only source investigation; no production implementation.

## Result

The proposed D2 choice was premature. The role/faction-less fallback is demonstrable in code and synthetic tests, but no actual turn triggering it was found in the inspected sources. Historical XML instead exposes recoverable classification defects: government roles in printed speaker labels rather than structured role elements, a question-format heading class the parser ignores, and an uppercase question-text class.

Prefer extraction of these source signals before introducing an unclassified contribution kind. The user's request to investigate is not approval of either original D2 option.

## Scope and method

- Census of 290 locally cached XML protocols: WP20 201, WP21 89. For recognized Befragung sections, inspected the initial redner marker of every direct rede; for recognized Fragestunde sections, inspected every direct flat redner marker.
- Befragung census: 79 TOP sections, 7,885 speaker markers (3,995 official, 3,890 member), zero with neither role nor faction.
- Fragestunde census: 76 TOP sections, 4,747 speaker markers (2,687 official, 2,060 member), zero with neither role nor faction. No missing redner element or empty role/faction marker among those classified turns.
- Checked ignored question-format heading candidates in the cached corpus. Two hits were ordinary debates about changes to Regierungsbefragung rules (20/66, 20/76), not missed question formats.
- Downloaded 21 public XML protocols into `/tmp/poliwatch-a1-historical-xml`, separate from the reference cache. WP18: 10, 13, 50, 84, 100, 150, 154, 200, 217, 245. WP19: 10, 13, 32, 50, 79, 100, 145, 150, 200, 208, 239. Wednesday samples were chosen across calendar years to include actual question formats; other samples are spread across the periods.
- The current parser recognizes eight Befragung sections and ten Fragestunde sections in this sample: 406 direct Befragung markers and 1,127 flat Fragestunde markers. None lacks both role and faction. A ninth Befragung, 18/84, is missed by heading extraction; its 51 direct markers also have faction or role evidence.
- Historical sample URLs, byte sizes and SHA-256s are recorded in the temporary directory's `sample-manifest.json`. This is a bounded sample, not an exhaustive WP18/19 validation or complete DIP-enrichment run.
- Cross-checked the concrete WP18 speaker labels and chair announcements against the official PDFs linked below.

## Concrete findings

### 18/13: government speakers appear structurally as faction members

Sources: [official XML](https://dserver.bundestag.de/btp/18/18013.xml), [official PDF, printed pages 903 onward](https://dserver.bundestag.de/btp/18/18013.pdf).

The first speaker, Maria Böhmer, is introduced by the Sitzungsleitung as giving the opening five-minute report. Her marker is:

```xml
<redner id="11002630"><name>
  <titel>Dr.</titel><vorname>Maria</vorname><nachname>Böhmer</nachname>
  <fraktion>CDU/CSU</fraktion>
</name></redner>Dr. Maria Böhmer, Staatsministerin im Auswärtigen Amt:
```

The role exists in `redner.tail`, the printed speaker label, but not in `name/rolle`. `speaker_class` therefore returns MEMBER, and `parse_redner` returns no speaking role. In the Befragung, 14 government-role turns have this structure; the remaining 13 are MdB questions. In Fragestunde, 91 government-role markers similarly appear without structured roles. These are not genuinely unclassifiable speakers.

### 18/84: heading and government-role evidence are both ignored

Sources: [official XML](https://dserver.bundestag.de/btp/18/18084.xml), [official PDF, printed pages 7975 onward](https://dserver.bundestag.de/btp/18/18084.pdf).

The Befragung heading uses `<p klasse="T_ohne_NaS">Befragung der Bundesregierung</p>`. The parser collects only `T_NaS`, `T_fett` and the `T_ZP_NaS` fallback. Its extracted heading is empty, so all 51 direct turns are treated as Reden. The first speaker's printed label names Thomas de Maizière as Bundesminister des Innern; the chair explicitly introduces his opening report. Twenty-six government-role turns lack structured roles, including this opening report; 25 are MdB questions.

Fragestunde uses uppercase `<p klasse="P">` for 11 read-out question paragraphs. `fragestunde_turns` recognizes only lowercase `p` for these questions, so it does not create those read-out question records. This is a separate extraction defect, not uncertainty over their meaning.

### Bounded recovery probe

In memory only, attached a role where the printed speaker-label suffix matches an existing `derive.side_of_role` government rule, and recognized the exact Befragung heading in `T_ohne_NaS`. Fed that temporary XML to the unchanged parser. No cached XML, JSON, SQLite or generated page was altered.

| Section | Current parser | With source role/heading recovery |
|---|---|---|
| 18/13 Befragung | 0 Reden, 27 questions, 0 answers | 1 Rede, 13 questions, 13 answers |
| 18/13 Fragestunde | 185 questions, 0 answers | 94 questions, 91 answers |
| 18/84 Befragung | 51 Reden, 0 questions, 0 answers | 1 Rede, 25 questions, 25 answers |
| 18/84 Fragestunde | 83 questions, 8 answers | 40 questions, 51 answers |

These are probe results, not final corrected counts: the probe intentionally did not fix the uppercase `P` question-text issue, broaden source coverage, or perform full persistence/enrichment.

## Proposed implementation direction

1. Normalize explicit speaker-role evidence from the printed marker when structured role evidence is absent. Validate role suffixes against the existing role mapping; apply the same recovered evidence to classification and persisted Sprechrolle. Never classify all occurrences of a person by their current job: evidence belongs to this source occurrence.
2. Recognize exact question-format headings across source-backed historical paragraph classes, including `T_ohne_NaS`. Do not detect a format merely because an ordinary debate heading mentions Regierungsbefragung.
3. Recognize historical question-text classes such as uppercase `P`, preserving the Sitzungsleitung versus asker distinction.
4. Use chair announcements and TOP/turn sequence as additional explicit procedural evidence. The spoken body can corroborate interpretation, but a question mark or a sentence addressing a minister does not establish a turn kind by itself.
5. Extend historical fixtures with the concrete cases above. Compare labels, text ownership and opening-report counts; do not optimize only for matching DIP totals.
6. After explicit source recovery, reject a genuinely unresolved question-format turn with source diagnostics (D4=A, approved 2026-10-05). Refuse the affected sitting parse; replay must fail before replacing the store. No catch-all contribution kind is introduced.

## Limitations and remaining work

The WP18/19 investigation is sampled; no exhaustive historical census or production normalization has been performed. The implementation plan now defines source-role conflict handling, D4 refusal after exhausted recovery and structured/aggregated diagnostics. Original D2 options remain unapproved history; the evidence-first recovery plan and later D4=A supersede that original proposal. The complete task order and acceptance gates are in [a1-followups.md](a1-followups.md). A1/A3 readiness still depends on implementation and combined A2 validation.

## Implementation evidence (2026-10-05)

The bounded probes above remain the original investigation. Final corrected extraction, source-backed fixture provenance, frozen baseline/current labels and scratch results are recorded in [a1-validation.md](a1-validation.md). Uppercase `P` recovery adds the missing read-out questions in 18/84; opening reports remain Reden. Approved D4 is enforced after explicit role recovery.
