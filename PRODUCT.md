# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, each held to its own bar. Neither bar is traded for the other.

**The politically interested citizen** expects convenience, intuition and a high-quality experience. They want to know what the Bundestag is doing right now, whether it is discussing what matters to them, and how that has changed, without learning the DIP data model. They visit on desktop and on mobile, and many come back regularly.

**Researchers and journalists** expect consistency, quality and data integrity. They want a dataset they can build peer-reviewed research and published articles on: tidy, drawn directly from the official record, versioned and citable. They also use the site's analyses as a starting point and check them against the data.

## Product Purpose

The project is two things built on one base.

**1. The dataset.** The official Bundestag record, mainly the Plenarprotokolle, turned into a coherent collection of tidy data that is directly traceable to its source. It covers Sitzungen, Tagesordnungspunkte, Reden, Drucksachen, Vorgänge, namentliche Abstimmungen and Abgeordnete. It is released in versions, documented, and citable. Version 1 covers the Wahlperioden with structured Plenarprotokoll XML. The DIP catalog lists that XML for WP 18 (from October 2013) to the present, and for none of WP 1–17. Earlier Wahlperioden are a later extension.

**2. The website,** which presents the dataset. It has two angles, weighted equally:

- **What the Bundestag is doing now.** A place people return to for the current and recent business of the plenary: the most recent Sitzungen with a published protocol, the Sitzungswoche they belong to and the next planned one, who is speaking, which laws and motions are being debated, and how the Abstimmungen came out. It favours intuition, quick facts and overviews. Every item is one click from its source. Reference for the votes part: the Abstimmungen of abgeordnetenwatch.de.
- **Long-term analysis.** Visualisations of the longer-running ties and trends in the dataset: which Zusammenschluss emphasises which Politikfelder, how much attention a topic such as Klimaschutz or Migration gets over time, how the language of the debate changes, who interrupts the flow of debate most. Reference: the Diskursanalyse of opendiscourse.de.

Both angles are to read the same dataset, so that a figure on the site is the figure a researcher gets from the release it was built from. Today only part of the site works that way (see Capabilities and Constraints).

A release succeeds when a typical visitor can do the following on desktop and on mobile:
1. Find out what the Bundestag discussed in its latest Sitzung and latest Sitzungswoche, and reach the Dossier of a Tagesordnungspunkt.
2. Find a vote, a linked Drucksache or a speaker's page, and correctly understand the missing-data message when there is none.
3. Open an analysis of a topic over time, read it correctly, and reach the Reden behind a data point.
Later, not v1: open a primary source from an AI summary, and see that the summary is generated and has not been editorially checked.

And when a researcher can download a release, cite it by version, and reproduce every figure the site shows from it.

## Positioning

The differentiator is the connection. Debate, people, legislation and votes form one path, and each item links back to the official record: protocol XML or PDF, Drucksache, roll-call publication. The daily view and the long-term analyses are built from the same dataset, so a reader can go from a trend to the Reden behind it, and from a single Sitzung to where it sits in the trend. Every figure is meant to be traceable. The published SQL recipes already run against the store at build time. Moving the rest of the site onto the same store is planned.

A tidy, citable record of the debates alone is not the difference: CPP-BT already offers one. The difference is the linked, current record. No other dataset was found that links speeches, TOPs, Drucksachen, Vorgänge and named votes through the current Wahlperiode. That rests on a search of November 2026, not on proof, so check it again before saying so publicly (`docs/research/bundestag-corpora-landscape-2026-11.md`).

Related research datasets. These are independent projects working in the same direction, an open parliamentary record. This project is not affiliated with any of them; the owner is open to working together later.
- **CPP-BT** (Seán Fobbe): the largest overlap. Reden text and metadata from the same XML, WP 1–21, CC0, with no links to TOPs, Drucksachen, Vorgänge or votes in its speech table.
- **GermaParl** (PolMine): annotated debates from 1949, the better choice for language and discourse work. Its open version ends in July 2023.
- **ParlLawSpeech:** the closest idea to ours, speech to bill to law, but for Germany only from 2009 to 2021.
- **BTVote:** the reference for roll-calls, up to WP 19.

