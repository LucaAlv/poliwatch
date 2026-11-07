---
# gstack: design-md-format=spec
name: Stimmkarte
description: The room where the votes are counted, with the doors open. A white page, edged sheets from the record, cards you could count by hand.
colors:
  ground: "#FFFFFF"
  ground-dark: "#232427"
  slip: "#FFFFFF"
  slip-dark: "#3A3C40"
  slip-edge: "#85878C"
  slip-edge-dark: "#85878C"
  text: "#1C1E22"
  text-dark: "#F0F0EA"
  text-muted: "#4A4C52"
  text-muted-dark: "#C8C9C3"
  hairline: "#1C1E2226"
  hairline-dark: "#F0F0EA40"
  ghost-line: "#1C1E2226"
  ghost-line-dark: "#F0F0EA2E"
  vote-yes: "#2456BE"
  vote-yes-dark: "#6A8FEC"
  vote-no: "#E5604D"
  vote-no-dark: "#E25D4A"
  vote-abstain-fill: "#FFFFFF"
  vote-abstain-fill-dark: "#F0F0EA"
  vote-abstain-line: "#6E7074"
  vote-abstain-line-dark: "#F0F0EA"
  vote-absent: "#6E7074"
  vote-absent-dark: "#C8C9C3"
  fraktion-cdu-csu: "#222222"
  fraktion-cdu-csu-dark: "#C3CAD3"
  fraktion-afd: "#0B6FA3"
  fraktion-afd-dark: "#2A9FD6"
  fraktion-spd: "#B5121E"
  fraktion-spd-dark: "#EE5560"
  fraktion-gruene: "#087A58"
  fraktion-gruene-dark: "#2FAE74"
  fraktion-linke: "#A81A86"
  fraktion-linke-dark: "#DE5CC0"
  fraktion-fdp: "#866A00"
  fraktion-fdp-dark: "#B09A00"
  fraktion-bsw: "#6F3BB0"
  fraktion-bsw-dark: "#A77CF0"
  fraktion-none: "#4A4C52"
  fraktion-none-dark: "#C8C9C3"
typography:
  display:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: clamp(3rem, 9vw, 4.5rem)
    lineHeight: 0.95
  heading-1:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 600
    fontSize: clamp(1.75rem, 4.2vw, 2.625rem)
    lineHeight: 1.18
    letterSpacing: -0.01em
  heading-2:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 600
    fontSize: clamp(1.3125rem, 2.6vw, 1.625rem)
    lineHeight: 1.18
    letterSpacing: -0.01em
  heading-3:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 600
    fontSize: 1.125rem
    lineHeight: 1.18
  nav:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 500
    fontSize: 1rem
    lineHeight: 1
  name:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 600
    fontSize: 1rem
    lineHeight: 1.1
  name-large:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 600
    fontSize: 1.3rem
    lineHeight: 1.15
  title:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 600
    fontSize: clamp(1.3rem, 2.88vw, 2.1rem)
    lineHeight: 1.18
  body:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 400
    fontSize: 1.0625rem
    lineHeight: 1.6
  note:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 400
    fontSize: 0.9375rem
    lineHeight: 1.6
  figure-lead:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: clamp(2.5rem, 5vw, 3.5rem)
    lineHeight: 0.95
  figure-row:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: clamp(1.875rem, 3.6vw, 2.5rem)
    lineHeight: 1
  figure:
    fontFamily: Atkinson Hyperlegible Mono
    fontWeight: 400
    fontSize: 1rem
  figure-small:
    fontFamily: Atkinson Hyperlegible Mono
    fontWeight: 400
    fontSize: 0.875rem
    lineHeight: 1.35
  reference:
    fontFamily: Atkinson Hyperlegible Mono
    fontWeight: 400
    fontSize: 1rem
rounded:
  card: 1px
  slip: 1px
  control: 2px
spacing:
  xs: 4px
  sm: 8px
  md: 12px
  lg: 16px
  xl: 24px
  2xl: 32px
  3xl: 48px
  4xl: 72px
  target: 44px
components:
  slip:
    backgroundColor: "{colors.slip}"
    textColor: "{colors.text}"
    rounded: "{rounded.slip}"
    padding: "{spacing.xl}"
  vote-card-yes:
    backgroundColor: "{colors.vote-yes}"
    rounded: "{rounded.card}"
    width: 7px
    height: 13px
  vote-card-no:
    backgroundColor: "{colors.vote-no}"
    rounded: "{rounded.card}"
    width: 7px
    height: 13px
  vote-card-abstain:
    backgroundColor: "{colors.vote-abstain-fill}"
    rounded: "{rounded.card}"
    width: 7px
    height: 13px
  vote-card-absent:
    backgroundColor: "{colors.vote-absent}"
    rounded: "{rounded.card}"
    width: 7px
    height: 5px
  strip:
    backgroundColor: "{colors.slip}"
    height: 14px
  control:
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    height: 44px
---

# Stimmkarte

The v1 surfaces, navigation and name here follow the owner's decisions of 2026-11-06 (`docs/plans/v1-scope-review.md`, commit cc0b0f7).

## Overview

**Creative North Star:** the room where the votes are counted, with the doors open. Nothing sells or persuades, and nothing stands between the reader and the record; the visitor is invited to count it themselves.

**The one thing to remember:** every figure here traces back to the official record. Every decision below serves that sentence.

**Open means the frame recedes and the evidence stays in sight.** The page is light, with few lines, headings of ordinary weight, and space where a rule would otherwise go. This is not minimalism for its own sake: never fold or remove a source, a count, a gap, the release or the data's age to make a page look cleaner. Take away what surrounds the record, never the record.

**Product context:** open-parlament is a nonpartisan German site and citable dataset built from the Bundestag's official record. "Stimmkarte" names this design system, never the product. Citizens want to know what the Bundestag is doing now, often on a phone. Researchers and journalists need figures they can check. Peers are abgeordnetenwatch.de (campaign feel, photo cards, donuts), bundestag.de (institutional card grid, donuts), plenarwatch.de (quiet minimal lists) and opendiscourse.de (template look).

**Mode per surface:**
- Door: the home page. It sends the visitor to one of the two angles.
- Return: Aktuell. The visitor comes back to see what happened and leaves again.
- Operate: Sitzungen, Abstimmungen, Gesetzesvorhaben, Abgeordnete, filters, Daten.
- Read: dossiers, speeches, Analysen, Quellen und Methode, So arbeitet der Bundestag.
- No Persuade or Experience surfaces exist.

**Return mode rules.** A person page or a dossier can wait; a return visit takes seconds.
- The first screen of Aktuell at 375 px answers four things: how old the record is (the Stand line), whether an update is overdue (a thin gap in the same place if so), the next planned Sitzungswoche, and the largest item of the latest Sitzungswoche, Sitzung and vote.
- Same order and same places on every visit, so memory of the page works. Newest first, with the date at the front of the row.
- Lead figures in `figure-lead`, with their label on the same line or directly below.
- The site stores nothing about a visit, so there is no "neu" badge. The date does that work.
- No disclosure hides a first-screen answer. A source line may stay folded.
- The newest vote always stands on the page, as a Vote lead below the next planned Sitzungswoche. A week without a roll call says so and still shows it, with its older date.

