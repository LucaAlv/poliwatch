# B4 follow-up: extractive "Worum es geht" from the Antrag itself

Planned and implemented (steps 1–4) 2026-10-28; step 0 and step 5 open, see "Implementation status". Scope: the open bullet "Extractive fallback from the Antrag itself" of [Abstimmungen for the daily view](../../TODOS.md#abstimmungen-for-the-daily-view-what-was-decided-by-topic-with-dissenters). Base: `main` at `71ade83` (v0.23.0.0, #111). Coordinated with A3 ([a3-coverage.md](https://github.com/LucaAlv/poliwatch/blob/worktree-a3-plan/docs/plans/a3-coverage.md) on `worktree-a3-plan`), see "A3 coordination".

## Problem

64 of 217 votes on the reference store have no DIP abstract (measured 2026-10-20); their "Worum es geht" block says "Keine Beschreibung in DIP". The research note ([bundestag-vote-pages.md](../research/bundestag-vote-pages.md) §5, §6.2) found that 45 of the 50 abstract-less votes (any-number method) are `Antrag` Vorgänge, 3 Entschließungsanträge, 1 Vertrauensantrag and 1 Gesetzentwurf: DIP's documentation service writes no abstracts for opposition Anträge. The Bundestag's own editors fill that gap by paraphrasing section II of the Antrag ("Der Deutsche Bundestag fordert die Bundesregierung auf: 1. …"). A Drucksache is an amtliches Werk (§ 5 UrhG), so we can quote that passage verbatim with a source line (§§ 62/63), with no model and no validators.

WP 18 and 19 (A3) add about 480 sittings of votes, and their Anträge are just as abstract-less, so the share without a description grows with coverage. The feature is worth more after A3 than before it.

## Product behaviour

Where a vote's context block would say "Keine Beschreibung in DIP", and the Vorgang's initiating document is an Antrag or Entschließungsantrag of a Bundestag Fraktion or Gruppe, show instead:

> **Worum es geht** · Quelle: Deutscher Bundestag – Drucksache 21/2234
> *Aus dem Antrag der Fraktion BÜNDNIS 90/DIE GRÜNEN „BAföG-Reform …“ (Drucksache 21/2234), Abschnitt II:*
> „Der Deutsche Bundestag fordert die Bundesregierung auf,
> 1. …
> 2. …“
> [Alle 9 Forderungen] (fold, same `<details>` pattern as "Ganze Beschreibung")

Rules:

1. **Verbatim or nothing.** The passage is the document's text with layout artefacts removed (page headers and footers, line-break hyphenation, the numbering the PDF layout split from its item). No word is changed, reordered or summarised. Where the extractor cannot find the passage with confidence, the panel keeps "Keine Beschreibung in DIP" (an honest gap beats a wrong quote).
2. **Fallback only.** A Vorgang that has a DIP abstract keeps it; the quote is not added beside it (D1, open for review).
3. **No outcome in the block.** As today, "Worum es geht" describes the Vorhaben; the result and the inversion stay in the lead sentence and badge. The attribution ("Aus dem Antrag der Fraktion …") names who demanded it, so a quote of a rejected AfD Antrag cannot read as the Bundestag's position. The lead sentence above it already says "Die Empfehlung lautete, den Antrag abzulehnen; …" on inverted votes (v0.22 interpretation, persisted).
4. **Teaser and fold.** First the opening clause and the first `n` numbered demands up to about `dip_text.CONTEXT_TEASER` characters, the rest in a fold. Never cut inside a demand: when the first demand alone is longer than the budget, the teaser is the opening clause plus that whole demand (R5).
5. **Source line** links the Drucksache PDF (`documents.url`, dserver host, validated by `html.source_url`) and names DIP as the text source.

Out of scope: Gesetzentwürfe (their "A. Problem / B. Lösung" block is a separate, later candidate, D2), Vertrauensanträge, Bundesrat documents, section I ("stellt fest"), any paraphrase, the AI sentence (deferred 2026-10-20).

## Data flow

```
report (cached, unchanged)            Vorgang cache (unchanged)
  vote.document_numbers  ─────┐        vorgaenge[id].abstract == ""
                              ▼              │
           politikfelder.vote_vorgang_ids ◄──┘   (narrow tier, as today)
                              │ abstract-less Vorgänge of the vote
                              ▼
        antrag_text.passage_targets(vote, report, vorgang cache, text cache)
           → BT Drucksache numbers whose type is unknown, or known Antrag / Entschließungsantrag
                              │ (online only, cache misses)
                              ▼
        DIP /drucksache?f.dokumentnummer=…&f.zuordnung=BT   (metadata, batched; R1)
                              │ only Antrag / Entschließungsantrag of a context Vorgang
                              ▼
        DIP /drucksache-text?f.id=…  ──►  data/dip-drucksache-text-cache.json.gz
                              │                       {number: {id, typ, urheber, titel, datum,
                              ▼                                 pdf_url, text, aktualisiert}}
        antrag_text.extract_forderung(text)  (pure, versioned: EXTRACTOR_VERSION)
                              ▼
   persist: documents.forderung, documents.forderung_state,
            vote_passages(vote_id, document_id, rank), votes.passage_state
                              ▼
   render: features/votes.render_vote_context (reads store-equivalent derivation, as context does today)
   export: format 9 (documents.forderung*, vote_passages, votes.passage_state)
```

Why each piece:

- **Which Drucksache.** The vote's own narrow numbers first: a Beschlussempfehlung vote's description names the Antrag it recommends on ("Drucksachen 21/2234, 21/8613"), and `derive.report_drucksachen` already knows the type of numbers linked in the sitting. A number whose type the report does not know is resolved by a batched `/drucksache` metadata call first (R1): a vote's numbers also name Beschlussempfehlungen and Gesetzentwürfe, whose full text can run to hundreds of KB, and only Anträge are worth fetching. Unlike `/vorgang`, each `/drucksache` record carries its own `dokumentnummer`, so a repeated `f.dokumentnummer` batch can be split by number. Keep a document only when its type is `Antrag` or `Entschließungsantrag`, its herausgeber is BT, and it belongs to one of the vote's context Vorgänge (`vorgangsbezug` in the DIP record). That last condition is what keeps a bundled Beschlussempfehlung from quoting a neighbouring Antrag (the same trap D7 closed for abstracts).
- **Text source: DIP `drucksache-text`, not the PDF.** It is the same API, key and client as the Vorgang fetch (`dip.ApiClient.list_all`), it carries the metadata, and it needs no `pdftotext` dependency. Not yet tried (no API key in the research session, none in this one): step 0 measures it, and if its text is unusable for WP 18/19 the PDF path is the fallback (D3).
- **Raw text cached, passage derived.** The cache keeps DIP's full text, so a change to the extractor re-runs offline in `--offline --repersist`, like the XML re-parse in A1, with no refetch. It is a separate gzip file, not a field of the Vorgang cache, so the published Vorgang cache does not grow by megabytes and its load time stays as is (D4). Estimated size: about 1,000 roll-call votes WP 18–21, about a third without abstract, about 1.3 Anträge each, 10–30 KB text each: 5–12 MB raw, 1.5–4 MB gzipped. Step 0 measures it.
- **Stored on `documents`.** The passage belongs to a document, not a vote: one Antrag can be the subject of several votes (Buchstaben, Wiederholung). `vote_passages` is the vote→document choice with rank, the analogue of `vote_proceedings`; `votes.passage_state` is the analogue of `votes.context_state` and feeds the same replay guard.

States (one vocabulary for `documents.forderung_state`, `votes.passage_state` where it applies):

| State | Meaning | Panel |
|---|---|---|
| `extracted` | text fetched, passage found | the quote |
| `no_passage` | text fetched, extractor found no section II | "Keine Beschreibung in DIP" |
| `not_fetched` | text not in the cache (offline, failed fetch) | "Vorgang nicht abgerufen" note, as today |
| `not_applicable` | vote has an abstract, or no Antrag-type document | today's block, unchanged |

The decision is per context Vorgang, not per vote: a vote about two Vorgänge, one with an abstract and one without, shows the abstract in the first block and the quote in the second. Each block then carries its own source line (R4); the shared head keeps only "Worum es geht".

## Extraction rule (to be fixed by step 0's measurement, not guessed)

Starting hypothesis from the research reading of 21/2234 and general Drucksache structure:

1. Normalise layout only: drop the running header/footer lines (`Deutscher Bundestag – 21. Wahlperiode – 3 – Drucksache 21/2234`), join hyphenated line breaks where the joined word occurs elsewhere in the text or the break is before a lower-case letter, join wrapped lines inside a paragraph.
2. Find the anchor: a line matching `^(II\.\s*)?Der (Deutsche )?Bundestag fordert die Bundesregierung (daher |deshalb |insbesondere )?auf` (case-sensitive on "Bundestag"). In older Anträge the frame is "Der Bundestag wolle beschließen: I. … II. …"; the anchor still holds for II. One anchor only; two anchors (Anträge with several "fordert" sections, e.g. "auf europäischer Ebene") → take the first and count the case in step 0.
3. End: the first of "Berlin, den", "Begründung", a next Roman-numeral section heading (`^III\.`), or the end of text.
4. Split demands on the list markers (`1.`, `a)`, `–`, `•`), keeping each item's text whole.
5. Sanity bounds: passage 40–8,000 characters, at least one demand or a single clause ending in a full stop; outside the bounds → `no_passage`.

Anträge that only "stellt fest" or "begrüßt", Entschließungsanträge whose operative part is "Der Bundestag lehnt … ab", and Vertrauensanträge become `no_passage` unless step 0 shows a second anchor worth adding (D5).

`EXTRACTOR_VERSION` is stored with the store's input fingerprint, like `speech_kinds.VERSION`, so a store built by another extractor version refuses facts/export until repersisted (the `require_current_speech_rules` pattern).

## A3 coordination

A3 owns the acquisition run for WP 18–21 (Phase 3) and is changing the online fetch path (pacing windows, `--sleep` defaults, the `/person` cache, exit codes) on `worktree-a3-plan`, which has not been merged and is based on v0.20. The agreements this plan needs, so historical votes get the quote without a second backfill:

1. **No report change.** B4-extractive reads only fields every cached report already has (`document_numbers`, `linked_drucksachen`) and two caches keyed by Vorgang id and Drucksache number. A3's acquired WP 18/19 reports need no new field and no re-acquisition, whichever branch merges first.
2. **One enrichment pass.** The text fetch is a third stage of `refresh_vorgang_cache` (after ids and numbers), driven by a pure `fetch_targets`-style function that returns only cache misses. A3's Phase 3 step 3 ("Vorgang cache fill") then fills the texts for every historical vote in the same run if B4 lands first. If A3's backfill runs first, one ordinary online build afterwards fills them; it fetches only missing texts (about 300–400 requests for WP 18–21, a few minutes at A3's DIP spacing), no sitting is re-acquired.
3. **A3's pacing applies.** The stage uses the same `ApiClient` and the same pause and stop-on-block rules A3 builds (handoff step 7, DIP `/person` measurement in a3-pilot Finding 2). B4 adds no own sleep constant; if B4 merges first it uses `NUMBER_LOOKUP_PAUSE`, and A3's merge replaces it in one place.
4. **Schema and export numbers.** B4 needs schema 8 and export format 9. A3's per-WP roster membership and Wahlperiode-dimensioned recipes need bumps too. Whichever branch merges second takes the next number on rebase; no migration code (pre-release, `--offline --repersist` rebuilds).
5. **Gate.** A3's `scripts/validate_store_gate.py` checks that a second unchanged replay keeps the DB byte-identical. The text cache is written sorted and deterministic, and the gate's replay must include it; B4's step 4 adds the new cache to the gate's input list if the gate has merged, or A3 adds it if B4 has.
6. **Pilot measure.** A3's Phase 1 pilot re-run (≈25 WP 18/19 sittings, `a3-pilot.md`) adds one row: the extraction states of its abstract-less votes, if B4 has merged; otherwise step 0 below samples WP 18/19 Anträge directly.
7. **Ordering recommendation.** Land B4-extractive before A3 Phase 3 (the full backfill, which needs the owner's go anyway), so the backfill's Vorgang fill is also the text fill and Phase 4's `compare_store_values` report shows the new coverage in one place.

These points are also recorded on the A3 TODO entry, since the A3 agent works in another checkout and cannot be messaged from here.

## Implementation order

### 0. Measure before fixing the rule (owner's machine: needs `DIP_API_KEY` and network)

On a copy of the reference store (never the canonical `.context/dip-pulse-site`):

- For every vote with `context_state` `resolved` and an empty abstract, list the candidate Drucksachen by the rule above; count votes with 0, 1, ≥2 candidates.
- Fetch their `/drucksache-text` (2 s spacing) into a scratch cache; record request count, bytes, any empty `text`.
- Sample 20 WP 18/19 Anträge (A3's 484 downloaded sittings name them) the same way.
- Run the hypothesis extractor; hand-check every result against the PDF for WP 21 and the 20 old ones: anchor found, end correct, demands whole, no header text inside, no dropped words.
- Write `docs/research/b4-antrag-extraction.md`: counts per state, size, the misses grouped by cause, and the final rule. Old and new number of panels with a description (today 153 of 217).

Gate to step 1: ≥90 % of Antrag-type candidates `extracted` with 0 wrong passages in the hand check. Otherwise stop and report.

### 1. `scripts/antrag_text.py`: pure, no I/O

`passage_targets(vote, report, vorgang_cache, text_cache) -> list[str]`, `select_documents(...)`, `extract_forderung(text) -> Forderung | None` (opening clause, demands, char span), `EXTRACTOR_VERSION`. Fixtures: trimmed DIP text of 21/2234 and of each miss class from step 0 under `tests/fixtures/antrag-text/`, provenance in `a1-source-manifest.json`. Tests in `tests/test_antrag_text.py`: anchor variants, header removal, hyphen joins that must not happen ("Bundes- und Landesrecht"), multiple sections, bundle exclusion via `vorgangsbezug`, BR document skipped, bounds.

### 2. Acquisition

- `dip.fetch_drucksache_texts(client, numbers)` in `validate_dip_protocol.py`, shape-checked like `vorgang_cache_record` (a `text` that is not a string raises `DipShapeError`).
- Stage 3 of `refresh_vorgang_cache`; skipped when the id or number stage found the API down. Saves every `CACHE_SAVE_EVERY`.
- `antrag_text.load_cache` / `save_cache`, atomic, staged in `registry.private_dir` like `politikfelder.save_cache`, sorted keys, gzip with `mtime=0` and empty `filename` as the export CSVs do (`build_dip_pulse_site.py` around line 2978), so an unchanged cache is byte-identical and A3's gate replay stays stable (R2).
- Input bound: `MAX_TEXT_CHARS` (like `dip_text.MAX_ABSTRACT_CHARS`), checked before any regex runs; a longer text is cached but extracts as `no_passage` (R3).
- Tests in `test_build_dip_pulse_site.py` with a fake client: only misses are fetched, a failure leaves the entry absent (retryable), an empty `text` is cached as fetched-empty (not retried every build, re-asked when `aktualisiert` changes, as abstracts are).

### 3. Persistence and replay

- Schema 8: `documents.forderung TEXT`, `documents.forderung_state TEXT CHECK (…)`, `vote_passages`, `votes.passage_state`; `require_current_schema` refuses schema 7.
- Persist writes them from the same derivation the renderer uses (one function in `antrag_text`, as `report_vote_vorgaenge` is shared today).
- Replay guard: extend `require_vorgang_cache_for_tags` (or a sibling) so a vote whose `passage_state` was `extracted` or `no_passage` cannot become `not_fetched` because the text cache is missing. `extracted` → `not_applicable` is allowed: it is DIP adding an abstract later (R6).
- `EXTRACTOR_VERSION` in the persisted inputs; facts/export/render refuse a stale one.
- Tests in `test_persist_dip_pulse_store.py`, `test_repersist.py`: round trip, second replay byte-identical, missing cache refused.

### 4. Render and export

- `features/votes.render_vote_context` takes the passage per Vorgang; `VotePanelContext` gains the text cache next to `vorgang_cache`, and `render_dip_pulse_html` loads it once per build where it loads the Vorgang cache today (render reads caches, not the store, see the open B3 finding 3 that one fix should cover for both); new copy constants next to `CONTEXT_*`. Escaping through `html.esc`; the list as `<ol>` only when the source numbers it.
- Export format 9: `documents.forderung`, `forderung_state`, `vote_passages`, `votes.passage_state`; field captions in `build_dip_pulse_site.py` (the export table descriptions at line 150ff.) and `docs/data-license.md` (Drucksache text is amtliches Werk; quote with source).
- Tests in `test_features_votes.py` (quote, fold, attribution on inverted vote 906, abstract still wins, each state's copy), `test_daten_export.py`.

### 5. Prove it on the reference copy

Full suite (`/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`), CI's zero-network demo, the browser checks from CONTRIBUTING.md. On the store copy: per-vote before/after of the context block; report "panels with a description" old 153 → new N of 217, and unchanged interpretation fields, tallies, tags, abstracts. Chrome light/dark, desktop/mobile on 906, 996, 1005, one abstract vote, one `no_passage`, one `not_fetched`.

## Effort and risk

Effort M. The extractor is the risk: a verbatim quote that silently drops a word or pulls a page header into the middle of a demand is a factual error presented as a citation. Step 0's hand check and the `no_passage` default are the controls. Second risk: DIP `drucksache-text` quality for WP 18 (older PDFs, two-column layouts); step 0 decides D3.

## Decisions for review

- **D1** Fallback only, or the quote also beside an existing abstract? Recommendation: fallback only; an abstract is DIP's neutral description, the quote is the sponsor's demand, and showing both doubles the block for 153 votes.
- **D2** Gesetzentwürfe without abstract (1 of 50): out of scope now, a TODO for the "A. Problem und Ziel / B. Lösung" block.
- **D3** DIP text vs PDF + `pdftotext`: DIP text, unless step 0 shows it unusable.
- **D4** Raw text cache as a separate gzip in `data/` (offline re-extraction) vs storing only the passage (smaller, needs refetch on rule change). Recommendation: separate cache; it also needs the hosting exclusion already open in TODOS ("Politikfelder: findings deferred from the B3 review", item 4).
- **D5** Second anchors ("lehnt ab", "begrüßt") only if step 0 counts them in ≥5 votes.
- **D6** Merge order with A3: B4-extractive before A3 Phase 3 (recommended), else one online build after it.

## Engineering review (2026-10-28)

The gstack `/plan-eng-review` skill is not installed in the cloud session that wrote this plan, so the review was done by hand against `main` (`71ade83`): the Vorgang fetch (`build_dip_pulse_site.refresh_vorgang_cache`, `politikfelder.fetch_targets`), the context derivation (`politikfelder.vote_vorgang_ids`), the renderer (`features/votes.render_vote_context`), the schema and the replay guard. Rerun `/gstack-plan-eng-review` on the owner's machine before implementing. Findings, already applied above:

- **R1 (P1, cost).** The first draft fetched `/drucksache-text` for every number of unknown type. A vote's numbers include Beschlussempfehlungen and Gesetzentwürfe, so that would download large texts that are never used. Now: batched `/drucksache` metadata first, text only for Antrag-type documents of a context Vorgang.
- **R2 (P1, A3 gate).** Python's gzip writes the current time into the header, so a re-saved, unchanged cache would differ byte for byte and fail A3's unchanged-replay check. Now: `mtime=0`, empty filename, as the export already does.
- **R3 (P2, robustness).** No input bound was set; `dip_text` bounds abstracts at 10,000 characters because its parsers go quadratic on bad input. Now: `MAX_TEXT_CHARS` before extraction.
- **R4 (P2, attribution).** The block head carries one source for all blocks ("Quelle: … DIP"). A block that quotes a Drucksache needs its own source line, or a mixed panel misattributes one of them.
- **R5 (P3, copy).** The teaser rule could not be met when the first demand exceeds 300 characters; now it shows that whole demand.
- **R6 (P2, replay).** The guard must not refuse the legitimate `extracted` → `not_applicable` move when DIP later writes an abstract.

Checked and fine as planned: no report field is needed (`document_numbers` and `linked_drucksachen` with `drucksachetyp`, `urheber`, `url` are already in every cached report, `validate_dip_protocol.compact_drucksache_position`), so A3's reports need no re-acquisition; the persist/render shared-derivation pattern matches `report_vote_vorgaenge`; the facts engine reads none of the new fields; all inserted text goes through `html.esc`.

Open for step 0, not decidable from code: whether `drucksache-text` returns usable text for WP 18 (D3); how DIP lists a reprinted Drucksache ("Neudruck", same number) and which record to quote; whether `vorgangsbezug` is filled on every Antrag record (if not, the bundle exclusion falls back to the Vorgang's own `/drucksache?f.vorgang=` list).

## Implementation status (2026-10-28)

Steps 1–4 are implemented on `claude/charming-lovelace-4a229o`, taking the recommendation for D1–D6. The session had no network and no DIP key, so **step 0 did not run**: the extraction rule is the starting hypothesis above, tested only on synthetic texts written in the DIP layout (`tests/test_antrag_text.py`, marked as synthetic). Nothing has been measured on real Drucksachen, and no reference-store figure (153 of 217 panels with a description) has moved yet.

What exists:
- `scripts/antrag_text.py`: `extract_forderung`, `forderung_teaser`, `vote_passages` / `report_vote_passages` (shared by persist, render and the replay guard), `fetch_targets`, the cache (`data/dip-drucksache-text-cache.json.gz`, gzip `mtime=0`), `EXTRACTOR_VERSION = 2` (2 since the code review of 2026-10-28 tightened the end, item, layout-line and hyphen rules).
- `validate_dip_protocol.fetch_drucksache_metadata` (batches of 50 numbers on `/drucksache`, Bundestag records only, filtered client-side because `f.zuordnung` is unverified) and `fetch_drucksache_texts` (batches of 10 ids on `/drucksache-text`).
- `build_dip_pulse_site.refresh_drucksache_texts`, stage 3 of `refresh_vorgang_cache`, paced by `NUMBER_LOOKUP_PAUSE`; the replay guard refuses losing a known passage.
- Schema 8 (`documents.forderung`, `forderung_state`, `forderung_version`; `vote_passages`; `votes.passage_state`), export format 9, captions, column sources (derived). A stale `forderung_version` is refused with the speech-rule check.
- Panel: the quote with caption "Aus dem Antrag „…“ (Urheber, Drucksache N):", the Drucksache PDF link, first whole demands inline, the rest under "Ganzen Forderungsteil zeigen"; "Antragstext nicht abgerufen" for a cache miss. Checked in Chromium on a demo page, light at 1100 px and dark at 390 px, no horizontal overflow.

Deviation from R4: the block head keeps "Quelle: Deutscher Bundestag/Bundesrat – DIP", which stays true (the text comes through DIP), and each quote adds its Drucksache in its caption; that keeps the abstract blocks unchanged.

Known limit: a Drucksache DIP returns with an empty text is cached as read and not asked again; step 0 counts how often that happens.

Unverified API assumptions, for step 0: a repeated `f.dokumentnummer` on `/drucksache` returns a union whose records each carry their `dokumentnummer`; `/drucksache-text` accepts a repeated `f.id`; records carry `vorgangsbezug` and `urheber[].titel`.

Next, on the owner's machine: run step 0 (measure, hand-check against the PDFs, replace the synthetic fixtures with trimmed real texts, adjust the rule and bump `EXTRACTOR_VERSION` if it changes), then step 5 on a reference-store copy, then `/gstack-plan-eng-review` or `/gstack-review` before shipping.

## Step 0, first real-text run (2026-10-28)

Partial: PDFs only, no DIP text and no reference store. [Research note](../research/b4-antrag-extraction.md). On 7 real Anträge and 44 other Drucksachen: no false positives; the reading-order text layer scrambled 3 of 7 lists, which the extractor wrongly accepted for 2 of them before this run and now refuses; the layout rendering quoted 6 of 7 correctly. `EXTRACTOR_VERSION` 3. D3 (DIP text vs PDF) now depends on what DIP's text body looks like, which still needs a DIP key.
