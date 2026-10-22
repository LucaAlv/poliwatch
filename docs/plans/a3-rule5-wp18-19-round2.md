# Speech rule 5 for WP 18/19, round 2: rule candidates for sign-off

The full audit ([a3-wp18-19-audit.md](a3-wp18-19-audit.md)) leaves four groups that are too large for exclusions. Each blocks many sittings or miscounts sittings that parse. This file proposes a rule for each one. **Nothing below is implemented.** Each needs the owner's yes, and then a test-first build and a new-rule unit review, as for 6a–6d.

## R1. Consent and offer wording (near-6a: 55 markers, 45 sittings, 28 blocked by it alone)

**Evidence:** the cause of every refusal was checked against the code (column `near_6a_cause` of [a3-wp18-19-blockers.tsv](a3-wp18-19-blockers.tsv)).
- **consent-side 38:** the chair's offer is fine, but the Redner's consent is off the closed list. The wordings are open-ended: "Aber sicher", "Aber jederzeit doch", "Sehr gerne", "Sicherlich, Herr Kollege", "Jederzeit", "Von mir aus", "Och ja", "Ich bitte darum", "Wenn es denn sein muss", "Mit dem größten Vergnügen", "Ja, darf sie", "Er darf, natürlich", "Herr Sarrazin immer", "So ist es", "Das soll er gerne haben", "Ich will versuchen, sie zu beantworten", and more.
- **offer-side 9:** the chair's offer names no Frage or Bemerkung: "Darf sie das?", "Mögen Sie?", "Wollen Sie antworten?", "Gestatten Sie?", "Zusatzfrage", "noch die Chance, etwas zu sagen".
- **other 8:** a recipient mismatch, a "Nein" read as a refusal, a consent printed in a `<name>` element, or the Redner making the offer himself. R1 does not fix these.

The closed list grew from the first 175 files, and it will not converge: almost every new sitting brings a new phrasing. Options:

- **R1a, extend the closed list** with the wordings seen. This is cheap and transparent, but each new WP 18/19 sitting can still bring a new phrase, so it fixes this corpus, not the encoding.
- **R1b, structural consent (recommended):** in an open exchange, a short Redner turn after the chair's offer is consent unless it refuses. A short turn is at most about 12 words, with no "nein", "nee", "nicht", "lieber nicht", "keine" or "später". The asker's turn that follows must still be a non-government MdB named or matching the offer, as today. This reads the structure the closed list approximates. The risk is a short non-refusal that is not consent. The negation list plus the required chair offer keep that narrow. The new-rule unit review would test it.
- **R1c, offer wording:** accept "Darf er/sie (das)?", "Mögen Sie?", "Gestatten Sie?" and "Zusatzfrage" as an offer, but only when the chair's turn also names the would-be asker. This goes with R1a or R1b; without it the 9 offer-side markers stay refused.

## R2. One person, two role spellings (conflicting-roles: 15 WP 18 sittings, 7 blocked by it alone)

`speech_kinds.effective_role` raises when the structured role (`rolle_lang`/`rolle_kurz`) and the role printed after the name map to different sides. In WP 18 the two disagree only in spelling:
- "Parl. Staatssekretär BMF" against "Parl. Staatssekretär beim Bundesminister der Finanzen", with BMWi, BMJV, BMI, BMEL and BMUB the same way;
- a Land member as "Minister" against "Minister (Niedersachsen)", and likewise "Senator (Berlin)" and "Staatsminister (Sachsen)";
- a soft hyphen (U+00AD) in "Staats­sekretärin".

**Proposal:** strip U+00AD from both. Read a "beim/bei der Bundesminister…" long form and its ministry abbreviation as the same side. When one side carries a "(Land)" suffix and the other is the same bare title, take the suffixed one: it says Bundesrat/Land, and the bare title is ambiguous. A real conflict, two different sides after normalisation, still raises.

**Check:** with the raise disabled (an audit copy only), 7 of the 15 parse and 8 show turn blockers that are classified in the audit. The side each normalised role maps to needs a test per spelling.

## R3. 6c floor wording (30 markers in 7 refused sittings, and 4 silent miscounts)

`NESTED_REDE_FLOOR` knows only "Als nächste(r) Redner(in)", "Das Wort hat/erhält" and "gebe … das Wort". WP 18 chairs also say:
- "Nächster Redner ist …", "Nächste Rednerin in der Debatte: …";
- "Der nächste Redner ist …", "X ist der nächste Redner";
- "Für die SPD spricht jetzt …", "… spricht nun …";
- "X hat für die SPD-Fraktion das Wort", "Jetzt hat X das Wort", "Als Nächstes hat das Wort …";
- "Als nächstem Redner erteile ich … das Wort";
- "Letzter Redner in dieser Debatte ist …", "Abschließender Redner …".

`REDE_SALUTATION` misses "Sehr verehrte Frau Präsidentin!".

