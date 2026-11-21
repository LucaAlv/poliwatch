# Release readiness: public repo, release review, comparison, four false sentences

Plan, 2026-11-14, against main v0.41.0.0 (0e6def4). Nothing was implemented when it was written; the "Holds?" column below is as of 0e6def4, and PR A has since done items 1 and 4. It covers four TODOS.md entries of stage 1:

1. "Public repository: follow-ups" (P1)
2. "Main and stable releases" (P1 for the checklist and the policy)
3. "Comparison and joinable ids in DATA.md" (P1, decision N4)
4. "Fresh-store record and E8: four sentences that say something false", items 1–3

The rename to open-parlament is out of scope; it waits until the parallel work lands. Two planning sessions run beside this one: withheld-Reden hardening (`facts.py`, `release_changes.py`, reviewed digests) and vote links (`match_roll_call_votes`, the vote outcome in `derive.py`, and one DATA.md sentence on what a link means). This plan keeps its DATA.md text in a section of its own, and its only code outside new files is a refusal in `scripts/publish_dip_pulse_data.py`.

Measurements below are read-only, on the reference store `.context/dip-pulse-site` in the main checkout (replayed on v0.41.0.0, 2026-11-14) and on the W1 XML of the excluded sittings in `~/agent-runs/w1/xml`.

## What still holds on main

| TODO statement | Holds? | Evidence |
|---|---|---|
| `SECURITY.md` says the repo is not public (lines 3 and 8) | Yes | Line 3: "bis dahin ist das Repository nicht öffentlich". Line 8: "Private reporting opens with the public release; until then the repository is not public." |
| The repo is public | Yes | `gh repo view`: `visibility: PUBLIC` |
| Private vulnerability reporting is on | Yes | `gh api repos/LucaAlv/poliwatch/private-vulnerability-reporting`: `{"enabled":true}` |
| `CITATION.cff` has no `repository-code` or `url` | Yes | The file has neither. **Not in the TODO:** `tests/test_citation_file.py:38` asserts `repository-code` is absent, so the test must change with the file. |
| No written review checklist, no CPP-BT comparison script | Yes | Nothing under `scripts/` or `tests/` names CPP-BT except a note in `person_corrections.json`. |
| `CLAUDE.md` still has the pre-release section | Yes | `CLAUDE.md:1`. Two code comments cite it: `tests/test_daten_page.py:206` and `tests/test_sitzungskalender.py:431`. |
| DATA.md has no comparison table or join notes | Yes | DATA.md is generated: header, coverage, withheld, tables, then `docs/data-methods.md` embedded, recipes, sources. `docs/data-methods.md` names no other dataset. |
| Fresh-store item 1: `listed_party_id IS NOT party_id` selects every row | Yes | `vote_members`: 425,322 rows, `listed_party_id` NULL on 425,222; `IS NOT` gives 425,322; `IS NOT NULL AND !=` gives 100 rows in 55 votes. |
| Fresh-store item 2: "beside 990, whose box gave the right word" | Yes | `docs/plans/a3-phase4.md:534`. E6 says 990's box gave the wrong word. `result_scope = 'application'` is still 34. |
| Fresh-store item 3: E8's base | Yes, and one more error | See item 4 below: the 84 excluded sittings include 20/11, which is WP 20. |
| Fresh-store item 4 | Done by #151 | |

One more finding the TODOs do not name: **GitHub secret scanning and push protection are both off** (`security_and_analysis`: `secret_scanning` and `secret_scanning_push_protection` disabled). Both are free for a public repository.

## Item 1. Public repository: follow-ups

### 1a. `SECURITY.md`

- Line 3 (German): drop the sentence "Diese steht mit der öffentlichen Veröffentlichung des Repositorys zur Verfügung; bis dahin ist das Repository nicht öffentlich." The rest of the paragraph stays.
- Line 8: delete the bullet. The bullet above it already says to use GitHub's private reporting, and it works today.
- `tests/test_issue_forms.py:113` keeps checking `SECURITY.md` for placeholder markers; no test change.

### 1b. `CITATION.cff`

**Recommendation: add `repository-code` now, and leave `url` until the site has a host.** CFF's `url` is the landing page of the work. Today that would be the repository again, which adds nothing, and a placeholder URL would be copied into citations. GitHub redirects the old URL after the rename, and the rename PR updates the line.

```yaml
repository-code: "https://github.com/LucaAlv/poliwatch"
```

