# Gesetzesvorhaben: usability and design refinement

**Current status (2026-10-09): implemented and locally validated.** The design and engineering review sections below preserve their pre-implementation findings. The implementation evidence near the end supersedes their open proof requirements. Changes remain uncommitted and undeployed.

Status: design- and engineering-reviewed implementation plan, 2026-10-08. Nine design decisions remain approved; seven required test gaps are mapped to implementation. No UI implementation or application test run yet.

## Goal and direction

Help politically interested readers find a particular law, understand the recorded parliamentary activity, and reach its documents, debates and speakers. Preserve the site's existing typography, colours, theme controls and primary-source links. The overview serves finding and browsing; a detail page serves understanding.

The scoped view supports title/Drucksache-number lookup and browsing by recorded activity year. D7 selects purpose-first orientation for that existing task. Policy-topic browsing requires suitable topic data and is outside this refinement; no pending topic-priority question blocks implementation of the defined metadata lookup.

## Evidence and constraints

Inspected the local overview and a real detail page through Chrome DevTools, including desktop screenshots and a 390px mobile viewport, and traced the renderers and their data collection.

- The local overview currently has 562 entries covering latest recorded dates from 2022-01-28 to 2026-09-25. This is a build-dependent sample, not a complete catalog of current laws.
- Each entry repeats its detail link and offers a browser-only follow marker. Following provides no notification or useful separate view.
- On desktop the speaker sidebar is 360px wide. A measured row has 286px of content divided into 120px / 26px / 120px columns, with two gaps. Long parliamentary affiliation/role labels visibly collide with the speech figures.
- The detail renderer silently limits speakers to twelve, repeats the law title throughout the timeline and puts raw technical fields among prominent facts.
- `latest_step` is the kind of the newest recorded event, sometimes a document type. It is not an authoritative legislative status. Same-date events also do not establish a meaningful procedural order.
- `introduced_by` combines authors of all associated documents, including later committee reports. It does not reliably identify the original initiator.
- `documents` includes Plenarprotokolle as well as Drucksachen. A count of that whole list must be labelled “Dokumente”, not “Drucksachen”.
- Speaker `party` contains the derived parliamentary side: a Fraktion or, for example, Bundesregierung. It is not always the person's political party. Specific ministerial titles are not a separate bill field.
- Votes are linked namentliche Abstimmungen. Their absence does not establish that no vote occurred.

## 1. Make the overview useful

Remove the four aggregate statistic boxes, follow summary, all “Folgen” buttons and the duplicate “Details” links. Remove the follow-only script and styles once their callers are checked. Keep the title as the single detail link, with clear blue link styling, hover underline and keyboard focus. Do not make a whole card clickable around glossary links or other controls.

Use the heading “Gesetzesvorhaben”. The purpose-first introduction accepted in D7 is “Finde Gesetzesvorhaben und lies nach, wie sie im Bundestag beraten wurden.” Keep the visible coverage note beside the result count: “Die Liste zeigt Vorhaben aus den hier ausgewerteten Sitzungen, nicht alle Gesetzesvorhaben.” Move pipeline details such as `--detail-limit` to the method documentation. The coverage note remains visible before the results rather than hidden in a tooltip or collapsed source block.

Place a compact control area immediately before the results:

| Control | Initial behaviour |
| --- | --- |
| Suche | Label “Gesetzesvorhaben suchen”; hint “Titel oder Drucksachennummer”. Search titles and every associated document number, not only the primary document. Trim whitespace, ignore case and combine entered words. |
| Zeitraum | “Jahr der letzten erfassten Aktivität”; “Alle Jahre” plus years present in the data. Explicitly describe that this filters the latest observed activity, not when the law was introduced. Missing dates remain visible under “Alle Jahre”. |
| Sortierung | “Zuletzt erfasst” by default, plus “Älteste zuerst” and “Titel A–Z”, with German title ordering and deterministic ties. |
| Feedback | Result count, active criteria and a reset control. Distinguish “no matching results” from an empty publication. Announce changes without moving focus. |

**No matches (D5=A):** when the published collection has entries but the selected criteria match none, show “Keine passenden Gesetzesvorhaben gefunden.” Add the short help text “Versuche einen anderen Suchbegriff oder setze Suche und Filter zurück.” The main recovery action is “Suche und Filter zurücksetzen”: clear the query and year, return to page one and keep the selected sort order. Restore all recorded entries and update the URL, result count and announcement. Do not suggest that the searched law does not exist.

**Empty publication (D6=A):** if the publication contains no law entries at all, show “Noch keine Gesetzesvorhaben verfügbar. Hier erscheinen Vorhaben aus den erfassten Sitzungsauswertungen.” The primary action is “Sitzungen ansehen” linking to `../overview.html`. Keep “Quellen und Methode” available as secondary access. Omit ineffective search/reset/pagination controls for this state. Do not say Parliament has no legislative procedures or claim an acquisition failure without corresponding evidence.

Search and filters apply to the entire collection before pagination. Show 20 results per page with accessible previous/next controls and “1–20 von 562”. Reset to page one when criteria change. Retain query, year, sort and page in URL parameters so links are shareable and Back restores the overview state. Avoid infinite scrolling.

**Explicit page navigation (D11=A):** after “Weiter” or “Zurück” changes the result page, update the displayed entries/URL and move scroll and focus to the result summary at the start of the new set (for example, “21–40 von 562”). The next tab stop leads into the new results. Use immediate movement, not animated scrolling. This transition applies only to deliberate pagination; search/filter typing and sort changes keep focus on their controls. Browser Back restores the previous overview state rather than being treated as a new pagination action.

**Responsive controls (D10=A):** keep search, year and sorting visible, without a phone-only filter disclosure. At 640px and below, stack the three labelled controls at full width. From 641px to 1023px, put search across the available width above the paired year/sort selectors. At 1024px and above, use one row with search receiving the remaining width. Fields may grow/wrap to preserve their visible labels; do not clip long values to force a control row. Use at least 44px control height and the existing 12px grid-gap vocabulary. The shared navigation keeps its separate, previously approved 1024px breakpoint.

**Enhancement lifecycle (D4=A):** publish the complete readable list first. Search/filter/sort controls remain disabled and pagination inactive until synchronous initialization succeeds; do not hide entries before the controls and result-state update are ready. There is no asynchronous acquisition or loading animation. If initialization or a later interaction fails, restore the complete list, disable unavailable controls and show the quiet notice “Suche derzeit nicht verfügbar. Alle erfassten Gesetzesvorhaben werden angezeigt.” The count then describes all entries, not stale filtered results. Preserve title/source links and browser search. Do not add a prominent warning panel or reload button. No-JavaScript readers likewise retain the full list with an appropriate static explanation of unavailable interactive search.

Simplify each entry to its full linked title, a readable date, the clearly labelled latest recorded event, and a quiet line of document/debate/roll-call counts. Use the plain-row treatment accepted in D8: separate entries with a thin `--line` divider and vertical space, rather than individual white rounded cards. Do not add shadows, enclosing card borders or row hover lifts. The title remains the single clearly styled detail link; a divider does not turn the row into another click target. Remove the repeated “Gesetzgebung” label. Keep full titles wrapping naturally; do not invent short titles or hide essential text behind hover. Move the long list of document authors to the detail page.

Do not offer “ongoing/completed”, party-of-initiator or policy-topic filters with the current ambiguous/missing fields. A latest-event-type filter is technically possible but not included in this refinement: its document-type vocabulary is less useful to a general reader than search and year. A later request for procedural browsing can reconsider it without blocking the defined controls.

## 2. Clarify the detail page

Replace the technical subtitle and four metric boxes with a compact context area: “Zuletzt erfasst”, its date, latest event label and a primary-source link when available. Put the DIP identifier in source/data information. Use German date formatting throughout. Explain that the latest recorded event is not necessarily the present legal status; omit a speculative progress bar.

Keep sections visibly available and add simple anchor navigation: “Verlauf”, “Debatten”, “Rednerinnen und Redner”, “Abstimmungen”, “Dokumente”, “Quellen und Daten”. The current implementation has panels rather than true tabs; anchor links preserve direct linking, browser search and no-JavaScript reading. The anchor order follows the mobile document order accepted in D3.

- **Verlauf:** group entries by date, lead with the event/document type, then its source link. Avoid repeating the unchanged law title in every row; retain titles when they supply distinct information. Keep all distinct events and source links, including multiple events on the same date. Do not silently infer a sequence among them.
- **Debatten:** replace unexplained “Plenarstellen” with a clear section name and show Sitzung/date and Tagesordnungspunkt, linked to the dossier anchor. Explain that associated agenda items may discuss multiple procedures.
- **Rednerinnen und Redner:** use dedicated speaker styling, separate from document/timeline grids. Name on the first line, Fraktion or Sprechrolle beneath it, then smaller speech figures with correct singular/plural. Let long names and affiliations wrap. Keep profile links where resolvable and plain text where not. Make Zeichen secondary. Keep the current ordering for this refinement, disclose it as “nach Zahl der erfassten Reden”, and explain the coverage. If more than twelve exist, show the total and offer a native expandable “Weitere Rednerinnen und Redner” section containing the rest.
- **Abstimmungen:** expose links for recorded roll-call votes already present in the bill data. Use “Keine namentliche Abstimmung in den erfassten Daten verknüpft” for zero, rather than implying no parliamentary vote happened.
- **Dokumente:** show document number, type and author in a layout designed for documents. Rename the full mixed list “Dokumente”; use “Drucksache” specifically for those entries. Label aggregated authors “Urheber der verknüpften Dokumente”, rather than “Eingebracht von”. Do not change source data to fit a cleaner label.
- **Quellen und Daten:** keep raw JSON collapsed at the end and retain access to source/method documentation. State gaps where they occur. Keep the wording about other procedures on the same TOP; do not imply those are amendments to this law.