**Aktuell never promises today.** A sitting appears once its Sitzungswoche is complete and its protocol is out, up to 6 days later (a Wednesday sitting shows the next Tuesday). No source gives anything newer. "Aktuell" is only the link's name. The page's heading names the period ("Letzte Sitzungswoche: KW 37/2026"), and no visitor-facing line about the data uses "heute", "gerade", "jetzt", "läuft" or "bisher". One sentence on the page gives the delay: "Eine Sitzung erscheint hier, wenn ihre Sitzungswoche abgeschlossen und das Protokoll veröffentlicht ist, üblicherweise bis zu 6 Tage danach." "Üblicherweise", because 6 days assumes the release ran on time. The sentence stands below the first-screen answers, since it explains them and answers nothing itself.

**Reference sites:** https://www.abgeordnetenwatch.de/bundestag/abstimmungen, https://plenarwatch.de, https://opendiscourse.de, https://www.bundestag.de/parlament/plenum/abstimmung

**Key characteristics:**
- A vote is shown as one card per member, so absences are visible.
- An edged sheet means the source prints it; the open page means this site worked it out.
- A short line connects a figure to the slip holding its source, and the slip opens by naming that source.
- References are set at reading size in full ink, never as grey small print.
- No photos, donuts, icons in tiles or a box around everything.

## Colors

**Strategy:** Restrained, with no brand colour. Colour only ever carries data, in two families told apart by shape.

**Votes use the Bundestag's own ballot colours.** [Members vote with blue, red and white cards](https://www.bundestag.de/services/glossar/nam_abst-245502), so this colour has a source. A vote is always a card. Enthaltung is a white card with an outline in `vote-abstain-line`, 1.5px, or 1px at the phone card size so a 5px card keeps its white. "Nicht abgegeben" is a low stub in `vote-absent`, so a missing vote reads as a gap.

**Vote colours need a light surface.** Cards and key swatches on a vote's page sit on the slip, because a member's vote is the record. In a list the strip sits directly on the page, since Nein reaches 3.44:1 on #FFFFFF. It would miss 3:1 below about #F1F1ED, and the strip would then need its slip back.

**A card shows the ballot, never its meaning.** Blue is Ja on every vote. On a vote where a Ja means "gegen den Antrag" (`inverted`), the colours stay and the words change: see Vote wall.

**Fraktionen keep their conventional colours,** because most readers already link them to the parties. A Fraktion's colour appears only on a tick, a line or the small bar beside its name, and always with the name. Shape separates the families: **a card is a vote; a tick or line is a Fraktion.** The two never share a mark. Controls carry no Fraktion colour: a pressed filter would hide it.

**No Fraktion colour for anything that is not a Fraktion.** fraktionslos, Bundesregierung, Bundesrat and other roles use `fraktion-none`. Gruppe Die Linke uses the Linke colour and Gruppe BSW the BSW colour. Older Fraktionen and Gruppen get a colour here before a page shows them.

**Fraktion colours are variables, never inline hex.** Each colour is a custom property per mode (`--f-spd`). A mark takes it through one class on its row (`f-spd`, which sets `--c`), so the renderer writes a class name and never a value. Every name resolves to a slug in one map; anything unmapped takes `f-none`.

**Surfaces carry provenance.**
- `slip`: what the source prints: speech text, member votes, document references, the totals and per-Fraktion counts on the Bundestag's roll-call page, the MdB-Stammdaten, a verbatim sentence.
- `ground`: what this site worked out: the derived "angenommen", shares and percentages, Rede counts, Mehrheitsvotum and Abweichungen, "für" and "gegen" on an inverted vote, and rankings.
- A list or table is the site's arrangement, so it sits on the ground. A cell that repeats a source figure there is still ground, and so are the strip and its counts. The vote's own page holds the slip.
- A figure the site corrected is no longer as printed. A count re-filed from the MdB-Stammdaten stays in its row and says so in words, with both numbers and the source.
- Headings and navigation carry no provenance. A heading sits with the content it introduces.

**The surface never carries provenance alone.** In light mode slip and ground are the same white (1.00:1), and in dark mode they differ by 1.40:1, so on the light page the sheet is told apart by its edge alone. Three cues are binding on every slip: the `slip-edge` line (3:1 or better against the ground in both modes), the source line leading to it, and the named source at its top (see Origin line). The footer of every page states the rule in words.

**Light or dark:** dark is a chosen pair of values, not an inversion, and the slip is never darker than the ground. The site follows the saved choice first (`bundestag-pulse-theme`), then `prefers-color-scheme`, and is light when neither says dark. The toggle stays.

**Interaction has no colour.** Links are ink with a 1px underline in `slip-edge`, which turns ink and 2px on hover. Focus is a 2px ink outline with a 2px offset. Selection inverts ink and ground. Visited links look the same as unvisited ones, which keeps source lists calm.

**Measured limits** (WCAG contrast computed from these values; colour-blind separation from the dataviz validator, all-pairs mode, re-run 2026-11-06):
- All text pairs reach 4.5:1 or better on ground and slip (lowest: muted text on the dark slip, 6.6:1).
- All Fraktion colours reach 3:1 on both surfaces in both modes (lowest: FDP 5.15:1 on the light page, SPD 3.21:1 on the dark slip).
- Vote colours reach 3:1 on the slip in both modes (lowest: Nein 3.44:1 light, 3.10:1 dark). On the ground Nein reaches 3.44:1 in light mode and 4.36:1 in dark mode, so the list strip can sit on the page in both.
- `slip-edge` reaches 3.59:1 on the light page and sheet; 4.32:1 and 3.07:1 in dark mode.
- Fraktion hues do **not** pass colour-blind separation. The worst pairs are SPD and FDP in light mode and BSW and AfD in dark mode (both ΔE 3.7, deuteranopia; tritanopia worst 2.6 and 2.8). Some pairs also miss the full-vision floor of 15 (Grüne and FDP 13.3 in light mode, BSW and Linke 12.4 in dark mode). Red against green cannot be fixed while keeping the conventional colours.
- Outside the validator's bands: CDU/CSU on purpose, in both modes, because it is conventionally black (light 0.252, dark 0.836, chroma near zero). Linke, FDP and BSW in dark mode sit just above the lightness band (0.672 to 0.685 against 0.67), and contrast still passes.
- Ja and Nein differ clearly in hue, with lightness contrast of 1.94:1 in light mode and only 1.14:1 in dark mode. Someone who sees no hue relies on the grouping and the printed counts.
- SPD and Nein, and AfD and Ja, sit close together. The AfD hue leans cyan and SPD is a deeper red to keep them apart, but the shape rule does the real work.

These limits are why the rules under Do's and Don'ts are binding, not advice.

## Typography

**Atkinson Hyperlegible Next** carries headings and names at weight 600, the navigation at 500, and all reading and interface text at 400. It was chosen because the site serves every citizen, and its open letterforms read as plain speech. Body text uses `hyphens: auto` with `lang="de"`.

**D-DIN Condensed Bold** is kept for what the record says loudest: the verdict and lead figures, and nothing else. It comes from the DIN lettering of German road signs and other public signage. Because it is rare on a page, a number or an outcome is the first thing the eye finds.

