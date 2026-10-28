# Errors in the source files

A list of places where an official source file says something wrong or files content in the wrong place. The point is to send these to the publishers for correction.

**In scope:** errors in what the Bundestag publishes:
- the Plenarprotokoll XML at `dserver.bundestag.de`;
- the DIP API;
- the roll-call pages at `www.bundestag.de`.

**Not in scope:** gaps in our own parser. A sitting our validator refuses is listed here only once a human has read the source and found the source itself wrong. Parser work lives in TODOS.md.

**Who to send it to:** not yet decided.
- The Plenarprotokoll XML and DIP are published by the Deutscher Bundestag.
- Find the right contact from the publishers' own pages before sending anything. Don't guess an address.
- Send nothing without an owner go: a report is outward-facing.

**Status values:**
- `candidate`: seen in our logs or audits, but the source passage has not been read for this list;
- `verified`: the source passage was read and quoted here;
- `reported`: sent, with date and channel;
- `corrected`: the source changed, with the date it was seen.

## Verified

### E1. 20/11: the chair's handover to the next speaker is filed inside the previous speech

- **Status:** verified 2026-10-28.
- **Source:** `https://dserver.bundestag.de/btp/20/20011.xml`, Tagesordnungspunkt 2, `<rede id="ID201100900">` (Dr. Matthias Miersch, SPD).
- **What is wrong:** after Miersch's closing "Vielen Dank." and the applause, the same `<rede>` goes on with the chair's handover to the next speaker:
  - Präsidentin Bärbel Bas: "Nächster Redner: für die AfD-Fraktion Karsten Hilse." and a remark to Hilse ("Sie haben gerade ein paar kreative Umbaumaßnahmen vorgenommen …");
  - Karsten Hilse (AfD), with his own `<p klasse="redner">`: "Das freut mich sehr.";
  - Präsidentin Bas: "Jetzt erteile ich Ihnen das Wort für Ihre Rede. – Herzlichen Dank."
  - Hilse's speech follows as its own `<rede id="ID201101000">`.
- **What it should be:** the exchange belongs before Hilse's `<rede>`, or at its start. It is not part of Miersch's speech.
- **Effect on poliwatch:** the validator refuses the sitting, because Hilse's line would otherwise count as an interjected question in Miersch's speech. 20/11 is excluded since 2026-10-28 (`docs/plans/a3-phase3.md`, 4.4).

## Candidates

### C1. Whole speeches and replies filed inside the previous speaker's `<rede>` (WP 18/19)

- **Status:** candidate. The pattern is recorded in the audits but not yet quoted here per passage.
- **Pattern:** a speech the chair gives the floor to separately is printed as nested content of the preceding `<rede>`, not as a `<rede>` of its own:
  - whole Reden after "Nächster Redner ist …", 30 cases in the audit, 7 of them in 18/26;
  - Erwiderungen on a Kurzintervention: 18/11, 18/20, 18/42, 18/88, 18/127, 19/12, 19/14;
  - persönliche Erklärungen and Erklärungen nach § 30 / § 31 GO: 18/29, 18/97, 18/98, 18/117, 18/118;
  - Geschäftsordnung statements: 18/2, 18/3, 18/67, 18/89.
- **Evidence:** `docs/plans/a3-wp18-19-blockers.tsv` (groups `6c-floor-wording`, `erwiderung-nested`, `erklaerung-nested`, `go-debate`), `docs/plans/a3-wp18-19-audit.md`, TODOS.md "WP 18/19: nested Erwiderung, Erklärung and Geschäftsordnung turns".
- **Open question before reporting:** whether the Bundestag treats this as an error or as a markup convention of that period. The printed protocol reads correctly; only the XML structure is off. Pick two or three clear cases, quote them, and ask about the convention first.

### C2. Two person ids in one `<redner id>` (WP 21)

- **Status:** candidate.
- **Source:** `<redner id="11005217 999990074">` for Svenja Schulze (SPD) in 21/18 (ID211802600, ID211807500), 21/24 (ID212409300), 21/25 (ID212501900, ID212504800), 21/28 (ID212802500, ID212809700), 21/44 (ID214402100) and 21/45 (ID214502600, ID214505400).
- **What looks wrong:** the id attribute holds two ids. The schema expects one. We use the first.
- **To check before reporting:** what `999990074` is (an id outside the MdB number range), and whether the Stammdaten list both.

### C3. Roll-call votes with no document number on www.bundestag.de

- **Status:** candidate. This may be how the pages are, not an error.
- **Source:** roll-call pages for some votes on Bundeswehr mandates, among others: 19/29 vote 510 (MINUSMA) and 19/4 vote 489 (IS), and others in WP 18, 19 and 20 (backfill warnings "matched no TOP").
- **To check:** whether the vote page or the XLSX names the Drucksache elsewhere. If neither does, the missing link is worth reporting.
