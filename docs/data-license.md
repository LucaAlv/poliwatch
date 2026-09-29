# Data licence and attribution

**Status: decided 2026-09-28** ([ADR 0003](adr/0003-licences-and-impressum.md)), not yet wired into the build.

The Daten page's download panel and manifest (`data/exports/datenstand.json`, field `license`) show whatever `--data-license` (or `$BUNDESTAG_PULSE_DATA_LICENSE`) is set to. The placeholder "Lizenzhinweis: siehe Quellen und Methode" stays until the short string below is set.

This file is the long-form counterpart of that string. It is copied into a public release as `LICENSE-DATA.md` (`scripts/publish_dip_pulse_data.sh`, a separate PR), and that publish step refuses to run while the licence string is empty.

## Short string

> Quelldaten: Deutscher Bundestag/Bundesrat – DIP (Nutzungsbedingungen DIP) und Deutscher Bundestag (namentliche Abstimmungen); Profildaten: abgeordnetenwatch.de (CC0 1.0); eigene Auswertungen: CC BY 4.0 (Namensnennung: Bundestag-Puls, Luca Veh). Aufbereitet und verändert; Details in LICENSE-DATA.md.

## Terms per layer

The file combines sources with different terms. Each column's layer is its `source` tag in `data/exports/datenstand.json` (`tables[].columns[].source`).

| `source` tag | Contents | Terms and attribution |
|---|---|---|
| `dip` | Plenary protocol structure, agenda items, speeches (including full `speeches.text`), legislative procedures and documents, extracted from the DIP API and the Plenarprotokoll XML | [Nutzungsbedingungen DIP](https://dip.bundestag.de/documents/nutzungsbedingungen_dip.pdf). Source: „Deutscher Bundestag/Bundesrat – DIP"; cited protocols additionally as „BT-PlPr." plus number (e.g. „BT-PlPr. 21/84"). Plenarprotokolle are amtliche Werke (§ 5 Abs. 2 UrhG): no copyright, but no alteration (§ 62) and source duty (§ 63). |
| `bundestag.de` | Roll-call results and per-member votes (`votes`, `vote_fractions`, `vote_members`, `vote_documents`, `agenda_item_votes`), including `votes.xlsx_url`, the link to the XLSX Namensliste, matched by date and title on bundestag.de's list page | Source: „Deutscher Bundestag". The per-member results are also printed in the Plenarprotokoll („Endgültiges Ergebnis"), an amtliches Werk; see ADR 0003, open question 5. |
| `abgeordnetenwatch` | `mps.aw_politician_id`, `profile_url`, `birth_year`, `gender`, `profession`, `wahlkreis`, `bundesland` | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/deed.de) ([abgeordnetenwatch.de/api](https://www.abgeordnetenwatch.de/api)). Attribution not required; given as courtesy. |
| `derived` | `mp_canonical`, `datenstand`, `fact_metrics`, `facts`, `fact_sources`, and `votes.result_raw`/`result_source` (the Angenommen/Abgelehnt badge: mostly a computed yes/no majority; `result_source = "official"` marks rows where bundestag.de states the result itself) | Our own work, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.de). They are computed from the layers above, whose attribution duties still apply. |

The DIP terms, in particular no. 5, continue to apply to any reuse of the DIP layer. That clause forbids use in a distorting context or use that could disparage members of the Bundestag, the Bundesrat, the government or others. It is a condition of the source, not an additional term we impose.

## What we changed (DIP no. 4b)

- The protocol XML and DIP API records are extracted and split into tables. `speeches.text` is the speech text with whitespace normalised: the paragraphs of a Rede (without the speaker line) are joined with single spaces, non-breaking spaces become plain spaces, and runs of whitespace collapse to one space. Wording and punctuation are not edited, but paragraph breaks are not kept. The duplicate `paragraphs_json` column is dropped at export.
- Fraktion spellings are normalised to one form per Fraktion (`parties.name`, `speeches.fraktion`).
  - `speeches.fraktion` is the Fraktion the protocol names for that Rede, i.e. the affiliation at the time of the speech.
  - `mps.party_id` is the affiliation as of the last build.
  - `speeches.fraktion` is `NULL` when the XML names no Fraktion (a minister speaking in role).
- Persons from the DIP roster, the protocol XML and the roll-call lists are consolidated into one person id (`mp_canonical`). Its purpose is that the exported „Rezepte" counts match the site's profile pages.
- `fact_metrics`, `facts` and `fact_sources` are computed by `scripts/facts.py` at build time (percentiles, baselines, receipts). `mp_canonical` and `datenstand` are created by `scripts/build_dip_pulse_site.py` during export.
- The site's machine-generated summaries are not part of the export.

## Known gap

Until the provenance fix in TODOS.md lands, the manifest still tags `mps.birth_year`, `gender`, `profession`, `wahlkreis` and `bundesland` as `dip`. The table above gives their real source, abgeordnetenwatch.

## Disclaimer

No warranty for correctness; this also applies to the sources (DIP no. 6). This notice is not legal advice. The questions still open for a lawyer are listed in ADR 0003.