Test: in `test_content_matches_what_is_decided`, take `repository-code` out of the forbidden keys and assert the line above. `doi`, `version`, `date-released` and `identifiers` stay forbidden until the Zenodo item. `docs/data-methods.md:108` says `CITATION.cff` names neither a DOI nor a version, which stays true.

If the owner wants `url` now anyway, the only honest value is the releases page (`https://github.com/LucaAlv/poliwatch/releases`), which is empty until the first `--publish`.

### 1c. Full-history secret scan

**Read-only pass run now (2026-11-14).** No secret was found. No gitleaks or trufflehog is installed, and installing one is a download, so this pass used regular expressions over `git log --all -p` in the main checkout: 45 refs (local and remote-tracking), 400 commits, 137 MB of patch text.
- **Provider-shaped keys** (Anthropic `sk-ant-`, OpenAI `sk-`, AWS access key IDs, GitHub `ghp_`/`github_pat_`, Slack `xox`, Google `AIza`, GitLab `glpat-`, PEM private keys): every hit is a test fixture inside `.claude/skills/gstack/`. The initial commit `e5f86e1` (2026-06-15) vendored gstack, 1,161 files, and `9ef407f` (2026-08-25) removed it. Examples: an AWS-shaped placeholder in `redact-engine.test.ts`, `sk-ant-your-key-here` in `.env.example`. gstack is MIT-licensed and its `LICENSE` is in the same commit, so the history may carry it.
- **Outside that path** (28.8 MB of patch): no assignment of a key, token, secret or password to a literal. `DIP_API_KEY` appears only as `os.environ.get(...)` reads and the placeholder `DIP_API_KEY=your-key-here`. No string shaped like a DIP key (`xxxxxxx.` + 30–44 characters). No `apikey=` in a URL.
- **E-mail addresses outside that path:** `parlamentsdokumentation@bundestag.de`, `example.org` and `*.test` addresses, test URLs with userinfo (`secret@www.bundestag.de`), and `luca@poliwatch.local` (an SSH line in `docs/pi.md`).
- **Not covered:** this pass is pattern-based, not entropy-based. It also misses commits that exist only on GitHub's `refs/pull/*/head`. These stay fetchable after a PR branch is deleted.

**Planned full scan (owner approves the install):** gitleaks, one offline binary under the MIT licence.

```bash
brew install gitleaks
```

Run it in a scratch mirror. A mirror clone of a GitHub repository fetches `refs/pull/*` too, so commits from deleted PR branches are included:

```bash
git clone --mirror https://github.com/LucaAlv/poliwatch.git "$SCRATCH/poliwatch-mirror.git"
```

```bash
gitleaks git --log-opts="--all" --redact --report-format json --report-path "$SCRATCH/gitleaks.json" "$SCRATCH/poliwatch-mirror.git"
```

(`gitleaks git` is v8.19+; older versions use `gitleaks detect --source <dir> --log-opts=--all`. If it refuses a bare repository, use a plain clone and `git fetch origin '+refs/pull/*/head:refs/remotes/pull/*'`.) Expect the gstack fixtures to show up. Triage them by path (`^\.claude/skills/gstack/`, commit `e5f86e1` only) and do not suppress them with a committed allowlist. Any hit outside that path gets read by hand. The scan is one-time and nothing is committed except a one-line result in TODOS.md Completed.

**Owner step, same day:** turn on secret scanning and push protection (Settings → Code security). GitHub then scans the full history for provider keys and blocks new ones at push, so the local scan never has to be repeated.

**On a hit:**
1. Treat the key as leaked. The repo is public, and forks, clones and GitHub's PR refs keep old commits. Revoke or rotate it at the provider first: a new DIP key from the DIP key request, a new LLM key in the provider console. The owner does this.
2. Check the provider's usage log for the time since the commit.
3. Do not rewrite history for a rotated key. A rewrite changes every SHA after it, while CHANGELOG, plans and release revisions cite commits, and it does not remove the key from forks or caches. Rewrite (`git filter-repo`, then GitHub Support to purge cached views and PR refs) only for content that does harm in itself, such as a private person's personal data.
4. Record what leaked, when, and that it was rotated in TODOS.md Completed, never the value.

### 1d. Pass over docs and plans for anything that should not be public

Method: pattern pass over the whole tree on `origin/main` (6.4 MB of docs, 4.4 MB of fixtures). It looked for credentials, personal data (addresses, phone numbers, e-mails, family), absolute home paths, internal hosts and IPs, third-party data of open licence, vendored code and large binaries. It is not a line-by-line read of the 90 files in `docs/plans/`.

