---
# gstack: design-md-format=spec
name: Stimmkarte
description: The room where the votes are counted. Plain ground, white slips from the record, cards you could count by hand.
colors:
  ground: "#C9CAC4"
  ground-dark: "#232427"
  slip: "#FBFBF8"
  slip-dark: "#3A3C40"
  text: "#141518"
  text-dark: "#F0F0EA"
  text-muted: "#3B3D42"
  text-muted-dark: "#C8C9C3"
  vote-yes: "#2456BE"
  vote-yes-dark: "#6A8FEC"
  vote-no: "#E5604D"
  vote-no-dark: "#E25D4A"
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
  name:
    fontFamily: D-DIN Condensed
    fontWeight: 700
    fontSize: 1.25rem
    lineHeight: 1
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
  figure:
    fontFamily: Atkinson Hyperlegible Mono
    fontWeight: 400
    fontSize: 1rem
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
  control:
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    height: 36px
---

# Stimmkarte

## Overview

**Creative North Star:** the room where the votes are counted. Nothing sells or persuades; the visitor is invited to count it themselves.

**The one thing to remember:** every figure here traces back to the official record. Every decision below serves that sentence.

**Product context:** a nonpartisan German site and citable dataset built from the Bundestag's official record. Citizens want to know what the Bundestag is doing now, often on a phone. Researchers and journalists need figures they can check. Peers are abgeordnetenwatch.de (campaign feel, photo cards, donuts), bundestag.de (institutional card grid, donuts), plenarwatch.de (quiet minimal lists) and opendiscourse.de (template look).

**Mode per surface:**
- Operate: votes archive, roster, filters, Daten.
- Read: dossiers, speeches, methods.
- No Persuade or Experience surfaces exist.

**Reference sites:** https://www.abgeordnetenwatch.de/bundestag/abstimmungen, https://plenarwatch.de, https://opendiscourse.de, https://www.bundestag.de/parlament/plenum/abstimmung

**Key characteristics:**
- A vote is shown as one card per member, so absences are visible.
- White means the protocol says so; the grey ground means this site worked it out.
- A short line connects a figure to the slip holding its source.
- References are set at reading size in full ink, never as grey small print.
- No photos, donuts, icons in tiles or a box around everything.

## Colors

**Strategy:** Restrained, with no brand colour. Colour only ever carries data, in two families told apart by shape.

**Votes use the Bundestag's own ballot colours.** Members vote with [blue, red and white cards](https://www.bundestag.de/services/glossar/nam_abst-245502), so this colour has a source. A vote is always a card. Enthaltung is an outlined white card. "Nicht abgegeben" is a low stub in the muted text colour, so a missing vote reads as a gap.

**Fraktionen keep their conventional colours,** because most readers already link them to the parties. A Fraktion's colour appears only on a tick, a line or the small bar beside its name, and always with the name. Shape separates the families: **a card is a vote; a tick or line is a Fraktion.** The two never share a mark.

**No Fraktion colour for anything that is not a Fraktion.** fraktionslos, Bundesregierung, Bundesrat and other roles use the muted text colour. Gruppe Die Linke uses the Linke colour. Older Fraktionen and Gruppen get a colour here before a page shows them.

**Surfaces carry provenance.**
- `slip`: material that stands in the source as printed, such as speech text, member votes and document references.
- `ground`: what this site computed or generated, such as counts, shares, the derived "angenommen" and AI summaries. AI summaries never sit on a slip, whatever their quality.

**Light or dark:** light by default, since most reading happens in daylight on phones and desks. Dark is a chosen pair of values, not an inversion. The slip stays lighter than the ground in both modes.

**Interaction has no colour.** Links are underlined ink. Focus is a 2px ink outline with a 2px offset. Selection inverts ink and ground. Visited links look the same as unvisited ones, which keeps source lists calm.

