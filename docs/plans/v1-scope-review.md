# v1 scope review

Status: **decided, 2026-11-06.** The owner answered every question; the ledger holds the answers, and `PRODUCT.md`, `TODOS.md` and the A4 plan are updated. The briefs below are kept as asked, with options the owner did not choose; where they differ, the ledger wins.

Frame: `/gstack-plan-ceo-review`, HOLD SCOPE, strategy-only depth. HOLD SCOPE because the request names six questions and asks for no new scope. Owner decisions go to the owner in chat, not through AskUserQuestion, because the global hook can auto-answer gstack briefs (`auq-adjudicator-hook` memory; it decided the frontend re-scope on 2026-11-02 before anyone had asked the owner).

Decisions are numbered Q1 to Q17, to keep them apart from D8 to D10 in the A4 plan.

Settled, not reopened: Fraktion colours stay; the static site generator no-go; no free search on the site; the nonpartisan commitments.

## Evidence

Page and store figures come from `~/agent-runs/a3/full`, the A3 build of 2026-10-28. It predates #133 to #138, so its newest sitting is 21/103 and it holds 556 votes (619 when repersisted). It describes page weight and data shape, not main's tip.

| # | Fact | Source |
| --- | --- | --- |
| E1 | All 716 reports have `summaries` = `not_requested` / `omitted`. The reference build holds no AI summary. | measured: report JSON |
| E2 | A protocol's XML appears the night after the next working day. `Last-Modified` is 23:45 GMT on 21/96 to 21/103, and matches `verteildatum`. A Wednesday sitting is out Thursday night, a Friday sitting Monday night. WP 21 `verteildatum` minus `datum`: median 1 day, largest 4 days. | measured: HEAD on `dserver.bundestag.de/btp/21/*.xml`, 2026-11-06; catalog |
| E3 | No build step fetches a Tagesordnung. `sitzungskalender` knows planned weeks, not agendas. | static read: no such URL in `scripts/` |
| E4 | WP 21 so far: 103 sittings, 66 a year, about 3 per sitting week, about 22 sitting weeks a year. | measured: catalog, 2025-03-25 to 2026-10-16 |
| E5 | One export generation is 425 MB, of which the gzipped SQLite is 252 MB. | measured |
| E6 | A repersist with render and export takes about 1,650 s on 716 sittings. | README:116; A4 slice 0 result |
| E7 | Zenodo: 50 GB and 100 files per record. A new version is "a completely new record" with its own identifier. No stated limit on how often. Whether quota is per version is inferred, not stated. | help.zenodo.org manage-files, manage-versions, manage-quota; about.zenodo.org/policies, read 2026-11-06 |
| E8 | All site HTML is 1,397 MB in 6,750 files. The raw dumps are 633 MB of that: 625 MB "Erfasste Quelldaten" on `bills/` (90% of its 694 MB), 8.5 MB "API-Felder" on `api-sitzungen.html`. Inline `<style>` is 96 MB. Without both, 668 MB. | measured |
| E9 | Politikfeld tags cover 92.7 / 95.7 / 95.3 / 94.7% of Reden characters in WP 18 / 19 / 20 / 21. By agenda item: 59.7 / 78.7 / 83.4 / 84.2%. The tags come from DIP Sachgebiete and Drucksachen, not from a term list. | measured: store |
| E10 | The nav shows 2 of 9 destinations, and 7 sit behind "Weitere Bereiche", Abstimmungen among them (`render_dip_pulse_html.py:1266`, `features/__init__.py:37`). `docs/designs/fixed-public-experience.md` cites NN/g against hiding destinations. | static read |
| E11 | `settings.html` is a 0.5.x compatibility notice whose removal was deferred to 0.6.0 (`build_dip_pulse_site.py:43`, `fixed-public-experience.md`). The project is at 0.33. | static read |
| E12 | `sources.html` is 372 KB. 333 KB of it is "Erzeugte Sitzungsdatensätze". | measured |
| E13 | `api-sitzungen.html` lists 4,680 sittings, 14.8 MB. Only WP 18 to 21 (801 rows) have XML. The brief's "pre-A3 build" is out of date: this figure is the A3 build. | measured: catalog, page |
| E14 | The chart prototype (three provisional topics on the full store, arm A) runs in plain Python, and the owner opened it on 2026-11-04. No term-list versus LDA answer is recorded since. | `frontend-go-no-go.md`; TODOS "Diskursanalyse" |
| E15 | **Corrected 2026-11-06:** the repository is public (`private: false`, GitHub API), as the owner pointed out. `SECURITY.md:8`, `TODOS.md:788,998` and the `CITATION.cff` note wrongly say or imply it is private, and private vulnerability reporting may not be on. A pattern search of tracked files at HEAD found no API keys of three common shapes; this is not a history audit. | GitHub API; `git grep` |
| E16 | Cloudflare Pages free: 20,000 files, 25 MiB per file. GitHub Pages: 1 GB (TODOS). Hetzner Webhosting S to XL: 10 to 300 GB, SSH only from L, about 1.90 to 19.90 EUR a month. | secondary web results, not checked on the vendors' pricing pages |
| E17 | One search found no direct hit for "Bundestag-Puls" or "poliwatch". OffenesParlament exists as an OKFN project. | weak: one search, not a trademark check |
| E18 | `IDEAS.md`, named at `PRODUCT.md:67`, no longer exists. | static read |
| E19 | `PRODUCT.md:58` is cited by line in `frontend-go-no-go.md`, the A4 plan and TODOS. | `git grep` |

