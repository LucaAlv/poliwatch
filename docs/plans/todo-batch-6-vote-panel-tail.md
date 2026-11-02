# TODO batch 6: vote panel tail

Status: plan, not implemented. Written 2026-11-01 on `claude/todos-batching-subagents-aa0a61` at main `69ade54`.
Reviews: eng review done 2026-11-01 and design review done 2026-11-01; findings of both are folded into the body (see "Eng review" and "Design review" below).

Three small TODO items. All three sit in the "Worum es geht" block of the vote panel, in its text scanner, or on the votes archive page:

| # | TODO heading, item | What |
|---|---|---|
| 1 | "B4 review findings: lower-priority edges", item 1, plus item 23(b) | Per-vote cap and fold for "Worum es geht" blocks; restore a visible disclosure marker on the "Ganze Beschreibung" toggle |
| 2 | Same heading, item 22(a) and 22(d) | `dip_text`: a `<script>`/`<style>` that closes beyond the 12,000-character window leaks its body; fix the docstrings. 22(b) and 22(c) are **not** fixed: they go to the owner question in "Owner decisions" |
| 3 | "Politikfelder: findings deferred from the B3 review", item 5 | Browser check for the inline filter script on `votes/index.html` |

Pre-release rule (CLAUDE.md): change in place, no shims. Items 1 and 3 are render-only or test-only.

Item 2 is **not** render-only: `dip_text.abstract_text` also feeds
- the stored `proceedings.abstract` (`persist_dip_pulse_store.py:1503`), and through it the content-hashed Daten export;
- the "abstract is empty" test in `antrag_text.py:478`, which decides fetch targets and passage states.

It changes output only for an abstract over 10,000 characters, and none of the 3,922 cached ones is (longest 5,111). So no stored value, export column or schema moves on today's data. The measurement steps below check this; eng finding A2 corrected this paragraph.

---

## Measured: blocks per vote

Script: `blocks_per_vote.py` (scratchpad; recipe in "Measurement recipes"). It runs the render path, `politikfelder.report_vote_vorgaenge` plus `antrag_text.report_vote_passages`, over every cached report. The stores are read-only.

**Reference store `~/agent-runs/a3/full`** (exists, checked 2026-11-01; 726 report JSONs, 556 votes):

| Vorgang blocks per vote | votes |
|---|---|
| 0 (only a gap note, state `none`) | 16 |
| 1 | 444 |
| 2 | 88 |
| 3 | 8 |
| 4 or more | 0 |

- Cross-check: the stored `vote_proceedings` rows per vote in `data/bundestag-pulse.sqlite` give the same distribution exactly (0:16, 1:444, 2:88, 3:8). Persist and render agree.
- Each vote has exactly 1 panel: no vote sits under two TOPs in this store.
- Visible teaser characters per vote, summed over its blocks (folds closed): 1 block max 301, mean 209; 2 blocks max 599, mean 422; 3 blocks max 896, mean 575.
- Block kinds: 464 abstract with fold, 57 short abstract, 123 "Keine Beschreibung in DIP".
- **Caveat:** this store has no Antrag text cache (`data/dip-drucksache-text-cache.json.gz` is absent). Blocks that would quote an Antrag show as "Keine Beschreibung" here. That undercounts quote blocks, which are taller. The block counts themselves do not depend on it.

**Second store `/Users/Luca/Projects/poliwatch/.context/b4-local-20261029-163417/working`** (has the Antrag text cache; 291 reports, 217 votes):
- Blocks per vote: 1: 178, 2: 35, 3: 4. Max 3.
- Block kinds: 159 abstract with fold, 9 short, 60 quoted Antrag (1 quote each), 32 "Keine Beschreibung".

The examples with 3 blocks (a3/full) are votes 305 and 306 in 18/61, 318 in 18/71, 559 in 19/66, 879 in 20/137, 897 in 20/152, 799 in 20/54 and 807 in 20/64.

**Why it is unbounded in principle.** The narrow tier allows at most `NARROW_NUMBER_FANOUT = 2` Vorgänge per Drucksache number (`politikfelder._vorgaenge_of_numbers`). A vote can name any number of narrow Drucksachen, so a vote over a bundle of Anträge could produce 2 blocks per Antrag. No vote reaches 4 today.

---

## Item 1: cap and fold the "Worum es geht" blocks (B4 edges item 1 and 23(b))

### Change

`scripts/features/votes.py`, `render_vote_context`:

1. Add a module constant next to `ABWEICHLER_INLINE`:
   ```python
   #: Vorgang blocks shown open under "Worum es geht"; the rest fold away (best first,
   #: the order of ``politikfelder.vote_vorgang_ids``). No reference vote has more
   #: than 3 (556 of 556 on a3/full), so this only guards the shape.
   CONTEXT_INLINE = 3
   ```
2. Build the per-Vorgang blocks exactly as today into `blocks`. Fold only when the fold would hide at least two blocks (design decision DD1). That is, if `len(vorgang_ids) > CONTEXT_INLINE + 1`, keep the first `CONTEXT_INLINE` open and wrap the rest:
   ```html
   <details class="vote-context-overflow"><summary>{n} weitere Vorgänge anzeigen</summary>…blocks…</details>
   ```
   A vote with 4 Vorgänge shows all 4 open: a fold that hides one block costs a click and saves no space.
   - `n >= 2` always, so the summary is always plural: `f"{html.format_int(n)} weitere Vorgänge anzeigen"`. No singular form is needed. The wording is an owner decision (below).
   - The count names Vorgänge, a real unit here (unlike `QUOTE_MORE`, where a count of "Forderungen" would misstate the Antrag).
   - This deliberately differs from the Abweichler fold, which hides an 11th name alone. Names are one line each; a Vorgang block is a paragraph.
3. Order is kept: blocks are already best first (`_ranked` by how many numbers name a Vorgang). The cap therefore hides the weakest-supported ones.
4. **The trailing D7 gap note stays outside the fold.** That is the `vorgang_ids and state == "not_fetched" and all(... in records)` paragraph. It marks a number no block shows, so a reader must see it without opening anything. Append it after the `<details>`, as today after the last block.
   - **And a folded block without a record also triggers it (DD3).** A folded "Vorgang nicht abgerufen" block is a gap no open block shows. The condition becomes: `state == "not_fetched"` and (every id has a record, **or** some folded id has none). The note is still shown at most once. It uses the existing `CONTEXT_NOT_FETCHED` copy, so no new wording.
   - Open blocks keep saying it in their own block, as today.
5. The cap is in the renderer only. **Not** in `politikfelder.vote_vorgang_ids`: `vote_proceedings`, `votes.context_state`, `vote_passages` and the export keep every Vorgang. Persist is untouched. The pages and the Daten tables keep naming the same Vorgänge (D13); the page just folds some.

### CSS (`scripts/render_dip_pulse_html.py`, vote-context rules, about lines 3779–3810)

- **Give the overflow its own class.** `.vote-context-more summary` (the shared rule at about line 3802) is a descendant selector. A `vote-context-more` class on the overflow would also restyle every nested abstract summary inside it. Hence `vote-context-overflow`.
- `.vote-context-overflow > summary`: the blue toggle style already used by `.vote-context-quote-more summary` (inline-flex, min-height 24px, blue, 13px, weight 650), with `margin-top:8px`. Add it to the existing selector list rather than a new block.
- **Touch target (DD4).** Under `@media (pointer:coarse)`, give `.vote-context-overflow > summary` and `.vote-context-quote-more summary` `min-height:44px`, as the archive chips already have (`votes_archive_styles`, `.chip`). The "Ganze Beschreibung" summary already holds the teaser paragraph and is taller than 44 px.
- **Dashed separator across the fold.** `.vote-context-block + .vote-context-block` does not match the first block inside the `<details>`, because its previous sibling is the `<summary>`. Add:
  ```css
  .vote-context-overflow > .vote-context-block { padding-top:8px; border-top:1px dashed var(--line); }
  ```
  This covers every folded block, the first included. The `+` rule keeps working between the open blocks.
