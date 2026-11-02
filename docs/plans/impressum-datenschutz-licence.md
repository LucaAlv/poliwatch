# Impressum, Datenschutz and licence files

Status: implemented 2026-11-01 on this branch (steps 1–9; deviations under "Implementation notes" at the end). The owner inputs below are still missing.
Branch: `claude/pre-public-items-plan-e8d01d` (cut from main 4705fb3, v0.27.0.0).
Backlog: `TODOS.md`, roadmap D, "Impressum, Datenschutz and licence files before the site goes public". This is the first open D item. The other open D items wait on the owner: the roll-call e-mail, a Zenodo account, and the hosting decision.
Decisions it implements: [ADR 0003](../adr/0003-licences-and-impressum.md) D1, D3, D4. D5 (governance) stays in the Community item, apart from the e-mail address both items share.

## Owner decisions

**Decided 2026-11-01: the owner chose option A for O1, O2, O3 and O4.** The steps below implement those choices. The (B) options are kept for the record.

**O1. Where the operator's name, address, e-mail and hosting details live.**
- **(A, recommended) A local JSON file outside git**, passed as `--operator-file` (or `$BUNDESTAG_PULSE_OPERATOR_FILE`), in the style of `--data-license`. The repository will go public, and an address committed to git history cannot be taken back. That matters if the lawyer says a c/o address is enough, or if the address changes. A scheduled build later reads the file from a repository secret.
- (B) A committed `site/operator.json`. Simpler, but the address becomes permanent public history.
- **Either way, a build without the values never passes silently.** Each missing field renders as `<span data-operator-missing="<field>">Angabe folgt.</span>` (eng review D2 A). The TODO's done check becomes "no generated page carries `data-operator-missing`". A test pins this.

**O2. The `--publish` gate this change opens.**
- `scripts/publish_dip_pulse_data.py` refuses `--publish` for two reasons only: the export carries no licence string, and `LICENSE-DATA.md` is missing at the repository root. This change removes both.
- TODOS "Release pipeline: deferred /ship review findings" deferred items 10a–d (P1) and 6 *because* that gate was closed. Once it opens, real input can reach them, so under CLAUDE.md they become correctness defects to fix now.
- **(A, recommended)** Fix 10a–d in step 1 of this branch. Step 3 fixes item 6 as a side effect.
- (B) Keep `--publish` shut with an explicit refusal that names the TODO, and fix the items later.

**O3. One source for the data-licence text.** Recommended (A):
- Move the researcher-facing part of `docs/data-license.md` (everything from "## Short string" on) into a root `LICENSE-DATA.md`.
- Move the maintainer notes above it into `docs/project-documentation.md`, and delete `docs/data-license.md`. Pre-release rule: no pointer file left behind.
- Every export generation then carries `LICENSE-DATA.md` as a file. Today only a release does, so the short string's "Details in LICENSE-DATA.md" is false for every local download.

**O4. Branch order.**
- The unmerged `fix/todo-batch-8-governance` (tip 175a79a) changes the Daten footer label and `tests/test_daten_page.py`.
- `fix/todo-batch-7-puls-outward` adds `BUNDESTAG_PULSE_SITE_URL`.
- Recommended: land batches 7 and 8 first, then rebase this branch onto main before step 4. The footer steps conflict with batch 8 otherwise.

**Inputs only the owner can supply. They are not needed to build, only to finish:**
- the postal address, after lawyer question 1;
- the dedicated Impressum e-mail, which D5 says must not be a personal address;
- the host and its log retention, for the Datenschutz hosting paragraph (hosting deferred);
- the supervisory authority, which is the Landesdatenschutzbehörde of the operator's Land.

## Implementation

### 1. Close the release-pipeline P1 findings (O2 A)

In `scripts/publish_dip_pulse_data.py` and `build_dip_pulse_site.py`'s CLI. Each fix gets a test in `tests/test_publish_dip_pulse_data.py` / `tests/test_data_pipeline_cli.py`:
- **10a.** If `--previous-manifest` is given, it must be a JSON object; `null`, a list or a number is refused. Also run the data-manifest check `build_dip_pulse_site.validate_manifest` (L12815) on it. Not `publication_state.validate_manifest`, which checks the site manifest (eng review S5).
- **10b.** `.resolve()` `--output-dir` and `--exports-dir` before anything reaches gh (gh runs with `cwd=repo_root`). Refuse a path containing `#`, which gh reads as its label separator.
- **10c.** `parser.error` on `--data-tag` combined with `--no-persist` or `--data-manifest`. The release script requires the export's `tag` to equal the requested version, so a missing store or `DataExportUnavailable` can no longer leave an older tagged export behind with exit 0.
- **10d.** Normalise CRLF on one side: the exporter's authored-input hash and `blob_sha256` hash the same bytes under `core.autocrlf=true`. A test sets `core.autocrlf=true` in a temp repository.

### 2. `LICENSE` (MIT)

- A root `LICENSE` with the standard MIT text, "Copyright (c) 2026 Luca Veh".
- A closing paragraph says MIT covers the code only, and that generated data and exports are under `LICENSE-DATA.md` (ADR 0003 D3).
- `CITATION.cff` already says `license: MIT`. Check that its message still reads true.

### 3. `LICENSE-DATA.md`, one source (O3 A)

- **The file.** Create the root `LICENSE-DATA.md` from `docs/data-license.md`.
  - The preamble above the first `##` stays researcher-facing: what the file is and where it applies.
  - `_license_notice` keeps embedding from the first `## ` heading.
- **The codebook input.** `CODEBOOK_INPUT_FILES["license"] = "LICENSE-DATA.md"`.
  - The release script already refuses an export whose authored inputs differ from the manifest commit, so the file is now verified against that commit.
- **The export.** The export writes `LICENSE-DATA.md` into each generation directory, listed in the manifest `files` with its `sha256`. Bump `EXPORT_FORMAT` to 12.
  - The listing needs a new file kind `license` (eng review S4):
    - `_manifest_inventory_problems` (L12873) accepts exactly one `license` file, named `LICENSE-DATA.md`;
    - `_REUSE_HASHED_KINDS` (L3483) gains `license`, so a reused export re-hashes it;
    - the Daten page file list shows it.
- **The release script.**
  - `--publish` checks that the verified manifest lists a non-empty `LICENSE-DATA.md`, instead of checking the repository root.
  - It drops its own working-tree copy (`shutil.copyfile`, line 166).
  - This fixes deferred item 6: the copy came from the working tree, and an empty file passed.
- **The layer strings.** Retarget the 6 of the 10 strings in `scripts/data_dictionary.json` that cite "docs/data-license.md" (the four `eigene-*` strings cite nothing; eng review S2) to "LICENSE-DATA.md". They reach researchers through DATA.md, and the old path does not resolve inside a download.
- **References.** Grep and update every `docs/data-license.md` reference: README, docs, ADR 0003 follow-ups, code comments, tests, and the `ATTRIBUTION_NAME` comment.
- **The status note.** Drop the note "The release copy as `LICENSE-DATA.md` is not built yet".

### 4. Default licence string

