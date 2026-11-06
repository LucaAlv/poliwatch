---
# gstack: design-md-format=spec
name: Stimmkarte
description: The room where the votes are counted. Plain ground, white slips from the record, cards you could count by hand.
colors:
  ground: "#E6E6E1"
  ground-dark: "#232427"
  slip: "#FBFBF8"
  slip-dark: "#3A3C40"
  slip-edge: "#6E7074"
  slip-edge-dark: "#85878C"
  slip-offset: "#00000040"
  slip-offset-dark: "#00000080"
  text: "#141518"
  text-dark: "#F0F0EA"
  text-muted: "#3B3D42"
  text-muted-dark: "#C8C9C3"
  hairline: "#14151840"
  hairline-dark: "#F0F0EA40"
  ghost-line: "#14151833"
  ghost-line-dark: "#F0F0EA2E"
  vote-yes: "#2456BE"
  vote-yes-dark: "#6A8FEC"
  vote-no: "#E5604D"
  vote-no-dark: "#E25D4A"
  vote-abstain-fill: "#FBFBF8"
  vote-abstain-fill-dark: "#F0F0EA"
  vote-abstain-line: "#141518"
  vote-abstain-line-dark: "#F0F0EA"
  vote-absent: "#3B3D42"
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
  fraktion-none: "#3B3D42"
  fraktion-none-dark: "#C8C9C3"
typography:
  display:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: clamp(3.75rem, 16vw, 6rem)
    lineHeight: 0.9
  heading-1:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: clamp(2.25rem, 6vw, 3.75rem)
    lineHeight: 1
  heading-2:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: clamp(1.75rem, 4vw, 2.5rem)
    lineHeight: 1
  heading-3:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: 1.375rem
    lineHeight: 1.1
  name:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: 1.25rem
    lineHeight: 1
  name-large:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: 1.625rem
    lineHeight: 1.05
  title:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: clamp(1.625rem, 3.6vw, 2.625rem)
    lineHeight: 1.08
  body:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 400
    fontSize: 1.0625rem
    lineHeight: 1.5
  note:
    fontFamily: Atkinson Hyperlegible Next
    fontWeight: 400
    fontSize: 0.9375rem
    lineHeight: 1.5
  figure-lead:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: clamp(3rem, 7vw, 4.5rem)
    lineHeight: 0.95
  figure-row:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: clamp(2.25rem, 5vw, 3.25rem)
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
    fontWeight: 700
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
    padding: "{spacing.lg}"
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

**Not ready to apply: three values below await the owner.** They are written as proposed and depart from what was approved on 2026-11-04: controls at 44px (approved 36px), ground #E6E6E1 with a slip edge (approved #C9CAC4, no edge), and source-printed counts on the slip (approved list named counts as ground). See the Decisions Log. Remove this note once they are answered.

## Overview

**Creative North Star:** the room where the votes are counted. Nothing sells or persuades; the visitor is invited to count it themselves.

**The one thing to remember:** every figure here traces back to the official record. Every decision below serves that sentence.

**Product context:** a nonpartisan German site and citable dataset built from the Bundestag's official record. Citizens want to know what the Bundestag is doing now, often on a phone. Researchers and journalists need figures they can check. Peers are abgeordnetenwatch.de (campaign feel, photo cards, donuts), bundestag.de (institutional card grid, donuts), plenarwatch.de (quiet minimal lists) and opendiscourse.de (template look).

**Mode per surface:**
- Return: start page, Wochenübersicht. The visitor comes back to see what happened and leaves again.
- Operate: votes archive, Gesetzesvorhaben, roster, filters, Daten.
- Read: dossiers, speeches, methods.
- No Persuade or Experience surfaces exist.

