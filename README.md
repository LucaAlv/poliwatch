# Bundestag-Puls

Bundestag-Puls is a dependency-free static-site pipeline for German Bundestag primary sources. Every publication presents one fixed public product: sitting dossiers, speeches, Drucksachen, votes, laws, MP pages, and source links appear wherever validated data exists. Operators may refresh optional data sources; visitors do not have to configure the site. AI summaries are the one separate content preference and are clearly labelled, cited, and globally collapsible.

There is no package manager, no framework, and no build toolchain. Two things happen:

1. `scripts/build_dip_pulse_site.py` fetches DIP data (or reads the local cache) and writes plain HTML/JSON/SQLite into `.context/dip-pulse-site/`.
2. `scripts/preview_dip_pulse_site.sh` runs that build and serves the output with `python3 -m http.server` on localhost.

`.context/` is gitignored: it is build output and cache, never source.

## Daten nutzen (für Forschende und Datenjournalisten)

Jede Auswertung dieser Website beruht auf denselben Rohdaten, die als SQLite-Datei und als CSV veröffentlicht werden. Auf der lokalen Vorschau (`database.html`, Nav-Punkt "Daten") stehen: eine gzippte SQLite-Verteilkopie, 24 CSV.gz-Dateien, ein sha256 pro Datei, ein Datenstand-Band mit Abdeckung, und fünf bei jedem Build ausgeführte SQL-"Rezepte" mit Kopieren-Button und ihren Ergebniszeilen daneben.

Drei Wege, lokal an die Daten zu kommen (die Seite selbst zeigt die exakten Dateinamen und Prüfsummen des laufenden Builds):

```bash
# Shell (sqlite3)
curl -LO http://localhost:8000/data/exports/g-<hash>/bundestag-pulse-local.sqlite.gz
gunzip bundestag-pulse-local.sqlite.gz
sqlite3 -header -column bundestag-pulse-local.sqlite
```

```python
# Python stdlib
import gzip, shutil, sqlite3, urllib.request
urllib.request.urlretrieve(url, "bundestag-pulse.sqlite.gz")
with gzip.open("bundestag-pulse.sqlite.gz", "rb") as src, open("bundestag-pulse.sqlite", "wb") as dst:
    shutil.copyfileobj(src, dst)
conn = sqlite3.connect("bundestag-pulse.sqlite")
```

```python
# pandas, either the SQLite file or a CSV
import pandas as pd
pd.read_sql("SELECT * FROM speeches", conn)
pd.read_csv("speeches-local.csv.gz", keep_default_na=False, dtype={"mp_id": "Int64"})
```

SQLite ist die maßgebliche Quelle; die CSVs sind ein wörtlicher Export ohne Formel-Escaping (in Tabellenkalkulationen als Text importieren). Ein öffentlicher, versionierter Release über GitHub Releases ist geplant (`scripts/publish_dip_pulse_data.sh`, separates PR) und noch nicht verfügbar; die Lizenz-/Nutzungsformulierung steht ebenfalls noch aus (Platzhalter auf der Seite: "siehe Quellen und Methode").

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | `python3 --version`. Entry-point scripts reject older versions. No third-party packages are needed. |
| bash + git | The preview script is bash. On Windows use WSL, or call `build_dip_pulse_site.py` directly. |
| `DIP_API_KEY` | Required for every online fetch. Not needed for offline rebuilds. |
| `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | Only for generating optional AI summaries. |

Getting a DIP API key: the Bundestag publishes a shared public key on the [DIP API help page](https://dip.bundestag.de/%C3%BCber-dip/hilfe/api) (no registration), or you can request a personal, permanently valid key by e-mail to `parlamentsdokumentation@bundestag.de`.

## 2. First-time setup

```bash
git clone https://github.com/LucaAlv/poliwatch.git
cd poliwatch
cp .env.example .env.local
```

Edit `.env.local` and fill in the keys you have — at minimum `DIP_API_KEY`:

```bash
DIP_API_KEY=your-key-here
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

`.env.local` is gitignored. The preview script loads it, as do `build_dip_pulse_site.py` and `validate_dip_protocol.py` (the two scripts that make API calls); `render_dip_pulse_html.py` never reads it, nor does `persist_dip_pulse_store.py`, which is a library whose script mode only refuses. Precedence differs by entry point: the preview script sources the file, so `.env.local` overrides an already-exported variable; the Python scripts skip keys that are already exported, so there the environment wins.

That asymmetry has one sharp edge worth knowing before it bites you. `.env.example` ships `DIP_API_KEY=` with an empty value, so a copied-but-unedited `.env.local` will wipe a key you passed on the command line, and the preview script then aborts with `DIP_API_KEY is not set`. Either fill the key in `.env.local` or delete the empty line before passing one from the environment.

A fresh clone can build and open a representative site immediately, without credentials or network access:

```bash
scripts/preview_dip_pulse_site.sh demo
```

The demo uses a committed extract of the official Plenarprotokoll 21/84, TOP 32 a/b, including its 16 speeches and the linked Drucksachen 21/6354 and 21/4833. It writes to `.context/dip-pulse-demo/`, validates the public output, and starts a local server. No credentials or network requests are involved, so it is the quickest way to inspect the product or verify a frontend change.

To work with current Bundestag data, run an online build:

```bash
scripts/preview_dip_pulse_site.sh update --limit 5 --detail-limit 2
```

This fetches the 5 newest Bundestag protocols into the catalog, enriches the 2 newest into full dossiers, writes the SQLite store, and starts a background server on `http://localhost:8000/` (or `$CONDUCTOR_PORT` when that is set). On macOS it also opens the browser; elsewhere open the printed URL yourself. Budget roughly half a minute per enriched sitting; refreshing votes, profiles, or the full MdB roster makes it substantially slower.

Verify the install without touching the network at all:

```bash
python3 -m py_compile scripts/*.py
python3 -m unittest discover -s tests
```

The tests run from committed fixtures under `tests/fixtures/` and need no network, no `.context/`, and no API keys. The supported floor is Python 3.11; CI runs the same two checks on Python 3.11, 3.12, and 3.13.

Run every command from the repository root. The preview script `cd`s there itself; the Python scripts resolve `.context/dip-pulse-site` relative to the current directory.

## 3. Everyday loop

```bash
scripts/preview_dip_pulse_site.sh        # offline rebuild from cache + serve
```

The default mode is offline: it re-renders all HTML from cached JSON/SQLite and makes zero API calls. It finishes in well under a second, which is what makes it the right command for UI and rendering work. The Daten export (`data/exports/`) follows the same rule: it re-runs only when its inputs changed (the store, the recipes, the export format, the tag/licence/issues-URL flags, or the catalog/dossier/Baustein coverage it reports), so an unchanged offline rebuild stays sub-second too; the first export after a real data change costs a few seconds to tens of seconds depending on store size.

```bash
scripts/preview_dip_pulse_site.sh stop   # stop the background server
```

The server keeps running between rebuilds. `http.server` reads from disk on every request, so a rebuild never needs a restart — just reload the page.

## 4. Refreshing

Three different things get called "refresh". They need different commands.

### 4a. After a rebuild — refresh the browser

Reload the page (Cmd-R / Ctrl-R). Re-running the preview script while the server is up prints `Vorschau aktualisiert` and leaves the same PID serving the new files. If a page still looks stale, hard-reload; if the server itself is wedged:

```bash
scripts/preview_dip_pulse_site.sh stop
scripts/preview_dip_pulse_site.sh
```

### 4b. After new Bundestag data — refresh the data

`update`, `refresh`, and `fetch` are the same alias for "online build". Everything after that word goes to `build_dip_pulse_site.py`.

Pull the current catalog and re-enrich the newest sittings; every dossier already built stays:

```bash
scripts/preview_dip_pulse_site.sh update
```

Every online build fetches the whole catalog — every Bundestag plenary protocol back to 1949, 4,667 entries in an August 2026 run, in roughly 15 seconds — and caches it as an *authoritative* catalog (`data/plenarprotokoll-catalog.json`). It is what completeness is judged against: a week or month is complete only when every sitting the catalog lists for it is in the store and fully acquired (§5). Only the newest `--detail-limit` sittings become dossiers; the rest stay catalog rows.

**Acquisition and retention are separate scopes.** The flags below choose which sittings are *acquired* (fetched again and rewritten). The SQLite store and the site are always rebuilt from the whole catalog plus every dossier cached in `data/plenarprotokoll-*.json`, so a narrow update never drops another sitting, speech, vote or page. There is no flag for this.

Acquire exactly one sitting, leaving every other dossier untouched:

```bash
scripts/preview_dip_pulse_site.sh update --document-number 21/90
```

Related knobs, in the order you will reach for them:

| Flag | Effect |
|---|---|
| `--limit N` | Acquire only the newest N protocols of `--protocol-wahlperiode`. Default `0` = no cap. The catalog is always fetched whole. |
| `--detail-limit N` | Protocols enriched into dossiers. Default `5`; `0` = all fetched, `-1` = none. |
| `--document-number 21/90` | Acquire only this protocol (repeatable); the catalog and every cached dossier are kept. |
| `--dossier-document-number 21/90` | Also acquire this protocol on top of what `--detail-limit` selects. Repeatable. |
| `--backfill-incomplete` | Acquire exactly the sittings the build reports as incomplete (below). |
| `--summary-mode auto` | Regenerate summaries with an LLM. Default `reuse` keeps existing summaries without new calls. |
| `--enrich ID` | Add optional profile or full-roster acquisition to this update (`aw-profiles`, `mp-roster`, `all`). Votes are already on by default. |
| `--no-votes` | Skip roll-call vote acquisition for this update. Cached votes and their acquisition state are kept. |