**Measured limits** (WCAG contrast computed from these values; colour-blind separation from the dataviz validator, all-pairs mode, 2026-11-04):
- All text pairs reach 4.5:1 or better on ground and slip.
- All Fraktion colours reach 3:1 on both surfaces in both modes (lowest: FDP 3.12:1 light, SPD 3.21:1 dark).
- Vote colours reach 3:1 on the slip in both modes (lowest: Nein 3.31:1 light, 3.10:1 dark), which is why the vote wall sits on a slip. On the light ground Nein reaches only 2.08:1, so a vote colour on the ground appears only as a key swatch next to its word and figure, never as a card carrying data.
- Fraktion hues do **not** pass colour-blind separation. The worst pairs are SPD and FDP in light mode and BSW and AfD in dark mode (both ΔE 3.7, deuteranopia). Some pairs also miss the full-vision floor of 15 (Grüne and FDP 13.3 in light mode, BSW and Linke 12.4 in dark mode). Red against green cannot be fixed while keeping the conventional colours.
- CDU/CSU is outside the validator's lightness and chroma bands on purpose: it is conventionally black.
- Ja and Nein differ clearly in hue, with lightness contrast of 1.94:1 in light mode and only 1.14:1 in dark mode. Someone who sees no hue relies on the grouping and the printed counts.
- SPD and Nein, and AfD and Ja, sit close together. The AfD hue leans cyan and SPD is a deeper red to keep them apart, but the shape rule does the real work.

These limits are why the rules under Do's and Don'ts are binding, not advice.

## Typography

**D-DIN Condensed Bold** carries headings, names and the verdict. It comes from the DIN lettering of German road signs and other public signage, and its narrow width suits German compounds. In display sizes, break compounds at word joints with soft hyphens (`Asylverfahrens&shy;beschleunigungs&shy;gesetz`) and set `hyphens: manual`, because automatic hyphenation breaks them mid-syllable.

**Atkinson Hyperlegible Next** is the reading and interface face, chosen because the site serves every citizen. Body text uses `hyphens: auto` with `lang="de"`.

**Atkinson Hyperlegible Mono** sets figures and source references at reading size, in full ink. Its slashed zero keeps numbers unambiguous. It is not used for small tracked labels.

**Loading:** self-hosted WOFF2 with `font-display: swap`, about 95 KB for all five files. Nothing loads from another host, which is what the Datenschutz page promises. All three families are under the SIL Open Font License 1.1; ship the licence texts with the files. D-DIN has Reserved Font Names, so serve Datto's files unmodified and do not subset them under that name. Sources: Datto's D-DIN WOFF2 files and the `@fontsource-variable/atkinson-hyperlegible-next` and `@fontsource/atkinson-hyperlegible-mono` packages.

The `display` size is for the single verdict of a detail page. It stops at 6rem so the evidence below it still starts on the first screen.

## Layout

Strict grid, left-aligned, maximum content width 1120px, with a 16px gutter at phone width. Running text stays within about 68 characters; data may take the full width.

Grouping comes from whitespace and rules, not boxes. A 2px ink rule separates major items, and a hairline separates rows on a slip. A box must mean something: a slip is the record, and a dashed box is a gap.

Fraktionen always appear in the same order within a view, by size in that Wahlperiode, never by a rank that changes per row unless the row is itself a ranking. Below 760px, vote rows stack with the name above the cards, and cards shrink to 5 by 10 px so a 630-seat vote stays on a phone screen.

## Elevation & Depth

Flat. A slip sits on the ground with a 1px offset line beneath it and nothing else. No blur shadows, no glow and no frosted surfaces. Sticky elements use a solid background.

## Shapes

Nearly square, like paper and cards: 1px on cards and slips, 2px on controls. Pills are not part of this system, including for filters.

## Components