On desktop retain a main reading column and supporting sidebar, reusing the current panel padding and section/list spacing. On narrow screens use this explicit sequence: title/context → section navigation → Verlauf → Debatten → Rednerinnen und Redner → Abstimmungen → Dokumente (including other procedures on the same TOP) → Quellen und Daten. The source/document order must support that sequence without JavaScript or CSS visual reordering that contradicts keyboard/screen-reader reading order. Wrap source links. Essential explanations remain visible; tooltips add detail.

**Readable type hierarchy (D9=A):** retain the existing bill-page title at 34px, 28px at the existing phone breakpoint, and section headings at 21px. Overview law titles retain the 21px heading scale. Use 16px for essential reading text: speaker names and affiliations/roles, document/event labels, explanations and source-link text. Speaker names are semibold; affiliation/role is regular text on its own line; supplementary figures are 14px on their own line. Use `--ink` for primary text and `--muted` only where the text remains legible against its actual theme surface. Keep the existing font family and use approximately 1.5 line height for reading text. Full names/titles wrap; no essential affiliation, event label or source name is clipped to retain density.

## 3. Explain parliamentary language and add restrained feedback

Reuse the dotted-underline glossary convention already used for “Gesetzgebung” in the Puls Debattenprofil. Reuse its existing text and source anchor for that term.

Add short, source-checked explanations for the terms readers encounter: Drucksache, Plenarprotokoll, Tagesordnungspunkt, erste/zweite/dritte Beratung, Beschlussempfehlung und Bericht, Unterrichtung, Stellungnahme, Gesetzesbeschluss, namentliche Abstimmung and Fraktion/Sprechrolle. Unknown types retain their source label rather than receiving an invented explanation. Put longer definitions in the existing sources/method glossary.

The tooltip appearance can follow Puls, but CSS pseudo-element text alone is insufficient as the accessible description. Provide real descriptive text for assistive technology. Make help available on hover and keyboard focus, and accessible via a tap to its glossary entry. Hover content must remain readable when the pointer enters it, be dismissible with Escape and stay within the viewport. Use a small native popover only if those behaviours need it; do not add a tooltip library. Important status and coverage caveats belong in visible copy.

Use short colour/border transitions on links and actual controls, and a brief opacity transition for explanations. Give keyboard focus the same clarity as hover. Keep plain speaker rows visually static unless they contain an interactive target. Avoid card movement, entrance animations and animated result reordering. Respect `prefers-reduced-motion`; search and pagination should update predictably.

## Implementation sequence and reuse

1. Overview cleanup, metadata search, year filter, sort and pagination/URL state.
2. Detail hierarchy, accurate labels, dedicated speaker rows, complete speaker access and existing vote links.
3. Glossary explanations, interaction feedback and the bounded desktop/mobile/accessibility check.

Implement in the current static Python renderer with native HTML/CSS and a small page-specific script. Reuse the catalog's filtering/sorting/reset pattern and the roster's search presentation where appropriate. Avoid a shared filtering framework, search backend, new package or migration of the legislative pipeline.

Primary targets are `render_bills_index`, `render_bill_detail`, `render_bill_script` and `bill_styles` in `scripts/build_dip_pulse_site.py`. Existing catalog interaction code is `render_catalog_script`; the glossary lives in `scripts/render_dip_pulse_html.py` and is rendered into `sources.html`. Keep glossary additions explicit and centralized.

`bill_styles()` is also used by the vote archive and Abgeordnete pages. Scope new rules to bill-page classes and preserve styles still consumed there. Check follow/readiness metadata consumers before removing bill-follow references. Keep `bills.json`, bill identities and speaker counting semantics unchanged in this refinement.

The requested search is bounded metadata lookup over this view, consistent with existing catalog/roster filtering. It does not search speech bodies or documents. Clarify that distinction in PRODUCT.md during implementation if its existing “no free full-text search” wording becomes ambiguous.

## Acceptance checks

- A visitor can find an older entry by title and by a non-primary Drucksache number. Search/year/sort work together; counts describe all matches, not only the displayed page. Reset, empty results and Back restoration work.
- All entries remain readable without JavaScript; initialize interactive controls and pagination only when their script runs. Print exposes the complete collection, not just the active page.
- No follow or duplicate Details controls remain. One clearly accessible title link opens each detail page.
- Long names, “BÜNDNIS 90/DIE GRÜNEN” and “Bundesregierung” do not overlap speech figures at desktop, 390px, 320px or 200% zoom. All recorded speakers are reachable.
- Zero, missing and partial data use accurate copy. Counts never present protocol files as Drucksachen or observed events as authoritative legal status.
- Glossary explanations work with mouse, keyboard, touch and assistive technology; focus, Escape, viewport edges and reduced motion behave correctly. Check light and dark themes.
- Generated detail/source/profile links resolve; the law with multiple events on one date retains all source references.
- Add focused regression coverage to `tests/test_bills.py` for the changed output/data boundaries, plus a small runnable check for the actual search/filter/pagination/state behaviour. Do not treat string checks of JavaScript as proof that it works.
- Run `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`, Python compilation and the offline demo/publication validation required by the repository. Through Chrome DevTools, inspect overview/detail on desktop and mobile in one batched pass, correct findings together, then confirm once. Include the MP roster and vote archive as shared-CSS regression checks.

Planning validation: source/data inspection and representative browser review only. No test run is needed for this document-only change.

## Plan design review

Review target: this plan, on `main` at `9e1d836`. Initial design-completeness impression: **7/10**. The review concerns the plan, not a rendered implementation. UI code remains unchanged.

- **D1 — review routing:** user selected A, review both pages evenly across all seven dimensions. This approves review emphasis, not proposed UI remedies.
- **D2 — independent review routing:** user selected A but reported that Claude Code had reached its usage limit. Do not invoke Claude Code. One independent GPT-6 Luna completeness review completed; external cross-model coverage is unavailable, not passed.
- Mockup generation is unavailable: neither the repo-local nor installed gstack design binary was found. Continue with plan/source evidence; no mockups are generated or approved.
- **Pass 1 — information architecture: initial 8/10.** The overview's finding/browsing job and the detail section purposes were clear. The explicit narrow-screen section sequence was initially undecided. A 10 specifies that sequence, its matching anchor order and the overview/detail navigation flow.
- **D3 — accepted:** user selected A, prioritize discussion and participants before documents on mobile: Verlauf → Debatten → Rednerinnen und Redner → Abstimmungen → Dokumente → Quellen. Keep title/context/navigation first and raw data last. All contents remain accessible through matching section links. Desktop main/supporting-column intent remains unchanged.
- **Pass 1 — information architecture: 8/10 → 10/10.** D3 resolves the missing mobile content hierarchy. The diagram below records the existing overview requirements and accepted detail sequence; it introduces no new controls or layout decision.
- **Pass 2 — interaction states: initial 8/10.** Empty/missing/partial data and result counts are covered, but enhancement failure and the explicit no-match recovery treatment need decisions. A 10 supplies a state table and clear recovery without implying a complete legislative catalog.
- **D4 — accepted:** user selected A, retain the full list with a quiet unavailability notice and disabled interactive controls on enhancement failure. No loading animation, prominent warning or reload action. The same readable-first contract applies before initialization and without JavaScript.
- **D5 — accepted:** user selected A, make “Suche und Filter zurücksetzen” the primary no-match recovery. Clear query/year, return to page one and retain sort order. The message concerns matches in the recorded collection, not whether a law exists.
- **Pass 2 — interaction states: intermediate 9/10.** D4 settles enhancement failure and D5 settles unsuccessful-search recovery. The remaining issue is the destination offered when the publication itself contains no law entries.
- **D6 — accepted:** user selected A, make “Sitzungen ansehen” the empty-publication primary action, with source/method access secondary. Show the coverage explanation and omit controls that cannot produce entries.
- **Pass 2 — interaction states: 8/10 → 10/10.** D4–D6 specify readable-first initialization/failure, no-match reset and the distinct empty-publication recovery. The state table records success, missing/partial fields and static source navigation without inventing an acquisition status or loading phase.
- **Pass 3 — visitor journey: initial 8/10.** Find/open/read/source/return and empty-state recovery are specified. The remaining gap is exact overview orientation copy: purpose first versus coverage first. The storyboard below records already specified/approved outcomes, not a new feature.
- **D7 — accepted:** user selected A, show “Finde Gesetzesvorhaben und lies nach, wie sie im Bundestag beraten wurden.” beneath the heading, with “Die Liste zeigt Vorhaben aus den hier ausgewerteten Sitzungen, nicht alle Gesetzesvorhaben.” beside the result count. Keep both visible before the results; no technical pipeline introduction.
- **Pass 3 — visitor journey: 8/10 → 10/10.** D7 makes the first-screen job concrete; D3–D6 already supply the reading order and recovery paths. The storyboard includes source checking and return navigation without adding new controls.
- **Pass 4 — visual specificity / generic-layout risk: initial 8/10.** Overview is Operate and detail is Read. Purpose, copy, section jobs and restrained motion are specific. The outstanding visual decision is whether overview entries retain bordered cards or use separated rows. Detail surfaces remain within the existing reading-column/supporting-context layout; precise component sizing is evaluated separately in Pass 5.
- **D8 — accepted:** user selected A, use plain overview rows with subtle divider lines and vertical space, retaining full titles and the single title link. Do not retain individual rounded-card surfaces or add shadows/hover lifts.
- **Pass 4 — visual specificity / generic-layout risk: 8/10 → 10/10.** D8 settles the remaining overview boundary treatment. The purpose-first introduction, exact recovery copy, section jobs, recorded-data vocabulary and limited interaction motion distinguish a useful parliamentary view from a generic dashboard. Typeface replacement is excluded by the incumbent-preserving scope, not silently waived as a new design choice.
- **Pass 5 — design-system alignment: initial 7/10.** Existing colors, themes, controls and page headings are reusable. No DESIGN.md exists; the concrete component gap is a defined bill-content type scale, especially essential speaker/document/event text versus supplementary figures. D9 will settle that scale without a new font or global site redesign.
- **D9 — accepted:** user selected A, retain 34px/28px page titles and 21px section headings, with 16px essential text and 14px supplementary figures. Separate names, affiliations and figures; keep the incumbent font. Apply the same readability contract to event/document text, not only speakers.
- **Pass 5 — design-system alignment: 7/10 → 10/10.** D9 settles the content scale. Existing palette/theme/visited/focus values and spacing patterns supply the remaining baseline; new selectors stay scoped to bill pages because the vote archive/MP pages reuse `bill_styles()`. No global design-system or font replacement is required by this scoped plan.
- **Pass 6 — responsive and accessibility: initial 8/10.** D3 settles reading order, the shared-header contract settles navigation, and the plan already requires keyboard/focus/touch explanations, theme checks and reduced motion. The remaining layout decision is whether phone search/year/sort controls stay fully visible or put secondary controls behind disclosure (D10). Record exact viewport/control behaviour after that decision, preserving essential accessibility constraints for either choice.
- **D10 — accepted:** user selected A, all search/year/sort controls remain visible. Stack them on phones, use search above paired selectors on tablets, and one row on desktop. Preserve visible labels, minimum 44px control height and keyboard access.
- **Pass 6 — responsive and accessibility: 8/10 → 10/10.** D10 supplies the missing control layout. The viewport/accessibility specification below combines that choice with D3's source order, D9's reading scale and the existing shared header; no extra navigation/disclosure component is introduced.
- **Pass 7 — unscored decision register: one new issue.** Actual planned pagination controls change the displayed twenty-entry subset, but the plan does not specify where scroll/focus should go after a page change. The hierarchy diagram places pagination after results, so retaining the bottom position can require another long scroll to begin reading the new set. D11 will settle this explicit navigation transition. Search/filter typing still retains focus under the existing feedback contract.
- **D11 — accepted:** user selected A, deliberate previous/next page navigation moves scroll/focus to the updated result summary at the start of the new set. Search/filter typing continues to retain focus. Do not add animated scrolling.
- **Pass 7 — unscored decision register: 9 resolved, 0 deferred, 0 unanswered.** D3–D11 each have an individual user answer. D1/D2 are review-routing choices and do not count as design decisions. No additional in-scope decision remains after checking the actual proposed controls, source/display semantics and accepted exclusions. Engineering mechanics and rendered validation remain required work, not unresolved design choices.