**Return mode rules.** A person page or a dossier can wait; a return visit takes seconds.
- The first screen at 375 px answers three things: how fresh the record is (a Stand line), whether it is current (a thin gap in the same place if not), and the largest item of the latest week, Sitzung and vote.
- Same order and same places on every visit, so memory of the page works. Newest first, with the date at the front of the row.
- Lead figures in `figure-lead`, with their label on the same line or directly below.
- The site stores nothing about a visit, so there is no "neu" badge. The date does that work.
- No disclosure hides a first-screen answer. A source line may stay folded.

**Reference sites:** https://www.abgeordnetenwatch.de/bundestag/abstimmungen, https://plenarwatch.de, https://opendiscourse.de, https://www.bundestag.de/parlament/plenum/abstimmung

**Key characteristics:**
- A vote is shown as one card per member, so absences are visible.
- White means the source prints it; the ground means this site worked it out.
- A short line connects a figure to the slip holding its source.
- References are set at reading size in full ink, never as grey small print.
- No photos, donuts, icons in tiles or a box around everything.

## Colors

**Strategy:** Restrained, with no brand colour. Colour only ever carries data, in two families told apart by shape.

**Votes use the Bundestag's own ballot colours.** [Members vote with blue, red and white cards](https://www.bundestag.de/services/glossar/nam_abst-245502), so this colour has a source. A vote is always a card. Enthaltung is a white card with an outline in `vote-abstain-line`, 1.5px, or 1px at the phone card size so a 5px card keeps its white. "Nicht abgegeben" is a low stub in `vote-absent`, so a missing vote reads as a gap.

**A vote colour only ever touches the slip.** Cards, the list strip and key swatches all sit on the slip colour, which is the only surface where Nein reaches 3:1 in light mode.

**A card shows the ballot, never its meaning.** Blue is Ja on every vote. On a vote where a Ja means "gegen den Antrag" (`inverted`), the colours stay and the words change: see Vote wall.

**Fraktionen keep their conventional colours,** because most readers already link them to the parties. A Fraktion's colour appears only on a tick, a line or the small bar beside its name, and always with the name. Shape separates the families: **a card is a vote; a tick or line is a Fraktion.** The two never share a mark. Controls carry no Fraktion colour: a pressed filter would hide it.

**No Fraktion colour for anything that is not a Fraktion.** fraktionslos, Bundesregierung, Bundesrat and other roles use `fraktion-none`. Gruppe Die Linke uses the Linke colour and Gruppe BSW the BSW colour. Older Fraktionen and Gruppen get a colour here before a page shows them.

**Fraktion colours are variables, never inline hex.** Each colour is a custom property per mode (`--f-spd`). A mark takes it through one class on its row (`f-spd`, which sets `--c`), so the renderer writes a class name and never a value. Every name resolves to a slug in one map; anything unmapped takes `f-none`.

**Surfaces carry provenance.**
- `slip`: what the source prints: speech text, member votes, document references, the totals and per-Fraktion counts on the Bundestag's roll-call page, the MdB-Stammdaten, a verbatim sentence.
- `ground`: what this site worked out or generated: the derived "angenommen", shares and percentages, Rede counts, Mehrheitsvotum and Abweichungen, "für" and "gegen" on an inverted vote, rankings, and AI summaries. AI summaries never sit on a slip, whatever their quality.
- A list or table is the site's arrangement, so it sits on the ground. A cell that repeats a source figure there is still ground, except the strip with its counts, which is a small slip.
- A figure the site corrected is no longer as printed. A count re-filed from the MdB-Stammdaten stays in its row and says so in words, with both numbers and the source.
- Headings and navigation carry no provenance. A heading sits with the content it introduces.

**The surface never carries provenance alone.** Slip against ground is 1.21:1 in light mode and 1.40:1 in dark mode, and no ground value tested reaches 3:1 against white. Three cues are binding on every slip: the `slip-edge` line (3:1 or better against the ground in both modes), the source line leading to it, and a named reference inside it. The footer of every page states the rule in words.

**Light or dark:** dark is a chosen pair of values, not an inversion, and the slip stays lighter than the ground in both modes. The site follows the saved choice first (`bundestag-pulse-theme`), then `prefers-color-scheme`, and is light when neither says dark. The toggle stays.

