# B4 follow-up: deterministic vote lead and Bundestag report link

Planning only, 2026-10-25. Scope: follow-up 2 of the B4 work in [TODOS.md](../../TODOS.md#abstimmungen-for-the-daily-view-what-was-decided-by-topic-with-dissenters).

## Starting point

Base implementation on `7b62d98` (`origin/main`, v0.22.0.0, #109), which fixes step 1. The checkout inspected during planning is still at `429556b`; do not implement on that older interpretation path. No branch or checkout was changed during planning.

Step 1 supplies protocol recommendation evidence, shared online/replay interpretation, and the `result_raw`, `result_source`, `result_scope`, `inverted` and provenance fields. Its `tests/test_vote_interpretation.py` covers 906, 996 and 1005, duplicate vote copies, and replay through SQLite, CSV, dossier and archive. In particular, 996 has an official **Antrag** rejection (`result_scope="application"`) despite a final tally of 439 Ja / 135 Nein: those Ja votes supported the rejecting recommendation. Preserve this contract.

Existing pieces to reuse:

- `derive.vote_outcome`: the interpreted outcome, without re-inverting application-scoped results.
- `derive.report_drucksachen` / `derive.vote_committees`: sitting-wide, Bundestag-only document lookup and committee citations.
- `features/votes.py`: shared panel renderer, source URL validation, result badge, inversion legend and DIP context blocks.
- `dip_text.committee_genitive`, `html.format_date` and `html.format_int`: existing German display helpers.
- `fetch_roll_call_vote_detail`: already downloads the vote page from which the report link can be extracted.

The research note records the deterministic article join through `showItContainer_<articleId>_<videoId>` and shared articles: [Bundestag vote pages](../research/bundestag-vote-pages.md). A planning spot-check of [vote 1005](https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=1005) confirms that its Debatte content covers several motions and headings alone do not identify the voted motion. This plan links the whole associated report; it does not select or reproduce editorial sections.

## Product behavior

Every vote panel gets a short deterministic lead before the existing DIP description, including panels with an abstract. It answers what was voted on, when, and with what outcome and raw tally. Place the existing committee citation immediately after it, so the lead and citation form one factual introduction without repeating the committee elsewhere. Keep the title, tally chart, badge, inversion legend, source documents and DIP missing-data states.

Use a lead sentence with a second short sentence only where needed to distinguish recommendation and Antrag. Prefer readable wording over forcing all facts into one long sentence. Illustrative copy for 906, with its final raw counts:

> Am 14.03.2024 stimmte der Bundestag über die Beschlussempfehlung zum Antrag auf Lieferung von Taurus-Marschflugkörpern ab (494 Ja-Stimmen, 188 Nein-Stimmen, 5 Enthaltungen). Der Antrag wurde abgelehnt (aus den Stimmenzahlen berechnet).

The topic phrase in this example is illustrative; implementation must use attributable stored wording, not generate this paraphrase. The committee follows using the existing “Beschlussempfehlung des … (Drucksache …)” citation. That wording identifies a document's authorship without claiming the committee is responsible for every related motion.

Show the optional source link as **Bericht und Debatte beim Bundestag**, even when a DIP abstract exists. A missing/ambiguous article supplies no report link; the existing official vote-page link stays available. The report is supplementary context, never evidence used to alter the result.

## Implementation order

### 1. Build the lead from existing facts

Add one small pure derivation helper in `scripts/derive.py` for the vote subject used by the lead. Reuse the object classification in step 1 (`_abstimmungsgegenstand`) by moving that existing rule into `derive` and updating its callers, rather than importing the acquisition module into the renderer or maintaining two competing classifiers. Keep its existing three answers (Beschlussempfehlung, Vorlage, unknown) and description → heading → title precedence unchanged. Step 1's conservative protocol attribution remains unchanged too. Use specific direct-object wording (Gesetzentwurf, Antrag, Änderungsantrag, Entschließungsantrag) only when the matching stored document metadata establishes it; otherwise retain the generic Vorlage/formal label. Do not broaden inversion inference to improve the prose.

Use the vote's own description, heading and document numbers, with sitting-wide metadata for those exact documents. Never choose the TOP's first Vorgang or a neighboring motion's title. A unique matching document can supply its title and type. Where several documents/parts could be the object, retain the formal description or use the existing vote title as a quoted label (“zur Abstimmung …”), without asserting a document identity the data does not establish. Preserve Buchstabe/Artikel qualifiers; do not shorten away the scope of a split vote. No new topic paraphraser or general German grammar engine.

Render the lead in `scripts/features/votes.py`, escaping all source text at the HTML boundary. Reuse existing date/count formatting and badge source wording. Apply these rules:

| Evidence | Wording rule |
| --- | --- |
| Direct Vorlage, known outcome | Describe that Vorlage and its recorded outcome. Acceptance of a Gesetzentwurf is not a claim that a law has entered into force. |
| Confirmed rejecting recommendation | Explicitly name the recommendation to reject; name the Antrag outcome using `derive.vote_outcome`. |
| Other recommendation, proposition-scoped result | Report the recommendation's result; do not invent the underlying Antrag's disposition from `inverted=None`. |
| Application-scoped official result | Name the Antrag outcome as recorded; do not invert it again or label it the recommendation's raw result. |
| Derived result | Keep “aus den Stimmenzahlen berechnet” visible in the prose, not just a tooltip or badge. |
| Unknown outcome / special majority without official result | Say the outcome is unavailable, with the existing procedure-specific explanation; a numeric Ja majority must not become a claim of acceptance. |
| Unknown subject, date or incomplete tally | Fall back to the recorded label, omit an unavailable date, and identify missing counts; absence is not a zero. |

Always label counts **Ja**, **Nein** and **Enthaltungen** for the actual ballot. Never call them votes for/against the Antrag when inverted. Zero abstentions are a valid count. “Nicht abgegeben” remains in the existing tally display and is not included in votes cast. Do not infer results anew in the sentence formatter. Keep the existing inversion legend.

Do not store the generated prose. Its inputs already survive report JSON, SQLite and export; wording can be regenerated without a data migration.

### 2. Extract only the associated report link

Add a bounded parser beside the existing roll-call HTML parsers in `scripts/validate_dip_protocol.py`, called from `fetch_roll_call_vote_detail`. Scope it to this vote page's Debatte panel and its `showItContainer` association, ignoring unrelated page widgets, recommendations and other tabs. Collect unique associated article IDs; repeated copies of one ID are fine, conflicting IDs mean no match.

Store one nullable `debate_url` on the enriched vote. Prefer an explicit Textarchiv URL whose article ID matches the panel. If the page exposes only IDs, verify the Bundestag's ID-based URL resolution before using it; do not invent a slug. The supported fallback is the vote page's actual Debatte tab target, extracted from its markup and verified to activate that tab. Do not assume `#debatte` is a working fragment. If neither target can be established, leave the value absent.

This bounded URL check is the first acquisition fixture task: retain only the relevant association markup and source retrieval metadata for a normal page, a shared-article page such as 1005, and a missing-article page. The web reader used during planning did not establish an ID-only canonical URL or preserve the tab fragment; those forms remain to be verified before implementation chooses one.

Resolve relative links against the official page and apply the existing HTTPS/host validation plus the expected Textarchiv path/article ID or exact vote-tab target. Validate again when rendering and fail to no report link for malformed or unsafe values. Reuse `bundestag-roll-call` source provenance; no new host permission or dependency.

No additional article request is needed in the normal build once a verified URL construction exists. Do not retain, copy, summarize or section-match the editorial body. Shared report URLs across votes are valid.

### 3. Preserve the link through reports, storage and release

Add `votes.debate_url` to the schema and `persist_vote` insert/upsert. Use the repository's rebuild convention: bump store schema 6 → 7 and `EXPORT_FORMAT` 7 → 8, provided those are still current on the implementation base. Extend `require_current_schema` to reject a store missing the new column with the existing `--offline --repersist` recovery instruction. No in-place database rewrite or stable-ID change.

The existing exporter should carry the new column automatically; verify this and add its meaning/source to the Daten caption and data documentation. It is a scraped source URL (`bundestag.de`), not generated prose. Update hard-coded schema/format expectations in current tests, demo/export fixtures and user documentation where applicable; do not rewrite historical plans.

Save the link on the report before serialization. Verify all copies of a vote, including sitting-only votes and duplicates after JSON reload, preserve the same link into panels and persistence. An absent key in a legacy/sparse duplicate must not erase a populated value; a fresh parser writes an explicit nullable value and updates that vote's copies consistently. Conflicting links for the same vote must produce no report link rather than be resolved by incidental iteration order. Use key presence and the existing report preparation path, without adding another acquisition flag.

Old reports with no field remain readable and produce the lead immediately. An offline repersist can add the nullable column but cannot discover an article URL from XML or a DIP abstract. Use the existing targeted online vote refresh for link recovery. A completed fresh detail fetch with no unambiguous article must clear an old link; do not apply the XLSX-specific carry-forward rule to override a fresh refusal. A failed fetch follows the existing cached-report retention behavior. No new acquisition state/flag or refresh CLI.

Files reached: `scripts/validate_dip_protocol.py`, `scripts/derive.py`, `scripts/features/votes.py`, `scripts/persist_dip_pulse_store.py`, export captions/version in `scripts/build_dip_pulse_site.py`, and narrowly scoped rendering styles in `scripts/render_dip_pulse_html.py` if needed. Documentation: `docs/project-documentation.md`, `docs/data-license.md` if field provenance needs clarification, schema references and the two relevant B4 TODO bullets after completion. The archive keeps its compact rows and existing panel anchors; no second prose implementation.

### 4. Prove the full path and inspect the panel

Extend existing tests; reuse step 1's fixtures and integration flow rather than building another test harness.

- `test_derive.py` / `test_b1_interpretation.py`: shared subject classification still blocks direct-Vorlage inversion; exact document attribution, bundled/partial votes and ambiguous titles stay conservative.
- `test_features_votes.py`: ordinary acceptance/rejection; rejecting recommendation with both raw result scopes; derived/unknown/special-majority outcomes; 0 versus missing counts; missing date/committee; escaped text. Assert that 906/996/1005 prose, badges and raw tally labels agree. Preserve abstracts and their three missing-data states, committee citations, inversion notes and single panel anchors.
- `test_roll_call_scraping.py`: unique/repeated/conflicting/missing article associations, unrelated widgets, shared article, relative URL handling and unsafe destinations. Fixture-backed full detail fetch must set the optional link without changing interpretation fields or counts.
- `test_vote_interpretation.py` (or the existing closest replay integration): serialized report → reload → repersist → downloadable SQLite/CSV → dossier. Verify the URL and all sentence inputs agree, a second replay is stable, old reports work, sparse duplicates do not lose links, and fresh absence clears a formerly saved link.
- `test_b1_store.py` / `test_daten_export.py`: nullable URL round trip, schema refusal/rebuild, export version and source caption. Use the integration test for cross-layer parity instead of repeating it in every unit file.

After implementation run the complete standard unittest suite with `/opt/miniconda3/bin/python3.13 -m unittest discover -s tests`, script compilation, and CI's zero-network demo/publication validation. Run the existing browser regression command as required by CONTRIBUTING.md.

On a disposable reference-site copy, compare by vote ID before/after: interpretation fields and final totals unchanged, lead coverage, link coverage, and missing/ambiguous links reported separately. The historical 215/217 article count is a reference, not a required current success rate. Spot-check 906, 996, 1005, a direct Gesetzentwurf vote, a no-abstract panel, an unknown outcome, a missing committee and a missing article. Use Chrome DevTools MCP for desktop/mobile panel inspection and actual link/tab activation; another driver only if unavailable, stating why. Confirm no render-time network calls.

## Completion and exclusions

Done when each panel supplies an accurate factual introduction, retains honest source/missing-data labels, cites the existing committee evidence, and offers a verified associated Bundestag report target where available. The link and sentence inputs must survive cache replay and release export without changing the corrected vote interpretation.

The extractive Antrag fallback, AI sentence/validators, mitberatende Ausschüsse, extra vote metadata, store-backed site migration and archive redesign remain separate work. No new dependency, model call, generic prose framework or article-content cache.

Planning validation: inspected the local rendering/storage/export paths and step 1's committed implementation/tests via `git show origin/main:…`; 64 existing `test_features_votes.py` tests passed on the local checkout. No feature implementation, full-suite run, reference-store repair or browser validation was performed. The direct article URL/tab behavior is explicitly left for the bounded source-verification task above.
