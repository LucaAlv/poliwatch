# Audit remediation plan

Findings from a full-project audit on 2026-08-18. Line numbers are anchored to commit
`53a2b8d` (v0.1.1.0); re-grep before editing if HEAD has moved.

Tasks are independent — pick any, in any order. Each one names its own completion criterion.

## The tight loop

Everything here verifies offline. No API key, no network, no `.context/` cache needed:

```bash
python3 -m py_compile scripts/*.py scripts/features/*.py
python3 -m unittest discover -s tests
```

47 tests, ~0.3s. Several tasks below also want the **probe** — a real site built from a
poisoned fixture, described under Task 1.

## Fog of war

Two subsystems were not audited line-by-line: the XML parsing and roll-call scraping in
`scripts/validate_dip_protocol.py` (1365 lines, 56% covered) and the resolution logic in
`scripts/abgeordnetenwatch.py` (431 lines, 40% covered). Findings below do not cover them.
Task 8 is the follow-up.

## Settled state

These were checked and are correct. Treat them as verified and spend effort elsewhere:

- **HTML text escaping.** `pulse_html.esc` is applied at 239 sites in the builder. The probe
  confirmed `<script>` payloads, `</script>` breakouts, and attribute-quote breakouts are all
  neutralised, and that zero payloads reach a `<script>` context.
- **SQL.** `sqlite_identifier` (`build_dip_pulse_site.py:552`) escapes embedded quotes, table
  names come from `sqlite_master`, the explorer connects `mode=ro`, and the `ALTER TABLE` at
  `persist_dip_pulse_store.py:274` iterates the hardcoded `_MPS_ADDED_COLUMNS` tuple.
- **Exception discipline.** Zero bare `except:`, zero swallowed exceptions, narrow types
  throughout.
- **Database rebuild atomicity.** `rebuild_database_from_entries` (`:435-448`) builds into a
  temp file and `replace()`s it.
- **Generated HTML structure.** All 11 pages are well-formed, with `lang`, `<title>`, and
  exactly one `<h1>`.
- **Documented flags, defaults, and Baustein dependencies.** Every flag in the README table
  and the docs reference exists in `parse_args` with the documented default and semantics.
  The precedence chain, the "core Bausteine cannot be disabled" rule, and the disable-cascade
  were probed live and behave as documented.
- **Secrets.** No API key reaches generated output; git history is clean.

## Known trap

The DIP `/plenarprotokoll` endpoint returns results ordered by **`datum` descending**, not by
`aktualisiert` descending. This was established by measurement. Reviewers repeatedly assume
the reverse and file high-severity ordering bugs that are not real. Task 3 concerns a
different ordering defect — the same-date tiebreak — which is genuine.

---

## Task 1 — Validate URL schemes (P1)

`esc()` is HTML-escaping only, and no URL scheme validation exists anywhere in the codebase.
Upstream `xml_url` / `pdf_url` values flow straight into `href`. A poisoned cache or a
compromised upstream yields a working `javascript:` URI in published output. README §7
documents hosting that output publicly.

Confirmed by probe — the generated `puls.html` contained:

```html
<a href="javascript:alert(4)">XML-Protokoll</a>
```

**Sinks** (`scripts/build_dip_pulse_site.py`): `1983`, `1984`, `2044`, `3442`, `3443`, `4476`,
`4477`, `4487`, `4488`, plus the bill timeline and abgeordnetenwatch profile links. Grep
`href="{` across both renderers to enumerate the full set rather than trusting this list.

Add a `safe_url()` helper beside `esc()` in `scripts/render_dip_pulse_html.py` that allows
`http` and `https` and returns `""` otherwise, then route every upstream-derived `href` and
`src` through it.

**Building the probe.** Copy the fixture, inject payloads, build, grep:

```bash
python3 - <<'PY'
import json, pathlib
d = json.loads(pathlib.Path('tests/fixtures/report.json').read_text())
d['protocol']['pdf_url'] = d['protocol']['xml_url'] = 'javascript:alert(4)'
d['protocol']['titel'] = 'TITEL <script>alert(1)</script>'
d['sampled_people'][0]['titel'] = 'Ada </script><img src=x onerror=alert(2)>'
d['sampled_people'][0]['fraktion'] = '" onmouseover=alert(3) x="'
d['agenda_items'][0]['api']['positions'][0]['source']['pdf_url'] = 'javascript:alert(4)'
out = pathlib.Path('/tmp/probe/data'); out.mkdir(parents=True, exist_ok=True)
(out / 'plenarprotokoll-20-999.json').write_text(json.dumps(d, ensure_ascii=False))
PY
python3 scripts/build_dip_pulse_site.py --offline --output-dir /tmp/probe --features all
grep -rn 'href="javascript:\|src="javascript:' /tmp/probe --include="*.html"
```