| Finding | Where | Recommendation |
|---|---|---|
| The owner's personal e-mail address is the author and committer on 225 commits. 153 use the GitHub noreply address, 22 are Anthropic's noreply. | Commit metadata, all refs | **Owner decision.** Recommended: leave the history (a rewrite breaks every cited SHA, see 1c.3). Set this repo's `user.email` to the noreply address, and turn on GitHub's "Block command line pushes that expose my email". |
| Roll-call data from bundestag.de in the public tree: `tests/fixtures/roll_call_detail_{869,996,beschluss}.html`, `member_votes.html`, `namenslisten_list.html`, `roll_call_1002.json`, and named Stimmen in `docs/plans/e4-refiled-votes-old-new.tsv` | Tree and history | No removal. Removing them from HEAD leaves them in history, and the pages are public on bundestag.de. Add one sentence to the owner's roll-call e-mail ("Settle the roll-call source for redistribution") asking whether test excerpts in a public code repository are covered. |
| Absolute home paths | `tests/test_presidium_kinds.py:699`, `docs/plans/coverage-gate-w1-w2.md:180`, `docs/plans/withholding-preflight/preflight.json` | No action. They reveal only the username, which the GitHub handle and ADR 0003 already make public. Changing the test path would make it skip in every worktree. |
| A home network host and private IP | `docs/pi.md` (`poliwatch.local`, `192.168.178.42`) | No action. It is an RFC 1918 address and reachable only from that LAN. |
| The operator named as a private person | `docs/adr/0003-licences-and-impressum.md:80` | Intended: the Impressum needs it. No home address is in the repo; ADR 0003 question 1 keeps that open. |
| Vendored gstack in `e5f86e1` (28.8 MB fixture JSON among it) | History only | No action. It is MIT with its licence file, and size is no publication issue. |

Nothing else was found: no drafts of the owner's e-mails, no private correspondence, no third-party corpus files (the CPP-BT zip was never committed, as the research note says).

## Item 2. Main and stable releases

### 2a. Where the checklist lives

- `docs/release-review.md`: the checklist, written for the owner, in English like the other docs.
- `docs/release-reviews/<version>.md`: one record per reviewed release, holding what was run, the outputs' digests, each finding, and the verdict. It is committed, so a reader can see what "stable" meant for that version.
- `scripts/compare_cpp_bt.py`: the comparison. It is standard library only and imports no project module (a test checks its imports). It reads only the export's SQLite, the source XML and CPP-BT's file. It is never called by the build, the release script or CI.

The stable marker is an annotated tag `stable-<version>` on the same commit as `data-<version>`, plus the review record. GitHub releases stay as the release script made them, because the script treats them as immutable. The Zenodo DOI goes on stable releases only (TODOS "A DOI per release", decided).

### 2b. Draft of `docs/release-review.md`

