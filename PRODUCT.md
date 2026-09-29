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

- **What the Bundestag is doing now.** A place people return to for the current and recent business of the plenary: what is on the agenda today and this week, who is speaking, which laws and motions are being debated, and how the Abstimmungen came out. It favours intuition, quick facts and overviews. Every item is one click from its source. Reference for the votes part: the Abstimmungen of abgeordnetenwatch.de.
- **Long-term analysis.** Visualisations of the longer-running ties and trends in the dataset: which Zusammenschluss emphasises which Politikfelder, how much attention a topic such as Klimaschutz or Migration gets over time, how the language of the debate changes, who interrupts the flow of debate most. Reference: the Diskursanalyse of opendiscourse.de.

Both angles are to read the same dataset, so that a figure on the site is the figure a researcher gets from the release it was built from. Today only part of the site works that way (see Capabilities and Constraints).

A release succeeds when a typical visitor can do the following on desktop and on mobile:
1. Find out what the Bundestag discussed in its latest Sitzung and this week, and reach the Dossier of a Tagesordnungspunkt.
2. Find a vote, a linked Drucksache or a speaker's page, and correctly understand the missing-data message when there is none.
3. Open an analysis of a topic over time, read it correctly, and reach the Reden behind a data point.
4. Open a primary source from an AI summary, and see that the summary is generated and has not been editorially checked.

And when a researcher can download a release, cite it by version, and reproduce every figure the site shows from it.

## Positioning

The differentiator is the connection. Debate, people, legislation and votes form one path, and each item links back to the official record: protocol XML or PDF, Drucksache, roll-call publication. The daily view and the long-term analyses are built from the same dataset, so a reader can go from a trend to the Reden behind it, and from a single Sitzung to where it sits in the trend. Every figure is meant to be traceable. The published SQL recipes already run against the store at build time. Moving the rest of the site onto the same store is planned.

Comparable sites:
- **abgeordnetenwatch.de:** leads with MPs and named votes. Its Abstimmungen are the reference for the votes part of the daily view: topic tags, a plain-language description of what was decided, source documents, dissenters.
- **opendiscourse.de:** a full-text corpus of Plenarprotokolle from 1949 to 2020. Its Diskursanalyse is the reference for the long-term view. It uses 73 LDA-modelled topics with yearly granularity. This project uses published, reviewable term lists instead, so every point on a curve can be recounted from the dataset.
- **plenarwatch.de:** votes and debates from primary sources, with published counting rules at /methodik/.
- The official Parlamentsdokumentation (DIP).

## Operating Context

- Visitors read German parliamentary material: Plenarprotokolle, Tagesordnungspunkte (TOPs), Reden, Drucksachen, Vorgänge, namentliche Abstimmungen, and Fraktionen.
- Data comes from the DIP API (dip.bundestag.de), the Plenarprotokoll XML, bundestag.de roll-call publications, the DIP MdB roster, and abgeordnetenwatch.de profile data.
- Coverage for version 1 is WP 18 to the present. The protocol catalog reaches back to 1949, but only as metadata. It does not produce Dossiers.
- An operator runs the build (`scripts/preview_dip_pulse_site.sh`). Operators decide what data gets fetched and enriched. They do not decide what visitors see.
- It is currently hosted locally only. The public host is not chosen yet. Design decisions must be ones that could ship to a public audience within weeks.

## Capabilities and Constraints

