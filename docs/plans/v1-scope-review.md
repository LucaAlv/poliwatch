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

## Second pass: research datasets (2026-11-06)

The owner asked for `/gstack-plan-ceo-review` on the committed scope, plus a thorough look at GermaParl. Full comparison and sources: [bundestag-corpora-landscape-2026-11.md](../research/bundestag-corpora-landscape-2026-11.md). Depth stays strategy-only. The owner answered N1 to N5 on 2026-11-07, and the answers are applied to `PRODUCT.md` and `TODOS.md`. No code changed. The defects the cross-check found are filed in `TODOS.md` and `docs/source-errors.md`, not fixed.

### Step 0A: premises

The first pass tested the plan against the project. It never tested it against other datasets, though researchers are one of the two audiences.

Real problem: researchers need a Bundestag record they can build on, and citizens need a way into it. Do-nothing cost: the first release is judged next to CPP-BT, on a claim CPP-BT already meets, with fewer sittings.

| Premise | Claim | Receipt | Verdict |
| --- | --- | --- | --- |
| P1 | The differentiator is the connection | `PRODUCT.md:40` | **Holds, narrower.** No current join was found (negative search). ParlLawSpeech links speech, bill and law for 2009 to 2021, so the claim is "current", not "only" |
| P2 | Researchers want a tidy, citable record, and that is what we offer | `PRODUCT.md:15` | **Partly false as a difference.** CPP-BT is tidy and citable, CC0, to 2026-09-19 |
| P3 | Comparable products are sites | `PRODUCT.md:42-46` | **Finding.** No research dataset is named. The positioning that did name them is in the design of the feature now cut, `docs/designs/fakt-der-woche.md:36-41` |
| P4 | Excluding a sitting costs its Reden | `a3-wp18-19-round2-result.md:165-172` | **Finding.** The cost table counted Reden. Decision 0 there skips a listed sitting before acquisition, so its TOPs, links and votes go too. The store holds 0 of 556 votes on the 85 dates [measured] |
| P5 | A refused unit means the sitting must go | `round2-result.md:165,174,189` | **Unexamined.** No per-unit alternative appears in the A3 plans or `TODOS.md` [`git grep`]. 19/25 was excluded to keep out 2 units, at a cost of 15 Reden and about 200 other units |
| P6 | One `redner_id` is one person | store | **False.** Seven ids are shared in the source; 5 of them put 43 stored units under the wrong person [measured: XML scan of every `<redner>`, store]. First reported as 2 ids and 5 units; that scan undercounted |
| P7 | "open-parlament" is clear of neighbours | Q11 | **Weak spot.** The owner confirmed OffenesParlament is unmaintained, but CPP-BT's September 2026 record still lists it as an alternative, so researchers will still meet the name |

`unverified=0`.

### Step 0B: what already exists

| Need | Reuse |
| --- | --- |
| Keep a sitting while withholding refused units | `scripts/audit_offline_turns.py` shows the idea, blanking refused turns to measure what remains, but it says itself its counts "cannot certify or replace a report/database", so it is not a base to build on. `contributions.kind` holds non-Rede kinds and raises on an unknown one. `coverage-exclusions.json` records no real reasons: all 85 entries say "excluded", and the reasons are in plan prose, so they must be written down (corrected 2026-11-07) |
| Check against an outside source | `rede_id` is the same Bundestag id in both datasets, format `ID19200100` [measured against the codebook] |
| Show coverage honestly | `datenstand` and per-year coverage from Q1 and Q10 |

### Reality rows

```
REALITY: premise-table finding 7 premises, unverified=0, findings on P3 to P6 PRODUCT.md:42
REALITY: already-done pass origin/main has no commit on PRODUCT.md, TODOS.md or these plans since 614dda2; nothing here is built TODOS.md:5
REALITY: surface-check pass the only named flag, --exclude-document-number, exists README.md:169
REALITY: binding-decisions finding branch search empty; Q1 and the 2026-10-22 decision 0 are binding, and N1 reopens them only on new evidence, by asking docs/plans/a3-wp18-19-round2-result.md:174
REALITY: numbers finding store figures are from the A3 build, re-measure before any gate; items marked [estimated] are subtractions or rates docs/plans/v1-scope-review.md:13
REALITY: deferred-asks pass no linked issue docs/plans/v1-scope-review.md:1
REALITY: pr-count pass docs only, one branch, default one PR per wave TODOS.md:5
```