- With neither `--data-license` nor the env var set, `resolve_data_export_options` returns the short string.
- It reads that string from the blockquote under "## Short string" in `LICENSE-DATA.md`, so the text is never written twice. Refuse with a clear error if the section is missing.
- Update `test_defaults_when_neither_cli_nor_env_set`.
- The changed default changes `inputs_hash`, so the next build re-exports once. **No figures move.**
- The Daten download panel:
  - shows the string;
  - links "LICENSE-DATA.md" through `generation_file_href`;
  - keeps the `sources.html#lizenz` link.
- The fallback "Lizenzhinweis: siehe Quellen und Methode" stays for a manifest that carries no licence, for example an older remote manifest read through `--data-manifest`. An explicitly empty `--data-license ""` cannot reach it, because the `or` chain in `resolve_data_export_options` (L13324) falls through to the default (eng review A2).

### 5. Shared legal links in every footer

- **The helper.** Add `render_legal_links(*, depth: int = 0) -> str` beside `render_global_header` in `scripts/render_dip_pulse_html.py`.
  - It uses the same `"../" * depth` prefix.
  - It returns `<span class="legal-links"><a href="{p}impressum.html">Impressum</a> · <a href="{p}datenschutz.html">Datenschutz</a></span>`.
  - One `.legal-links` rule goes into `global_header_styles()`, which every full page already includes.
- **Append it to each existing footer.** Don't rewrite them. Root pages, depth 0:
  - `index.html`
  - `puls.html`
  - `overview.html`
  - `api-sitzungen.html`
  - `bundestag.html`
  - `sources.html`
  - `database.html`
  - `settings.html`
- **Pages one directory deep, depth 1:**
  - the dossier footer: append after `footer_nav_html`, keep the bare `<footer>` tag and the substrings `DossierLayoutTests` match;
  - `bills/index.html` and the bill detail pages;
  - `abgeordnete/index.html` and the detail pages;
  - `votes/index.html`;
  - `fakt/index.html`, the week pages and `methodik.html`.
- **Add a footer** to `render_database_unavailable_page`, the one full page that has none. The `puls.html` empty shell (`render_pulse_shell`) already has a footer (L6192) and only gets the links appended (eng review S3).
- **Excluded on purpose:**
  - the abgeordnete alias redirect pages, which are `meta refresh` only with no visible content;
  - `NAV_ITEMS`, which `tests/test_features.py` pins. Legal pages belong in the footer, not the navigation.

### 6. `impressum.html` and `datenschutz.html`

- **Renderers.** `render_impressum_page(operator)` and `render_datenschutz_page(operator, *, data_base_url)` in `build_dip_pulse_site.py`.
  - They follow the `render_bundestag_page` shape: `page_head()`, `render_global_header(depth=0)`, inline styles, the footer from step 5, `page_scripts()`.
  - `render_site` writes them next to `settings.html`.
  - Add both to the required files in `publication_state.validate_publication_directory`.
- **Operator input (O1 A).**
  - `--operator-file` / `$BUNDESTAG_PULSE_OPERATOR_FILE`, loaded by one function.
  - The file is a JSON object with string fields:
    - `name`
    - `street`
    - `postal_code`
    - `city`
    - `email`
    - `hosting` (an object: `provider`, `address`, `privacy_url`, `log_retention`)
    - `supervisory_authority` (an object: `name`, `url`)
  - Refuse invalid JSON, a non-UTF-8 file, a non-object, a non-string field, an over-long value or a control character with a clear error, never a traceback (checklist class 9; eng review A3). The e-mail must look like an address. The URLs go through the site's existing safe-href check.
  - With neither the flag nor the env var set, every operator field renders the `data-operator-missing` placeholder (D2 A), and so does a field missing from a present file. A path that is set but missing or unreadable stops the build with an error naming the path (D3 A).
  - Escape everything.
  - Not exported and not part of `inputs_hash`.
- **Impressum content** (German, ADR 0003 D4):
  - "Angaben gemäß § 5 DDG und § 18 Abs. 1 MStV": name, postal address, e-mail.
  - "Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV": the same person and address.
  - Contact routes per D5: public data errors and site bugs go to GitHub Issues, and only private matters go to the e-mail. While the repository is private, the Issues sentence names no link, matching batch 8's D5 amendment.
  - The DIP source line „Deutscher Bundestag/Bundesrat – DIP" and a link to `sources.html#lizenz`.
  - No boilerplate liability disclaimers.