- **Stack:** a Python standard-library pipeline that writes plain HTML, JSON and SQLite. There is no package manager, framework or build toolchain. Acquisition, the store and the HTML renderers still share `scripts/build_dip_pulse_site.py`. Today the Dossiers, `puls.html`, the Gesetzgebung pages and the votes archive render from per-Sitzung report JSON. Only the Abgeordnete, Fakten and Daten pages read the SQLite store. Moving every page onto the store is planned (TODOS.md, "Split the dataset from the site").
- **Visitor-facing language is German only.** No English or i18n layer is planned.
- **Curated views on the site, free querying in the dataset.** The site offers edited views, and a view can have controls such as a period, a Zusammenschluss or a term from a published list. Every view is precomputed at build time from the dataset. There is no free full-text search on the site. A visitor who wants to query freely is pointed to the SQLite download.
- **No visitor feature switches.** The Baustein/gear model was removed on purpose. A section appears when the data behind it exists. When data is missing, the page says so honestly instead of hiding the gap.
- **AI summaries** are the only content preference a visitor can set. They are optional, permanently labelled `KI-generiert · nicht redaktionell geprüft`, carry 3–5 citations that each resolve to a source, and can be collapsed globally. The browser stores only that collapse preference.
- Main surfaces today: the sitting catalog, sitting Dossiers, Puls/Wochenradar (`puls.html`), Fakt der Woche (weekly and monthly), Abgeordnete roster and profile pages, votes and the votes archive, Gesetzgebung, sources/method, and Daten (`database.html`). None of the long-term analyses exist yet.
- Domain vocabulary (Rede vs. Kurzintervention vs. Befragung, Sprechrolle, Abweichler, Wahlperiode, Sitzung mit Dossier, and others) is defined in `CONTEXT.md`, with decisions in `docs/adr/`. Use those definitions rather than inventing new ones.
- **Licences are decided** (ADR 0003): layered data licence, MIT for code, and an Impressum naming a private person. Implementing them is still open.
- **Open decisions:**
  - The product name. "Bundestag-Puls" appears in the code and README, "poliwatch" is the repo name, and IDEAS.md suggests "open-parlament". Nothing is final, so design work must not build identity around any of these names.
  - The public host.
  - The shape of the Daten page. The data release is a goal either way. Open: how much documentation the page carries itself, and how much moves into the release's codebook.
  - One site or two for the two angles. Current plan: one site with shared pages for Sitzungen, Reden, Abgeordnete, Vorgänge and votes, which both angles link into.

## Brand Commitments

- **Nonpartisan and neutral.** The site takes no editorial stance, treats all Fraktionen the same way, and ties every claim to a primary source.
- Generated content is always labelled as generated, and is never presented as editorial or verified.
- No name, logo or visual identity has been committed yet.

## Evidence on Hand

- Real official data. `scripts/preview_dip_pulse_site.sh demo` builds offline from a committed extract of Plenarprotokoll 21/84, TOP 32 a/b (16 Reden, Drucksachen 21/6354 and 21/4833). The largest local store holds 285 Sitzungen of WP 20 and 21 (2022-01-27 to 2026-06-12). WP 18 and 19 are not acquired yet.
- Design plans and sketches in `docs/designs/` (`fixed-public-experience.md` with its wireframe PNG, `puls-wochenradar.md` with a sketch, `daten-page.md`, `fakt-der-woche.md`).
- There are no users, testimonials, press, usage metrics or partners yet, because the product is pre-release. Do not invent any.

## Product Principles

1. **Primary source first.** Every statement, number and summary leads back to the official record in one step.
2. **Show gaps honestly.** Missing data gets a clear explanation and is never hidden or quietly skipped. Every count says which Sitzungen it covers.
3. **Curated views, free data.** The site is edited: visitors never assemble it themselves, and its structure is stable and predictable. Exploration happens inside views built for it. Free querying belongs to the dataset, not the site.
4. **Neutral by construction.** Fraktionen and MPs are treated the same way in ordering, wording and emphasis. Topic lists and term lists are published, so a reader can check that no side is framed differently.
5. **Ease for citizens, integrity for researchers, both at once.** Everything a citizen sees is simple to reach and to read. Everything a researcher relies on is consistent, documented and reproducible. A simplification may leave detail out, but it never states a figure the dataset does not support. Research depth is one click away and never clutters the citizen's path.
6. **One figure, one computation.** The site and the release compute each figure once, from the same dataset. A figure on the site can be reproduced from the release it was built from, and a change to a released figure is recorded, not silently overwritten.
