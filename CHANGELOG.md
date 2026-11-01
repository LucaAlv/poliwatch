# Changelog

All notable changes to this project will be documented in this file.

## [0.26.0.0] - 2026-10-31

### Added

- A data release script, `scripts/publish_dip_pulse_data.sh` (logic in `publish_dip_pulse_data.py`). It turns an existing Daten export into an immutable, versioned release directory `data-<version>/`, which holds `datenstand.json`, the export files, `CHANGES.md`, `changes.json` and `SHA256SUMS`.
  - **Dry run by default:** it prints the site-build flags and the `gh release create` command it would run.
  - **`--publish`** creates the GitHub release. It refuses until `LICENSE-DATA.md` exists (ADR 0003) and the export carries a licence string.
  - **What gets refused:** an export not built with a release tag, a cited revision that is not a bare commit of this repository, authored inputs that differ from that commit, any file that does not match the manifest, and an existing tag or release directory.
  - Nothing has been published yet.
- Release versions are calendar versions, `YYYY.MM.DD` (`.2`, `.3` for further releases on the same day), tagged `data-<version>`. `--next-version` prints the next one. The site build takes it as `--data-tag`, which accepts only `local` or a release version.
- Every release carries a public data changelog: `CHANGES.md` plus `changes.json`, in the format described in `docs/data-changelog.md`.
  - **Derived from the two manifests:** export format, store schema, key version and schema hash, plus protocol, vote and row counts, old to new.
  - **Authored per release:** a summary, schema changes, added coverage, and every correction of a published value (table, key, column, old value, new value, reason).
  - **Refusal:** a release whose schema moved without an authored description is refused.
- `CITATION.cff` at the repository root. It claims no DOI or version yet.

### Changed

- The cited build revision is reproducible.
  - **Same edit, same revision:** the same edit gives the same `-dirty-<hash>` under the common git diff settings. A git timeout gives `-unverified-<hash>`, which still changes with every edit, instead of one fixed `-unverified`.
  - **Release requirements:** a release export needs a bare 12-digit commit, and its authored codebook inputs must be committed and unchanged.
  - **Where it's explained:** the Daten page and DATA.md explain the suffix.
  - **Effect on local exports:** a dirty tree's revision string changes form and hash once. No figure moves.
- The publication check (`--validate-publication`) also scans the export's `DATA.md` and `datenstand.json` for leaked local paths and placeholders.

### Fixed

- An export that fails after swapping in its new generation puts the previous generation back. Before, the old manifest could be left pointing at the new files.

## [0.25.2.0] - 2026-10-31

### Changed

- A vote panel can now quote an Antrag whose demand sentence puts a clause between „die Bundesregierung“ and „auf“: „im Rahmen der verfügbaren Haushaltsmittel auf“, „unter Einhaltung der haushälterischen Vorgaben auf“, „zur … auf“, „zum … auf“ and „dazu auf“. The opening quotes the whole sentence. On the saved 91-document corpus, ten more Drucksachen are quoted, each checked word for word against the PDF: quoted documents 64 → 74 of 91, reference cohort 50/71 → 60/71 (84.5 %). Derived but not measured on a site build: vote panels with a description 196/217 → 206/217. A store persisted with the previous extractor is refused until it is re-persisted with `--offline --repersist`.

### Fixed

- An Antrag is quoted only where its text proves the structure, so no quote on the saved corpus is wrong any more. Incorrect quotes went from 3 to 0:
  - 18/2742 joined „jesidisch-“ and „kurdischen“ into „jesidischkurdischen“ and is now not quoted.
  - 18/3154 lost its nine bullet markers and is now not quoted, instead of showing a flattened list.
  - 19/16794 carried the printer's imprint (Gesamtherstellung, Vertrieb, ISSN) between two demands and is now quoted without it.
- A lettered list that runs past z) into aa) to gg) keeps every item. 20/13415 folded aa) to ff) into demand z).
- An Antrag whose source text glues a dropped hyphen to „oder“ („Überoder Unterforderung“, 20/2345) is not quoted.
- The facts engine and the rebuild refuse a downloaded release SQLite given as `--database-path` and leave the file byte for byte as it was. Before, the facts engine could write into it and a rebuild replaced it with a fresh build store.

## [0.25.1.0] - 2026-10-31

### Changed

- In a vote panel's opening sentence, „namentliche Abstimmung“ links to the explainer on `bundestag.html#abstimmen`. All 246 vote leads on the reference site carry the link.

### Fixed