### Responsive and accessibility contract

| Viewport | Overview controls/content | Detail and shared navigation |
| --- | --- | --- |
| 320px / 390px phones (through 640px) | Search, year and sort full-width in that order; labels always visible; result range/reset/pagination wrap; full result titles and source metadata wrap; existing 14px horizontal shell padding | D3's single-column source order; three separate speaker lines using D9; section links wrap in normal flow; existing compact shared header |
| 768px tablet (641px–900px) | Search full-width, year and sorting paired beneath; no collapsed secondary filters; existing 22px shell padding | Single-column detail at the incumbent 900px collapse; compact shared header below 1024px |
| 901px–1023px | Same visible tablet controls | Incumbent desktop main/supporting-column layout can resume above 900px; sidebar speaker text wraps independently; compact shared header remains |
| 1024px and wider | One control row; search gets remaining space; divider-separated entries | Retain main/supporting-column layout and existing 360px sidebar; all eight shared destinations visible; no page-local replacement menu |

Preserve one main content landmark, a logical heading outline, labelled local section navigation, visible field labels and native input/select/button/link semantics. Search/filter typing and sort changes announce the result count politely while keeping focus on the active control. Deliberate pagination moves focus/scroll to the new result summary under D11; avoid duplicate screen-reader announcements of that focused summary. Do not use placeholder-only labels, custom select/menu roles, focus traps or autocomplete suggestions not requested by this plan.

Use the existing shared focus ring and visited-link distinction. Controls have at least 44px touch targets; essential text has at least 4.5:1 contrast in both themes. Keep text and controls usable at 200% zoom and 320px reflow without page-level horizontal scrolling. Reading paragraphs/explanations stay within approximately 65–75 characters per line when space permits; headings and source lists wrap within their actual column. Headers stay closer to their own content than to the preceding section using the incumbent section/list spacing.

Native additional-speaker/raw-data disclosures remain keyboard operable and do not conceal essential coverage/status caveats. Tooltip content is real accessible text, opens on hover/focus, remains readable when entered with the pointer, dismisses with Escape, and has touch-accessible glossary links. Reduced motion removes transitions; no content starts hidden for an animation. These are implementation/verification requirements for the already specified accessible explanations, not optional follow-ups.

### Visitor journey storyboard

| Step | Visitor does | Likely feeling | Plan support |
| --- | --- | --- | --- |
| 1 | Lands on the law overview | Curious, wants an immediate way to find a law | Clear heading/search, purpose-first introduction and visible coverage by the result count (D7) |
| 2 | Enters a title or document number, optionally narrows the year | In control rather than facing hundreds of entries | Whole-collection search/filter/sort, match count, twenty-result pages |
| 3 | Finds no matching entry or no published law entries | Needs a next step, should not infer the law does not exist | D5 reset for no matches; D6 sitting-catalog recovery for empty publication |
| 4 | Opens the linked title | Oriented about which law and which recorded event | Full title, compact recorded context, no duplicate Details/Follow action |
| 5 | Reads timeline, then debates/speakers | Understands the parliamentary discussion | D3 reading order, named section links, clear speaker affiliation/role and counts |
| 6 | Encounters an unfamiliar parliamentary term | Can learn without losing essential context | Hover/focus explanation and touch-accessible glossary; critical caveats stay visible |
| 7 | Checks an official document, vote or person profile | Can verify rather than relying on a status guess | Primary-source links, optional resolvable profile links, accurate vote/document labels |
| 8 | Returns to the overview | Can continue without repeating work | URL state and Back restoration of query/year/sort/page |

Time horizons: within five seconds the title and search identify the task; within five minutes a reader can find a law, understand the record and reach a source; on repeat visits, predictable ordering and honest coverage maintain trust. Long-term trust does not depend on invented lifecycle status or new accounts/notifications. No additional journey finding remains after D7.

### Interaction-state coverage — existing contracts and D4

These pages are statically generated; browser navigation loads their HTML. Filtering uses records already in the page. There is no visitor-operated acquisition request, retry loop, background fetch or loading skeleton. Each row states visible behaviour, not an inferred backend status.

| Feature | Loading | Empty | Error | Success | Partial |
| --- | --- | --- | --- | --- | --- |
| Overview search/filter/sort | Full static list remains readable; controls disabled until ready; synchronous initialization, no spinner (D4) | No matches: explanatory message and “Suche und Filter zurücksetzen” clears query/year (D5). Empty publication: coverage explanation and “Sitzungen ansehen”; method access secondary, no ineffective controls (D6) | All entries shown, controls disabled, quiet search-unavailable notice (D4) | Matching titles, activity dates, counts and active criteria; all matches considered before pagination | Coverage note says the list contains the generated/recorded procedures, not every law; missing dates remain under “Alle Jahre” |
| Pagination and URL state | Inactive until enhancement succeeds (D4) | No pages of results when no matches; D5 reset returns to page one, with chosen sort retained. Empty publication has no pagination | Failure restores full static list and unfiltered total (D4); no misleading current-page count | Twenty entries per page, range/total, previous/next; explicit page change focuses/scrolls to the new summary (D11); criteria changes reset to first page; Back restores view | An entry remains findable regardless of its original page; no pagination limit on no-JS/print reading |
| Detail context/timeline | Ordinary document navigation; no new loading control | Missing latest date/source stays explicitly unavailable; no invented current status | Broken external services use normal browser navigation behaviour; do not claim a source is available when no URL exists | Law title and latest recorded context; dated event groups retain all distinct source links | Latest observed event does not assert the current legal status; equal-date entries do not invent procedural order |
| Debates and speakers | Static content, including native additional-speaker disclosure | Say no debates/speeches are linked in the recorded data; keep other sections/source access available | Unresolved person profiles use plain names instead of broken links | Names, Fraktion/Sprechrolle and speech figures are separate; linked profiles/dossier anchors remain available | Show the total; after twelve speakers the remainder is reachable through native disclosure; explain coverage |
| Recorded roll-call votes | Static content | “Keine namentliche Abstimmung in den erfassten Daten verknüpft”; do not infer that no vote happened | Missing vote URLs remain non-links; official-source navigation errors use browser behaviour | Available vote titles/source links | Counts refer only to linked namentliche Abstimmungen |
| Documents/glossary/source data | Static text and native links/disclosures | Missing document/source fields get honest labels; raw data remains optional reading | Unknown parliamentary terms keep their source label; unavailable source URLs are not fabricated | Document numbers, types/authors and available explanations/source links | Mixed document list includes protocol files; source/role labels preserve their actual meaning |

### Screen hierarchy and navigation flow

```text
Overview
  Shared navigation (existing)
  Gesetzesvorhaben heading + brief task introduction
  Search / activity year / sorting
  Coverage + result count + reset when applicable
  Result entries: linked title → date/event → source counts
  Pagination
      │ title link
      ▼
Detail
  Shared navigation + Alle Gesetzesvorhaben
  Law title → latest recorded context
  Section links (in content order)
  Mobile reading sequence (D3):
    Verlauf
    Debatten ────────────────► Sitzung dossier/TOP
    Rednerinnen und Redner ──► person profile when available
    Abstimmungen ────────────► linked roll-call source
    Dokumente ───────────────► official source document
    Quellen und Daten ──────► method / collapsed raw data
      │ Back to overview
      ▼
  Restore the overview's query/year/sort/page
```