## Briefs

### Q1. What is v1?

The data release does not need the redesign, a host for the site, or any A4 slice: the release is built from the store. The site needs all three.

- **A (recommended).** Three stages. **Data release:** track A's correctness items and track D's data half. **Public site:** the daily view plus one analysis, "Politikfelder over time". **Then** the term series, Zwischenrufe, Muster and Präsenz as each is ready.
- **B.** Data release, then a daily-only site, then analyses. The fastest public site, but it launches with one of two equal angles, and criterion 3 has to move out of the first site.
- **C.** One v1 with everything. Nothing is public until the neutrality review and the term series are done, and the data waits for work it does not depend on.

Why A: E9 shows the one analysis can run without the term-list decision, and it keeps criterion 3 and "weighted equally" true at launch. A data release first also gets the dataset in front of researchers before the site work.

Cost of any data-first option: the first release ends the pre-release rule for the dataset. `CLAUDE.md` then needs a stability policy, and a later count fix becomes a recorded correction.

**Answer (owner, 2026-11-06): A plus a coverage gate.** E20: the store holds 716 of 801 catalog sittings (WP 18: 194/245, WP 19: 206/239, WP 20: 213/214, WP 21: 103/103), so 85 whole sittings are missing, mostly 2014 to 2018. The Politikfeld figure in E9 is a label gap on speeches that are present, and gates the analysis in stage 2, not the data release.