**Long words and long titles.** Text this site writes takes soft hyphens at word joints (`Asylverfahrens&shy;beschleunigungs&shy;gesetz`) with `hyphens: manual`. Titles from DIP arrive without them, so they take `hyphens: auto` with `overflow-wrap: anywhere` as the floor, and no line overflows at 375 px. An official title longer than about 140 characters is set in `body`, not in a heading. On a list it clamps to four lines; on its own page it is never cut.

**Atkinson Hyperlegible Mono** sets figures and source references at reading size, in full ink. Its slashed zero keeps numbers unambiguous. It is not used for small tracked labels. A figure in a column of figures stays mono, so digits line up. A single lead figure takes `figure-lead` or `figure-row` in D-DIN, because the mono at display size reads as a typewriter and its slashed zero turns into a blot.

**Loading:** self-hosted WOFF2 with `font-display: swap`, about 95 KB for all five files. Nothing loads from another host, which is what the Datenschutz page promises. All three families are under the SIL Open Font License 1.1; ship the licence texts with the files. D-DIN has Reserved Font Names, so serve Datto's files unmodified and do not subset them under that name. Sources: Datto's D-DIN WOFF2 files and the `@fontsource-variable/atkinson-hyperlegible-next` and `@fontsource/atkinson-hyperlegible-mono` packages.

The `display` size is for the single verdict of a detail page. It stops at 4.5rem so the evidence below it still starts on the first screen.

## Layout

Strict grid, left-aligned, maximum content width 1120px, with a 16px gutter at phone width. Running text stays within about 68 characters; data may take the full width. A slip holding running text hugs that measure instead of leaving a white field beside it.

Grouping comes from whitespace first: 72px between sections, 32px at phone width. A hairline separates items and rows, and one line in `text-muted` stays under a table's header. A box must mean something: a slip is the record, and a dashed box is a gap.

Fraktionen always appear in the same order within a view, by size in that Wahlperiode, never by a rank that changes per row unless the row is itself a ranking.

**Page head.** Back link if there is a parent, then `heading-1`, then the Stand line, then the Zitieren line where a page takes it there, then a thin gap if a release is overdue. A back link is navigation, not a kicker, and nothing else stands above the heading.

**Stand line.** On every page that shows a figure from the dataset, in `note` size and the body face, with `text-muted`. It holds three things in this order: the page's main release, linked to its entry on Daten; the newest Sitzung in that release with its date; and the data's age ("Release 2026-09-15 · neueste Sitzung 21/94 vom 11.09.2026 (vor 56 Tagen)"). The identifier format is not decided, so that is only an example. Nothing else goes in this line, because a fourth item takes it to four lines on a phone. A dossier or vote names its release, and its protocol's own date stands with the protocol.

**Age and overdue are worked out in the browser.** Pages are rebuilt only with a release, so an age written at build time freezes exactly when an update fails. The HTML carries the Sitzung's date in `<time datetime>` and the date the next release is due; a few lines of script add the age and reveal the gap. Without script the date still stands.

| Situation | What the reader sees |
|-----------|----------------------|
| Sitting within the usual delay | No gap; the one sentence on Aktuell explains it |
| Recess, no sitting for weeks | No gap; "Nächste geplante Sitzungswoche" with its dates |
| Release past its due date | Thin gap "Nicht aktuell", saying which release is missing and since when |

Age alone never says "Nicht aktuell", since a summer recess is not a fault.

**Zitieren line.** Pages show the main release and citations should name stable, so a page holding citable figures says how the two relate. It stands on vote, Sitzung, person and analysis pages, on the ground, in `note` size and full ink, with "Zitieren:" at weight 600 and a link to the citation on Daten. It is its own line, because the Stand line is full. It follows the Stand line, except on a vote's page, where it stands directly under the slip: the verdict's head must leave the evidence on the first screen, and a reader who wants to cite ends at the sources anyway.

| Situation | The line says |
|-----------|---------------|
| The record is in stable and unchanged | "Diese Abstimmung steht unverändert im stabilen Stand 2026-08-04." |
| The record is in stable and corrected since | "Diese Abstimmung steht im stabilen Stand 2026-08-04, wurde seitdem aber korrigiert." It links to the entry under Changes |
| The record is not yet in stable | "Diese Abstimmung ist noch nicht im stabilen Stand 2026-08-04. Zitierbar ist der laufende Stand 2026-09-15." |
| Counts over many Sitzungen (person, analysis) | "Diese Zählungen reichen bis Sitzung 21/94, der stabile Stand 2026-08-04 bis Sitzung 21/90." |
| The latest main release is itself stable | "Der laufende Stand 2026-09-15 ist zugleich der stabile." |

- "In stable" never stands alone, because a reader takes it to mean the same figure. "Unverändert" may only be printed where the build compared the record with the stable release. A page of counts over many Sitzungen gets no yes or no, only how far each release reaches.
- The line is written at build time, and marking a release as stable changes it. So marking a release as stable rebuilds the pages, which under principle 6 keeps their release.

**Below 760px** the layout changes rather than stacks:
- Navigation wraps to two rows (see Navigation).
- Vote rows stack with the name above the cards, and cards shrink to 5 by 10 px, so a 630-member vote stays on a phone screen. The largest vote in the store has 736 members (WP 20) and has not been measured; check it when applying.
- List rows put the strip below the title, at full width.
- A table with a column it can spare moves it under the row's name (Fraktion on the roster), and a table that cannot spare one scrolls inside its own focusable region.
- A figure and its label share a line.

Between 760 and 1000px, small multiples take two columns.

## Elevation & Depth

Flat. A slip sits on the ground with its 1px `slip-edge` line and nothing else. No blur shadows, no glow and no frosted surfaces. Sticky elements use a solid background.

## Shapes

Nearly square, like paper and cards: 1px on cards and slips, 2px on controls. Pills are not part of this system, including for filters.

## Components

**Header.** The product name, `open-parlament`, as plain text in `heading-3` on the left, linked to the home page, the theme control as plain text on the right, and the navigation below, with space and no rule beneath. The name is always lower case, also at the start of a sentence, and never breaks at its hyphen: `white-space: nowrap` on a span, not a non-breaking hyphen character, which would break search and copied citations. No logo yet. The header does not stick. A skip link is the first focusable element on every page.

**Navigation.** Seven text links in `nav`, in this order at every width: Aktuell, Sitzungen, Abstimmungen, Gesetzesvorhaben, Abgeordnete, Analysen, Daten. Analysen appears once the first analysis exists. Each link is a full target; the current page has a 2px ink underline. No pills or boxes. Nothing is hidden behind a menu, because Analysen is one of the two equal angles and hidden destinations are what today's nav gets wrong. The row simply wraps. Below 760px the links take `0.9375rem` with -0.01em tracking and a 4px gap, which measures two rows at 375 and 360 px and three at 320 px, with no overflow. From 761 px they fit one row. No hamburger, no "Mehr".