Comparable sites:
- **abgeordnetenwatch.de:** leads with MPs and named votes. Its Abstimmungen are the reference for the votes part of the daily view: topic tags, a plain-language description of what was decided, source documents, dissenters.
- **opendiscourse.de:** a full-text corpus of Plenarprotokolle from 1949 to 2020. Its Diskursanalyse is the reference for the long-term view. It uses 73 LDA-modelled topics with yearly granularity. This project uses published, reviewable term lists instead (confirmed 2026-11-06), so every point on a curve can be recounted from the dataset. A neutrality review of the lists comes before any term series is published.
- **plenarwatch.de:** votes and debates from primary sources, with published counting rules at /methodik/.
- The official Parlamentsdokumentation (DIP).

## Operating Context

- Visitors read German parliamentary material: Plenarprotokolle, Tagesordnungspunkte (TOPs), Reden, Drucksachen, Vorgänge, namentliche Abstimmungen, and Fraktionen.
- Data comes from the DIP API (dip.bundestag.de), the Plenarprotokoll XML, bundestag.de roll-call publications, the DIP MdB roster, and abgeordnetenwatch.de profile data.
- Coverage for version 1 is WP 18 to the present. The protocol catalog reaches back to 1949, but only as metadata. It does not produce Dossiers.
- An operator runs the build (`scripts/preview_dip_pulse_site.sh`). Operators decide what data gets fetched and enriched. They do not decide what visitors see.
- It is currently hosted locally only. The public host will be a German host with SSH, provider not picked yet, with data files on GitHub Releases and Zenodo. Design decisions must be ones that could ship to a public audience within weeks.

## Capabilities and Constraints

- **Stack:** a Python standard-library pipeline that writes plain HTML, JSON and SQLite, with no package manager, framework or build toolchain. A public record has to stay buildable and auditable for years by a small operator, so every dependency has to earn its upkeep. A static site generator was tested against this and rejected on 2026-11-04 (`docs/plans/frontend-go-no-go.md`); revisit only when a real chart cannot reasonably be hand-drawn. Which pages already read the store is tracked in `docs/plans/a4-site-from-release.md`.
- **Visitor-facing language is German only.** No English or i18n layer is planned.
- **Curated views on the site, free querying in the dataset.** The site offers edited views, and a view can have controls such as a period, a Zusammenschluss or a term from a published list. Every view is precomputed at build time from the dataset. There is no free full-text search on the site. A visitor who wants to query freely is pointed to the SQLite download.
- **No visitor feature switches.** The Baustein/gear model was removed on purpose. A section appears when the data behind it exists. When data is missing, the page says so honestly instead of hiding the gap.
- **AI summaries** are out of v1, on the site and in the release (the reference build holds none); the code stays. When they return, they are the only content preference a visitor can set. They are optional, permanently labelled `KI-generiert · nicht redaktionell geprüft`, carry 3–5 citations that each resolve to a source, and can be collapsed globally. The browser stores only that collapse preference.
- **Surfaces for v1:** the home page as the door to both angles; Aktuell (`puls.html`); Sitzungen; Abstimmungen; Gesetzesvorhaben; Abgeordnete; Analysen, once the first analysis exists; Daten. Footer: Quellen und Methode, So arbeitet der Bundestag, Impressum, Datenschutz. Decided 2026-11-06 (`docs/plans/v1-scope-review.md`): `api-sitzungen.html` and `settings.html` are cut, and Fakt der Woche is off the v1 site and out of the release until it is rebuilt to this project's quality bar. The only long-term analysis planned for the first public site is "Politikfelder over time".
- **A refused passage does not cost a whole Sitzung** (decided 2026-11-07). The Sitzung stays in with its TOPs, links and votes, and only the refused Rede, or one a review found to be wrong, is withheld, flagged with a reason and outside all Reden counts. Sitzungen brought back this way get the same merge and attribution review as the rest. A Sitzung stays out whole only with a named source defect, or a defect that cannot be narrowed to single Reden. The share withheld is published by words per Sitzung, year and Fraktion. Each analysis on the site states the minimum coverage it needs and marks a period below it as thin, not as complete (decided 2026-11-09).
- **Release stages:** (1) the data release, after a coverage gate; (2) the public site, with the daily view and one analysis, built from a release alone; (3) further analyses, each when ready.
- **Two kinds of release:** a main release is published automatically per completed Sitzungswoche, only if every check passes, and the site always reads the latest one. A stable release is one frozen main release that the owner has reviewed about every three months against a written checklist. Stable releases carry the DOI and are the ones to cite. Both stay downloadable.
- Domain vocabulary (Rede vs. Kurzintervention vs. Befragung, Sprechrolle, Abweichler, Wahlperiode, Sitzung mit Dossier, and others) is defined in `CONTEXT.md`, with decisions in `docs/adr/`. Use those definitions rather than inventing new ones.
- **Licences are decided** (ADR 0003): layered data licence (`LICENSE-DATA.md`, shipped with every export), MIT for code (`LICENSE`), and an Impressum naming a private person. The files, `impressum.html` and `datenschutz.html` are built; the Impressum values (address, e-mail, host, supervisory authority) wait on the owner and a lawyer's answer on the address, and render as marked placeholders until then.
- **Decided 2026-11-06:** the product name is open-parlament (lower case). There is one site, with shared pages for Sitzungen, Reden, Abgeordnete, Vorgänge and votes, which both angles link into. The Daten page carries downloads, citation, coverage per year, the date of the last review, the changelog and recipes; schema and codebook live in the release's `DATA.md`.
- **Open decision:** the host provider.