- **Datenschutz content.** Every sentence must be true of the code (checklist class 11):
  - **Verantwortlicher:** the operator, as in the Impressum.
  - **Hosting and server logs:** from `operator.hosting`, otherwise the `data-operator-missing` placeholder.
  - **No cookies, no tracking, no third-party resources loaded.** Verified by a grep over `scripts/**` for `localStorage|sessionStorage|cookie|indexedDB|<script src|<link href|@import|fetch(` at implementation time. The 2026-11-01 survey found only same-origin resources.
  - **localStorage:** exactly the keys the code writes. Two today: `bundestag-pulse-theme` and `bundestag-pulse-ai-summaries-v1`. Both are written only on a click and never transmitted. Re-grep before writing. Don't state a TDDDG legal basis; add the § 25 TDDDG question to the lawyer list.
  - **Outbound links:** bundestag.de, dip.bundestag.de, abgeordnetenwatch.de, gesetze-im-internet.de. No request happens until a click.
  - **Download host:** only when `data_base_url` is absolute, name its host.
  - **Contact:** e-mail and GitHub Issues (GitHub's own privacy policy applies).
  - **Persons in the data:** MPs' names, votes, birth years and speeches come from public sources, with a purpose statement. The legal basis is lawyer question 4, so the page says no more than the ADR has decided.
  - **Rights:** Art. 15–21 and Art. 77 DSGVO, the authority from `operator.supervisory_authority`, otherwise the `data-operator-missing` placeholder.

### 7. `sources.html` licence item

- Replace the `licence_method_item` placeholder ("… steht noch aus.") with a four-row layer table:
  - DIP and Plenarprotokoll extraction: DIP terms, with the source line and "BT-PlPr." citations;
  - Abstimmungen: Deutscher Bundestag, with the protocol as the basis;
  - abgeordnetenwatch: CC0 1.0;
  - eigene Auswertungen: CC BY 4.0, attributed to "Bundestag-Puls, Luca Veh".
- Add the change marking ("aufbereitet und verändert"), the DIP no. 5 notice, and "Details: LICENSE-DATA.md in jedem Download" linking the Daten page.
- Write it as an authored constant. The 10 dictionary layers are too fine-grained for this page.

### 8. Machine-generated label

- The label already exists: both LLM renderers (`render_llm_summary`, `render_session_llm_summary`) print „KI-generiert · nicht redaktionell geprüft" and `data-ai-generated="true"`.
- Add a test in `tests/test_ai_summaries.py` that pins both.
- Amend ADR 0003's "not verified today" sentence.
- Fakten, vote leads and Politikfelder are rule output, not LLM output, and are out of scope.

### 9. Docs that become false

- README line 43 ("Lizenz-/Nutzungsformulierung steht ebenfalls noch aus"), plus a licence section that names `LICENSE` and `LICENSE-DATA.md`.
- PRODUCT.md line 65 ("Implementing them is still open").
- TODOS:
  - The DOI item's "There is no `LICENSE` file at the repository root yet".
  - Release item 10 and item 6, marked fixed.
  - The Impressum item: rewrite its done criterion to "no generated page carries `data-operator-missing`, and every footer links Impressum and Datenschutz" (D2 A). Mark it completed only once the owner inputs are in. Until then, record what is built and which inputs are missing.
  - The Community item keeps `security.txt` and the private-e-mail contact link, which wait on the domain.
- ADR 0003:
  - a short amendment for O1/O3;
  - the § 25 TDDDG lawyer question.
- Add `--operator-file` to `docs/project-documentation.md`, with an example file that holds placeholder values only.

## Tests

- **Done criterion as a test** (`tests/test_demo_site.py`): build the demo site, walk every `*.html` except alias redirects, and assert that each links `impressum.html` and `datenschutz.html` with the right depth prefix, and that both targets exist.
- **Placeholder (D2 A):** without an operator file, both pages carry one `data-operator-missing` element per missing field. With a complete fixture file, no generated page carries one, and `sources.html` no longer contains "steht noch aus".
- **Operator file input shape:** `null`, a list, a non-string field, an over-long value, a control character, a bad e-mail and a `javascript:` URL each give a clear refusal. Escaping is checked with `<script>` in `name`.
- **Licence:**
  - the default short string is read from `LICENSE-DATA.md`;
  - the export generation lists `LICENSE-DATA.md` with a matching `sha256`;
  - DATA.md no longer names `docs/data-license.md`;
  - `--publish` refuses a manifest without it, or with an empty file;
  - the release copy comes from the generation, not the working tree.
- **Publication validator:** refuses an output tree without `impressum.html` or `datenschutz.html`.
- **Operator file path set but missing (D3 A):** the build stops with an error naming the path. With no flag and no env var, the placeholders render.
- **Datenschutz drift guard (D4 A):** the localStorage keys in `page_scripts()` and the external hosts in the demo build match what `render_datenschutz_page` names.
- **Footer regression (D5 A):** the demo site is rendered with `render_legal_links` patched to "" and as is. With the span removed and `generated_at` normalised, every page is identical. The new footer on `render_database_unavailable_page` is checked separately.
- **Licence kind (S4):** a reused export re-hashes `LICENSE-DATA.md`, and the inventory validator refuses a generation with zero, two or a misnamed `license` file.
- **AI label pin** (step 8).
- **Existing tests to update:**
  - `test_defaults_when_neither_cli_nor_env_set`;
  - the `--publish` refusal tests at `tests/test_publish_dip_pulse_data.py:357-401`;
  - the DATA.md licence-line test in `tests/test_daten_export.py`.

## Validation and acceptance

```sh
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests
uv run --python 3.13.12 python -m unittest discover -s tests
/opt/miniconda3/bin/python3.13 scripts/build_demo_site.py   # then --validate-publication, as CI does
grep -rln "data-operator-missing" <demo output>             # only impressum.html and datenschutz.html, without an operator file
```

- **Browser check** (checklist "Inline JS and layout"): open `impressum.html`, `datenschutz.html`, one dossier footer and one `abgeordnete/` footer at 375px and in dark mode.
- **Export:** one offline build on the reference store re-exports exactly once (format 12, new `inputs_hash`). `compare_store_values.py` shows no moved figures; the store is untouched.
- **Acceptance:**
  - every non-redirect page links both legal pages;
  - with the owner's operator file, no generated page carries `data-operator-missing`;
  - every download carries `LICENSE-DATA.md`;
  - `--publish` cannot be reached with the item 10 defects.

## Out of scope

- `security.txt`, the issue-form contact link, and per-page "Fehler melden" links. These belong to the Community item and need the domain.
- Footer copy with dev wording ("--detail-limit", "Statischer Prototyp").
- The hosting choice itself.
- Item 10's sibling deferrals 1–5 and 7–9, which stay P2.

## Eng review, 2026-11-01

Target: this plan, `docs/plans/impressum-datenschutz-licence.md`, as written above (the owner chose option A on O1–O4). Evidence revision: `4705fb3` (origin/main tip, the branch base). This file is the report file. The review authorizes no implementation.

### Scope record

- Feature answers: no cuts proposed.
- Structure: A, Original arrangement (one PR for steps 1–9). D1 was auto-decided by the owner's adjudicator: step 1 has no value on its own while `--publish` is blocked, and keeping it together means the gate never opens with the defects still in.
- Accepted scope: steps 1–9 as planned.
- Pending remedies: S1.

### Scope Challenge findings

1. **S1** [P1] (confidence: 9/10). Location: `TODOS.md:777`, plan O1 and the Acceptance section. The done check `grep -rn "steht noch aus"` over the site can never come out empty, because source text contains the phrase.
   - Evidence: the 290-sitting reference site (`.context/dip-pulse-site`) has it on 7 dossiers and 2 bill pages, for example "Hier ist Anklage erhoben; ein Urteil steht noch aus."
   - Consequence: the placeholder the plan uses as its "operator data missing" signal is ambiguous. Needs a decision (D2 below).
2. **S2** [P3] (9/10), factual correction. `scripts/data_dictionary.json` has 10 licence layers, but only 6 of the strings cite `docs/data-license.md`. The four `eigene-*` strings do not (for example `eigene-auswertung`: "Eigene Auswertung CC BY 4.0 (Bundestag-Puls, Luca Veh); verwendete Quelldaten behalten ihre jeweiligen Bedingungen."). Step 3 is amended to retarget 6 strings.
3. **S3** [P3] (9/10), factual correction. `render_pulse_shell` already has a footer (`build_dip_pulse_site.py:6192`, a sentence with no links). Only `render_database_unavailable_page` (L5208) has none. Step 5 is amended.
4. **S4** [P2] (9/10). `build_dip_pulse_site.py:12873` accepts only the kinds `sqlite`, `table_csv`, `recipe_csv` and `codebook`, and `_REUSE_HASHED_KINDS = ("codebook", "recipe_csv")` (L3483). An uncategorised `LICENSE-DATA.md` in the generation fails validation ("kind unsupported"), and a reused export would not re-hash it.
   - This is necessary implementation of the approved O3 (owner answer "Yes, all four", 2026-11-01), so it is added to step 3 without a new question.
5. **S5** [P3] (9/10), factual correction. Two functions are named `validate_manifest`: `publication_state.py:277`, which checks the site manifest, and `build_dip_pulse_site.py:12815`, which checks the data manifest. Item 10a needs the data one. Step 1 is amended.

Reality rows:
- `REALITY: premise-table finding 3 of 18 premises false (S2, S3, S5), unverified=0 scripts/build_dip_pulse_site.py:6192`
- `REALITY: already-done pass origin/main 4705fb3 has no commit after 2026-10-31 touching LICENSE*, data-license.md or Impressum TODOS.md:764`
- `REALITY: surface-check pass --data-tag/--no-persist/--data-manifest/--validate-publication exist build_dip_pulse_site.py:13002`
- `REALITY: binding-decisions pass O1-O4 option A (owner 2026-11-01), ADR 0003 D1-D5 not reopened docs/adr/0003-licences-and-impressum.md:1`
- `REALITY: numbers pass 7 dossier + 2 bill pages with the phrase [measured: .context/dip-pulse-site grep]; 18 footer templates [measured: grep <footer] build_dip_pulse_site.py:5193`
- `REALITY: deferred-asks pass TODO bullets all mapped; security.txt deferred to Community item TODOS.md:764`
- `REALITY: pr-count pass one PR (D1 A), no .gstack/ship-policy.json docs/plans/impressum-datenschutz-licence.md:234`

## Decision ledger

### S1: what marks a missing operator value, and what the done check greps

Finding: S1, P1, confidence 9/10, `TODOS.md:777` and the plan's O1 and Acceptance sections. Reviewer: Claude (eng review).

Plan baseline: a missing operator field renders as "… steht noch aus.", and done means `grep -rn "steht noch aus"` over the generated site is empty. Original proposal, approved implicitly with O1 A.

Runtime evidence: source text contains the phrase on 7 dossiers and 2 bill pages of the 290-sitting reference site (measured by grep, 2026-11-01). No marker exists today.

Comparison grid:

| Choice | Current | A | B |
|---|---|---|---|
| S1 placeholder signal | the text "steht noch aus" | an element carrying `data-operator-missing="<field>"`, plus the visible German text "Angabe folgt." | the text "steht noch aus", with the grep limited to impressum.html, datenschutz.html and sources.html |
| Done criterion (TODOS.md:777) | a site-wide grep is empty | no generated page carries `data-operator-missing`; a test builds with a complete fixture and asserts that | a grep over the three files is empty |
| Refusing a build without operator data | not planned | unchanged (not planned; a deploy gate is a TODO candidate) | unchanged (not planned) |
| O1–O4, steps 1–9 | approved | unchanged | unchanged |

Question D2:

D2 — How should the build mark a missing Impressum/Datenschutz value?
Project/branch/task: claude/pre-public-items-plan-e8d01d, step 6 of the Impressum/licence plan.
ELI10: Until you supply your address, e-mail and host, the two legal pages show a stand-in text. The plan wanted the done check to be "the phrase 'steht noch aus' appears nowhere on the site". But real speeches say that phrase too ("ein Urteil steht noch aus"). It is on 9 pages of the reference site, so that check could never pass, and it can't tell a missing address from a quoted speech.
Stakes if we pick wrong: the site could go public with a stand-in where the Impressum address belongs, and nothing would flag it; or the check fails forever on speech text.
Recommendation: A because a dedicated attribute is unambiguous, survives copy changes, and lets the future deploy step refuse with one exact check.
Completeness: A=10/10, B=7/10
Pros / cons:
A) Dedicated marker attribute (recommended)
  ✅ `data-operator-missing` never occurs in source text, so the check has no false hits from speeches or bills.
  ✅ A future deploy step, or a validator flag, can refuse on one exact selector that names the missing field.
  ❌ The TODO's done criterion has to be rewritten, and the visible text changes from "steht noch aus" to "Angabe folgt."