Scan priorities: overview title/search, matching law titles, recorded activity; detail law title/context, its timeline, discussion and participants. Source access remains direct.

### What already exists

Reuse the current bill palette and type hierarchy in `bill_styles()`, the German date helpers, catalog/roster metadata-search patterns, shared visited/focus styles and theme controls, primary-source links, and the Puls glossary convention. The approved shared header uses “Wochenübersicht” and “Sitzungen” as the two visible routes below 1024px, with the remaining routes in native “Weitere Bereiche”; do not reopen or replace it here.

There is no DESIGN.md. This scoped refinement uses existing styles and the shared-header decisions recorded in `docs/plans/frontpage-design.md`, rather than inventing a new visual identity. Do not copy that homepage's title sizes or page width into bill pages without a separate design decision.

### Existing values to reuse — evidence, not a new design system

| Existing role | Source value / contract |
| --- | --- |
| Light text / secondary text | `--ink: #171a1f`, `--muted: #606a78` |
| Light page / surface / divider | `--paper: #f7f8fa`, `--panel: #ffffff`, `--line: #d9dee6` |
| Light link / visited link | `--blue: #174ea6`; existing shared teal visited-link treatment |
| Dark theme | Reuse shared theme variables and controller; do not hardcode light colors into new bill selectors |
| Bill shell | Existing maximum 1280px; 22px horizontal padding, reduced to 14px at the existing phone breakpoint |
| Bill title / section headings | Existing H1 34px / 1.1, 28px on phones; H2 21px / 1.25, retained by D9 |
| Typeface | Existing Inter/UI fallback stack, retained within this scoped refinement; separate site-wide typeface work is not reopened |
| Space and boundaries | Existing 8px/12px/16px/22px spacing vocabulary and `--line`; plain overview row boundary by D8 |
| Shared navigation | Existing semantic active link, minimum 44px control height and native compact disclosure below 1024px |
| Link feedback | Existing shared visited distinction and visible focus; title/source links remain actual links |

Treat these recorded values as the incumbent baseline. D9 individually approves the readable content scale below and D10 the responsive control layout. Mapping a value here does not itself approve a new treatment.

### Approved bill-content roles

| Role | Size / hierarchy | Behaviour |
| --- | --- | --- |
| Page title | 34px desktop, 28px phone, existing 1.1 line height | Full title, highest content prominence, naturally wrapping |
| Section heading / overview result title | 21px, existing 1.25 line height | Result title is the clearly styled link; section heading stays attached to its content |
| Essential reading / document / event text | 16px, approximately 1.5 line height | Full labels and sources; no table-column clipping |
| Speaker name | 16px semibold, first line | Profile link where resolvable; otherwise plain text |
| Fraktion or Sprechrolle | 16px regular, next line | Full label, wrapping independently of the name/figures |
| Supplementary speech figures / supporting metadata | 14px, separate from essential labels | Quiet but legible; do not shrink essential content to this scale |
| Spacing baseline | Existing 16px panel padding and 12px section/list-grid gaps | Reuse the existing grid/list patterns; no new spacing system or decorative shadows |

Dates/figures can use tabular numerals within the existing font. The dominant law title, then date-group/section headings, then essential row text establish the reading hierarchy. Scope these roles to new bill markup rather than changing every shared `.doc-row` consumer.

### Independent review findings — proposed, not accepted fixes

| Finding | Evidence | Consequence | Disposition |
| --- | --- | --- | --- |
| Mobile detail order was unspecified | “Stack sections in a useful reading order”; current renderer puts the main column before the speaker/debate aside | A long document list can put debates and speakers far down the mobile page | Resolved by D3=A; document/anchor order updated |
| Enhancement failure/loading fallback was unspecified | Controls, URL state and pagination are planned; no-JS readability is required but initialization failure behaviour was not explicit | A partially initialized script can leave a hidden list or unusable controls | Resolved by D4=A; readable-first lifecycle and quiet fallback recorded |
| Introductory and recovery copy was not concrete | “Brief German introduction”, “plain-language coverage note”, and distinct empty states lacked final copy | Technical prose or an unhelpful empty state could survive the refinement | Resolved by D5–D7: no-match recovery, empty-publication recovery and purpose/coverage introduction |
| Some visual instructions remained subjective | “Compact”, “quiet”, “secondary” and “deliberate gaps” did not define sizes or spacing | Implementation could retain crowding despite improved markup | Resolved by D8–D10: overview boundaries, existing values/readable scale and explicit responsive control layout |

The primary checked these findings against the plan and renderer. D3–D11's individually approved remedies are accepted. The independent review's four findings and the primary's final-register pagination transition are resolved.

### Independent litmus evidence

Overview mode: **Operate**, find and browse a law. Detail mode: **Read**, understand its recorded procedure and follow sources.

| Check | Independent reviewer | Primary assessment |
| --- | --- | --- |
| Product/task clear in first screen | Initially NO: task/coverage copy was not written | YES after D7: purpose first, explicit coverage by the count, visible search |
| Strong visual anchor | Initially NOT SPECIFIED | YES after D8–D9: dominant law title and linked result headings; compact recorded context, no competing metric tiles |
| Scannable headings | YES | YES: named detail sections and overview controls |
| Each section has one job | YES | YES: finding/browsing versus distinct detail sections |
| Cards necessary | Reviewer says cards are not required | NO: D8 intentionally uses separated overview rows; no decorative card requirement |
| Motion meaningful | YES | YES: feedback on real controls/explanations, with reduced motion |
| Works without decorative shadows | YES | YES: no decorative shadow dependency is proposed |

No new hard-rejection finding was established by the independent review. Its recommendations are single-model evidence; no external-model consensus is claimed. All six scored passes and the unscored decision register are complete. These are plan-completeness assessments, not claims of validated rendered quality.

### Pass 4 — primary visual checks

| Hard-rejection pattern | Evidence / result |
| --- | --- |
| Generic SaaS card grid as first impression | No proposed grid; aggregate statistic boxes are removed and D8 selects plain result rows |
| Beautiful image with weak brand | No new imagery or brand replacement in scope |
| Strong headline without action | Search/filter area is the overview action; detail has source and section links |
| Busy imagery behind text | No imagery behind text proposed |
| Repeated mood statements | Purpose-first utility copy and distinct factual sections; no mood copy |
| Carousel without narrative purpose | No carousel proposed |
| App made of stacked cards rather than layout | D8 replaces overview cards with divided rows; detail keeps a reading/supporting-context layout and removes the prominent metric boxes |

No definite hard rejection is established by the proposed plan. Evaluate the scoped Operate/Read surfaces without imposing marketing heroes, a new font system or entrance animation. Preserve the incumbent stack under the existing site's pending separate typeface work; D9 resolves the scoped content type scale in Pass 5. The specific bill title/result links anchor the content, and no decorative shadow or image is needed for that hierarchy.

## NOT in scope

1. Global visual identity, typeface or DESIGN.md replacement: preserve the incumbent site; the existing `TODOS.md` item “DESIGN.md, tokens and a typeface decision via /design-consultation” already tracks broader design-system work.
2. A framework, search backend or document/speech full-text search: metadata lookup over the existing collection covers the defined visitor task.
3. Legislative acquisition/SQLite migration or changes to `bills.json` identities/counting: this refinement fixes presentation and accurate labels, not the pipeline contracts.
4. Speculative policy-topic tags, authoritative lifecycle filters or progress bars: the current bill fields do not establish these meanings; do not manufacture them for the UI.
5. Accounts, notifications, saved-law infrastructure or a replacement Follow feature: the requested simplification removes the ineffective marking rather than expanding it.

## Approval reconciliation and TODO disposition

Each new design remedy D3–D11 has its own user answer, all A. Apply only those outcomes and the original task's defined overview/detail/glossary improvements. The review-routing answers D1/D2 approve neither remedies nor new implementation scope. Mapping incumbent tokens, recording a storyboard and making verification explicit do not create extra design decisions.

All in-scope accessibility, empty-state, responsive and navigation checks are required implementation work below. **No new deferred TODO proposals remain.** Do not move necessary verification into optional follow-up debt. The pre-existing global design-system/typeface TODO remains unchanged; no TODOS.md edit or extra scope approval is needed.

## Implementation Tasks

Synthesized from the original scoped findings and this review's individually approved remedies. Run with Codex or Claude Code; check off as each task ships. Estimates assume the current standard-library/static renderer, reused patterns and bounded browser verification; browser/source checking compresses less than mechanical editing.

- [x] **T1 (P1, human: ~4h / agent: ~20min)** — Overview — Replace the unbounded card list with searchable, filterable, paginated rows.
  - Surfaced by: original overview findings; D7 purpose/coverage, D8 row boundaries and D10 visible responsive controls.
  - Files: `scripts/build_dip_pulse_site.py`, `tests/test_bills.py`.
  - Verify: title/non-primary-document lookup over all entries; year/sort combinations; twenty-result pages; full titles; no stats/Follow/duplicate Details; phone/tablet/desktop controls; generated links and scoped-CSS regressions.
- [x] **T2 (P1, human: ~2h / agent: ~15min)** — Overview states — Implement readable-first enhancement, useful recovery and restored navigation state.
  - Surfaced by: Pass 2 / D4–D6 and Pass 7 / D11.
  - Files: `scripts/build_dip_pulse_site.py`, `tests/test_bills.py`; smallest runnable interaction check chosen during engineering review.
  - Verify: disabled/unavailable JavaScript and an injected initialization/interaction failure retain all entries; no-match reset clears query/year and preserves sort; empty publication links to sittings; explicit pagination focuses the new summary; typing retains focus; Back restores query/year/sort/page; no-JS/print reading exposes all entries.