## Brand Commitments

- **Nonpartisan and neutral.** The site takes no editorial stance, treats all Fraktionen the same way, and ties every claim to a primary source.
- Generated content is always labelled as generated, and is never presented as editorial or verified.
- The name is open-parlament; "open" promises public code and open data, and the data's licences are layered, so say so plainly. No logo has been committed yet. The visual direction is committed: see `DESIGN.md` ("Stimmkarte", 2026-11-04). Fraktion colours stay, tuned there.

## Evidence on Hand

- Real official data. `scripts/preview_dip_pulse_site.sh demo` builds offline from a committed extract of Plenarprotokoll 21/84, TOP 32 a/b (16 Reden, Drucksachen 21/6354 and 21/4833). The largest local store (A3, 2026-10-29) holds 716 Sitzungen of WP 18–21, 18/4 to 21/103 (2013-12-17 to 2026-10-16): every Sitzung the DIP catalog lists for WP 18–21 except 85 on the reviewed exclusion list (WP 18: 51, WP 19: 33, 20/11). It has 556 namentliche Abstimmungen (619 when repersisted with the branch tip, `docs/plans/a3-merged-gate.json`), and 0 sittings are missing on a fresh catalog.
- Design plans and sketches in `docs/designs/` (`fixed-public-experience.md` with its wireframe PNG, `puls-wochenradar.md` with a sketch, `daten-page.md`, `fakt-der-woche.md`, `gesetzesvorhaben.md`).
- There are no users, testimonials, press, usage metrics or partners yet, because the product is pre-release. Do not invent any.

## Product Principles

1. **Primary source first.** Every statement, number and summary leads back to the official record in one step.
2. **Show gaps honestly.** Missing data gets a clear explanation and is never hidden or quietly skipped. Every count says which Sitzungen it covers and which units it leaves out.
3. **Curated views, free data.** The site is edited: visitors never assemble it themselves, and its structure is stable and predictable. Exploration happens inside views built for it. Free querying belongs to the dataset, not the site.
4. **Neutral by construction.** Fraktionen and MPs are treated the same way in ordering, wording and emphasis. Topic lists and term lists are published, so a reader can check that no side is framed differently.
5. **Ease for citizens, integrity for researchers, both at once.** Everything a citizen sees is simple to reach and to read. Everything a researcher relies on is consistent, documented and reproducible. A simplification may leave detail out, but it never states a figure the dataset does not support. Research depth is one click away and never clutters the citizen's path.
6. **One figure, one computation.** The site and the release compute each figure once, from the same dataset. Every figure on the site comes from one named release, shown on the page, and can be reproduced from it. Every data update of the site is a release; a rebuild that changes only code or copy keeps its release. A stable release is a main release the owner has reviewed. A change to a released figure is recorded in the next release's changelog, not silently overwritten.