**Footer.** A hairline, the provenance key in words ("Blatt mit Rand: steht so in der Quelle, die das Blatt oben nennt. Offene Fläche: von dieser Website berechnet oder zusammengestellt."), then the data note and four links, each a full target: Quellen und Methode, So arbeitet der Bundestag, Impressum, Datenschutz.

**Home.** The door to both angles, which are weighted equally. `heading-1`, the Stand line, then two doors of the same form, Aktuell and then Analysen: a hairline, a heading link with the normal underline, one sentence, and one piece of what stands behind the door.
- **Aktuell door.** The newest vote as a Vote lead, since the card is what the site is about.
- **Analysen door.** The lead question of an analysis, then one small panel per Fraktion on a shared axis, each with its name and latest value as text, and one line naming the measure. All of them, because one Fraktion alone would pick a side on the home page, and overlaying them is ruled out. This is a reduced form of small multiples, whose full panels and table stand on the analysis page.
- **Layout.** Two columns from 761 px, stacked below. At 375 by 667 px the first door ends at 610 px and the second's heading stands at the bottom of the first screen, from 631 to 675 px; at 360 by 640 px only its hairline does. Only the overdue gap may push it lower.

The public site ships with its first analysis (stage 2); a build before that shows a Gap in the second door, and no Analysen link. Below them "Zuletzt": the latest Sitzungswoche and Sitzung as date-first rows, then the next planned Sitzungswoche, then a link to the dataset. No third door and no list of all areas, since the navigation already is that list.

**Verdict.** On a vote's page: `display` for the outcome word, then the official title, the date and Sitzung, and a note saying the outcome is computed where it is. All of this is ground. The source line leads from here to the slip, which opens with its origin line, then the totals in `figure-row`. On an inverted vote the verdict names the Antrag ("Antrag abgelehnt", from `derive.vote_outcome`), never the bare result of the recommendation.

**Vote wall.** One card per member, grouped into rows by Fraktion, sorted within a row by Ja, Nein, Enthaltung, nicht abgegeben. Beside each row are the Fraktion's name and the counts the source prints. The stored counts (`vote_fractions`, and `vote_members.party_id` for the cards) are the ones after re-filing, which differ from the page on 55 roll-calls (E4), so a row must not present them as printed without checking. Where a Stimme moved into or out of the row (`vote_members.listed_party_id` is set), the row follows the rule under Surfaces: the stored count is the corrected number, and the printed one is the number of `vote_members` rows under `COALESCE(listed_party_id, party_id)`. A key is always visible, with the ballot-card explanation. Detail pages only; lists use the strip. If member rows are incomplete, say so and show the counts, never a partial wall presented as whole.
- **As text.** Cards are `aria-hidden` and have no `title`, which neither touch nor screen readers receive reliably. Below the key, each Fraktion has a `<details>` ("CDU/CSU: alle 208 Stimmen als Text") listing its members under Ja, Nein, Enthaltung and nicht abgegeben, with counts. Browser search finds a name.
- **Inverted vote.** On the ground, directly under the title, a sentence states what was voted on and "Ja heißt hier: gegen den Antrag", and one line names who was for and against. On the slip, the sentence the reading rests on comes first, verbatim (`inversion_excerpt`), under its own origin line ("Quelle dieses Satzes:", from `inversion_source`); where that is only the title on the roll-call page, it says so. The counts follow under theirs. The key reads "Ja (hier: gegen den Antrag)". The source's counts and colours do not change. An inverted vote belongs in the tests.
- **One person's votes.** The same cards in one row per person, one card per vote, oldest first, with the same key and a table as text.

**Strip.** The list form of a vote: a small white bar with a 1px `slip-edge` line, 14px high, directly on the page with no box around it, holding one segment per vote kind in proportion, in the same fills as the cards, with "nicht abgegeben" as a lower stub. Its counts follow in `figure-small`, in words. On an inverted vote a bold line below says "Ja heißt hier: gegen den Antrag." A key opens the list once, also without a box. The strip is `aria-hidden`; the counts carry it.

**Vote lead.** The newest vote where a visitor arrives, on Home and Aktuell, on the ground: the label and date ("Letzte namentliche Abstimmung: 12.06.2026"), the verdict in D-DIN at `figure-row` size, the official title as a 44px link to the vote's page, clamped to two lines, then the strip and its counts. The date always stands first, because the newest vote can be months older than the last Sitzungswoche. The verdict comes from `derive.vote_outcome`, so an inverted vote reads "Antrag abgelehnt", with the strip's bold line below it. If no vote exists, a Gap takes its place.

**Tally.** One tick per Rede, gathered in fives, in the Fraktion's colour, followed by the count as text and preceded by the name. Long periods use one tick per ten, with that scale printed in the row. Single ticks are not tap targets. Rows wrap at phone width in the same Fraktion order.

**Share line.** A horizontal line whose length is the value, with the name and the value as text beside it: 2px in `text-muted` for a neutral share such as a Tagesordnungspunkt's Reden, 4px in the Fraktion's colour for a Fraktion's share. Never stacked, because a segment would then rely on colour alone.

**Source line (Beleg).** A 1px `slip-edge` line, 24px long, runs from a figure to a slip containing the reference (for example "Plenarprotokoll 21/84, S. 10276 D", linked) and, where available, the verbatim sentence. On lists it is a `<details>`, which needs no script; its summary keeps a visible marker, because without one it reads as plain text. Link text must name the source. When the source has no page number, name the protocol and say so.

**Origin line.** The first line inside a slip says where the sheet comes from: "Quelle:" in `note` at weight 600, then the named reference in `reference`, in full ink ("Quelle: bundestag.de, Abstimmung 1009"). On white the edge is the sheet's only visual mark, so the words do the work. It is a 44px target like any reference on a slip.
- **It names what the rows were read from.** A renderer writes the source it actually used, never a default. A person page reads two sources: Funktion and Wahlperioden come from DIP, and Geburtsjahr, Beruf, Bundesland and Wahlkreis come from abgeordnetenwatch.de. Each gets its own line under the next rule. A link to a profile that supplied no row stands under the slip on the ground, since it is not the sheet's source.
- **Two sources, two lines.** Each part of a sheet opens with its own line.
- **Many references.** Where each row carries its own reference, the line names the kind and says so, without a link ("Quelle: Plenarprotokolle des Bundestages, bei jeder Rede genannt").
- **The exception.** A slip holding only its reference, as in a list's Beleg, is already that line and needs no second one.
- A corrected count still says so in its row. The line names the source, and it does not promise that every figure stands there unchanged.

**Gap.** A dashed 1px box in `slip-edge` with a short title and the reason in words, on the ground. It looks like an empty place in the file, not an error. Empty states are required on every data view, each with what is missing, why, and a way back where there is one. The thin form states staleness in the page head and does not move between visits.

| Situation | What the reader sees |
|-----------|----------------------|
| Data not fetched | Gap: "Nicht verfügbar" and the reason |
| Period has none | Gap: "Keine in dieser Woche" and what was covered |
| Filter matches nothing | Gap with a link that clears the filter; the result count says 0 |
| Release overdue | Thin gap in the page head: "Nicht aktuell" (see Stand line) |
| Member rows missing | Totals on the slip, a gap instead of the wall |
| Search without script | Full list and a note pointing to browser search |
| Pages are static | No loading state, except the result count after a filter, which is `aria-live` |