- Dark theme: no new colour token. The blue toggle and `--line` already have dark values. Check that `.vote-context-overflow` needs no `:root[data-theme="dark"]` entry (the existing toggles have none).

### 23(b): the disclosure marker on "Ganze Beschreibung"

Today `.vote-context .vote-context-more > summary { display:block; … }` drops the native marker, because Chrome draws `::marker` only for `display:list-item`. The other vote-panel toggles (`.vote-context-quote-more summary`, `.vote-abweichler-more summary`) are `inline-flex`, so they have no marker either. Only `.member-votes summary` and the speech cards keep the native triangle.

**Decision (CSS only, markup unchanged):** a marker on the blue toggle text, not before the teaser prose. Per DD2, the same marker goes on all three vote-context toggles: "Ganze Beschreibung", the new overflow and "Ganzen Forderungsteil zeigen". The block then has one toggle vocabulary:
```css
:is(.vote-context-more, .vote-context-overflow, .vote-context-quote-more) > summary::-webkit-details-marker { display:none; }  /* Safari: no second marker */
.vote-context-more > summary .vote-context-toggle::before,
:is(.vote-context-overflow, .vote-context-quote-more) > summary::before { content:"▸ "; content:"▸ " / ""; }
.vote-context-more[open] > summary .vote-context-toggle::before,
:is(.vote-context-overflow, .vote-context-quote-more)[open] > summary::before { content:"▾ "; content:"▾ " / ""; }
```
- The `/ ""` alt text keeps screen readers from reading the glyph; `<details>` already exposes expanded/collapsed. A browser that does not know the alt syntax drops that declaration and keeps the first one.
- The markup stays the same, so the exact-markup assertion in `test_features_votes.VoteContextPanelTests.test_the_abstract_is_sanitised_escaped_and_folded` still holds.
- Rejected: `display:list-item` on the summary (precedent: `.site-nav summary`, about line 718). It puts the triangle in front of up to 300 characters of teaser prose, where it reads as a bullet.
- Settled by the design review (DD2): all three vote-context toggles get the marker. `.vote-abweichler-more` ("alle N anzeigen") stays without one in this batch. It sits under the Fraktion rows, not in the context block. It is listed in "NOT in scope" and proposed as a TODO at ship time.

### Tests

`tests/test_features_votes.py`, class `VoteContextPanelTests`. That file is not in A3's diff.
- `test_more_than_four_vorgaenge_fold_the_rest_in_order`: 5 ids give 3 open blocks, then one `details.vote-context-overflow` whose summary reads "2 weitere Vorgänge anzeigen" and which holds blocks 4 and 5 in order. 4 ids give 4 open blocks and no overflow (DD1). 3 ids give no overflow.
- `test_the_not_fetched_note_stays_outside_the_fold`: covers DD3 with three cases.
  - 5 ids, state `not_fetched`, all records present: the gap note comes after `</details>` and appears once.
  - 5 ids where id 5 (folded) has no record: the note appears after `</details>`, once (DD3).
  - 5 ids where id 1 (open) has no record and the rest do: no trailing note; the open block says it.
- A nested abstract fold inside the overflow keeps its own `vote-context-more` class. The overflow summary does not carry `vote-context-toggle`.

`tests/test_render_dip_pulse_html.py`: one CSS test, placed in the class that holds `test_teaser_hides_on_open_without_has` (about line 438, mid-file). **Not** appended at the end of the file, where A3 adds `PartyColorTests`. It asserts:
- the overflow separator rule;
- the `::before` marker rules for closed and `[open]`, for all three toggles (DD2);
- the `::-webkit-details-marker` rule;
- the coarse-pointer `min-height:44px` rule for the overflow and quote-more summaries (DD4).

### Measurement

The rule (3 open, fold only when 2 or more would hide, so a vote with 4 shows all 4) changes **0 of 556** panels (a3/full) and **0 of 217** (b4-local). The first panel to fold would need 5 Vorgänge; the maximum today is 3. For comparison, a cap of 2 with the same rule would still fold nothing, because no vote has 4 or more. A plain cap of 2 (fold any extra) would fold 8 of 556 and 4 of 217. The marker CSS changes every page's stylesheet but no text.

Verify after the change: render every vote's context HTML on both stores with main's `scripts/` and with the branch's, then diff (recipe below). Expected: 0 differing blocks. Report old and new counts in the commit message.

---

## Item 2: `dip_text` script/style past the window (B4 edges item 22(a), 22(d))

### The defect, measured on the current code

When a raw abstract is longer than `MAX_ABSTRACT_CHARS` (10,000), `abstract_text` reads only the first 12,000 characters (`+ CUT_LOOKAHEAD`). In `_paragraphs`, a `<script>`/`<style>` whose close tag is not inside that window is treated as "unclosed", so it is a plain tag and its body stays as text. The defect is wider than the TODO says:

| raw shape | text today | body characters leaked |
|---|---|---|
| `"x"*9990 + "<script>" + "y"*2500 + "</script>tail"` (TODO's reproducer) | ends `…yy` | 2 |
| `"x"*7000 + " <script>" + "y"*6000 + "</script>tail"` (opens 3,000 chars before the cut) | 9,992 chars | **2,991** |
| `"x"*7000 + " <script>" + "y"*4000 + "</script>tail"` (closes inside the window) | 7,000 chars | 0 (correct) |
| `"x"*9990 + "<script>" + "y"*2500` (never closes anywhere) | ends `…yy` | 2 (correct by the current rule: an unclosed script is a plain tag) |

0 of 3,922 cached abstracts reach the cut (the longest has 5,111 characters).

### Fix (recommended): look for the close tag in the rest of the raw text

`abstract_text` also passes the whole raw string to `_paragraphs` (`raw[:len(text)] == text`, so positions agree). The window logic runs first, unchanged. Only when the text is truncated **and** the window gives no complete close does it ask `raw`. The window gives no complete close when either:
- `close` is None, or
- `close_end == -1`, i.e. the close starts inside the window but its `>` lies beyond it. This case was found by the eng review, finding A1: today `text.find(">", close.end() - 1)` returns -1 there and the tag reads as unclosed.

The raw check:
- **Close exists in raw:** a match of `_SKIPPED_CLOSE[name]` in `raw` at or after `end`, with a `>` at or after its last character. Then the block ends past the cut. Set `end = len(text) + 1`, so the existing `end > cut` branch keeps the text before the tag and drops the rest. That is what reading the whole raw would give.
- **No close in raw:** the tag is really unclosed. It is a plain tag, as now. This keeps the existing rule (`"<p>Eins</p> <script>zwei"` reads `"Eins\n\nzwei"`) and the fourth table row.
- **Bound (memo, eng finding A1/P1):** keep per call one memo per tag name: `(searched_from, match_or_None)`. Tags are visited left to right, so `end` only grows.
  - A memo with `None` answers every later `end` with None.
  - A memo with a match at `q >= end` answers with that match. There is no match between `searched_from` and `q`.
  - Only `q < end` triggers a new search from `end`.

  The `>` test is `q_end - 1 <= last_gt`, with `last_gt = raw.rfind(">")` computed once. So the raw is scanned at most about twice per name, not once per tag. Without the memo, 1,500 unclosed `<script>` tags in the window would each scan a 2-million-character raw.
- The window scan (`_tag_ends`) stays at 12,000 characters. The 2-million-character cases in `test_a_huge_abstract_is_read_in_bounded_time` stay in milliseconds. Add two cases to that test's list:
  - `"<script>" * 250_000` (no close anywhere);
  - `"<script>" * 1500 + "</script " * 200_000` (1,812,000 characters). Every close is past the window, at 12,000 onwards, and no `>` exists after any of them (`raw.rfind(">")` is 11,999). Checked against the scanner at 69ade54: the window has 0 closes and the first raw match is at 12,000. Without the once-computed `last_gt`, each of the 1,500 tags would rescan about 1.8 M characters for a `>`.
  - (`"<script></script" * N` does not work as a case: `_SKIPPED_CLOSE` needs one of `[\t\n\r\f />]` after `script`, so it never matches.)

**Alternative (not recommended):** drop to the cut from any skipped tag with no close in the window, bounded like other tags to those opening within `CUT_LOOKAHEAD` before the cut. It keeps the 12,000-character read but:
- it still leaks the second table row, which opens 3,000 before the cut;
- without the bound, a truly unclosed early `<script>` would empty an over-limit abstract that a short one keeps. Item 19 called out exactly that kind of finding.

### 22(d): docstrings

- `_markup_end`: say that a `<!--` with no `-->` is read by the `<!…>` rule and ends at its first `>`, or stays text if there is none.
- `abstract_text`:
  - say the same for an unclosed comment;
  - replace "Only the first `MAX_ABSTRACT_CHARS` characters are read" with what the code does: the first 10,000 + 2,000 are scanned, plus one search of the rest for a `</script>`/`</style>` close.
- `_paragraphs`: its claim that "a `<script>` block that starts before the cut and ends after it is dropped" is false today for a close beyond the window. Make it true with the fix, and say how the close is found.
- `CUT_LOOKAHEAD` comment: mention it does not bound the close-tag search.

### Tests (`tests/test_dip_text.py`, not in A3's diff)

`test_a_script_or_style_closing_past_the_window_is_dropped`. For both `script` and `style`, it covers four rows:
- the TODO reproducer;
- the 3,000-before-the-cut shape (opens more than `CUT_LOOKAHEAD` before the cut);
- a close tag straddling the window edge, at 11,995–12,004;
- a close tag whose name is inside the window and whose `>` lies past it: `"</script" + " " * 50 + ">"` placed at 11,990 (eng finding A1);
- a close with no `>` anywhere, which stays a plain tag.

Expected text: the characters before the tag, cut at the tag. For the never-closed rows the expected text is today's output. The `# Value:` line names item 22(a).

### Measurement

Run main's and the branch's `abstract_text` over every cached abstract in `~/agent-runs/a3/full/data/dip-vorgang-cache.json`. Expected: **0 of 3,922** differ, because none exceeds 10,000 characters. Also run it on 3.11 and 3.13.12 (`uv run --python …`), as item 2 did, so the Python-independence claim still holds.

### Not planned: 22(b), 22(c)

These are the `="` attribute-name shape and the unterminated quote after `= `. They are **not** fixed in this batch. This scanner has had three review cycles, each found another malformed shape, and 0 of 3,922 texts are affected. See the owner question below.

---

## Item 3: browser check for the `votes/index.html` filter (Politikfelder B3 item 5)

### Files

- **New `tests/votes_archive_browser_fixture.py`.** A standalone script: `python3 tests/votes_archive_browser_fixture.py <out-dir>` writes `<out-dir>/index.html`.
  - It is not a `test_*.py` module, so unittest discovery skips it, and no test module doubles as a CLI. Item 23(c) names that pattern as debt in `test_politikfelder.py`.
  - It imports `_support`, `build_dip_pulse_site as build` and `politikfelder`. It builds entries from `FIXTURES / "report.json"` (as `test_politikfelder.fixture_report` does, but copied, not imported). It edits the votes, calls `build.collect_votes_archive(entries, cache)`, and writes `build.render_votes_archive_index(rows)`.
  - Rows come from `collect_votes_archive`, so `data-fraktion-positions` comes from `_fraction_position` and `data-politikfelder` from `politikfelder.shown`: the real path, not hand-made attributes.
- **New `tests/votes_archive_browser_check.js`.** A browser function in the shape of `radar_browser_check.js`, with a `// Value:` header line.
- **`tests/run_bills_browser_check.mjs`:** one more `readFileSync`, one `spawnSync` for the fixture into `publicDir/votes`, and one navigate/evaluate block at desktop and mobile width. Plus a second navigation with `?politikfeld=…`.

### Fixture data (4 votes, 2 months)

| vote | month | Fraktion A | Fraktion B | inverted | Politikfelder |
|---|---|---|---|---|---|
| 1 | 2024-05 | yes (Ja > half) | no | no | Verkehr |
| 2 | 2024-05 | no | yes | no | Gesundheit |
| 3 | 2024-04 | `für den Antrag` (Nein > Ja + Enthaltung) | no | **yes** | Verkehr, Gesundheit |
| 4 | 2024-04 | tie | yes | no | untagged |

Real Fraktion names from the fixture (e.g. "SPD", "CDU/CSU"). The table names are placeholders.

### Assertions

1. **Initial state:** no chip is pressed, all 4 rows are visible, both month headings are visible, and the count reads "4 Abstimmungen". The empty note is hidden.
2. **Fraktion A:** rows 1 and 3 show. Row 3 shows through the inverted `für den Antrag` path. The count reads "2 von 4 Abstimmungen", `aria-pressed="true"` and `is-active` are set.
3. **OR within a group:** Fraktion A and B pressed shows all 4 rows (row 4 through B, although A is a tie); the count reads "4 von 4 Abstimmungen" because a filter is active.
4. **AND across groups:** Fraktion B plus Politikfeld Verkehr shows no row. The empty note shows, the count reads "0 von 4", and both month headings hide.
5. **Month heading:** Politikfeld Gesundheit alone shows rows 2 and 3, so both months show. "Ohne Politikfeld" (`untagged`) alone shows only row 4, so the 2024-05 heading hides.
6. **Clear:** pressing every pressed chip again restores 4 rows, hides the empty note, and resets the count to "4 Abstimmungen".
7. **Query preload** (second navigation, `?politikfeld=Verkehr&politikfeld=Nichtda`): the Verkehr chip is pressed on load, rows 1 and 3 show, and the unknown name is ignored without an error.
8. **No overflow** at 390 px: `document.documentElement.scrollWidth <= innerWidth`.

### Running it

Local port binding is blocked in this sandbox: the runner listens on 127.0.0.1 and Chrome's DevTools port. So `node tests/run_bills_browser_check.mjs` cannot run here. **The owner runs it**, or it runs in a session with `sandbox.network.allowLocalBinding: true`. The implementer runs the fixture script alone (no port) and checks the HTML it writes. CI runs it (`.github/workflows/ci.yml`, step "Run browser checks": `node tests/run_bills_browser_check.mjs python`), so the new block runs on every push even though it cannot run in this sandbox.

---

## Files and functions touched

| File | Function / area | Item |
|---|---|---|
| `scripts/features/votes.py` | `render_vote_context`; new `CONTEXT_INLINE` | 1 |
| `scripts/render_dip_pulse_html.py` | vote-context CSS (about lines 3779–3810) | 1, 23(b) |
| `scripts/dip_text.py` | `_paragraphs`, `abstract_text`, docstrings of `_markup_end` and `CUT_LOOKAHEAD` | 2 |
| `tests/test_features_votes.py` | `VoteContextPanelTests` (+2–3 tests) | 1 |
| `tests/test_render_dip_pulse_html.py` | 1 CSS test beside `test_teaser_hides_on_open_without_has` | 1, 23(b) |
| `tests/test_dip_text.py` | +1 test; extend `test_a_huge_abstract_is_read_in_bounded_time` | 2 |
| `tests/votes_archive_browser_fixture.py` (new) | fixture writer | 3 |
| `tests/votes_archive_browser_check.js` (new) | browser assertions | 3 |
| `tests/run_bills_browser_check.mjs` | fixture spawn + navigate/evaluate | 3 |
| `TODOS.md`, `CHANGELOG.md`, `VERSION` | at ship time only, not by this plan | all |

Read-only for this batch: `scripts/build_dip_pulse_site.py`, `scripts/politikfelder.py`, `tests/test_politikfelder.py`, `tests/test_build_dip_pulse_site.py`. The fixture calls `collect_votes_archive` and `render_votes_archive_index` but changes neither.

## Conflict surface vs A3

`git diff main...worktree-a3-plan` (A3 tip `50e7dfd`) for every file above:

| File | A3 hunks | How this plan stays clear |
|---|---|---|
| `scripts/features/votes.py` | none | n/a |
| `scripts/dip_text.py` | none | n/a |
| `scripts/render_dip_pulse_html.py` | one, at line 39 (`PARTY_COLORS`: FDP, Gruppe Die Linke, Gruppe BSW) | Edits only the vote-context CSS at about line 3779–3810, 3,700 lines away |
| `tests/test_render_dip_pulse_html.py` | one, appended at end of file (`PartyColorTests`, before `if __name__`) | The new test goes mid-file at about line 441, beside `test_teaser_hides_on_open_without_has`. Nothing is appended at the end |
| `tests/test_features_votes.py` | none | n/a |
| `tests/test_dip_text.py` | none | n/a |
| `tests/run_bills_browser_check.mjs` | none | n/a |
| new files | n/a | no overlap possible |
| `tests/test_politikfelder.py` (not touched) | lines about 60 and 120 | Deliberately not used for the fixture |
| `tests/test_build_dip_pulse_site.py` (not touched) | 89 changed lines | Not used |
| `scripts/build_dip_pulse_site.py`, `scripts/politikfelder.py` (not touched) | heavy / small | Read-only. The fixture only calls `collect_votes_archive` and `render_votes_archive_index`. If A3 changes their signatures, the fixture follows at merge |

`TODOS.md` (heavily edited by A3) is touched only at ship time, in the two TODO sections named above. Expect a conflict there only; resolve by keeping both.

## Measurement recipes

All read-only on the stores. Scripts live in the session scratchpad or under `docs/plans/`, never in the stores.

1. **Blocks per vote:** the run that produced the numbers above. For each `data/plenarprotokoll-*.json` except the catalog:
   - load the Vorgang cache with `politikfelder.load_cache(root)` and set `cache[antrag_text.CACHE_NAMESPACE] = antrag_text.load_cache(root)`;
   - count `len(ctx.vorgang_ids)` per `politikfelder.report_vote_vorgaenge(report, cache)` entry.

   Cross-check with SQL on the store, opened `mode=ro`:
   ```sql
   select n, count(*) from (select v.id, (select count(*) from vote_proceedings vp where vp.vote_id = v.id) n from votes v) group by n;
   ```
2. **Panel diff (item 1):** in the same loop, call `features.votes.render_vote_context(ids, state, cache, passages.get(key))` for every vote and write `{report: {vote: sha256(html)}}` to JSON. Capture the baseline **before** the first edit on this branch: the branch starts at main `69ade54`, so no second worktree is needed. Rerun after the change and diff. Expected: 0 differences. Because the stored `vote_proceedings` and `proceedings.abstract` are untouched by item 1, no store replay is needed for it.
3. **Abstract diff (item 2):** `abstract_text(record["abstract"])` for every record in `dip-vorgang-cache.json` with a non-empty abstract (3,922). Baseline before the edit, rerun after. Expected: 0 differences. Since this is the value persist writes to `proceedings.abstract`, 0 differences also means 0 stored abstracts move. Repeat on Python 3.11 and 3.13.12 via `uv run --python` (uv is at `~/.local/bin/uv`; whether those interpreters are cached offline is unverified).


### `blocks_per_vote.py` (recipe 1, reproduced here because the session scratchpad does not persist)

Run: `python3 -I blocks_per_vote.py <store-root> <worktree>/scripts`. `-I`, because it reads store files.

```python
"""Measure Worum-es-geht blocks per vote on a read-only output dir (render-time path)."""
import collections, json, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, sys.argv[2])
import politikfelder, derive, dip_text, antrag_text
cache = politikfelder.load_cache(root)
cache[antrag_text.CACHE_NAMESPACE] = antrag_text.load_cache(root)
dist = collections.Counter(); states = collections.Counter(); kinds = collections.Counter()
quotes_per_block = collections.Counter(); seen = {}
for p in sorted((root / "data").glob("plenarprotokoll-*.json")):
    if p.name == "plenarprotokoll-catalog.json":
        continue
    report = json.loads(p.read_text(encoding="utf-8"))
    ctxs = politikfelder.report_vote_vorgaenge(report, cache)
    passages = antrag_text.report_vote_passages(report, cache, ctxs)
    for key, ctx in ctxs.items():
        if (p.name, key) in seen:
            continue
        seen[(p.name, key)] = ctx
        dist[len(ctx.vorgang_ids)] += 1; states[ctx.state] += 1
        for vid in ctx.vorgang_ids:
            rec = (cache.get("vorgaenge") or {}).get(vid)
            text = dip_text.abstract_text((rec or {}).get("abstract"))
            if rec is None:
                kinds["not_fetched"] += 1
            elif not text:
                vp = passages.get(key)
                q = [x for x in ((vp.by_vorgang.get(vid) if vp else None) or []) if x.state == "extracted"]
                quotes_per_block[len(q)] += 1
                kinds["quotes" if q else "none"] += 1
            else:
                kinds["abstract_fold" if dip_text.abstract_teaser(text)[1] else "abstract_short"] += 1
print("votes", len(seen)); print("blocks per vote", sorted(dist.items()))
print("states", dict(states)); print("block kinds", dict(kinds))
print("quotes per abstractless block", sorted(quotes_per_block.items()))
```

For recipe 2, extend the inner loop:
- call `features.votes.render_vote_context(ctx.vorgang_ids, ctx.state, cache, passages.get(key))`, after `import features.votes`;
- store `hashlib.sha256(html.encode()).hexdigest()` under `(p.name, key)`;
- dump the result to JSON once before the first edit and once after, and diff the two files.

## Owner decisions

**Answered by the owner on 2026-11-01. Every recommendation is accepted:**
- 1: 3 blocks open; fold only when 2 or more would hide (DD1).
- 2: „{n} weitere Vorgänge anzeigen".
- 3: parity with html.parser on malformed markup is not a goal. Close 22(b)/(c) in TODOS.md at ship time and state the rule in the `dip_text` docstring.
- 4: search for the close tag in the raw tail.
- 5: DD2, DD3 and DD4 are all kept. Eng D1 and D2 stand.

The original options follow for the record.

The global AskUserQuestion hook may answer gstack's questions. These are also logged here with a recommendation:

1. **Cap value for "Worum es geht" blocks.** Recommend **3 open, fold only when 2 or more would hide** (DD1, so up to 4 show open). 0 panels change today on either store, and three blocks is about 900 visible teaser characters at most. A plain cap of 2 would fold 8 of 556 panels.
2. **Overflow summary wording.** Recommend "{n} weitere Vorgänge anzeigen" (always plural under DD1). Alternative mirroring Abweichler: "alle {N} Vorgänge anzeigen", which counts the open ones too.
3. **Is parity with html.parser on malformed markup a goal at all?** Recommend **no**. The goals are:
   - the same text on every Python (item 2's reason for the scanner);
   - no hidden content (script/style bodies) leaking as text.

   Fix leaks like 22(a). Do not chase shape and spacing differences like 22(b) and 22(c) unless a real abstract hits one. If the owner agrees, close 22(b)/(c) in TODOS.md with that sentence and record it in the `dip_text` module docstring, so the next review stops filing them.
4. **22(a) fix shape.** Recommend searching the close tag in the raw tail: exact for this shape, linear, one search per tag name. The bounded "drop to cut" alternative still leaks a script that opens more than 2,000 characters before the cut.

5. **Calls this agent made itself (no AskUserQuestion was available, so neither the owner nor the hook answered them; the recommended option was taken each time).** All are reversible by editing one rule:
   - DD2: the ▸/▾ marker also on the quote fold "Ganzen Forderungsteil zeigen", which restyles an existing toggle.
   - DD3: "Vorgang nicht abgerufen" also shows after the fold when a folded block lacks a record, which changes when the public panel says it.
   - DD4: 44 px coarse-pointer height on two toggles.
   - Eng D1 (file arrangement) and D2 (raw close check with memo).

## Not verified here

- The browser check (sandbox blocks local ports). The owner runs `node tests/run_bills_browser_check.mjs`.
- Safari/VoiceOver reading of the `::before` alt text. Chrome only, as for item 18.

---

# Eng review (gstack-plan-eng-review, 2026-11-01)

Target: this file, `docs/plans/todo-batch-6-vote-panel-tail.md` (named explicitly). Report file: this file.

How it ran:
- **Mode:** subagent run with no AskUserQuestion tool. As the caller instructed, every decision below took the recommended option and is logged here and in "Owner decisions". The preamble echoed `SESSION_KIND: interactive`, but nobody reads this run live.
- **Skipped:** the gstack upgrade prompt (`UPGRADE_AVAILABLE 1.91.176.0 1.91.379.0`). It writes under `~/.claude/skills`, which the sandbox denies.
- Prior learning applied: headless-window-clamps-mobile-width (confidence 10/10, 2026-10-26). The item 3 runner block uses `Emulation.setDeviceMetricsOverride` for the 390 px pass, as the radar block does.

## Step 0: Scope Challenge

**What already exists:**

| Need | Existing piece |
|---|---|
| Fold pattern for item 1 | `render_abweichler` with `ABWEICHLER_INLINE = 10` and the "alle N anzeigen" `<details>` (`scripts/features/votes.py:171-183`) |
| Count wording | `render_dip_pulse_html.format_count` (line 1822) |
| Item 3 runner | `tests/run_bills_browser_check.mjs` already serves a fixture dir and evaluates check functions at two widths (radar block) |
| Item 3 rows | `build.collect_votes_archive` |
| Item 3 page | `build.render_votes_archive_index` |

Nothing new is invented.

**Complexity:** 9 files, counted once each: 3 scripts, 3 test modules, 2 new test files and the runner. No new classes or services. The 8-file gate trips.
- **D1, structure:** `Original arrangement` (9 files) against `Smaller arrangement` (8 files: put the archive fixture writer into `tests/test_features_votes.py` behind a `__main__` flag). The smaller one recreates the CLI-in-a-test-module pattern that B4 item 23(c) records as debt.
- Recommendation and auto-decision: **Original arrangement**. Feature answers: no cuts proposed. Accepted scope: the three items as planned. Pending remedies: none.

**Scope Challenge result: scope accepted as-is.**

**Reality rows:**

| Row | Status | Evidence |
|---|---|---|
| premise-table | pass | 11 premises, all receipted (list below), unverified=1 |
| already-done | pass | `git log 69ade54..origin/main` for the four named files is empty (local refs; no fetch, offline rule). The old `fix/todo-batch-{1,2,4}` branches were squash-merged in #124 (`69ade54` message lists their fixes), and none implements B4 item 1, 22(a) or B3 item 5 |
| surface-check | pass | `node` v24.15.0 has native WebSocket (the runner needs Node 21+). `uv` is at `~/.local/bin/uv`. CI step "Run browser checks" exists (`.github/workflows/ci.yml:36-38`). `politikfelder.load_cache` and `antrag_text.load_cache` signatures were read. No new CLI flags |
| binding-decisions | pass | `gstack-decision-search --scope branch` returned nothing. The plan keeps the earlier contracts: one rule for persist and render (D13), item 18's no-`:has()` rule, D7's gap note. Item 1 explicitly leaves `vote_proceedings` alone |
| numbers | pass | Blocks per vote [measured: blocks_per_vote.py on a3/full and b4-local, plus SQL on the a3/full store]. Leak table [measured: python3 against `dip_text` at 69ade54]. 3,922 / 5,111 [measured in item 2/15 records; re-measure before gate] |
| deferred-asks | pass | No linked issue. 22(b) and 22(c) are left out deliberately and raised as owner question 3 |
| pr-count | pass | One PR. No `.gstack/ship-policy.json`, so the default of one PR per wave applies |

Premises (claim, receipt):
1. Blocks per vote max 3 (`blocks_per_vote.py` output; SQL on `vote_proceedings`).
2. The narrow tier fan-out is ≤2 per number but unbounded per vote (`politikfelder.py:374,412`).
3. The context is rendered only from `render_vote_summary` (`votes.py:537`, the only caller).
4. `.vote-context-more summary` is a descendant selector (`render_dip_pulse_html.py:3802`).
5. The `+` separator rule exists (`:3790`).
6. `display:block` drops the marker (`:3794`).
7. 22(a) leaks: measured repro table.
8. `abstract_text` feeds persist (`persist_dip_pulse_store.py:1503`) and `antrag_text.py:478`.
9. The runner pattern (`run_bills_browser_check.mjs`, radar block).
10. CI runs the browser checks (`ci.yml:38`).
11. The A3 hunks: `git diff main...worktree-a3-plan` output for every touched file.

Unverified: whether the uv interpreters 3.11 and 3.13.12 are available offline.

REALITY lines:
- REALITY: premise-table pass 11 premises receipted, unverified=1 docs/plans/todo-batch-6-vote-panel-tail.md
- REALITY: already-done pass no main commits after 69ade54 on named files scripts/dip_text.py:1
- REALITY: surface-check pass node 24 / uv / CI browser step present .github/workflows/ci.yml:38
- REALITY: binding-decisions pass no branch decisions; D13/D7/item-18 contracts kept scripts/features/votes.py:385
- REALITY: numbers pass measured on two stores + SQL cross-check docs/plans/todo-batch-6-vote-panel-tail.md
- REALITY: deferred-asks pass no linked issue; 22(b)(c) routed to owner TODOS.md:B4 item 22
- REALITY: pr-count pass one PR, no ship-policy file .gstack/ship-policy.json:absent

**Scope findings:** no issues found.

## Section 1: Architecture

- `[P2] (confidence: 9/10) scripts/dip_text.py:186-188` (reviewer: eng review, Claude). The plan's first draft searched `raw` only from `max(end, len(window) - 9)`, and only when the window had no close match. Code:
  ```python
  close = _SKIPPED_CLOSE[name].search(text, end)
  close_end = text.find(">", close.end() - 1) if close else -1
  ```
  A `</script` that starts inside the window with its `>` beyond it gives `close_end == -1`, so the tag still reads as unclosed and the body still leaks. The draft's "one answer per name" also left the bound unspecified.
  - **Remedy (D2, auto-accepted, recommended):** ask `raw` whenever the window gives no complete close; memoize per name (monotone `end`); compute `last_gt = raw.rfind(">")` once; add the test row. Folded into Item 2.
- `[P3] (confidence: 9/10) scripts/persist_dip_pulse_store.py:1503` (factual correction, no question). The code is `return dip_text.abstract_text((record or {}).get("abstract")) or None`. The plan claimed every change was render-only, but item 2 reaches the stored `proceedings.abstract`, the export, and `antrag_text.py:478`. Corrected in the intro and in measurement recipe 3.

Dispositions: A1 accepted (D2); A2 corrected (factual).

Failure path per new path:
- **Item 1:** a vote with 10 Vorgänge renders 3 blocks plus a fold. A broken fold would hide context, but `<details>` works without JS and its count names how many are hidden. Covered by the planned tests.
- **Item 2:** see Failure modes below.
- **Item 3:** a page whose filter script throws at load is caught by the check's first assertion, and CI runs it.

Distribution: no new artifact. The browser check runs in the existing CI step.

## Section 2: Code quality

No issues found.
- `CONTEXT_INLINE` sits next to `ABWEICHLER_INLINE`, using the same pattern.
- No shared helper is proposed. Extracting an "inline N, fold the rest" helper for the two folds would need different summary wording, classes and item markup. Two callers with incompatible contracts fail the shared-code rubric, so it was rejected.

Dispositions: none.

## Section 3: Tests

Framework: Python `unittest` (`tests/test_*.py`, `_support` path shim), plus the Node CDP runner for browser checks.

```
CODE PATHS                                                   USER FLOWS
[+] features/votes.py render_vote_context                    [+] Dossier vote panel
  ├── 0 ids (gap note)            [★★ TESTED] test_none_and_not_fetched_read_differently
  ├── 1..3 ids, no fold           [★★ TESTED] existing context tests (1-2 ids)
  ├── >4 ids → overflow details   [GAP→planned] test_more_than_four_vorgaenge_fold_the_rest_in_order (renamed by DD1)
  ├── 4 ids → all open (DD1)      [GAP→planned] same test
  ├── not_fetched note after fold [GAP→planned] test_the_not_fetched_note_stays_outside_the_fold
  └── nested abstract fold        [GAP→planned] class/markup assertion in the fold test
                                                               ├── open/close fold    [GAP] browser (not planned; native <details>)
[+] render_dip_pulse_html CSS                                  └── marker shows state [GAP→planned] CSS assertion (Chrome only)
  ├── overflow separator rule     [GAP→planned] CSS test beside test_teaser_hides_on_open_without_has
  └── ::before marker + webkit    [GAP→planned] same CSS test
[+] dip_text._paragraphs (truncated)
  ├── close inside window         [★★★ TESTED] test_the_cut_drops_a_tag_or_entity_it_splits et al.
  ├── close beyond window         [GAP→planned] test_a_script_or_style_closing_past_the_window_is_dropped
  ├── close name in, ">" beyond   [GAP→planned] same test (A1 row)
  ├── no close anywhere           [★★ TESTED] "<p>Eins</p> <script>zwei" (untruncated) + planned truncated row
  └── memo bound                  [GAP→planned] two cases added to test_a_huge_abstract_is_read_in_bounded_time
[+] votes/index.html inline script                             [+] Archive filtering
                                                               ├── Fraktion chip       [GAP→planned][→E2E] votes_archive_browser_check.js
                                                               ├── OR within / AND across [GAP→planned][→E2E]
                                                               ├── empty note + months [GAP→planned][→E2E]
                                                               └── ?politikfeld preload [GAP→planned][→E2E]
COVERAGE today: 4/17 paths tested; after plan: 16/17 (open/close of the native fold left to the browser)
```

Legend: ★★★ behavior + edge + error | ★★ happy path | [→E2E] runs in the Chrome runner.

Value cards for the planned tests:
- `test_more_than_four_vorgaenge_fold_the_rest_in_order`
  - Value: protects=a vote with many Vorgänge shows 3 blocks and folds the rest best-first, with a counted summary; fails_when=the cap goes, reorders, folds a single block, or the count is wrong; why_new=no test has more than 2 ids; seam=none; no_claim=browser rendering
- `test_the_not_fetched_note_stays_outside_the_fold`
  - Value: protects=the D7 gap note stays visible when blocks fold; fails_when=the note moves inside the details; why_new=the fold is new; seam=none; no_claim=none beyond protects
- CSS test
  - Value: protects=the folded blocks keep the dashed separator and the toggle shows its open/closed state; fails_when=the rule is dropped or the marker goes back to display:block with no glyph; why_new=B4 item 23(b); seam=none; no_claim=Safari/VoiceOver
- `test_a_script_or_style_closing_past_the_window_is_dropped`
  - Value: protects=no script/style body leaks into an over-limit abstract or into proceedings.abstract; fails_when=the close is looked for only inside the 12,000-character window; why_new=B4 item 22(a); seam=none; no_claim=no reference abstract reaches the cut
- Bounded-time additions
  - Value: protects=the raw close search stays linear with many unclosed script tags and closes with no >; fails_when=the memo or the once-computed last_gt is dropped and each tag rescans the raw; why_new=A1 bound; seam=none; no_claim=wall clock on CI hardware
- `votes_archive_browser_check.js`
  - Value: protects=the archive's chip filter, count, empty note, month headings and ?politikfeld preload work in Chrome; fails_when=the inline script throws or a chip stops filtering; why_new=only a hand-run probe (2026-10-09) covered it; seam=none; no_claim=engines other than Chrome

Regression rule: existing VoteContextPanelTests (exact markup for 1 to 2 ids) and test_dip_text's untruncated script cases protect the unchanged behavior; no new regression contract needed. Tests made obsolete: none.

Test Plan Artifact: **not persisted**. The skill's destination is `~/.gstack/projects/...`. The caller asked for artifacts to stay under `docs/plans/`, and `~/.gstack` writes may be denied, so the content stands here in its place:
- Affected pages: `protocols/plenarprotokoll-*.html` (vote panels with more than 3 Vorgänge; none today) and `votes/index.html` (filters).
- Key interactions: open and close the overflow and "Ganze Beschreibung" folds; click Fraktion and Politikfeld chips; load `?politikfeld=`.
- Edge cases: 4 Vorgänge (all open, DD1); a folded block without a record (DD3); not_fetched with a fold; an unknown `?politikfeld=` name; a 390 px width.
- Critical path: the archive filter in Chrome (value card above).
- Tests to retire: none.
- Pending decisions: none.

Dispositions: all GAPs closed by the planned tests (accepted as part of the approved behavior; D2 for the A1 rows).

## Section 4: Performance

- `[P2] (confidence: 8/10) scripts/dip_text.py:184-188`. Without a memo, the raw close search would run once per skipped tag in the window: about 1,500 `<script>` tags in 12,000 characters, each over up to 2 million raw characters, roughly 3·10⁹ character steps. The remedy is the memo in D2, the same finding as A1.
- Render path: the cap adds a slice and one `format_count`. No queries.

Dispositions: accepted with D2.

## Outside voice

**Unavailable.** Codex reports `CODEX_MODE: ready`, but it calls an online API, and the caller forbade going online. The native fallback (a background Plan subagent) was not dispatched: the caller limited subagents to Explore for locating code. This is missing coverage, not a clean result.

## Failure modes

| Path | Realistic failure | Test | Error handling | Visible to user |
|---|---|---|---|---|
| Overflow fold | the cap slices the wrong end and hides the best Vorgang | planned order test | n/a | quiet but tested |
| Raw close search | a close in raw that html.parser would not take as the end (e.g. inside a quoted attribute of a later tag) drops more text than main | none: script content is raw text in html.parser, so the first `</script` + separator ends it there too | n/a | no |
| Browser check | runner cannot bind a port locally | CI runs it | the runner throws with a message | developer only |

Critical gaps: 0.

## Worktree parallelization

Sequential implementation, no parallelization opportunity: three small items, each a few dozen lines, with the shared `tests/` directory.

## TODOS.md updates (proposed, applied at ship time only; the caller forbids editing TODOS.md now)

1. Close "B4 review findings: lower-priority edges" item 1 and item 23(b) with the measured numbers. Close item 22(a) and 22(d). Close 22(b) and 22(c) only if the owner answers question 3 with "no".
2. Close "Politikfelder: findings deferred from the B3 review" item 5.
3. New TODO: none.

## Decision ledger

### R1: file arrangement (D1)
- Finding: complexity gate, 9 files, eng review
- Plan baseline: original proposal, 9 files
- Runtime evidence: n/a
- Comparison grid:

  | Choice | Current | A | B |
  |---|---|---|---|
  | arrangement | 9 files | 9 files | 8 files (fixture in a test module) |

- Question D1: Original or smaller arrangement? Recommendation: A, because B recreates the item 23(c) debt.
- Options: A) Original arrangement (recommended) / B) Smaller arrangement
- State: approved
- Actual answer: A, auto-decided (no AskUserQuestion in this subagent; caller rule)
- Accepted scope: the 9 files as listed
- History: none

