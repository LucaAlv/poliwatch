# Fix protocol citation labels

Status: implemented 2026-10-22; validation recorded below.
Branch: `fix/protocol-citation-labels`.
Source TODO: [Cite protocols as „BT-PlPr." per DIP no. 4c](../../TODOS.md#cite-protocols-as-bt-plpr-per-dip-no-4c).

## Required behavior

Public citations identify the issuing chamber, document type and number. Bundestag protocol citations read `BT-PlPr. 21/84`, retaining any TOP, page or speech context and the existing link.

[DIP terms §4c](https://dip.bundestag.de/documents/nutzungsbedingungen_dip.pdf), checked 2026-10-22, allow the full names or the abbreviations `BT-PlPr.`, `BR-PlPr.`, `BT-Drs.` and `BR-Drs.`, each with the document number. The clause also allows information already apparent from the presentation. Keep the existing general DIP attribution.

## Findings and scope

Five strings in `scripts/build_dip_pulse_site.py` currently use `BT-PlPr` without its period:

| Function | Output |
| --- | --- |
| `build_dossiers_with_progress` | Download/refresh progress messages |
| `collect_bill_pages` | Bill debate-event source, consumed by `render_bill_detail` |
| `render_abgeordnete_detail` | MP speech-history source links |
| `render_overview` | Dossier overview labels |
| `build_catalog_rows` | Protocol catalog labels |

The existing licence documentation and ADR 0003 already show `BT-PlPr.` correctly.

The related citation audit must cover these additional presentation paths:

- Bill document-event sources currently contain only `dokumentnummer`. Document lists distinguish Bundesrat papers using `_is_bundesrat_document`; preserve that distinction when qualifying event citations. Check protocol-type documents too: the bill fixtures include `PlPr 21/1`.
- `_render_fact_sources` currently emits `Drucksache <number>` and `Plenarprotokoll <number>`. Check the available chamber metadata and qualify ambiguous citations.
- `render_source_links` in `scripts/render_dip_pulse_html.py` and `render_document_links` in `scripts/features/votes.py` show document-number pills. Check their enclosing labels before changing them; a bare number in an already unambiguous context need not be rewritten.
- Check bill plenary references (`Sitzung <number>`), other rendered protocol links, and data-recipe presentation for the same contextual exception. Record the audit result for each path when implementing.

Raw source metadata, document numbers, stable identifiers, URLs, anchors, search keys, stored receipts and export schemas must retain their current values. Apply qualification at the presentation boundary. No database migration, API fetch or re-persist is needed for the five confirmed fixes. Do not mass-replace upstream fixture text or historical design documents.

## Implementation steps

1. Correct the five confirmed strings directly, including the matching progress-message expectations in `tests/test_build_dip_pulse_site.py`.
2. Complete the bounded citation audit above. Fix ambiguous citations using the exact abbreviation or permitted full name and the existing issuer/type information. Reuse `_is_bundesrat_document` where applicable; inspect existing issuer helpers before adding any formatting logic. Never infer Bundestag solely from a missing issuer, or turn a protocol reference into a Drucksache citation. If a path lacks enough issuer/type information, trace its existing producer before deciding the smallest correction.
3. Extend existing fixture-based tests for the changed outputs. Cover the generated bill event and its rendered link, MP speech history, overview/catalog labels, and any corrected Drucksache citations. Include Bundestag and Bundesrat papers and a protocol-type bill document if the audit changes document-event formatting. Preserve existing escaping, unsafe-link fallback, missing-number behavior, URLs and anchors. Do not create a new test framework.
4. Rebuild the zero-network demo and inspect generated citation text. After validation, mark the TODO complete using the repository's convention and record the citation-audit outcome.

## Validation

Run from the repository root after implementation:

```sh
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests
/opt/miniconda3/bin/python3.13 -m py_compile scripts/*.py
node tests/run_bills_browser_check.mjs /opt/miniconda3/bin/python3.13
/opt/miniconda3/bin/python3.13 scripts/build_demo_site.py --output-dir /tmp/poliwatch-citation-demo
/opt/miniconda3/bin/python3.13 scripts/build_dip_pulse_site.py --validate-publication /tmp/poliwatch-citation-demo
```

Inspect the demo for malformed `BT-PlPr` labels and verify representative source links still target the same document/TOP/speech. Retain existing negative assertions that prohibit protocol labels in intentionally simplified UI; do not blindly change every test containing `BT-PlPr`.

Done when all five confirmed strings have the period, each audited public citation is qualified or has a documented unambiguous context, issuer distinctions remain correct, and the checks pass.

## Risks and exclusions

The main risk is mislabelling Bundesrat papers or protocol-type bill documents while qualifying bare-number citations. A blanket `BT-Drs.` prefix would introduce that error. Longer labels may also affect compact document pills, so verify affected browser fixtures if those labels change.

No redesign, generalized citation system, legal-policy rewrite, data backfill, deployment or new dependency is part of this task. No upstream fixture text or historical design documents were rewritten.


## Implementation and citation audit (2026-10-22)

| Presentation path | Outcome |
| --- | --- |
| Five confirmed `BT-PlPr` strings | All now use `BT-PlPr.`; progress, bill debate event, MP history, overview and catalog have regression coverage. |
| Bill document events | Qualify as `BT-Drs.`, `BR-Drs.`, `BT-PlPr.` or `BR-PlPr.` using issuer/type evidence. Strip the synthetic `PlPr ` prefix only from the displayed label. Unknown chambers explicitly say `Kammer nicht erfasst`; a missing issuer never defaults to BT. Missing event numbers retain the existing source fallback. |
| Bill document lists | Preserve the existing type/glossary context; explicit issuer metadata now overrides number/URL heuristics. Bundesrat protocols say `Bundesrat-Plenarprotokoll`, never `Bundesrat-Drucksache`. |
| Fact source lists | Protocol/speech/agenda/vote receipts originate from the BT-only protocol store and now say `BT-PlPr.`. Supporting documents resolve issuer/type through the receipt's exact document ID at render time, so a BT and BR paper with the same number keep distinct labels. Stored receipts are unchanged. |
| XML document pills | The enclosing `Drucksachen` heading supplies type. Keep contextual bare numbers; explicitly mark identifiable BR papers `BR-Drs.`. Unsafe URLs still produce unlinked, escaped text. |
| Vote document pills and archive | The surrounding `Drucksachen` label supplies type. Explicitly mark BR papers, preserving issuer metadata only for the selected source link. XML still selects the URL ahead of DIP; metadata for another document with the same number cannot label that selected link. BT/unknown pills retain bare numbers without assigning a chamber. |
| Bill plenary/speech references and MP contribution links | Replace ambiguous sitting numbers with `BT-PlPr.`; preserve dates, pages, TOP and contribution/speech anchors. These producers use BT dossier protocols. |
| Data recipes | r4 links the vote title using a hidden BT protocol number; no standalone protocol citation is displayed. r5's visible `erste_drucksache` is actually selected from `protocols.document_number`, so display `BT-PlPr.` while leaving SQL, manifest fields and values unchanged. |
| Other protocol navigation | Simplified sitting chips, headings and latest-sitting numbers remain within explicit Bundestag sitting/protocol context. Preserve their intentional lack of formal citation labels and the existing negative assertions. Catalog source buttons (`XML`/`PDF`) sit beside the corrected full citation. |

Issuer evidence is deliberately conservative: explicit `herausgeber` (`BT`/`BR`) wins, followed by the known dserver `/btd/`, `/btp/`, `/brd/` paths and DIP's `(B)` marker. Arbitrary URL substrings and document-number shape alone do not identify the chamber. The persistence helper was not reused because its missing-issuer fallback is BT. No identity or persistence behavior changed.

Regression cases include same-number BT/BR documents, explicit metadata overriding a conflicting path/suffix, protocol-type bill documents from both chambers, unknown issuers, selected XML versus DIP links, escaping, unsafe-link fallback, and unchanged source numbers/URLs/anchors.

Validation passed: full unittest suite (1,371 tests run, one existing optional reference-store skip; 1,370 passed), focused checks for the final contribution/MP labels and archive path, Python compilation, desktop/mobile browser fixtures (including BR document pills), zero-network demo rebuild and publication validation. The demo contains only overview/catalog protocol citations and empty bill/MP indexes; its labels have the period. Bill, MP and mixed-chamber source links are verified by fixtures rather than claimed as present in that demo.
