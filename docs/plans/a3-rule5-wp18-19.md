# Speech rule 5 for WP 18/19 XML: sub-rules for sign-off

The owner decided on 2026-10-20 to extend speech rule 5 to the WP 18/19 encodings ([a3-pilot.md](a3-pilot.md), Finding 1). [ADR 0004](../adr/0004-presidium-counts-for-the-fraktion.md) settles the presidium. This file proposes the sub-rules. Nothing below is implemented; each one needs a yes before it goes in.

## Evidence

- Source: 175 WP 18/19 XML files.
- Blockers: the 37 refusals, each with the text before the blocking turn and the turn itself, in [a3-rule5-wp18-19-blockers.txt](a3-rule5-wp18-19-blockers.txt).
- The first column of that list is a rough automatic sort. The grouping below is by reading the turns.
- Each refusal is the parser's *first* blocker in its file. A file can hold more, which the full audit (step 3 of "How it gets checked") lists.

| Group | Blockers | Examples |
|---|---:|---|
| A. A granted Zwischenfrage or Zwischenbemerkung whose grant or thanks rule 5 does not read | about 25 | 19/127 "Aber gern." then "Vielen Dank für die Möglichkeit einer Zwischenfrage"; 19/104 "Vielen Dank, dass Sie die Zwischenbemerkung zulassen"; 19/227 "Die will ich erlauben, ja."; 19/239 "Das schaffe ich." then the chair's "Dann, bitte."; 18/71 "Aber ja." |
| B. The chair gives the floor to an MdB who was addressed, with no question asked | about 4 | 19/210 "Sprechen Sie." then "weil Sie mich ja indirekt angesprochen haben"; 19/215 "Herr Kollege." then "Sie haben mich jetzt gerade direkt angesprochen"; 19/216 |
| C. A whole Rede printed inside the previous one | 2 | 18/10 "Als nächste Rednerin spricht die Kollegin Julia Bartz." then Bartz's whole Rede; 18/70 Binder |
| D. Sitzungsleitung and the constituent sitting | 3 | 18/100 Präsident Lammert gives the floor (a nested marker with role Präsident); 18/1, 19/1 the elected Präsident's "ich nehme die Wahl an" |
| E. A government member inside an exchange | 2 | 18/50 Ministerin Hendricks answers inside the Fuchs exchange; 19/13 in the Befragung the minister hands a question to a Staatssekretär |
| F. One-offs | about 5 | 19/92 "Nein, nein, …", the addressee answering the Redner's question; 19/189 arranging two Kurzinterventionen; 19/193 the mask; 19/32 "es wäre eigentlich eine Zwischenfrage gewesen", given as a Kurzintervention; 19/102 the answer to the chair's Rückfrage for the record |

## Proposed sub-rules

**6a. More grant evidence (group A).**
- Today's grant patterns (`NESTED_GRANT_EVIDENCE`) read only the chair's wording.
- Proposal: a nested MdB turn is a Zwischenfrage (or Zwischenbemerkung, the same kind) when either of these holds:
  - The Redner's own last turn before it is a short consent: at most about ten words, of the closed list "Ja", "Gerne", "Gern", "Bitte", "Selbstverständlich", "Natürlich", "Immer", "Klar", "Aber ja / gern / natürlich", "Die will ich erlauben", "An mir soll das nicht scheitern", "Das schaffe ich". The consent must follow the chair's offer of a question in the same exchange.
  - The turn itself opens by thanking for being allowed to ask. The patterns are "Dank … (für) das Zulassen / die Zulassung / die Möglichkeit … (Zwischen)frage / Bemerkung", "dass Sie die … Frage / Zwischenfrage / Zwischenbemerkung / Bemerkung zulassen", and "Es zeichnet Sie aus, dass Sie …".
- The question mark stays optional, as it is today for an announced grant.
- **Counts:** these become Beiträge (`zwischenfrage`), never Reden.