**Not in v1.** AI summaries and their collapse control. When they return they sit on the ground, never on a slip, under the permanent mono label "KI-generiert · nicht redaktionell geprüft", and need checking against a real summary, since this form has only been seen empty. Fakt der Woche is also off the v1 site and gets its design when it is rebuilt.

**Lists.** Rows on the ground, separated by hairlines. Date first, in mono. A list over about 50 rows groups by period, with the period as `heading-2`. Long lists rely on filters, not paging. Sitzungen also lists the Sitzungen left out of the record, with number, date and reason, inside a `<details>`.

**Tables.** Rows on the ground (or on a slip when every cell stands in the source), hairlines between rows, a 1px `text-muted` line under a sticky solid-background header. Numbers right-aligned in mono, text left-aligned, row headers marked `scope="row"`. A wide table scrolls inside a focusable region, never the page.

**Small multiples.** One panel per Fraktion on a shared axis: a 2px line in the Fraktion's colour, the others as 1px neutral ghost lines, the latest value labelled directly, the name in the panel title. Crosshair and tooltip on hover or touch, plus a table of all values below. Figures are aggregated in Python before they reach a chart.

**Reading a speech.** One slip per Rede, hugging the measure: the origin line with protocol and page, name in `name-large` with the Fraktion bar, paragraphs in `body`. A Zwischenfrage or Kurzintervention stays inside the Rede, indented between hairlines under a small heading saying what it is and who asked, with a note that it is not counted as a Rede. Above the slips, a list of the speakers in order, each a full target with Fraktion and page. Never a box inside the slip.

**Controls.** 44px minimum height at every width, 1px `slip-edge` outline (3.59:1), no fill, no colour, pressed state inverted. Every control has hover, focus-visible, pressed and disabled states; disabled uses the muted colour with a dashed outline and is never low-contrast text carrying needed information. One primary form exists, filled ink, for the single main action of a page such as a download.
- **Targets.** A link alone on its line is a 44px target at phone width: nav links, source lists, list actions, a row's title, a reference on a slip, any link that is the only thing in its paragraph. Where the row must not grow, the link takes 11px of padding and the same negative margin. A link inside a sentence is not a target.
- **Filters.** Up to six options are a row of buttons, seven or more a native `<select>`, at every width, so 23 buttons never stack above a list. Every field has a visible label, never a placeholder alone. A field is a control, not a slip, so it has no white fill.

**Code and downloads.** SQL sits on the ground between hairlines, in mono at note size, and scrolls inside a focusable region. A checksum is mono and wraps anywhere. A file's size and format stand beside its link.

**Daten.** On the ground, since this is the site's own product, in this order: the Stand line, one sentence, the two releases, why they differ, citation, coverage per year, changes, recipes, and a link to `DATA.md`, which holds schema and codebook.
- **Two releases.** Side by side from 761 px, stacked below, in the same form: heading, identifier in mono, one sentence, SQLite download, CSV control, checksum. The CSV control is an outline control on both releases, with the number of files and their total size in its label. It is a `<details>` that opens the list of files in place, each with its size and a 44px link. "Stabiler Stand" with `stable` beside it comes first and takes the page's one primary control, because citations should name it, and its sentence gives the last date it was reviewed by hand. "Laufender Stand" with `main` beside it takes the outline control, and its sentence says it passed every automatic check and that the site always shows it. Where the latest main release is itself the stable one, the sentence says so. No wording may suggest main is unchecked: a failed check publishes nothing.
- **Why they differ.** One visible sentence directly below both: main holds newer Sitzungen and corrections, and stable was also reviewed by hand and stays frozen, so a cited figure can be checked.
- **Citation.** The code form, but it wraps instead of scrolling, because it is copied whole. It names the stable release and its DOI. One note below gives the form for a single vote or Sitzung, and says a Sitzung not yet in stable is cited by the main release and its date, since every main release is kept.
- **Coverage per year.** A table, newest year first: year, Sitzungen in the record, Sitzungen left out, with a link to Sitzungen for the reasons. No chart: nobody compares these values by eye.
- **Changes.** A list with the date first, then `main` or `stable`, then one line. A moved figure gives its old and new value.
- **Recipes.** One `<details>` each, holding the SQL and its result table.

## Accessibility

Landmarks on every page (`header`, `nav` with a label, `main`, `footer`) and a skip link. `lang="de"`. Cards, strips and ticks are `aria-hidden` and always have text beside them or a text list below. Charts have `role="img"`, a label pointing to their table, and the table. Disclosures are `<details>`. Scrolling regions take `tabindex="0"`. Under forced colours, cards keep their fills (`forced-color-adjust: none`) and the printed counts carry the rest.

## Do's and Don'ts

- Do show every Fraktion colour with the Fraktion's name beside it. Colour never identifies a Fraktion alone.
- Do facet Fraktionen into panels or rows, with a table view for every chart.
- Do put a source line on every figure a reader might cite.
- Do open every slip with its origin line, unless the slip holds only its reference.
- Do say on a page of citable figures how it relates to the stable release, and never print "unverändert" without having compared.
- Do show gaps in words, with the reason.
- Do take away lines, weight and boxes before anything a reader could check.
- Do run the dataviz validator when adding a Fraktion colour, and record the result here.
- Don't draw a vote as anything but a card, or a Fraktion as a card.
- Don't change a card's colour for what the vote means.
- Don't put a vote colour on a light ground darker than about #F1F1ED without a slip under it.
- Don't overlay several Fraktion lines in one plot, or use donuts or stacked bars where colour alone tells the segments apart. The strip is proportional but its segments differ in shape and carry printed counts.
- Don't colour text with a Fraktion or vote colour; marks carry colour, text stays ink.
- Don't put computed figures or generated text on a slip. A count the source prints is not computed. A re-filed count is the one exception, and it says so in its row.
- Don't use photos, icon tiles, kickers above headings, pills, nested boxes or a brand accent colour.
- Don't make anything a tap target below 44px, except a link inside a sentence.

## Motion

- **Approach:** minimal-functional.
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50-100ms) short(150ms for a slip unfolding)
- **The one authored moment:** a source slip unfolding in place. It is off under `prefers-reduced-motion`.

## Held Open Until the Reader Test

Five outside readers test the finished site just before launch (decision Q16), and the ground and the vote wall may change then. Build so that this costs little:
- **Ground.** The value lives only in `--ground`, and likewise `--slip` and `--edge`. No hex in renderers, inline styles or SVG, and no test pins a value. If it moves, re-measure Measured limits. On the light ground, with the white slip and the `slip-edge` above, the values to expect are:

| Ground | Slip step | Edge | Nein | Lowest Fraktion |
|--------|-----------|------|------|-----------------|
| #FFFFFF | 1.00 | 3.59 | 3.44 | 5.15 |
| #F7F7F3 | 1.07 | 3.35 | 3.20 | 4.80 |
| #EFEFEA | 1.15 | 3.12 | 2.98 | 4.47 |
| #E6E6E1 | 1.25 | 2.87 | 2.74 | 4.12 |