**Done when:** the probe's final grep returns nothing, every upstream-derived `href`/`src` in
both renderers passes through `safe_url`, and a unit test pins the helper's behaviour for
`javascript:`, `data:`, protocol-relative `//host`, and a normal `https:` URL.

## Task 2 — Correct the documentation mismatches (P2)

The README is accurate almost everywhere. These are the exceptions, ordered by how likely
each is to burn someone following the guide.

1. **`--protocol-wahlperiode` is documented nowhere** and it changes what `--limit` means.
   `build_dip_pulse_site.py:106` reads `if limit > 0 and wahlperiode:` with the flag
   defaulting to `21` (`:5181`). So `--limit 0` reaches back to 1949 as README §4b claims,
   but any `--limit N > 0` silently restricts the fetch to WP21 — `--limit 500` cannot reach
   older periods without `--protocol-wahlperiode 0`. Document the flag in the README flag
   table and the docs reference, and state the interaction.
2. **README §4c's re-persist recipe drops the MdB roster.** The loop is correct, but §4c
   line 146 describes it as working "the way the online build does". The online build also
   runs `ingest_mdb_roster` (`:5316-5330`, `:2750-2764`), which fetches DIP `/person` live.
   No cached roster file exists, so a user with `mp-roster` enabled who follows the recipe
   loses roster-only MPs — the same silent shrink §4b warns about. Add the caveat.
3. **README §7's deploy command lacks `--offline`.** As written it aborts without a DIP key
   (`:5265-5268`), and `--features all` refetches the full catalog plus the three slowest
   features. Add `--offline`. That same `--features all` also enables `dev-view`, which
   publishes your local absolute path — see Task 9.
4. **The precedence chain omits `--features-file`.** Both README §5 and
   `docs/project-documentation.md:178` give an 8-step chain; `:4991-4997` implements 9 steps,
   with `--features-file` between `features.local.json` and `BUNDESTAG_PULSE_FEATURES`. The
   docs reference contradicts itself — line 358 documents the flag, line 178 omits it.
5. **settings.html shows a flag, not a command.** README §5 promises "the exact command needed
   to build it"; `render_dip_pulse_html.py:526-530` renders `<code>--enable {id}</code>`, and
   the page's own footer (`:4801`) calls it a *Build-Argument*. Match the README to the page.
6. **README §2 says `.env.local` is read by "the two scripts that make API calls".**
   `scripts/abgeordnetenwatch.py` also makes live calls; it just needs no key.
7. **`docs/project-documentation.md:489`** attributes `GOOGLE_API_KEY` to validation only,
   while the same file's line 393 correctly gives it as a builder fallback.
8. **README §9 links `TODOS.md`**, which holds only `# TODOS` and an empty `## Completed`.
   Give the file content or drop the link.

**Done when:** each of the eight items is either corrected or has a one-line note in this plan
recording why it was left alone, and `grep -rn "protocol-wahlperiode" README.md docs/` returns
a hit.

## Task 3 — Fix the ordering tiebreak and the cursor loop (P3)

Two defects in `scripts/build_dip_pulse_site.py`, both small:

- **`protocol_sort_key` (`:61`)** returns `(datum, id)` where `id` is compared as a string, so
  two protocols sharing a `datum` sort as `id-100 < id-99`. This is the bug class that caused
  the v0.0.2.0 "Aktueller Puls" regression. `catalog_sortnum` (`:3738`) was given a zero-padded
  numeric key at the time; `protocol_sort_key` was not. Give it a numeric tiebreak.
- **`fetch_protocols` (`:110-118`)** breaks when the API repeats a cursor, but a page returning
  zero documents with a rotating cursor loops forever. Break when a page adds no documents.

**Done when:** a test pins that same-date protocols with ids `9`, `10`, `99`, `100` order
numerically, and a test drives `fetch_protocols` against a stub client returning empty pages
with rotating cursors and asserts termination.

## Task 4 — Make report writes atomic (P3)

`write_report_files` (`:284-292`) writes the dossier JSON and HTML with plain `write_text`,
while the sibling database rebuild already uses tmp + `replace()`. An interrupted build leaves
truncated JSON; the next build skips it with a stderr warning, so a dossier disappears from
the site quietly. Use the same tmp + `replace()` pattern.

While in this function's neighbourhood: `rebuild_database_from_entries` (`:442-447`) unlinks
the temp file in its `except` block before `finally: store.close()` runs. On POSIX this is
fine. On Windows the unlink raises `PermissionError` and masks the original exception. Close
first, then unlink.

**Done when:** both dossier files are written via tmp + `replace()`, and the temp database is
closed before it is unlinked.

## Task 5 — Verify the PID before killing it (P3)

`stop_server` (`scripts/preview_dip_pulse_site.sh:53`) kills whatever PID sits in the PID file.
A stale file whose PID has been recycled means killing an unrelated process. Confirm the
process is the expected `http.server` before signalling it.

**Done when:** `stop` leaves a recycled, non-matching PID running and says so.

## Task 6 — Reconcile the Python version floor (P2)