B) Grep limited to the three pages
  ✅ Keeps the TODO's wording and the visible text the plan already has.
  ✅ No new attribute, and nothing new to remember.
  ❌ The check depends on a list of file names, so a fourth page that needs the operator data (security.txt later) silently escapes it.
Net: a precise marker for a small rewrite of the TODO, or keeping the wording at the cost of a check that rests on a file list.

Header: Placeholder

Options:

A) Dedicated marker (recommended)
Each missing operator field renders as `<span data-operator-missing="<field>">Angabe folgt.</span>`. The TODO's done criterion becomes "no generated page carries data-operator-missing". A test builds without an operator file (the markers are present, one per missing field) and with a complete fixture (none present). Nothing refuses a build. Effort: human ~1h / CC ~10 min.

B) Scoped grep
The text stays "steht noch aus", and the done criterion becomes "grep over impressum.html, datenschutz.html and sources.html is empty". A test covers the same two builds. Nothing refuses a build. Effort: human ~45 min / CC ~5 min.

State: approved
Actual answer: A) Dedicated marker, D2, auto-decided by the owner's adjudicator on 2026-11-01. Reason: speech text contains the phrase, so a text check is ambiguous; the marker also covers pages added later.
Accepted scope:
- Each missing operator field renders as `<span data-operator-missing="<field>">Angabe folgt.</span>`.
- The TODO's done criterion becomes "no generated page carries data-operator-missing".
- A test builds without an operator file (one marker per missing field) and with a complete fixture (no markers).
- No build refuses.
- O1–O4 and steps 1–9 unchanged.
History: none

### Section 1, Architecture: findings

1. **A1** [P2] (confidence: 8/10). Plan step 6: "A missing file or field is not an error." An operator who passes `--operator-file` with a typo in the path gets a build in which every Impressum value shows "Angabe folgt.", and nothing tells them why.
   - The existing CLI refuses other bad operator input instead: `--data-issues-url` refuses an unsupported scheme with a `ValueError` (`build_dip_pulse_site.py:13328`).
   - Needs a decision (D3 below).
2. **A2** [P3] (9/10), factual correction. Step 4 said the "siehe Quellen und Methode" fallback stays "only for an explicitly empty value". But `license_text = getattr(args, "data_license", None) or os.environ.get("BUNDESTAG_PULSE_DATA_LICENSE") or ""` (L13324) turns `--data-license ""` into the default, so that case cannot occur. The fallback remains reachable through a remote manifest with no licence. Step 4 is amended.
3. **A3** [P3] (8/10), correction to an approved contract. The class-9 refusals in step 6 left out invalid JSON and non-UTF-8 input. Step 6 is amended; this is necessary implementation of O1 A.

Data flow (proposed):

```
operator.json ──(--operator-file / $BUNDESTAG_PULSE_OPERATOR_FILE)──> load_operator() ──┬─> render_impressum_page()   ─> impressum.html
  (untracked, owner)                     refuses: bad JSON/type/length/ctrl/url    └─> render_datenschutz_page() ─> datenschutz.html
                                         missing field -> data-operator-missing marker      (data_base_url host when absolute)

LICENSE-DATA.md (repo root, committed) ──> _license_notice() ─> DATA.md (embedded)
        │                              ──> short string ─> resolve_data_export_options() default ─> manifest.license / Daten panel
        └──> export copies into g-<hash>/ (kind "license", sha256) ─> publish_dip_pulse_data.py verifies vs manifest ─> release asset

render_legal_links(depth) ──> appended to 18 footers + new footer on render_database_unavailable_page
validate_publication_directory ──> requires impressum.html, datenschutz.html
```

## Decision ledger (continued)

### A1: an operator file path that does not exist

Finding: A1, P2, confidence 8/10, plan step 6. Reviewer: Claude (eng review).

Plan baseline: "A missing file or field is not an error", with the placeholder rendered. Step 6, approved with O1 A, and with D2 A for the marker.

Runtime evidence: no `--operator-file` exists today. The existing analogue, `--data-issues-url`, refuses bad input with a `ValueError` (L13328).

