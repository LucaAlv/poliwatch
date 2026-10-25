# B4 review fixes

Fixes for every finding of the two-axis `/code-review` of `main...HEAD` on `worktree-b4-abstimmungen-daily-view` (2026-10-20, tip 638e9ba). Spec: `docs/plans/b4-daily-votes.md`.

## Decisions (user, 2026-10-20)

- **E1 Panel parameters:** use one required panel context and amend R8. `render_vote_summary` loses its optional `report`, `vote_contexts` and `vorgang_cache`. Tests build the context through one helper.
- **E2 D7 gap:** a vote is `not_fetched` when any resolved Vorgang has no cached record. Its `vote_proceedings` rows are still written.
- **E3 Titel migration:** run the online refetch on a copy of the reference cache, then delete the `"titel" not in record` refetch and the F10 Vorgangstyp fallback.

## Facts checked before planning

Each item below was checked; it is not taken from the reviewers' word.

- **Legacy vote shapes on the reference data:** 290 reports, 246 vote occurrences. **0** items use the singular `"vote"` key and **0** votes lack an id. The scraper always sets `id` (`validate_dip_protocol.py:1672`). The legacy branches are therefore dead on the only store that matters.
- **Reference Vorgang cache:** **0** of 7511 records have the `titel` key, so every context label today is the F10 fallback.
- **`vote_key = derive.vote_identity`:** existed on main before B4 (`politikfelder.py:517`), so it is not a B4 finding. The other six copies of the `votes or [vote]` idiom also predate B4; B4 added one.
- **"TOP" and "sitting" in docstrings:** CONTEXT.md itself writes "TOP", so this finding is dropped.
- **`"Keine Abweichler (…)"`:** was chosen in f29e322 to state the counting rule. It is not a recorded decision against the glossary's public-text rule, so it gets fixed here.
- **`_vote_procedure_type(item=None)`:** this is a real case (a vote under no TOP), not a shim. Only the `sitting_documents=None` default is a shim.
- **`documents.herausgeber`:** `NOT NULL CHECK IN ('BT','BR')` (`persist_dip_pulse_store.py:230`), so the recipe can filter on it.

## Step 1: mechanical fixes (no figure moves)

1. **Recipe count.** Comments say "the recipes" with no number (`build_dip_pulse_site.py:29, :2348, :2515, :3588`). The Daten eyebrow (`:3962`, still "Fünf Abfragen"), the lede (`:3964`) and the landing text (`:4125`) take the number word from a small `_recipe_count_word()` over `len(RECIPES)`.
   - In README.md:14 and `docs/project-documentation.md:154, :433`, drop the count ("die SQL-Rezepte" / "the `RECIPES`").
   - Add a test that the eyebrow and lede word equals `len(RECIPES)`.
2. **False comment.** `render_dip_pulse_html.py:539` ("the dossier .vote-panel stays light") should say that both the archive row and the panel turn dark, since 638e9ba added `.vote-panel` to the dark override.
3. **Duplicate gap note.** `render_vote_summary` builds `<p class="vote-state-note vote-abweichler-gap">` twice. Make it one module constant `ABWEICHLER_GAP_HTML`.
4. **Feature Envy.** `render_committee_line(committees, item)` becomes `render_committee_line(committees, links)`. The caller passes `document_source_links(item)`.
5. **Names:**
   - `vote_ctx` → `votes_component_ctx` (`render_dip_pulse_html.py:2950`).
   - `context_html` → `vote_context_html`.
   - `_join_de` → `join_with_und`.

## Step 2: drop the legacy vote shapes

This also covers Standards #1 for `vote_anchor_id` and the duplicated idiom.

1. Add `derive.item_votes(item) -> list` (`item.get("votes") or []`). Replace all 8 copies of `item.get("votes") or ([item["vote"]] if …)`:
   - `derive.py:343`
   - `politikfelder.py:560, :640`
   - `features/votes.py:316`
   - `render_dip_pulse_html.py:1511, :2131`
   - `persist_dip_pulse_store.py:1551`
2. Delete the singular-`vote` carry-forward branch (`build_dip_pulse_site.py:1967-1968`).
3. `derive.vote_identity` becomes `str(vote["id"])`, and its (title, date) branch goes.
   - `vote_anchor_id` returns `str` and is never `None`.
   - The archive href loses its implicit None case.
   - The archive's "persist skips a vote without an id" skip and persist's `if not vote_id: continue` (`:1232, :1443, :1477`) become a raised error. A vote with no id is now a scraper bug, not data.