To iterate on one dossier without touching the rest of a site, build it into its own directory: `scripts/build_dip_pulse_site.py --output-dir .context/scratch --document-number 21/90`.

### Backfill incomplete sittings

Every build that ran the facts engine prints what is incomplete, for example:

```text
warning: [facts] 4 weeks and 3 months are incomplete: a Fakt needs every sitting DIP lists, fully acquired.
  13 listed sittings are not in the store: 21/85, 21/86, 21/87, …
  not acquirable yet (DIP has no XML for them): 21/96, 21/97
  285 sittings are in the store but not fully acquired:
    votes: no vote acquisition metadata (report predates it) (285×)
  incomplete weeks (newest 4 of 4): 2026-W39 (missing 21/95, 21/96, 21/97); …
  Fix: python3 scripts/build_dip_pulse_site.py --output-dir .context/dip-pulse-site --backfill-incomplete   (acquires 296 sittings; every other cached dossier is kept)
  Docs: README.md#backfill-incomplete-sittings
```

The `facts` pages name the missing sitting too (`unvollständig erfasst: Sitzung 21/96 (2026-09-24) fehlt`). A sitting keeps its period incomplete for one of these reasons:

| Reason | Meaning |
|---|---|
| `not_persisted` | DIP lists it, the store has no dossier: never built, cut by `--detail-limit`, or its build failed. |
| `no vote acquisition metadata` | The cached report predates the recorded vote state, so nothing says the roll-call list was read. |
| `cached votes without acquired_at` | Votes were reused from a cache that never stamped them. |
| `votes not_requested` | The sitting was built with `--no-votes`, `--vote-scan-pages 0` or a `-votes` config entry. |
| `votes partial` / `votes failed` | The scan ran out of pages (`scan_budget_exhausted`: raise `--vote-scan-pages`), a request failed (`source_unavailable`) or the Bundestag markup changed (`source_changed`). |
| `XML speeches not parsed` | The dossier has no parsed speeches. |
| `no scan-end evidence` | The votes were stamped complete by a build that did not record how the scan ended. |
| `date_changed` | DIP now dates the sitting differently from the store; the backfill refreshes it. |
| `source_stale` | A sitting of the last two weeks with no roll call on a list whose newest entry is older: the list may not have caught up. It settles by itself after 14 days, or on the next backfill once the list catches up. |
| `scan_budget_exhausted after N pages` | A backfill at the same `--vote-scan-pages` reproduces it, so the backfill leaves the sitting alone and the printed fix raises the budget. |

One recipe fixes all of them:

```bash
python3 scripts/build_dip_pulse_site.py --output-dir .context/dip-pulse-site --backfill-incomplete
# add --vote-scan-pages 60 when the list names scan_budget_exhausted
```

`--backfill-incomplete` acquires exactly the listed sittings DIP has XML for, ignoring `--limit` and `--detail-limit` (and it cannot be combined with `--document-number`); every other cached dossier is kept. Each sitting is a full re-download of its XML and DIP data, so a backfill of many sittings takes a while. A sitting that is still incomplete afterwards stays in the next report with its reason. With votes switched off (`--no-votes`, `--vote-scan-pages 0` or a `-votes` config entry) the backfill skips the sittings held back only by votes, says how many, and the printed fix adds `--enrich votes`, which lifts a config veto.

### Try a fetch or a backfill in a scratch directory

Before an online run rewrites the site you serve, run it into a copy and look at the result. Call `build_dip_pulse_site.py` directly with its own `--output-dir`: the preview wrapper always builds into and serves its own `OUTPUT_DIR` (`DIP_PULSE_OUTPUT_DIR`, default `.context/dip-pulse-site`), so passing `--output-dir` through `update` would build somewhere it does not serve.

```bash
# 1. A copy of the cache (a clone copy, so it is cheap on macOS and APFS; use --reflink=auto elsewhere)
cp -cR .context/dip-pulse-site .context/scratch

# 2. The run under test, into the copy only
python3 scripts/build_dip_pulse_site.py --output-dir .context/scratch --backfill-incomplete

# 3. Look at it, on another port than the real preview
python3 -m http.server 8001 --directory .context/scratch

# 4. Compare the store with the original
for d in dip-pulse-site scratch; do
  sqlite3 .context/$d/data/bundestag-pulse.sqlite "SELECT COUNT(*), MAX(date) FROM votes"
done
```

The copy has its own `data/` (cached reports, catalog, store, abgeordnetenwatch cache), so the run reads and writes nothing else. Delete it with `rm -rf .context/scratch`, or swap it in with `mv` once the numbers are right. The build prints its incomplete-sittings report (above) for the copy too, so the run shows which weeks and months it fixed.