Comparison grid:

| Choice | Current (plan) | A | B |
|---|---|---|---|
| A1: `--operator-file` given, path missing or unreadable | placeholders, exit 0 | clear error, the build stops | placeholders and a warning line on stderr, exit 0 |
| No flag and no env var | placeholders | unchanged (placeholders, D2 marker) | unchanged |
| File present, a field missing | placeholder | unchanged (D2 marker) | unchanged |
| D2 marker, O1–O4, steps 1–9 | approved | unchanged | unchanged |

Question D3:

D3 — What happens when --operator-file names a file that does not exist?
Project/branch/task: claude/pre-public-items-plan-e8d01d, step 6 of the Impressum/licence plan (the operator file).
ELI10: The build reads your name, address and e-mail from a file whose path you pass in. The plan treats a missing file like "no data yet" and shows "Angabe folgt." on the Impressum. A typo in the path would then quietly produce an Impressum without your address, even though you meant to supply it.
Stakes if we pick wrong: a public build goes out with a stand-in Impressum because of a typo, and nothing stopped it. Or a build stops when you only meant to leave the data out.
Recommendation: A because you only pass the flag when you mean to supply data, so a missing file is an input error, and the CLI already refuses bad input that way.
Completeness: A=10/10, B=7/10
Pros / cons:
A) Refuse a missing file (recommended)
  ✅ A typo in the path stops the build with a message naming the path, before any page is written.
  ✅ Matches how --data-issues-url already refuses bad input, so the CLI behaves the same way everywhere.
  ❌ A scheduled build whose secret file failed to materialise stops instead of publishing placeholders.
B) Warn and use placeholders
  ✅ The build always finishes. A stale or missing secret never blocks a data update.
  ✅ The stderr warning still names the path for anyone who reads the log.
  ❌ Nobody reads the logs of an unattended build, so the stand-in can go public unnoticed.
Net: a hard stop on a mistyped path, or a build that always finishes and relies on someone reading a warning.

Header: Missing file

Options:

A) Refuse missing file (recommended)
If `--operator-file` or `$BUNDESTAG_PULSE_OPERATOR_FILE` is set and the path does not exist or cannot be read, the build stops with an error naming the path. With neither set, the D2 placeholders render. A test covers both cases. Effort: human ~20 min / CC ~3 min.

B) Warn, then placeholders
If the path is set but missing, the build writes one warning naming the path to stderr, renders the D2 placeholders and exits 0. A test asserts the warning and the markers. Effort: human ~20 min / CC ~3 min.

State: approved
Actual answer: A) Refuse missing file, D3, auto-decided by the owner's adjudicator on 2026-11-01. Reason: setting the flag means data is intended, and the CLI already refuses bad input.
Accepted scope:
- If `--operator-file` or `$BUNDESTAG_PULSE_OPERATOR_FILE` is set and the path does not exist or cannot be read, the build stops with an error naming the path.
- With neither set, the D2 placeholders render.
- A test covers both cases.
- D2, O1–O4 and steps 1–9 otherwise unchanged.
History: none

### Section 2, Code quality: findings

No issues found.
- `render_legal_links(depth)` has 18 verified callers: the `<footer>` templates in `build_dip_pulse_site.py` and `render_dip_pulse_html.py:4204`. It mirrors `render_global_header(depth)` (`render_dip_pulse_html.py:1247`).
- The operator loader follows `resolve_data_export_options` (L13318).
- The legal pages reuse `bill_styles()`, which includes `global_header_styles()` (L7766).
- No new module is needed.

### Section 3, Tests: coverage diagram

```
CODE PATHS (proposed)                                        USER FLOWS
[+] publish_dip_pulse_data.run_release                       [+] Reader opens Impressum from any footer
  ├── 10a previous manifest null/list/number  [GAP→plan test]   ├── [GAP→plan] root page footer -> impressum.html
  ├── 10b relative/# output dir               [GAP→plan test]   └── [GAP→plan] depth-1 page footer -> ../impressum.html
  ├── 10c --data-tag + --no-persist/manifest  [GAP→plan test] [+] Reader checks the licence
  ├── 10d CRLF autocrlf                        [GAP→plan test]   ├── [GAP→plan] Daten panel short string + LICENSE-DATA.md link
  └── license gate via manifest kind          [GAP→plan test]   └── [GAP→plan] sources.html#lizenz layer table
[+] export: LICENSE-DATA.md kind "license"    [GAP→plan test] [+] Operator builds the public site
  └── reuse path re-hashes it (S4)            [GAP→plan test]   ├── [GAP→plan] no file: markers present (D2)
[+] resolve_data_export_options default       [★★ test_data_pipeline_cli:98, update]  ├── [GAP→plan] file complete: no markers
[+] load_operator                                               ├── [GAP→plan] path set, missing: build stops (D3)
  ├── bad JSON / non-UTF-8 / non-object        [GAP→plan test]   └── [GAP→plan] bad field: clear refusal
  ├── non-string / long / ctrl / bad mail/url  [GAP→plan test]
  └── escaping (<script> in name)              [GAP→plan test]
[+] render_legal_links(depth)                  [GAP→plan demo walk]
  └── existing footer content preserved        [GAP] CRITICAL regression (D5)
[+] Datenschutz claims vs code                 [GAP] drift guard (D4)
[+] LLM summary label                          [GAP→plan pin, test_ai_summaries]
[+] validate_publication_directory required    [GAP→plan test]

COVERAGE (after plan tests): every proposed path has a planned test except D4/D5, which are pending.
QUALITY: the existing ★★ default test is updated; no ★ smoke-only additions.
```

### D4: a permanent test that keeps the Datenschutz page true

Finding: T1, P2, confidence 8/10, plan step 6 ("Every sentence must be true of the code", checked by grep "at implementation time"). Reviewer: Claude (eng review).

Plan baseline: a one-time grep when the page is written. Nothing re-checks the page later.

Runtime evidence: two localStorage keys today, `bundestag-pulse-theme` (`render_dip_pulse_html.py:893`) and `bundestag-pulse-ai-summaries-v1` (L1155). No external `<script src>`, `<link href>` or `@import` in any renderer (survey 2026-11-01). Nothing stops a later change from adding one.

Comparison grid:

| Choice | Current (plan) | A | B |
|---|---|---|---|
| T1: Datenschutz drift guard | one-time grep at implementation | a test reads the storage keys from `page_scripts()` and the src/href/@import hosts from the demo build, and asserts both match what `render_datenschutz_page` names | one-time grep only (as planned) |
| D2, D3, O1–O4, steps 1–9 | approved | unchanged | unchanged |

Question D4:

D4 — Add a test that fails when the code stops matching the Datenschutz page?
Project/branch/task: claude/pre-public-items-plan-e8d01d, step 6 (datenschutz.html).
ELI10: The Datenschutz page will promise readers "no cookies, no third-party resources, only these two settings stored in your browser". That is true today. If a later change adds a web font from a CDN or a third stored setting, the page would quietly become false, and a false privacy statement is the kind of thing that gets a private site operator an Abmahnung.
Stakes if we pick wrong: the legal page drifts out of date without anyone noticing, or we carry one more test that must be updated with every storage or resource change.
Recommendation: A because the page is a legal statement and the test costs one small test in an existing file, plus one walk over the demo build.
Completeness: A=10/10, B=6/10
Pros / cons:
A) Add the drift test (recommended)
  ✅ A new localStorage key or external host fails CI until the Datenschutz text names it.
  ✅ It reuses the demo build test_demo_site.py already makes, so no new fixture is needed.
  ❌ Every intentional new stored setting or host needs a matching text edit in the same change.
B) One-time grep only
  ✅ No extra test to maintain. The plan stays as written.
  ✅ The implementation-time grep still checks the first version of the page.
  ❌ Any later change can make the privacy statement false with no signal.
Net: a small, permanent guard on a legal claim, against no maintenance and silent drift.

Header: Drift test

Options:

A) Add drift test (recommended)
A test in `tests/test_demo_site.py`:
- collects the `localStorage` keys from `page_scripts()`;
- collects every non-relative `src`, `href` on `<link>` and `@import` URL from the demo build's HTML;
- asserts that the keys equal the list `render_datenschutz_page` names, and that no host is loaded other than ones the page names (none today).

Effort: human ~1h / CC ~10 min.

B) One-time grep only
Keep the plan's implementation-time grep and add no permanent test. Effort: none.

State: approved
Actual answer: A) Add drift test, D4, auto-decided by the owner's adjudicator on 2026-11-01. Reason: a false privacy statement is a correctness defect under CLAUDE.md, and only a permanent test catches later drift.
Accepted scope:
- A test in `tests/test_demo_site.py` collects the localStorage keys from `page_scripts()` and every non-relative `src`, `<link>` href and `@import` URL from the demo build.
- It asserts that the keys equal the list `render_datenschutz_page` names, and that no host is loaded other than ones the page names (none today).
- D2, D3, O1–O4 and steps 1–9 otherwise unchanged.
History: none

### D5: regression contract for the existing footers

Finding: T2, CRITICAL regression risk, confidence 8/10, plan step 5 ("Append it to each existing footer. Don't rewrite them."). Reviewer: Claude (eng review).

Plan baseline: append only. Only the dossier footer has tests: `tests/test_render_dip_pulse_html.py:146,157` and `tests/test_build_dip_pulse_site.py:4430`. The other 17 footers have no coverage.

Runtime evidence: 18 hand-written footers. Each has different text and links, for example "Das XML-Protokoll ist maßgeblich" on puls.html (L7093) and "--detail-limit" on overview.html (L10700).

Comparison grid:

| Choice | Current (plan) | A | B |
|---|---|---|---|
| T2: behaviour to preserve | everything outside the new span, unstated | every byte of every generated page except the inserted `<span class="legal-links">…</span>`, plus the new footer on `render_database_unavailable_page` | the dossier footer only (existing tests) |
| Intentional differences | the new span on every footer, a new footer on one page | the same, stated in the test | the same, stated nowhere |
| Acceptance | none | the demo site is rendered twice, once with `render_legal_links` patched to return "" and once as is; every page must be byte-identical once the span is removed, with wall-clock `generated_at` normalised, except the database-unavailable page, which is checked separately | the existing dossier tests pass |
| D2, D3, D4, O1–O4, steps 1–9 | approved | unchanged | unchanged |

Question D5:

D5 — How do we prove the footer change removed or altered nothing else?
Project/branch/task: claude/pre-public-items-plan-e8d01d, step 5 (legal links in every footer).
ELI10: Step 5 edits 18 hand-written footers to add two links. Only the dossier footer has tests today. A slip in any of the other 17 (a lost link to Quellen, a broken sentence, a misplaced tag) would go unnoticed. The review's rules require a stated regression contract for a change like this: what stays, what changes, and how a test proves it.
Stakes if we pick wrong: a footer link or sentence quietly disappears from thousands of pages, or we write a test that adds time to every CI run.
Recommendation: A because it proves "nothing but the span changed" across every page type in one test, without hand-listing 17 footers.
Completeness: A=10/10, B=4/10
Pros / cons:
A) Render twice, compare (recommended)
  ✅ Any change outside the new span, on any page type, fails the test with the page name.
  ✅ No per-footer expectations to maintain: the test compares the build with itself.
  ❌ The demo site is built twice in that test, which adds a few seconds to the suite.
B) Existing dossier tests only
  ✅ No new test, and no extra build time.
  ✅ The dossier footer, the most complex one, stays covered.
  ❌ 17 footers have no regression coverage while all 18 templates are edited.
Net: one comparison test that covers every page, or relying on the diff review for 17 footers.

Header: Footer guard

Options:

A) Render twice, compare (recommended)
Preserve every byte of every generated page except the inserted `<span class="legal-links">…</span>`. The intended differences are that span on every footer and a new footer on `render_database_unavailable_page`. A test in `tests/test_demo_site.py` renders the demo site twice: once with `render_legal_links` patched to return "", once as is. It asserts that every page is identical once the span is removed, with known wall-clock fields such as `generated_at` normalised, and checks the database-unavailable page's new footer separately. Effort: human ~1h / CC ~10 min.

B) Dossier tests only
Preserve the dossier footer through its existing tests. The other 17 footers rely on diff review. Effort: none.

State: approved
Actual answer: A) Render twice, compare, D5, auto-decided by the owner's adjudicator on 2026-11-01. Reason: 17 edited footers had no coverage, and a missing footer link is user-facing.
Accepted scope:
- Preserve every byte of every generated page except the inserted `<span class="legal-links">…</span>`. The intended differences are that span and a new footer on `render_database_unavailable_page`.
- A test in `tests/test_demo_site.py` renders the demo site twice: once with `render_legal_links` patched to return "", once as is.
- It asserts that the pages are identical once the span is removed, with `generated_at` normalised, and checks the new database-unavailable footer separately.
- D2, D3, D4, O1–O4 and steps 1–9 otherwise unchanged.
History: none

### Section 4, Performance: findings

No issues found.
- `render_legal_links` adds one string per page (about 6,750 pages after A3, measured 2026-10-29).
- The operator file and `LICENSE-DATA.md` are each read once per build.
- The export gains one file of about 10 KB (estimated from `docs/data-license.md`).
- D5's test renders the demo site a second time. The time this adds is unknown and should be measured when the test is written.

### Outside voice

Unavailable.
- Codex failed in this sandbox: "failed to initialize in-process app-server client: Operation not permitted".
- The native Plan-subagent fallback did not report within five minutes and was stopped.
- Recorded as `outside_status: unavailable`. Fix: run `codex review` outside the sandbox.
- No cross-model check exists for this plan.

### T3: TODO, refuse a public deploy while operator markers remain

Finding: TODO proposal arising from D2/D3, P2, confidence 8/10. Reviewer: Claude (eng review).

Plan baseline: no build refuses on missing operator data (D2 A, accepted scope "No build refuses").

Runtime evidence: there is no deploy step today. The hosting item (`TODOS.md:118`) and the scheduled-release item (`TODOS.md:134`) will add one.