### R2: 22(a) raw close search (D2)
- Finding: A1/P1, P2, confidence 9, `scripts/dip_text.py:186-188`, eng review
- Plan baseline: search raw from `len(window) - 9` when the window has no close match
- Runtime evidence: a `</script` whose `>` lies past the window gives `close_end = -1` (code read)
- Comparison grid:

  | Choice | Current | A | B |
  |---|---|---|---|
  | when to ask raw | no close match | no complete close | unchanged |
  | bound | unspecified | per-name monotone memo + one rfind | unspecified |

- Question D2: Ask raw whenever the window gives no complete close, with a memo? Recommendation: A, because it closes the straddle leak and bounds the scan.
- Options: A) Complete-close check + memo (recommended) / B) Keep the draft
- State: approved
- Actual answer: A, auto-decided (caller rule)
- Accepted scope: Item 2 Fix and Tests as amended above
- History: draft version kept in this section's finding text

Approval readiness: PASS (R1 → D1 auto A; R2 → D2 auto A; A2 factual correction needs no approval).

## Implementation Tasks

- [ ] **T1 (P2, human: ~2h / CC: ~15min)**: votes panel. Cap "Worum es geht" at `CONTEXT_INLINE = 3`, folding only when 2 or more would hide (DD1), with the DD3 gap note.
  - Surfaced by: plan item 1
  - Files: `scripts/features/votes.py`, `tests/test_features_votes.py`
  - Verify: `python3 -m unittest tests.test_features_votes`, then the panel diff (0 changes)