**6b. An addressed MdB given the floor (group B).**
- Proposal: when the chair gives the floor with no question being asked ("Sprechen Sie.", "Herr Kollege.", "So, jetzt."), and the turn says the speaker was addressed ("angesprochen", "Sie haben mich …"), it is a Zwischenbemerkung (`zwischenfrage`).
- Alternative: keep refusing. These are rare, and each such sitting would then need an exclusion.

**6c. A whole Rede nested (group C).**
- Proposal: when the chair's text before the turn gives the floor in the form of the Rednerliste ("Als nächste(r) Redner(in) spricht …", "Das Wort hat / erhält …"), and the turn opens with a salutation ("Sehr geehrte …", "Frau Präsidentin! …"), the turn becomes a **Rede of its own**.
  - Its id is derived from the outer Rede id and the marker. Like the existing synthetic ids, it is counted in the manifest.
  - The outer Rede ends at the marker.
  - The DIP Aktivitäten check (ADR 0002) confirms the count per sitting.
- Alternative: refuse, and list these sittings as excluded. That loses whole Reden.

**6d. Sitzungsleitung and the constituent sitting (group D).**
- Per ADR 0004, a nested marker whose `<rolle_lang>` is Präsident, Vizepräsident(in) or Alterspräsident is Sitzungsleitung, which is excluded and kept as a `procedural` diagnostic.
- The elected Präsident's short acceptance ("ich nehme die Wahl an", within the election TOP) is excluded the same way: it is part of the procedure.
- The new Präsident's inaugural address that follows is an official address on behalf of the Bundestag. Whether the XML gives it a `<rede>` of its own or continues it in the nested acceptance turn is not yet checked. Per ADR 0004 it is not counted as a Fraktionsrede; until official addresses get their own treatment, it is refused. Proposal: refuse 18/1 and 19/1 for now and list them as exclusions, or decide the treatment of official addresses now.

**6e. A government member inside an exchange (group E).**
- 18/50: an answer by a member of the government inside a Zwischenfrage exchange is not a Rede. Proposal: a Beitrag of its side, like a Befragung answer, kind `erwiderung`.
- 19/13: in a Befragung, a minister's hand-over to a Staatssekretär is procedural (excluded).
- These are two cases only. Each would be checked by hand in the audit.

**6f. One-offs (group F).** Proposal: no general rule, and each case is checked by hand in the audit:
- procedural, excluded: 19/189 (arranging two Kurzinterventionen) and 19/193 (the mask);
- a Zwischenfrage by 6a: 19/92 (the addressee answering the Redner's question) and 19/102 (the answer to the chair's Rückfrage);
- a Kurzintervention, as the chair named it: 19/32.

## How it gets checked

1. Test-first per sub-rule, on trimmed fixtures from the blockers above (provenance in `a1-source-manifest.json`), with negative cases. Two examples:
   - a consent "Ja" with no offer of a question is not a grant;
   - a salutation without a floor-giving is not a new Rede.
2. Re-run `scripts/audit_offline_turns.py` on the 290 WP 20/21 XML files. The target is 0 changed counts against the rule-5 record ([offline-v5-validation.md](offline-v5-validation.md)). Any change is listed with its old and new values.
3. Run the same audit on every WP 18/19 file. This needs the rest of the download, about 310 files, at a gentler rate once dserver answers again. The output is a counting record like offline-v5-validation.md: counts per kind, the remaining blockers, and the cases checked by hand.
4. Only then: the pilot re-run, then Phase 3.

## Decisions (owner, 2026-10-20)

- 6a, 6c and 6d: approved as proposed.
- 6b: approved as a rule (Zwischenbemerkung, kind `zwischenfrage`).
- 18/1 and 19/1: exclusions for now; official addresses get their own TODO.
- 6e and 6f were not asked: their sittings stay refused until each is reviewed (exclusion or a later rule).

## Decisions asked (answered above)

- 6a, 6c and 6d as proposed?
- 6b: rule or refuse?
- 19/1 and 18/1 (the inaugural addresses): exclusions for now, or decide official addresses now?