- **What:** the future deploy step, whether hosting or the scheduled workflow, refuses to publish when any generated page carries `data-operator-missing`, and names the fields.
- **Why:** D2 makes a missing Impressum value detectable, but nothing yet acts on it. A public site with "Angabe folgt." where the address belongs fails § 18 MStV.
- **Pros:** one exact check at the point of no return; demo and CI builds are unaffected.
- **Cons:** another gate in a deploy pipeline that does not exist yet; it must be remembered when that pipeline is built.
- **Context:** the marker comes from step 6 of this plan. Start in whatever script or workflow first copies the site to a public host.
- **Depends on:** this plan (step 6), and the hosting decision.

Comparison grid:

| Choice | Current | A | B | C |
|---|---|---|---|---|
| T3: deploy refuses on markers | not recorded | added as a bullet to the hosting item in TODOS.md | not recorded | built now, as a `--validate-publication --require-operator` flag |
| D2 "No build refuses", D3, D4, D5, O1–O4 | approved | unchanged | unchanged | D2's normal builds unchanged; refusal only with the new flag |

Question D6:

D6 — Record a TODO so the future deploy refuses an Impressum that still says "Angabe folgt."?
Project/branch/task: claude/pre-public-items-plan-e8d01d, follow-up to D2 (the operator markers).
ELI10: After this change, a missing address or e-mail shows "Angabe folgt." with a machine-readable marker. Nothing stops a deploy with those markers yet, because there is no deploy step. The question is whether to write down now that the deploy must check for them, build a check flag right away, or leave it.
Stakes if we pick wrong: the first public deploy goes out with an incomplete Impressum, or we build a flag for a pipeline that doesn't exist yet.
Recommendation: A because the check belongs in the deploy step, which isn't built yet, and a TODO bullet under hosting makes sure it isn't forgotten.
Note: options differ in kind, not coverage. No completeness score.
Pros / cons:
A) Add to TODOS.md (recommended)
  ✅ The requirement sits in the hosting item, which is exactly where the deploy step will be designed.
  ✅ No code for a pipeline that does not exist yet, and this PR's diff stays as approved.
  ❌ It relies on someone reading the hosting TODO when the deploy is built.
B) Skip
  ✅ No added text. D2's marker still exists for anyone who looks for it.
  ✅ Keeps TODOS.md shorter.
  ❌ Nothing records that a deploy must refuse an incomplete Impressum.
C) Build it now
  ✅ A `--require-operator` flag on `--validate-publication` exists and is tested before any deploy.
  ✅ The future deploy only has to pass one flag.
  ❌ Adds scope to an already large PR, for a caller that does not exist yet.
Net: a reminder in the right place, nothing, or a flag built ahead of its caller.

Header: Deploy TODO

Options:

A) Add to TODOS.md (recommended)
Add one bullet to "Site hosting plan for the 2.5 GB generated site": the deploy refuses when a page carries `data-operator-missing`, and names the fields. No code in this PR. Effort: human ~5 min / CC ~1 min.

B) Skip
Record nothing. The marker exists, but no TODO says a deploy must check it. Effort: none.

C) Build it now
Add `--require-operator` to `--validate-publication` in this PR. It makes `validate_publication_directory` fail when any page carries the marker, with a test. Normal builds are unchanged. Effort: human ~1h / CC ~10 min.

State: approved
Actual answer: A) Add to TODOS.md, D6, auto-decided by the owner's adjudicator on 2026-11-01. Reason: no deploy step exists yet; the reminder goes where the deploy will be designed.
Accepted scope:
- One "Deploy gate" paragraph added to the TODOS.md hosting item ("Site hosting plan for the 2.5 GB generated site"), written during this review.
- No code in this PR.
History: none

Approval readiness: PASS. Checked IDs and their answers:
- D1, structure A (auto-decided)
- S1/D2 A
- A1/D3 A
- T1/D4 A
- T2/D5 A
- T3/D6 A
- S4 and A3 are necessary implementation of O1/O3 A (owner answer "Yes, all four").
- S2, S3, S5 and A2 are factual corrections with no change in behaviour.

## Review outputs

### NOT in scope
- `security.txt` and the private-e-mail contact link wait on the domain, in the Community item.
- Per-page "Fehler melden" links belong to batch 8 and the Community item.
- The deploy gate on `data-operator-missing` is recorded in the TODOS hosting item (D6). No code in this PR.
- Release-pipeline deferrals 1–5 and 7–9 stay P2 in TODOS.
- Footer copy with dev wording ("--detail-limit", "Statischer Prototyp") is cosmetic and predates this plan.
- Choosing a host decides the Datenschutz hosting paragraph, which renders a placeholder until then.

### What already exists
- `render_global_header(depth)` (`render_dip_pulse_html.py:1247`) is the pattern `render_legal_links(depth)` copies.
- Every page already includes `global_header_styles()`, directly or through `bill_styles()` (L7766) or `_facts_page_style()` (L9472), so one `.legal-links` rule reaches all pages.
- `resolve_data_export_options` (L13318) is the pattern for the operator flag and env var. `safe_issues_url` (L12748) is the URL check to reuse.
- `_license_notice` (L3857) and `CODEBOOK_INPUT_FILES` (L3058) already embed the licence text in DATA.md. The plan only retargets the path.
- The release script already verifies authored inputs against the commit (`publish_dip_pulse_data.py:113-118`). Moving the licence into the codebook inputs reuses that check, which is how item 6 gets fixed.
- `validate_publication_directory` (`publication_state.py:396`) already checks the required files and the publication denylist.
- The LLM summary label already exists (`render_dip_pulse_html.py:2808`, 2891). The plan only pins it with a test.

### Failure modes

| New path | Realistic failure | Test / handling | User sees |
|---|---|---|---|
| Operator file | path typo | D3 refusal plus a test | a clear error naming the path |
| Operator file | `<script>` or `javascript:` in a field | class-9 refusal and escaping, with tests | a clear error, or escaped text |
| Missing operator data | public deploy with placeholders | D2 marker plus a test; deploy gate is a TODO (D6) | "Angabe folgt.", detectable |
| Footer helper | wrong depth prefix, or a lost existing link | demo walk plus D5 comparison test | a broken link, caught in CI |
| LICENSE-DATA.md in the export | kind not accepted, or reuse skips the re-hash | S4 plus tests | the export refuses (clear) |
| Default licence string | "## Short string" section missing | refusal plus a test | a clear error |
| `--publish` | item 10a–d input | step 1 refusals plus tests | a clear refusal |
| Datenschutz text | later drift from the code | D4 drift test | CI failure |

Critical gaps: 0. Every failure mode has a test or a clear error.

### Worktree parallelization strategy

| Step | Modules touched | Depends on |
|---|---|---|
| 1 Release P1 fixes | scripts/ (publish, build CLI), tests/ | — |
| 2–4 Licence files, export kind, default string | repo root, scripts/ (build export, data_dictionary), tests/ | — |
| 5–6 Footer helper, legal pages, operator loader | scripts/ (render, build site), scripts/publication_state, tests/ | batches 7 and 8 merged first (O4 A) |
| 7–9 sources.html table, AI label pin, docs | scripts/ (build site), docs/, TODOS.md | 2–4 for the wording |