The code runs on **Python 3.9**. Verified: `py_compile` and all 47 tests pass under 3.9.6, and
no 3.10+ runtime feature exists anywhere in `scripts/` — the five `scripts/features/*.py`
modules lacking `from __future__ import annotations` use only PEP 585 builtin generics, which
are 3.9-native.

README §1 claims 3.11+, the CI matrix is 3.11/3.12/3.13, and nothing enforces either: there is
no `python_requires` and no runtime check. A contributor on 3.9 sees green locally and green in
CI, so a genuine 3.11-only feature can land unnoticed.

Pick one and make it true — either extend the CI matrix down to 3.9 and relax the README, or
keep 3.11 as the floor and add a check that enforces it.

**Done when:** the README, the CI matrix, and an enforcement mechanism agree on one number.

## Task 7 — Extract the page renderers (structural, 2-3 days)

`scripts/build_dip_pulse_site.py` is **79% presentation**: of 5127 function-lines, 4075 are
rendering and 1052 are orchestration. `render_front_page` alone is 599 lines
(`:1440-2038`); `render_catalog_page` 462 (`:3992-4453`); `render_database_page` 386
(`:702-1087`); `render_overview` 349; `render_landing_page` 312; `render_sources_page` 305.
Separately, 916 lines of CSS and JS live in Python string literals across 11 functions.

The seam already exists and is half-built. `scripts/render_dip_pulse_html.py` is already the
shared presentation library — it owns `esc`, `page_head`, `page_scripts`,
`render_global_header`, `global_header_styles`, the theme and feature scripts, and the dossier
page itself. The builder consumes it 266 times. What remains is that every *other* page
renders inline in the builder.

Move the page renderers into modules beside `render_dip_pulse_html.py`, splitting by page
family (catalog, overview, database, bills, abgeordnete, settings). That leaves the builder at
roughly 1200 lines of genuine fetch, cache, merge, CLI, and feature resolution.

Do this after Task 1, so the `safe_url` call sites move once rather than twice.

**Done when:** `scripts/build_dip_pulse_site.py` contains no `render_*` function, the test suite
passes unchanged, and a site built from `tests/fixtures/report.json` with `--features all`
differs from one built at the starting commit only in `data/features.json`'s `generated_at`
field (see Task 9 — if Task 9 landed first, the diff is empty).

## Task 8 — Audit the unexamined subsystems

The XML parsing and roll-call scraping in `scripts/validate_dip_protocol.py` and the resolution
logic in `scripts/abgeordnetenwatch.py` were not examined line-by-line. They are the two
lowest-covered procedural modules and both parse markup from sources that change without
notice — `docs`/README §8 already documents a `warning:` path for the roll-call list markup
changing.

Ground the work in the committed fixtures: `tests/fixtures/protocol.xml`,
`roll_call_list.html`, `member_votes.html`.

**Done when:** every parsing function in both modules has been traced against its fixture, and
each malformed-input path is either covered by a test or recorded here as accepted risk.

## Task 9 — Stop leaking the local path, and make the build reproducible (P2)

Two builds of the same input differ in exactly two places:

```
api-sitzungen.html:717  data-output-dir="/tmp/det1"   vs   data-output-dir="/tmp/det2"
data/features.json:2    "generated_at": "...819491+00:00"  vs  "...054701+00:00"
```

The first is an information leak. The `dev-view` Baustein embeds the **absolute local output
directory** into the page, so a published site carries a path like
`/Users/<name>/conductor/workspaces/poliwatch/khartoum/.context/dip-pulse-site`. This matters
more than it looks: README §7's deploy command is `--features all`, which enables `dev-view`.
Following the documented hosting instructions publishes your local directory structure. Render
the dossier command with a relative path, or gate the panel out of non-local builds.

The second blocks reproducible builds and makes any "did my refactor change the output" check
noisier than it needs to be. Honour [`SOURCE_DATE_EPOCH`](https://reproducible-builds.org/docs/source-date-epoch/)
when it is set, so the timestamp can be pinned.

**Done when:** two consecutive builds of the same input into different output directories are
byte-identical under a fixed `SOURCE_DATE_EPOCH`, and no absolute filesystem path appears in
any generated file:

```bash
grep -rn "$HOME\|/Users/\|/tmp/" /tmp/probe --include="*.html" --include="*.json"
```

## Coverage reference

Measured with the stdlib `trace` module (nothing to install). Import-time lines undercount, so
the `scripts/features/` figures are not meaningful; the procedural modules are sound.

| Module | Executable lines | Covered |
|---|---|---|
| `persist_dip_pulse_store.py` | 192 | 85% |
| `validate_dip_protocol.py` | 709 | 56% |
| `build_dip_pulse_site.py` | 1198 | 49% |
| `abgeordnetenwatch.py` | 250 | 40% |
| `render_dip_pulse_html.py` | 428 | 24% |
| **Total** | **3017** | **46%** |
