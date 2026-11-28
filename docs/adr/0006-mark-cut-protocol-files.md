---
status: accepted
---

# Mark a cut Protokoll file and keep its sitting

Some Protokoll XML files of the Bundestag are first editions that stop partway through their sitting (`docs/source-errors.md`, E16). Each prints "Der gesamte und damit endgültige Stenografische Bericht der N. Sitzung wird am … veröffentlicht"; the final edition came out only as the PDF, and the XML was never replaced. Such an *abgebrochene Protokolldatei* (cut Protokoll file) is marked, and its sitting is kept with everything the file prints. It is not complete for speeches, and what DIP lists for the part it does not print is stored as a list of its own that counts nowhere.

Decided by the owner on 2026-11-23 (D1, "Yes, plan it"), with the end times on 2026-11-24 (D2) and the term and the reader-facing sentence on 2026-11-26. Planned and built in [cut-protocols.md](../plans/cut-protocols.md), steps 1 to 10. When it was decided, 33 of 806 sittings had a cut file (1 in WP 19, 11 in WP 20, 21 in WP 21), and DIP listed 1,189 Reden and 429 Reden zu Protokoll after the cuts. In WP 21 that is 7.5 % of all Reden, the last debates of the longest days.

This is hard to reverse, and a reader will ask why 20 weeks of WP 21 more count as *unvollständig erfasst* than a week's own data suggests, and why WP 21 has no monthly Fakt in the first release.

## The mark

- **Two rules agree on which files are cut.** The notice is printed, and DIP's Aktivitäten list more "Rede" (the chair's farewells and greetings left out) than the file prints, counting a withheld unit as printed only where it would be a Rede (one that would be a Rede zu Protokoll counts with those; one not yet reviewed counts as neither), or more "Rede (zu Protokoll gegeben)" than it holds. A file with the notice whose Aktivitäten list no more is whole (19/107). A sitting DIP has not indexed yet is marked, not assumed whole, and is fetched again until DIP lists its Aktivitäten.
- **A file without the notice that looks cut** (rule 3) stops the store gate for a person to read. It marks nothing.
- **The rule has a version** (`protocol_cut.CUT_RULE_VERSION`), stored per sitting in `speech_rule_inputs.cut_rule_version`. A cached report or a store from another version is stale until `--offline --repersist`.
- **The mark goes when the Bundestag replaces the file**: a re-read of a complete file clears it. A backfill fetches a cut sitting again only when DIP's `xml_hash` differs from the cached file, when its report was read from another file than the cached one, or when DIP had not indexed it.

## What is stored

- **The sitting stays,** with its Reden, Beiträge, Tagesordnungspunkte and votes as the file prints them. Leaving it out as a source defect would have dropped 4,555 stored Reden and 70 votes, and left a larger hole than the one in the file.
- **What DIP lists after the cut** goes to `unprinted_contributions`: each "Rede" DIP places after the last printed `<rede>` by page and quadrant (one in the cut's own quadrant may be that Rede's neighbour and is not listed; without a quadrant only a later page counts), and each "Rede (zu Protokoll gegeben)" no stored one matches by surname in the sitting. Speaker as DIP prints it, page, DIP ids, the MdB where DIP's person resolves; no text.
- **A table, not a flag on `speeches`**, for ADR 0005's reason: a count that forgot to filter would count them.

## Facts

- **A cut sitting is not complete for speeches.** Every Fakt whose basis is speeches, in every week and month that holds it, reads *unvollständig erfasst* and names the sitting ("Sitzung 21/99: Protokolldatei abgebrochen"). The cut outranks withheld Reden as the reason. A report from before the rule never reads as complete.
- ***Die längste Sitzung der Woche*** has a basis of its own, `times`: the parsed XML prints the sitting's start and end, which a cut file still does. Where the printed PDF gives another end than the file's head, a reviewed list (`scripts/reviewed_end_times.json`) corrects it, citing the PDF and its page; `xml_header_json` keeps the file's time, and the Fakt's receipt names both.
- ***Erste Reden*** ranks an unprinted Rede after every printed Rede of its sitting, bound to its person by MdB: a person whose first Rede was not printed has no debut.

## Readers

- The dossier of a cut sitting shows, as a gap, where the file stops, what DIP lists after it, the PDF at that page and DIP's speakers, none of them looking like a Rede.
- One generated sentence says which Reden DIP lists that a count lacks, on a Puls week whose Redeanteil and Rangfolge hold a cut sitting and on a person page with unprinted rows.
- DATA.md and the Daten page give the cut files per Wahlperiode and per sitting from the store (`coverage.cut_protocols`); no figure is typed into a document.

## The minimum for analyses (N9)

A period that holds a cut sitting is thin whatever its share of own words, as a period with an excluded sitting is under ADR 0005: the words after the cut are unknown, so no share can be computed for them. Each analysis applies this at its own grain when it is built; no analysis exists yet.

## Considered Options

- **Exclude the 33 sittings as `source_defect`.** Rejected: drops 4,555 stored Reden and 70 votes, and the coverage gap grows.
- **Name them in DATA.md only.** Rejected: leaves Fakten that claim completeness for weeks that miss Reden.
- **Read the missing part from the PDFs.** Not now (D3): a pilot on five sittings comes after the first release. Until then WP 21 has no monthly Fakt.
- **Judge `laengste-sitzung` by speeches too.** Rejected (D2): its published Fakten over WP 19 to 21 would fall from 92 to 67, and the remaining ones would compare with shorter weeks, though the metric reads only times the cut file prints.
