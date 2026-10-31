# Five more small TODOs outside the v1 roadmap (batch 3)

Branch `fix/five-more-todos-3`, from main at 1b2df58 (v0.23.7.0), 2026-10-30.

## How the five were chosen

A TODO qualifies when:
- it is not a roadmap item (A–D in TODOS.md);
- it does not wait on `worktree-a3-plan`;
- no function it touches is rewritten in `git diff main...worktree-a3-plan`. Overlap was checked by symbol name, not line number.

The A3 branch is roadmap A3 in flight. It rewrites `validate_dip_protocol.py`, `person_registry.py`, RECIPES, `export_distribution_data`, `render_site`, `parse_args`/`main()` and the Abgeordnete index. Every TODO that touches those was dropped.

No other unmerged branch touches `scripts/features/votes.py`, `scripts/dip_text.py` or the card code in `scripts/facts.py`. The only hits were `b4-lane-b`, `claude/wizardly-noether-4axi2h` and `claude/sharp-dijkstra-ghqbb6`, and their content has already landed through #107, #118 and v0.23.2.0. There are no open PRs.

| # | TODO (heading in TODOS.md) | Pri | Files | A3 overlap |
|---|---|---|---|---|
| 1 | Fakt cards cut off the caveats of `knappste-abstimmung` and `meiste-abweichler` | P2 | `facts.py` (`render_card`, REGISTRY caveats) | A3 changes `card_caveat` (coverage slot) and the `erste-reden` caveat; neither line is ours. The test goes through `card_caveat` so it holds after the merge. |
| 2 | B4 review findings, edge 11: a vote-wide Abweichler claim needs the groups to add up to the vote | P2 | `derive.py`, `features/votes.py` (`_abweichler_summary_html`), `build_dip_pulse_site.py` (`_abweichler_count`) | none (symbols absent from the A3 diff) |
| 3 | Link the vote panel's "namentlich" badge to `bundestag.html` | P3 | `features/votes.py` (`render_vote_lead`, `VotePanelContext`), `render_dip_pulse_html.py` (panel ctx) | none |
| 4 | B4 review findings, edge 4: the teaser can cut after "(Abs." | P2 (item) | `dip_text.py` (`abstract_teaser`) | none (A3 does not touch `dip_text.py`) |
| 5 | B4 review findings, edge 15: the 10,000-character cut can leave a cut tag or entity | P2 (item) | `dip_text.py` (`abstract_text`) | none |

Edges 4, 11 and 15 are sub-items of one TODO entry ("B4 review findings: lower-priority edges"). #119 also counted a single edge (14) as one TODO. That entry is not a roadmap item. Roadmap B4's open work is the extractive fallback in `antrag_text.py`, which none of these touch.