- A Fakt card shows its whole caveat, up to four lines, instead of cutting it after two. The caveats of „Die knappste Abstimmung der Woche“ and „Die meisten Abweichler der Woche“ lost their second half before. The caveat now ends just above the footer and grows upward, and the comparison text moves up to make room. The widest caveat line measures 869 of the 920 px available. The caveat texts are unchanged.
- A vote panel says „Niemand stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe“, and the Abstimmungen archive gives an Abweichler count, only when the Fraktionen and Gruppen add up to the vote's total. Where Stimmen are missing from the groups, the panel shows the gap note once, under the vote. On the reference site all 217 votes add up, so no panel or archive count changes (217 archive rows, 632 Abweichler).
- A context teaser no longer ends after an abbreviation that follows a bracket or quote, such as „(sog.“ or „(Abs.“; it cuts at the last real sentence end or at a word with „…“. 10 of 3,922 cached teasers change, all of which ended in „(sog.“.
- An abstract cut at 10,000 characters no longer ends in a fragment of a tag or entity („<a hr“, „&am“) as visible text; only the one tag the cut splits is dropped. No cached abstract reaches the cut (the longest has 5,111 characters), so none changes.
- An abstract reads the same on every Python patch release. html.parser's 2025 security releases (3.11.13, 3.12.11, 3.13.4) drop a tag that never closes („Ende <a hr“ became „Ende“) and read an unclosed comment to the end; older releases keep both as text. Each comment is now removed and each never-closing „<“ escaped before parsing, so both keep the text, and an abstract with a marked section („<![CDATA[“) always takes the plain-text fallback. 0 of 3,922 cached abstracts change on either release.

## [0.25.0.0] - 2026-10-31

### Added

- Every data export now carries `DATA.md`, a German codebook you can read without the website: what each table and column means, its unit, source and licence layer, the per-Wahlperiode coverage of exactly this SQLite file (sittings, date range, TOPs, Reden, Beiträge, Abstimmungen, Stimmen), the counting rules, the exact SQL of each published recipe, the layered licence terms and how to cite the export. Every definition was checked against the code that writes the column.
- The six SQL recipes on the Daten page now also ship as result CSVs (`recipe-<id>-<tag>.csv`), with every SQL column in projection order, including the link IDs the page hides, so each result can be reproduced against the export's SQLite file. The Daten page links `DATA.md` in the download panel and each recipe's CSV beside its table.

### Changed

- Export format 10: `datenstand.json` lists every file of a generation with its kind (`sqlite`, `table_csv`, `recipe_csv`, `codebook`), size, SHA-256 and, for CSVs, row count, and each recipe names its CSV. A manifest of another export format is refused; re-export with this version.
- r3 („Abweichler“) counts per person and Fraktion: someone who switched Fraktion gets one row per Fraktion instead of one row with the label of one of them. On the reference export the top five are unchanged (Bayram 30, Dieren 18, Kraft 13, Koeppen 11, Kubicki 9); 2 of 363 persons now have two rows, both below the cut.
- The cited build revision is a 12-character commit, with `-dirty-<hash>` when tracked files differ from it and `-unverified` when git cannot tell. A release export needs a clean revision. An export re-runs when the codebook inputs, the revision or the exporter change, and a cached generation whose `DATA.md` or recipe CSVs were altered is written again.

### Fixed

- The licence notice (`docs/data-license.md`) lists every column it gives CC BY 4.0, including `speeches.sprechrolle`, `speeches.unattributed_char_count` and `speech_rule_inputs`, which it previously left under DIP terms.

## [0.24.1.0] - 2026-10-30

### Added

- „So arbeitet der Bundestag“ (`bundestag.html`), the ninth nav entry: who brings in Vorlagen, when the Bundestag sits, how it votes (Handzeichen, Hammelsprung, namentliche Abstimmung), the freies Mandat and the way from Gesetzentwurf to Gesetz. Every section names its legal basis with a link to the Grundgesetz on gesetze-im-internet.de or the Geschäftsordnung on bundestag.de, checked against the official texts. Both glossaries on the sources page and the week radar's „namentlich abgestimmt“ badge link to it; a visited badge keeps its colour.

### Fixed

- The Abgeordnete list no longer includes members of the Bundesrat. The roster took every DIP person whose function contained „MdB“, which matched „MdBR“ and „Stellv. MdBR“: on WP 21 (DIP, 2026-10-30) the list showed 740 people, 151 of them Bundesrat members; it now shows the 589 with the function MdB. A store built before this drops them on its next rebuild: an `--offline --repersist` or an online build re-derives the MdB flag from each carried-forward roster row's stored function, with no roster refetch (A3 store, 2026-10-31: 1,712 → 1,360 roster MdBs, the 352 Bundesrat rows dropped). Only a build that does not rewrite the store (`--offline` without `--repersist`, or `--no-persist`) still shows them. 48 MdBs whose current office is a government one are still missing (DIP lists them without the MdB function), a known gap with its own TODO; adding them now would split 29 of them into two Personen.
- A Personenseite of someone who is not in the Abgeordnete list says „Redner“ with the Sprechrolle they spoke in, from Reden and Beiträge (Bundesregierung, Bundesrat, weitere Sprechrolle), and „Mitglied des Bundestages laut Plenarprotokoll“ with the Fraktion when a Rede or Beitrag counts for a Fraktion or they cast a namentliche Abstimmung, instead of an empty Fraktion and Wahlkreis. A page kept without any Rede or Beitrag says „Keine Reden erfasst“. The Abgeordnete index lists the Redner under „Weitere Rednerinnen und Redner“, which the search filters but the Fraktion filter does not, so their pages are reachable.
- „Der meistdiskutierte Vorgang des Monats“ (metric version 3) counts a Tagesordnungspunkt only when it debates exactly one Vorgang; the Reden of a verbundene Beratung of several Vorgänge count for none, where version 2 credited them all to the Vorgang DIP listed first. An Entschließungsantrag debated with its Gesetzentwurf does not make a second Vorgang. On WP 21 sittings 21/87–21/103, 3 of 4 monthly winners change: June from „Infrastruktur-Zukunftsgesetz“ (16 Reden) to „Empfehlungen der Rentenkommission …“ (13), July from „… Straßenverkehrsgesetzes (Tempolimit)“ (17) to „Deutschland braucht echte Reformen …“ (14), September from „Haushaltsgesetz 2027“ (16) to „Das Solidarprinzip stärken“ (13); October stays „Nachhaltigkeit und Zukunftsfragen“ (26). Each old winner was debated together with other Anträge. When the one Vorgang is a co-advised (mitberatener) one, it is named by its own title. The card and the Methodik state the rule in full.
- A roll-call profile link with a `.` or `..` path segment, also percent-encoded, is no longer taken as a person's profile (it could resolve to the Abstimmung page itself). No stored link had one.
- The zero-network demo shows 14 Reden for TOP 32 of 21/84, as today's parser counts them, instead of 16; the Kurzintervention and its Erwiderung appear as Beiträge, with a Zwischenfrage.

## [0.24.0.0] - 2026-10-29

### Added

- Vote panels can quote an Antrag's demands when DIP has no abstract, with sponsor attribution, a link to the original Drucksache and a fold for longer passages. Existing DIP descriptions take precedence.

### Changed

- Antrag texts are cached for offline extraction and included in schema 8 / export format 9 through document passages and vote associations. Rebuild older stores with `--offline --repersist`.
- Local validation increases reference votes with descriptions from 153 to 196 of 217. Extraction remains below its acceptance threshold, and three historical WP 18/19 quotation fidelity defects remain documented.

### Fixed

- Quotes retain an elision hyphen stranded at a line break, such as `Steuerzahler und -zahlerinnen` in Drucksache 21/224. Extractor version 7 requires re-persisting existing passage data.
- A context that already has a quotation still reports when another candidate's text or metadata has not been fetched.

## [0.23.6.0] - 2026-10-29

### Fixed

- puls.html's Redeanteil card is headed „Redeanteil der Fraktionen und Gruppen“ and lists every row. It stopped at eight before, so in a WP 21 week (up to ten rows) the Bundesrat or fraktionslos row could drop and the bars summed to less than 100 %. Bundesregierung, Bundesrat, weitere Sprechrolle, fraktionslos and Unbekannt now follow the Fraktionen and Gruppen below a rule; in the Wochenvergleich a row that spoke only in the compared week shows at 0 % with its loss, so the shifts net to zero; and a cut-short week's note reads „Zuordnung für N von M Reden erfasst“.
- A dossier cached before the parser checked link hosts no longer shows a number read off a quoted news URL as a Drucksache (88/739016 from a syriahr.com link in 20/206), and the vote panel no longer takes such a link. Every reader of the XML Drucksache references applies the rule persist already used, so no stored figure moves.
- On bundestag.de vote pages a fractional majority such as „2/3-Mehrheit“ is no longer read as a Drucksache number: it neither refuses an official outcome as naming another document nor joins a vote's documents from the roll-call list. No stored vote changes until it is fetched again, since the official outcome is read at fetch time.
- A `--data-manifest` override must carry exactly this build's recipes (same ids in order, identical SQL); the Daten page takes each recipe's title and SQL from the build, so a tampered manifest cannot show other text as SQL next to the copy button. An override exported by code with different recipe SQL is refused with the recipe named; re-export it. A recipe without `empty_reason`, or with a row that is not an object, is refused instead of crashing the build.
- A build stopped by a stale cached report prints the command that re-fetches that very sitting (`--document-number 21/82`), and a refused vote shape names its TOP or `sitting_votes`. A refusal of reports from an older counting rule says to run `--fetch-xml`, then `--offline --repersist`, and names for a re-fetch only the reports without an `xml_url`; `ERROR [persist]` now prints that fix too. README no longer says a plain online update re-fetches a deleted report.

## [0.23.5.0] - 2026-10-29

### Fixed

- A bill's „Zuletzt erfasst“ step on a day with several events is now the procedurally latest one: the sitting's Beratung over a Drucksache filed that day (a same-day „Gesetzentwurf“ no longer beats „1. Beratung“), the Beratung over a same-day Entschließungsantrag or roll-call vote, and the Gesetzesbeschluss over the 2. Beratung. On the reference cache 8 of 562 bills change: 5 from „Beschluss“ to „Abstimmung über Vermittlungsvorschlag“, 1 from „Geschäftsordnungsantrag zur Beratung“ to „2. Beratung“, 1 from „2. Beratung“ to „3. Beratung“ and 1 from „Unterrichtung“ to „2. Beratung“. The 47 bills whose latest step is „Gesetzesbeschluss“ keep it.

## [0.23.4.0] - 2026-10-29

### Changed

- The Methodik page and the Plenarprotokoll overview call a Sitzung's page a „Dossier“ („Jedes Dossier verlinkt den Zwischenbericht als JSON“, „Erzeugte Dossiers“) instead of „Sitzungsseite“ and „Sitzungsdossiers“.

## [0.23.3.0] - 2026-10-29

### Fixed

- The demo build's grouped Antrag TOP on puls.html lists each Antrag's own title instead of one bold block of the joint „a) … b) …“ agenda heading. The demo fixture had copied that heading into both titles; real builds were not affected.
- `scripts/extract_demo_fixture.py` runs again: it passed bytes to the protocol parser, which now takes text.

## [0.23.2.0] - 2026-10-29

### Changed

- puls.html flags a week older than four ISO weeks with „Nicht aktuell: letzte Woche mit Sitzung vor N Wochen“ right after the heading, instead of only in the muted facts line; shorter gaps still lead the facts line with the age.
- The site calls its reporting period „Woche mit Sitzung“ (or „Woche“), not „Sitzungswoche“, which names the Bundestag's planned calendar. This covers the Wochenvergleich, the Fakt der Woche cards and footer („Vergleich: N Wochen mit Sitzung“), and the Fakten Methodik.

## [0.23.1.0] - 2026-10-28

### Fixed

- Bill search now ignores accents and treats ß as ss, so “fur” finds “für” and “strasse” finds “Straße”. Titles and query spelling remain unchanged, including when restoring searches through browser history.

## [0.23.0.0] - 2026-10-26

### Added

- Each roll-call vote panel now introduces the recorded subject, date, outcome and raw vote counts, followed by its committee citation where available. Calculated and unavailable outcomes remain clearly labelled.
- Vote panels link to the associated Bundestag report where one can be identified. The optional source link is also included in SQLite and CSV downloads; existing cached reports need an online vote refresh to acquire it.

## [0.22.1.0] - 2026-10-26

### Fixed

- Weeks without an eligible comparison week retain their current totals and fraction shares without repeated `n/a` markers or an empty delta column. Comparisons with no shared sitting weekdays retain their per-row unavailable deltas.

## [0.22.0.0] - 2026-10-24

### Fixed

- Vote panels now explain when a Ja supports a recommendation to reject an Antrag, using the chair's announcement and its Drucksachen. All 14 previously missed reference votes show the inversion legend; direct votes on a Vorlage remain uninverted.
- Existing caches recover vote interpretation with `--offline --repersist`, keeping every copy of a vote consistent across dossiers, the archive and data exports. Vote 1005 now shows `Antrag: Abgelehnt (berechnet)` instead of a missing result, and sitting-level votes survive online acquisition.
- Official outcomes remain attributable when the read-out tally differs from the final tally by up to three votes per side, only within a uniquely identified document block. The reference-page comparison recovers 43 additional official outcomes without changing an existing one; vote 996 shows the official Antrag rejection at 439/135 without double inversion. Ambiguous matches stay unresolved.

## [0.21.1.0] - 2026-10-23

### Added

- Regression coverage for offline audit comparisons ensures an independently loaded historical parser uses its own classifier and leaves current counts unchanged across multiple XML files.

## [0.21.0.0] - 2026-10-23

### Added

- Each roll-call vote on a dossier says what it was about: a "Worum es geht" block with DIP's description of the Vorgang the vote decides, linked to DIP by its title, with a short teaser and the full text behind "Ganze Beschreibung". A vote's Vorgang comes from its own Drucksachen, narrowed to its TOP's Vorgänge. On the reference cache 217 of 217 votes have their Vorgang, and 153 have a DIP description; the others say "Keine Beschreibung in DIP", "Kein einzelner DIP-Vorgang ermittelt" or "Vorgang nicht abgerufen".
- Each vote cites the committee recommendation it was taken on: "Beschlussempfehlung des Haushaltsausschusses (Drucksache …)", found among the vote's Drucksachen across the whole sitting, or "Ausschuss nicht ermittelt". 190 of 217 reference votes cite one.
- Under each Fraktion or Gruppe of a vote, the panel names who voted against its majority (Ja against a Nein-Mehrheit or Nein against a Ja-Mehrheit), the first ten inline and the rest behind "alle N anzeigen", linked to their Personenseite. "Niemand stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe" is said only when every group's Einzelstimmen are complete; a group whose Einzelstimmen do not add up to its tally says so instead of naming no one. The reference votes have 632 such Stimmen.
- The votes archive shows how many voted against their group's majority on each vote (only when that count is complete), and each archive entry links straight to its vote panel (`…#vote-<id>`, 217 of 217 resolve).
- The Daten export has a `vote_proceedings` table (the Vorgänge a vote is about, with rank), `proceedings.abstract` (DIP's description as plain text) and `votes.context_state` (resolved, none or not_fetched), labelled as derived or source data, and a sixth recipe, `r6-ausschuss`, counting votes by the committee whose Beschlussempfehlung they cite.

### Changed

- Store schema 6 and Daten export format 7 with 28 CSVs. A store built by an earlier version is refused with the instruction to run `--offline --repersist`.
- A vote's procedure type is read from the Drucksachen of the whole sitting, not only its own TOP, so the archive rows showing "–" fall from 5 to 0.
- An online build also asks DIP again for vote Vorgänge whose description is empty (86 on the reference cache; none had gained one).
- Persist and the standalone renderer refuse a stale vote shape (a TOP's singular `"vote"`, non-list votes, a vote without an id) instead of treating the sitting as voteless; a stale report outside the build's catalog no longer stops the build, and a null or empty `"vote"` passes.

### Fixed

- An Einzelstimmen card that links back to the Abstimmung (bundestag.de does this for an MP without a biography; 77 rows in 14 votes) is no profile URL any more: it no longer serves as an identity that folded every such MP of a vote into one, is not stored as the MP's profile (14 → 0 mps), and the name is no longer linked to the vote page. The registry kept the 63 occurrences it had already folded on their records, so the reference store was rebuilt without its earlier registry: `vote_members` 154,015 → 154,078, persons 4,265 → 4,298 (47 records, one per affected MP, replace the 14 folded ones; 41 stale `xml:` records from an older identity rule fold into their MPs' current records with no speech or contribution changing person; 10 bindings to speeches and contributions that no longer exist are gone). Abweichler are unchanged (632).
- Einzelstimmen whose biography link fails the profile check (a backslash, user info, a port or whitespace in the URL, or anything other than an https bundestag.de biography or abgeordnetenwatch profile) are no longer linked or used as an identity. No reference link is affected.
- In dark mode, the "Einzelstimmen (N Abgeordnete)" control under each vote is readable (it was dark blue on the dark panel, about 2.2:1; now 8.2:1).

## [0.20.8.0] - 2026-10-23

### Fixed

- The Debattenprofil now counts each agenda item once per procedure type in both compared calendar weeks, so bundled petitions no longer inflate the profile. The card and glossary explain the counting rule.
- Returning procedures now appear under “Wieder auf der Tagesordnung”, with notes consistently calling them Vorgänge.

## [0.20.7.0] - 2026-10-23

### Fixed

- Fact citations now say “Belege”, and the data export description includes agenda items among the evidence types.
- Monthly facts without an observation now say “diesen Monat nicht messbar”.
- Fact pages and Methodik now explain that rebuilding can change earlier cards after data, rule or wording changes, and that cards disappear when their evidence no longer resolves.

## [0.20.6.2] - 2026-10-22

### Changed

- The refresh guide now explains how `--protocol-wahlperiode` works with acquisition limits, with examples for the current period, older periods and all periods.

## [0.20.6.1] - 2026-10-22

### Fixed

- Assistive technology can now identify the bill overview's search and filter controls as a search landmark named “Gesetzesvorhaben finden”. Empty publications continue to omit the controls.

## [0.20.6.0] - 2026-10-22

### Fixed

- Protocol citations now consistently use `BT-PlPr.` with their document number. Bill timelines and fact sources identify Bundestag and Bundesrat documents by chamber and type while preserving their source links.

## [0.20.5.1] - 2026-10-22

### Fixed

- Data exports now correctly identify abgeordnetenwatch as the source of MP birth year, gender, profession, constituency and state. Export format 6 refreshes cached provenance labels without changing row IDs or the store schema.

## [0.20.5.0] - 2026-10-22

### Changed

- Bill pages now label linked plenary records as ‘Beratungen im Plenum’, including records without speeches; counts are unchanged and the section anchor is now #plenarstellen.

## [0.20.4.0] - 2026-10-21

### Changed

- The dossier sidebar now says "Meiste Reden". Its methodology explains that topics are ranked by speech count and the bars show speech and text shares within the sitting. Existing links to the ranking still work.

## [0.20.3.0] - 2026-10-21

### Fixed

- A failed SQL recipe copy preserves text selected elsewhere, including identical text in another recipe, instead of replacing the reader's selection.

## [0.20.2.0] - 2026-10-20

### Fixed

- Resetting the Gesetzesvorhaben filters returns keyboard focus to the search field, clears the query, year and page, and keeps the selected sort order.
- Following the same speech link again reopens a closed speech card, including when activated with Enter. Modified clicks, downloads and links targeting another browsing context keep their native behavior.

## [0.20.1.0] - 2026-10-20

### Fixed

- DIP refreshes retain valid Vorgänge when another record is malformed, leave incomplete lookups retryable, and distinguish validation errors from outages. ID lookups cannot overwrite unrelated cached Vorgänge.
- Offline replay refuses any previously fetched TOP or vote becoming `not_fetched`, even when another identity recovers. Unreadable, locked, corrupt or incomplete stores stop replay without replacing the database.
- Builds preserve unsupported or unreadable Vorgang caches and explain how to recover. Corruption backups have unique names, and atomic cache writes retry beside the cache when private staging fails, including during the final rename.
- Politikfeld and Fraktion filter buttons on the week radar and votes archive have 44px touch targets; desktop sizing stays unchanged.

## [0.20.0.0] - 2026-10-19

### Added

- Every Tagesordnungspunkt and every roll-call vote has one to three Politikfelder from a closed list of 13 (Migration, Soziales, Wirtschaft & Finanzen, Energie & Klima, Verteidigung, Innere Sicherheit, Justiz, Digitales, Gesundheit, Bildung, Verkehr, Außenpolitik, Staat & Demokratie), or is explicitly untagged. They are derived without a model from DIP's Sachgebiet labels: of the Vorgänge a TOP belongs to, otherwise of the Drucksachen it names, otherwise of the Einzelplan in its heading. A vote takes the fields of its own Drucksachen, otherwise those of its TOP. On the reference cache 2,109 TOPs are tagged through their Vorgänge, 196 through their Drucksachen and 149 through their Einzelplan, 458 stay untagged (mostly Fragestunden, Befragungen, Wahlen and Geschäftsordnung), and 216 of 217 votes are tagged.
- Dossiers show the Politikfelder of each TOP. The week radar shows them on each row and can be filtered by Politikfeld. The votes archive shows them on each vote and can be filtered by Politikfeld, including "Ohne Politikfeld", together with the Fraktion filter; `votes/index.html?politikfeld=Migration` (repeatable) opens it filtered.
- The Daten export has two new tables, `agenda_item_politikfelder` and `vote_politikfelder` (field, rank and source of each tag), labelled as derived data, and `proceedings.sachgebiet` carries DIP's raw labels.
- Every build prints how the Politikfelder came out, by source, and names any Sachgebiet label DIP uses that the mapping does not know.

### Changed

- Store schema 5 and Daten export format 5 with 27 CSVs. A store built by an earlier version is refused with the instruction to run `--offline --repersist`.
- An online build fetches the DIP Vorgänge and Drucksache numbers the tags need into `data/dip-vorgang-cache.json`, paced at about 1.5 requests a second so DIP's edge does not block the API. The first fill of the reference archive (about 2,400 numbers) takes about 45 minutes; later builds fetch only what is new. Offline builds use the cache as it is; a TOP or vote whose input is missing from it is stored as `not_fetched` and shown without a tag.
- `--offline --repersist` refuses to run when the Vorgang cache would leave more TOPs or votes without their tags than the current store has (a missing, emptied or partly restored cache), and names the fix: run an online update first.
- A DIP answer that is not JSON (a bot-challenge page, a cut-off body) is retried like a dropped connection, and a list answer of the wrong shape fails with a clear error instead of a traceback.

## [0.19.1.0] - 2026-10-19

### Fixed

- CDU/CSU is visible in dark mode. Its party colour was near-black on dark surfaces, so its Fraktion bars, stacks and dots all but disappeared; it is now light grey in dark mode and unchanged in light mode.
- In dark mode, navigation links highlight on hover again, and the current page keeps its highlight while hovered.
- No text on the Wochenübersicht is smaller than 12px: badges, the "Wer sprach" legend and the Wochenpuls labels moved up from 11px, and the "Wer sprach" column is wider so the legend wraps less.
- Headings on the Wochenübersicht break into balanced lines instead of leaving one word alone, and the sitting chips keep a space between date and protocol number.
- On touch screens the Wochenübersicht's buttons, sitting chips, section links, "Sitzungsbelege prüfen" and the "Debatte im Protokoll öffnen" links are at least 44px tall.

## [0.19.0.0] - 2026-10-18

### Changed

- A Drucksache is identified by its issuer (Bundestag or Bundesrat) and its number, not by its URL. A DIP URL rewrite no longer creates a new document, and Bundesrat numbers no longer collide with Bundestag numbers. On the reference cache the store holds 7,952 documents instead of 7,956 (5,749 Bundestag, 2,203 Bundesrat): four numbers had a second, wrong or malformed URL (20/11710, 20/13328, 21/1060, 21/1061), and each now keeps the URL that encodes its number. Junction links, grouping, person keys, roster bindings and facts are unchanged.
- Store schema 4 and Daten export format 4. A store built by an earlier version is refused with the instruction to run `--offline --repersist`; every document id is minted once more, so document receipts in the facts change id once.
- The Daten recipes r1 and r3 name each person from the same row the Personenseite uses (roster row, then speaker row): 496 r1 names, 16 r1 parties and 25 r3 labels change on the reference cache, and one Personenseite heading changes.
- A repeat offline rebuild of the reference cache takes about 245 s instead of about 300 s.
- Nothing is written inside the published output while a build runs: the staged store, the writer lock, the facts write and the Daten export's scratch files live in a private directory beside the output directory (`.OUTPUT.private/`). A failed export leaves the published files as they were.

### Fixed

- Removing an applied partition (for example Föhr/Mende) from the corrections file is refused instead of silently giving one speaker the other's profile.
- An incremental build groups persons the same way a fresh build does after a roll-call profile link is corrected; a record with two contradicting abgeordnetenwatch ids gets no profile instead of whichever sorts first; reviewed merges no longer depend on file order.
- DIP persons without an id are skipped with a warning instead of all sharing one “Unbekannt” person. DIP person ids written as 7, "7" or " 07 " are one person.
- An agenda index given as text ("3") is the same item as 3 everywhere: in the store, in page anchors and links, in bill pages, in summary reuse and when re-reading cached XML. A malformed, missing or repeated index in a cached report is refused with a message.
- `--offline` over a store that cannot be opened, or a data pipeline that fails in SQLite or in the staged write, ends with one `error:` line and exit 1 instead of a traceback; the store is left as it was.
- Person pages are never written through a symbolic link, and a page directory that resolves outside the output directory is refused.
- On the same sitting day, the first-speech fact orders protocols by number (21/9 before 21/10), and vote receipts list Drucksachen in number order.

## [0.18.0.0] - 2026-10-14

### Added

- Find a Gesetzesvorhaben by title or Drucksache number, narrow the list to the year of its latest recorded activity, and sort it by newest, oldest or title. The list shows 20 entries per page, keeps search, year, sort and page in the URL so Back and shared links restore the view, and announces result counts to screen readers. Without JavaScript, or if the script fails, every entry stays readable; printing always includes the whole list.
- Open each recorded speech of a speaker straight from a bill page: one speech gets a direct “Rede lesen” link, several get a dated list with sitting and page. The link opens that speech in the sitting dossier and scrolls to it.
- Parliamentary terms on bill pages (Drucksache, Plenarprotokoll, Tagesordnungspunkt, Beratungen, Beschlussempfehlung und Bericht, Stellungnahme and others) explain themselves on hover or keyboard focus and link to a new “Parlamentarische Begriffe” section on the sources page, each with its official Bundestag source.

### Changed

- The bill overview is a plain, readable list: one title link per bill, its latest recorded step and date, and counts of documents, debates and roll-call votes. The browser-only “Folgen” marker, its counter and the summary boxes are gone.
- Bill pages read in a fixed order — Verlauf grouped by date, Debatten, Rednerinnen und Redner, Abstimmungen, Dokumente, Quellen und Daten — with section links at the top. All speakers are listed (twelve shown, the rest behind “Weitere Rednerinnen und Redner”) instead of only the first twelve. Bundesrat papers are labelled “Bundesrat-Drucksache” rather than as Bundestag Drucksachen (2,047 of 4,627 bill documents on the reference cache).
- Sitting dossiers no longer overflow phone screens: long compound words in headings, metrics and speech text wrap and hyphenate.

### Fixed

- Speech counts on bill pages count each speech once. A bill whose agenda item appeared under several DIP positions counted that item's speeches once per position. On the reference cache the total falls from 11,726 to 9,274 speeches and from 49,528,541 to 37,448,236 characters across 53 of 562 bills; the Haushaltsgesetze move most (2024: 984 → 307, 2025: 974 → 309, 2026: 886 → 280). No speaker row is added or lost.
- The latest step of a bill is the parliamentary step, not the sitting's Plenarprotokoll recorded on the same day: 156 of 562 bills previously showed “Plenarprotokoll” and now show their Beratung (95 “1. Beratung”, 49 “2. Beratung”, 12 others). No latest date changed.
- Bills that share a date keep the same order before and after the page's script runs, and in print.
- Debate rows label Zusatzpunkte and Einzelpläne as such instead of “Tagesordnungspunkt Zusatzpunkt …”.
- Search finds titles regardless of how an umlaut is encoded.
- Each bill's raw source data lists a repeated agenda item once (1,075 → 895 items on the reference cache).

## [0.17.1.0] - 2026-10-09

### Fixed

- A speaker who is printed under several names or parties in the protocols (a Fraktion switcher, a name with and without a title) now gets the same person page, name, party and biography whichever sitting is processed last. Before, the last sitting decided, so a rebuild in another order could group the same speaker differently. On the reference cache this joins 21 pairs of speaker and roster records that the old order had left split, among them former Linke members now in the BSW Gruppe, Wagenknecht, Hunko, Helferich, Spaniel and Seitz; 23 roll-call records of party-switching members stay unattached to their person instead of being attached by chance (3,095 persons become 3,094). No published count of Reden per Fraktion or per Sprechrolle, no page and no fact moved.
- A person whose record is listed in the Abgeordnetenkader keeps the title, Wahlperioden and function from that list. A value cached in an older dossier no longer wins just because it sorts first.
- A roll-call record printed under two parties attaches to a roster or speaker person only when exactly one of them matches, and two roll-call records that voted in the same roll call, or whose profile links disagree, never attach to the same person through different parties. The result no longer depends on the hash seed of the Python process.
- A speaker's two Redner-IDs that share one abgeordnetenwatch profile now both link the person page; before, only the one persisted last did.
- The name shown for a person prefers the plain printed form over a “Nachname, Vorname” roll-call form or a DIP title with its “, MdB, Partei” tail.

## [0.17.0.0] - 2026-10-07

### Changed

- Open the latest generated sitting directly from the homepage, alongside a separate weekly overview with dates and coverage labels. A pinned historical week keeps its own period while the latest sitting stays current.
- Find the public areas through concise homepage sections, replacing the introductory cards, archive counters and principles.
- The weekly view is now named “Wochenübersicht”. Below 1024 px, secondary navigation sits under “Weitere Bereiche”; keyboard focus stays visible when the layout changes.

## [0.16.0.0] - 2026-10-06

### Added

- Compare speech classifications across cached XML and historical counting rules with a read-only audit, including source hashes, unresolved turns and count changes.

### Fixed

- Offline replay recognises source-backed question permissions, renewed consent and corrected recipients while preserving refusals and keeping named and faction permissions separate.
- Procedural exchanges no longer inflate speech counts. Split replies and explicitly resumed speeches retain their native speaker, text and identity, with excluded or merged turns preserved as diagnostics.

## [0.15.1.0] - 2026-10-05

### Fixed

- Offline replay retains nested Zwischenfragen when the main speaker or chair interrupts, or when an explicit grant or acknowledgement supplies the evidence. Multi-speaker grants apply only to the named askers; refusals and unrelated later speakers do not inherit consent.
- Cached reports and stores made under earlier counting rules require a fresh `--offline --repersist` rebuild before their counts are used. Stale-rule diagnostics describe older classifications accurately and request `--fetch-xml` only when XML is missing.

## [0.15.0.0] - 2026-10-05

### Added

- Read nested Zwischenfragen and explicitly written submissions as separate Beiträge, with their own text, speaker and source links. Written submissions without a proven Tagesordnungspunkt appear with the sitting; they do not count as delivered Reden.
- Rebuild cached reports with `--offline --repersist` under the current counting rules. Facts, exports and store-backed pages refuse older rule provenance and name the rebuild needed to refresh it.

### Fixed

- Historical Befragung and Fragestunde sources now use the role printed on each occurrence, recognised headings and explicit question/answer evidence. Unresolved or contradictory source evidence rejects the affected sitting instead of silently counting it as a Rede.
- Kurzintervention classification distinguishes grants from refusals and closing announcements, while read-out questions receive an asker only when the sitting's source evidence identifies one uniquely.
- Cached replay proves each TOP association before carrying votes or enrichment forward, checks paired XML hashes, and leaves accepted outputs intact when source matching fails.
- Vote receipts take their sitting id, document number and date from one authoritative source row, including when duplicate or stale links exist.

## [0.14.0.0] - 2026-10-04

### Added

- Names in dossier roll-call member lists now link to their Personenseite, where you can follow the person's votes and speeches. Members without an internal match keep their Bundestag profile link, or their plain name when no profile is available.

### Fixed

- Vote records printed surname-first now join their roster or speaker identity when the match is unambiguous. Conflicting ids, ambiguous namesakes and distinct people in the same roll call remain separate; vote-member occurrence ids stay unchanged. On the 285 cached sittings, 147,971 of 154,015 stored member rows now resolve internally, producing 166,656 working member links.
- Personenseiten prefer roster and speaker biography over vote-list attributes, and correctly label a Bundestag profile fallback.

## [0.13.0.0] - 2026-10-03

### Added

- Kurzinterventionen, Erwiderungen, and the Fragen and Antworten of the Befragung der Bundesregierung and the Fragestunde are now stored as their own Beiträge, typed by kind, in a new `contributions` table and CSV (24 CSV files now; export format 3). Each Beitrag has a stable text id and its speaker is bound in the person registry like a Rede's. Each dossier shows them beside its Reden, a Person's page shows them apart from their Reden, and the week radar reads “2 Reden, 59 Fragen, 55 Antworten” for a Befragung. The Fragestunde, which has no `<rede>` elements and stored nothing for 75 of 76 sittings, is read from its flat turns.
- Change what counts as a Rede without fetching anything again. Every online update now keeps the sitting's Plenarprotokoll XML in `data/xml/`, and `--offline --repersist` re-reads Reden and Beiträge from it. `--fetch-xml` downloads the XML for sittings cached before this release (public bundestag.de files, about 0.3 s each).
- A build that writes the store re-reads a cached report from before this counting rule from its cached XML, and refuses to persist one it cannot re-read, naming it and the fix, so old and new Reden counts never mix in the store. A build that persists nothing warns instead.

### Changed

- Only Reden count as Reden. On the 285 cached sittings the Reden count falls from 34,775 to 25,800 (DIP's own count is 26,396) and the characters of all Reden by 6.1 %. The Bundesregierung's Redeanteil falls from 14.6 % to 4.6 %; CDU/CSU 22.2 to 24.8, SPD 17.7 to 21.2, AfD 14.6 to 15.2, Grüne 13.5 to 14.5, FDP 7.4 to 8.5, Linke 6.9 to 7.4. The opening reports of a Befragung stay Reden. The five Fakt der Woche metrics that count Reden are at version 2.
- Kurzinterventionen are detected from the Sitzungsleitung's wording, and the parser compares them and the Erwiderungen per sitting with DIP (638 of 682 and 583 of 646 overall, 57 of 285 sittings differ). Detection prefers precision, so some Kurzinterventionen still count as Reden.
- A cached report with a Befragung or Fragestunde heading is never ranked as a week topic, also when the report was made before this release.

### Fixed

- A Befragung or Fragestunde whose heading the Bundestag XML sets in a different paragraph class (20/143, 20/159) is recognised: 212 Fragen and Antworten no longer count as Reden and 67 Fragestunde turns are stored.
- A Kurzintervention the Sitzungsleitung asks for with “Sie möchten eine Kurzintervention machen? – Bitte schön.” (20/112) is now recognised, and a remark that closes one (“Damit ist die Kurzintervention beendet”) no longer turns the next Redner's Rede into one.
- A Fragestunde question the Sitzungsleitung reads out is credited to the MdB only when the announcement contains their whole surname, not a longer name that contains it. Fragestunde turns whose speaker marker names no MdB and no official are counted in `fragestunde_unplaced_turns` of the validation summary instead of vanishing. (No cached sitting has one, and the surname rule moves no real row.)
- An online update caches the sitting's XML only when it keeps the report. A failed vote scan that keeps the cached dossier no longer leaves revised XML beside the old report, and `--offline --repersist` drops an AI summary whose cited Reden the re-read changed.
- A sitting week with only Fragestunde turns lists them in the “Außerdem” line of the week radar instead of only saying that no Reden were extracted.
- The export format is now `2` (`export_format` and the distribution copy's `user_version`): it added `contributions.csv.gz`.
- `--offline --repersist` now also refreshes each agenda item's heading, Drucksachen and page range from the cached XML, so a repersisted store shows the same headings as an online build. Before, the 16 items whose heading sits in a `T_ZP_NaS` paragraph (Befragung, Fragestunde, an Eidesleistung and 12 Zusatzpunkte) kept an empty heading. On the cached sittings the only matching change is that the Eidesleistung of 20/159 now picks up its Wahl position.
- A Rede after a Kurzintervention is an Erwiderung only when the same Redner gives it. Fifteen real Reden, including a maiden speech that the “erste Reden” Fakt needs, had been filed as Erwiderungen.
- `--offline --repersist` refuses cached XML that is not the protocol of its sitting (a maintenance page, another sitting, no agenda items), names the file, and leaves the store untouched. It no longer marks such a report as current. The profiles resolved online survive the re-parse.

## [0.12.0.0] - 2026-10-02

### Added

- Every published row has a stable, source-derived id, and every person a durable key that survives rebuilds: a link to a speech, a vote or a person page still points to the same thing after the next build.
- Person pages at `abgeordnete/<person_id>.html`, with redirect pages for keys a merge retired, and dossier, bill and fact links that follow the speech occurrence to the right person.
- Reviewed corrections in `scripts/person_corrections.json`: partitions for a Redner-ID that two people share, and merges with an optional survivor. Alexander Föhr and Dirk-Ulrich Mende, who share Redner-ID `11005304`, now have separate pages (13 speeches / 51,884 characters and 9 / 42,000, previously one person with 22 / 93,884). Protocol pages and bill tallies show the reviewed speaker; the cached dossier JSON keeps the printed one as source evidence.

### Changed

- Build-store schema 3 and export format 2 use text entity keys; facts and recipes read the persisted person of each record. Receipt identity no longer depends on presentation position.
- Old stores are upgraded only by an explicit `--offline --repersist`. A rebuild carries the person registry forward, requires the cached evidence of every stored protocol, holds one writer lock, recomputes facts once and validates integrity and foreign keys before the database is swapped in atomically. A full 285-report rebuild takes about 150 s instead of about 300 s.
- Name-based person matches are recomputed on every build, so an incremental and a fresh build group records identically (checked on the 285-report reference cache: grouping unchanged, 3,386 persons).
- `--offline --no-persist` renders without reading the store, and a store that is not a database ends with an error line instead of a traceback.

### Removed

- `persist_dip_pulse_store.py` no longer writes a single report into an existing store; it names `--offline --repersist`, the one write path that reconciles persons correctly.
- Occurrence assignments and splits in `person_corrections.json` are refused until they are redesigned; no shipped correction used them.

## [0.10.0.0] - 2026-09-30

### Added

- See every fetched roll-call vote in its sitting, even when no agenda item can be assigned. Unambiguous title matches link votes to their topic; unmatched votes appear under “TOP nicht zugeordnet” and remain in the archive, member histories, facts, and data export.
- Read the Antrag outcome and faction positions when a vote concerns a recommendation to reject it, with an explicit “Ja = Antrag ablehnen · Nein = Antrag annehmen” explanation and retained source evidence.

### Changed

- Special-majority procedures remain unknown without an attributable official result. Ordinary votes retain the Ja/Nein rule, and raw vote counts remain unchanged.
- Vote acquisition completeness now measures scans and successful detail fetches independently of topic assignment. Existing stores migrate sitting links and interpretation fields without losing votes.

### Fixed

- Conflicting or negated recommendation evidence no longer reverses the displayed outcome. Results derived from counts use the voted proposition’s scope when official text cannot establish an outcome.
- Fresh profile resolution updates vote members instead of silently keeping stale cached links.

## [0.9.0.0] - 2026-09-29

### Added

- Apply stored-value corrections to every cached sitting without network access using `--offline --repersist`. The rebuild preserves the MdB roster, leaves the previous database untouched on failure, and keeps the file when its content is unchanged.
- Compare two builds with a read-only report showing changes in speech text, vote majorities, affiliations, person pages, legislative pages, and published facts. Shared-sitting and whole-store modes keep new acquisitions distinct from corrected values.

### Fixed

- Speech lengths now include only the named speaker’s words, excluding the chair and intervening speakers. Unattributed text is measured separately.
- Parliamentary groups and factions use consistent names, including the historical Gruppe Die Linke; duplicate speaker names and merged source records are handled consistently.
- Government, Bundesrat, and other official speaking roles count separately from factions. Unknown roles stop persistence with a diagnostic naming the affected speeches.
- Vote majorities are absent on a tie or when nobody voted. Vote panels, archive filters, and dissent counts use the same rule; non-attached members are excluded from faction dissent.
- Person pages use verified identifiers and unambiguous name matches, keeping namesakes and conflicting DIP identities separate while rejoining corroborated records for people with two speaker IDs.
- Only legislative procedures receive Gesetzesvorhaben pages; other procedures on the same agenda item (Entschließungsanträge, Anträge) are listed on each Gesetzgebung’s page as such, not as its companions. Public labels and the data-correction recipes now describe these rules.

## [0.8.0.0] - 2026-09-29

### Added

- An update now fetches roll-call votes by default. Until now they were an opt-in, so every update since June recorded votes as "not requested" and the July and September 2026 votes never reached the site. `--no-votes` skips the scan for one run. Backfilled into a copy of the reference store, votes went from 217 to 232 and the newest vote from 2026-06-12 to 2026-09-25.
- Every build now says what is incomplete: the weeks and months that cannot post a Fakt yet, the sittings DIP lists that are missing or not fully acquired, why, and the exact command that fixes it. `--backfill-incomplete` acquires exactly those sittings and keeps every other cached dossier.
- A Fakt week or month that is held back names the sitting that is missing ("unvollständig erfasst: Sitzung 21/96 (2026-09-24) fehlt").
- The build logs how many roll-call list pages and vote pages each sitting needed, and the sittings of one build share the list pages.
- The repository now carries a domain glossary (`CONTEXT.md`) and decision records (`docs/adr/`) that define the terms the site uses (Sitzung, Dossier, Rede, Fakt, completeness and more), and why a Kurzintervention is not counted as a Rede.

### Changed

- A week or month is now complete only when every sitting DIP lists for it is in the store and fully acquired. Before, a sitting whose dossier failed or was never built was invisible, so a period could look complete on one of three sittings. On the reference copy this withholds the weeks and months that lack sittings (for example June 2026, which had been measured on 3 of 6 sittings), and 15 sittings whose roll-call votes match no agenda item stay incomplete until the match rule improves.
- A vote acquisition is complete only with evidence: the scan passed the sitting's date, no request failed, every listed vote found its agenda item, and the report records how the scan ended. Older reports without that record are re-acquired by the backfill.
- Every online build fetches the whole DIP catalog (checked against DIP's own count) and keeps every cached dossier. `--limit` and `--document-number` now narrow only which sittings are refreshed, never what the site and the store keep.
- A vote scan that fails for a network or server reason keeps the sitting's cached dossier instead of replacing it.
- Roll-call and XML page requests retry a transient network error; a reset while reading a DIP response no longer ends a long build.
- The README documents the backfill recipe, a scratch-directory preview, and the order in which config files, environment and flags decide which enrichments run.

### Fixed

- A Drucksache reference with a foreign URL no longer aborts the build (a cached 2022 dossier quotes a syriahr.com article).
- Cached reports and the catalog are written atomically, so an interrupted build cannot leave a truncated file.

### Removed

- `--preserve-existing-dossiers`. Every build keeps the dossiers it has cached; delete a dossier's JSON file to drop it. A systemd unit or script that passes the flag must drop it.

## [0.7.0.0] - 2026-09-28

### Added

- Every roll-call vote panel now shows whether the motion passed. The badge reads "Angenommen" or "Abgelehnt", sourced from bundestag.de's own stated result when the page states one, or otherwise computed from the vote count and marked "(berechnet)" so the difference is visible on hover.
- Every Drucksache a vote panel mentions now links to its source document instead of showing plain text, and a link to the vote's XLSX Namensliste export appears next to the detail link when bundestag.de has published one.
- A new "Abstimmungen" page lists every roll-call vote across every sitting the site has built, reverse-chronological and grouped by month, with a Fraktion filter (by that Fraktion's majority position on each vote).

## [0.6.6.0] - 2026-09-26

### Added

- The dossier sidebar now marks the TOP you are reading. The highlight follows scrolling, sidebar clicks, resizes and the end of the page, keeps the marked row in view inside the ranking list, and turns off where the sidebar sits above the text (narrow or short windows) and in print.
- Each SQL recipe on the Daten page has a "Kopieren" button. Where the browser cannot write to the clipboard, the button selects the SQL for ⌘C/Strg+C instead; a copy that fails late never overrides a newer click or your own selection. Without JavaScript the button stays hidden.
- Dossier footers link to the Daten page when the build has data to show, like the other pages' Daten links.

## [0.6.5.0] - 2026-09-25

### Changed

- When sitting counts differ, the Wochenvergleich now compares speeches, agenda items, speech text, and Fraktion speaking shares across weekdays present in both weeks. The page names those weekdays and keeps `n/a` when none overlap.

### Fixed

- The Wochenpuls sparkline now identifies its full-week trend when the figures above it use matched weekdays.

## [0.6.4.0] - 2026-09-25

### Changed

- The architecture diagram now traces Fakten, the Daten export and generation manifest through to the Daten page. A short contributor guide links the test, offline rebuild and online update commands.

### Fixed

- Command-line scripts now reject Python versions below the documented 3.11 floor with a clear English and German error.

## [0.6.3.0] - 2026-09-25

### Fixed

- Aufmerksamkeitsrang rows now begin with the agenda topic instead of procedural wording, keeping the first sub-item's topic on a bundled heading (an Antrag under a) followed by a Gesetzentwurf under b)); the complete normalized heading remains available on hover.

## [0.6.2.0] - 2026-09-25

### Fixed

- Ranking links retain matching TOP anchors when an index contains HTML-sensitive characters.
- Links share teal visited states and visible keyboard focus outlines, including pages without their own teal palette variable.

### Removed

- New stores and speech writes no longer duplicate speech text in `paragraphs_json`. Existing stores drop the column on SQLite 3.35+; older versions log a warning and retain it. Distribution downloads keep the same schema and row counts.

### Verified

- Dossiers already show the session title above the content and place the protocol developer dump after it. Regression coverage preserves both; explicit developer builds retain their existing visible raw data without a toggle, while normal builds omit it.

## [0.6.0.0] - 2026-09-24

### Added

- A new "Fakt der Woche" page series shows one standout, statistically unusual fact per sitting week (and, monthly, per calendar month): the closest vote, the most rebel votes against a Fraktion's line, the longest debate and longest single speech, the longest sitting, the most first-time speeches, the most active MP of the month and the month's most-discussed legislative matter. Every card names its comparison population and links straight back to the protocol, speech, vote or bill it cites; a Methodik page explains the rule and why some weeks post no fact at all (the numbers only qualify once they're unusual enough, not merely "the most" of a slow week). A new "Fakten" entry joins the site's main navigation.
- Each fact ships as a downloadable, shareable image card alongside its page — the longest-speech card now also names the debate's topic, not just who spoke.
- The Daten export documents the three new fact tables and the speech-time Fraktion column as derived/DIP-sourced data respectively, so a downloaded copy of the database is self-explanatory about where every column comes from.

### Changed

- The "Redeanteil nach Fraktion" export recipe now groups speeches by the Fraktion the speaker belonged to at the time of the speech, not their current party — a member who has since switched or left a Fraktion no longer retroactively changes an earlier week's speech-share numbers.
- Building the Fakt der Woche pages resolves each fact's source citation once per build instead of twice, and stops re-scanning the whole debate-topic table once per citation — the archive keeps rebuilding at the same speed as it grows week over week.

### Fixed

- Merging a duplicate party record (the historical "list-repr" party-name bug) now recomputes which side of a vote was the majority from the merged tallies, instead of leaving a stale majority that could misclassify who voted with or against their Fraktion.
- A citation whose page reference has no quadrant marker — a normal, common case in the protocol XML — now resolves correctly instead of being wrongly treated as an unrecoverable source.
- A sitting week with genuinely zero first-time speeches now counts correctly toward the "most first-time speeches" metric's history, instead of being silently dropped and skewing how surprising later weeks' counts look.
- Building the site with `--no-persist`, or before the Fakt der Woche data has ever been generated, no longer deletes a previous real build's published fact pages and cards, or overwrites the fact archive with a false "nothing published yet" message.

## [0.5.0.0] - 2026-09-19

### Added

- A deterministic, zero-credential demo now builds the official Plenarprotokoll 21/84 TOP 32 a/b acceptance case offline, validates the deployable artifact, and links all 16 speeches plus Drucksachen 21/6354 and 21/4833.
- Publications now carry a schema-v2 data-state manifest and a reader-facing Datenstand section that distinguish unavailable, partial, genuine-empty, reused, and not-requested data.
- Operators can inspect acquisition capabilities and resolved configuration without network access through `--list-capabilities` and `--explain-config`; development views are isolated from deployable output.

### Changed

- Every visitor now receives the same complete public experience—Aktueller Puls, Sitzungen, Gesetze, Abgeordnete, and Quellen—without a gear menu, feature switches, or hidden building blocks.
- AI summaries are the only content preference: valid summaries are expanded initially, clearly labelled as AI-generated and not editorially reviewed, globally collapsible, source-bound, citation-checked, and omitted cleanly when unavailable.
- `--enrich` now controls only optional acquisition of votes, abgeordnetenwatch profiles, and the full MP roster; deprecated feature inputs remain translating aliases through `0.5.x` and are scheduled for removal in `0.6.0`.

### Fixed

- Public source links now require allowlisted HTTPS hosts, generated paths are confined to the publication root, and CI rejects developer-marked or incomplete publication artifacts.
- The fixed public experience remains intact on the week-radar and Daten pages after integrating the latest `main` releases.

## [0.4.0.0] - 2026-09-19

### Added

- The "Daten" page (`database.html`) replaces the sample-row explorer with a download page: one click gets the gzipped SQLite distribution copy or any of the 16 CSV tables, each with its size and full sha256; a Datenstand band shows how many catalog protocols are covered as dossiers and which Bausteine (roll-call votes, abgeordnetenwatch profiles, MdB roster) the file contains; five SQL "Rezepte" run at every build against the very file offered for download, with their result rows shown next to the SQL and linked to the MP, protocol and bill pages; a "So geht's los" section gives three copy-paste routes (shell, Python stdlib, pandas); every table's columns, keys and foreign keys are listed in compact schema rows with a data dictionary that marks which source each column comes from.
- The distribution copy is built by `export_distribution_data()`: `speeches.paragraphs_json` (a duplicate of `speeches.text`) is dropped, `mp_canonical` maps every `mps` row to its consolidated person, and a `datenstand` table plus `PRAGMA user_version` mark the file as a distribution copy. Export needs SQLite ≥ 3.35; older builds render the page with a "Daten nicht erzeugt" notice naming the reason. Files are deterministic (gzip without timestamps), so unchanged inputs give byte-identical downloads; the export is skipped when nothing it depends on changed (store, recipes, export format, tag, licence, issues URL, coverage counts, Baustein readiness), re-run with `--force-export`, and skipped entirely when `--data-manifest` overrides it. Each export writes a fresh `data/exports/g-<hash>/` generation and removes the previous one only after `datenstand.json` points at the new one; concurrent builds are serialised by `data/exports/.lock`, and a lock left by a crashed build is cleared automatically.
- New CLI flags `--data-base-url`, `--data-manifest`, `--force-export`, `--data-license`, `--data-issues-url` with `BUNDESTAG_PULSE_DATA_*` env fallbacks (CLI beats env beats default); a `--data-manifest` URL is an explicit opt-in fetch (10 s timeout, 32 MB cap) that `--offline` refuses; an override manifest is shape-checked before rendering and the issues URL must use `https://`, `http://`, `mailto:` or a site-relative path. Documented in `docs/project-documentation.md`; the licence wording lives in `docs/data-license.md` (still pending).
- `persist_dip_pulse_store.connect()` refuses to open a distribution copy as a build store.

### Changed

- Nav label and every "Datenbank"/"Datenbank erkunden" mention across `index.html`, `overview.html`, `api-sitzungen.html` and `sources.html` renamed to "Daten"; the index page's two SQLite-download/explorer cards merge into one "Daten" card with a "Stand … · N Protokolle" line; the SQLite download link on every page now points at the distribution copy instead of the build store, and the in-page "Daten" links appear exactly when the page has content.
- `collect_abgeordnete()` returns a third value, `canonical_by_mp_id`, mapping every `mps.id` (not only page-eligible ones) to its consolidated person.
- `sources.html` gains a "Lizenz und Weiterverwendung" entry (`#lizenz`) that the Daten page links to; the wording is a placeholder until the data licence is settled.

### Fixed

- SQLite errors while building the distribution copy (locked store, full disk) surface as a named `error:` line instead of a traceback.

### Known stale docs

- `docs/bundestag-puls-architecture.html`/`.json` omitted the Daten export step and the Daten page; regenerated in 0.6.4.0.

## [0.3.0.0] - 2026-09-18

### Added

- `puls.html` is a week radar now (`docs/designs/puls-wochenradar.md`): the page header names the newest sitting week (or `--week`) with one chip per sitting and a facts sentence that says whether the week is still running, how old it is and when the build ran ("Auswertung vom"); "Themen der Woche" ranks the week's agenda items by speech count, names them by their DIP Vorgang titles (an Antrag-only group lists every title at equal weight), shows the share of all speeches with a bar, who spoke per Fraktion, a "Fortgesetzt" trace when the procedure ran in an earlier week, the KI-Zusammenfassung with receipts (`summaries`), a "namentlich abgestimmt" badge (`votes`) and a link into the protocol on every row; question formats (Befragung, Fragestunde, Regierungsbefragung) and the remaining agenda items are listed under the rows with their counts.
- The Wochenvergleich band gains a "Namentliche Abstimmungen" card aggregated over the week (`votes`), keeps its cards without a comparison week (Wochenpuls and Redeanteil of the current week, no deltas), and reads "n/a" on the Wochenpuls chips when the two weeks hold a different number of sittings.
- Build diagnostics for the page on stderr: `[puls] KW 24/2026: 3 Sitzungen, 5 Themen, 1 Frageformat, 22 weitere, today=…`, plus warnings for undated sittings, a week without extracted speeches and a build date before the sitting week (README §8).

### Changed

- `--today`, `SOURCE_DATE_EPOCH` and `--week` now shape `puls.html`; two builds of the same cache with the same pins are byte-identical.

### Removed

- The old `puls.html` hero (sitting summary, fact tiles, "Quellen" row), the Themenbewegung card, the per-sitting Abstimmungsverschiebung panel and the `#bewegung` anchor. `#wochenvergleich` and `#abstimmungen` stay.

## [0.2.3.0] - 2026-09-18

### Added

- Builds can be pinned: `--today YYYY-MM-DD` fixes the build date, `--week YYYY-WW` names the ISO sitting week for `puls.html`, and `SOURCE_DATE_EPOCH` (UTC) is honoured when `--today` is absent. Both are validated on every build now; `puls.html` starts reading them with the week radar in the next release.
- A `--week` that the build cannot hold is refused before any file is written, and the error lists the sitting weeks that are available.

### Changed

- Source links taken from DIP data (PDF sources on positions, activities, the KI-Zusammenfassung receipts and the developer details, XML/PDF links on the overview and Daten pages) are emitted only for `http(s)` URLs; anything else degrades to plain text.
- Groundwork for the `puls.html` week radar (`docs/designs/puls-wochenradar.md`): topic naming across positions and mitberaten twins, a shared occurrence index for the returning-procedures card, roll-call votes counted by id instead of by attachment, and shared receipt rendering. Nothing on the site changes yet; the page itself follows in the next release.

## [0.2.2.0] - 2026-09-14

### Fixed

- The Aufmerksamkeitsrang sidebar on protocol dossiers is now fully reachable: on desktop it stays pinned while its rows scroll inside the sidebar, with a fade showing when more agenda items are below, instead of clipping the tail until the very end of the page.
- On narrow screens the ranking opens as a short index (five agenda items, three on phones) with an "Alle N Tagesordnungspunkte anzeigen" button, so the agenda list sits right below it; expanding moves focus to the first revealed item, and every agenda item links back to the ranking.
- Dossiers without agenda items or without extracted speeches show a plain notice instead of an empty ranking, and printouts show every ranking row with no controls.

## [0.2.1.0] - 2026-09-13

### Fixed

- Protocol dossiers now show Drucksachen directly below each agenda item heading and give speaker lists the full card width instead of leaving a mostly empty second column.
- Agenda items without linked Drucksachen no longer show an empty public placeholder; the developer diagnostics continue to report the missing source data.

## [0.2.0.0] - 2026-09-06

### Added

- Website Bausteine are now true per-browser preferences: every publication contains all user-facing areas, switches apply immediately, survive reloads, and default to the core-only view.
- Settings report whether optional vote, summary, profile, and roster data is available, partial, or unavailable without triggering network requests.
- `--enrich votes|aw-profiles|mp-roster|all` explicitly selects optional update-time data acquisition; summary generation remains separately protected by `--summary-mode`.

### Changed

- Offline and reduced-enrichment builds no longer remove bill or MP pages. Missing source data produces an honest empty state instead.
- Browser dependencies are resolved locally: enabling bill following enables bills, and disabling bills disables bill following.
- The old feature-selection CLI, JSON, and environment inputs are deprecated for one release. They remain accepted with warnings but no longer control published UI.

## [0.1.1.0] - 2026-08-03

### Changed

- The README is now a full setup guide. It covers prerequisites, where to get a DIP API key, the first online build a fresh clone needs, the sub-second offline preview loop for everyday work, and what to run after new Bundestag data or after pulling code changes.
- Refreshing is documented as the three separate things it actually is: reloading the browser, fetching new parliamentary data, and rebuilding the site after a code update. Each one now has the exact command.
- The flags that decide how much of your local site survives an online build are spelled out, including why `--preserve-existing-dossiers` matters and how to rebuild a site that a narrow update shrank to a single sitting.
- Bausteine are documented end to end: per-build flags, durable defaults in `features.local.json`, why an offline build cannot fetch votes or profiles, and the difference between what a build makes available and what the gear menu shows.
- New sections cover server settings, hosting the generated site elsewhere, and a troubleshooting table keyed to the exact error messages you can hit, including the empty `DIP_API_KEY=` line that silently overrides a key you passed on the command line.

### Fixed

- The project documentation no longer suggests passing `DIP_API_KEY` as a one-command prefix without saying that a copied `.env.local` overwrites it, which made the suggested fix fail with the error it was meant to solve.

## [0.1.0.0] - 2026-08-02

### Added

- A single Baustein registry now controls build availability and browser visibility for votes, summaries, abgeordnetenwatch profiles, MP pages and roster data, bill tracking, and developer views.
- Repeatable `--enable`/`--disable` flags, `--features`, JSON configuration files, `BUNDESTAG_PULSE_FEATURES`, and `--list-features` provide one configuration vocabulary with dependency resolution.
- Every generated page now includes a settings gear, an instant local visibility panel, and a link to the full `settings.html` view. A tooling manifest is written to `data/features.json`.
- Addon modules are discovered lazily through `scripts/features/loader.py` and expose shared enrich, persist, page, section, style, and script hooks.

### Changed

- The shipped default is now strict core-only: DIP fetch, sitting catalogs, protocol dossiers, and the SQLite store/explorer. Optional network and content features must be enabled explicitly.
- Global navigation and page bootstrap/runtime scripts are centralized, so nested pages derive their links from their depth and every template receives the same feature behavior.

### Fixed

- Bill pages no longer generate the broken `bills/abgeordnete/index.html` link.
- The Datenbank navigation item no longer disappears from dossier, bill, or MP pages.
- Developer-only content is hidden before first paint, and every theme toggle on a page is now initialized.

## [0.0.2.0] - 2026-07-31

### Fixed

- "Aktueller Puls" now opens on the newest sitting you have data for. Offline previews used to pick whichever dossier file sorted first by name, so the 100th sitting of the 20th Bundestag from 27 April 2023 was presented as the current one.
- The home page snapshot, the sitting overview, and the sources page now name the same latest sitting as "Aktueller Puls" instead of disagreeing with it.
- The cached sitting catalog is written newest-first, whatever order the DIP API hands it back in.

### For contributors

- Regression coverage pins newest-first ordering across the rendered pages and the cached catalog, including dossiers whose metadata is missing or truncated.

## [0.0.1.0] - 2026-07-30

### For contributors

- Project agents now automatically select the right workflow for common planning, review, QA, and shipping tasks.
- Regression coverage now protects offline preview builds that reuse legacy SQLite caches.

### Fixed

- Offline previews now open legacy SQLite caches without crashing when newer MP biography fields are missing.