### 4c. After pulling code changes — refresh the site

```bash
git pull
python3 -m unittest discover -s tests
scripts/preview_dip_pulse_site.sh
```

The offline rebuild regenerates every page from the existing cache, so template, renderer, navigation, and presentation changes land without re-fetching. Old integer-ID stores require explicit `--offline --repersist`; plain offline rendering and direct export print the exact upgrade command instead of migrating them.

An offline rebuild does *not* re-derive the rows in that store — it only re-renders. Two cases therefore need more than step 4c:

- **The update changed what gets persisted** (new columns filled during persist, values derived from the cached reports). Re-persist the cached reports without any network access, see [Re-persist the cached reports](#re-persist-the-cached-reports) below.

- **The update changed what is read from the Plenarprotokoll XML** (what counts as a Rede, Redner parsing in `validate_dip_protocol.py` and `speech_kinds.py`). The cached XML in `data/xml/` is re-read by `--offline --repersist` without a network, see [Re-persist the cached reports](#re-persist-the-cached-reports) below.

- **The update changed fetching** (DIP records, roll-call scraping, profile resolution). The cached reports predate the fix, so re-fetch with 4b.

Otherwise the offline rebuild is enough.

#### Re-persist the cached reports

```bash
python3 scripts/build_dip_pulse_site.py --offline --repersist --output-dir .context/dip-pulse-site
```

`--repersist` (only with `--offline`) persists every cached `plenarprotokoll-*.json` into a uniquely staged database. It preserves the person registry independently of roster preservation, keeps roster attributes without inherited speaker IDs, carries previous facts for comparison, reconciles people, recomputes facts and checks integrity before replacement. Then it renders as usual. A nonblocking writer lock protects the rebuild; missing evidence for an existing protocol aborts. The new database replaces the old one only when every stage succeeds:

- an unreadable or malformed cached report, or a report that fails to persist, prints one `ERROR [repersist]:` line naming the file, exits 1, and leaves the previous database byte for byte as it was (it is opened read-only, so an older schema is not migrated either);
- when the rebuilt content equals the current database apart from timestamps, the existing file is kept and the run says so, so running it twice changes nothing.

Counting rule version 2 adds nested Zwischenfragen and explicitly typed written submissions (`zu_protokoll`) as separate Beiträge. Neither enters Rede totals, shares or term series. Dossiers show their text, source links and containing contribution; person pages show their separate counts and links. Unassigned written submissions remain visible at sitting level. Historical printed speaker roles, `T_ohne_NaS` headings and uppercase question paragraphs are supported; unresolved question-format turns stop source acceptance.

Rule version 3 rejected unproven nested turns instead of counting them as Zwischenfragen, excluded retrospective thanks from Kurzintervention grants, and associated written submissions with their local annex TOP references. Replay also rejects null agenda-item lists before replacing the store. Rule version 4 adds explicit grant and acknowledgement evidence for nested turns, carries grant evidence across chair interruptions and same-speaker resumptions, limits named group grants to those speakers, and does not treat explicit refusals as grants.

Each persisted protocol records its actual input rule version in `speech_rule_inputs`. Facts, export and store-consuming offline/`--no-persist` rendering refuse missing/stale versions before writing output. Fresh report JSON cannot certify an old database. Repair with the command above; missing XML requires `--fetch-xml` first. Replay validates the XML/report SHA when present and proves one-to-one TOP associations before updating DIP/vote enrichment. A changed or ambiguous source set requires reacquiring the whole sitting report. Detailed DIP kind differences are retained in `data/a1-classification-diagnostics.json`; one build warning points to that file. See [A1 source and scratch validation](docs/plans/a1-validation.md).

Schema 3 / export format 2 uses stable text row IDs and issued person URLs. See the [key dictionary, correction format and backup requirements](docs/stable-ids.md). Back up the build store with all cached evidence: the registry retains issued keys, aliases and historical occurrence bindings that cannot be reconstructed from current reports alone.

It applies what is derived when persisting, and re-reads the Reden and Beiträge of every report from its cached Plenarprotokoll XML (`data/xml/plenarprotokoll-<sitting>.xml`, written by every online update since A1), so a change to what counts as a Rede needs no re-fetch. A store built before A1 has no cached XML: run `python3 scripts/build_dip_pulse_site.py --fetch-xml --output-dir .context/dip-pulse-site` once (public bundestag.de files, no API key, about 0.3 s per sitting), then `--offline --repersist`. A report from before A1 with no cached XML stops the re-persist with the store untouched, so old Reden counts never sit next to new ones; a report whose XML cannot be fetched (no `xml_url`) has to be deleted from `data/` (an online update re-fetches it). It does not re-resolve profiles or re-fetch anything else; those need an online update (4b). To prove what a correction moved, compare against a copy of the directory made beforehand (`scripts/compare_store_values.py`, see "Validate a data correction").

#### Validate a data correction

A change that moves a stored value (a parsing rule, a derivation, an identity rule) is checked against the store before it is trusted: keep a copy of the store from before the change, apply the change to another copy, and let `scripts/compare_store_values.py` print what moved.

```bash
# 1. The baseline: a copy of the whole output directory, made before the change
cp -cR .context/dip-pulse-site .context/baseline          # clone copy; use cp -R elsewhere

# 2. Apply the change to a second copy, by the route it needs (4c)
cp -cR .context/baseline .context/after
#    derived from the cached reports (Mehrheitsvotum, Zusammenschluss, Sprechrolle, ...), or from the cached
#    Plenarprotokoll XML (what counts as a Rede, Redner parsing; run `--fetch-xml` first if data/xml/ is empty):
python3 scripts/build_dip_pulse_site.py --offline --repersist --output-dir .context/after
#    needs a fresh DIP or profile lookup (match kinds, abgeordnetenwatch profiles): an online run into
#    the copy, e.g. `--document-number 21/84`, or `--backfill-incomplete` (see "Try a fetch or a backfill in a
#    scratch directory"). To re-fetch every cached sitting, name each one (about 30 s per sitting without votes,
#    so 2 to 3 hours for 300 sittings; `--no-votes` keeps the votes already cached):
python3 scripts/build_dip_pulse_site.py --output-dir .context/after --no-votes \
  $(ls .context/after/data/plenarprotokoll-2*-*.json | sed -E 's#.*plenarprotokoll-([0-9]+)-([0-9]+)\.json#--document-number \1/\2#')

# 3. Compare, old first
python3 scripts/compare_store_values.py .context/baseline .context/after                 # the fixed cohort (default)
python3 scripts/compare_store_values.py .context/baseline .context/after --cohort all    # whole-store coverage
```

Both arguments are output directories (the store plus the generated pages). The script only reads, and exits 0 once it compared, 2 for a directory that is not an output directory. It prints old, new and the delta for the row counts, `parties` (mps rows, MdB, Reden naming each name; a name that appears or disappears is listed), the Mehrheitsvotum distribution, votes and their newest date, the characters of all Reden (with the largest per-protocol moves and the characters no speaker could be found for), the Beiträge per kind (`contributions`), the Redeanteil per Zusammenschluss and Sprechrolle, the Reden that fall back to the speaker's party, the Zusammenführung (records, merges per provenance, name buckets left split), the `r3-abweichler` recipe, the generated pages, and the stored facts: publishable weeks and months, every period that stopped being complete with its reason, and every changed winner with the identity of the winning speech or vote.

- **Fixed cohort** (default) compares what is parsed from a protocol on the protocols both stores hold, so a sitting an online run acquired does not blur a value fix. **`--cohort all`** shows what a rebuild added or lost. Row counts, parties, pages and facts are always whole-store, and say so in their heading.
- A quantity with no evidence in a store (an older schema without the column, a page directory that was not built, no MdB roster) prints `unavailable`, never 0. A one-sided quantity shows the other side's figures against `unavailable`.
- Quote the output in the commit that changes the value, with one or two examples a reader can check at the source: the protocol, the Rede id or vote id, the page. Say which part the change fixes and which it only measures.

Tests for the script are in `tests/test_compare_store_values.py`; `scripts/compare_store_values.py --help` lists the options.

Hard reset, when the cache itself is suspect:

```bash
scripts/preview_dip_pulse_site.sh stop
rm -rf .context/dip-pulse-site
scripts/preview_dip_pulse_site.sh update --limit 5 --detail-limit 2
```

## 5. Public presentation and operator controls

Every ordinary build publishes the same public destinations and source-backed sections. Missing optional data is explained contextually as not requested, complete with no match, partial, or unavailable. `sources.html#datenstand` shows aggregate state and acquisition time. The old `settings.html` URL remains as an explanatory compatibility page during `0.5.x`; old `bundestag-pulse-features` browser data is inert.

In sitting dossiers, names in roll-call member lists link to the matching Personenseite when the identity is unambiguous. Otherwise the row keeps its Bundestag profile link, or shows a plain name when no profile is available.

AI summaries are visible when a usable, structurally validated summary exists. The exact label is `KI-generiert · nicht redaktionell geprüft`. Visitors can expand or collapse all summaries with one control; that single preference uses `bundestag-pulse-ai-summaries-v1`. Structural citation validation proves that cited targets resolve, not that every claim is factually supported or balanced.

Operators control only optional acquisition work. List those controls and their effective provenance without network or build work with:

```bash
python3 scripts/build_dip_pulse_site.py --list-capabilities
python3 scripts/build_dip_pulse_site.py --explain-config
```

| Enrichment | Network work |
|---|---|
| `votes` | Refresh roll-call totals, fraction results, individual votes, the Angenommen/Abgelehnt outcome, and the XLSX Namensliste link from bundestag.de. **On by default** for every online update. |
| `aw-profiles` | Resolve public abgeordnetenwatch.de profile links |
| `mp-roster` | Refresh the complete MdB roster from DIP |

On `puls.html` the week radar ([docs/designs/puls-wochenradar.md](docs/designs/puls-wochenradar.md)) gates three blocks this way: the "namentlich abgestimmt" badge on a radar row and the "Namentliche Abstimmungen" card in the Wochenvergleich band (`votes`), and the KI-Zusammenfassung with its receipts under a radar row (`summaries`). All of them render into every build and are hidden by the visitor's setting, so the page reads correctly either way.

The ordinary offline preview needs no feature arguments:

```bash
scripts/preview_dip_pulse_site.sh
```

An online update acquires roll-call votes by default: a sitting fetched without them is recorded as `not_requested`, and the newest votes never reach the store. Use `--enrich` for the enrichments that are not on by default. It is repeatable and accepts `votes`, `aw-profiles`, `mp-roster`, or `all`:

```bash
scripts/preview_dip_pulse_site.sh update --enrich aw-profiles
scripts/preview_dip_pulse_site.sh update --enrich all --summary-mode auto
scripts/preview_dip_pulse_site.sh update --no-votes     # skip the roll-call scan this time
```

The vote scan reads the Bundestag's roll-call list newest first, at most `--vote-scan-pages` pages (default 30) per sitting; one build shares the pages between its sittings. A sitting's votes are recorded `complete` only when the scan passed the sitting's date or reached the end of the list. When it used every page without doing either, the sitting is `partial` (or `failed` if no vote was found) with the reason `scan_budget_exhausted`, and the build prints `raise --vote-scan-pages`. A scan's result replaces the cached votes of that sitting; nothing is merged from the cache. A scan that fails for a network or server reason (`source_unavailable`, `source_changed`) while the cache holds votes for the sitting is treated like any failed dossier refresh: the whole cached dossier stays untouched and the build logs it. Without cached votes the failed scan stands and the sitting's votes are `failed`. A fetched roll-call vote stays attached to its sitting even when it cannot be assigned to one unique agenda item; it appears under “TOP nicht zugeordnet” and does not make the acquisition incomplete. Votes count as verified only when the report also records how the scan ended (`validation_summary.roll_call_scan_end` is `date_passed` or `list_end`); a stamp from an older build has no such evidence and is re-acquired by the backfill.

**Precedence.** Sources speak in this order, later ones winning: the built-in default (`votes`), `features.json`, `features.local.json`, `--features-file`, `BUNDESTAG_PULSE_ENRICHMENTS`, then `--enrich` and `--vote-scan-pages N` (N > 0, which selects votes). A config file's `enrich` list replaces the set built up by earlier config layers but never removes the default, so a `features.local.json` that lists only `aw-profiles` still acquires votes. Only a veto switches a default off: `--no-votes` (which beats everything, including `--enrich votes` on the same command line), `--vote-scan-pages 0`, a `-votes` entry in an `enrich` list or in `BUNDESTAG_PULSE_ENRICHMENTS`, or the legacy `disable` key. `--explain-config` prints the effective set with the source of each entry and this precedence line.

Without `--summary-mode auto` the default `reuse` carries existing summaries forward and makes no LLM request. Generating summaries needs `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` and may incur provider cost. `--enrich all` deliberately does not imply summary generation.

An update that omits an enrichment reuses already cached votes, profile links, summaries, and roster rows. Only an explicitly requested enrichment refreshes that source.

For durable operator defaults, use the gitignored `features.local.json` next to `features.json`:

```json
{ "enrich": ["aw-profiles", "-votes"] }
```

`BUNDESTAG_PULSE_ENRICHMENTS=aw-profiles,-votes` is the environment-variable equivalent. The example adds profile links and vetoes the vote scan; drop `-votes` to keep the default. The old `--features`, `--enable`, `--disable`, `--list-features`, and `BUNDESTAG_PULSE_FEATURES` inputs remain accepted with a warning throughout `0.5.x`; they no longer remove published UI and are scheduled for removal in `0.6.0`.

Developer payloads are separate from presentation and enrichment. Use `--include-dev-view` only with a dedicated output directory such as `.context/dip-pulse-site-dev`; the builder rejects attempts to mix it into the ordinary public output.

## 6. Server settings

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `$CONDUCTOR_PORT` or `8000` | HTTP port |
| `PREVIEW_BIND` | `127.0.0.1` | Bind host; set `0.0.0.0` to expose on the LAN deliberately |
| `OPEN_BROWSER` | `1` | Set `0` to not open a browser on start |
| `DIP_PULSE_OUTPUT_DIR` | `.context/dip-pulse-site` | Static output directory |
| `DIP_PULSE_PID_FILE` | `.context/dip-pulse-server.pid` | Background server PID |
| `DIP_PULSE_LOG_FILE` | `.context/dip-pulse-server.log` | Server log |

```bash
PORT=9000 OPEN_BROWSER=0 scripts/preview_dip_pulse_site.sh
```

`--today`, `SOURCE_DATE_EPOCH`, and `--week` pin the build clock and sitting week for `puls.html` and the homepage's weekly entry. The selected week on the homepage now matches `puls.html`; the weekly page uses the date to label a running week, state the age of an older week ("Letzte Sitzungswoche vor 13 Wochen"), and print the "Auswertung vom" date. Pin them so two builds of the same cache are byte-identical:

| Input | Effect |
|---|---|
| `--today YYYY-MM-DD` | Build date: decides running vs. past week; `puls.html` prints it as "Auswertung vom" |
| `SOURCE_DATE_EPOCH` | Fallback when `--today` is absent: an integer Unix timestamp, read as UTC (a CI build with a pinned epoch shows that UTC date) |
| neither | The current date at build time |
| `--week YYYY-WW` | The ISO sitting week shown by `puls.html` and the homepage; without it, the newest dated week. A week the build cannot hold is refused before any file is written (offline: no cached dossier; online: none of the dossiers this run builds, per `--detail-limit`/`--dossier-document-number`, or keeps: every cached dossier stays) and the message lists the available weeks. Online, if every dossier of that week then fails to build, the build stops after the dossiers, before `puls.html` |

```bash
python3 scripts/build_dip_pulse_site.py --offline --today 2026-09-15 --week 2026-24
```

Stop the server before changing `PORT`, `PREVIEW_BIND`, or `DIP_PULSE_OUTPUT_DIR`. The script only checks whether *a* server is alive, not which port or directory it serves, so changing these while it runs rebuilds the files, leaves the old server in place, and prints the new URL even though nothing is listening there.

## 7. Hosting the generated site elsewhere

`.context/dip-pulse-site/` is self-contained static output. Every internal link is relative (only citations to bundestag.de and abgeordnetenwatch.de are absolute), so it can be copied to any static host, including a subdirectory:

```bash
python3 scripts/build_dip_pulse_site.py
rsync -a .context/dip-pulse-site/ user@host:/var/www/bundestag-puls/
```

Calling the builder directly instead of the preview script keeps the deploy build from starting a local server.

Note that `data/` ships alongside the pages and contains the cached DIP JSON and the SQLite store — that is intentional (the database explorer and dev views read them), but it means the whole cache becomes public.

## 8. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `error: DIP_API_KEY is not set.` | Online mode without a key. Put it in `.env.local`. A `DIP_API_KEY=... scripts/preview_dip_pulse_site.sh update ...` prefix only works when `.env.local` does not define the key at all — an empty `DIP_API_KEY=` line overwrites it (§2). |
| `error: No cached protocols found in .context/dip-pulse-site/data.` | Offline build on an empty cache. Run one online update first (§2). |
| Weeks or months read `unvollständig erfasst` and no Fakt is posted | Their sittings are missing or not fully acquired. The build prints which, and the command that fixes it: see "Backfill incomplete sittings" in §4b. |
| Port already in use | `PORT=9000 scripts/preview_dip_pulse_site.sh` |
| Votes or profile links are unavailable | Check `sources.html#datenstand` for whether acquisition was skipped, partial, or failed. Votes are acquired by default, so `not_requested` means `--no-votes`, `--vote-scan-pages 0` or a `-votes` config entry was in effect: run an online update without it. `partial` or `failed` with `scan_budget_exhausted` means the roll-call scan ran out of pages before reaching the sitting's date: raise `--vote-scan-pages`. Profile links need `--enrich aw-profiles` (§5). |
| `warning:` about roll-call votes | The Bundestag list markup or filterlist id changed. Pass `--roll-call-list-id NEW-ID` or set `BT_ROLL_CALL_LIST_ID`. |
| `warning:` about the Namenslisten page | "0 rows" means the id rotated or the markup drifted — set `BT_NAMENSLISTEN_LIST_ID` (no CLI flag exists for it). "returned N rows (the request limit)" is informational, not fixable by that variable: the page's window is a fixed 200 rows, so an older vote gets no link this build, but keeps one a previous build already found. The outcome badge is unaffected either way. |
| abgeordnetenwatch 429s / timeouts | The resolver throttles and retries; the update continues without profile links. Omit `--enrich aw-profiles` for debug runs. |
| `ERROR [sprechrolle]: N speaker role(s) map to no Sprechrolle: …` | A speaker's `<rolle_lang>` in a cached protocol is one no rule in `SPRECHROLLE_RULES` maps. The message lists every such role with the protocol and Rede id; the store is left as it was. Add each role to the rules, see [Sprechrolle rules](#sprechrolle-rules), then re-run. |
| `Missing/stale persisted speech rules` | The store contains missing or old per-protocol rule versions. Facts, export and store-consuming rendering stop before writes; repair with `--fetch-xml` if needed, then `--offline --repersist`. Current report JSON alone does not repair the store. |
| `warning: N of M cached reports predate the current speech-counting rule …` | These reports use an older speech-counting rule, so Reden counts, Redeanteil and facts may mix rule versions. The warning appears when persisting nothing (`--offline` without `--repersist`, `--no-persist`). Re-read cached XML with `--offline --repersist` (§4c); if a report has no cached XML, run `build_dip_pulse_site.py --fetch-xml` first. |
| `ERROR [repersist]` or `ERROR [persist]: N cached reports predate the current speech-counting rule and have no cached XML …` | A store-writing build refuses reports with older counting rules when their XML is unavailable, and names them; the store is left untouched. Run `--fetch-xml`, then `--offline --repersist`. A named report whose XML cannot be fetched (no `xml_url`) has to be deleted from `data/`. |
| `ERROR [repersist]: … is not the Plenarprotokoll XML of …` | A file in `data/xml/` is not the protocol of its sitting (a maintenance page, another sitting, no agenda items). The store is left untouched. Delete the named file and run `--fetch-xml` again. |
| Builds feel slow | Narrow with `--document-number`, lower `--detail-limit`, and request only the enrichments you need. |
| `error: --week 2030-01 ist nicht im Archiv` | The requested week has no cached dossier; the message lists the weeks that do (§6). |
| `warning: [puls] N Sitzungen ohne Datum ausgeschlossen (21/82, …)` | Those cached dossiers carry no `datum`, so they cannot be placed in a sitting week; the radar renders from the dated ones and the page header notes the count. Re-fetch the named sittings with `update --document-number …`. With no dated sitting at all the page shows only "Die erzeugten Sitzungen tragen kein Datum". |
| Radar shows no rows (`warning: [puls] KW …: keine Reden extrahiert`) | Every agenda item of that week has zero extracted speeches, so there is nothing to rank; the page says so in one note. Usually the XML speeches were not fetched or the extraction was empty — re-run `update --document-number …` for the week's sittings and check the dossier's validation warnings. |

### Sprechrolle rules

A Rede in a Sprechrolle ([CONTEXT.md](CONTEXT.md); `<rolle>` in the protocol XML) counts for one of three sides and for no Fraktion or Gruppe (ADR 0001): `bundesregierung`, `bundesrat` or `weitere`. The side is stored per speech in `speeches.sprechrolle`, derived when persisting and when rendering from the speaker's `<rolle_lang>` by `SPRECHROLLE_RULES` in `scripts/derive.py`: an ordered list of `(pattern that must match the whole role text, side)` where the first match wins.

- A role that names a Land in brackets ("Ministerpräsident (Bayern)", "Staatsminister (Hessen)") is the Bundesrat.
- The Bundeskanzler, Bundesminister, Parlamentarische Staatssekretäre, Staatsminister beim Bund, Beauftragte and Koordinatoren der Bundesregierung are the Bundesregierung.
- The Wehrbeauftragte des Deutschen Bundestages and the Polizeibeauftragte des Bundes are `weitere`.

A role no rule maps stops the persist step (`ERROR [sprechrolle]`), so a new title never lands in a Fraktion's numbers unnoticed. To fix it, add a line to `SPRECHROLLE_RULES` with the side it belongs to, then apply it to the cached reports with `--offline --repersist` (§4c). `tests/test_sprechrolle.py` lists every role the cached reports contained when it was written; add the new one there as well.

## 9. More documentation

- [docs/project-documentation.md](docs/project-documentation.md) — full command, flag, and environment reference, pipeline internals, SQLite schema.
- [A1 source and scratch validation](docs/plans/a1-validation.md), [A1/A2 coordination contract](docs/plans/a1-a2-contract.md), and [ADR 0002](docs/adr/0002-kurzinterventionen-are-not-reden.md) — source coverage, persistence/replay boundaries, and the Rede/Beitrag counting decision.
- [docs/design/bundestag-pulse-design.md](docs/design/bundestag-pulse-design.md) — product and design rationale.
- [docs/designs/](docs/designs/) — per-feature design docs from review sessions, e.g. [puls-wochenradar.md](docs/designs/puls-wochenradar.md) for the `puls.html` week radar or [fakt-der-woche.md](docs/designs/fakt-der-woche.md) for the `fakt/` pages.
- [docs/data-license.md](docs/data-license.md) — long-form licence/provenance notes for the published data, including which SQLite columns are DIP-sourced vs. derived.
- [CHANGELOG.md](CHANGELOG.md) — release history. [TODOS.md](TODOS.md) — tracked follow-up work.
