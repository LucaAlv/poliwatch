# Data licence and attribution

**Status: pending.** The Daten page's download panel and manifest (`data/exports/datenstand.json`, field `license`) show whatever `--data-license` (or `$BUNDESTAG_PULSE_DATA_LICENSE`) is set to; the placeholder text until then is "Lizenzhinweis: siehe Quellen und Methode".

This file is the long-form counterpart of that string. It is copied into a future public release as `LICENSE-DATA.md` (`scripts/publish_dip_pulse_data.sh`, a separate PR) and that publish step refuses to run while the licence string is empty.

## What the distribution contains

- Plenary protocol structure, agenda items, speeches, and legislative procedures, extracted from official Bundestag DIP API sources (`dip.bundestag.de`).
- Roll-call vote results and per-member votes, extracted from Bundestag roll-call publications (`bundestag.de`).
- MdB biography fields (`birth_year`, `gender`, `profession`, `wahlkreis`, `bundesland`) from the DIP MdB roster, and `aw_politician_id`/`profile_url` from abgeordnetenwatch.de. `data/exports/datenstand.json` marks each column's source (`tables[].columns[].source`).
- `speeches.fraktion`: the Fraktion the plenary protocol XML names for the speaker of that Rede, normalised to the same spellings as `parties.name`. It is the affiliation at the time of the speech, where `mps.party_id` is the affiliation as of the last build; `NULL` when the XML names no Fraktion (a minister speaking in role). Source `dip`, like the rest of the protocol extraction.
- A derived `mp_canonical` table mapping every internal `mps.id` to a consolidated person id, used to make the exported "Rezepte" counts match the site's own profile pages.

## What is not yet settled

- The exact reuse/attribution wording for redistributing DIP data, roll-call data, and abgeordnetenwatch profile links together in one file.
- Whether any field needs to be excluded from public redistribution beyond what is already excluded (raw speech text is truncated to a snippet on the site, but the distribution SQLite still carries the full `speeches.text` — the duplicate `paragraphs_json` column is dropped at export time, `text` is not).

Until this is resolved, no public release should be published (`scripts/publish_dip_pulse_data.sh` enforces this once it lands).