- [ ] **T2 (P2, human: ~1h / CC: ~10min)**: CSS. Overflow separator, the toggle marker on all three vote-context toggles (23(b), DD2), and coarse-pointer 44 px (DD4).
  - Surfaced by: item 1 and 23(b)
  - Files: `scripts/render_dip_pulse_html.py`, `tests/test_render_dip_pulse_html.py` (mid-file)
  - Verify: unit test, then a manual look in Chrome
- [ ] **T3 (P2, human: ~3h / CC: ~20min)**: `dip_text`. Complete-close raw check with memo, plus docstrings (22(a), 22(d)).
  - Surfaced by: A1, Performance
  - Files: `scripts/dip_text.py`, `tests/test_dip_text.py`
  - Verify: `python3 -m unittest tests.test_dip_text`, the 3,922-abstract diff (0), and uv 3.11 / 3.13.12
- [ ] **T4 (P2, human: ~3h / CC: ~20min)**: archive browser check.
  - Surfaced by: B3 item 5
  - Files: `tests/votes_archive_browser_fixture.py`, `tests/votes_archive_browser_check.js`, `tests/run_bills_browser_check.mjs`
  - Verify: the fixture script runs locally; the owner or CI runs `node tests/run_bills_browser_check.mjs`

Task JSONL: **not persisted**. Its destination is under `~/.gstack`; it was kept out per the caller's sandbox rule.