4. In report loading, add one guard that raises on an item with a `"vote"` key or an id-less vote, naming the report. A stale cached report then fails loudly instead of dropping votes. This is a refusal, not a shim.
5. Tests:
   - Delete `test_a_vote_without_id_keeps_no_anchor` and any test feeding the singular key or `vote_id=None` (e.g. `test_features_votes.py:256`). Replace them with one test that the guard raises.
   - **Amend D9** in the B4 plan: "A vote without an id keeps the TOP anchor" is withdrawn, because none exist (0/246) and the shape is refused.

## Step 3: panel context and the long function (E1)

1. Add a `VotePanelContext` dataclass in `features/votes.py` with fields `report`, `vote_contexts`, `vorgang_cache`, `mp_lookup` and `mp_prefix`.
   - The signature becomes `render_vote_summary(item, acquisition, panel)`.
   - `VotesComponent.dossier_sections` builds it from ctx.
   - The `{"agenda_items": [item]}` stand-in and "without vote_contexts no block is drawn" both go. A missing context is a caller bug.
   - `render_abweichler` and `member_name_html` take `panel` instead of `(mp_lookup, mp_prefix)`.
2. Make `_vote_procedure_type`'s `sitting_documents` required.
3. Split `render_vote_summary` into four helpers. The body keeps only the loop and the panel assembly.
   - `_panel_id(vote, item, first_item, anchored)`
   - `_fraction_group_html(fraction, abweichler, no_members, panel, vote)`
   - `_abweichler_summary_html(abweichler, no_members)`
   - `_member_sections_html(vote, panel)`
4. Tests: add one `panel_for(item, **overrides)` helper in `test_features_votes.py` and `test_mehrheitsvotum.py`. The ~40 call sites change only by passing it.
   - **Amend R8** to name this as an intentional update, next to the href (D9) and the procedure type (D4).

## Step 4: types for the context answer

1. Add `politikfelder.VoteContext(NamedTuple)` with `vorgang_ids: list[str]` and `state: ContextState`, where `ContextState = Literal["resolved", "none", "not_fetched"]`. `CONTEXT_STATES` is derived from `get_args`. `vote_vorgang_ids`, `report_vote_vorgaenge`, the persist loop and the panel read `.vorgang_ids` and `.state` instead of unpacking a tuple.
2. In `derive.vote_abweichler`, the state `"none"` (no member rows) becomes `"no_members"` so it no longer collides with the context `"none"`. Add `AbweichlerState = Literal["no_members", "partial", "complete"]`. _Amended at ship (/ship review, 2026-10-22): the alias was dropped as unreferenced; the states stay documented in `vote_abweichler`._

## Step 5: D7 state (E2)

1. `vote_vorgang_ids` returns `VoteContext(ids, "not_fetched")` when `ids` is non-empty but any id has no record in `cache["vorgaenge"]`.
   - Persist still writes those `vote_proceedings` rows.
   - The panel already says "Vorgang nicht abgerufen" per block, so it is unchanged.
2. Reword the docstring of `CONTEXT_STATES` and the captions of `votes` and `vote_proceedings`: "not_fetched: at least one Vorgang or Drucksache is not in the cache; rows that are known are still listed".
3. Tests:
   - Add one `vote_vorgang_ids` case with a resolved id whose record is missing.
   - Add one persist case: rows written, state `not_fetched`.
   - Rework `test_the_state_is_resolved_then_not_fetched_then_none` to the new precedence.
4. **Figure move:** report `context_state` counts old→new on the replay. Some votes now counted `resolved` will move to `not_fetched`.

## Step 6: recipe matches the panel

The r6 SQL gets `AND d.herausgeber = 'BT'`, so the recipe and `derive.report_drucksachen` drop Bundesrat papers alike. The D1 equality test then holds by construction, not by today's data. Report the r6 rows old→new; D15 suggests 0 moved.

## Step 7: glossary wording (CONTEXT.md)

1. Public strings follow the Abweichler entry:
   - `ABWEICHLER_NONE`: "Niemand stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe (gezählt: Ja gegen eine Nein-Mehrheit oder Nein gegen eine Ja-Mehrheit)"
   - `ABWEICHLER_GAP`: "Einzelstimmen unvollständig – nicht ermittelbar, wer anders als die Mehrheit der eigenen Fraktion oder Gruppe stimmt"
   - Archive badge: "N stimmen anders als die eigene Fraktion oder Gruppe" (singular "1 stimmt …"). The `data-abweichler` attribute and code identifiers keep the term; the glossary allows it outside public text.
2. Add glossary entries in the CONTEXT.md style (definition, _Avoid_):
   - **Vorgangsbeschreibung**, the "Worum es geht" block: the DIP abstract of the Vorgänge a vote is about, which describes the Vorhaben and never the result.
   - **Beschlussempfehlung (zitiert)**, the committee line: a citation of the document, not a claim of a committee role (D14).
   - **context_state** under the export terms.