**Interaction has no colour.** Links are underlined ink. Focus is a 2px ink outline with a 2px offset. Selection inverts ink and ground. Visited links look the same as unvisited ones, which keeps source lists calm.

**Measured limits** (WCAG contrast computed from these values; colour-blind separation from the dataviz validator, all-pairs mode, re-run 2026-11-06):
- All text pairs reach 4.5:1 or better on ground and slip (lowest: muted text on the dark slip, 6.6:1).
- All Fraktion colours reach 3:1 on both surfaces in both modes (lowest: FDP 4.12:1 on the light ground, SPD 3.21:1 on the dark slip).
- Vote colours reach 3:1 on the slip in both modes (lowest: Nein 3.31:1 light, 3.10:1 dark). On the light ground Nein reaches only 2.74:1, and it would need a near-white ground to pass, which is why a vote colour never touches the ground.
- `slip-edge` reaches 3.96:1 on the light ground and 4.79:1 on the slip; 4.32:1 and 3.07:1 in dark mode.
- Fraktion hues do **not** pass colour-blind separation. The worst pairs are SPD and FDP in light mode and BSW and AfD in dark mode (both ΔE 3.7, deuteranopia; tritanopia worst 2.6 and 2.8). Some pairs also miss the full-vision floor of 15 (Grüne and FDP 13.3 in light mode, BSW and Linke 12.4 in dark mode). Red against green cannot be fixed while keeping the conventional colours.
- Outside the validator's bands: CDU/CSU on purpose, in both modes, because it is conventionally black (light 0.252, dark 0.836, chroma near zero). Linke, FDP and BSW in dark mode sit just above the lightness band (0.672 to 0.685 against 0.67), and contrast still passes.
- Ja and Nein differ clearly in hue, with lightness contrast of 1.94:1 in light mode and only 1.14:1 in dark mode. Someone who sees no hue relies on the grouping and the printed counts.
- SPD and Nein, and AfD and Ja, sit close together. The AfD hue leans cyan and SPD is a deeper red to keep them apart, but the shape rule does the real work.

These limits are why the rules under Do's and Don'ts are binding, not advice.

## Typography

**D-DIN Condensed Bold** carries headings, names, the verdict and lead figures. It comes from the DIN lettering of German road signs and other public signage, and its narrow width suits German compounds.

**Long words and long titles.** Text this site writes takes soft hyphens at word joints (`Asylverfahrens&shy;beschleunigungs&shy;gesetz`) with `hyphens: manual`. Titles from DIP arrive without them, so they take `hyphens: auto` with `overflow-wrap: anywhere` as the floor, and no line overflows at 375 px. An official title longer than about 140 characters is set in `body`, not in a condensed heading. On a list it clamps to four lines; on its own page it is never cut.

**Atkinson Hyperlegible Next** is the reading and interface face, chosen because the site serves every citizen. Body text uses `hyphens: auto` with `lang="de"`.

**Atkinson Hyperlegible Mono** sets figures and source references at reading size, in full ink. Its slashed zero keeps numbers unambiguous. It is not used for small tracked labels. A figure in a column of figures stays mono, so digits line up. A single lead figure takes `figure-lead` or `figure-row` in D-DIN, because the mono at display size reads as a typewriter and its slashed zero turns into a blot.

**Loading:** self-hosted WOFF2 with `font-display: swap`, about 95 KB for all five files. Nothing loads from another host, which is what the Datenschutz page promises. All three families are under the SIL Open Font License 1.1; ship the licence texts with the files. D-DIN has Reserved Font Names, so serve Datto's files unmodified and do not subset them under that name. Sources: Datto's D-DIN WOFF2 files and the `@fontsource-variable/atkinson-hyperlegible-next` and `@fontsource/atkinson-hyperlegible-mono` packages.

The `display` size is for the single verdict of a detail page. It stops at 6rem so the evidence below it still starts on the first screen.