Sequential implementation, no parallelization opportunity. Every step edits `scripts/build_dip_pulse_site.py`, so parallel lanes would conflict on one 13k-line file.

## Implementation Tasks
Synthesized from this review's findings. Each task derives from a specific finding above. Run with Claude Code or Codex; check the box as you ship.

- [ ] **T1 (P1, human: ~1h / CC: ~10min)** — operator placeholders — Render a missing field as `<span data-operator-missing="<field>">Angabe folgt.</span>` and rewrite the TODO done criterion.
  - Surfaced by: Scope Challenge, S1 (D2 A).
  - Files: scripts/build_dip_pulse_site.py, TODOS.md, tests/test_demo_site.py
  - Verify: `python3.13 -m unittest tests.test_demo_site`
- [ ] **T2 (P2, human: ~1h / CC: ~10min)** — export — Add the `license` file kind to the inventory validator, `_REUSE_HASHED_KINDS` and the Daten list.
  - Surfaced by: Scope Challenge, S4.
  - Files: scripts/build_dip_pulse_site.py, tests/test_daten_export.py
  - Verify: `python3.13 -m unittest tests.test_daten_export`
- [ ] **T3 (P2, human: ~20min / CC: ~3min)** — operator loader — Refuse an operator path that is set but missing or unreadable.
  - Surfaced by: Architecture, A1 (D3 A).
  - Files: scripts/build_dip_pulse_site.py, tests/test_data_pipeline_cli.py
  - Verify: unittest for both cases
- [ ] **T4 (P2, human: ~20min / CC: ~3min)** — operator loader — Refuse invalid JSON and non-UTF-8 input with a clear error.
  - Surfaced by: Architecture, A3.
  - Files: scripts/build_dip_pulse_site.py, tests/test_data_pipeline_cli.py
  - Verify: unittest
- [ ] **T5 (P2, human: ~1h / CC: ~10min)** — tests — Add the Datenschutz drift test (storage keys and external hosts).
  - Surfaced by: Test review, T1 (D4 A).
  - Files: tests/test_demo_site.py
  - Verify: `python3.13 -m unittest tests.test_demo_site`
- [ ] **T6 (P1, human: ~1h / CC: ~10min)** — tests — Add the footer regression comparison: render twice, strip the span, normalise `generated_at`.
  - Surfaced by: Test review, T2 (D5 A).
  - Files: tests/test_demo_site.py
  - Verify: `python3.13 -m unittest tests.test_demo_site`
- [ ] **T7 (P3, human: ~5min / CC: ~1min)** — plan text — Apply the factual corrections S2, S3, S5 and A2 while building. They are already applied in this plan.
  - Surfaced by: Scope Challenge and Architecture.
  - Files: none beyond the planned steps
  - Verify: read steps 1, 3, 4 and 5

_No new tasks from Code quality or Performance._

### Unresolved decisions
None in this review.

### Completion summary
- Step 0, Scope Challenge: scope accepted as-is (D1: Original arrangement).
- Reality rows: 7 of 7 applicable rows emitted; 0 unverified premises (3 false premises corrected).
- Architecture review: 3 issues found (A1 via D3; A2 and A3 corrected).
- Code quality review: 0 issues found.
- Test review: diagram produced, 2 gaps identified (D4 drift test, D5 footer regression).
- Performance review: 0 issues found.
- NOT in scope: written.
- What already exists: written.
- TODOS.md updates: 1 item proposed and added (D6, the deploy gate in the hosting item).
- Failure modes: 0 critical gaps flagged.
- Unresolved decisions: 0 in this review.
- Outside voice: Codex unavailable (sandbox "Operation not permitted"); the native fallback produced no report within 5 minutes; no outside coverage.
- Parallelization: 0 parallel lanes, 4 sequential steps.
- Lake Score: 4 of 4 completeness-scored answers picked the 10/10 option (D2, D3, D4, D5).
- Scope Challenge findings, reported separately: 5 (S1–S5).
- Test plan artifact: `~/.gstack/projects/LucaAlv-poliwatch/Luca-claude-pre-public-items-plan-e8d01d-eng-review-test-plan-20261101-155550.md`.

### Suppressed findings
None.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Review | codex-plan-review (auto, in eng review) | Independent 2nd opinion | 1 | unavailable | none (Codex sandbox failure; native fallback timed out) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open (all resolved) | 5 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:** codex, plan-review phase, unavailable. Codex exec failed with "Operation not permitted" in the sandbox; the native Plan fallback was stopped after the 5-minute timer. No findings, and no clean credit.
- **VERDICT:** no review is CLEAR. Eng Review found 5 issues and resolved all of them (D2–D5 and corrections; the status stays issues_open by rule). The plan is ready to implement with the amendments above. eng review required
NO UNRESOLVED DECISIONS

## Implementation notes, 2026-11-01

Where the build differs from the steps above, and why:

- **O4, branch order.** Batches 7 and 8 were not on main, so the owner chose to build on 4705fb3 anyway. Once PR #127 (batches 5–8, v0.28.0.0) landed, the branch was rebased onto d189961. There were two conflicts: the Daten footer, which keeps main's „Datenfehler melden (GitHub)“ label and adds the legal span, and the `--data-issues-url` row in `docs/project-documentation.md`, which keeps main's text.
- **10a.** The plan said to also run `build_dip_pulse_site.validate_manifest` on `--previous-manifest`. That validator refuses every export format but the current one, so the release after this branch's format bump (11 to 12) could never name its predecessor. `publish_dip_pulse_data.previous_manifest_problem` checks the fields `release_changes` reads instead, and refuses `null`, numbers and lists.
- **10c.** The release script has no "requested version" input. The build itself now refuses: `parse_args` rejects a release `--data-tag` with `--no-persist` or `--data-manifest`, and `run_data_pipeline` raises when no export carries the tag (no store, `DataExportUnavailable`, `$BUNDESTAG_PULSE_DATA_MANIFEST`).
- **10d.** Both sides are normalised (`build_revision.text_sha256`), not one, so the outcome does not depend on the checkout the release script runs in.
- **Step 3, release check.** `verify_export` checks the licence file for every run, dry or `--publish`. The file must be listed, non-empty, and its `sha256` must equal `codebook_inputs["LICENSE-DATA.md"]`, which is already verified against the manifest commit. The licence file is written before `DATA.md`, so `DATA.md`'s file table lists it.
- **Step 3, preamble.** The old preamble was for maintainers. `LICENSE-DATA.md` has a new short one for someone who opens it in a download. The maintainer notes moved to `docs/project-documentation.md`.
- **Step 6, URL check.** The site's `safe_href` allowlists Bundestag hosts, and a host's or authority's URL cannot be on that list. Operator URLs must be `https://` with a host and no credentials, the rules `validate_external_url` applies without its allowlist. Unknown fields in the operator file are refused, so a typo in a key does not silently become a placeholder.
- **Footer coverage.** The demo build has no Abgeordnete detail pages, Fakt week or month pages, or bill detail pages. The D5 comparison covers the 16 pages it does build. The other footers got the same one-line insertion, reviewed by hand.