Before the first data release:
1. Another parser round on the 85 excluded sittings.
2. A written bar: a sitting may stay out only with a named source defect, listed with its reason. Coverage is published per year.
3. Measured: votes in the excluded sittings, whether those sittings differ systematically from the included ones, and the abgeordnetenwatch match share of WP 18/19 Redner.
4. The store rebuilt on current main, and the gate run on it.
5. The correctness items of track A finished: ADR 0004 kinds (Q13), the retired-bindings registry issue, E4 (#138).

Fallback, decided only after a first attempt shows the cost: release WP 20 and 21 first as a complete set, WP 18 and 19 in a later version.

### Q2. How much of A4 before the site goes public?

No slice is needed for the data release. Slices 2 to 9 move the remaining pages to the store, slice 10 proves it, and slice 11 is a file split.

- **A (recommended).** Slices 2 to 10 before the public site. Slice 11 after, whenever it helps.
- **B.** Public site earlier. Pages stay on report JSON, and each release runs a figure-agreement check like `docs/plans/a4-slice1-oracle/r3_agreement.py`. Principle 6 is reworded until the slices land. Faster, but the check only covers what it compares, and every renderer gets redesigned and then moved.
- **C.** All of it, slice 11 included. Slice 11 changes nothing a reader sees.

Why A: `PRODUCT.md:36` promises every figure can be reproduced from the release, and slice 10 is the only proof of it. Q4 and Q7 shrink slices 5, 2 and 7.

### Q3. Freshness

E2 is the hard limit: the protocol path cannot show "today", and E3 means no other source does either.

- **A (recommended).** One kind of release. Every data update of the site is a release, and a rebuild that changes only code or copy keeps its release. Start at one release per completed Sitzungswoche, about 22 a year and 9 GB a year. The worst lag is 6 days (a Wednesday sitting shown the next Tuesday). Move to one per protocol night, about 66 a year and 28 GB a year, once the scheduled workflow has run for a while; the rule and wording do not change.
- **B.** The site runs ahead, with citable releases about quarterly. Fresher (1 to 4 days), but a figure from the last months cannot be reproduced from any release, and every affected page has to say so. `PRODUCT.md:36` has to weaken.
- **C.** Two kinds: an immutable snapshot per update, a DOI only on periodic releases. Same freshness as B with reproducibility kept, but readers and the changelog have to tell the two kinds apart.

Zenodo sets no cap on this (E7). The cost is operator time (E6) and the corrections a person writes per release (TODOS "Public data changelog").

Wording if A:
- `PRODUCT.md:25`: "the most recent Sitzungen with a published protocol and the Sitzungswoche they belong to, and the next planned Sitzungswoche" replaces "today and this week".
- `PRODUCT.md:31`: "its latest Sitzung and latest Sitzungswoche".
- Principle 6: "The site and the release compute each figure once, from the same dataset. Every figure on the site comes from one named release, shown on the page, and can be reproduced from it. Every data update of the site is a release; a rebuild that changes only code or copy keeps its release. A change to a released figure is recorded in the next release's changelog, not silently overwritten."

**Q3 answer (owner, 2026-11-06): two kinds of release, replacing options A and C above.**
- **Main release:** published automatically per completed Sitzungswoche, and only if every check passes. A failed check publishes nothing. The site always reads the latest main release, and each page names it. Every main release is kept, with a date and checksums.
- **Stable release:** one frozen main release, reviewed by the owner about every three months against a written checklist, with a DOI. It is a marker on that release, not a separate database. Old stable versions stay downloadable. Citations should name stable.
- **First stable:** the first data release, after the Q1 gate.
- **A review finds a bug:** the fix goes into a new main release, the owner checks that change, and that release becomes stable.
- **Daten page:** offers both downloads, explains why they can differ, and shows the date of the last review.
- **New roadmap items:** the review checklist, and an alert when an update fails, with the site showing the age of its data.

The wording above for `PRODUCT.md:25` and `:31` stands. Principle 6 gains: "A stable release is a main release the owner has reviewed." Per-night main releases remain possible later.

### Q4. AI summaries (A4 D8, criterion 4)

E1: no summaries exist, so criterion 4 cannot be tested on any current build.

- **A (recommended).** Out of v1, on the site and in the release. Criterion 4 moves to a "later" list and the code stays. Slice 5 adds no `summaries` table.
- **B.** In v1, in the release as its own table (the A4 plan's recommendation). This needs a generation run over 716 sittings, a licence layer and a review of the output. Cost not measured.
- **C.** In v1 as a site-only file. This weakens A4's done criterion and principle 6.

### Q5. Surfaces (depends on Q1)

| Surface | Serves | Recommendation |
| --- | --- | --- |
| `index.html` | both | **Keep** as the door to both angles |
| `puls.html` | daily | **Keep**, the core of the daily view |
| `overview.html` | shared | **Keep** as Sitzungen. Takes the exclusion list from the catalog page |
| `api-sitzungen.html` | neither | **Cut.** WP 1 to 17 metadata goes to the release (`sittings`, slice 2), the 85 exclusions to `overview.html` (E13) |
| `sources.html` | both | **Keep** as Quellen und Methode. Cut the 333 KB sitting list (E12) |
| `settings.html` | neither | **Cut** (E11) |
| `bundestag.html` | both | **Keep**, footer link |
| `database.html` | researchers | **Keep** as Daten, shape in Q10 |
| Fakt der Woche | neither today | **Off the v1 site and out of the release** (owner, overriding the brief's "merge"); rebuilt later |
| Gesetzesvorhaben | shared | **Keep**, without the raw dump (Q7) |
| Abgeordnete | shared | **Keep** |
| Abstimmungen | daily, shared | **Keep**, promoted in the nav |
| `impressum.html`, `datenschutz.html` | required | **Keep**, footer |
| `analysen/` | long-term | **New**, in the nav only once the first analysis exists |

### Q6. Main navigation (depends on Q5)

Recommended: Aktuell, Sitzungen, Abstimmungen, Gesetzesvorhaben, Abgeordnete, Analysen, Daten. Footer: Quellen und Methode, So arbeitet der Bundestag, Impressum, Datenschutz. Alternative: keep today's two links plus a menu, against E10. How seven links fit at 375 px is for the design session.

### Q7. The two raw dumps (A4 D10)

**A (recommended).** Drop both: E8, 633 MB, 45% of all site HTML, and principle 3. The content is in the release in structured form. **B.** Move them to the exempt dev view. **C.** Keep them on public pages.

### Q8. Public host (coupled to Q7)

With Q7 and a shared stylesheet the pages are about 670 MB (E8), so every host below fits. The host decides what the Datenschutz page has to say, which is why it comes before the Impressum values.

- **A (recommended).** A German host with SSH for the pages (for example a Hetzner Webhosting plan with SSH, or a small VPS), and data files on GitHub Releases plus Zenodo. Simple Datenschutz text and rsync deltas.
- **B.** Cloudflare Pages. Free and fast, but a US provider in the Datenschutz text.
- **C.** GitHub Pages. Its 1 GB cap leaves little room, and pages grow with every sitting.

Whichever is picked, the flat GitHub asset layout needs `generation_file_href` to change (TODOS "Write the release script", decision (b)), and `data/` must not be deployed wholesale.

### Q9. One site or two

**A (recommended).** One, as the current plan says: shared pages are the differentiator (`PRODUCT.md:40`), and two sites mean two Impressum and hosting setups. **B.** Two, on one release. Slice 10 keeps this open later.

### Q10. Daten page shape, and the pilot gate

**A (recommended).** The page carries downloads, citation, Datenstand, changelog and recipes. Schema and codebook prose live in the release's `DATA.md`, which the page links. Delete "Pilot gate: decide keep/remove for the Daten page": the dataset is a product in its own right since 2026-09-30, so a keep-or-remove gate no longer applies. **B.** Keep the page as it is and only remove the gate. **C.** Keep both.

### Q11. Product name

Needed at the data release, not only the site: the CC BY attribution string says "Bundestag-Puls" while `CITATION.cff` says "poliwatch" (TODOS release item 11). Three candidates exist. "Bundestag-Puls" names the weekly view and has 43 code lines, and whether "Bundestag" may read as official is a question for the lawyer. "poliwatch" and any "-watch" name read as a watchdog beside abgeordnetenwatch and plenarwatch, against the neutral brand. "open-parlament" sits close to OffenesParlament (E17). The owner's own call. Recommendation: pick before the first release, and fix `PRODUCT.md:67`, which cites a file that is gone (E18).

### Q12. Third-party data in the release (A4 D9)

**A (recommended).** No new third-party data. Renderers read only what is already persisted, under the existing licence layers. **B.** Add DIP Vorgang records to the release: more licence surface, little gain.

### Q13. ADR 0004 kinds

A `<rede>` with a presidium `rolle_lang` is one of three kinds. **A (recommended).** Sitzungsleitung is excluded; an official address is its own kind, shown on the Dossier and in no Reden count; a debate Rede counts for the Fraktion. This lets 18/1 and 19/1 leave the exclusion list and moves 18/245. **B.** Keep 18/1 and 19/1 excluded for the first release and treat only 18/245. Fewer cases now, two known gaps in the first release.

### Q14. Term lists

`PRODUCT.md:44` states term lists as fact; TODOS says provisional, waiting for a preview. Does the prototype of 2026-11-04 (E14) count as that preview? **A (recommended).** Yes: confirm term lists over a topic model, keep the neutrality review as the gate before any term series is published. **B.** Not yet: `PRODUCT.md:44` says provisional until a further preview. **C.** Reconsider a topic model.

### Q15. Repository visibility (new, follows from Q1)

E15. **A (recommended).** The repository goes public at the data release, since each release names its code commit and a reader has to be able to read it. Check the history first. **B.** Zenodo-only data release, repository private until the site. The manifest then cites a commit nobody can open.

### Q16. Reader evidence

Nobody outside the project has seen the site or `DESIGN.md`. **A (recommended).** Five readers before `DESIGN.md` goes site-wide, on the first converted pages, with tasks taken from criteria 1 to 3 on desktop and mobile, and one researcher or journalist trying the data release. Rewrite the P3 TODO and raise it. The owner recruits; about 45 minutes each. **B.** Test before launch, after the rollout: later changes cost more. **C.** No test: launch on builder judgement.

### Q17. Stack paragraph

Draft for `PRODUCT.md:58`, staying on line 58 because other files cite it (E19):

> **Stack:** a Python standard-library pipeline that writes plain HTML, JSON and SQLite, with no package manager, framework or build toolchain. A public record has to stay buildable and auditable for years by a small operator, so every dependency has to earn its upkeep. A static site generator was tested against this and rejected on 2026-11-04 (`docs/plans/frontend-go-no-go.md`); revisit only when a real chart cannot reasonably be hand-drawn. Which pages already read the store is tracked in `docs/plans/a4-site-from-release.md`.

The reason sentence is drafted from the go/no-go's cost list. The owner should confirm it is the real reason.

## Decision ledger

| ID and owner | Contract and evidence | Current | Proposed | Status | Exact approval and scope |
| --- | --- | --- | --- | --- | --- |
| Q1 owner | `PRODUCT.md:33`, E9, E20 | A plus coverage gate | none | approved | owner in chat, 2026-11-06: "Yes, A plus gate". Three stages; the data release passes the gate below first. |
| Q2 owner | `PRODUCT.md:36`, A4 slice map | slices 2 to 11 before the public site | none | approved | owner in chat, 2026-11-06: "A+C", slice 11 included because it eases future work. None needed for the data release. Order against the redesign is for the architecture session; the plan has slice 11 after 10. |
| Q3 owner | `PRODUCT.md:25,28`, E2 to E7 | main and stable releases | none | approved | owner in chat, 2026-11-06: "yes, sounds good", to the owner's own two-release proposal. See "Q3 answer". B rejected: the site must not drift from published data. |
| Q4 owner | criterion 4, E1 | out of v1, site and release | none | approved | owner in chat, 2026-11-06: "Yes, out of v1". Criterion 4 moves to a "later" list, the code stays, slice 5 adds no `summaries` table. |
| Q5 owner | E10 to E13 | table in Q5, except Fakt der Woche | none | approved | owner in chat, 2026-11-06: "agree with all", then "yes" to Fakt der Woche off the v1 site (`puls.html`, nav, archive pages) and its `facts` tables out of the release; it returns later as a rebuilt feature that meets the project's quality bar. Engine stays. Fakt B, C and "post one card" wait for that rethink. This overrides the table's "Merge" row. |
| Q6 owner | E10 | Aktuell, Sitzungen, Abstimmungen, Gesetzesvorhaben, Abgeordnete, Analysen, Daten; footer: Quellen und Methode, So arbeitet der Bundestag, Impressum, Datenschutz | none | approved | owner in chat, 2026-11-06: "Yes, as proposed". Analysen appears once the first analysis exists. Collapse at 375 px is for the design session. |
| Q7 owner | A4 D10, E8 | both raw dumps dropped | none | approved | owner in chat, 2026-11-06: "yes, drop both". Pages stay; only the collapsed blocks go. Slice 7 first checks that no field readers need exists only in the dump, and moves any such field into the store. |
| Q8 owner | E8, E16 | German host with SSH for the pages; data on GitHub Releases and Zenodo | none | approved | owner in chat, 2026-11-06: "German host". Provider and plan still to pick; check prices on the vendor's page. `generation_file_href` changes, and `data/` is not deployed wholesale. |
| Q9 owner | `PRODUCT.md:70` | one site | none | approved | owner in chat, 2026-11-06: "One site". |
| Q10 owner | `PRODUCT.md:69`, TODOS | short page: main and stable downloads, citation, coverage per year, last review date, changelog, recipes; schema and codebook in `DATA.md`; pilot gate deleted | none | approved | owner in chat, 2026-11-06: "Yes, both". |
| Q11 owner | `PRODUCT.md:67`, E17, E18 | open-parlament, lower case, for the whole project | none | approved | owner in chat, 2026-11-06: "Lets go for open-parlament for now". Owner holds open-parlament.de, has checked Open Parliament TV and confirmed OffenesParlament is unmaintained. "Plenarchiv" noted as a possible dataset name. Owner registered openparlament.de on 2026-11-06. Owner to-do before the first release: trademark register check. |
| Q12 owner | A4 D9 | no new third-party data; renderers read only what is persisted | none | approved | owner in chat, 2026-11-06: "yes, lets go with A". The slices check each page's field is in the store and add any that is missing. A refreshed cache reaches pages only through a rebuild. |
| Q13 owner | ADR 0004 | three kinds: Sitzungsleitung excluded; official address its own kind, shown on the Dossier, in no Fraktion's Reden count; debate Rede counts for the Fraktion | none | approved | owner in chat, 2026-11-06: "Yes, three kinds". The build first lists every case in WP 18/19; hard cases return to the owner. Moved counts are reported old and new. |
| Q14 owner | `PRODUCT.md:44`, E14 | term lists confirmed over a topic model; neutrality review gates any published term series | none | approved | owner in chat, 2026-11-06: "Yes, term lists". |
| Q15 owner | E15 | no decision needed: already public | none | closed by correction | owner in chat, 2026-11-06: "this repo is public on github". My brief was wrong. Follow-up for the roadmap: fix the stale claims, turn on private vulnerability reporting, add `repository-code` to `CITATION.cff`. |
| Q16 owner | TODOS, DESIGN.md | five-reader test before launch, after the rollout | none | approved | owner in chat, 2026-11-06: "Test before launch" (option B over testing before the rollout). The pass rule and the separate researcher check of the data release are not decided by this answer. |
| Q17 owner | E19, TODOS "Design hand-over leftovers" | stale | draft | unresolved | none yet |

## What this means for the design and architecture sessions

**Design session**
- Pages to design for: home as the door to both angles, Aktuell, Sitzungen, Abstimmungen, Gesetzesvorhaben, Abgeordnete, Analysen, Daten. Do not spend work on `api-sitzungen.html`, `settings.html` or Fakt der Woche.
- Navigation: seven main links, four footer links. How seven fit at 375 px is yours.
- The name is open-parlament, so identity work may use it. No logo yet.
- The reader test comes after the rollout, just before launch. Keep the grey ground and vote wall easy to change.
- New page elements: the page's main release and data age on every data page; on Daten, main and stable downloads, coverage per year, last review date.
- No AI summaries in v1. Their label and collapse control are not v1 components.
- "Aktuell" must not promise today: a sitting can be up to 6 days old when it appears.

**Architecture session**
- A4 slices 2 to 11 land before the public site; none is needed for the data release. Stage 1 work (coverage gate, correctness) goes first. Your call: the order of slices against the redesign, and whether slice 11 can move earlier, since the 14,775-line file slows the redesign and the plan has it after slice 10.
- Smaller slices: 5 (no summaries), 2 and 7 (no dumps, no catalog page), 3 (no Fakt gap notes). `facts` tables leave the release.
- Renderers read only what is persisted (D9). A refreshed cache reaches a page only through a rebuild.
- The site builds from the latest main release. A code-only rebuild keeps its release.
- Release layout: GitHub Releases plus Zenodo (stable only) for data, a German SSH host for pages. `generation_file_href` changes; `data/` is not deployed wholesale.
- Automation needs a fail-closed gate and an alert. Parser breaks wait for the owner.

## Review frame

Depth was strategy-only, HOLD SCOPE. This is a documentation review, so sections on error maps, security, data flow, code quality, tests, performance, observability and deployment have no code to apply to; their concerns appear as decisions Q3, Q8 and the "Main and stable releases" TODO. No outside voice ran: Codex cannot run in this sandbox (`codex-review-sandbox` memory), so no second model has reviewed this. One premise failed under the owner's eye: E15 said the repository was private, from stale docs.

Open: the host provider; the reader test's pass rule; the researcher check of the data release.

## GSTACK REVIEW REPORT

| Runs | Status | Findings |
| --- | --- | --- |
| 1 | issues_open | 17 questions: 16 answered, 1 closed by correction. Coverage gap of 85 sittings raised by the owner's challenge; no AI summaries exist; "today" has no source |

VERDICT: scope decided by the owner. No outside coverage.

**UNRESOLVED DECISIONS:**
- Host provider, reader test pass rule, researcher check of the data release (all recorded in TODOS.md).