**Why it matters beyond refusals:** when such a nested Rede contains a "?", it is accepted as a Zwischenfrage instead of refused. This happens in 18/17, 18/30, 18/39 and 18/94: four whole Reden (4200–5000 chars) counted as Zwischenfragen in sittings that parse.

**Proposal:** widen `NESTED_REDE_FLOOR` to these forms. A floor form must still not name a Frage, Bemerkung, Kurzintervention or Erwiderung (`NESTED_REDE_NOT_FLOOR`, unchanged). Add "Sehr verehrte" to the salutation. Each new split gets the DIP Aktivitäten check, as the 7 existing ones passed.

## R4. Surname with a middle initial (recipient-initial: 9 markers, 8 sittings, 4 blocked by it alone)

WP 18/19 XML prints some MdBs with the initial inside `<nachname>`:

| `<nachname>` | Files |
|---|---:|
| W. Birkwald | 124 |
| G. Lämmel | 45 |
| G. Wöhrl | 37 |
| S. Neu | 37 |
| M. Huber | 13 |
| E. Fischer | 12 |
| A. Lamers | 9 |

The chair says "Birkwald", so the recipient match fails. WP 20/21 has none.

**Proposal:** when matching the chair's named asker, compare against the `<nachname>` with a leading initial removed. Whether the stored `last_name` should also drop the initial is an identity question, outside this rule. It touches the identity merge (name+party pass), so it is asked separately.

## Decisions asked

1. R1: a, b or c (b+c recommended), or none. If none, the 45 sittings go on the exclusion list.
2. R2: yes or no.
3. R3: yes or no. If no, 18/17, 18/30, 18/39 and 18/94 must be excluded although they parse.
4. R4: yes or no; and whether `last_name` should drop the initial (identity).
5. Recurring kinds with no rule proposed yet (erwiderung-nested 7 sittings, erklaerung-nested 5, go-debate 4): exclusions now, or a later round.

## Owner decisions, 2026-10-22

1. **R1: R1b + R1c.** Structural consent and the extra offer phrasings. R1a (a longer closed list) is declined.
2. **R2: yes.**
3. **R3: yes.**
4. **R4: yes**, for the recipient match only. Whether `last_name` drops the initial is deferred. After the pilot re-run, check whether the identity merge joins the 7 initial-printed MdBs across WP 18/19 and WP 20/21, and fix it then if it does not.
5. **erwiderung-nested, erklaerung-nested, go-debate:** excluded now, with rules in a later round. Each gets a TODO, and each sitting leaves the list when its rule lands (with old/new figures).
6. **Exclusion list approved: 73 of 484 sittings.** This corrects the 68 in the audit record: 5 sittings are blocked only by the 8 near-6a markers whose cause R1 does not fix. The list holds 70 refused sittings plus 18/28, 18/245 and 19/1, which parse but count wrongly:
   18/1, 18/2, 18/3, 18/6, 18/8, 18/10, 18/11, 18/20, 18/21, 18/26, 18/28, 18/29, 18/36, 18/42, 18/43, 18/50, 18/63, 18/67, 18/83, 18/88, 18/89, 18/95, 18/97, 18/98, 18/110, 18/112, 18/113, 18/117, 18/118, 18/124, 18/127, 18/143, 18/158, 18/159, 18/160, 18/161, 18/170, 18/171, 18/180, 18/184, 18/190, 18/193, 18/215, 18/219, 18/221, 18/241, 18/245, 19/1, 19/12, 19/13, 19/14, 19/18, 19/20, 19/23, 19/32, 19/36, 19/40, 19/42, 19/44, 19/47, 19/59, 19/61, 19/68, 19/92, 19/102, 19/158, 19/170, 19/173, 19/189, 19/192, 19/193, 19/215, 19/239.
   It is computed from [a3-wp18-19-blockers.tsv](a3-wp18-19-blockers.tsv) and assumes the R1–R4 sittings pass their unit review. A sitting that fails its review goes back on the list.
7. **Role-less chair: built in this round** (TODO "Recognize the Sitzungsleitung …"). It fixes the live WP 21 miscount 21/17, and should take 18/28 and 18/95 off the list (18/10 too, unless another blocker turns up behind it). **Presidium Reden (ADR 0004): stays a TODO.** 18/1, 18/245 and 19/1 stay excluded.
8. **Zwischenfrage counting: per exchange.** Consecutive asker markers inside one open exchange, with no new chair offer between them, are one unit. This applies to all Wahlperioden, so report the moved WP 20/21 counts old/new.
9. **Backfill pacing: adopted and built in.** 2 s spacing, about 50 XML per window, a 60-minute pause, and a stop on the first answer over 10 s. Build it test-first. Measure DIP `/person` at the start of the pilot re-run, in small bursts, and stop on the first block.

Build order for the round: R2, R4, R3, R1b+R1c, role-less chair, per-exchange counting, pacing. Each step is test-first and committed with its result. Then the new-rule unit review, the DIP check of the new 6c splits, the exclusion file, and the pilot re-run. Phase 3 still needs the owner's explicit go.