## Layout

Strict grid, left-aligned, maximum content width 1120px, with a 16px gutter at phone width. Running text stays within about 68 characters; data may take the full width. A slip holding running text hugs that measure instead of leaving a white field beside it.

Grouping comes from whitespace and rules, not boxes. A 2px ink rule separates major items, and a hairline separates rows. A box must mean something: a slip is the record, and a dashed box is a gap.

Fraktionen always appear in the same order within a view, by size in that Wahlperiode, never by a rank that changes per row unless the row is itself a ranking.

**Page head.** Back link if there is a parent, then `heading-1`, then the Stand line (`note`, mono: protocol, date distributed, date of the evaluation), then a thin gap if the data is stale. A back link is navigation, not a kicker, and nothing else stands above the heading.

**Below 760px** the layout changes rather than stacks:
- Navigation drops to four items (see Navigation).
- Vote rows stack with the name above the cards, and cards shrink to 5 by 10 px, so a 630-seat vote stays on a phone screen.
- List rows put the strip below the title, at full width.
- A table with a column it can spare moves it under the row's name (Fraktion on the roster), and a table that cannot spare one scrolls inside its own focusable region.
- A figure and its label share a line.

Between 760 and 1000px, small multiples take two columns.

## Elevation & Depth

Flat. A slip sits on the ground with its 1px `slip-edge` line and a 1px offset line beneath it, and nothing else. No blur shadows, no glow and no frosted surfaces. Sticky elements use a solid background.

## Shapes

Nearly square, like paper and cards: 1px on cards and slips, 2px on controls. Pills are not part of this system, including for filters.

## Components

**Header.** The product name as plain condensed text on the left, since no name or logo is committed, the theme control on the right, the navigation below, and a 2px ink rule beneath. It does not stick. A skip link is the first focusable element on every page.

**Navigation.** Condensed text links, each a full target; the current page has a 3px underline. No pills or boxes. Wide: every destination in one row (Wochenübersicht, Sitzungen, Abstimmungen, Gesetzesvorhaben, Abgeordnete, Fakten, Daten, Quellen). Below 760px: Woche, Sitzungen, Abstimmungen and a "Mehr" `<details>` holding the rest in two columns, which needs no script. "Mehr" takes the underline when the current page is inside it. No hamburger.

**Footer.** A 2px ink rule, the provenance key in words ("Weißes Blatt: steht so in der Quelle. Grund: von dieser Website berechnet oder erzeugt."), then the data note and links to Quellen, Daten, Impressum and Datenschutz.

**Verdict.** On a vote's page: `display` for the outcome word, then the official title, the date and Sitzung, and a note saying the outcome is computed where it is. All of this is ground. The source line leads from here to the slip, which opens with the totals in `figure-row`. On an inverted vote the verdict names the Antrag ("Antrag abgelehnt", from `derive.vote_outcome`), never the bare result of the recommendation.

**Vote wall.** One card per member, grouped into rows by Fraktion, sorted within a row by Ja, Nein, Enthaltung, nicht abgegeben. Beside each row are the Fraktion's name and the counts the source prints. A key is always visible, with the ballot-card explanation. Detail pages only; lists use the strip. If member rows are incomplete, say so and show the counts, never a partial wall presented as whole.
- **As text.** Cards are `aria-hidden` and have no `title`, which neither touch nor screen readers receive reliably. Below the key, each Fraktion has a `<details>` ("CDU/CSU: alle 208 Stimmen als Text") listing its members under Ja, Nein, Enthaltung and nicht abgegeben, with counts. Browser search finds a name.
- **Inverted vote.** On the ground, directly under the title, a sentence states what was voted on and "Ja heißt hier: gegen den Antrag", and one line names who was for and against. On the slip, the sentence the reading rests on comes first, verbatim (`inversion_excerpt`), with its named source (`inversion_source`); where that is only the title on the roll-call page, it says so. The key reads "Ja (hier: gegen den Antrag)". The source's counts and colours do not change. An inverted vote belongs in the tests.
- **One person's votes.** The same cards in one row per person, one card per vote, oldest first, with the same key and a table as text.

