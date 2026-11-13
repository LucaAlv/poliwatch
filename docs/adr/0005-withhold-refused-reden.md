---
status: accepted
---

# Withhold a refused Rede instead of leaving out its whole Sitzung

When the parser cannot read one Rede of a Sitzung, that Rede is withheld and the rest of the Sitzung is kept. The same holds for a Rede the owner has reviewed and put on a list. A withheld Rede keeps its text and its reason in `withheld_units`. It counts nowhere: not as a Rede, not as a Beitrag, and not for a Person or a Zusammenschluss. The Sitzung keeps its other Reden, its Tagesordnungspunkte, its Drucksache links and its namentliche Abstimmungen. A Sitzung stays out whole only for a defect of its source, or for a defect that cannot be narrowed to single Reden.

Decided by the owner as N1 B on 2026-11-07. The build's shape was settled in the eng review of 2026-11-09 (decisions D1 to D10 in [v1-scope-review.md](../plans/v1-scope-review.md), "Eng review: the withholding build"). Built in coverage gate PR 2 ([coverage-gate-pr2.md](../plans/coverage-gate-pr2.md)). Until then, the decision of 2026-10-22 applied: one refused unit kept its whole Sitzung out. That left out 85 of 801 catalog Sitzungen, the longest days of WP 18 and 19, with every vote held on them.

## What is withheld

- **A located refusal.** The parser raises it while it emits one Rede: "unresolved nested contribution" or, in a Befragung, "unresolved nested question-format speaker". Both name the Rede and the marker, and both are raised as the typed `LocatedRefusal`. Every other refusal still refuses the Sitzung. That covers classification, Befragung turns, Fragestunde markers, conflicting roles, Rede reconciliation and the reviewed list.
- **A reviewed entry** in `scripts/reviewed_units.json`, kind `withhold`, with a reason. It names the unit as the parser emits it and the first Redner-ID of its owner. An entry the Sitzung does not match stops the run. Its first entries are the known wrong units of 18/2, 18/29, 18/83 and 19/25 (N7).

## The unit

- **The refused part, not the whole source element (D4).** When the parser has split a `<rede>` because another member's Rede is printed inside it, a refusal in a split part `ID…:n` withholds that part. The outer Rede stays stored. Example: 18/10 `ID1801002600:2`.
- **The whole Rede, with an opening nobody questioned.** No refused marker is a Rede's first. So each withheld Rede includes its speaker's opening, which by itself would have counted. The costliest example is 18/1: the Alterspräsident's opening speech `ID1800100100` is withheld because the one-sentence acceptance of the elected Präsident inside it matches no rule. A withheld host Rede also takes its speaker's own words along when the reviewed list names it for a Rede-shaped Zwischenfrage inside (18/2, 18/83).
- **Own words and other speakers' turns apart.** `withheld_units.text` holds the Redner's own words, formed as `speeches.text` is. The turns of other speakers inside it go to `withheld_turns`, one row per marker, so no word is filed under the wrong name.

## Moved text (D7)

- An earlier rule can move text before the refusal. A resumed Rede's words go back to the same speaker's previous Rede (`merged_rede`), and a reply goes to its Erwiderung (`merged_erwiderung`). That text stays where the rule put it, also when the Rede it came from is withheld later. The withheld record holds what was left.
- Text another Rede gave to a withheld Rede goes with it.
- The source Rede reconciles as `withheld`. Its moved segments are recorded in the diagnostics, which name their target. That is how "partly merged into X, rest withheld" is carried: one status plus the diagnostics. Turns a rule treated as procedural (Sitzungsleitung, an election acceptance) are not speech and are in neither field.

## What stays the same

- **Ids, text, speaker and kind of every other unit.** Each Rede emits its units and diagnostics into lists of its own, which join the Tagesordnungspunkt only when the Rede finishes. So a withheld Rede leaves nothing behind.
- **Sequence of every speech and Rede-based Beitrag (D3).** `speeches.sequence` is the Rede's position among the Tagesordnungspunkt's `<rede>` elements after the split. A withheld or procedural Rede leaves a gap. Nested and Zu-Protokoll Beiträge follow and may shift; their ids do not.
- **The page range of the Tagesordnungspunkt.** It still spans the withheld Rede, because the page range describes the printed source.
- `scripts/check_withhold_one.py` withholds one Rede per Tagesordnungspunkt in every held Sitzung and checks all of this (D6).

## Releases (D5, D9)

- **The run summary** names every Rede a rebuild newly withholds or no longer withholds.
- **The release manifest** lists every withheld Rede (`withheld_reden`).
- **The changelog** names the ones a release adds and releases.
- **The cap.** A weekly release goes out with up to `WITHHELD_CAP = 2` newly withheld Reden. Above that, the release is refused until the owner has read each one and names it with `--confirm-withheld`, because a pile-up points to parser drift. The first release lists every withheld Rede and has no cap. A change of the cap is recorded in the data changelog.

## The list and the store

- **A store must match the reviewed list it was persisted under (R3).** The store keeps a digest of each Sitzung's reviewed entries. Facts, export and pages refuse a store whose digest differs from the current file, until `--offline --repersist` has re-read those Sitzungen. An online run re-reads them by itself.

## Coverage and the bar (N9, gate step 4)

- **Coverage.** DATA.md and the Daten page publish coverage per year, by Sitzungen and by Reden. They give the withheld share by own words per year, per Fraktion and year, and per Sitzung. Withheld own words are divided by own words of all Reden, stored or withheld.
- **The exclusion record.** Every entry of `coverage-exclusions.json` carries a reason code and a sentence. A Sitzung may stay out for good only with `source_defect` or `not_narrowable`. The codes `awaiting_rule` and `awaiting_acquisition` name Sitzungen on their way back. A bare "excluded" is refused.

## Considered Options

- **Withhold the refused Rede (chosen, N1 B).** Every vote, Tagesordnungspunkt and link of the Sitzung stays, and the dataset says exactly what it holds back.
- **Keep the whole-Sitzung rule (rejected).** It left the longest days of WP 18/19 out, with 0 of their votes. A trend over those years would have compared unlike coverage.
- **The whole source `<rede>` with every split part (rejected, D4).** It would withhold the correctly parsed Rede of a second member.
- **A flag on `speeches` (rejected, D2).** Every count would have had to filter on it, and one that forgot would count a withheld Rede silently.

## Consequences

- **Speech rule 8, store schema 12, export format 17.**
- **`audit_offline_turns.py` is retired (D10).** The parser now withholds by itself. The W1 preflight tool that used it is kept in git history at a4acab0.
- **The 85 Sitzungen stay on the exclusion record until T4** acquires their votes, Tagesordnungspunkte and links. At the W1 XML, 70 parse once their refused Reden are withheld (89 Reden), and 4 parse with their reviewed entries applied. Twelve wait on ADR 0004's kinds for presidium and guest Reden. One, 19/36, waits on an annex rule, and 18/20 is a source defect.
- **ADR 0004's presidium kinds land after this decision** and extend it. Their refusal for an unreviewed presidium `<rede>` becomes a third located class. Their kinds join `reviewed_units.json`. Their statuses join the reconciliation.
