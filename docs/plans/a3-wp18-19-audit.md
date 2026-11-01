# WP 18/19 counting audit on all 484 sittings (2026-10-20/22)

This is step 4 of [a3-next-handoff.md](a3-next-handoff.md). It runs the parser of 6ba5fa7 (speech rule 5 with 6a–6d, [a3-rule5-validation.md](a3-rule5-validation.md)) over every WP 18/19 Plenarprotokoll XML. No parser rule was added or widened. The rules this audit suggests are in [a3-rule5-wp18-19-round2.md](a3-rule5-wp18-19-round2.md) and need the owner's yes.

## Source and method

- **Source:** all 484 XML files from `dserver.bundestag.de/btp/<wp>/<wp><nnn>.xml` (WP 18: 245 sittings, WP 19: 239). They are in `~/agent-runs/a3/wp18-19-xml/`, with sha256 and size per file in `~/agent-runs/a3/wp18-19-xml-manifest.json` (393 MB). The download rate is in [a3-pilot.md](a3-pilot.md), Finding 2.
- **Harness:** `~/agent-runs/a3/tools/` and `tools/rule5/`.
  - `parse_audit.py` gives per file the status, the counts per kind and a hash over every unit. Run: `parse-wp1819-484.json`.
  - `rule5/audit_all.py` runs the repo's `audit_offline_turns.audit()` on every file and records every refused marker, not only the first. It also records a non-turn error as a hard error instead of stopping. Run: `audit-wp1819-484.json`.
  - The repo's `scripts/audit_offline_turns.py` itself stops at the first non-turn `ValueError` (18/101, "conflicting roles"). It was run on the 469 files without such an error (parser sha256 `2210d829…`). It gives the same result as `audit_all` in every sitting: 372 accepted, 97 rejected, 185 unresolved markers. Making the script record such files instead of stopping is a tool fix for later, test-first.
- **Instrumented parser:** `rule5/make_newrule_parser.py` builds a scratch copy that logs every Zwischenfrage admitted only by 6a/6b. It reproduces last session's units on the first 175 files. An independent per-turn diff against the pre-rule-5 parser (`rule5/turn_diff.py`) finds the same 19 units plus the two 6c splits.
- **Review:** Sonnet subagents read every refused marker and every new-rule unit in the source, in seven batches. A second pass checked the cause of each near-6a refusal against the code. The classified list of all 205 markers and 15 hard errors is [a3-wp18-19-blockers.tsv](a3-wp18-19-blockers.tsv).

## Nothing moved in the files checked before

- **WP 20/21:** the units hash of each of the 290 files is unchanged against `parse-rule5.json`.
- **The first 175 WP 18/19 files:** status, error and units hash are unchanged.

The parser did not change, so these were expected to hold. The diff confirms it.

## Files and refusals per WP

| | Files | Parse | Refused at a turn | Refused on "conflicting roles" | Refused markers |
|---|---:|---:|---:|---:|---:|
| WP 18 | 245 | 166 | 64 | 15 | 139 (+20 behind the role error) |
| WP 19 | 239 | 206 | 33 | 0 | 46 |
| **Total** | **484** | **372** | **97** | **15** | **185 (+20)** |

- **The role error:** "conflicting roles" is raised before any turn is classified, so the 15 files were audited again with a scratch copy that does not raise. 7 of them then parse. 8 hold 20 refused markers, which are in the table above as "+20".
- **The share refused:** 112 of 484 sittings, 23%. On the first 175 files it was 20 (11%). The other 309 sittings, mostly WP 18, are harder: 92 of 309 are refused (30%).

## Counts per kind in the sittings that parse

| Kind | WP 18 (166) | WP 19 (206) |
|---|---:|---:|
| rede | 7298 | 16370 |
| zwischenfrage | 651 | 946 |
| kurzintervention | 144 | 346 |
| erwiderung | 108 | 294 |
| zu_protokoll | 887 | 865 |
| befragung_frage | 1154 | 2182 |
| befragung_antwort | 1135 | 2157 |
| fragestunde_frage | 3440 | 3295 |
| fragestunde_antwort | 3399 | 3267 |

These include the sittings with silent miscounts listed below. They are not certified counts.