**Dropped, and why:**
- Waiting on `worktree-a3-plan`: Textanteil r2, the "Sitzungen mit Dossier" disclosure, the stale cached-report polish, and the XML Drucksache correction.
- A3 territory: `ever_mdb` Bundesrat (A3's tip commit is about exactly this), `person_roles`, the government-office MdBs, Mitberatende Ausschüsse (`compact_position`, a new table), the ingestion audit, vote-acquisition hardening, and B4 edge 12 (RECIPES).
- Delete the feature-selection axis: it threads through `render_site` and `main()`, which A3 rewrites. The nav dead-link item goes with it, since deleting the axis would make that fix throwaway work.
- B4 edge 3 (CSV formula injection): prefixing cells changes the bytes of a citable dataset. That is an owner decision on fidelity, and the code sits in A3's export zone.
- Roadmap or blocked: XLSX roll-call (B5), RSS (needs the final domain for absolute links), "Nächste Sitzungswoche" (a new source, so a licence-layer question).
- Manual items: rasterize-and-post, the five-reader test.

**Order of work:** 4 → 5 → 2 → 3 → 1. The pure functions go first. Item 1 goes last because it is the only one with an owner decision (card geometry or caveat wording). Each item is one commit, test first. Every new test carries the `# Value: protects=… fails_when=… why_new=… seam=…` line that the test modules use.

---

## 1. Fakt cards cut off the caveats of `knappste-abstimmung` and `meiste-abweichler`

**Problem, measured on main:** `render_card` keeps `wrap_lines(card_caveat(row), width=76, max_lines=2)`, and `wrap_lines` cuts without a sign. Caveat lengths per metric:

| Metric | Characters | Lines at 76 |
|---|---|---|
| `knappste-abstimmung` | 246 | 4 |
| `meiste-abweichler` | 313 | 5 |
| `erste-reden` | 93 | 2 |
| `meistdiskutierter-vorgang` | — | 2 |
| all others | — | none |

D27 says a metric is not read without its caveat, and a card travels without its page.

**Outcome (2026-10-30): the owner chose A.** A rendered worst case showed a three-line comparison block (possible for `meiste-abweichler`, `laengste-debatte` and `meistdiskutierter-vorgang`) touching the four-line caveat. So the caveat now ends at a fixed baseline (920) and grows upwards, and the comparison block moves up only as far as a long caveat needs (`card_lower_layout`, comparison at 672 in the worst case). The widest caveat line measured 869 of 920 px in Chrome. Code review 2026-10-31: the topic line (y=650, `laengste-rede` only, which has no caveat today) now moves up with the comparison block, so a raised comparison cannot reach it (topic 622 at worst; over a three-line title that leaves about 3 px by the test's cap-height estimate, and no card has yet had a topic and a caveat together, which the test pins). Every card position and size is now a named `CARD_*` constant, and the rendered SVG bytes are unchanged.

**Owner decision: give the card room (A, recommended) or shorten the text (B).** Both keep one caveat text per metric. The registry text is what the card, the week page (`build_dip_pulse_site.py:8850`) and the Methodik (`:9040`) all show, and a card-only caveat would be a second text to keep in sync.

**A. Card geometry only, wording unchanged.** Give the caveat 4 lines at 22 px with 28 px line height, wrapped at 83 characters, starting at y=836.
- Baselines become 836/864/892/920. The footer stays at 960.
- The comparison block ends at most at baseline 804 (3 × 52 from 700), so nothing collides.
- Measured with `wrap_lines` at width 83, with A3's longest coverage phrase filled in:
  - `knappste-abstimmung`: 3 lines
  - `meiste-abweichler`: 4 lines
  - `erste-reden`: 2 lines
- No text changes anywhere, so pages and Methodik stay as they are.
- Risk: `wrap_lines` counts characters, not glyph widths. 83 characters × about 11 px (Helvetica at 22 px) is about 913 px of the 920 available. Render both cards and measure the longest caveat line (`getComputedTextLength()` in a headless browser on the SVG) before committing. If it overflows, wrap at 80 characters. At 80, `meiste-abweichler` needs 5 lines, so it would also need option B's shorter text.

**B. Shorter text, card at 3 lines of 76 (y=850/882/914).**
- `knappste-abstimmung` fits with its meaning intact (211 characters, 3 lines):
  > Verglichen werden nur namentliche Abstimmungen. Je mehr eine Woche davon hat, desto knapper fällt die knappste im Schnitt aus (gemessen über 58 Wochen); ein hoher Prozentwert sagt also auch etwas über ihre Zahl.
- `meiste-abweichler` does not. Every draft that keeps the four clauses ran to 4 lines at 76:
  - free votes on Gewissensfragen;
  - who counts;
  - Enthaltungen, Abwesende and Fraktionslose do not count;
  - more Abstimmungen make more Abweichungen expected.

  Fitting 3 lines would mean dropping a clause, which D27 argues against. So B on its own is not enough.

**Either way:**
- Add a `CARD_CAVEAT_LINES` constant (4 for A, 3 for B) and a `CARD_CAVEAT_WIDTH` constant, both used by `render_card`.
- Add a test: for every metric in `REGISTRY` and `MONTHLY_REGISTRY`, `wrap_lines(card_caveat(row), CARD_CAVEAT_WIDTH, 99)` has ≤ `CARD_CAVEAT_LINES` lines.
  - The row carries `coverage_label="seit Beginn der 18. Wahlperiode"`, the longest coverage phrase A3 introduces. On main the key is ignored.
  - This replaces the single-metric `test_the_caveat_fits_on_the_card`.
- `test_required_caveats_are_registry_data` keeps asserting "Gewissensfragen".

**Tests first:**
- The all-metrics line-count test above. It fails today on `knappste-abstimmung` (4) and `meiste-abweichler` (5).
- A render test: the concatenated `<text class="caveat">` lines of `render_card` for each of the two metrics equal the full `card_caveat(row)` text, whitespace-normalised.

**Check before committing:** grep whether caveat text enters a metric `version`, the facts tables or a content hash.
- If it does, bump the version and say so.
- If it does not, no stored value moves. The cards and pages change wording only.
- Report the old and new caveat text in the commit message.

**Done when:** no card cuts a caveat, and every metric's caveat line count is pinned by the test (the TODO's own criterion).

---

## 2. B4 edge 11: a vote-wide Abweichler claim needs the groups to add up to the vote

**Problem:** take a Fraktion missing from both the fraction rows and the Einzelstimmen. The remaining groups can each be "complete":
- `_abweichler_summary_html` (`features/votes.py:440`) then prints "Niemand stimmt anders …";
- `_abweichler_count` (`build_dip_pulse_site.py:4532`) gives the archive a 0;
- meanwhile `vote.total` holds Stimmen that no group accounts for.

This is the one B4 edge that can make a public statement false.

**Approach:**
1. Add `derive.vote_groups_cover_total(vote) -> bool`. It sums `merge_fractions(vote["fractions"])` counts over `VOTE_COUNT_KEYS` across all rows, including fraktionslos and Unbekannt, because those Stimmen are part of the total even though they get no Abweichler entry. It returns whether that sum equals `vote["total"]` on every key the total carries.
   - A vote with no `total` or no fraction rows does not cover.
   - Step 0: read the keys of `vote["total"]` on the reference reports, to confirm they match `VOTE_COUNT_KEYS`, before fixing the comparison.
2. `_abweichler_count`: return None unless `vote_groups_cover_total(vote)`.
3. `_abweichler_summary_html`: take a `covered` flag from the caller. When it is not covered:
   - never print `ABWEICHLER_NONE`;
   - print the existing gap note `ABWEICHLER_GAP_HTML`.

   Its text is "Einzelstimmen unvollständig – nicht ermittelbar, wer anders als die Mehrheit der eigenen Fraktion oder Gruppe stimmt". That is true in this case too: the missing Fraktion's Einzelstimmen are what is missing, so no new wording is needed.

   Per-group Abweichler lines stay: they are true for their group.

   **Built differently (e702916, 2026-10-30):** the vote-wide gap note stands only when no group row already carries it. A short group under an uncovered vote shows the note under its row, and a second copy under the vote said the same thing twice. **Code review 2026-10-31:** the completeness and cover tests that `_abweichler_count` and the panel each applied are one function, `derive.vote_abweichler_count`; `_abweichler_count` is gone. A total count that is not a number (or missing) covers nothing instead of raising.
4. Out of scope: edge 12 (the `meiste-abweichler` Fakt and the r3 SQL do not apply the page rule). Its SQL lives in RECIPES/`facts.py`, and A3 rewrites RECIPES. Leave it in TODOS.

**Tests first:**
- `tests/test_derive.py`: covering and non-covering votes, a fraktionslos row counted, and a missing `total`.
- `tests/test_features_votes.py`: a vote with two complete groups and no Abweichler, but a total larger than their sum, renders no "Niemand stimmt anders" and renders the gap note.
- A test that the archive count for the same vote is None, rendered as "–".

**Numbers:** the TODO records 217 of 217 reference votes with matching totals, so the expected move is 0. Measure it on the reference store (`.context/dip-pulse-site`, offline): count votes whose panel shows `vote-abweichler-none` and whose archive shows a number, before and after. Report both, even if both are unchanged.

**Done when:** the panel and the archive make a vote-wide claim only for a vote whose group rows add up to its total. Strike edge 11 in TODOS.

---

## 3. Link the vote panel's "namentlich" wording to `bundestag.html#abstimmen`

**Problem:** the panel's lead sentence (`render_vote_lead`, `features/votes.py:222`) reads "… fand im Bundestag die namentliche Abstimmung „…" statt". The term is not explained. The week radar's badge already links `bundestag.html#abstimmen` (`build_dip_pulse_site.py:5447`), and the section id `abstimmen` exists (`:10229`).

**Approach:**
1. Wrap "namentliche Abstimmung" in that sentence in `<a href="{site_prefix}bundestag.html#abstimmen">`.
2. Give `VotePanelContext` a `site_prefix: str = "../"` next to `mp_prefix`.
   - Step 0: list every page that renders a vote panel and its depth. Today `mp_prefix` is always `"../abgeordnete/"` (`render_dip_pulse_html.py:3012`, `features/votes.py:574`), so every panel sits one level down. Confirm whether `votes/index.html` renders `render_vote_lead` or only its own rows, and set `site_prefix` wherever `mp_prefix` is set, from the same depth.
3. Pass the panel into `render_vote_lead` (it gets `vote, panel.report` today), or pass the prefix alone. Keep the function testable without a full context.
4. Escaping: today the function escapes once at the end (`html.esc(sentence + " " + result + ".")`), with the raw `subject` inside `sentence`. An `<a>` inserted into `sentence` would be escaped into visible text.
   - Build the sentence from escaped parts: `esc(when)`, the link, and `esc(„subject“ (tally).)`.
   - Escape `result` on its own.
5. Check that the sentence sits in no other `<a>`, so no link ends up nested inside another.

**Tests first:** in `tests/test_features_votes.py`:
- the lead contains `href="../bundestag.html#abstimmen"` around "namentliche Abstimmung";
- a test with a non-default `site_prefix`;
- a subject containing `&` and `<b>` comes out escaped once, with no raw `<b>` and no `&amp;amp;`.

**Numbers:** none; this is a copy and link change.

**Done when:** every vote panel links its "namentliche Abstimmung" to the explainer, with the right depth on every page that shows a panel. Move the TODO to Completed.

---

## 4. B4 edge 4: the teaser can cut after "(Abs."

**Problem:** `abstract_teaser` (`dip_text.py:128`) rejects a sentence end when the token before the full stop is a number, a single letter, contains a "." or is in `_ABBREVIATIONS`. It takes the token with `rsplit(None, 1)[-1]`, so "(Abs." yields `(abs`, which is not in the set, and the teaser is accepted as ending a sentence after "(Abs.". The same happens with "(Nr.", "(vgl.", "„Art." and "[Ziff.".

**Approach:** strip leading opening punctuation (`(`, `[`, `„`, `"`, `‚`, `'`) from the token before every check. That is one `lstrip` with a named constant. No other rule changes.

**Tests first** (`tests/test_dip_text.py`):
- a first paragraph longer than `CONTEXT_TEASER` whose only full stop in the window follows "(Abs." falls back to the word-boundary cut with " …";
- one with a real sentence end before "(Abs." cuts there;
- "(Nr." and "„Art." are covered as well.

**Numbers:** on the reference Vorgang cache (`data/dip-vorgang-cache.json` of the reference site), compute `abstract_teaser(abstract_text(raw))` before and after for every cached abstract. Report how many teasers change and quote one. This changes no stored value: the teaser is render-only, and `proceedings.abstract` holds the full text.

**Done when:** no teaser ends after an abbreviation inside brackets or quotes. Strike edge 4.

---

## 5. B4 edge 15: the 10,000-character cut can leave a cut tag or entity

**Problem:** `abstract_text` reads `str(raw)[:MAX_ABSTRACT_CHARS]`. A cut inside `<a href=…>` or `&amp;` leaves `<a hr` or `&am`, which html.parser hands back as text, so it appears in the panel.

**Approach:** when `len(raw) > MAX_ABSTRACT_CHARS`, trim the slice back before parsing:
- Drop everything from the last tag-starting `<` (per `_TAG_START`) whose tag never closes outside quotes. Use the same quote-aware `closes` scan `_strip_tags` does, factored into a shared helper, not a plain "no `>` after it" test. Otherwise `<a title="x>y" hr` survives, because a `>` follows inside the quotes.
- Drop a trailing partial character reference (`&#?\w*$` with no `;`).

Do this in a helper next to `_strip_tags`, used only on the cut path.

**Built differently:**
- The partial character reference goes only when the character after the cut continues it (a letter, digit, `#` or `;`). "AT&T " before the cut is whole text and stays (d3a6c55).
- Code review 2026-10-31 found that "the last `<` whose tag never closes" also caught a `<` that is text: "if a<b then …" past the cut came back as "if a", and a `<` inside a closed tag's quoted attribute was taken for a tag. The trim now reads tags over the whole raw text and drops only the tag that opens before the cut and closes after it. A `<` whose tag never closes stays text, as html.parser keeps it in an abstract that fits. An abstract that fits is read unchanged, which also keeps edge 2 (output stability) untouched for every reference row.

**Tests first** (`tests/test_dip_text.py`):
- raw = filler to `MAX_ABSTRACT_CHARS - 4` + `<a href="x">y</a>`: the result contains no `<`;
- the same with `&amp;` straddling the cut: no `&am`;
- a cut inside a quoted attribute value containing `>`;
- an abstract shorter than the limit gives byte-identical output to main.

**Numbers:** the longest reference abstract has 5,111 characters, so 0 stored abstracts move. Confirm with a one-line max over the cache.

**Done when:** no cut tag or entity reaches the text. Strike edge 15.

---

## Bookkeeping and ship

- Strike edges 4, 11 and 15 in "B4 review findings: lower-priority edges", as edge 14 was. Move items 1 and 3 to Completed with their dates.
- Run the full suite (`python -m unittest`), the zero-network demo build, and an offline rebuild of the reference site for items 2–5. Report the measured numbers per item in the commit messages, old and new.
- Version bump, CHANGELOG and PR through `/gstack-ship`, as #118 and #119 did.