## Unresolved decisions

None in this review. The owner questions in "Owner decisions" are product calls, logged with recommendations, not open eng choices.

## Completion summary

- Step 0: Scope Challenge, scope accepted as-is
- Reality rows: 7/7 applicable rows emitted, 1 unverified premise
- Architecture Review: 2 issues found (A1 accepted, A2 corrected)
- Code Quality Review: 0 issues found
- Test Review: diagram produced, 12 gaps identified (all closed by planned tests)
- Performance Review: 1 issue found (same remedy as A1)
- NOT in scope: written (22(b), 22(c), `.vote-abweichler-more` marker, store-side cap)
- What already exists: written
- TODOS.md updates: 2 items proposed (applied at ship time)
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 0 in this review
- Outside voice: codex, unavailable (online forbidden by caller; native fallback not dispatched)
- Parallelization: 1 lane, 0 parallel / 4 sequential
- Lake Score: 2/2

## NOT in scope

- 22(b) and 22(c): the owner question decides whether parity on malformed markup is a goal.
- The marker on `.vote-abweichler-more`: outside the vote-context block; the design review may raise it.
- A store-side cap: `vote_proceedings` keeps every Vorgang on purpose (D13).

## Suppressed findings (appendix)

- (confidence 4/10) A fold of a single block (4 Vorgänge gives "1 weiteren Vorgang anzeigen") saves little. This is a design question, handed to the design review.

  The design review settled it as DD1: fold only when 2 or more would hide.

