# Data licence and attribution

**Status: decided 2026-09-28** ([ADR 0003](adr/0003-licences-and-impressum.md)), not yet wired into the build.

The Daten page's download panel and manifest (`data/exports/datenstand.json`, field `license`) show whatever `--data-license` (or `$BUNDESTAG_PULSE_DATA_LICENSE`) is set to. The placeholder "Lizenzhinweis: siehe Quellen und Methode" stays until the short string below is set.

This file is the long-form counterpart of that string. It is copied into a public release as `LICENSE-DATA.md` (`scripts/publish_dip_pulse_data.sh`, a separate PR), and that publish step refuses to run while the licence string is empty.

Everything from „Short string“ on is also embedded unchanged, headings one level down, in each export's `DATA.md` (`_license_notice` in `scripts/build_dip_pulse_site.py`). This status note and the paragraphs above it are for maintainers and stay out of `DATA.md`; keep researcher-facing text below the first `##` heading.

## Short string

> Quelldaten: Deutscher Bundestag/Bundesrat – DIP (Nutzungsbedingungen DIP) und Deutscher Bundestag (namentliche Abstimmungen); Profildaten: abgeordnetenwatch.de (CC0 1.0); eigene Auswertungen: CC BY 4.0 (Namensnennung: Bundestag-Puls, Luca Veh). Aufbereitet und verändert; Details in LICENSE-DATA.md.

## Terms per layer

The file combines sources with different terms. Each column's licence is the layer `DATA.md` gives it (column „Lizenzschicht", authored in `scripts/data_dictionary.json`). The `source` tag in `data/exports/datenstand.json` (`tables[].columns[].source`) is the coarser origin class in the table below; the export fails when a column's layer does not allow its tag (`LICENSE_LAYER_SOURCES`). That check catches cross-origin contradictions only: the CC BY metadata layers also allow `dip` and `bundestag.de` tags, so whether a column is metadata or content rests on the authored layer. Our own ids and timestamps on source tables are project metadata under CC BY 4.0 even where the tag names the source.

| `source` tag | Contents | Terms and attribution |
|---|---|---|
| `dip` | Plenary protocol structure, agenda items, speeches (including full `speeches.text`) and contributions (Kurzinterventionen, Erwiderungen, Fragen and Antworten, including full `contributions.text`), legislative procedures and documents, extracted from the DIP API and the Plenarprotokoll XML | [Nutzungsbedingungen DIP](https://dip.bundestag.de/documents/nutzungsbedingungen_dip.pdf). Source: „Deutscher Bundestag/Bundesrat – DIP"; cited protocols additionally as „BT-PlPr." plus number (e.g. „BT-PlPr. 21/84"). Plenarprotokolle are amtliche Werke (§ 5 Abs. 2 UrhG): no copyright, but no alteration (§ 62) and source duty (§ 63). |
| `bundestag.de` | Roll-call results and per-member votes (`votes`, `vote_fractions`, `vote_members`, `vote_documents`, `agenda_item_votes`), including `votes.xlsx_url`, the link to the XLSX Namensliste, and nullable `votes.debate_url`, the scraped Bundestag report link associated with the vote's Debatte panel | Source: „Deutscher Bundestag". `result_raw` keeps the result for the proposition actually voted on, `result_source` says whether it was official or derived, and `result_scope` records whether an official result refers to the recommendation or the Antrag. The per-member results are also printed in the Plenarprotokoll („Endgültiges Ergebnis"), an amtliches Werk; see ADR 0003, open question 5. |
| `abgeordnetenwatch` | `mps.aw_politician_id`, `profile_url`, `birth_year`, `gender`, `profession`, `wahlkreis`, `bundesland` | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.de) ([abgeordnetenwatch.de/api](https://www.abgeordnetenwatch.de/api)). Attribution not required; given as courtesy. |
| `derived` | `mp_canonical`, `datenstand`, `agenda_item_politikfelder` and `vote_politikfelder` (the Politikfeld tags: a fixed rule maps the DIP Sachgebiet labels of the linked Vorgänge to 13 Politikfelder; no model writes them), `vote_proceedings` and `votes.context_state` (the Vorgänge a roll-call vote is about, chosen by a fixed rule from its Drucksache numbers, and whether that rule found one, found none, or lacked the DIP data), `fact_metrics`, `facts`, `fact_sources`, the person registry (`persons`, `person_aliases`, `person_records`, `person_bindings`), `votes.inverted`/`inversion_source`/`inversion_excerpt` (evidence that a recommendation was to reject an Antrag), and `contributions.kind`/`parent_rede_id`/`sprechrolle` (the parser's classification of what the Plenarprotokoll records as a Beitrag) | Our own work, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de). They are computed from the layers above, whose attribution duties still apply. |

The DIP terms, in particular no. 5, continue to apply to any reuse of the DIP layer. That clause forbids use in a distorting context or use that could disparage members of the Bundestag, the Bundesrat, the government or others. It is a condition of the source, not an additional term we impose.

## What we changed (DIP no. 4b)

- The protocol XML and DIP API records are extracted and split into tables. `speeches.text` is the speech text with whitespace normalised: the paragraphs of a Rede (without the speaker line) are joined with single spaces, non-breaking spaces become plain spaces, and runs of whitespace collapse to one space. Wording and punctuation are not edited, but paragraph breaks are not kept. The duplicate `paragraphs_json` column is dropped at export.
- The parser classifies each turn of the protocol. `speeches` holds Reden only. Kurzinterventionen, Erwiderungen, and the Fragen and Antworten of a Befragung or Fragestunde are stored as Beiträge in `contributions` (`kind`, `parent_rede_id`, `sprechrolle`). The protocol does not label these kinds as data: the classification is ours, made from the wording and structure of the XML, and is not free of errors. A Beitrag the parser missed is still in `speeches`.
- Fraktion spellings are normalised to one form per Fraktion (`parties.name`, `speeches.fraktion`).
  - `speeches.fraktion` is the Fraktion the protocol names for that Rede, i.e. the affiliation at the time of the speech.
  - `mps.party_id` is the affiliation as of the last build.
  - `speeches.fraktion` is `NULL` when the XML names no Fraktion (a minister speaking in role).
- Persons from the DIP roster, the protocol XML and the roll-call lists are consolidated into one person id by the person registry (`persons`, `person_aliases`, `person_records`, `person_bindings`; `mp_canonical` maps every source record to its person). Its purpose is that the exported „Rezepte" counts match the site's profile pages.
- A roll-call vote is stored once per source vote. `votes.protocol_id` preserves its sitting even when no agenda item could be attributed; `agenda_item_votes` remains the optional topic link. Topic-based facts retain an unknown topic for these votes, while sitting-level vote counts and member histories still include them.
- `fact_metrics`, `facts` and `fact_sources` are computed by `scripts/facts.py` at build time (percentiles, baselines, receipts). `mp_canonical` and `datenstand` are created by `scripts/build_dip_pulse_site.py` during export.
- `proceedings.abstract` is DIP's Vorgang abstract with the HTML stripped and whitespace normalised: a line break (`<br>`) or block element ends a paragraph, paragraphs are separated by a blank line (`\n\n`), other markup such as `<strong>` is removed with its text kept, entities are decoded, and runs of whitespace inside a paragraph collapse to one space. Wording is not edited. Only the first 10,000 characters are read (the longest on the reference cache has 5,111), and a numeric character reference past U+10FFFF reads as U+FFFD.
- The site's machine-generated summaries are not part of the export.

## Disclaimer

No warranty for correctness; this also applies to the sources (DIP no. 6). This notice is not legal advice. The questions still open for a lawyer are listed in ADR 0003.