## Silent miscounts in sittings that parse

These sittings are accepted, but some of their units are wrong. They need an exclusion or a rule before a backfill.

| Sitting | Unit | What is wrong | Found by |
|---|---|---|---|
| 18/17 | `nested:ID1801709200:3` Kudla, 4229 chars | A whole Rede, given the floor as "Als Nächste hat das Wort Bettina Kudla", is counted as a Zwischenfrage. | `rule5/floor_zf.py` |
| 18/30 | `nested:ID1803001600:2` Gehring, 5042 chars | Same, after "Nächster Redner: Kai Gehring". | same |
| 18/39 | `nested:ID1803906300:2` Strengmann-Kuhn, 4903 chars | Same, after "Als nächstem Redner erteile ich das Wort …". | same |
| 18/94 | `nested:ID1809407600:2` Dagdelen, 4529 chars | Same, after "Nächste Rednerin ist Sevim Dagdelen". | same |
| 18/28 | `nested:ID1802802200:2` Singhammer | The chair is printed as a marker without a role, and his "gestatten Sie eine Zwischenfrage des Kollegen Beck?" is counted as his Zwischenfrage. This is the same defect as 21/17. | `rule5/chair_scan.py` |
| 18/245, 19/1 | presidium `<rede>` elements | Counted as Reden (known, ADR 0004 TODO). | earlier record |

How the scans were checked:
- **The floor scan:** it flags every accepted nested Zwischenfrage whose preceding chair text gives the floor in Rednerliste form without naming a question. It found 6. Two are genuine:
  - 18/14 Ströbele, who opens by thanking for being allowed;
  - 20/92 Lötzsch m4, the same asker going on after "Frau Lötzsch hat das Wort", which is a per-marker fragment.
- **The length scan, WP 18–21:** the 2681 accepted nested Zwischenfragen have a median of 723 chars and a 99th percentile of 2006. The 5 over 2500 chars that do not open with a Rede salutation are genuine long Zwischenbemerkungen: 20/111, 18/70, 18/73, 18/77, 18/240. The four floor-wording Reden above are all over 4000 chars and open with a salutation.
- **The chair scan:** it found 12 units. Apart from 21/17, 20/102 and 19/120 (known), and 18/28, all are a Vizepräsident(in) asking as an MdB while someone else chairs: 18/79 Roth; 19/11, 19/53 and 19/58 Kubicki; 19/11 Roth. The 19/77 hit is Michael Roth, a surname clash with Claudia Roth.

## Remaining blockers by group

**Group tags:**
- **Pattern names:** "new" rows are tagged by pattern. "cascade" markers are left out of the file sets, since each falls when its root is resolved.
- **Several tags per file:** a file parses only when every tag in its set is resolved, by a rule or by an exclusion.