- [x] **T3 (P1, human: ~3h / agent: ~20min)** — Law detail — Clarify content hierarchy, source labels and complete speaker access.
  - Surfaced by: bill-field semantics, cramped/shared speaker grid, silent twelve-speaker limit and D3's mobile reading order.
  - Files: `scripts/build_dip_pulse_site.py`, `tests/test_bills.py`.
  - Verify: DOM/anchor order matches D3; same-date timeline events retain distinct sources; documents include protocol files under accurate labels; author aggregation is not called the initiator; linked roll-call votes are reachable; all speakers are accessible and profile/source links resolve.
- [x] **T4 (P1, human: ~2h / agent: ~15min)** — Bill styles — Apply readable scoped component sizes and accessible responsive layouts.
  - Surfaced by: Pass 5 / D9 and Pass 6 / D10, with D8's divided rows.
  - Files: `scripts/build_dip_pulse_site.py`; shared theme helpers only if reuse requires them.
  - Verify: 16px essential/14px supplementary scale; long names/roles/documents do not overlap; 320px/390px/768px/900px/1024px/desktop reflow and 200% zoom; minimum 44px controls; focus/visited distinction and contrast in both themes; MP/vote-archive styling remains correct.
- [x] **T5 (P1, human: ~2h / agent: ~25min)** — Explanations — Extend the existing glossary with accessible parliamentary explanations and restrained feedback.
  - Surfaced by: original requested explanations and the existing CSS-only Puls pattern's accessible-text/dismissal limits.
  - Files: `scripts/render_dip_pulse_html.py`, `scripts/build_dip_pulse_site.py`, focused existing renderer tests.
  - Verify: new definitions checked against official primary sources before publication; existing Gesetzgebung text reused; mouse/focus/touch access, Escape dismissal, pointer entry and viewport-edge behaviour; unknown terms remain source labels; reduced motion; status/coverage caveats stay visible.
- [x] **T6 (P1, human: ~2h / agent: ~25min)** — Validation — Prove the complete reader journey and shared-style boundaries.
  - Surfaced by: acceptance checks across all passes; no in-scope verification is deferred.
  - Files: relevant existing tests, offline demo/publication output and this plan's task checkboxes.
  - Verify: `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`, Python compilation, offline demo/publication validation and a bounded Chrome DevTools desktop/mobile/keyboard/theme/print pass. Include a law with long names, more than twelve speakers and same-date events, plus MP/vote-archive shared-CSS checks. Correct findings together and confirm once. No new test framework is required.

_Pass 3 contributes orientation/source/return requirements to T1–T3; it creates no separate feature task. Pass 4 contributes row treatment to T1/T4. Pass 7 contributes the approved pagination transition to T2; no further task is invented._

The machine-readable task artifact is written to the configured gstack project-state directory: `/Users/Luca/.gstack/projects/LucaAlv-poliwatch/tasks-design-review-gesetzesvorhaben-20261008-53602.jsonl`.

## Design Review Completion Summary

| Review area | Before → after approved fixes / result |
| --- | --- |
| System audit | Overview + law details; no DESIGN.md; incumbent styles/shared navigation reused |
| Step 0 impression | 7/10; both pages reviewed evenly |
| Pass 1 — information architecture | 8/10 → 10/10 |
| Pass 2 — interaction states | 8/10 → 10/10 |
| Pass 3 — visitor journey | 8/10 → 10/10 |
| Pass 4 — visual specificity / generic-layout risk | 8/10 → 10/10 |
| Pass 5 — design-system alignment | 7/10 → 10/10 |
| Pass 6 — responsive / accessibility | 8/10 → 10/10 |
| Pass 7 — decisions (unscored) | 9 resolved, 0 deferred, 0 unanswered |
| NOT in scope | 5 exclusions recorded |
| What already exists | Recorded with source values and shared-header decisions |
| TODOS.md updates | 0 new proposals; existing global design-system TODO unchanged |
| Mockups | 0 generated / approved; designer binary unavailable |
| Individually approved new decisions | 9: D3–D11; D1/D2 excluded as review routing |
| Implementation tasks | 6, all include required verification |
| Overall design-completeness score | 7/10 → 10/10, lowest of Passes 1–6 |
| Completion status | DONE_WITH_CONCERNS: no rendered mockups or external-model review; application UI/tests not changed or run |

The scoped plan is design-complete. This is not a visual-quality score for a finished site. Engineering review must validate the DOM/sidebar arrangement, actual browser state/failure handling and proportionate runnable interaction checks; perform visual QA after implementation.

## Unresolved Decisions

None within this design scope. Mockup/external-model availability are coverage limitations, not silently defaulted design decisions. Engineering review and implementation validation remain required.

## Review Readiness Dashboard — design-review snapshot

Project history is context, not clearance for a different plan. The latest historical engineering review concerns `docs/plans/frontpage-design.md`, has `issues_open`, and predates HEAD by one commit; it does not clear this Gesetzesvorhaben plan. `skip_eng_review` is false.

| Review | Project records including this run | Last relevant result | Required |
| --- | --- | --- | --- |
| Eng Review | 3 | ISSUES OPEN (PLAN), 2026-10-07; frontpage plan, not this plan | Yes |
| CEO Review | 0 | Not run; no fundamental product-direction gap found here | No |
| Design Review | 2 | CLEAR (FULL), this plan, 2026-10-08 | No |
| Adversarial | 0 | Not run | No |
| Outside Voice — CEO/Eng plan phase | 3 | UNAVAILABLE, 2026-10-07; no completed external coverage for this plan | No |

Design-phase independent completeness review: GPT-6 Luna completed one native review with four findings, resolved through the individual decisions above. Claude Code was not invoked because the user reported its usage limit. No native fallback is presented as completed external coverage. **Dashboard verdict: NOT CLEARED for implementation/shipping; engineering review required.**

## Engineering review

Target: `docs/designs/gesetzesvorhaben.md`, branch `main`, commit `9e1d836`, 2026-10-08. Report destination is this selected plan. This is a review of proposed work against current source/tests, not an implementation or acceptance-test run. The user chose A to run engineering review after the completed design review. All D3–D11 approvals remain fixed.

### Startup and evidence

The design-doc finder selected this plan. PRODUCT.md supplies the product context; the brain-cache helper could not update its metadata under the sandbox and has no usable cached digests, so no unavailable brain content is claimed. The existing product and recorded approvals already answer the product/scope questions. Aside was unavailable; primary MDN documentation was checked through the web tool. No new framework, provider or dependency is recommended.

A read-only GPT-6 Luna explorer audited existing tests/tooling. The primary read the bill collector/script/renderers/styles, catalog script, glossary rendering, bill/header/demo tests and CI. That explorer supplies test evidence only; it is not credited as an independent Outside Voice.

Prior learnings applied: `macos-python-default-below-floor` (10/10) fixes the interpreter choice; `render-mutates-cached-dossier` (10/10) reinforces presentation-only transformations without mutating bill/report inputs; `qa-macos-real-tmp-path` (10/10) selects /private/tmp for local fixtures. Relevant history includes v0.17 homepage/navigation, speaker-identity work and the Reden/Beiträge distinction. Existing broader counting/store and design-system TODOs do not block this presentation work. No unrelated TODO is added.

### Scope Challenge

**No issues found. Scope accepted as-is.** Keep all six design implementation tasks and five exclusions. No feature cut, new service or shared filtering framework is justified.

Estimated changed implementation paths: two renderer modules; `tests/test_bills.py`, `tests/test_build_dip_pulse_site.py`, `tests/test_demo_site.py`; and a small future `tests/bills_browser_check.js`. Six code/test paths, zero new classes/services. This plan is the separate review artifact. PRODUCT.md needs no mandatory edit: bounded metadata lookup does not introduce free document/speech full-text querying. The complexity selector is therefore not triggered.