**Strip.** The list form of a vote: a small slip with a 1px ink line, 14px high, holding one segment per vote kind in proportion, in the same fills as the cards, with "nicht abgegeben" as a lower stub. Its counts follow in `figure-small`, in words. On an inverted vote a bold line below says "Ja heißt hier: gegen den Antrag." A key opens the list once, as a slip. The strip is `aria-hidden`; the counts carry it.

**Tally.** One tick per Rede, gathered in fives, in the Fraktion's colour, followed by the count as text and preceded by the name. Long periods use one tick per ten, with that scale printed in the row. Single ticks are not tap targets. Rows wrap at phone width in the same Fraktion order.

**Share line.** A horizontal line whose length is the value, 4px, with the name and the value as text beside it. Ink for a neutral share such as a Tagesordnungspunkt's Reden, the Fraktion's colour for a Fraktion's share. Never stacked, because a segment would then rely on colour alone.

**Source line (Beleg).** A 2px ink line, 24px long, runs from a figure to a slip containing the reference (for example "Plenarprotokoll 21/84, S. 10276 D", linked) and, where available, the verbatim sentence. On lists it is a `<details>`, which needs no script; its summary keeps a visible marker, because without one it reads as plain text. Link text must name the source. When the source has no page number, name the protocol and say so.

**Gap.** A dashed 2px box in the muted colour with a short condensed title and the reason in words, on the ground. It looks like an empty place in the file, not an error. Empty states are required on every data view, each with what is missing, why, and a way back where there is one. The thin form states staleness in the page head and does not move between visits.

| Situation | What the reader sees |
|-----------|----------------------|
| Data not fetched | Gap: "Nicht verfügbar" and the reason |
| Period has none | Gap: "Keine in dieser Woche" and what was covered |
| Filter matches nothing | Gap with a link that clears the filter; the result count says 0 |
| Week is old | Thin gap in the page head: "Nicht aktuell" |
| Member rows missing | Totals on the slip, a gap instead of the wall |
| Search without script | Full list and a note pointing to browser search |
| Pages are static | No loading state, except the result count after a filter, which is `aria-live` |

**AI summary.** On the ground, never on a slip, under the permanent mono label "KI-generiert · nicht redaktionell geprüft", with its citations as source lines. No generated page has one yet, so this form has only been seen empty: check it against a real summary before it ships.

**Lists.** Rows on the ground, separated by hairlines, under a 2px rule. Date first, in mono. A list over about 50 rows groups by period, with the period as `heading-2`. Long lists rely on filters, not paging.

**Tables.** Rows on the ground (or on a slip when every cell stands in the source), hairlines between rows, a 2px ink rule under a sticky solid-background header. Numbers right-aligned in mono, text left-aligned, row headers marked `scope="row"`. A wide table scrolls inside a focusable region, never the page.

**Small multiples.** One panel per Fraktion on a shared axis: a 2px line in the Fraktion's colour, the others as 1px neutral ghost lines, the latest value labelled directly, the name in the panel title. Crosshair and tooltip on hover or touch, plus a table of all values below. Figures are aggregated in Python before they reach a chart.

**Reading a speech.** One slip per Rede, hugging the measure: name in `name-large` with the Fraktion bar, the reference to the right (below on a phone), paragraphs in `body`. A Zwischenfrage or Kurzintervention stays inside the Rede, indented between hairlines under a condensed heading saying what it is and who asked, with a note that it is not counted as a Rede. Above the slips, a list of the speakers in order, each a full target with Fraktion and page. Never a box inside the slip.