| Group | Markers WP 18 | Markers WP 19 | Files touched | What it is |
|---|---:|---:|---:|---|
| near-6a | 42 | 13 | 45 | A granted Zwischenfrage that 6a does not read. Cause per marker:<br>• consent-side 38: the offer is fine, the consent wording is off the closed list ("Aber sicher", "Sehr gerne", "Jederzeit", "Von mir aus", "Wenn es denn sein muss", "Mit dem größten Vergnügen", "Ich bitte darum", …).<br>• offer-side 9: the chair's offer names no Frage or Bemerkung ("Darf sie das?", "Mögen Sie?", "Wollen Sie antworten?", "Zusatzfrage").<br>• other 8: a recipient mismatch, a "Nein" read as a refusal, a consent printed in a `<name>` element, or the Redner making the offer. |
| 6c-floor-wording | 30 | 0 | 7 | A whole Rede printed nested, but the chair's floor wording is outside `NESTED_REDE_FLOOR`: "Nächster Redner ist …", "Für die SPD spricht jetzt …", "X hat … das Wort", "Letzter Redner …". Three openings also miss `REDE_SALUTATION` ("Sehr verehrte Frau Präsidentin!"). 18/83 alone has 16 such markers. |
| conflicting-roles | 15 files | 0 | 15 | One person, two role spellings in the same sitting: "Parl. Staatssekretär BMF" against "… beim Bundesminister der Finanzen", and a Land minister as "Minister" against "Minister (Niedersachsen)". The two map to different sides. |
| 6f | 13 | 10 | 20 | The reviewed one-offs: the addressee answers the Redner's question, a Kurzintervention printed nested, an answer to a Rückfrage, procedural arranging. |
| recipient-initial | 9 | 0 | 8 | The XML `<nachname>` carries a middle initial ("W. Birkwald", "M. Huber"; also "G. Lämmel", "S. Neu", "G. Wöhrl", "A. Lamers", "E. Fischer" occur in WP 18/19, none in WP 20/21). It never equals the chair's surname, so a false `recipient_mismatch` follows. |
| recipients | 4 | 5 | 8 | A real or printed mismatch: a name misprint ("Dr. Höcke" for Hocker), a chair-added second asker, a soft hyphen in "Müller-­Rosentritt", "Klein- Schmeink", a chair correction. |
| erwiderung-nested | 6 | 2 | 7 | The addressee answers a Kurzintervention nested, and the chair's wording ("möchte noch kurz erwidern", "wünschen Sie zu erwidern?") is outside `invited`. |
| erklaerung-nested | 5 | 0 | 5 | A persönliche Erklärung, Erklärung zur Aussprache (§ 30) or zur Abstimmung (§ 31) printed nested. |
| go-debate | 5 | 0 | 4 | Geschäftsordnung statements or motions printed nested. |
| refusal-misread | 5 | 1 | 5 | The Redner's "Nein, …" answers a Zwischenruf, or "normalerweise lasse ich keine Fragen zu. Bei Ihnen mache ich eine Ausnahme", and is read as a refusal. |
| 6e | 1 | 4 | 3 | A government member answers inside an exchange or hands a Befragung question on. |
| role-less-chair | 3 | 0 | 3 | 18/10, 18/36, 18/95: the chair is printed as a speaker marker without a role. |
| others, one or two each | 6 | 7 | 12 | chair-grant-without-consent (3 files), asker-owned-rede (2), gov-member-asks (2: a minister asks a granted Zwischenfrage and is refused as government side), stale-pending-asker, chair-adds-second-asker, near-6b, asker-self-offer, decline-then-kurzintervention. |
| exclusion | 1 | 0 | 1 | 18/1. |
| cascade | 28 | 6 | – | Refused only because an earlier marker in the same Rede was blanked. |

**Per file:**
- **Rule-only, 47 files:** blocked only by the four rule candidates of the proposal.
  - near-6a 28;
  - conflicting-roles 7, and 5 more with conflicting-roles plus a rule-candidate turn group;
  - recipient-initial 4;
  - 6c-floor-wording 3.
- **Exclusion-only, 45 files:** blocked only by groups no rule is proposed for.
- **Mixed, 20 files:** need a rule and an exclusion-kind fix.

The file lists are in "Proposed exclusion list" below. "Rule-only" is an upper bound. The audit blanks each refused turn, and accepting a turn changes grant and continuation state for the turns after it. Every file a rule unlocks needs a new-rule unit review like the one below before its counts are trusted.

## Review of the units the new rules admit

On all 484 files, the instrumented parser logs 34 Zwischenfragen admitted only by 6a/6b. The role-relaxed run of the 15 role-error files adds 3 more, 37 in all. 19 were reviewed last session. The 18 new ones were read in the source:

| Verdict | Units |
|---|---:|
| correct | 15 |
| fragment (one exchange, two markers) | 3: 18/109 `ID1810903100` m3 (opening line, the question is m5); 18/40 `ID1804005000` m4 (thanks only, the question is m6); 18/124 `ID1812403100` m5 (premise only; it sits in a role-error file) |
| wrong | 0 |

So no unit admitted by 6a/6b is wrong. Fragments now number 7 in WP 18/19: the 4 of last session and these 3.

**6c:**
- **Splits:** splits happen in 6 sittings: 18/10, 18/26 (two, one a split of a split), 18/43, 18/70, 18/83. Only 18/70 parses.
- **6d:** unchanged since last session. 18/100 and 19/1 are its only cases in the reviewed set.

## The 6c cross-check against DIP (ADR 0002)