Below about #F1F1ED the strip needs its slip back, and below about #EBEBE6 `slip-edge` must darken to stay at 3:1.

- **Vote wall.** One render function, with card geometry only in `--cw`, `--ch`, `--cg` and `--enth-w` and fills only in `--v-*`. Tests assert the counts and the text lists, not card sizes. A vote page must stay complete without the cards: the printed counts and the text per Fraktion already carry it, so replacing the wall changes one function.

## Component Inventory

For the one shared stylesheet. Values come from the front matter; the classes are the ones the preview uses (`~/.gstack/projects/LucaAlv-poliwatch/designs/design-system-20261104/build_preview_v2.py`, which holds the working CSS).

```css
:root {
  color-scheme: light;
  --ground: #FFFFFF; --slip: #FFFFFF; --edge: #85878C;
  --ink: #1C1E22; --ink-2: #4A4C52; --hair: #1C1E2226; --ghost: #1C1E2226;
  --v-ja: #2456BE; --v-nein: #E5604D; --v-enth-fill: #FFFFFF; --v-enth-line: #6E7074; --v-abs: #6E7074;
  --f-cdu: #222222; --f-afd: #0B6FA3; --f-spd: #B5121E; --f-gruene: #087A58;
  --f-linke: #A81A86; --f-fdp: #866A00; --f-bsw: #6F3BB0; --f-none: var(--ink-2);
  --display: "D-DIN Condensed", "Arial Narrow", sans-serif;
  --body: "Atkinson Next", Verdana, sans-serif;
  --mono: "Atkinson Mono", ui-monospace, monospace;
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px; --s6: 32px; --s7: 48px; --s8: 72px;
  --target: 44px;
  --cw: 7px; --ch: 13px; --cg: 2px; --enth-w: 1.5px;
}
/* The same block under both selectors: the first serves readers without script. */
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { /* dark values */ } }
:root[data-theme="dark"] {
  color-scheme: dark;
  --ground: #232427; --slip: #3A3C40; --edge: #85878C;
  --ink: #F0F0EA; --ink-2: #C8C9C3; --hair: #F0F0EA40; --ghost: #F0F0EA2E;
  --v-ja: #6A8FEC; --v-nein: #E25D4A; --v-enth-fill: #F0F0EA; --v-enth-line: #F0F0EA; --v-abs: #C8C9C3;
  --f-cdu: #C3CAD3; --f-afd: #2A9FD6; --f-spd: #EE5560; --f-gruene: #2FAE74;
  --f-linke: #DE5CC0; --f-fdp: #B09A00; --f-bsw: #A77CF0;
}
@media (max-width: 760px) { :root { --cw: 5px; --ch: 10px; --cg: 1.5px; --enth-w: 1px; } }
.f-cdu { --c: var(--f-cdu); } /* one per Fraktion; .f-none { --c: var(--f-none); } */
```

| Component | Class | Surface | Tokens | Notes |
|-----------|-------|---------|--------|-------|
| Header | `.site`, `.brand`, `.skip` | ground | `heading-3`, no rule | Not sticky; skip link first |
| Navigation | `.site-nav` | ground | `nav`, `--target`, 2px current underline | Wraps; `0.9375rem`, -0.01em and 4px gap below 760px |
| Footer | `.site-foot`, `.prov`, `.foot-nav` | ground | `note`, `--target`, `--hair` | Carries the provenance key |
| Door | `.doors`, `.door`, `.door-what`, `.door-lead` | ground | `heading-2`, `body`, `name`, `--hair` | Home only; one column below 760px |
| Door panels | `.sparks`, `.spark` | ground | 2px `--c`, 24px high, `figure-small` | 3 columns at every width; name and value as text |
| Vote lead | `.vote-lead`, `.vote-lead-verdict`, `.vote-lead-title`, `.vote-lead-count` | ground | `figure-row` in D-DIN, `note`, `figure-small`, `--target` | Home and Aktuell; max 44rem |
| Slip | `.slip`, `.slip.tight` | slip | `--slip`, `--edge`, `--s5`; tight `--s2 --s3`; `--s3` below 760px | `box-shadow: 0 0 0 1px var(--edge)` |
| Source line | `.faden`, `details.beleg` | ground to slip | 1px by `--s5`, `--edge` | Summary keeps a marker |
| Origin line | `.origin`, `.lab` | slip | `note`, `reference`, `--ink`, `--target` | First in the slip; one per source |
| Verdict | `.verdict`, `.what`, `.meaning` | ground | `display`, `title`, `body` | Then `.faden` and the slip |
| Totals | `.totals`, `.swatch` | slip | `figure-row`, `--v-*` | Swatch 10 by 18 px, stub 10 by 7 px |
| Vote wall | `.wall-row`, `.cards i` | slip | `name-large`, `figure-small`, `--cw`, `--ch`, `--cg`, `--enth-w`, `--v-*` | Stub 5px, 4px below 760px; `aria-hidden` |
| Wall as text | `.text-lists`, `.names`, `details.plain` | slip | `note`, `--target` | Columns 3, at least 200px |
| Key | `.key` | slip | `note`, hairline above | Always with the ballot sentence |
| Strip | `.strip`, `.vrow-count` | ground | 14px, `--slip`, 1px `--edge`, `--v-*` | Stub 35% height; no box |
| Tally | `.who`, `.ticks` | ground | 2px by 18px, `--c`, `name`, `figure` | Gap 5px between fives |
| Share line | `.share`, `.shares` | ground | 2px `--ink-2` or 4px `--c` | Length is the value |
| List row | `.vrow`, `.brow`, `.rrow` | ground | `heading-3`, `figure`, `--hair` | Title may clamp to 4 lines; radar rows set their title at 1.5rem to 1.875rem |
| Lead figure | `.huge`, `.figs .big` | ground | `figure-lead`, `figure-row` | Label on the same line below 760px |
| Stand line | `.stand`, `time[data-age]`, `[data-due]` | ground | `note`, `--ink-2` | Under the page heading; age and overdue come from script |
| Zitieren line | `.zitier`, `.lab` | ground | `note`, `--ink` | Under the Stand line; on a vote's page under the slip |
| Sitzung row | `.srow` | ground | mono `figure`, `--target`, `--hair` | Date on its own line below 760px |
| Release | `.releases`, `.release`, `.rel-id`, `.rel-kind`, `.why` | ground | `heading-2`, mono, `--target` | Stable first and primary |
| CSV control | `details.csv`, `summary.ctl` | ground | `--target`, 1px `--edge` | Keeps a marker; opens the file list |
| Citation | `.code.cite-text` | ground | mono `note`, `--hair` | Wraps, never scrolls |
| Changes | `.relog` | ground | mono `figure`, `--hair` | Date first |
| Gap | `.gap`, `.gap.thin` | ground | 1px dashed `--edge`, `heading-3` | Thin form in the page head |
| Control | `.ctl`, `.ctl.primary`, `.btn-row` | ground | `--target`, 1px `--edge`, 2px radius | `aria-pressed`, `:disabled` dashed |
| Field | `.field`, `.filters` | ground | `--target`, 1px `--edge`, `note` label | No fill |
| Table | `table.data`, `.tablewrap` | ground or slip | `note`, `figure`, `--hair` | Sticky header takes its surface's colour |
| Code | `.code` | ground | mono `note`, `--hair` | Scrolls, `tabindex="0"` |
| Speech | `.speech`, `.prose`, `.contribution` | slip | `name-large`, `body`, `--s3` between paragraphs, 68ch | Needs paragraphs as structure: `speeches.text` has none (`docs/plans/a4-site-from-release.md`) |
| Small multiples | `.panels`, `.panel` | ground | 2px `--c`, 1px `--ghost` | 3 columns, 2 below 1000px, 1 below 760px |
| Fraktion bar | `.fbar` | either | 4px by 0.78em, `--c` | Always beside the name |