**Controls.** 44px minimum height at every width, 1px ink outline, no fill, no colour, pressed state inverted. Every control has hover, focus-visible, pressed and disabled states; disabled uses the muted colour with a dashed outline and is never low-contrast text carrying needed information. One primary form exists, filled ink, for the single main action of a page such as a download.
- **Targets.** A link alone on its line is a 44px target at phone width: nav links, source lists, list actions. A link inside a sentence is not.
- **Filters.** Up to six options are a row of buttons, seven or more a native `<select>`, at every width, so 23 buttons never stack above a list. Every field has a visible label, never a placeholder alone. A field is a control, not a slip, so it has no white fill.

**Code and downloads.** SQL sits on the ground between 1px ink rules, in mono at note size, and scrolls inside a focusable region. A checksum is mono and wraps anywhere. A file's size and format stand beside its link.

## Accessibility

Landmarks on every page (`header`, `nav` with a label, `main`, `footer`) and a skip link. `lang="de"`. Cards, strips and ticks are `aria-hidden` and always have text beside them or a text list below. Charts have `role="img"`, a label pointing to their table, and the table. Disclosures are `<details>`. Scrolling regions take `tabindex="0"`. Under forced colours, cards keep their fills (`forced-color-adjust: none`) and the printed counts carry the rest.

## Do's and Don'ts

- Do show every Fraktion colour with the Fraktion's name beside it. Colour never identifies a Fraktion alone.
- Do facet Fraktionen into panels or rows, with a table view for every chart.
- Do put a source line on every figure a reader might cite.
- Do show gaps in words, with the reason.
- Do run the dataviz validator when adding a Fraktion colour, and record the result here.
- Don't draw a vote as anything but a card, or a Fraktion as a card.
- Don't change a card's colour for what the vote means.
- Don't put a vote colour on the ground.
- Don't overlay several Fraktion lines in one plot, or use donuts or stacked bars where colour alone tells the segments apart. The strip is proportional but its segments differ in shape and carry printed counts.
- Don't colour text with a Fraktion or vote colour; marks carry colour, text stays ink.
- Don't put computed figures or generated text on a slip. A count the source prints is not computed.
- Don't use photos, icon tiles, kickers above headings, pills, nested boxes or a brand accent colour.
- Don't make anything a tap target below 44px, except a link inside a sentence.

## Motion

- **Approach:** minimal-functional.
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50-100ms) short(150ms for a slip unfolding)
- **The one authored moment:** a source slip unfolding in place. It is off under `prefers-reduced-motion`.

## Component Inventory

For the one shared stylesheet. Values come from the front matter; the classes are the ones the preview uses (`~/.gstack/projects/LucaAlv-poliwatch/designs/design-system-20261104/build_preview_v2.py`, which holds the working CSS).