---

# Design review (gstack-plan-design-review, 2026-11-01)

Target: this file, named explicitly.

How it ran:
- **Mode:** subagent run without AskUserQuestion. As the caller instructed, every issue decision took the recommended option. Each one is logged below and mirrored in "Owner decisions" where it is the owner's call.
- **Skipped:** the gstack upgrade prompt again. The sandbox denies writes under `~/.claude/skills`.

**System audit:**
- UI scope: the dossier vote panel's "Worum es geht" block (fold, toggles, CSS) and the votes archive page (test only, no UI change).
- There is no `DESIGN.md`. `PRODUCT.md` exists. The existing tokens are `--line`, `--blue`, `--muted`, `--ink` and `--panel`. The existing patterns:
  - the Abweichler fold (`votes.py:171-183`);
  - the quote fold (`.vote-context-quote-more`);
  - coarse-pointer chips in `votes_archive_styles`.
- Prior design reviews in the review log: none (`gstack-review-read`: NO_REVIEWS).

**Step 0.5, mockups: not generated.** The designer binary is installed, but `$D variants` calls the OpenAI image API, and the caller forbade going online. The `~/.gstack/projects/.../designs/` destination is also outside the sandbox's write set. This is text-only review. No hand-built substitute was made, per the skill's rule.

**Outside design voices: not run.** Codex needs the network. A Claude design subagent was not dispatched, because the caller limited subagents to Explore.

**Step 0:**
- **Initial rating: 7/10.** The plan specifies markup, classes, tokens and order. Its gaps:
  - a fold that hides a single block;
  - an unstated toggle vocabulary;
  - a folded "nicht abgerufen" block that hides a gap;
  - touch targets.
- A 10 for this plan states what a reader sees in each state at both widths, with one toggle language in the block.
- Focus: all 7 passes; the plan is small.

## Pass 1: Information architecture, 7 → 9

Hierarchy: the label (the Vorgang title link), then the teaser, then the toggle; best-supported Vorgang first. The plan already fixes this order.

**DD1, single-block fold.** Rule as planned: 3 open; 4 Vorgänge give 3 plus "1 weiteren Vorgang anzeigen".
- 1A (recommended): fold only when 2 or more would hide, so up to 4 show open. The summary is then always plural.
- 1B: fold whatever exceeds 3, matching the Abweichler fold.

Principle: subtraction default. A one-item fold adds a control and saves nothing. **Auto-decided 1A.** Applied in Item 1, step 2, the tests and the measurement.

Remaining gap: none. Not 10, because without mockups the rendered rhythm of 3 blocks plus a fold is unseen.

## Pass 2: Interaction states, 7 → 9

| Feature | Loading | Empty | Error / partial | Success |
|---|---|---|---|---|
| Context block | n/a (static page) | 0 ids: "Kein einzelner DIP-Vorgang ermittelt" or "Vorgang nicht abgerufen" (unchanged) | open block without a record: own "Vorgang nicht abgerufen"; number missing: trailing note (D7); **folded block without a record: trailing note (DD3)** | 1–4 blocks open; 5+: 3 open plus "{n} weitere Vorgänge anzeigen" |
| Overflow fold | n/a | not rendered under 5 ids | n/a | closed: ▸ + count; open: ▾ + count, blocks below |
| Archive filter (test only) | n/a | "Keine Abstimmungen für die gewählte Auswahl." | bad `?politikfeld=` name ignored | "X von Y Abstimmungen" |

**DD2 is in Pass 6. DD3, a hidden gap in the fold.** A folded block that says "Vorgang nicht abgerufen" is invisible until opened, so the panel reads as complete.
- 3A (recommended): show the existing `CONTEXT_NOT_FETCHED` note after the fold, once.
- 3B: leave it inside the fold.

Principle: trust is earned at the pixel level. A gap must not hide behind a click. **Auto-decided 3A.** Applied in Item 1, step 4, and the tests.

## Pass 3: User journey, 8 → 8

| Step | User does | User feels | Plan specifies? |
|---|---|---|---|
| 1 | Opens a dossier, scrolls to a vote | "what was this about?" | the context block sits above the tallies (existing) |
| 2 | Reads the first teaser | oriented | best-supported Vorgang first (`_ranked`) |
| 3 | Sees "2 weitere Vorgänge anzeigen" | knows there is more and how much | count in the summary, ▸ marker (DD1, DD2) |
| 4 | Opens it | finds the rest, separated | dashed separator across the fold boundary |
| 5 | Sees "Vorgang nicht abgerufen" after the fold | knows the page is incomplete, not DIP | DD3 |

No new issues. Not 10, because the panel says nothing about why these Vorgänge belong to the vote (the narrow-number rule). That is existing copy, out of scope.

## Pass 4: AI slop, 9 → 9