DIP's Aktivitäten (`/aktivitaet?f.plenarprotokoll=…`, cached in `~/agent-runs/a3/dip-aktivitaeten-6c.json`, script `rule5/dip_6c_check.py`) list each split speaker's Rede as an activity of its own. Each sits on a page just after the outer Rede:

| Split | Outer Rede (page) | Split Rede (page) |
|---|---|---|
| 18/70 `ID1807005100:2` | Rief (6702B) | Binder (6704A) |
| 18/10 `ID1801002600:2` | Lindner (625A) | Bartz (625D); her Erwiderung is listed too (627A) |
| 18/26 `ID1802609100:2` | Höger (2134A) | Carsten Müller (2134D) |
| 18/26 `ID1802609100:2:2` | Müller | Brugger (2135D) |
| 18/26 `ID1802609700:2` | Tackmann (2139C) | Spiering (2140B) |
| 18/43 `ID1804301900:6` | Deligöz (3863C) | Hubertus Heil (3866B) |
| 18/83 `ID1808301300:3` | Schwesig (7914D) | Lay (7916C) |

All 7 splits are confirmed. DIP answered all 18 requests at 2 s spacing in under 0.2 s.

## Proposed exclusion list for the owner

Approved already: **18/1, 19/1**.

Proposed in addition. Each goes through `--exclude-document-number`, D2.
1. **Silent miscounts:**
   - 18/28, the role-less chair. Exclude until the role-less-chair TODO is fixed.
   - 18/17, 18/30, 18/39, 18/94. Exclude unless R3 of the proposal is adopted.
2. **Presidium Reden (ADR 0004 TODO):** 18/245, as 19/1 already is.
3. **Exclusion-only refusals (45, including 18/1):** 18/2, 18/6, 18/8, 18/10, 18/11, 18/29, 18/50, 18/63, 18/89, 18/95, 18/97, 18/112, 18/113, 18/117, 18/118, 18/127, 18/158, 18/159, 18/160, 18/170, 18/184, 18/215, 18/221, 19/12, 19/13, 19/14, 19/20, 19/23, 19/32, 19/36, 19/42, 19/44, 19/47, 19/59, 19/61, 19/92, 19/102, 19/158, 19/173, 19/189, 19/192, 19/193, 19/215, 19/239.
   - **Why exclusion is not quite enough here:** D4 refuses these sittings anyway. An exclusion only turns the refusal into a reviewed, recorded gap.
   - **Groups that could become rules later:** erwiderung-nested, erklaerung-nested and go-debate are recurring kinds, not one-offs.
4. **Mixed (20):** 18/3, 18/20, 18/21, 18/26, 18/36, 18/42, 18/67, 18/83, 18/88, 18/98, 18/110, 18/124, 18/143, 18/161, 18/171, 18/180, 18/190, 18/219, 19/18, 19/68. These stay refused even with R1–R4, so they are exclusions too unless the group they also need gets a rule.
5. **Rule-only (47):** exclusions only if the owner declines the matching rule:
   - 18/27, 18/33, 18/43, 18/44, 18/46, 18/60, 18/76, 18/82, 18/101, 18/103, 18/109, 18/122, 18/133, 18/136, 18/146, 18/147, 18/149, 18/151, 18/152, 18/162, 18/164, 18/165, 18/168, 18/173, 18/174, 18/176, 18/179, 18/183, 18/193, 18/197, 18/199, 18/210, 18/218, 18/235, 18/238, 18/241, 18/243;
   - 19/27, 19/40, 19/52, 19/69, 19/101, 19/127, 19/170, 19/201, 19/225, 19/227.

If every rule is declined, the exclusion list is 112 refused sittings plus 19/1, 18/245, 18/28 and the four floor-wording sittings: 119 of 484 (25%). With R1–R4 adopted, it is 73: 70 refused, plus 19/1, 18/245 and 18/28. An earlier draft said 68, which counted all near-6a markers as fixed by R1. But 8 of them have an "other" cause that R1 does not fix, and 5 sittings are blocked by those alone. The 73 holds only if the rule-only files pass their unit review. The owner approved this list on 2026-10-22 ([round-2 decisions](a3-rule5-wp18-19-round2.md#owner-decisions-2026-10-22)).