```css
:root {
  color-scheme: light;
  --ground: #E6E6E1; --slip: #FBFBF8; --edge: #6E7074; --offset: #00000040;
  --ink: #141518; --ink-2: #3B3D42; --hair: #14151840; --ghost: #14151833;
  --v-ja: #2456BE; --v-nein: #E5604D; --v-enth-fill: #FBFBF8; --v-enth-line: #141518; --v-abs: #3B3D42;
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
  --ground: #232427; --slip: #3A3C40; --edge: #85878C; --offset: #00000080;
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
| Header | `.site`, `.brand`, `.skip` | ground | `name`, 2px `--ink` rule | Not sticky; skip link first |
| Navigation | `.site-nav`, `.nav-more` | ground | `name`, `--target`, 3px current underline | `<details>` below 760px |
| Footer | `.site-foot`, `.prov` | ground | `note`, 2px `--ink` rule | Carries the provenance key |
| Slip | `.slip`, `.slip.tight` | slip | `--slip`, `--edge`, `--offset`, `--s4`; tight `--s2 --s3`; `--s3` below 760px | `box-shadow: 0 1px 0 var(--offset), 0 0 0 1px var(--edge)` |
| Source line | `.faden`, `details.beleg` | ground to slip | 2px by `--s5`, `--ink` | Summary keeps a marker |
| Verdict | `.verdict`, `.what`, `.meaning` | ground | `display`, `title`, `body` | Then `.faden` and the slip |
| Totals | `.totals`, `.swatch` | slip | `figure-row`, `--v-*` | Swatch 10 by 18 px, stub 10 by 7 px |
| Vote wall | `.wall-row`, `.cards i` | slip | `name-large`, `figure-small`, `--cw`, `--ch`, `--cg`, `--enth-w`, `--v-*` | Stub 5px, 4px below 760px; `aria-hidden` |
| Wall as text | `.text-lists`, `.names`, `details.plain` | slip | `note`, `--target` | Columns 3, at least 200px |
| Key | `.key` | slip | `note`, hairline above | Always with the ballot sentence |
| Strip | `.strip`, `.vrow-count` | small slip | 14px, 1px `--ink`, `--v-*` | Stub 35% height |
| Tally | `.who`, `.ticks` | ground | 2px by 18px, `--c`, `name`, `figure` | Gap 5px between fives |
| Share line | `.share`, `.shares` | ground | 4px, `--ink` or `--c` | Length is the value |
| List row | `.vrow`, `.brow`, `.rrow` | ground | `heading-3`, `figure`, `--hair` | Title may clamp to 4 lines; radar rows set their title at 1.5rem to 1.875rem |
| Lead figure | `.huge`, `.figs .big` | ground | `figure-lead`, `figure-row` | Label on the same line below 760px |
| Stand line | `.stand` | ground | mono `note`, `--ink-2` | Under the page heading |
| Gap | `.gap`, `.gap.thin` | ground | 2px dashed `--ink-2`, `heading-3` | Thin form in the page head |
| Control | `.ctl`, `.ctl.primary`, `.btn-row` | ground | `--target`, 1px `--ink`, 2px radius | `aria-pressed`, `:disabled` dashed |
| Field | `.field`, `.filters` | ground | `--target`, 1px `--ink`, `note` label | No fill |
| Table | `table.data`, `.tablewrap` | ground or slip | `note`, `figure`, `--hair` | Sticky header takes its surface's colour |
| Code | `.code` | ground | mono `note`, 1px `--ink` rules | Scrolls, `tabindex="0"` |
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
| 2026-11-06 | **Awaiting owner.** Controls 44px at every width, not 36px | Departs from the approved 36px. The site ships 44px targets (`min-height:44px` in `build_dip_pulse_site.py`) and CHANGELOG entries fixed them; 36px would regress the phone. The preview shows 44px does not crowd the Operate pages |
| 2026-11-06 | **Awaiting owner.** Ground #E6E6E1, was #C9CAC4, with a 1px `slip-edge` on every slip, was none | Departs from the approved value. No ground reaches 3:1 against white (1.59:1 at #C9CAC4), so the surface could never carry provenance alone; the edge does, and the value is then free to be chosen by eye. On a figure page the ground is the whole page, and #C9CAC4 reads overcast. Dark ground unchanged. The provenance rule stays |
| 2026-11-06 | **Awaiting owner.** Counts the source prints stand on the slip | Rewords the approved Surfaces list, which named counts as ground. `parse_roll_call_list_page` and `parse_fraction_votes` read totals and per-Fraktion counts from bundestag.de's own `data-chart-values`, so they are record, and the collision with "no computed figures on a slip" dissolves. "Don't put computed figures on a slip" stands. Corrected counts (E4) say so in words |
| 2026-11-06 | A vote colour only ever touches the slip; the list strip is a small slip | Nein reaches 3:1 only on a near-white ground (2.08:1 at #C9CAC4, 2.74:1 at #E6E6E1, 3.03:1 at #F1F1ED), so the strip needed its own slip. "Key swatch on the ground" was then the only exception left, and it went once the totals moved onto the slip |
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
| 2026-11-06 | Outside sources re-checked | Validator re-run: ΔE figures confirmed, tritanopia added, three dark Fraktion values found just above the band. bundestag.de glossary read in a browser: blue Ja, red Nein, white Stimmenthaltung |