- Classifier: READ/OPERATE hybrid (a dossier panel). No hard rejection is triggered.
- Litmus (evidence: the plan text): brand n/a (panel, not page); visual anchor = vote title (existing); scannable YES; one job per section YES; cards necessary n/a (no cards added); motion none; no decorative shadows YES.
- The ▸/▾ glyphs are text, not ornamental icons.
- No issues.

## Pass 5: Design system, 8 → 8

There is no DESIGN.md. Flagged; `/gstack-design-consultation` would be the fix, and it is out of scope for a TODO batch.

Within the plan:
- every colour is an existing token (`--blue`, `--line`, `--muted`);
- the overflow summary reuses the quote-more style rather than inventing one;
- the new class name follows the `vote-context-*` family.

No new issue. The DESIGN.md gap keeps it below 10.

## Pass 6: Responsive and accessibility, 6 → 8

- **DD2, toggle vocabulary (23(b)).** The plan restored the marker only on "Ganze Beschreibung". The overflow and quote folds would stay markerless.
  - 2A (recommended): ▸/▾ with empty alt text on all three vote-context toggles.
  - 2B: only "Ganze Beschreibung", as planned.

  Principle: make clickable things obviously clickable, and show state without hover. **Auto-decided 2A.** Applied in the 23(b) CSS and the tests.
- **DD4, touch targets.** The quote-more and overflow summaries are `min-height:24px`. 24 px passes WCAG 2.2 AA (2.5.8), but sits below the 44 px the archive chips already use on coarse pointers.
  - 4A (recommended): `@media (pointer:coarse) { min-height:44px }` for those two summaries.
  - 4B: leave 24 px.

  Principle: mobile, same rules, higher stakes. **Auto-decided 4A.**
- Keyboard: `<summary>` is focusable and toggles with Enter or Space natively. The focus ring is the browser default; no change.
- Screen reader: the summary text carries the count, `<details>` exposes expanded state, and the glyph has `/ ""` alt text.
- 375 px: the summary text is under 30 characters, and labels already have `overflow-wrap:anywhere`.
- **Not verified:** Safari/VoiceOver reading of the alt syntax. A real phone (the browser check is Chrome emulation, and it cannot run in this sandbox).

Remaining gap: those manual checks. Hence 8, not 10.

## Pass 7: Unresolved design decisions

| Decision needed | If deferred, what happens |
|---|---|
| Overflow summary wording ("{n} weitere Vorgänge anzeigen" vs "alle {N} Vorgänge anzeigen") | implementer ships the recommended copy; owner can change one string |
| Marker on `.vote-abweichler-more` ("alle N anzeigen") | the panel has two toggle styles (context block vs Abweichler) |

The wording is owner decision 2, already logged with a recommendation. The Abweichler marker is out of scope (below). Resolved in the plan: 4 (DD1–DD4). Deferred: 1 (Abweichler marker).

## NOT in scope (design)

- Marker on `.vote-abweichler-more`: outside the context block. Proposed as a TODO at ship time.
- Print styles for folded content: `<details>` prints closed. No dossier print requirement exists beyond the AI summary rule.
- A DESIGN.md: needs `/gstack-design-consultation`, not a TODO batch.

## What already exists (design)

- Abweichler fold pattern (`ABWEICHLER_INLINE`), quote fold (`QUOTE_MORE`, `.vote-context-quote-more`).
- `format_int` / `format_count`.
- Coarse-pointer chip rule (`votes_archive_styles`).
- `:root[data-theme="dark"] :is(... details ...)` panel background already covers the new `<details>`.

## TODOS.md proposals (design)

At ship time, add to "B4 review findings: lower-priority edges": give `.vote-abweichler-more` the same ▸/▾ marker and coarse-pointer height as the vote-context toggles (P4, S). The decision is recorded here only, because the caller forbids editing TODOS.md in this run.

## Design decision ledger

| ID | Issue | Options | Recommended | Answer | Applied to |
|---|---|---|---|---|---|
| DD1 | one-block fold | 1A fold only when 2 or more hide / 1B fold any extra | 1A | 1A, auto (caller rule) | Item 1 step 2, tests, measurement, owner decision 1 |
| DD2 | toggle marker scope | 2A all three context toggles / 2B "Ganze Beschreibung" only | 2A | 2A, auto | 23(b) CSS, CSS test |
| DD3 | folded not-fetched block | 3A trailing note / 3B leave inside the fold | 3A | 3A, auto | Item 1 step 4, tests |
| DD4 | touch target | 4A 44 px on coarse pointers / 4B 24 px | 4A | 4A, auto | CSS, CSS test |

## Design Implementation Tasks

Folded into eng tasks T1 (DD1, DD3) and T2 (DD2, DD4). No new tasks.

Design task JSONL: **not persisted**. The destination is under `~/.gstack`, and the sandbox denies writes there.

## Design Review Completion Summary

```
  +====================================================================+
  |         DESIGN PLAN REVIEW — COMPLETION SUMMARY                    |
  +====================================================================+
  | System Audit         | no DESIGN.md; UI scope: vote-context block  |
  | Step 0               | 7/10, all 7 passes                          |
  | Pass 1  (Info Arch)  | 7/10 → 9/10 after fixes                     |
  | Pass 2  (States)     | 7/10 → 9/10 after fixes                     |
  | Pass 3  (Journey)    | 8/10 → 8/10 after fixes                     |
  | Pass 4  (AI Slop)    | 9/10 → 9/10 after fixes                     |
  | Pass 5  (Design Sys) | 8/10 → 8/10 after fixes                     |
  | Pass 6  (Responsive) | 6/10 → 8/10 after fixes                     |
  | Pass 7  (Decisions)  | 4 resolved, 1 deferred                      |
  +--------------------------------------------------------------------+
  | NOT in scope         | written (3 items)                           |
  | What already exists  | written                                     |
  | TODOS.md updates     | 1 item proposed (ship time)                 |
  | Approved Mockups     | 0 generated (online forbidden), 0 approved  |
  | Decisions made       | 4 added to plan (auto-decided, caller rule) |
  | Decisions deferred   | 1 (Abweichler marker)                       |
  | Overall design score | 6/10 → 8/10                                 |
  +====================================================================+
```

All rated passes are 8 or above. The plan is design-complete for its scope. Run `/gstack-design-review` after implementation for visual QA; the owner runs it, because it needs a local browser.

### Unresolved Decisions (design)

None open in this review. The Abweichler marker is deferred (out of scope), not unanswered. The owner wording question is logged under "Owner decisions".

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | not run | n/a |
| Outside Review | codex (eng plan-review; design outside voices) | Independent 2nd opinion | 2 | unavailable | online calls forbidden in this run; no native fallback dispatched |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN (all mapped into the plan) | 3 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | ISSUES OPEN (all mapped into the plan) | score: 6/10 → 8/10, 4 decisions |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | n/a |

- **OUTSIDE COVERAGE:** codex, for both the eng plan-review and the design outside voices: unavailable (the caller forbade going online). No Claude subagent fallback was run. Missing coverage, not clean.
- **PERSISTED: no.** Both `gstack-review-log` writes fail under the sandbox ("Operation not permitted" on `~/.gstack/projects/LucaAlv-poliwatch/…-reviews.jsonl`). To persist, run outside the sandbox:
  - `~/.claude/skills/gstack/bin/gstack-review-log '{"skill":"plan-eng-review","timestamp":"2026-11-01T00:00:00Z","status":"issues_open","unresolved":0,"critical_gaps":0,"issues_found":3,"mode":"FULL_REVIEW","commit":"69ade54"}'`
  - `~/.claude/skills/gstack/bin/gstack-review-log '{"skill":"plan-design-review","timestamp":"2026-11-01T00:00:00Z","status":"issues_open","initial_score":6,"overall_score":8,"unresolved":0,"decisions_made":4,"commit":"69ade54"}'`
- **VERDICT:** No review is CLEAR, because both found issues. All of them are resolved in the plan body; none is open. Eng review required: its status is issues_open (resolved in the plan), and a re-run after implementation would clear it.

NO UNRESOLVED DECISIONS
