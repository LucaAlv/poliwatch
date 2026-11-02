# 0003 Licences, attribution and Impressum for the public release

**Status:** accepted, 2026-09-28. Not legal advice; the open questions at the end need a lawyer before launch.

## Context

The Daten download redistributes DIP data, bundestag.de roll-call data and abgeordnetenwatch data in one SQLite file, and the site goes public under a person's name. What each source allows (read 2026-09-28):

- **DIP** — [Nutzungsbedingungen DIP](https://dip.bundestag.de/documents/nutzungsbedingungen_dip.pdf) (27 Feb 2023).
  - **4b:** API data "dürfen umfassend in jeglicher Form genutzt und weiterverarbeitet werden".
  - Redistribution must always name the source, and changes must be marked as such.
  - **4c:** the source is „Deutscher Bundestag/Bundesrat – DIP"; cited protocols additionally get „BT-PlPr." plus the number.
  - **4d:** commercial use must say the data is free on dip.bundestag.de.
  - **5:** no use in a „sinnentstellenden Zusammenhang" or that could lead to the „Herabwürdigung" of members.
  - **6:** no warranty; third-party rights are the user's risk.
- **bundestag.de** — [Impressum/Nutzungsbedingungen](https://www.bundestag.de/services/impressum).
  - Site content is private use only „sofern nachfolgend nicht anders geregelt".
  - Drucksachen and Plenarprotokolle are amtliche Werke without copyright ([§ 5 Abs. 2 UrhG](https://www.gesetze-im-internet.de/urhg/__5.html)). They remain subject to the change ban (§ 62) and the source duty ([§ 63 UrhG](https://www.gesetze-im-internet.de/urhg/__63.html)).
  - [Open Data](https://www.bundestag.de/services/opendata) lists the roll-call XLSX lists as machine-readable open data but names no licence.
- **abgeordnetenwatch.de** — [API page](https://www.abgeordnetenwatch.de/api): "Die Daten stellen wir unter der CC0 1.0-Lizenz zur Verfügung." There is no attribution request.
- **Roll-call results in the protocol.** The Plenarprotokoll prints the „Endgültiges Ergebnis" of each namentliche Abstimmung with member names under Ja/Nein/Enthalten; checked in [21/84 XML](https://dserver.bundestag.de/btp/21/21084.xml). So the per-member results we scrape from bundestag.de are also part of an amtliches Werk.
- **Impressum law:**
  - [§ 5 DDG](https://www.gesetze-im-internet.de/ddg/__5.html) covers services that are „geschäftsmäßig, in der Regel gegen Entgelt".
  - [§ 18 Abs. 1 MStV](https://www.gesetze-bayern.de/Content/Document/MStV-18) requires name and address from any Telemedium that is not purely personal or family.
  - § 18 Abs. 2 MStV additionally requires a named natural person as „Verantwortlicher" for journalistic-editorial offers.
- For comparison, [plenarwatch.de/impressum](https://plenarwatch.de/impressum/) names a GbR i. G. as provider and one partner under § 18 Abs. 2 MStV.

DIP clause 5 and the duties to name the source and mark changes are conditions we received, not ones we can waive. **The DIP-derived data therefore cannot be relicensed as a whole under CC0 or CC BY.**

## Decisions

### D1 Data licence: a layered notice, one layer per source

| Layer | Tables/columns (manifest `source` tag) | Terms |
|---|---|---|
| DIP and Plenarprotokoll extraction | every column tagged `dip` | Nutzungsbedingungen DIP; source line „Deutscher Bundestag/Bundesrat – DIP"; protocol citations as „BT-PlPr. 21/84" |
| Roll-call votes | `votes`, `vote_fractions`, `vote_members`, `vote_documents`, `agenda_item_votes` (`bundestag.de`) | Source „Deutscher Bundestag". The Ja/Nein/Enthalten lists are also printed in the Plenarprotokoll (amtliches Werk, § 5 Abs. 2 UrhG), which is the basis we rely on. Non-voters and `xlsx_url` depend on the open follow-up (question 5) |
| abgeordnetenwatch | `mps.aw_politician_id`, `profile_url`, `birth_year`, `gender`, `profession`, `wahlkreis`, `bundesland` | CC0 1.0 |
| Our own work | everything tagged `derived` (`facts`, `fact_metrics`, `fact_sources`, `mp_canonical`, `datenstand`, `votes.inverted`/`inversion_source`/`inversion_excerpt`, `votes.result_raw`/`result_source`/`result_scope`/`procedure_type`, `mps.person_id`/`aw_match`) | CC BY 4.0; DIP's source duty still applies to what they are computed from |

**Amended 2026-10-29 (export format 10, the codebook layout).** A column's layer is now the „Lizenzschicht" `DATA.md` gives it from `scripts/data_dictionary.json`; the manifest `source` tag is the coarser origin class, and the export fails when the layer does not allow the tag (`LICENSE_LAYER_SOURCES` in `scripts/build_dip_pulse_site.py`). The check catches cross-origin contradictions only; the CC BY metadata layers also allow source tags, so the authored layer decides metadata versus content. This refines the table above: our own ids and timestamps on source tables are project metadata under CC BY 4.0, and computed columns such as `vote_fractions.leading_vote` are our own work although their table is a roll-call table.

**Change marking (DIP 4b).** The notice lists what we changed:
- text and structure are extracted from the protocol XML and the DIP API into tables;
- each turn of the protocol is classified: `speeches` holds Reden only, and Kurzinterventionen, Erwiderungen and the Fragen and Antworten of a Befragung or Fragestunde are stored as Beiträge in `contributions` (ADR 0002); the classification is ours, made from the wording and structure of the XML;
- Fraktion spellings are normalised (`speeches.fraktion`, `parties.name`);
- persons are consolidated across sources (`mp_canonical`);
- the `derived` tables are computed by us.

The site's LLM summaries are not in the export. On the site they must be labelled as machine-generated; both renderers print „KI-generiert · nicht redaktionell geprüft“ with `data-ai-generated="true"`, pinned by a test since 2026-11-01. Fakten, vote leads and Politikfelder are rule output, which no model writes.

**Clause 5** is passed on as a notice ("Die Nutzungsbedingungen des DIP, insbesondere Nr. 5, gelten für Weiterverwendungen fort"). We don't restate it as our own licence term.

**Short string** for `--data-license` and the manifest:
> Quelldaten: Deutscher Bundestag/Bundesrat – DIP (Nutzungsbedingungen DIP) und Deutscher Bundestag (namentliche Abstimmungen); Profildaten: abgeordnetenwatch.de (CC0 1.0); eigene Auswertungen: CC BY 4.0 (Namensnennung: Bundestag-Puls, Luca Veh). Aufbereitet und verändert; Details in LICENSE-DATA.md.

**Commercial use:** none, so DIP 4d does not apply today. Revisit if donations start (see D4).

Rejected alternatives:
- One DIP notice for the whole file: it over-restricts the CC0 and self-made parts.
- Switching the vote source to the protocol XML or abgeordnetenwatch first: kept as a fallback if the Bundestag objects (see follow-ups).

### D2 `speeches.text` ships in full

The text is an extraction from the Plenarprotokoll, an amtliches Werk, not a verbatim copy: the paragraphs of a Rede are joined with single spaces, non-breaking spaces become plain spaces, and whitespace runs collapse (`validate_dip_protocol.speech_text_and_paragraphs`, `persist_dip_pulse_store.clean`). Wording and punctuation are untouched. Whether that meets § 62 (no changes) is open question 7. § 63 (name the source) is met by the source line.

The full-corpus file is not a collection that consists „überwiegend" of one speaker's speeches ([§ 48 Abs. 2 UrhG](https://www.gesetze-im-internet.de/urhg/__48.html)).

A future per-MP export of all of one person's speeches needs its own check before it ships.

### D3 Code licence: MIT

- The repository code is under MIT; copyright holder is the site operator (D4).
- MIT covers code only. Generated data and exports fall under D1, stated in both `LICENSE` and `LICENSE-DATA.md`.
- Permissive was chosen over copyleft (AGPL-3.0, EUPL-1.2) to maximise reuse.
- Apache-2.0 was the alternative, with an explicit patent grant. Switching before launch costs only the file.

### D4 Impressum: private person

- The operator is a private natural person (Luca Veh). There is no GbR or other entity.
- The Impressum names the person, a ladungsfähige postal address and an e-mail address, citing § 5 DDG and § 18 MStV. The same person is also named „Verantwortlich nach § 18 Abs. 2 MStV", as a precaution: Fakt der Woche and the summaries may count as journalistic-editorial content (question 6).
- A Datenschutzerklärung (GDPR) is required next to the Impressum; hosting access logs at minimum.
- No payments today. If donations are added later, re-check:
  - whether the site becomes „geschäftsmäßig" under § 5 DDG;
  - whether DIP 4d applies;
  - whether a separate recipient is wanted (plenarwatch routes donations to a sole proprietorship).

### D5 Contribution governance and contact channels

The operator is one person with limited time, the audience is mostly not developers, and the subject is political. Governance therefore optimises for usable data-error reports and for keeping party politics out of the tracker.

- **Two channels:**
  - **GitHub Issues** for everything public: data errors and site bugs.
  - **The Impressum e-mail** (a dedicated address, not a personal one) only for what cannot be public: GDPR requests, corrections or takedown demands from the people concerned, press enquiries, and security reports from people without a GitHub account.
  - E-mail is answered at the operator's discretion. Everything else is redirected to Issues, with no promise of a reply.
- **Security:**
  - GitHub private vulnerability reporting, plus `/.well-known/security.txt` (RFC 9116) on the site pointing to it and to the e-mail.
  - `SECURITY.md` defines the scope: injection through source text into HTML, leaked keys, a tampered download. A wrong figure is a data error, not a security issue.
- **Conduct:** short German project rules linked from `CONTRIBUTING.md` instead of Contributor Covenant 2.1 (which 3.0 has superseded):
  - Issues are about data, method and code, not about whether a politician or party is right.
  - Party-political debate is closed without discussion.
  - No disparaging statements about people. This mirrors DIP no. 5, which the data carries anyway.
  - Covenant 3.0 was not adopted: its enforcement ladder assumes moderators this project doesn't have.
- **Issue forms** (YAML, German, auto-applying triage labels):
  - „Datenfehler" with required page URL, what the site says, what the source says, and a DIP/protocol link.
  - „Fehler auf der Seite".
  - Blank issues are off.
  - No ideas template, and Discussions stay off until there is demand.
  - The site's „Fehler melden" link (`issues_url`) opens the Datenfehler form with the page URL pre-filled.

**Amended 2026-11-01 (what the first governance batch ships).**
- **Link:** the label is „Datenfehler melden (GitHub)", so a reader knows before the click that the report happens on GitHub and needs an account. The only report link is the Daten page footer; per-page links wait for a site base URL and A3 (TODOS.md).
- **Pre-fill:** the page pre-fill is a configured query string, not a render-time helper. The documented `--data-issues-url` value in `docs/project-documentation.md` opens the form with `seite=database.html`; `tests/test_issue_forms.py` checks that the template and field ids it names exist. The operator sets it for the public build only once the repository is public; a private repository gives non-members a 404.
- **Datenfehler form:** two optional fields beyond the list above: `datenstand` (the release, for errors in a download) and `hinweise`. The intro states that confirmed errors are fixed and the issue closed, with no promised reply.
- **No conduct checkbox:** a required checkbox is not enforced while the repository is private, and a ticked box changes no behaviour. The rules (`CODE_OF_CONDUCT.md`, „Regeln für Beiträge") are linked from the forms' intro and from `CONTRIBUTING.md`.
- **Labels:** the forms apply `needs-triage`, plus `datenfehler` or `bug`; a label missing from the repository is skipped silently.
- **E-mail channel:** the „Private Anliegen" contact link in `config.yml`, the e-mail address in `SECURITY.md` and conduct rule 4, and `security.txt` wait for the Impressum and the final domain. Until then the forms say private matters do not belong in a public issue and name no alternative.
- **Security reporting:** GitHub private vulnerability reporting can be switched on only for a public repository, so it follows the visibility flip. `SECURITY.md` says so until then.

## Open questions for a lawyer before launch

1. Whether a c/o or Impressum address service satisfies § 18 MStV for a private person, or whether the home address must be published.
2. Whether DIP clause 5 must or can be passed on to downstream users, and how it sits next to CC BY/CC0 layers in the same file.
3. Whether speeches inside a Plenarprotokoll are part of the amtliches Werk or remain the speaker's own work (§ 48 vs § 5 UrhG), and where the line falls for per-MP speech views.
4. Legal basis for publishing personal data (MPs' names, birth years, votes, Zwischenruf authors) under the GDPR, including whether Art. 85 (journalistic purposes) applies.
5. Whether redistributing the bundestag.de roll-call scrape is covered by the protocol basis, or needs the Bundestag's written consent.
   - The cheaper first step is a one-line question to parlamentsdokumentation@bundestag.de.
6. Whether the site is „journalistisch-redaktionell gestaltet" at all (§ 18 Abs. 2 MStV, and the press-law duties that come with it), or whether § 18 Abs. 1 is enough.

7. Whether whitespace normalisation and joining paragraphs (D2) count as a change under § 62 UrhG, or whether the export must keep paragraph breaks.
8. Whether the two localStorage entries the site writes on a click (the theme and the AI-summary collapse state, never transmitted) need consent or a statement of their basis under § 25 TDDDG. `datenschutz.html` describes them and states no legal basis.

## Consequences and follow-ups

Tracked in `TODOS.md`:
- **Implementation (built 2026-11-01, `docs/plans/impressum-datenschutz-licence.md`):** footer links, `impressum.html`, `datenschutz.html`, `LICENSE` (MIT), `LICENSE-DATA.md` (formerly `docs/data-license.md`), the `--data-license` default, and the `lizenz` item on `sources.html`. The operator's values are still missing (see the amendment below).

## Amendment, 2026-11-01: where the operator data and the licence text live

- **Operator data (D4) stays out of git.** Name, postal address, e-mail, host and supervisory authority come from a local JSON file passed as `--operator-file` (or `$BUNDESTAG_PULSE_OPERATOR_FILE`), not from the repository: the repository will go public, and an address in its history cannot be taken back, which matters if question 1 allows a c/o address or the address changes. A value the file does not give renders as a `data-operator-missing` placeholder, and the future deploy step must refuse any page that still carries one (TODOS, hosting item).
- **One source for the data licence (D1).** The root `LICENSE-DATA.md` is the only copy of the licence text. Every export carries it next to `DATA.md`, which quotes it from „Short string“ on, and its short string is the default `--data-license`. The maintainer notes of the former `docs/data-license.md` moved to `docs/project-documentation.md`.
- **Provenance fix (completed 2026-10-22).** Export format 6 tags `mps.birth_year`, `gender`, `profession`, `wahlkreis` and `bundesland` as `abgeordnetenwatch`, matching the roster enrichment and the D1 table.
- **Citation format:** protocol citations must read „BT-PlPr." with the period.
- **Roll-call coverage:** check whether non-voters („nicht abgegeben") are also listed in the protocol, or only in the XLSX.
- **Governance:** `SECURITY.md`, `security.txt`, the conduct rules, the issue forms and the e-mail scope, per D5.