> # Release review checklist
>
> A main release becomes stable when the owner has run every step below on it and the record `docs/release-reviews/<version>.md` says "stable". About every three months (decision Q3). The first release is reviewed in full and is the first stable.
>
> **Inputs.** The candidate's release directory (`data-<version>/`, checked with `shasum -a 256 -c SHA256SUMS`). The last stable's release directory (none for the first). The source XML of the candidate's sittings (`data/xml/` of the store the release came from). CPP-BT's newest speech metadata from Zenodo (`CPP-BT_<date>_DE_CSV_Reden_Metadaten.zip`; download with the owner's approval and record its version and SHA-256).
>
> **1. Coverage per year.** From the candidate's DATA.md, "Abdeckung nach Jahr und zurückgehaltene Reden" and "Ausgeschlossene Sitzungen":
> - every exclusion reads `source_defect` or `not_narrowable`; any `awaiting_*` stops the review (the release script refuses it too, once the withheld-before-t4 plan's PR B lands);
> - per year: sittings, Reden stored, Reden withheld, share withheld. Compared with the last stable, explain every year whose sittings fell or whose withheld share rose;
> - per Wahlperiode: our sittings against CPP-BT's (step 4 prints both).
>
> **2. Figures moved since the last stable.** Put each release's SQLite at `<dir>/data/bundestag-pulse.sqlite` and run `scripts/compare_store_values.py LAST CANDIDATE`, once with `--cohort shared` and once with `--cohort all`. Pages read "unavailable", which is expected. Every value that moved in the shared cohort must be named by a correction in some release's `changes.json` between the two, or follow from a rule change the CHANGELOG names. An unexplained move is a bug (see "A bug found in review").
>
> **3. Spot checks against the protocols.** Draw five sittings with a seed written into the record: one per Wahlperiode, plus the newest. In each, check against the protocol PDF:
> - five Reden: Redner, Fraktion, TOP, and the opening and closing sentence;
> - every withheld Rede: its reason, and that the text is the printed one;
> - up to three named votes: the tally against the bundestag.de page, and the linked TOPs.
>
> Also check every sitting that changed its status since the last stable (newly held, newly withheld Reden, released Reden).
>
> **4. Comparison with CPP-BT, per sitting.** `python3 scripts/compare_cpp_bt.py --export <sqlite> --xml-dir <dir> --cpp-bt <zip> --out docs/release-reviews/<version>-cpp-bt.tsv`. The join rules are those of DATA.md, "Verknüpfung mit anderen Korpora". Pass when:
> - no `rede_id` of ours is missing from CPP-BT in a sitting both hold;
> - every id only CPP-BT has is classified (§31, Neudruck, procedural, withheld, excluded sitting, contribution); any `unclassified` is read by hand;
> - surname differs on a shared id only where `scripts/cpp_bt_known_differences.tsv` lists it (spellings and name changes, each with a reason); any other is read by hand;
> - Fraktion differs only where that file lists it (`docs/source-errors.md` C5, C6);
> - word-to-token ratio: a shared Rede over 50 tokens whose ratio differs from its sitting's median by more than 15% is listed; read the 20 largest. The two thresholds are first values, calibrated on the first run and written down here.
>
> CPP-BT is automatic too and does not check deeply. Agreement is no proof both are right; disagreement is a lead.
>
> **5. Claims.** Re-check the "Vergleich" table of DATA.md against each dataset's page when its date is more than six months before the candidate, and update the date. Check that the licence section still names the open roll-call question, or its answer.
>
> **6. Verdict.** Write the record: inputs and their digests, each step's result, findings with their fix release. Then tag `stable-<version>`, and archive the release on Zenodo once that exists.
>
> **A bug found in review.** The candidate is not patched and does not become stable. The fix goes into a new main release. Replay the fix on a copy of the store (README, "Validate a data correction") and check that only the figures it should move moved. That release's `changes.json` names the correction, and steps 2 and 4 run again on the new release, limited to what the fix touches. The new release then becomes stable. Until then the last stable stays the stable one.

### 2c. `scripts/compare_cpp_bt.py`

Method from `docs/research/bundestag-corpora-landscape-2026-11.md`, "Cross-check against CPP-BT", rewritten so it is not throwaway:

- **Inputs:** `--export` (the release's SQLite, or `.sqlite.gz`, read with `mode=ro`), `--xml-dir` (source XML, to classify ids only CPP-BT has by their parent element), `--cpp-bt` (the zip or its CSV), `--out`.
- **One normalisation function** for each key (review checklist class 4): `sitting_key()` drops " (neu)" and folds `18/100` and CPP-BT's form to one; `source_rede_id()` drops our `:N`; `nested:*` ids and empty ids (Fragestunde) are skipped by name, never by a failed match.
- **Output:** one TSV row per sitting (ours, theirs, both, only ours, only theirs by class, surname differences, Fraktion differences, token-ratio outliers), then one row per difference, then a summary with the inputs' SHA-256. Exit code 0 for "compared", whatever it found. The review reads it; the script never judges.
- **Tests** (`tests/test_compare_cpp_bt.py`) on a synthetic CSV and a three-sitting SQLite: " (neu)", `:N`, `nested:`, an id in `withheld_units`, a §31 annex id, a sitting only one side holds (absent, not zero: review checklist class 5), a surname with a diacritic difference, and a hostile CSV (unbalanced quote, a 1 MB field, a BOM) (classes 8 and 9). Also a test that the script imports only the standard library.
- **First run in the PR:** on the reference store's current export and the 2026-09-19 file whose SHA-256 the research note records. The owner approves the 10.7 MB download. Reproduce the research note's join figures where the stores agree: our 716 then, 718 now. A difference is explained in the PR, not tuned away.
- `scripts/cpp_bt_known_differences.tsv`: starts from the 185 surname differences the note classified (Dağdelen/Dagdelen, Kemmer/Schmitt, …) and the two Fraktion cases, each with its reason.

### 2d. Draft stability policy (replaces `CLAUDE.md`, "Project stage: pre-release")

> ## Project stage: released data, pre-release site
>
> Data releases (`data-<YYYY.MM.DD>`) are published and cited. The site is not public yet. Code, pages and the site's URLs still change in place, with no compatibility shims. What a release says about the data is fixed:
>
> - **A release never changes.** No release, file or tag is edited or replaced. A fix ships in the next main release.
> - **Every moved published figure is recorded.** When a change moves a value that any release has published, the next release's `changes.json` names it: table, stable key, column, old value, new value, reason. The commit still reports old and new values (README, "Validate a data correction").
> - **Ids keep their meaning.** Stable keys follow `docs/stable-ids.md`: never reused, and a retired person key stays as an alias. A change to `key_version`, the schema or the export format is allowed only in a release whose `schema_changes` describes it; the release script refuses otherwise.
> - **Withheld Reden are listed.** A release lists every Rede it newly withholds or releases. More than two newly withheld Reden need the owner's confirmation (ADR 0005).
> - **Stable releases** are main releases the owner reviewed with `docs/release-review.md`. A bug found in review is fixed in a new main release, which then becomes stable.
> - **Accuracy first.** A change that makes a figure more correct goes in, however much it moves. Stability means it is recorded, not that it is avoided.
>
> When the site goes public, a second paragraph covers page URLs and the Daten page.

**When to switch.** Not before the first release: until then nothing is published, and the pre-release rule is the true one. Merge the replacement in the first PR after the first successful `--publish`, on the same day. In that PR, re-read the two test comments that cite the pre-release rule (`tests/test_daten_page.py:206`, `tests/test_sitzungskalender.py:431`) and `PRODUCT.md:90`. Adjust "Review findings: fix now or defer": a correctness defect in a published release becomes a correction in the next main release.

### 2e. What the first release needs, and what waits for the site

| Needed for the first release (stage 1) | Waits for the site (stage 2) |
|---|---|
| `docs/release-review.md` and `scripts/compare_cpp_bt.py` (PR B) | Both downloads (latest main, latest stable) on the Daten page, with why they can differ |
| The full review of the first release, recorded in `docs/release-reviews/<version>.md`, and its `stable-<version>` tag | The last review date on the Daten page |
| The stability policy in `CLAUDE.md` (PR D, right after the first `--publish`) | Each page naming the main release it was built from |
| | The site showing the age of its data |
| | Automatic main releases per Sitzungswoche ("Scheduled data-release workflow"); until then each main release is cut by hand |

## Item 3. Comparison and joinable ids in DATA.md

### 3a. Where the text goes

The DATA.md prose comes from `docs/data-methods.md` (`CODEBOOK_INPUT_FILES["methods"]`, embedded with headings one level down). Add one new section, **"## Vergleich mit anderen Datensätzen und Verknüpfung"**, between "Abdeckung und bekannte Grenzen" and "Quellen, Weitergabe und Zitieren". The vote-links session's sentence on what a link means belongs in "Personen und Abstimmungen" and is not touched here. The Vergleich table's links row points to it rather than repeating it.

### 3b. Placeholders that cannot ship

Figures that wait are written as `PLATZHALTER(<what is missing>)`, the marker `tests/test_issue_forms.py` already refuses in public text. The export only refuses an empty methods file, so the marker would reach DATA.md. **Add one refusal to `scripts/publish_dip_pulse_data.py`:** `--publish` refuses an export whose DATA.md contains `PLATZHALTER`, and the dry run prints the first one. Local builds, tests and the site keep working while the figures wait.
- Review class 1 (sibling paths): the refusal belongs in the release script, the only path that publishes. The site's Daten page links DATA.md but publishes nothing on its own.
- Class 11 (claims): the test asserts the refusal on a fixture export that contains the marker.

### 3c. Draft text (German, for `docs/data-methods.md`)

The cells for the other datasets come from the research note of 2026-11-06. PR C re-reads each dataset's page for every cell on the day it lands and dates the table then.

> ## Vergleich mit anderen Datensätzen und Verknüpfung
>
> Die Datensätze in dieser Tabelle sind unabhängige Projekte. Dieses Projekt ist mit keinem von ihnen verbunden. Die Angaben zu ihnen stammen aus ihrer Dokumentation, gelesen am PLATZHALTER(Datum der Prüfung); „nicht angegeben“ heißt, die gelesenen Seiten sagen es nicht.
>
> | | Dieser Datensatz | CPP-BT | GermaParl | ParlLawSpeech (DE) | BTVote |
> |---|---|---|---|---|---|
> | Abdeckung | WP 18 bis heute; Sitzungen je Wahlperiode in „Gespeicherte Abdeckung je Wahlperiode“ | WP 1–21, Version PLATZHALTER(Version) | offen bis 2023-07-07 (v2.1.0); eine Beta bis 2025-03-18 nur auf Anfrage | 2009–2021 | WP 1–19 |
> | Einheit | Rede; Beiträge nach Art; namentliche Abstimmung und Stimme | Protokoll; Rede ab WP 18 | Sprecherbeitrag, Absatz, Satz; Reden rekonstruiert | Rede | Abstimmung, Abgeordnete |
> | Verknüpfungen | Rede, Tagesordnungspunkt, Drucksache, Vorgang und namentliche Abstimmung über Schlüssel (siehe „Personen und Abstimmungen“) | keine Spalte für Tagesordnungspunkt, Drucksache, Vorgang oder Abstimmung | Tagesordnungspunkt nur im XML, als experimentell bezeichnet | `bill_ID`, `procedure_ID`; Tagesordnungspunkt als Freitext | keine Verknüpfung mit Reden angegeben |
> | Kennungen | `rede_id` und Redner-ID des Bundestages | dieselben `rede_id` und `redner_id` | keine Sprecherkennung | Name | eigene Abgeordnetenkennung |
> | Lizenz | geschichtet, siehe „Quellen, Bedingungen und Transformationen“ | CC0 | CC BY-SA laut Dokumentation, CC BY im Zenodo-Feld | CC BY 4.0 | CC0 |
>
> ### Verknüpfung mit anderen Korpora
>
> - **Rede-ID.** `speeches.rede_id`, `contributions.rede_id` und `withheld_units.rede_id` sind die Kennungen der `<rede>`-Elemente im Plenarprotokoll-XML, wie der Bundestag sie vergibt. Eine Kennung steht in genau einer dieser Tabellen. CPP-BT führt dieselben Kennungen als `rede_id`.
> - **Protokollnummer.** `protocols.document_number` hat die Form `18/100`. CPP-BT hängt an neu gedruckte Protokolle „ (neu)“ an; für den Abgleich entfernen.
> - **`ID…:N`.** Druckt das Protokoll in einer `<rede>` die Rede eines anderen Mitglieds, trennt der Parser sie ab und hängt `:N` an. CPP-BT führt das ganze Element als eine Rede. Für den Abgleich `:N` streichen; die Teile gehören dann zu einer Kennung.
> - **`nested:…`.** Zwischenfragen und eingebettete Befragungsbeiträge, die der Parser aus einer Rede löst, tragen `nested:<rede_id>:<n>`. Das ist keine Kennung des Bundestages; in CPP-BT steht dieser Text in der umgebenden Rede. Nicht über die Kennung verknüpfen.
> - **Fragestunde.** Ihre Fragen und Antworten stehen im XML nicht als `<rede>` und haben keine `rede_id`.
> - **Redner-ID.** `mps.xml_redner_id` ist die Redner-ID des Bundestages. Einige vergibt der Bundestag an mehr als eine Person. Für die geprüften Fälle (`scripts/person_corrections.json`) steht dort die eigene Kennung der gemeinten Person, nicht die gedruckte; CPP-BT führt die gedruckte. Personen deshalb über die `rede_id` verbinden und den Nachnamen vergleichen, nicht über die Redner-ID.
> - **Was CPP-BT als Rede führt und dieser Datensatz nicht:** Erklärungen nach § 31 GO; der Neudruck eines Redebeitrages (19/35, 19/45); als eigene `<rede>` gedruckte Sitzungsleitung, Eidesantworten und Wahlannahmen (ADR 0004); zurückgehaltene Reden (`withheld_units`); Sitzungen, die ganz draußen bleiben („Ausgeschlossene Sitzungen“). Kurzinterventionen, Erwiderungen, Befragungsbeiträge und Ansprachen stehen hier als Beiträge in `contributions`.
> - **Gemessen am PLATZHALTER(Datum) gegen CPP-BT PLATZHALTER(Version):** PLATZHALTER(Satz aus der Ausgabe von `scripts/compare_cpp_bt.py`: Sitzungen beider Seiten je Wahlperiode; ob jede `rede_id` dieses Exports in CPP-BT steht; die Kennungen nur dort, nach Art, davon § 31; abweichende Nachnamen auf gemeinsamen Kennungen).

Every rule above is checked against code before it lands (review class 11):
- one table per id: the query above found 0 overlaps on the reference store, and `withheld_units.rede_id` is documented "Nie zugleich in speeches oder contributions";
- `:N`: `withheld_units.rede_id` meaning, and 13 `speeches.rede_id` with `:` on the store;
- `nested:`: 3,446 `contributions` ids;
- Fragestunde: 18,758 contributions with no `rede_id`, all of kind `fragestunde_*`;
- annex exclusions: `ANNEX_EXCLUSIONS` in `validate_dip_protocol.py`;
- the partitions: `person_corrections.json`, 7 entries today. The text names no count, so it does not go stale.

### 3d. Which figures wait

| Figure | Waits for | Why |
|---|---|---|
| Sittings per WP, ours against CPP-BT's | T4 and the coverage gate | T4 restores 82 of the 85 plus 21/106 |
| "Every `rede_id` of ours is in CPP-BT" | T4 | A claim about the restored sittings too |
| Ids only CPP-BT has, by kind (§31 was 1,666 on the A3 store) | T4, then a fresh CPP-BT | The 85 sittings hold annexes too |
| Surname and Fraktion differences | T4 | Registry figures moved with v0.35 and v0.41 |
| CPP-BT's version and the date checked | The day the section lands, and each stable review | CPP-BT updates several times per Wahlperiode |

Nothing else in the draft carries a figure.

## Item 4. Fresh-store record and E8, items 1–3

All three are wording fixes. No figure moves. Queries were run read-only on 2026-11-14.

**Item 1, `docs/plans/a3-phase4.md:520`.** Replace "where `listed_party_id IS NOT party_id`" with "where `listed_party_id` is set and differs from `party_id` (`listed_party_id IS NOT NULL AND listed_party_id != party_id`)".

```sql
-- on .context/dip-pulse-site/data/bundestag-pulse.sqlite, opened mode=ro
SELECT count(*), sum(listed_party_id IS NULL), sum(listed_party_id IS NOT party_id),
       sum(listed_party_id IS NOT NULL AND listed_party_id != party_id) FROM vote_members;
-- 425322 | 425222 | 425322 | 100
SELECT count(*), count(DISTINCT vote_id) FROM vote_members
 WHERE listed_party_id IS NOT NULL AND listed_party_id != party_id;
-- 100 | 55
```

**Item 2, `docs/plans/a3-phase4.md:534`.** Replace "It is a second such vote beside 990, whose box gave the right word." with "Unlike 990's, 996's box gives the right word." (`docs/source-errors.md` E6: 990's box says "Antrag angenommen" where the Antrag was rejected). `SELECT count(*) FROM votes WHERE result_scope = 'application'` is still 34.

**Item 3, `docs/source-errors.md` E8, "Scale".** Re-checked with an ElementTree count over every `plenarprotokoll-*.xml` in the reference store's `data/xml/` (718) and in `~/agent-runs/w1/xml/` (84; 18/20 was never fetched). It counts `<anlagen-text>` blocks whose `anlagen-typ` contains "entschuldigt", the blocks of those holding a `<rede>`, and blocks with a "Zu Protokoll gegeben" heading (`klasse="Anlage…"`) under an `anlagen-typ` without "zu Protokoll". Run with `uv run --python 3.13 python -I count_annex.py <store>/data/xml ~/agent-runs/w1/xml`:

```python
import collections, glob, os, re, sys
import xml.etree.ElementTree as ET

sittings, ent, with_rede, zp_other = collections.Counter(), collections.Counter(), [], []
for d in sys.argv[1:]:
    for f in sorted(glob.glob(os.path.join(d, "plenarprotokoll-*.xml"))):
        wp, nr = re.search(r"plenarprotokoll-(\d+)-(\d+)\.xml", f).groups()
        sittings[wp] += 1
        for block in ET.parse(f).getroot().iter("anlagen-text"):
            typ = block.get("anlagen-typ") or ""
            heads = ["".join(p.itertext()) for p in block.iter("p") if (p.get("klasse") or "").startswith("Anlage")]
            if "entschuldigt" in typ.lower():
                ent[wp] += 1
                if block.find(".//rede") is not None:
                    with_rede.append(f"{wp}/{nr}")
            if any("Zu Protokoll gegeben" in h for h in heads) and "zu protokoll" not in typ.lower():
                zp_other.append(f"{wp}/{nr}")
print(dict(sittings), dict(ent), sum(ent.values()), with_rede, zp_other)
```

| | WP 18 | WP 19 | WP 20 | WP 21 | All |
|---|---:|---:|---:|---:|---:|
| Sittings: reference store | 194 | 206 | 213 | 105 | 718 |
| Sittings: excluded, W1 XML | 50 | 33 | 1 (20/11) | 0 | 84 |
| "entschuldigt" blocks | 243 | 237 | 214 | 105 | **799** |
| of them holding a `<rede>` | | 19/36 | | | 1 |
| Zu-Protokoll heading under another title | | 19/36 | | | 1 |

So 799 stands, on a different base: 802 sittings of WP 18–21, not WP 18/19, and the 84 are not all WP 18/19 either. New sentence:

> **Scale:** of the 799 annex blocks with an "entschuldigt" title in 802 sittings of WP 18–21 (the 718 of the reference store and 84 excluded sittings: 50 of WP 18, 33 of WP 19 and 20/11), this is the only one holding a `<rede>`, and the only block in the 802 with a Zu-Protokoll heading under another title. Counted 2026-11-14.

Then close items 1–3 in TODOS.md and move the entry to Completed.

## PR split and order

| PR | Content | Kind | Depends on | Review |
|---|---|---|---|---|
| **A** | Item 1: `SECURITY.md`, `CITATION.cff` plus its test, the scan result in TODOS.md. Item 4: the three sentences, TODOS entry closed. | Docs plus one test edit | Nothing. The gitleaks run and the owner's settings come before merge, so the TODOS line can say "scanned, clean" or name the hit. | Small diff: class 11 for every sentence, class 13 on the test. |
| **B** | `docs/release-review.md`, `docs/release-reviews/` (README line only), `scripts/compare_cpp_bt.py`, `scripts/cpp_bt_known_differences.tsv`, tests, and the first run's output in the PR body | Code | Nothing; the owner approves the CPP-BT download | Classes 4, 5, 8, 9, 11, 12; Codex and red team if the diff passes 200 lines |
| **C** | `docs/data-methods.md` section with placeholders; the `PLATZHALTER` refusal in `publish_dip_pulse_data.py` plus a test | Docs plus a small refusal | B, for the join rules the script proves. Rebase over the vote-links PR if it lands first: same file, other section. The withheld-before-t4 plan's PR B also edits `publish_dip_pulse_data.py` (`run_release`, beside `verify_export`); land after it and put the new refusal beside its `awaiting_*` refusal. | Class 11 against code for each rule; class 1 for the refusal |
| **C2** | The placeholders filled from `compare_cpp_bt.py` on the T4 store, and the date checked | Docs | T4, the coverage gate, B | Class 11 with real-store values |
| **D** | The `CLAUDE.md` stability policy, the two test comments, `PRODUCT.md:90` re-read | Docs | The first successful `--publish` | Class 11 |

A, B and C can start now in that order; A and B are independent. C2 comes before the first `--publish`, whose refusal enforces it. D comes right after. The site rows of 2e stay in stage 2. The rename touches `CITATION.cff` and `ATTRIBUTION_NAME` after A; the Vergleich text says "dieser Datensatz" and needs no rename edit.

## Decided by the owner (2026-11-14)

The owner accepted every recommendation above and gave these approvals:
- **gitleaks:** installed by the owner. The full-history scan runs as in 1c on a mirror clone in the scratchpad, with `--redact`, triaged by path. Anything outside the gstack fixture path stops the work and is reported.
- **Commit e-mail:** keep the history. This repo's local `user.email` is the GitHub noreply address already on 153 commits. The "block command line pushes that expose my email" setting stays an owner step.
- **`CITATION.cff` `url`:** left out until the site has a host. `repository-code` goes in with PR A.
- **CPP-BT download:** the 10.7 MB speech metadata from Zenodo is approved for PR B. Its version and SHA-256 go into the first run's record.
- **Still the owner's:** turning on secret scanning and push protection (Settings → Code security), and the "block pushes that expose my email" setting. **Done 2026-11-21:** both on (secret scanning and push protection checked `enabled` through the API).
- **Held:** PR C, C2 and D. C lands after the withheld-Reden PR B, which also edits `publish_dip_pulse_data.py`.

## What the owner supplies

These items wait on:
- **Install approval for gitleaks** (`brew install gitleaks`), and turning on **secret scanning and push protection** in the repository settings (PR A).
- **The commit e-mail decision:** keep the history (recommended), switch to the noreply address and block pushes that expose the personal one.
- **CITATION `url`:** confirm it waits for the site host (recommended), or take the releases page now.
- **CPP-BT download approval:** the 10.7 MB speech metadata, once for PR B and once per stable review.
- **One more sentence for the roll-call e-mail:** whether test excerpts of the roll-call pages in a public code repository are covered.
- **Calibration sign-off** after B's first run: the token-ratio thresholds (15%, 50 tokens) and the spot-check size (five sittings).

Out of scope here, named because these items wait on them: the roll-call e-mail and the MdB-Stammdaten terms (the first `--publish`), a Zenodo account (DOI on stable releases), and the trademark check (rename).