## Step 8: module boundaries

1. Add a new `scripts/dip_text.py` for turning DIP fields into German display text. It takes:
   - `_AbstractParser` and `abstract_text`, moved from `politikfelder.py`
   - `abstract_teaser` and `_ABBREVIATIONS`, from `features/votes.py`
   - `committee_genitive` and `join_with_und`, from `features/votes.py`

   `politikfelder.py` returns to tagging and fetch targets. `features/votes.py` keeps rendering and `dip_vorgang_url`, which is its only caller.
2. Move the tests with them: the `abstract_text` cases out of `test_politikfelder.py`, and the genitive and teaser cases out of `test_features_votes.py`, into `tests/test_dip_text.py`.

## Step 9: titel refetch, then delete the migration (E3)

This step needs the network. DIP throttles after a few hundred requests, so allow pauses.

1. Copy `/Users/Luca/Projects/poliwatch/.context/dip-pulse-site/data` to a scratch directory. Run one **online** build against the copy, never the original. That is about 3 titel batches plus the D11 empty-abstract refetch.
2. Record two things:
   - **The D11 count** (still owed by the B4 plan): votes with a DIP abstract before and after, against the plan's "about 153". Of the 64 empty-abstract Vorgänge, how many gained one.
   - Titel coverage after the refetch. Also record how many records DIP returns with an empty `titel`.
3. Delete the migration code:
   - The `"titel" not in record` clause in `fetch_targets`. The empty-abstract refetch stays, because DIP fills abstracts late; that is D11, not migration.
   - The F10 Vorgangstyp fallback in `_vorgang_label`.
   - The "predates the field" sentence in `vorgang_cache_record`.

   Keep one plain label, "DIP-Vorgang <id>", only for an empty `titel` from DIP, if step 2 finds any.
4. Promote the refreshed cache to the reference location only with your OK. That overwrites shared data.

## Step 10: amend the B4 spec (scope that is ratified, not reverted)

Record these in `docs/plans/b4-daily-votes.md` as deliberate. Reverting them would lower quality.

- **`committee_genitive`:** "des <Ausschuss>" needs the genitive to be grammatical, and the "Urheber:" form is the refusal to guess.
- **`abstract_teaser`'s abbreviation list and word-boundary ellipsis:** without them, "about 300 characters cut at a sentence" cuts after "Abs.".
- **`.vote-no-result`:** the restyle in 638e9ba.
- **`report_drucksachen`'s BT filter:** now mirrored in the recipe by Step 6.
- **The `vorgang()` fixture edit in `test_politikfelder.py`:** D11 itself makes the old `fetch_targets` expectation refetch `d`, so "must pass untouched" conflicts with D11. Name it in R8's intentional updates.
- **D9:** withdrawn as described in Step 2. **D7:** precedence per Step 5.

## Result (2026-10-20)

Steps 1–10 are committed (dd084e2 … 50b21ec). Offline replay of bdd9fa2 (after step 8) against 638e9ba, both on copies of the reference store, `--offline --repersist` (512 s / 615 s):

- 28 CSVs both sides; every cell equal apart from `created_at`/`updated_at` and the `datenstand` row.
- Tags 0 moved, 217 votes, archive `data-abweichler` sum 632, 190 votes with a BT Beschlussempfehlung, r6 rows identical (Step 6: 0 moved).
- `votes.context_state` (Step 5): resolved 217 → 217, 0 moves. On this cache every resolved Vorgang has a record (0 of 234 missing), so the new D7 rule moves nothing yet.
- Step 9 (online, on a copy): 4,289 Vorgänge refetched, 0 failed; titel 0 → 234 of 234 context Vorgänge, 0 empty; D11: 0 of 86 empty-abstract context Vorgänge gained one, votes with an abstract 153 → 153. The refreshed cache is in the scratch copy only, not promoted.

## Order and gates

Do steps 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 as separate commits. Run the full test suite after each one.

After step 8, run the offline replay on a copy of the reference store (`--offline --repersist`, 900 s bound). Compare it with a replay of 638e9ba:

- Abweichler total 632
- tags 0 moved
- vote count 217
- committee coverage 190/217
- the Daten CSV diff shows only:
  - `votes.context_state` moves (Step 5, reported old/new)
  - r6 rows, if any (Step 6)
  - UI text

Step 9 runs last, because it needs the network and touches the cache, and it gets its own commit with the figures from step 9.2. Update CHANGELOG and TODOS (D11 line at TODOS.md:884-885) with the old and new numbers.