**Vote wall.** One card per member, grouped into rows by Fraktion, sorted within a row by Ja, Nein, Enthaltung, nicht abgegeben. Beside each row are the Fraktion's name and its counts as text. A key is always visible, with the ballot-card explanation. Each card's title gives the member and vote. Detail pages only; list pages use one proportional strip, since 630 elements per row would be too heavy. If member rows are incomplete, say so and show the counts, never a partial wall presented as whole.

**Tally.** One tick per Rede, gathered in fives, in the Fraktion's colour, followed by the count as text and preceded by the name. Long periods use one tick per ten, with that scale printed in the row. Single ticks are not tap targets.

**Source line (Beleg).** A 2px ink line, 24px long, runs from a figure to a slip containing the reference (for example "Plenarprotokoll 21/84, S. 10276 D", linked) and, where available, the verbatim sentence. On lists it is a `<details>`, which needs no script. Link text must name the source. When the source has no page number, name the protocol and say so.

**Gap.** A dashed 2px box in the muted colour with the reason in words, on the ground. It looks like an empty place in the file, not an error. Empty states are required on every data view.

**AI summary.** On the ground, never on a slip, under the permanent mono label "KI-generiert · nicht redaktionell geprüft", with its citations as source lines.

**Small multiples.** One panel per Fraktion on a shared axis: a 2px line in the Fraktion's colour, the others as 1px neutral ghost lines, the latest value labelled directly, the name in the panel title. Crosshair and tooltip on hover or touch, plus a table of all values below. Figures are aggregated in Python before they reach a chart.

**Navigation.** Condensed text links; the current page has a 3px underline. No pills or boxes.

**Controls.** 36px minimum height, 1px ink outline, pressed state inverted. Every control has hover, focus-visible, pressed and disabled states; disabled uses the muted colour and is never low-contrast text carrying needed information.

## Do's and Don'ts

- Do show every Fraktion colour with the Fraktion's name beside it. Colour never identifies a Fraktion alone.
- Do facet Fraktionen into panels or rows, with a table view for every chart.
- Do put a source line on every figure a reader might cite.
- Do show gaps in words, with the reason.
- Do run the dataviz validator when adding a Fraktion colour, and record the result here.
- Don't draw a vote as anything but a card, or a Fraktion as a card.
- Don't overlay several Fraktion lines in one plot, or use donuts or stacked bars where colour alone tells the segments apart.
- Don't colour text with a Fraktion or vote colour; marks carry colour, text stays ink.
- Don't put computed figures or generated text on a slip.
- Don't use photos, icon tiles, kickers above headings, pills, nested boxes or a brand accent colour.

## Motion

- **Approach:** minimal-functional.
- **Easing:** enter(ease-out) exit(ease-in) move(ease-in-out)
- **Duration:** micro(50-100ms) short(150ms for a slip unfolding)
- **The one authored moment:** a source slip unfolding in place. It is off under `prefers-reduced-motion`.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-11-04 | Initial design system created | /design-consultation; owner's memorable thing: every figure traces back to the official record. Independent direction by a Claude subagent; Codex could not run in the sandbox |
| 2026-11-04 | Fraktion colours kept, against the reviewer's and Claude's recommendation | Owner: the association between colours and parties is strong for most people, and leaving it out is the bigger drawback than the clash with Ja and Nein. The clash is handled by shape: a card is a vote, a tick or line is a Fraktion |
| 2026-11-04 | Fraktion colours re-tuned; non-Fraktion roles lose their hues | Today's `PARTY_COLORS` fail on the grey ground (Grüne 2.16:1, FDP 1.86:1) and BSW is too close to Linke. Bundesregierung and Bundesrat are not Fraktionen and exceeded the palette |
| 2026-11-04 | Display stops at 6rem | A full-width verdict pushed the vote cards off the first screen |
| 2026-11-04 | Plain CSS tokens, used from Python-rendered pages | The frontend go/no-go ended in no-go, so PRODUCT.md's stdlib stack stays (`docs/plans/frontend-go-no-go.md`) |