Name to slug: CDU/CSU `cdu`; AfD `afd`; SPD `spd`; BÜNDNIS 90/DIE GRÜNEN `gruene`; Die Linke and Gruppe Die Linke `linke`; FDP `fdp`; BSW and Gruppe BSW `bsw`; everything else `none`.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-04 | Initial design system created | /design-consultation; owner's memorable thing: every figure traces back to the official record. Independent direction by a Claude subagent; Codex could not run in the sandbox |
| 2026-11-04 | Fraktion colours kept, against the reviewer's and Claude's recommendation | Owner: the association between colours and parties is strong for most people, and leaving it out is the bigger drawback than the clash with Ja and Nein. The clash is handled by shape: a card is a vote, a tick or line is a Fraktion |
| 2026-11-04 | Fraktion colours re-tuned; non-Fraktion roles lose their hues | Today's `PARTY_COLORS` fail on the grey ground (Grüne 2.16:1, FDP 1.86:1) and BSW is too close to Linke. Bundesregierung and Bundesrat are not Fraktionen and exceeded the palette |
| 2026-11-04 | Display stops at 6rem | A full-width verdict pushed the vote cards off the first screen |
| 2026-11-04 | Plain CSS tokens, used from Python-rendered pages | The frontend go/no-go ended in no-go, so PRODUCT.md's stdlib stack stays (`docs/plans/frontend-go-no-go.md`) |
| 2026-11-06 | Controls 44px at every width, not 36px. Owner accepted | Departs from the approved 36px. The site ships 44px targets (`min-height:44px` in `build_dip_pulse_site.py`) and CHANGELOG entries fixed them; 36px would regress the phone. The preview shows 44px does not crowd the Operate pages |
| 2026-11-06 | Superseded the same day by the open direction below. Ground #E6E6E1, was #C9CAC4, with a 1px `slip-edge` on every slip, was none | Departs from the approved value. No ground reaches 3:1 against white (1.59:1 at #C9CAC4), so the surface could never carry provenance alone; the edge does, and the value is then free to be chosen by eye. On a figure page the ground is the whole page, and #C9CAC4 reads overcast. Dark ground unchanged. The provenance rule stays |
| 2026-11-06 | Counts the source prints stand on the slip. Owner accepted | Rewords the approved Surfaces list, which named counts as ground. `parse_roll_call_list_page` and `parse_fraction_votes` read totals and per-Fraktion counts from bundestag.de's own `data-chart-values`, so they are record, and the collision with "no computed figures on a slip" dissolves. "Don't put computed figures on a slip" stands. Corrected counts (E4) say so in words |
| 2026-11-06 | Superseded by the open direction below for lists. A vote colour only ever touches the slip; the list strip is a small slip | Nein reaches 3:1 only on a near-white ground (2.08:1 at #C9CAC4, 2.74:1 at #E6E6E1, 3.03:1 at #F1F1ED), so the strip needed its own slip. "Key swatch on the ground" was then the only exception left, and it went once the totals moved onto the slip |
| 2026-11-06 | Cards show the ballot, never its meaning; an inverted vote changes the words | A blue Ja is what the member cast. Flipping colours would falsify the record; leaving it unexplained misleads. Verdict from `derive.vote_outcome`, sentence on the ground, verbatim source sentence and "Ja (hier: gegen den Antrag)" on the slip. 40 of 217 votes in the preview store are inverted |
| 2026-11-06 | The wall has a text form per Fraktion; cards lose `title` | `title` reaches neither touch nor a screen reader reliably. A `<details>` list keeps the first view visual and needs no script |
| 2026-11-06 | Enthaltung has `vote-abstain-fill` and `-line`; outline 1px at phone size | At 1.5px a 5px card keeps 2px of white and read as black in the preview |
| 2026-11-06 | Provenance is carried by edge, source line and named reference, stated in the footer | 1.21:1 and 1.40:1 cannot carry it, and a first-time reader does not know the convention |
| 2026-11-06 | Fraktion colours are per-mode variables, set by class | `PARTY_COLORS` writes one hex into inline styles, which cannot change with the mode |
| 2026-11-06 | Saved theme, then system, then light; toggle stays | Matches `theme_bootstrap_script` and the Datenschutz page; "light by default" only applies when neither says dark |
| 2026-11-06 | A third mode, Return, for the start page and Wochenübersicht | Operate and Read do not describe a visit of seconds. The site stores nothing about visits, so dates and stable placement do the work of "neu" |
| 2026-11-06 | Visited links stay as they are | Return mode could use a visited mark, but browsers only allow a colour change there, and the only colour change this system permits is too faint to help. The approved rule stands |
| 2026-11-06 | Lead figures in D-DIN, mono at reading size and in columns | The approved rule named mono "at reading size" and left large figures open. In the preview a large mono looked like a typewriter and its slashed zero blotted; D-DIN gave the figure pages the character they lacked |
| 2026-11-06 | Up to six filter options are buttons, seven or more a select | The archive has 14 Politikfelder and 9 Fraktionen: 23 targets of 44px would stack more than 500px above the list on a phone |
| 2026-11-06 | Header, footer, page head, lists, tables, share line, reading, code and accessibility rules added | The extended preview met each on real content and found no answer here. "Mehr" keeps `<details>` from today's site, without a hamburger |
| 2026-11-06 | DIP titles use automatic hyphenation with `overflow-wrap: anywhere`, over 140 characters in `body`, clamped only on lists | Nobody inserts soft hyphens into source text. The longest title has 642 characters; at 375 px nothing overflowed |
| 2026-11-06 | v1 surfaces: home is a door, Aktuell is Return, the AI summary and Fakt der Woche are not v1 components | Owner's scope decisions Q4 to Q6 (`docs/plans/v1-scope-review.md`, commit cc0b0f7 on `claude/strange-germain-01ea7e`). `api-sitzungen.html` and `settings.html` are cut, so they get no design |
| 2026-11-06 | The product name is open-parlament, lower case, plain text, no logo | Owner's decision Q11 |
| 2026-11-06 | All seven links stay visible and wrap to two rows on a phone; "Mehr" goes | Q6 left this to design. A menu saves one 44px row but would hide Analysen, one of two equal angles, and Abstimmungen was promoted because of that fault. Measured at `1.125rem` with an 8px gap: two rows at 375 and 360 px, three at 320 px, one from 761 px. This replaces the "Mehr" in the header row above |
| 2026-11-06 | Home has two equal doors, both on the first screen at 375 by 667 px | PRODUCT.md weights the angles equally. The earlier start page answered only the daily angle. Cutting each door to heading, sentence and lead line, with the latest rows below both, brought the second onto the first screen |
| 2026-11-06 | The Stand line names the main release and the data's age, worked out in the browser | Q3. Pages rebuild only with a release, so a build-time age freezes when an update fails. This retires the build clock's "Auswertung vom" and "Woche läuft" and `STALE_AFTER_WEEKS` |
| 2026-11-06 | "Nicht aktuell" means only an overdue release | Today's rule flags age over 4 weeks, which a recess reaches without any fault. A 6-day delay is normal under Q3, so it gets a sentence, not a gap |
| 2026-11-06 | "Aktuell" is only a link name; no line says "heute", "gerade", "jetzt", "läuft" or "bisher" | The owner's constraint: a sitting can be up to 6 days old when it appears. "Was der Bundestag gerade verhandelt" on the earlier start page broke it |
| 2026-11-06 | Stable takes the primary control on Daten, main the outline; German labels with the technical name beside them | One primary control per page stays true, and citations should name stable (Q3). "Stabiler Stand" and "Laufender Stand" are this design's wording, since citizens do not know "main". "Geprüft" was rejected as a label, because main passes every automatic check too |
| 2026-11-06 | Ground and vote wall stay token-only until the reader test | Q16 puts the test after the rollout, and the owner asked that both stay easy to change |
| 2026-11-06 | A row's title and a slip's reference are 44px targets | The earlier check let them pass as inline links at 20 to 22px, and passed any link inside a `<p>` or `<li>` even when it stood alone there. Padding with a matching negative margin keeps the row height |
| 2026-11-06 | Outside sources re-checked | Validator re-run: ΔE figures confirmed, tritanopia added, three dark Fraktion values found just above the band. bundestag.de glossary read in a browser: blue Ja, red Nein, white Stimmenthaltung |
| 2026-11-06 | The open direction: the frame recedes, the evidence stays in sight | Owner: the grey and the general feel are heavy, and the goal was transparency and openness. The weight came less from the grey than from big condensed bold on every heading and label and 2px near-black rules around everything. "Minimal" only applies to the frame: no source, count or gap may be folded for looks |
| 2026-11-06 | Ground #F7F7F3, slip #FFFFFF with `slip-edge` #85878C, text #1C1E22, muted #4A4C52 | Lighter than every earlier value. The sheet now differs from the page by its edge, which is why the edge stays (3.35:1). Final value by the owner's eye, then the reader test. Fraktion colours unchanged; validator re-run on #F7F7F3 gives the same ΔE figures |
| 2026-11-06 | Headings, names and navigation in Atkinson Next 500 to 600; D-DIN Condensed only for the verdict and lead figures; smaller sizes | Condensed letters read as closed and cramped, and a face used everywhere stops marking anything. Departs from the approved "D-DIN carries headings". The verdict stops at 4.5rem, was 6rem |
| 2026-11-06 | Hairlines and whitespace replace 2px ink rules; no rule under the header; sections 72px apart | Each rule was a small fence around the content. Share lines, source lines, gaps and control outlines thin out with them |
| 2026-11-06 | The list strip sits on the page, with no slip around it | At #F7F7F3 Nein reaches 3:1 on the ground, so the box around every row is no longer needed. The Enthaltung outline and the absent stub take #6E7074, so a large Enthaltung no longer reads as a black block |
| 2026-11-06 | The provenance key says "Blatt mit Rand" and "Offene Fläche" | "Weißes Blatt" and "Grund" no longer describe what a reader sees on a page this light |
| 2026-11-06 | Navigation below 760px is `0.9375rem` with -0.01em tracking and a 4px gap: two rows at 375 and 360 px, three at 320 px | The wider face needed tightening to keep two rows on a 360 px phone. This replaces the measures in the row above on seven links |
| 2026-11-06 | Owner accepted the open direction and chose ground #FFFFFF | Owner, after comparing in the preview: "much better", and the lightest background is the one they like most. Replaces #F7F7F3 above. The page and the sheet are now the same white, so only the edge, the source line and the named reference mark a source. Contrast only improves; validator re-run on #FFFFFF gives the same ΔE figures. The reader test can still move it |
| 2026-11-07 | Every slip opens with an origin line, one per source | Impeccable critique, P1: provenance is the promise and barely shows on white. The reference often stood at the sheet's end, after up to 736 cards. Words carry it now; white and the edge stay. Writing it down found that a person page mixes DIP (`persist_dip_pulse_store.py` reads `funktion` and `wahlperiode` from a DIP person) and abgeordnetenwatch.de (`build_dip_pulse_site.py` takes Geburtsjahr, Beruf, Bundesland and Wahlkreis from its profile), so the two get separate lines, and that a profile link supplying no row is no source |
| 2026-11-07 | A wall row's counts are not assumed to be as printed | `/gstack-ship` review after merging E4: `vote_fractions` is now written from `derive.filed_fractions`, so 146 rows in 55 roll-calls hold the re-filed count. The rule under Surfaces already asked for both numbers; the Vote wall now says where each comes from. Today's note (`_refiled_note_html`) names the members and prints no numbers |
| 2026-11-07 | A Zitieren line on vote, Sitzung, person and analysis pages, with five states | Critique, P1: pages show main, Daten says cite stable, nothing connected them. "In stable" alone would read as "same figure" after a correction, so "unverändert" needs a comparison and a corrected record gets its own state. Analysis pages are beyond the critique's list, because they hold the figures most likely to be cited |
| 2026-11-07 | On a vote's page the Zitieren line stands under the slip | In the head it pushed the totals to 673 px at 375 by 667, off the first screen; under the slip they start at 621 px. The rule that the evidence starts on the first screen wins over one place for the line on every page. Judgement by the design session, not tested with readers |
| 2026-11-07 | CSV is an outline control that opens the file list in place | Critique, P1: the main download was 252 MB of SQLite and the CSV a small link that led nowhere. Stable's SQLite keeps the page's one primary control. A release has 38 CSV files (32 tables, 6 recipes) and no single archive, so the control lists them instead of pretending to be one download |
| 2026-11-07 | Home and Aktuell show the newest vote: verdict, strip and counts, date first | Critique, P1: a visitor could see both and never meet a card. It replaces the door's lead line and the vote's row under "Zuletzt". In the preview the newest vote is from 12 June and the last Sitzungswoche from September, so the date has to lead |
| 2026-11-07 | The Analysen door shows six small panels | Weighting the angles equally rules out a vote on one door and a line of text on the other. A panel for one Fraktion would pick a side on the home page, and the rule against overlaying rules out one chart |
| 2026-11-07 | The second door's heading must reach the first screen, not its end. Replaces "both doors end on the first screen" | The vote does not fit otherwise: the second door ended at 620 px and now ends at 960 px at 375 by 667. Shortening the first door's sentence and label brought the heading up to 631 to 675 px. At 360 by 640 px only its hairline shows. Judgement by the design session, since the critique's fix and the earlier rule cannot both hold; a reader test can reverse it |
| 2026-11-07 | Door links carry the normal underline | Critique, P1: without it they read as headings. No exception to the link rule is left there |
