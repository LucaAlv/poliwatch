# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: the politically interested citizen.** They want to understand one recent Bundestag event without learning the DIP data model. Their job: find out what was debated, see the speakers, documents and votes connected to it, and check an important statement against a primary source. They visit on desktop and on mobile.

**Secondary: developers, researchers and data journalists** who want the data itself. The Daten page (`database.html`) is for them: SQLite and CSV downloads, checksums, coverage, and SQL recipes that run at build time. They come second. A design decision that helps them must not make the citizen's path harder.

## Product Purpose

The site is a static website built only from primary Bundestag sources. It covers plenary sittings, speeches, Drucksachen, roll-call votes, laws, MP pages and source links, and it shows each of these wherever validated data exists. Visitors get one fixed public product with nothing to configure.

A release succeeds when a typical visitor can do three things on desktop and on mobile:
1. Reach the latest dossier and identify its main agenda items.
2. Find a vote, linked Drucksache or speaker profile that applies to it, and correctly understand the missing-data message when there is none.
3. Open a primary source from an AI summary, and see that the summary is generated and has not been editorially checked.

## Positioning

The site's differentiator is the connected, cited dossier: debate, people, legislation and votes in one path, each linked back to the official record (protocol XML/PDF, Drucksache, roll-call publication). It does not compete on how many datasets or switches it has. Every figure can be traced: the Daten page runs its published SQL recipes against the same store the site renders from, so a researcher who downloads the file gets the same rows.

Comparable sites: plenarwatch.de (votes and debates from primary sources, with published counting rules at /methodik/), abgeordnetenwatch.de (leads with MPs and named votes), and the official Bundestag Parlamentsdokumentation.

## Operating Context

- Visitors read German parliamentary material: Plenarprotokolle, Tagesordnungspunkte (TOPs), Reden, Drucksachen, Vorgänge, namentliche Abstimmungen, and Fraktionen.
- Data comes from the DIP API (dip.bundestag.de), bundestag.de roll-call publications, the DIP MdB roster, and abgeordnetenwatch.de profile links.
- An operator runs the build (`scripts/preview_dip_pulse_site.sh`). Operators decide what data gets fetched and enriched. They do not decide what visitors see.
- It is currently hosted locally only. The public host is not chosen yet. Design decisions must be ones that could ship to a public audience within weeks.

## Capabilities and Constraints

- **Stack:** a Python standard-library pipeline that writes plain HTML, JSON and SQLite. There is no package manager, framework or build toolchain. The HTML/CSS is generated in `scripts/render_dip_pulse_html.py` and `scripts/build_dip_pulse_site.py`.
- **Visitor-facing language is German only.** No English or i18n layer is planned.
- **One fixed public experience.** There are no visitor feature switches (the Baustein/gear model was removed on purpose). A section appears when the data behind it exists. When data is missing, the page says so honestly instead of hiding the gap.
- **AI summaries** are the only content preference a visitor can set. They are optional, permanently labelled `KI-generiert · nicht redaktionell geprüft`, carry 3–5 citations that each resolve to a source, and can be collapsed globally. The browser stores only that collapse preference.
- Main surfaces today: the sitting catalog, sitting dossiers, Puls/Wochenradar (`puls.html`), Fakt der Woche (weekly and monthly), Abgeordnete roster and profile pages, votes, laws/Gesetzgebung, sources/method, and Daten (`database.html`).
- Domain vocabulary (Rede vs. Kurzintervention vs. Befragung, Sprechrolle, Abweichler, Wahlperiode, Sitzung mit Dossier, and others) is defined in a glossary. It is not on `main` yet; it lives on the `expand-database` / `fix-votes-completeness` branches. Use those definitions rather than inventing new ones.
- **Open decisions:**
  - The product name. "Bundestag-Puls" appears in the code and README, "poliwatch" is the repo name, and IDEAS.md suggests "open-parlament". Nothing is final, so design work must not build identity around any of these names.
  - The public host.
  - The data licence and attribution wording (`docs/data-license.md`, status pending).

## Brand Commitments

- **Nonpartisan and neutral.** The site takes no editorial stance, treats all Fraktionen the same way, and ties every claim to a primary source.
- Generated content is always labelled as generated, and is never presented as editorial or verified.
- No name, logo or visual identity has been committed yet.

## Evidence on Hand

- Real official data. `scripts/preview_dip_pulse_site.sh demo` builds offline from a committed extract of Plenarprotokoll 21/84, TOP 32 a/b (16 speeches, Drucksachen 21/6354 and 21/4833). A full catalog covers every plenary protocol since 1949.
- Design plans and sketches in `docs/designs/` (`fixed-public-experience.md` with its wireframe PNG, `puls-wochenradar.md` with a sketch, `daten-page.md`, `fakt-der-woche.md`).
- There are no users, testimonials, press, usage metrics or partners yet, because the product is pre-release. Do not invent any.

## Product Principles

1. **Primary source first.** Every statement, number and summary leads back to the official record in one step.
2. **Show gaps honestly.** Missing data gets a clear explanation and is never hidden or quietly skipped.
3. **One edited product, not a portal.** Visitors never assemble the product themselves. Its structure is stable and predictable.
4. **Neutral by construction.** Fraktionen and MPs are treated the same way in ordering, wording and emphasis.
5. **Readers before researchers.** The citizen's path comes first. Researchers get depth that is correct and reproducible, and it never becomes the citizen's clutter.