### Step 0C: where this goes

```
  TODAY                          THIS PLAN                       12-MONTH IDEAL
  716 of 801 sittings;    --->   first release, linked and  ---> the citation for "how did this
  joins exist, nobody            current, weekly; site with      debate relate to the bill and the
  outside has seen them          one analysis                    vote", checked against CPP-BT and
                                                                 GermaParl on every stable release
```

The plan moves toward this, if the release keeps every join it can keep.

### New decisions

Numbered N, to stay apart from Q1 to Q17, A4's D and R rows and roadmap C1.

**Figures for N1.** Lost in the 85 excluded sittings: 8,235 `rede_id`s (CPP-BT's rows on those sittings, including §31 declarations) [measured 2026-11-07; first stated as about 9,300, which also counted annex units in sittings we hold], about 850 TOPs and 4,000 Drucksache links [estimated: store rates], about 70 votes [estimated: 0.78 to 0.86 per sitting]. Refused markers in the WP 18/19 audit, before any rules: 205 in 112 sittings, about 2 per sitting [measured: `a3-wp18-19-audit.md:24-28`]. After round 2's rules: 103 markers in 87 Reden in 69 sittings, at most 4 per sitting, none on a Rede's first marker [measured: `a3-wp18-19-round2-blockers.tsv`]. Cascades stayed in the same Rede (`audit:91`). A further 13 of the listed sittings parse and raise no refusal (`round2-result.md:229`), see N7.

| ID and owner | Contract and evidence | Current | Proposed | Status | Exact approval and scope |
| --- | --- | --- | --- | --- | --- |
| N1 owner | Q1 gate step 1; `round2-result.md:174`; P4, P5 | Whole sittings stay out until parser rounds clear them | Keep each sitting and its links; withhold only refused `<rede>` units, flagged with a reason, outside all Reden counts | decided | Owner 2026-11-07: "N1: B", confirmed after the corrected premise (outside finding 5): "Confirm N1: B". Reopens decision 0 of 2026-10-22 and Q1 gate step 1 on new evidence |
| N2 owner | `PRODUCT.md:15,40,42-46`; P1 to P3 | Comparables are sites | Name the research datasets; state the claim as the linked, current record; say there is no affiliation | decided, wording changed | Owner: leaning A, but "joined" reads as working together. "I am very open to collaborating in the future, but at the moment it is more a 'common stated direction or cause'." |
| N3 owner | Q1 gate step 3; download rule | Excluded sittings not compared | Fetch `CPP-BT_2026-09-19_DE_CSV_Reden_Metadaten.zip` (Zenodo 22844952, 10.7 MB, CC0) for a per-sitting `rede_id` comparison; repeat before each stable release, outside the build | decided, done | Owner: "N3: A". Result below |
| N4 owner | `PRODUCT.md:58`; landscape | `DATA.md` has no comparison | A "Vergleich" table and joinable ids (`rede_id`, `xml_redner_id`) in `DATA.md` | decided | Owner: "N4: A". TODO "Comparison and joinable ids in DATA.md" |
| N5 owner | Q16 open item | No researcher named | The owner handles the researcher check | decided | Owner: "N5: I'll handle this myself." |
| Mode owner | Skill Step 0E | none | HOLD SCOPE | default | The owner's reply named no mode, so the recommended HOLD SCOPE ran. Not an owner choice |
| N6 owner | Section 2; `validate_dip_protocol.py:1373,1300` | A `<rede>` can vanish with no unit and no refusal | Every `<rede>` id ends up stored, withheld with a reason, or excluded by a named rule, reconciled per sitting | part of N1 | N1 cannot be shown complete without it. Recorded as what the implementer must prove, inside the owner's N1 answer |
| R7 implementer | Step 0 and N3; `CLAUDE.md` review rule | 45 units lost (first counted as 46), 43 under the wrong person, 2 stray Fraktion values | Fixed on two unmerged branches, on the owner's word: `claude/objective-satoshi-86c7a1` (35c7e77), `claude/elated-tereshkova-f657d3` (b35245c). Stray Fraktion values still filed | built, not landed | Owner 2026-11-07: "Start both" |
| N7 owner | Outside finding 1; `round2-result.md:127,141,225-229,248`; reopens part of N1 | 13 listed sittings parse, raise no refusal and are kept out only by the list, so N1 as worded does not reach them. 7 wait on the ADR 0004 item (18/178, 18/223, 18/245, 19/1, 19/9, 19/19, 19/73). 2 stay out by the owner's round 2 decision (18/62, 18/90). The open question is 4 sittings with known wrong units: 18/2, 18/29, 18/83, 19/25, the example behind P5 | A reviewed list of single units to withhold in those 4, each with a reason, in the same withheld state as N1 | decided | Owner 2026-11-07: "N7: A". Rejected: keeping the 4 out whole |
| N8 owner | Outside finding 4; `round2-result.md:89-91,228` | The 400 kept sittings had a merge and attribution review. The sittings N1 restores would not | The same review on restored sittings. Pass rule: any wrong unit goes on the withheld list with a reason, and T4 does not pass until the review has | decided | Owner 2026-11-07: "N8: A". Rejected: relying on the gate and the CPP-BT comparison, which do not check content |
| R9 implementer | Outside finding 8; `validate_dip_protocol.py:3455-3492` | A Rede outside a TOP has no place in the schema; `agenda_item_id` is required on `speeches` | Under the item the Inhaltsverzeichnis names; a Rede with no entry, or one after a TOP, refuses the sitting. No schema change. `docs/plans/reden-outside-tops.md` | settled, owner may veto | The fix session's eng review; the adjudicator hook answered, not the owner. No figure changes meaning |
| R10 implementer | Codex finding 4; `build_dip_pulse_site.py:3440`; `speeches` UNIQUE(agenda_item_id, sequence) | Withheld units have no storage shape, and no one is assigned the 20 statements that read `speeches` | A flag on `speeches` or a separate table; list every reader | pending | Decide in `/plan-eng-review`, before T3 |
| R11 implementer | Codex finding 2; `validate_dip_protocol.py:943,1396,1450-1562` | Reconciliation assumes one source id per stored unit, but the parser splits Reden and moves text | Inventory the raw XML before any edit to the tree; a written rule for split-off units and moved text | pending | Decide in `/plan-eng-review`, before T3 |
| N9 owner | Codex finding 5; `TODOS.md` gate step 4 | The bar has no number: a sitting with every Rede withheld would still count as held, and yearly unit totals hide where the loss falls | Publish the withheld share by words per sitting, year and Fraktion, and set a numeric bar from T4's measurement | unresolved | none yet |
| N10 owner | Codex finding 3; `validate_dip_protocol.py:2686,2893` | No test or gate checks that a vote link is right, though links are the stated difference | A reviewed sample of links before the first release, and the meaning of a link stated in `DATA.md` | unresolved | none yet |

### N3 result

Full method and tables: [the landscape note](../research/bundestag-corpora-landscape-2026-11.md), "Cross-check against CPP-BT". In the 707 sittings both hold:

- Every real `rede_id` of ours is in CPP-BT. They have 1,716 more in shared sittings.
- 1,666 of those are §31 declarations, left out by rule. That explains the WP 20 gap of 476, which the second-pass note had left open.
- 45 units are lost with no refusal: 29 Reden outside any TOP (18/49: 26 of 51, including Schäuble's budget speech; 18/44: 3) and 16 written submissions with a longer annex title (18/133, 18/134). First counted as 46: the Rede of 21/43 turned out to be held by existing rules. The 4 other annex units are not lost: 2 are § 31 declarations and 2 are reprints.
- Comparing surnames led to 3 more shared ids. With a scan of every `<redner>`, 43 units sit under the wrong person. The first scan said 5.
- The excluded sittings are longer than the rest, which answers gate item 3 and strengthens N1. Median Reden 70 against 54 in WP 18, 125 against 102.5 in WP 19. By words we hold 69.0% of 2018.

## Review sections (2026-11-07, HOLD SCOPE, strategy-only)

**Current scope.** Mode: HOLD SCOPE, by default. Accepted: Q1 to Q17 as decided; N1 B, N2 reworded, N3 done, N4, N5 with the owner, N6 inside N1, N7 A, N8 A. Deferred: the fixes for R7. Rejected: none. Not chased: linguistic annotation, WP 1 to 17, ParlaMint encoding, Parquet.

### Section 1: Architecture

```
  Protocol XML ──► parser ──► every <rede> ─┬─ stored unit ───────────► Reden counts
  DIP (TOPs,                                ├─ withheld + reason ─────► named omissions
  Drucksachen,                              └─ excluded by rule (§31)─► documented rule
  Vorgänge)                                   │
  roll-calls ──────────► stored for every     └─ reconcile per sitting: must add up,
                         kept sitting              else the build refuses that sitting
                                  │
                                  ▼
                  release ──► site (A4) ──► page names release and omissions
                     │
                     └── outside the build: CPP-BT rede_id comparison per stable release
```

- **Boundary that changes:** the unit of refusal moves from the sitting to the `<rede>`. The exclusion list stays, for whole-sitting source defects only.
- **Coupling:** the comparison with CPP-BT is a checklist step, with no build dependency. If CPP-BT stops, the check stops and the release does not.
- **Feasibility risk:** the 85 sittings were never acquired (P4), so N1 needs a fetch. The estimate is about 2,200 DIP requests, unless the bulk prefetch already covers them.
- **Rollback:** nothing is published, so the store is rebuilt.
- **Value test:** the reconciliation is a check on the system, and its consumer is the build's refusal. The comparison serves the stable-release review and retires if CPP-BT stops updating.

### Section 2: Error and rescue map

| Capability | What can go wrong | Handled today? | User sees |
| --- | --- | --- | --- |
| Reading `<rede>` | Element outside the path the parser reads | **No. CRITICAL GAP** (18/49, 18/44) | A complete sitting with half its Reden |
| Annex classification | Title differs from the exact strings | **No. CRITICAL GAP** (18/133, 18/134) | Submissions missing, nothing said |
| Person binding | One id, several people | **No. CRITICAL GAP** (43 units) | The wrong person's record |
| Fraktion value | Not a Fraktion | **No** (2 units) | A stray group, possible in a count |
| Refusal | One bad unit | Yes, but it costs the sitting | Sitting missing, with its votes. N1 changes this |
| Withholding (new) | Blanking shifts other units | Unknown. The implementer must prove it does not | Wrong ids or order |
| Fetching the 85 (new) | DIP stops or limits requests | Budget and stop rule exist from A3 | Sitting stays listed as not acquired |

The three silent paths break "refuse, never miscount". N6 is the rescue for the first two and for any future case of the same kind.

### Section 3: Security

No issues found. There is no new endpoint, input or secret. The downloaded CSV stayed in the scratchpad and was read as data with `python3 -I`. A DIP key is needed for the fetch and already has a home.

### Section 4: Data flow and edge cases

```
  <rede> -> classify -> refused? -> keep text, flag, leave out of counts -> release -> page
                    \-> nil/empty id, no <redner>: withheld with a reason, not dropped
                    \-> outside a TOP: needs a decided home, agenda_item_id is required today
                    \-> all units refused: the written bar decides whether the sitting stays
                    \-> source file changed since fetch: comparison shows it, C4 may be one
```

| Interaction | Edge case | Handled? |
| --- | --- | --- |
| Reader opens a sitting with a withheld Rede | Sees the place and the reason, reaches the XML | To design, Section 11 |
| Researcher sums Reden per Fraktion | Withheld units absent, and named | N1, DATA.md |
| Researcher joins to CPP-BT | §31, `(neu)`, `:N`, `nested*`, shared ids | N4 |
| Text search in the dump | Withheld text is present | Must be flagged in the row, implementer to confirm |

### Section 5: Code quality

Strategy depth, so only this. `validate_dip_protocol.py:1300` and the audit both read fixed paths and strings, which is why the audit could not see what the parser skipped. A check written against "every `<rede>` in the file" avoids that. The `nested*` ids look like `rede_id`s in `contributions` and misled this review's own first count, so `DATA.md` should explain them.

### Section 6: Tests

| New thing | Must assert | Rejects | `no_claim` |
| --- | --- | --- | --- |
| Reconciliation | Stored + withheld + rule-excluded = all `<rede>` ids, per sitting | 18/49 today | Whether a stored unit's content is right |
| Withholding | Other units identical with and without the withheld unit | Shifted ids or sequence | Whether the refusal itself was right |
| Reden outside a TOP | 18/49 yields 51 ids | 25 | The right TOP label, until decided |
| Annex titles | 18/133 and 18/134 yield their 16 | 0 | Other unseen titles; reconciliation catches those |
| Shared ids | Each of the 43 under the printed person; Völlers keeps her own | One id, one person | Ids not yet seen as shared |
| CPP-BT comparison | Report per sitting, no build dependency | Silent drift | That either source is right |

The 2am test is a full replay where reconciliation passes on all kept sittings and the comparison leaves only named kinds. The hostile test is a synthetic sitting with a `<rede>` in an unexpected container.

### Section 7: Performance

No issues found at this depth. Reconciliation adds one pass over each sitting's XML, which is already parsed. The real cost is the fetch of the 85. The comparison ran in a few minutes on the laptop.

### Section 8: Observability

Withheld units need a count per sitting and year in the release manifest, so a stable-release review sees a rise. The checklist already has "figures moved since the last stable", and withheld counts join it. Gap: nothing today reports units lost, which is what N6 adds.

### Section 9: Rollout

Order: fix the two silent-loss and shared-id P1s, then build withholding with the reconciliation, then fetch the 85, rebuild, gate, compare, release. Every step moves figures, so report old and new values as `CLAUDE.md` asks. Nothing is public, so there is no migration. Post-rebuild checks: 18/49 has 51 ids, votes on the 85 dates match the roll-call list date by date, and the comparison shows only named kinds. Fetch the 85 XML files first and scan them for shared ids and Reden outside a TOP, because the figures here cover only the 716 files.

### Section 10: Long-term trajectory

- **Reversibility:** 4 of 5. Withholding can be undone by rule, until researchers cite figures.
- **Debt added:** a withheld state that every count must respect. Debt removed: an exclusion list doing two jobs.
- **Path dependency:** once released, the reasons become part of the citable record, so keep them few and named.
- **One-year test:** the ADR and the per-unit reasons explain it to a newcomer.
- **Trajectory:** a parser round now shrinks a list instead of restoring whole days.

### Section 11: Design

Small UI scope: a withheld Rede is a new visible state. No pixel-level review here; "Apply DESIGN.md to the site" must cover it.

| Feature | Empty | Partial | Success |
| --- | --- | --- | --- |
| Sitting page | No Reden: says so | "n Reden hier nicht gezählt", with reason and source link | As today |
| Coverage per year | Year with no sitting | Sittings and units both shown | 100% |

## Fallback outside review (2026-11-07)

Codex could not start in the sandbox, so the skill's bounded fallback ran: one Plan subagent, inside this harness. It counts as a native review, not as outside coverage. It checked the plan against the repo and the A3 store, and did not run the parser. Its prompt ended mid-sentence in `TODOS.md`, so the items after "Reden the parser drops without refusing" were not reviewed there.

| # | Severity | Finding | Checked | Disposition |
| --- | --- | --- | --- | --- |
| 1 | Critical | 13 listed sittings parse and raise no refusal, so N1 does not reach them, and the reconciliation and comparison would pass with their known wrong units | Confirmed, `round2-result.md:229`. 7 are official or presidium addresses that ADR 0004 kinds cover | **N7**, narrowed to 4 sittings; owner chose A |
| 2 | High | Refused turn and refused `<rede>` are two designs. No refused marker is a Rede's first, so withholding the `<rede>` also removes its unquestioned opening | Confirmed, 87 Reden | Keeps the owner's N1 wording, `<rede>`: 87 Reden, against 8,235 `rede_id`s in the 85 sittings. The opening is withheld with the rest. Stated in the TODO, for the ADR |
| 3 | High | Some refusals fit neither design: Fragestunde markers have no rede id, "conflicting roles" is sitting-wide, 18/90's defect is outside any `<rede>`; classification carries state across TOPs; reconciling `<rede>` ids misses a dropped Fragestunde turn | Not traced line by line; consistent with the code read | Added to what the implementer must prove. Estimate raised |
| 4 | High | Restored sittings would skip the review the other 400 had | Confirmed | **N8**, owner chose A |
| 5 | High | "Links nobody else offers" is overstated for the excluded years: ParlLawSpeech covers speech to law to 2021, BTVote votes to WP 19. WP 20/21 first is the simpler release | Confirmed in part: no single dataset was found with all of them, and C was in front of the owner, but the N1 brief called these links "the part nobody else offers" | "Why" corrected. Corrected premise put to the owner, who confirmed B. Fallback now has a trigger |
| 6 | Medium | Step 0B reuse claims are overstated; the estimate rested on them | Confirmed | Step 0B corrected; gate writes real reasons; estimate raised |
| 7 | Medium | "Too much refused" has no number. "18/83, 16 markers" looks stale | Confirmed: 18/83 has 0 refused markers, its defects are wrong units. At most 4 per sitting | The bar now says source defect or a defect that cannot be narrowed to single units. 18/83 moved to N7 |
| 8 | Medium | T1 is not an hour. A Rede outside a TOP needs a decided home | Confirmed. `contributions.agenda_item_id` is nullable, `speeches` is not | T1 estimate raised, R9 |
| 9 | Medium | The roll-call licence e-mail comes after the work that leans on votes | Confirmed, `TODOS.md:26` | Roadmap note. Sending is the owner's |
| 10 | Medium | Post-rebuild checks too weak; figures for the 85 are rates from shorter sittings; the 85 were not scanned | Confirmed | Section 9 and T4 tightened |
| 11 | Medium | "Independent build" oversells: same XML, ids only, frozen version | Confirmed | Wording corrected; checklist adds surnames and tokens |
| 12 | Low | `unverified=0` reads cleaner than the estimates under it | Agreed. It counts premises, not figures | Noted |

## Codex plan challenge (2026-11-07)

The owner ran `codex exec` read-only from the terminal, so this is the plan's outside review. Its prompt held the plan before N7 was narrowed and answered, so it did not see those answers. Verdict: revise before implementation, because the gates could pass with identity errors, incomplete accounting and misleading links. Each finding was checked against the code and the A3 store:

| # | Severity | Finding | Checked | Disposition |
| --- | --- | --- | --- | --- |
| 1 | High | Clearing `xml_redner_id` can keep the wrong identity through a trusted abgeordnetenwatch id. The repo already has reviewed partitions | Partly. The mechanism exists and does split person pages, but holds only 11005304. On the five ids the wrong person comes through the xml id: their rows carry `xml:<id>`, and aw_match is `name` or NULL. The lookup at `build_dip_pulse_site.py:1095` does run on the redner id, so a profile can attach upstream | T2 and the TODO now extend the partitions. The running session has the correction |
| 2 | High | Reconciliation assumes a mapping the parser does not have: splits and moved text | Confirmed. 13 speeches with `:N` ids in 11 sittings, 3,419 contributions with `nested:` ids, 18,678 Fragestunde contributions with no `rede_id` | **R11**, added to what the implementer must prove |
| 3 | High | The gate does not check that speech, bill and vote links are right | Partly. Links need the same date and any shared Drucksache (`:2686`, `:2893`). 590 links, 556 votes, 0 across protocols. 13 votes link to more than one TOP, six of them to 4 to 7 Haushalt TOPs (894, 898, 960, 961, 979, 980), and 84 TOPs have more than one vote. Many may be right. Nothing checks them | **N10**, to the owner |
| 4 | High | "Outside all Reden counts" is an unassigned change across readers | Confirmed, with a limit: 20 statements in 3 files. A separate table has its own cost: the sequence slots | **R10**, for `/plan-eng-review` |
| 5 | Medium | No adequacy threshold | Confirmed. Reden withheld per sitting: 1 in 55, 2 in 11, 3 in 2, 4 in 1. Markers by the marker's speaker, who may not own the Rede: LINKE 28, GRÜNE 28, SPD 19, CDU/CSU 14, AfD 5, FDP 5, ministers 4. No shares by words, because the blockers file has no lengths and the XML of the 85 is not on disk | **N9**, to the owner |

## Second pass: required outputs

**NOT in scope.** Deferred: fixes for R7 (`TODOS.md`). Not chased: annotation, WP 1 to 17, ParlaMint encoding, Parquet, §31 declarations as a new dataset (excluded by ADR 0002; they explain votes, so a later pass could reopen it). Contact with other projects: the owner's.

**What already exists.** The idea in `audit_offline_turns.py`; `contributions.kind`; A3's DIP budget and bulk prefetch; `rede_id` as a shared key with CPP-BT.

**Dream state delta.** After this plan the record keeps every sitting it can, says what it leaves out, and has been compared with a second automatic build over the same XML. Still missing against the 12-month ideal: outside readers, citations, and a repeated comparison.

**Failure modes.**

| Capability | Failure | Rescued | Test | User sees | Logged |
| --- | --- | --- | --- | --- | --- |
| Reading `<rede>` | Outside the read path | N | N | Silent. **CRITICAL GAP** | N |
| Annex titles | Other title | N | N | Silent. **CRITICAL GAP** | N |
| Person binding | Shared id | N | N | Wrong person. **CRITICAL GAP** | N |
| Sittings that parse with known wrong units | No refusal, so N1 passes them | N | N | Wrong counts if the list shrinks. **CRITICAL GAP** until N7 A and N8 A are built | N |
| Withholding | Shifts units | unknown | planned | Wrong order | implementer to verify |
| Vote links | Shared Drucksache links the wrong TOP | N | N | Misleading link. **CRITICAL GAP**, N10 | N |
| Fetch of the 85 | DIP stops | Y | Y | Not acquired | Y |

**Task list.**

- [x] **T1 (P1, human ~3 days / CC ~half a day)** Parser: Reden outside a TOP (after R9), annex titles, 21/43. Surfaced by N3. Built on `claude/objective-satoshi-86c7a1`, not landed: 18/49 has 51 ids, Reden 54,718 → 54,747.
- [x] **T2 (P1, human ~1 day / CC ~1 h)** Person binding for shared ids, by extending the reviewed partitions. Surfaced by P6, Codex finding 1. Built on `claude/elated-tereshkova-f657d3`, not landed: the 43 units move, Fraktion figures hold. Still owed: rendered pages not opened; rescan once the 85 are fetched.
- [ ] **T3 (P1, human ~3–4 weeks / CC ~3–5 days, estimated; was ~2 weeks / ~1–2 days)** Withholding per unit, with reconciliation, an ADR and N7's reviewed list of single units, after `/plan-eng-review`, which settles R10 and R11 and re-estimates this task. Surfaced by N1, N6, N7, outside finding 3, Codex findings 2 and 4. Verify: Section 6 rows; the known wrong units in 18/2, 18/29, 18/83 and 19/25 are withheld with a reason.
- [ ] **T4 (P1, human ~4 days / CC ~half a day, estimated, plus DIP time; was ~1 day / ~1 h before N8's review)** Fetch the 85, scan, review restored sittings (N8), rebuild, gate, compare. Follows T3. Verify: votes match the roll-call list date by date; the review has passed, with every wrong unit on the withheld list.
- [ ] **T5 (P1, human ~1 h / CC ~15 min)** `DATA.md` comparison. Surfaced by N4. Verify: doc-link test.
- [ ] **T6 (P2, human ~1 h / CC ~15 min)** Stray Fraktion values. Verify: every Fraktion value is known.

**Stale diagrams.** 0. The Step 0C diagram was updated to "linked".

**Completion summary.** Mode: HOLD SCOPE, by default. Sections 1 to 11 reviewed; Section 3 and 7 no issues. Failure modes: 7 capabilities, 5 critical gaps. Stale diagrams: 0. Scope proposals: 0, by mode. Reality rows 7/7. Outside voice: bounded native fallback, 12 findings; Codex, run by the owner, 5 findings. Lake score: N/A, no scored option was 10/10.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| CEO Review | `/plan-ceo-review` | Scope and strategy | 2 | ISSUES OPEN | Run 1: 17 questions, 16 answered, 1 closed by correction. Run 2, mode HOLD SCOPE: 0 proposals, 5 critical gaps open until built, 2 decisions open (N9, N10) |
| Outside Review | Codex, run by the owner | Independent 2nd opinion | 1 | issues found | 5 findings: 3 confirmed, 2 in part; 2 to the owner, 2 to eng review, 1 corrected T2. Native fallback before it: 12 findings, all resolved |
| Eng Review | `/plan-eng-review` | Architecture and tests (required) | 0 | not run | none |
| Design Review | `/plan-design-review` | UI and UX gaps | 0 | not run | none |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | none |

- **OUTSIDE COVERAGE:** Codex plan challenge: completed 2026-11-07, run by the owner, because the sandbox blocks it here. Its prompt predates the N7 narrowing and the N7 and N8 answers. The owner's two earlier `codex review` runs covered the diff before commit 06defd1 and found no actionable defects. Native fallback (Plan subagent): completed, not outside coverage.
- **REVIEW HISTORY:** not persisted. The sandbox blocks writes to `~/.gstack`, so these rows exist only in this file.
- **VERDICT:** no review is CLEAR. T1 and T2 are built on unmerged branches; T5 and T6 can start. Eng review required before T3, and it settles R10 and R11; T4 follows T3.

**UNRESOLVED DECISIONS:**
- N9: what coverage is adequate.
- N10: a check that the links are right.
- Host provider and reader test pass rule (recorded in TODOS.md).