Reuse map:
- [Layer 1] `render_catalog_script` at build_dip_pulse_site.py:8406 supplies token AND matching, filtering, reset and DOM-row sorting patterns. Reuse the ideas; it lacks pagination, URL restoration and fault recovery, so do not copy it unchanged or migrate its callers.
- [Layer 1] `pulse_html.esc`, date/count formatting, `source_url`, `_bill_event_href`, `mp_page_href`, native disclosures and shared header/theme styles already own the relevant boundaries.
- [Layer 1] `write_bill_pages` at :6218 writes the overview/details and unchanged bills.json through the existing publication flow; no new deployment artifact or visitor data acquisition is needed.
- [Layer 1] Existing glossary anchors/text and sources renderer are the explanation source; keep parliamentary terms distinct from the DIP Vorgangstyp classification.
- [Layer 1] Native browser URL/history and CSS cover this enhancement. [MDN History](https://developer.mozilla.org/en-US/docs/Web/API/History) documents the native state API. A native popover may support the already approved explanations; [MDN Popover](https://developer.mozilla.org/en-US/docs/Web/API/Popover_API/Using) documents its behaviour. Do not rely solely on newer hover-invoker features or add a library.
- No build/publish CI change is required: the existing offline renderer writes these HTML pages and sources.html; validation stays in the current Python 3.11–3.13 CI matrix.

Dispositions: existing scope retained; no scope remedies or new approval question.

### 1. Architecture review

**No issues found beyond implementation mechanics already required by the approved contracts.**

Use escaped per-row metadata derived at build time from full title, every document number, latest activity date and stable bill identity. Read rows once at initialization. Do not fetch `data/bills.json`: it also contains raw agenda evidence unnecessary for filtering. The full static list is the source of readable fallback and print output; the script derives a visible subset, never deletes records.

Proposed flow, not current implementation:

```text
Existing report JSON + reviewed speaker lookup
  -> collect_bill_pages (unchanged identities/counting/source data)
  -> write_bill_pages
       +-> render_bills_index
       |    escaped full rows + disabled controls + source links
       |    -> index-only bill script
       |         parse URL -> normalize controls -> compute matches
       |         -> sort -> clamp page -> show 20 -> range/criteria
       |         -> write URL -> enable ready controls
       |         any failure -> show ALL rows + disable + D4 notice
       +-> render_bill_detail
       |    sources/profile href guards + all static sections
       |    -> native extra-speaker/raw-data disclosures
       |    -> optional explanation enhancement, glossary link fallback
       +-> bills.json (same data contract)
Shared definitions -> render_sources_page -> real glossary destinations
Existing publication validation -> staged generated HTML/JSON
```

URL inputs are untrusted state, not markup. Validate sort against the supported values and year against available options; parse/clamp page to a positive valid result page; safely default malformed state. Preserve unrelated parameters and fragments. Use `textContent` for counts/query feedback. Do not introduce query-string HTML interpolation, arbitrary hrefs, storage or a server.

Initialization must be transactional from the reader's perspective: install/validate controls and handlers before showing a subset; catch initialization and each interaction/history update; fallback restores row visibility, full total and inactive pagination. Synchronous work avoids request races. Restore from the URL on history traversal and document return; this is not a new deliberate pagination click and must not force D11's focus movement.

Use one main landmark whose section nodes follow D3's order. Desktop grid placement can retain the 360px supporting column without moving DOM nodes on resize or grouping all discussion after documents in an aside. Mobile is the natural document order. Stable section IDs support anchor navigation; missing section data retains honest empty copy. No JavaScript tabs or duplicate section copies are needed.

Keep the glossary link usable without enhancement, with real descriptive text and safe anchors. Scope the explanation controller to bill pages; unavailable popup support retains the glossary link. Important caveats remain visible. New definitions require official primary-source checking during implementation, as already specified; this review adds no unverified legal definition.

Dispositions: D3/D4/D11, the original metadata/source contracts and T1–T5 carry these necessary mechanics. No new architecture policy, migration or extraction is approved here.

### 2. Code quality review

**No issues found requiring a new remedy.**

Replace the follow-only script for the overview; do not load filtering code on law details. Repository search found follow storage/attributes only in the bill renderer. Remove those specific callers/rules, not common action/open-button/metric/document styles still used by MP/vote pages. Leave old browser storage inert; no storage migration is needed.

The shared-code rubric does not justify an extraction: catalog and proposed law filtering differ in paging, error recovery and history; the roster has its own data/columns. Similar selectors alone do not establish a common contract. No callers are migrated and no speculative line-saving claim is made. Dedicated bill row/speaker/explanation selectors improve isolation.

Use existing escaping and guarded source/profile-link helpers. Group events for display without changing the collector or collapsing distinct same-date sources. The inspected parser helper `validate_dip_protocol.xml_top_fields` (:2276–2304) derives `xml_speakers` from `top["speeches"]` and keeps `xml_contributions` separate. The proposed “Reden” label therefore matches the existing normalized input boundary; preserve counting semantics.

No inline complex-service diagram is needed because no model/service is introduced; update the existing bill flow comments alongside the implementation rather than leaving “Folgen” and “top 12” comments stale.

Dispositions: scoped styles and display-only transformations remain required by T3/T4 and D3/D9/D10. No separate framework, shared search abstraction or counting-module work.

### 3. Test review

Current evidence is distinguished from planned coverage. No new test or fixture is created during this review.

```text
CODE PATHS (12 inventory units)                 USER FLOWS (10 units)
collect_bill_pages                              proposed overview/detail journey
 + [★★★ TESTED] identity/companions               + [GAP] title + secondary-number lookup
 + [★★★ TESTED] speaker occurrence identity       + [GAP] combined criteria + no-match reset
write_bill_pages / render_site                   + [GAP] explicit pagination/focus
 + [★★★ TESTED] page/link/stale-page contract      + [GAP] shared URL / Back / Forward
existing glossary + sources                      + [GAP] no-JS + print all rows
 + [★★ TESTED] stable anchors/unknown type         + [GAP] initialization/interaction failure
proposed bill enhancement                        + [GAP] mobile read -> all speakers -> source
 + [GAP] title/all-document token matching        + [GAP] hover/focus/touch/Escape explanation
 + [GAP] year/missing date and German sort        + [GAP] zoom/themes/keyboard/shared surfaces
 + [GAP] page bounds/range/focus                   + [GAP] complete offline refined publication
 + [GAP] normalized URL + history restore
 + [GAP] ready/failure/no-JS/print lifecycle
proposed detail markup
 + [GAP] ordered sections/all sources/speakers
proposed explanations
 + [GAP] descriptions/dismissal/fallback
new bill-specific style consumers
 + [GAP] isolation + responsive/theme behaviour

COVERAGE: 4/22 inventory units have useful existing tests (18%)
Code paths: 4/12; user flows: 0/10
QUALITY: ★★★:3, ★★:1; 18 uncovered units grouped into 7 findings
Legend: ★★★ behaviour plus boundaries/errors; ★★ happy-path contract.
This is a bounded contract inventory, not measured line/branch coverage.
Future paths remain GAP until implementation and executed proof exist.
```

Existing useful tests:
- `tests/test_bills.py:58–130`: Gesetzgebung classification, companions, occurrence identity, reviewed names and namesakes.
- `tests/test_bills.py:133–180`: generated page identity, entity links and vocabulary; :176/:178 explicitly expect the overview metric/title that this design removes.
- `tests/test_build_dip_pulse_site.py:1113–1164`: publication destinations and stale-page cleanup.
- `tests/test_build_dip_pulse_site.py:1900–1946`: glossary known/unknown labels, depth, safe anchors and sources-page destinations.
- `tests/test_global_header.py:11–120`: shared nav/focus/visited/theme contracts; these do not prove bill layout.
- `tests/test_demo_site.py:20–94`: zero-network build, validation, unsafe-source handling, interrupted publication and bounded scaling; these do not execute bill interactions.

Seven findings, each required proof of already approved behaviour:
1. **[P1] (confidence: 9/10) docs/designs/gesetzesvorhaben.md:106**: “Add focused regression coverage to `tests/test_bills.py` for the changed output/data boundaries”. G1: redesigned overview output has no regression assertion, while `tests/test_bills.py:176` asserts `self.assertIn("Aktuelle Gesetzesvorhaben", index)`. Extend that test to enforce the new heading/coverage, one title link, no stats/follow/details, escaped metadata and full static rows. Keep entity identity, vocabulary and all valid links. **Accepted prior scope**, original request and D7/D8.
2. **[P1] (confidence: 9/10) docs/designs/gesetzesvorhaben.md:35–36**: “Search titles and every associated document number” and “Missing dates remain visible under ‘Alle Jahre’”. G2: no executing metadata/filter/sort test exists; current `render_bill_script` starts with the follow storage key at build_dip_pulse_site.py:5730. Test mixed-case multi-word matching, secondary document number, combined year criteria, missing dates and German deterministic ties through the actual controls. **Accepted prior scope**, overview requirements and D10.
3. **[P1] (confidence: 9/10) docs/designs/gesetzesvorhaben.md:44–46**: “Retain query, year, sort and page in URL parameters” plus D11 focus movement. G3: paging/history/focus is a future script path with no executing test. Check 20/21/40/41 boundaries, criteria reset to page one, D5 sort-preserving reset, invalid URL normalization, URL reload and browser Back/Forward without forced focus. **Accepted prior scope**, D5/D11 and the original state contract.
4. **[P1] (confidence: 9/10) docs/designs/gesetzesvorhaben.md:50,100**: “If initialization or a later interaction fails, restore the complete list” and “Print exposes the complete collection”. G4: lifecycle, fault and print branches have no current proof. Check JS-disabled reading and real pre-ready/post-ready failure variants; print must override pagination/filter hiding and expose all entries. **Accepted prior scope**, D4 and T2/T6.
5. **[P1] (confidence: 9/10) docs/designs/gesetzesvorhaben.md:61–69**: “Keep all distinct events and source links” and the D3 document order. G5: existing renderer uses `(bill.get("speakers") or [])[:12]` at build_dip_pulse_site.py:6108 and repeated detail panels, while rendered detail acceptance is missing. Check 13 speakers, long roles, singular figures, mixed document types, same-date sources, linked/absent votes and resolved/unresolved profiles with one main landmark and matching anchors. **Accepted prior scope**, original detail requests, D3/D9/D10.
6. **[P1] (confidence: 9/10) docs/designs/gesetzesvorhaben.md:79**: “CSS pseudo-element text alone is insufficient as the accessible description”. G6: existing `data-tip` anchor at render_dip_pulse_html.py:2207 supplies pseudo-content, not the proposed real description/dismissal. Extend glossary-output tests and execute focus/hover/pointer-entry/Escape/touch/fallback checks; verify definition sources and target depth. **Accepted prior scope**, requested explanations and the approved accessibility contract.
7. **[P1] (confidence: 9/10) docs/designs/gesetzesvorhaben.md:93**: “Scope new rules to bill-page classes and preserve styles still consumed there”. G7: `bill_styles()` is consumed at build_dip_pulse_site.py:4082 and :6622; shared header tests do not assert those MP/vote layouts after the refinement. Preserve those consumers while proving bill wrapping, 44px controls, contrast, themes, 200% zoom and 320px reflow; validate an offline publication. **Accepted prior scope**, T4/T6 and D9/D10.

Dispositions: G1–G7 accepted as necessary proof carried forward from the original acceptance list and design answers; no optional-depth or new regression-policy question. No LLM/prompt change is in scope, so no eval suite is required.

Smallest runnable browser check: a future `tests/bills_browser_check.js` exercising the real generated fixture in Chrome DevTools. It uses actual controls/events and asserts rendered rows, URL and focus; no fake DOM or copy of the production matching/sorting algorithm. Generate the fixture using test_bills.py's renderer boundary. Add a test-only prelude before the actual emitted script for initialization faults; after-load injection proves only later interaction failure. Keep production free of test-only exports/flags. Python output tests and real-browser evidence remain distinct; no new CI browser framework.

Test Plan saved and read back: `/Users/Luca/.gstack/projects/LucaAlv-poliwatch/Luca-main-eng-review-test-plan-20261008-201946.md`. Each critical/edge case has a value card. No test is retired; obsolete metric/title expectations change inside the existing vocabulary test while its unchanged contracts stay.

### 4. Performance review

**No issues found requiring a new remedy.** Current sample: 562 rows. Source markup size is not measured in this review, and no runtime timing is invented.

Read row metadata once, normalize search once per interaction, filter in a linear pass and sort the matching records with deterministic ties. No SQLite query, remote search, PDF fetch, bills.json load, asynchronous request cache or additional persistence is introduced. Reuse rendered rows and move/hide them instead of reparsing row HTML or rebuilding them from raw JSON.

Twenty-item pagination reduces visible scanning, not the full HTML payload; that is intentional for the approved no-JS/print behaviour. Existing raw JSON detail weight stays a separate known concern, not a new optimization project. Inspect one representative full build during the required browser pass; add workers/virtualization/indexing only if measured latency later warrants a separately scoped change.

Dispositions: retain the static metadata/DOM approach; no performance scope expansion.

### Outside Voice

Reviews remain enabled. Claude Code is not invoked because the user reported its usage limit. The skill's native fallback requires declared Plan, TaskOutput and TaskStop capabilities, which this host does not expose. Its instructions explicitly prohibit substituting a general-purpose agent for that fallback. No fallback is dispatched.

Outside voice unavailable. Continuing to planning decisions and Approval readiness. Coverage: host=codex, outside_provider=claude-code, outside_status=unavailable, outside_attempted=false, phase=plan-review, source=none. The design-phase GPT-6 Luna report remains design evidence only. No independent engineering review, agreement or cross-model consensus is claimed.

### Decision ledger

Each row carries a required implementation/proof consequence of an existing approved contract; it introduces no selectable new policy. No pending comparison grid or engineering remedy question was needed.

| ID | Baseline and actual answer | Evidence / accepted scope | State |
| --- | --- | --- | --- |
| EG1 | Original requested cleanup; D7=A, D8=A | G1: new overview output assertions; preserve title/source/identity contracts | Approved prior scope |
| EG2 | Original metadata lookup; D10=A | G2: actual controls cover all documents, year and sort | Approved prior scope |
| EG3 | Original URL/paging contract; D5=A, D11=A | G3: state bounds, reset, Back and deliberate-page focus proof | Approved prior scope |
| EG4 | D4=A; original print/no-JS acceptance | G4: readable-first and both failure stages, full print list | Approved prior scope |
| EG5 | Original detail/source scope; D3=A, D9=A, D10=A | G5: complete detail content/order/links and data semantics | Approved prior scope |
| EG6 | Original explanations; approved accessibility contract, D9=A/D10=A | G6: source-checked real descriptions and input-method behaviour | Approved prior scope |
| EG7 | Original shared-style/validation acceptance; D9=A, D10=A | G7: MP/vote/header boundaries plus complete responsive checks | Approved prior scope |

Actual engineering remedy answers this invocation: none required; prior answers reused. The user's latest A authorizes this review, not UI implementation or deployment.

**Approval readiness: PASS** for EG1–EG7 against the stated original requirements and individual D3–D11 answer references. No new product behaviour, test framework, optional coverage depth or deferred TODO is silently approved.

### Failure modes

| Proposed path | Realistic failure | Required handling / proof | Reader impact |
| --- | --- | --- | --- |
| Metadata/URL initialization | malformed URL, missing control, history write throws | normalize untrusted state; D4 full-list rollback; G2–G4 browser fixture | All laws remain readable with quiet notice |
| Search/year/sort/page | later handler fails after some rows are hidden | one fallback restores every row/count and disables controls; G3/G4 | No silently stranded subset |
| Browser return | stale saved DOM or popstate not applied | restore URL-derived view without pagination focus; G3 | Criteria/page remain understandable |
| No-JS/print | hidden attribute persists on non-current rows | readable HTML first; scoped print override for all rows; G1/G4 | Complete reading/print access |
| Detail transformation | thirteenth speaker or equal-date source disappears | display-only grouping/native disclosure; G5 | All recorded information stays reachable |
| Definition enhancement | unsupported popup, Escape reopens, edge clipping | real description/glossary fallback, dismissal state and edge checks; G6 | Explanation remains accessible |
| Shared styles/publication | deleted shared selector or broken output links | scope bill selectors; MP/vote/whole-publication checks; G7 | Other pages and source links remain usable |

**Failure modes: 0 critical gaps flagged.** Each path has required handling and planned proof. These are future acceptance requirements, not executed evidence.

### Implementation Tasks — engineering additions to T1–T6

These tasks specify the verification work already included in the six design tasks; do not double-count estimates or create an extra feature lane. Estimates reflect real-browser work, which compresses less than editing.

- [x] **ET1 (P1, human: ~3h / agent: ~30min)** — Overview proof: extend bill-output tests and add the small real-browser check.
  - Surfaced by: G1–G4; owning core tasks T1/T2.
  - Files: `tests/test_bills.py`, future `tests/bills_browser_check.js`; actual index/script in `scripts/build_dip_pulse_site.py`.
  - Verify: all metadata/criteria/sort/page/URL/focus cases, initialization and later failure, no-JS and print. String assertions alone do not pass.
- [x] **ET2 (P1, human: ~1h / agent: ~15min)** — Detail proof: extend a real generated detail fixture with thirteen speakers and complete sources.
  - Surfaced by: G5; core T3/T4.
  - Files: `tests/test_bills.py`, `scripts/build_dip_pulse_site.py`.
  - Verify: D3 DOM/anchor order; all speakers, roles/figures; same-date sources; document/vote semantics; profiles; no data mutation.
- [x] **ET3 (P1, human: ~1h / agent: ~15min)** — Explanation proof: extend current glossary-output tests and real-browser interaction assertions.
  - Surfaced by: G6; core T5.
  - Files: `tests/test_build_dip_pulse_site.py`, future browser check, both renderer modules as already scoped.
  - Verify: stable existing Gesetzgebung destination/text; official new definition sources; real descriptions, hover/focus/pointer/Escape/touch and fallback.
- [x] **ET4 (P1, human: ~1h / agent: ~20min)** — Publication/layout proof: complete the existing offline and shared-consumer checks.
  - Surfaced by: G7; core T4/T6.
  - Files: `tests/test_demo_site.py`, `tests/test_build_dip_pulse_site.py`; existing header tests run unchanged.
  - Verify: full suite, compile and offline demo validation; one batched Chrome DevTools viewport/theme/keyboard/zoom/print pass including MP/vote pages.

_No new implementation tasks from Scope Challenge, Architecture, Code Quality or Performance._ No new deferred TODO proposals.

Task aggregation artifact: `/Users/Luca/.gstack/projects/LucaAlv-poliwatch/tasks-eng-review-20261008-201946.jsonl` (ET1–ET4 appear as T1–T4 within that phase's JSONL).

### Dependencies and parallelization

**Sequential implementation, no parallelization opportunity.** One primary renderer owns all bill markup/styles and the sources-page output; parallel UI workers would collide. Tests travel with the change they protect.

Order: T1/T2 + ET1 → T3/T4 + ET2 → T5 + ET3 → T6 + ET4. Independent tests do not wait for unrelated feature work; run relevant checks after each owning change and the complete validation once at the end. No worktree lanes or concurrent renderer edits are needed.

### Engineering Completion Summary

| Item | Result |
| --- | --- |
| Step 0 | Scope accepted as-is; FULL_REVIEW |
| Architecture | 0 new issues |
| Code quality | 0 new issues |
| Test review | Diagram produced; 7 grouped test gaps mapped to required work |
| Performance | 0 new issues |
| NOT in scope / existing solutions | Preserved five exclusions; explicit reuse map |
| TODOS.md | 0 new proposals |
| Failure modes | 0 critical gaps |
| Unresolved decisions | 0 this review |
| Outside voice | Claude Code unavailable, user usage limit; required native fallback capabilities absent |
| Parallelization | 0 parallel lanes; 1 sequential implementation stream |
| Lake Score | N/A; no new completeness-scored engineering answers |
| Status | DONE_WITH_CONCERNS: required implementation proof remains; no external engineering review |
| Executed validation | Plan/source/test inspection and artifact read-back only; no application test run or UI changes |
| Learnings | No new durable learnings this session; existing project pitfalls applied |

**Unresolved decisions that may bite you later:** none. The seven test gaps are mapped implementation requirements, not missing user answers. The review log remains `issues_open` because findings count includes those required checks; it does not claim a finished UI has passed tests. No repeated design or CEO review is needed for this unchanged scope.

**Suppressed findings:** none. The investigated suspicion that bill totals might include non-Reden was rejected by the parser's separate speeches/contributions output. No counting-policy change is proposed.

## Implementation and validation — 2026-10-09

Implemented the approved scope in the two existing Python renderers, using native controls/disclosures, scoped CSS and small scripts. No dependencies, data-model changes, acquisition refresh or new filtering service were introduced.

- Overview: removed summary metrics, Follow actions and duplicate Details controls; all 562 cached laws remain available through whole-list title/document-number search, latest-activity year, deterministic German sorting and 20-result pages. URL state, Back/Forward, reset, visible coverage and empty/unavailable states are implemented.
- Detail: six sections in the approved reading order, same-date source grouping, mixed document labels, accurate aggregated-author wording, linked votes, separate speaker name/role/count lines, complete speaker disclosure and collapsed source data.
- Explanations: real accessible descriptions, existing Gesetzgebung copy/anchor, official-source glossary entries, native tap navigation, focus/hover handling, Escape, viewport bounds and reduced motion.
- Browser findings fixed: keyboard focus scrolling closed the explanation; a tall sidebar pushed Documents below a large gap; controls misaligned when the year label wrapped; missing dates used empty datetime attributes; verbose TOP labels repeated Tagesordnungspunkt.

### Executed evidence

| Check | Result |
| --- | --- |
| Full stdlib suite | 1160 tests, 1 skipped, OK, 75.591 seconds; final small CSS/label refinements additionally passed all 14 bill tests |
| Compile / syntax / whitespace | Python compilation, Node browser-check syntax and git diff --check passed |
| Offline demo | Rebuilt and explicitly publication-validated /private/tmp/poliwatch-gesetz-site |
| Cached preview | Offline rebuild: 290 cached dossiers, 562 laws, 1039 MP profiles and 217 vote rows; reused export data; bill pages refreshed after final refinements |
| Publication boundary | Explicit validator passed the cached publication and demo; final cached read-back repeated after the last refresh |
| Real Chrome overview | 41-row generated fixture: AND/secondary-number search, all filters/sorts, 21/40/41 pagination, no matches/reset, URL/history, focus and Tab order; existing 562-law preview also inspected |
| Failure handling | Throwing Intl.Collator during initialization and throwing history.replaceState during interaction each restored all 41 rows, disabled controls and showed the quiet unavailable notice |
| No JavaScript / empty | Native sandboxed iframe without scripting showed all 41 rows, disabled controls and noscript guidance; genuinely empty publication showed no controls and its Sitzungen link |
| Print | Separate native headless Chrome PDF from an active one-result search contained all 41 law titles on 7 pages and omitted search controls; /private/tmp/poliwatch-gesetz-print.pdf |
| Detail | 15-speaker fixture verified at 320,390,768,900,1024,1280 CSS px; source order, 12-to-15 disclosure, source grouping, vote link, non-overlap and close timeline/documents spacing passed |
| Glossary | Chrome accessibility tree exposes descriptions; keyboard scroll regression and Escape pass; pointer-entry controller retains content; native mobile tap reached the correct Sources anchor; no console errors on that journey |
| Reduced motion / reflow | Native Chrome forced reduced-motion preference reported true, 0s link transition and no tooltip animation; 640×450 at device scale 2 passed overview/detail as the 200% equivalent reflow check |
| Themes / shared consumers | Desktop/phone screenshots inspected in both bill themes; dark labels/hints contrast 7.76:1; MP profile and vote archive inspected, with no bill-only styles applied |

The browser check is a JavaScript async function in `tests/bills_browser_check.js`, runnable through Chrome DevTools evaluate_script on the generated overview or detail fixture. Generate the fixture with:

```sh
/opt/miniconda3/bin/python3.13 tests/test_bills.py --browser-fixture /private/tmp/poliwatch-bills-browser
/opt/miniconda3/bin/python3.13 -m http.server 8001 --bind 127.0.0.1 --directory /private/tmp/poliwatch-bills-browser
```

Native interactive print evaluation timed out; the user dismissed the dialog and Chrome's separate headless PDF established the print result. DevTools does not expose media preference emulation, so native headless Chrome established reduced-motion behavior. Its keyboard zoom shortcut did not change the emulated metrics; equivalent reflow was verified instead. Screenshot inspection used inline images because MCP screenshot file output rejected both the repo and /private/tmp paths. No Safari/Firefox or screen-reader application run is claimed.

The existing MP dark theme has white warning/field surfaces with low-contrast text, and vote rows already join title/result text tightly. These are outside the Gesetzesvorhaben scope and predate this diff; shared base selectors and theme rules were retained. They were observed during shared-consumer checks, not introduced by the bill-only rules.

All required implementation tasks have executed local proof. Historical review logs remain historical records; no external Claude review, shipping approval, commit, push or deployment is claimed. Local preview: http://127.0.0.1:8000/bills/index.html.

## User feedback follow-up — 2026-10-09

Added 8px vertical and 12px horizontal padding, borders and rounded corners to the six bill-section links; their minimum height remains 44px. Speaker names retain profile links. One recorded speech has a direct “Rede lesen” link; several speeches use a native “N Reden ansehen” disclosure with dated sitting/page links. Following a speech fragment opens that speech's native details and scrolls to it in the dossier, including later hash changes. Malformed fragments are ignored.

The collector now retains exact dossier speech anchors and deduplicates them per bill before counting. Multiple DIP positions for one bill can repeat the same agenda item; those repeated entries previously inflated speaker counts. Shared agenda items remain associated with each relevant bill, with the existing explicit caveat about multiple bills. Source reports and raw procedure evidence remain intact. No dependencies or store schema changes.

Validation: 1161 tests passed (one skipped); focused bill tests cover duplicate positions, two bills sharing an agenda item, multiple sittings, missing/punctuated speech IDs, exact generated dossier anchors, direct/disclosed rendering and unsafe-link rejection. Node syntax and git diff --check pass. The full cached offline build and explicit publication validation pass. Every one of 9274 speech references on 562 bills resolves to a generated anchor in 209 dossiers and matches the deduplicated count. Chrome fixture checks pass at 1280px and 320px; real single/multiple speech navigation passes on desktop and phone, including open text, hash changes and malformed fragments without console errors. Light desktop and dark phone screenshots were inspected; the actual bill page stays within its 390px viewport.

Safari/Firefox and a dedicated screen-reader application were not rerun. Changes remain uncommitted and undeployed. Preview: http://127.0.0.1:8000/bills/bill-326806.html#redner.

## Sitting dossier narrow-screen overflow — 2026-10-09

The speech links above land in sitting dossiers, which overflowed phones. Cause: single-column grid tracks written as bare `1fr` or left implicit size as `minmax(auto,1fr)`, so the widest unbreakable word sets the column width. One TOP heading word, "(Anpassungsverfahrensabweichungsgesetz", widened `.layout`, `main` and `.top-head` on sitting 21/90 to 431px in a 390px viewport (344px at 320px through `.meta-grid`). One unbroken token in an open speech widened `.speech-cards` to 788px on 21/49. `.attention-row` and a vote title link did the same on 21/39 and 20/47.

Fix, in `render_dip_pulse_html.py` only: every single-column fallback in the 1120px and 720px breakpoints, plus `main`, `.speech-cards` and `.attention-row`, now uses `minmax(0,1fr)`. `.meta-grid` on phones uses `repeat(2, minmax(0,1fr))`. A single grouped rule gives the page title, TOP headings, metrics, sidebar row titles, vote titles and speech text `overflow-wrap:break-word` and German hyphenation (`lang="de"`). `hyphenate-limit-chars:12 5 5` keeps short words like "Sitzung" whole; `-webkit-hyphens` covers Safari. The sidebar heading is deliberately excluded. The stylesheet is embedded only in dossiers.

Validation: all 290 dossiers were swept at 390px and 320px with every `<details>` open. With only the layout, `main` and header clamps in place, 84 of 580 page-widths still overflowed, 82 of them inside open speeches. With the final CSS, 0 overflow. At 1280px the desktop layout is unchanged (340px sidebar, 874px main column), with no overflow on 40 dossiers. A regression test covers the track clamps and the wrapping rule. The full suite passes: 1162 tests, one skipped.

## GSTACK REVIEW REPORT

This is the engineering review of the selected Gesetzesvorhaben plan. Counts include project history; historical frontpage reviews do not clear this plan. All original design answers remain fixed.

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| CEO Review | /plan-ceo-review | Scope and strategy | 0 | NOT RUN | No new product-direction gap requiring a review |
| Outside Review | codex-plan-review; Claude Code skipped | Independent engineering challenge | 4 project runs; 1 for this plan | UNAVAILABLE | User-reported Claude usage limit; required Plan/TaskOutput/TaskStop fallback absent; source=none, host=codex, outside_provider=claude-code, outside_status=unavailable, phase=plan-review |
| Eng Review | /plan-eng-review | Architecture and tests | 4 project runs; 1 for this plan | ISSUES OPEN (PLAN) | 7 required test-gap findings mapped to ET1–ET4 within T1–T6; 0 new architecture/code-quality/performance issues, 0 critical gaps, 0 unresolved; FULL_REVIEW; no tests executed |
| Design Review | /plan-design-review | UI and UX | 2 project runs; 1 for this plan | CLEAR (FULL), 2026-10-08 | Plan completeness 7/10 → 10/10; 9 individually approved decisions; 0 unresolved; host=codex, outside_provider=claude-code, outside_status=unavailable, phase=design |
| DX Review | /plan-devex-review | Developer experience | 0 | NOT RUN | No new developer-facing surface |

**OUTSIDE COVERAGE:** Engineering phase: Claude Code unavailable and not attempted at the user's direction; native fallback capabilities absent, no independent engineering report completed. Design phase: native GPT-6 Luna completed four findings, subsequently resolved; external Claude Code unavailable. The engineering test explorer supplies evidence only. No cross-model consensus or substitute external coverage is claimed. Designer mockups remain unavailable.

**VERDICT:** Approved design implemented and locally validated; see the executed evidence above. All seven engineering proof requirements have local coverage, with the stated browser-tool limitations. No unresolved scope decisions remain. Commit, push, deployment and an external Claude review were not performed.

NO UNRESOLVED DECISIONS
