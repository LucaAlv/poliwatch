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
| R10 implementer | Codex finding 4; `build_dip_pulse_site.py:3440`; `speeches` UNIQUE(agenda_item_id, sequence) | Withheld units have no storage shape, and no one is assigned the 20 statements that read `speeches` | A flag on `speeches` or a separate table; list every reader | decided | Eng review 2026-11-09, D2 A: a separate `withheld_units` table; D3 B: `speeches.sequence` is the source position |
| R11 implementer | Codex finding 2; `validate_dip_protocol.py:943,1396,1450-1562` | Reconciliation assumes one source id per stored unit, but the parser splits Reden and moves text | Inventory the raw XML before any edit to the tree; a written rule for split-off units and moved text | decided | Eng review 2026-11-09, D4 A: the refused part is withheld; D7 A: text pass 1 moved out stays where it went, reconciled as partly merged |
| N9 owner | Codex finding 5; `TODOS.md` gate step 4 | The bar has no number: a sitting with every Rede withheld would still count as held, and yearly unit totals hide where the loss falls | Every sitting stays in, and the withheld share by words is published per sitting, year and Fraktion. Each analysis on the site declares a minimum coverage and marks a period below it as thin. The owner sets the number after T4 measures | decided | Owner 2026-11-09: "Yes, to analyses". Rejected: a per-sitting bar, which would bring back whole-sitting losses |
| N10 owner | Codex finding 3; `validate_dip_protocol.py:2686,2893` | No test or gate checks that a vote link is right, though links are the stated difference | A reviewed sample of about 150 links before the first release: all 13 votes linked to several TOPs, all 84 TOPs with several votes, 50 random plain links, sharing a pass with N8. The meaning of a link stated in `DATA.md` | decided | Owner 2026-11-09: "Yes, ~150 links". Rejected: all 590. Not answered: fix the matching rule or flag the link; recommended rule where a pattern explains the error, flag for one-offs |

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
                    \-> source file changed since fetch: comparison shows it, C5 may be one
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
| 3 | High | The gate does not check that speech, bill and vote links are right | Partly. Links need the same date and any shared Drucksache (`:2686`, `:2893`). 590 links, 556 votes, 0 across protocols. 13 votes link to more than one TOP, six of them to 4 to 7 Haushalt TOPs (894, 898, 960, 961, 979, 980), and 84 TOPs have more than one vote. Many may be right. Nothing checks them | **N10**, owner chose a ~150-link sample (T7) |
| 4 | High | "Outside all Reden counts" is an unassigned change across readers | Confirmed, with a limit: 20 statements in 3 files. A separate table has its own cost: the sequence slots | **R10**, for `/plan-eng-review` |
| 5 | Medium | No adequacy threshold | Confirmed. Reden withheld per sitting: 1 in 55, 2 in 11, 3 in 2, 4 in 1. Markers by the marker's speaker, who may not own the Rede: LINKE 28, GRÜNE 28, SPD 19, CDU/CSU 14, AfD 5, FDP 5, ministers 4. No shares by words, because the blockers file has no lengths and the XML of the 85 is not on disk | **N9**, owner: the bar applies to analyses, not sittings |

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
| Vote links | Shared Drucksache links the wrong TOP | N | N | Misleading link. **CRITICAL GAP** until T7's review is done | N |
| Fetch of the 85 | DIP stops | Y | Y | Not acquired | Y |

**Task list.**

- [x] **T1 (P1, human ~3 days / CC ~half a day)** Parser: Reden outside a TOP (after R9), annex titles, 21/43. Surfaced by N3. Built on `claude/objective-satoshi-86c7a1`, not landed: 18/49 has 51 ids, Reden 54,718 → 54,747.
- [x] **T2 (P1, human ~1 day / CC ~1 h)** Person binding for shared ids, by extending the reviewed partitions. Surfaced by P6, Codex finding 1. Built on `claude/elated-tereshkova-f657d3`, not landed: the 43 units move, Fraktion figures hold. Still owed: rendered pages not opened; rescan once the 85 are fetched.
- [ ] **T3 (P1, human ~3–4 weeks / CC ~3–5 days, estimated; was ~2 weeks / ~1–2 days)** Withholding per unit, with reconciliation, an ADR and N7's reviewed list of single units, after `/plan-eng-review`, which ran on 2026-11-09: two PRs, refined as tasks W1-W8 in "Eng review: the withholding build". Surfaced by N1, N6, N7, outside finding 3, Codex findings 2 and 4. Verify: Section 6 rows; the known wrong units in 18/2, 18/29, 18/83 and 19/25 are withheld with a reason.
- [ ] **T4 (P1, human ~4 days / CC ~half a day, estimated, plus DIP time; was ~1 day / ~1 h before N8's review)** Fetch the 85, scan, review restored sittings (N8), rebuild, gate, compare. Follows T3. Verify: votes match the roll-call list date by date; the review has passed, with every wrong unit on the withheld list.
- [ ] **T5 (P1, human ~1 h / CC ~15 min)** `DATA.md` comparison. Surfaced by N4. Verify: doc-link test.
- [ ] **T6 (P2, human ~1 h / CC ~15 min)** Stray Fraktion values. Verify: every Fraktion value is known.
- [ ] **T7 (P1, human ~2 days / CC ~2 h, estimated)** Review about 150 vote links and state a link's meaning in `DATA.md`. Surfaced by N10, Codex finding 3. Runs with the N8 review once the 85 are fetched; the 556 votes held today can be reviewed earlier. Verify: every reviewed link is right, fixed or flagged, with the counts reported.

**Stale diagrams.** 0. The Step 0C diagram was updated to "linked".

**Completion summary.** Mode: HOLD SCOPE, by default. Sections 1 to 11 reviewed; Section 3 and 7 no issues. Failure modes: 7 capabilities, 5 critical gaps. Stale diagrams: 0. Scope proposals: 0, by mode. Reality rows 7/7. Outside voice: bounded native fallback, 12 findings; Codex, run by the owner, 5 findings. Lake score: N/A, no scored option was 10/10.

## Eng review: the withholding build, T3 (2026-11-09)

**Target:** T3 as this file and `TODOS.md` "Coverage gate before the first data release" describe it: withholding refused `<rede>` units (N1 B), N7's reviewed list, the reconciliation of every `<rede>` (N6), the storage of withheld units (R10), and the raw XML inventory with rules for split-off units and moved text (R11). Owner decisions N1, N7, N8, N9 and N10 are settled and not reopened here. The fetch of the 85 sittings (T4) and the reviews (N8, T7) are outside this target. Design doc check: the helper found `docs/designs/puls-wochenradar.md` and a CEO plan from another branch, both unrelated; this file's CEO review is the design input.

### Scope Challenge

**What already exists:**
- **Where a refusal is per Rede:** two refusals name one Rede and are raised while it is emitted, after every Rede of the TOP was classified: "unresolved nested question-format speaker at {rid} marker {n}" (`validate_dip_protocol.py:1549`) and "unresolved nested contribution at {rid} marker {n}" (`:1556`). Classification (`classify_reden`, `:1403`) and the merges of pass 1 (`:1418-1505`) run with every Rede present.
- **No state crosses Reden in that loop:** `granted_nested_speaker`, `grant_epoch` and `open_exchange` reset for each Rede (`:1516-1518`). So skipping one Rede's output leaves every other Rede's classification and text as they are.
- **Which refusals cannot be narrowed:** Befragung turns (`speech_kinds.py:396`), Fragestunde markers (`:559`), "conflicting roles" (`:176`) and "nested contribution needs a source rede id" (`validate_dip_protocol.py:1535`). These are raised for a whole TOP or sitting, so such a sitting stays out under the bar.
- **The idea, proven:** `scripts/audit_offline_turns.py` blanks a refused segment and parses on, but only for refusals with a locator (its regex, line 30). It says its partial counts "cannot certify or replace a report/database".
- **A reviewed-list pattern:** `scripts/person_corrections.json`, where an entry the source does not match refuses the build (`person_registry.py`).
- **Ids that already survive a skipped Rede:** speeches and nested Beiträge are keyed by `rede_id` (`stable_ids.py:56-69`). Fragestunde turns are keyed by item and `len(redes)+i` (`validate_dip_protocol.py:1599`), and the Rede list does not change.
- **The version gate:** `require_current_speech_rules` (`persist_dip_pulse_store.py:81-100`) and the exclusion list in `coverage-exclusions.json`, whose reason is always "excluded" (`build_dip_pulse_site.py:678-700`).

**The smallest change:**
1. Before `mark_presidium_fraktionsreden`, `mark_roleless_chairs` and `split_nested_reden` edit the tree, record every `<rede id>` under `sitzungsverlauf` and in the annexes.
2. In the per-Rede loop, catch the two located refusals, hold that Rede back with its reason, and undo what it already added: nested units (`:1572`) and `merged_zwischenfrage` diagnostics (`:1566`). Then go on with the next Rede. Every other refusal still refuses the sitting.
3. Apply the reviewed list (N7, then N8) at the same point.
4. At the end of `parse_protocol_xml`, give each inventoried id one status: stored, merged into another unit, procedural, withheld with a reason, or excluded by a named rule. Any id left over refuses the sitting. Fragestunde markers are counted against emitted turns.
5. Store, export and document the withheld units, publish coverage by words (N9), and give `coverage-exclusions.json` real reasons.

**Complexity, estimated:** about 12 files: `validate_dip_protocol.py`, `persist_dip_pulse_store.py`, `build_dip_pulse_site.py`, `data_dictionary.json`, a new reviewed list, `compare_store_values.py`, `validate_store_gate.py`, `CONTEXT.md`, `docs/data-methods.md`, a new ADR 0005, a new test file, and `tests/test_daten_export.py`. No new classes. This trips the 8-file gate.

**Search check:** no new infrastructure, concurrency or framework pattern; standard library only. Not searched.

**TODOS cross-reference:** blocked by "Reden the parser drops without refusing", built on `claude/objective-satoshi-86c7a1`. Reconciliation would refuse 18/49, 18/44, 18/133 and 18/134 until that lands. The shared speaker id fix on `claude/elated-tereshkova-f657d3` is independent. T4, N8 and T7 follow this build.

**Reality rows.** Premises:

| Premise | Receipt | Verdict |
| --- | --- | --- |
| The two located refusals are raised per Rede, after classification | `validate_dip_protocol.py:1403,1549,1556` | true |
| Exchange state resets per Rede | `validate_dip_protocol.py:1516-1518` | true |
| The 103 refused markers of round 2 are all located refusals | `audit_offline_turns.py:30` reads only those; `a3-wp18-19-round2-blockers.tsv` | true |
| 20/11 is a located refusal | `a3-phase3.md:323` | true |
| `speeches.sequence` is the position among stored speeches | `persist_dip_pulse_store.py:1248` | true |
| Nested Beiträge take `max+1` sequences | `validate_dip_protocol.py:1612` | true |
| The store has no synthetic speech ids | A3 store, `rede_id NOT LIKE 'ID%'`: 0 of 54,718 [measured 2026-11-09] | true |
| 20 statements read `speeches` | code map, 2026-11-09 | true |
| Once its located refusals are withheld, each of the 69 sittings parses | XML of the 85 not on disk | unverified |

REALITY: premise-table finding 9 premises, unverified=1 (the 69 sittings parse once withheld) `docs/plans/a3-wp18-19-round2-blockers.tsv:1`
REALITY: already-done pass local main 58d343d has no later change to the parser or persist; github.com is blocked in the sandbox, so origin was not fetched `scripts/validate_dip_protocol.py:1358`
REALITY: surface-check pass `--exclude-document-number`, `--include-document-number`, `--offline`, `--repersist`, `--backfill-incomplete` exist in `--help` `scripts/build_dip_pulse_site.py:13654`
REALITY: binding-decisions pass decision search empty; N1 B, N7 A, N8 A, N9, N10, decision 0 of 2026-10-22, ADR 0002 and ADR 0004 bind this build `docs/plans/v1-scope-review.md:291`
REALITY: numbers pass 87 Reden, 103 markers, 69 sittings [measured: blockers tsv]; 20 readers [measured: code map]; efforts [estimated] `docs/plans/a3-wp18-19-round2-blockers.tsv:1`
REALITY: deferred-asks pass no linked issue `TODOS.md:48`
REALITY: pr-count finding no `.gstack/ship-policy.json`, so one PR per wave by default; D1 asks whether to split, at the cost of one more ship gate `TODOS.md:48`

**Scope Challenge findings:**

1. [P1] (confidence: 9/10) `persist_dip_pulse_store.py:1248` and `validate_dip_protocol.py:1612`: the plan requires that withholding leave "every other unit's id, sequence and text unchanged" (`TODOS.md:63`). Ids and text hold, but `speeches.sequence` is `enumerate` over stored speeches and nested Beiträge take `max+1`, so later units in the same TOP renumber. Every reader uses sequence only to order (`build_dip_pulse_site.py:8986`, `:9016`, `facts.py:391`). Decision D3.
2. [P1] (confidence: 9/10) R10: where withheld units live. Decision D2.
3. [P1] (confidence: 8/10) R11: the unit withheld. The parser raises on the Rede of the edited tree, which can be a split part (`ID1801002600:2` in the blockers file), and the plan's count of 87 is at that grain. Decision D4.
4. [P1] (confidence: 9/10) The implementer's proof "each refusal class has a home" (`TODOS.md:64`) is answered: two located classes are withheld per Rede, and every other class keeps its sitting out. Factual correction, recorded; no decision.
5. [P1] (confidence: 8/10) `validate_dip_protocol.py:1566,1572,1511-1515`: a withheld Rede must undo its nested units and diagnostics, take text merged into it along, and give merged-in sources the status "merged into a withheld unit". Required to meet the approved contract; recorded, no decision.
6. [P2] (confidence: 8/10) `persist_dip_pulse_store.py` `resolve_speaker`: a withheld unit binds no person, so it adds nothing to a person page. Follows from "outside all Reden counts"; recorded.
7. [P2] (confidence: 7/10) `stable_ids.py:51-57`: a speech with no XML id takes a synthetic id from the stored sequence, so withholding could change it. The store has none today [measured]. A test asserts that a withheld Rede never precedes an id-less speech unchanged; recorded.
8. [P2] (confidence: 6/10) One of the 84 listed WP 18/19 sittings is neither among the 69 with markers, nor among the 13 that parse, nor 18/20. Its reason is not known until T4 fetches it. The bar covers it either way; recorded for T4.

### Decision ledger (eng review)

#### S1: delivery arrangement
Finding: Scope Challenge complexity, about 12 files, reviewer: this review
Plan baseline: T3 as one task (`docs/plans/v1-scope-review.md`, task list T3), no arrangement approved
Runtime evidence: none; proposed work
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| S1 arrangement | one task, about 12 files | one PR, 12 files | PR 1: inventory and reconciliation (`validate_dip_protocol.py`, a new test file, `docs/data-methods.md`); PR 2: withholding, storage, export, list, ADR (the other 9 files plus tests) |
| Features | N1 B, N6, N7 list, R10, R11, N9 coverage, exclusion reasons | unchanged | unchanged |
| R10, R11, D3 | pending | pending | pending |

Question D1:
D1: One PR or two for the withholding build?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3) of the v1 scope review.
ELI10: The build has two halves. One checks that every Rede in the XML ends up somewhere, and refuses a sitting where one vanishes. The other holds a refused Rede back instead of losing the whole sitting. The first half is useful alone, and it is the check the second half is proven against.
Stakes if we pick wrong: one large PR is harder to review and ships the safety check untried; two PRs cost one more ship gate.
Recommendation: B because the reconciliation is the net the withholding must pass through, and it would have caught the 45 lost units on its own.
Note: options differ in kind, not coverage — no completeness score.
Pending remedies not decided here: R10 (D2), D3 sequence, R11 (D4).
Pros / cons:
A) Original arrangement
  ✅ One ship gate and one review of about 12 files, so the whole design is read together.
  ✅ No ordering to manage between two PRs that both touch the parser module.
  ❌ The reconciliation reaches production only together with withholding, so neither is tried alone.
B) Smaller arrangement (recommended)
  ✅ PR 1 is 3 files and refuses any sitting that drops a Rede silently, from the day it lands.
  ✅ PR 2 then adds one more reconciliation status, withheld, against a check already in use.
  ❌ One more ship gate (review plus the owner's Codex run), and PR 1 must land after the Reden fix.
Net: one review of everything, against an earlier and separately tested safety check.
Header: Structure
Options:
A) Original arrangement
One PR with all 12 files: inventory, reconciliation, withholding, the withheld table, export, the reviewed list and ADR 0005. One ship gate; the reconciliation is first used together with withholding.
B) Smaller arrangement
Two PRs. PR 1: the raw XML inventory and the reconciliation in `validate_dip_protocol.py`, a new test file, `docs/data-methods.md`; it lands after the Reden fix. PR 2: withholding, storage, export, the reviewed list and ADR 0005. One more ship gate.

State: approved
Actual answer: B) Smaller arrangement, answered 2026-11-09 by the owner's adjudicator hook (plan-tune auto-decide): "Two PRs is a delivery-sequencing choice that is cheap to reverse … the reconciliation is the net the withholding must pass through"
Accepted scope: two PRs. PR 1: raw XML inventory and reconciliation in `validate_dip_protocol.py`, a new test file, `docs/data-methods.md`; lands after the Reden fix. PR 2: withholding, storage, export, the reviewed list, ADR 0005
History: none

**Scope record:** feature answers: none proposed; structure: B (D1, adjudicator, 2026-11-09); accepted scope: all features of T3 as listed under Target, in two PRs; pending remedies: R10 (D2), sequence (D3), R11 (D4). Scope Challenge result: scope accepted as-is.

#### R10: where withheld units are stored
Finding: Scope Challenge 2, P1, confidence 9/10, `build_dip_pulse_site.py:3440` and 19 more readers of `speeches`, reviewer: Codex finding 4 and this review
Plan baseline: "withheld, flagged with a reason, text kept, outside all Reden counts" (N1 B, `TODOS.md:51`); shape not approved
Runtime evidence: 20 statements read `speeches` in `build_dip_pulse_site.py` (8), `facts.py` (6), `compare_store_values.py` (6); 6 read `contributions`; no reason or status column exists on either table [code map 2026-11-09]
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R10 storage | pending | new table `withheld_units`: protocol, TOP, `rede_id`, source position, reason code and detail, printed speaker and Fraktion, page, characters, words, text; `speeches` and `contributions` unchanged; exported as `withheld_units.csv` | `withheld_reason` column on `speeches` and `contributions`; every reader filters on it |
| S1 arrangement | approved B (D1) | B | B |
| D3 sequence, R11 grain | pending | pending | pending |

Question D2:
D2: Where should withheld Reden be stored?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3), PR 2.
ELI10: A withheld Rede keeps its text but must not count anywhere. Twenty queries count rows of the speeches table today: the recipes, Fakten, the comparison script. If withheld Reden sit in that table with a flag, each query has to remember to skip them, and one that forgets counts them silently.
Stakes if we pick wrong: a recipe or page counts Reden the dataset says it withholds, and nothing catches it.
Recommendation: A because the existing 20 readers stay correct by construction, and a researcher still gets every withheld Rede in its own CSV.
Completeness: A=9/10, B=6/10
Pros / cons:
A) A separate withheld table (recommended)
  ✅ No existing query changes, so no count can pick up a withheld Rede by mistake.
  ✅ Coverage, DATA.md and the CSV read one small table for the withheld counts and words.
  ❌ A reader who wants every Rede, withheld or not, has to join two tables.
B) A flag on speeches and contributions
  ✅ Every Rede of a sitting stays in one table, in source order, with one schema.
  ✅ Releasing a Rede later is one column update instead of a move between tables.
  ❌ All 20 readers and every future one must filter, and a missed filter miscounts silently.
Net: safety of the existing counts against keeping every Rede in one table.
Header: Storage
Options:
A) Separate table
New table `withheld_units` with protocol, TOP, `rede_id`, source position, reason, printed speaker and Fraktion, page, characters, words and text; `speeches` and `contributions` unchanged; exported as `withheld_units.csv`, described in DATA.md. Effort: human ~1 day / CC ~1 h, estimated.
B) Flag on speeches
A `withheld_reason` column on `speeches` and `contributions`; each of the 20 readers and every new one filters on it, with a test per reader. Effort: human ~2 days / CC ~2 h, estimated.

State: approved
Actual answer: A) Separate table, answered 2026-11-09 by the owner's adjudicator hook: "a separate table satisfies that by construction … The cost is a join for anyone who wants every Rede"
Accepted scope: new table `withheld_units` (protocol, TOP, `rede_id`, source position, reason code and detail, printed speaker and Fraktion, page, characters, words, text); `speeches` and `contributions` unchanged; `withheld_units.csv` in the export and DATA.md. In PR 2
History: none

#### D3: what "unchanged" means for sequence
Finding: Scope Challenge 1, P1, confidence 9/10, `persist_dip_pulse_store.py:1248`, `validate_dip_protocol.py:1580,1612`, reviewer: this review
Plan baseline: "withholding one unit leaves every other unit's id, sequence and text unchanged" (`TODOS.md:63`, CEO review)
Runtime evidence: `speeches.sequence` is the position among stored speeches (`enumerate`, `:1248`); a Rede stored as a Beitrag takes its position among all Reden of the TOP (`:1580`); nested Beiträge take `max+1` (`:1612`); Fragestunde turns take `len(redes)+i` (`:1599`). Readers use sequence only to order (`build_dip_pulse_site.py:8986`, `:9016`, `facts.py:391`). Synthetic speech ids use it too (`stable_ids.py:51-57`), 0 in the store
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| D3 sequence contract | ids, sequence and text unchanged (plan); code renumbers later speeches and nested Beiträge | ids, text, speaker and kind unchanged; sequence is an order and may renumber within a withheld Rede's TOP; DATA.md says so | `speeches.sequence` becomes the Rede's position among the TOP's `<rede>` elements, the space rede-based Beiträge already use; nothing renumbers except nested Beiträge of that TOP, whose ids stay |
| Store-wide values | n/a | no stored value changes | every `speeches.sequence` after a Beitrag-labelled or procedural Rede changes once, reported old/new |
| S1, R10 | approved B (D1), A (D2) | unchanged | unchanged |
| R11 grain | pending | pending | pending |

Question D3:
D3: Should a withheld Rede renumber the Reden after it?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3), PR 2.
ELI10: Each Rede has a number for its place in the debate. Today speeches are numbered 1, 2, 3 among the speeches that were stored, so taking one out renumbers everything after it. Beiträge made from a Rede are already numbered by their place among all Reden. The plan promised that withholding changes no other unit's number.
Stakes if we pick wrong: a researcher's cited position of a Rede changes when a neighbour is withheld now or released by a later parser rule.
Recommendation: B because it keeps the plan's promise for speeches at a small one-time cost, and puts speeches and Beiträge in one order a reader can merge.
Completeness: A=7/10, B=9/10
Pros / cons:
A) Order only, may renumber
  ✅ No stored value changes today, and persist stays as it is.
  ✅ Ids, text, speaker and kind still never change, which is what identity rests on.
  ❌ Breaks the plan's promise: a release that withholds or frees a Rede renumbers its neighbours.
B) Source position for speeches (recommended)
  ✅ Withholding or releasing a Rede never renumbers a speech or a rede-based Beitrag.
  ✅ Speeches and rede-based Beiträge share one source order, so a reader can interleave them.
  ❌ Every stored speech sequence after a Beitrag or procedural Rede changes once, which must be reported.
Net: no change today against numbers that stay put across later releases.
Header: Sequence
Options:
A) Order only
Keep `speeches.sequence` as the position among stored speeches; withholding renumbers later speeches and nested Beiträge in that TOP; DATA.md says sequence is an order, not an identifier. Tests assert ids, text, speaker and kind unchanged. Effort: none beyond the docs.
B) Source position
`speeches.sequence` becomes the Rede's position among the TOP's `<rede>` elements, as rede-based Beiträge have now; nested Beiträge may still renumber within the TOP, their ids unchanged. Report old and new sequence counts once. Effort: human ~half a day / CC ~30 min, estimated.

State: approved
Actual answer: B) Source position, answered 2026-11-09 by the owner's adjudicator hook: "Source position fixes that and matches rede-based Beiträge … a one-time shift in stored sequences is a cost of the work only"
Accepted scope: `speeches.sequence` is the Rede's position among the TOP's `<rede>` elements (the report carries it; persist stores it); nested Beiträge may renumber within the TOP, ids unchanged; old and new sequence counts reported once. In PR 2
History: none

#### R11: the unit a refusal withholds
Finding: Scope Challenge 3, P1, confidence 8/10, `validate_dip_protocol.py:943,1396,1507`, reviewer: Codex finding 2 and this review
Plan baseline: "withhold only refused `<rede>` units" (N1 B, owner 2026-11-07); "withholding works on the whole `<rede>`, as decided. After round 2's rules that means 87 Reden" (`TODOS.md:69`)
Runtime evidence: `split_nested_reden` (`:943`, called at `:1396`) moves the tail of a `<rede>` into a new `<rede id="{outer}:{marker}">`; the per-Rede loop runs over that edited list (`:1507`) and raises on one of its entries. The blockers file names such parts, e.g. `ID1801002600:2` (Liebich's Kurzintervention); its 87 distinct ids are at this grain [measured]
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| R11 grain | pending | the Rede the parser raised on, after the split: a split part alone, or the outer Rede when the marker is in it; with its nested Beiträge and any text merged into it; the outer id reconciles through its parts | the whole `<rede>` of the raw XML, with every part split from it |
| Withheld count after round 2 | 87 (`TODOS.md:69`) | 87 [measured: blockers tsv] | at least 87, more where a refused part belongs to a longer outer Rede [not measured] |
| S1, R10, D3 | approved B, A, B | unchanged | unchanged |

Question D4:
D4: When a split-off part is refused, what is withheld?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3), PR 2.
ELI10: The parser sometimes cuts one XML Rede into parts, for example when a Kurzintervention by another member sits inside someone's speech. A refusal can then fall on just that part. We can hold back only the part that failed, or the whole original Rede with the speech around it.
Stakes if we pick wrong: either correctly parsed speech is withheld for no reason, or the grain differs from the 87 the plan was costed on.
Recommendation: A because it matches how the parser sees units and the measured 87, and keeps the surrounding speech that nobody questioned.
Completeness: A=9/10, B=7/10
Pros / cons:
A) The refused part (recommended)
  ✅ Withholds exactly what failed, so the other speaker's correctly parsed Rede still counts.
  ✅ Matches the 87 Reden the plan and the coverage figures were measured at.
  ❌ The raw XML id can then be partly stored and partly withheld, which the reconciliation must show.
B) The whole XML Rede
  ✅ One raw XML id is always either fully stored or fully withheld, which reads simply.
  ✅ No outer Rede is ever shown without a part the source printed inside it.
  ❌ Withholds speech by a second member who did nothing wrong, and the count is no longer 87.
Net: precision of what is withheld against one status per raw XML id.
Header: Grain
Options:
A) Refused part
Withhold the Rede the parser raised on as it stands after the split, with its nested Beiträge and any text merged into it; the outer id reconciles through its parts, each stored or withheld. Effort: included in PR 2's estimate.
B) Whole XML Rede
Withhold the raw `<rede>` with every part split from it; each raw id is fully stored or fully withheld. Effort: about the same; the withheld count must be re-measured at T4.

State: approved
Actual answer: A) Refused part, answered 2026-11-09 by the owner's adjudicator hook: "N1's wording … is met by a split part, which is a <rede> element after split_nested_reden … It is cheap to reverse before release"
Accepted scope: withhold the Rede the parser raised on as it stands after the split, with its nested Beiträge and any text merged into it; the outer id reconciles through its parts. In PR 2
History: none

**Scope Challenge dispositions:** 1 accepted (D3 B). 2 accepted (D2 A). 3 accepted (D4 A). 4 factual correction, recorded. 5 required by the approved contract, recorded as PR 2 work and tests. 6 required by "outside all Reden counts", recorded. 7 covered by D3: synthetic ids now take the source position, so withholding cannot change one. 8 recorded for T4.

### Section 1: Architecture

```
parse_protocol_xml(xml)                                   PR 1 | PR 2
  ET.fromstring
  inventory: every <rede id> in sitzungsverlauf + anlagen   [1]
  mark_presidium_fraktionsreden, mark_roleless_chairs (edit tree)
  per TOP:
    split_nested_reden (edit tree: id -> id, id:N)
    classify_reden, pass 1 merges (all Reden present)
    pass 2, per Rede (state resets, :1516-1518):
      on the reviewed list? ------------------------------> withheld  [2]
      emit into local lists
        located refusal (:1549, :1556) -> drop local lists -> withheld [2]
        other refusal -> raise, sitting refused (unchanged)
      commit local lists (speech or Beitrag, nested, diagnostics)
    Fragestunde turns; markers counted against turns        [1]
  reconcile: each inventoried id -> stored | merged into X |
    procedural | withheld(reason) | excluded by rule;
    leftover id -> raise, sitting refused                   [1]
report -> persist: speeches (sequence = source position),
  contributions, withheld_units -> export, DATA.md, Daten   [2]
```

Findings, most severe first:

1. [P1] (confidence: 8/10) `build_dip_pulse_site.py:278-281,14847`: today a located refusal in a new sitting aborts the run (D4: "no staged store may replace accepted data"). After PR 2 the same refusal withholds one Rede and the run goes on, so the automatic weekly main release would carry a withheld Rede nobody has looked at. Decision D5.
2. [P1] (confidence: 8/10) `persist_dip_pulse_store.py:81-100`, `speech_kinds.py:24`: PR 2 changes stored output for sittings already held (D3 sequences) and adds a table, so the speech rule version, schema and export format all move. The Reden fix takes rule 7, and main is at schema 11 and export 16. Take the numbers when PR 2 is built, after both fix branches land, because format numbers collided twice before. Required; recorded.
3. [P1] (confidence: 8/10) `build_dip_pulse_site.py:678-700,14598-14603`: the exclusion list is consulted before acquisition and validates only `document_number`, with the reason always "excluded". Gate step 4 is approved: PR 2 requires a reason that is not "excluded" and names a source defect or a defect that cannot be narrowed. The 69 sittings, 20/11 and the N7 four leave the list at T4. Required; recorded.
4. [P2] (confidence: 8/10) `build_dip_pulse_site.py:1956-1963`: offline replay re-parses cached XML through the same `parse_protocol_xml`, and the reviewed list is a repository file, so replay and a fresh run withhold the same units. A test pins this. Recorded.

#### D5: a newly withheld Rede in an automatic release
Finding: Section 1 finding 1, P1, confidence 8/10, `build_dip_pulse_site.py:278-281`, reviewer: this review
Plan baseline: main releases are published automatically per Sitzungswoche "only if every check passes" (`PRODUCT.md`, Release stages); N1 B withholds refused Reden; no rule for new ones
Runtime evidence: a located refusal raises `DipError(source_rejected=True)` and the run returns 1 (`:278-281`, `:14847`), so no release is published today
Comparison grid:

| Choice | Current | A | B |
| --- | --- | --- | --- |
| D5 new withheld Rede | run aborts, no release | release goes out; each newly withheld Rede is listed in the run summary and the release's data changelog, with its reason and the N9 shares | automatic release stops until the owner confirms each newly withheld Rede on the reviewed list |
| S1, R10, D3, R11 | approved B, A, B, A | unchanged | unchanged |

Question D5:
D5: Should a newly withheld Rede stop the automatic weekly release?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3), PR 2.
ELI10: Today, when the parser cannot read one Rede of a new sitting, the whole run stops and no weekly release goes out. After this build it will hold that Rede back and carry on. The question is whether the weekly release still waits for you to look, or goes out and lists what was held back.
Stakes if we pick wrong: either one odd Kurzintervention stops the weekly release, the problem N1 solved, or withheld Reden pile up unseen.
Recommendation: A because a withheld Rede is already outside every count and named with its reason, so listing it keeps the release honest without stopping it.
Completeness: A=8/10, B=9/10
Pros / cons:
A) Release and list (recommended)
  ✅ The weekly release keeps its schedule, and every count already leaves the withheld Rede out.
  ✅ Each new withheld Rede shows in the run summary and data changelog, so nothing is silent.
  ❌ A withheld Rede reaches a release before anyone has read it.
B) Stop until confirmed
  ✅ Every withheld Rede in any release has been looked at by the owner first.
  ✅ A new parser gap is noticed the day it appears, not at the next stable review.
  ❌ One refused Kurzintervention stops the weekly release until the owner acts.
Net: release cadence against an owner look at each new withheld Rede.
Header: New withheld
Options:
A) Release and list
The automatic release goes out; each newly withheld Rede is listed in the run summary and the release's data changelog with its reason, and the N9 shares are updated. The stable-release checklist reviews them. Effort: human ~half a day / CC ~30 min, estimated.
B) Stop until confirmed
The automatic release stops while any withheld Rede is not on the reviewed list; the owner confirms it there, then the release goes out. Effort: human ~1 day / CC ~1 h, estimated.

State: approved
Actual answer: A) Release and list, answered 2026-11-09 by the owner's adjudicator hook: "Stopping on every new withheld Rede would bring back the whole-sitting abort that N1 B was chosen to remove … It is cheap to reverse before release"
Accepted scope: the automatic release goes out; each newly withheld Rede is listed in the run summary and the release's data changelog with its reason; the N9 shares are updated; the stable-release checklist reviews them. In PR 2
History: none

**Section 1 dispositions:** 1 accepted (D5 A). 2, 3 and 4 required by approved work, recorded as PR 2 tasks.

### Section 2: Code quality

1. [P2] (confidence: 8/10) `validate_dip_protocol.py:1549,1556` and `audit_offline_turns.py:30`: the audit script recognises a located refusal by matching the message text. PR 2 should raise a typed subclass of `ValueError` carrying `rede_id`, marker and message at those two lines, and catch that type. A reworded message must not quietly turn a withheld Rede into a refused sitting, or the reverse. Existing tests that match the message keep working, because it stays a `ValueError` with the same text. Required for the approved withholding to be explicit; recorded.
2. [P2] (confidence: 8/10) `validate_dip_protocol.py:1566,1572,1577,1579`: the loop appends to `nested_units`, `diagnostics`, `speeches` and `contributions` as it goes. PR 2 collects each Rede's output in local lists and commits them only when the Rede finishes, so a withheld Rede leaves nothing behind. The alternative, undoing partial appends, is easier to get wrong. Recorded.
3. [P2] (confidence: 7/10) Reason codes: `refused_nested_contribution`, `refused_nested_question_speaker`, and `reviewed` with the list entry's note. A fixed set, documented in DATA.md, so the N9 shares can be grouped by reason. Recorded.
4. [P3] (confidence: 7/10) `scripts/audit_offline_turns.py` duplicates what PR 2 does inside the parser and says its counts cannot certify a store. Proposed for retirement under TODOS below.

Shared code: no extraction proposed. The reviewed list reuses the pattern of `person_corrections.json` (an entry the source does not match refuses), not its code, because the two lists key on different things.

**Section 2 dispositions:** 1 to 3 recorded as PR 2 implementation requirements; 4 goes to the TODO decision.

### Section 3: Tests

Framework: `unittest` (`python3 -m unittest`), 2,138 tests on this branch. Coverage map for the planned paths:

```
CODE PATHS                                              STATUS
PR 1  inventory (raw <rede> ids, sitzungsverlauf+anlagen)  [GAP] new
      reconcile: stored / merged into X / procedural /
        excluded by rule (§31, reprint, annex)            [GAP] new, one row per status
      reconcile: leftover id -> sitting refused           [GAP] new
      Fragestunde markers vs emitted turns                 [GAP] new
      all held sittings reconcile (replay)                 [GAP] -> D6
PR 2  located refusal :1556 -> withheld, run continues     [GAP] new (test_a3_rule5 pins the raise today)
      located refusal :1549 -> withheld                    [GAP] new
      other refusals still refuse the sitting              [★★ TESTED] test_a1_followups.py:734, test_speech_kinds.py:367; extend
      rollback: nested units, diagnostics of the Rede      [GAP] new
      text merged into a withheld Rede goes with it        [GAP] new
      split part refused -> only that part withheld (D4)   [GAP] new
      reviewed list: listed Rede withheld                  [GAP] new
      reviewed list: entry the sitting lacks -> refuse     [GAP] new
      speeches.sequence = source position (D3)             [GAP] new; existing persist tests to update
      withheld_units persisted, no person bound            [GAP] new
      export: withheld_units.csv, DATA.md, coverage words  [GAP] extend test_daten_export.py
      exclusion reason required, not "excluded"            [GAP] extend test_backfill.py:561-640
      new withheld Rede listed in run summary (D5)         [GAP] new
      replay == fresh for withheld units                   [GAP] extend offline-v5 fixtures
      other units unchanged when one Rede is withheld      [GAP] -> D6
USER FLOWS
      researcher sums Reden per Fraktion: withheld absent, [GAP] export test
        listed in withheld_units.csv
      Daten page shows withheld counts and words share     [GAP] render test
      operator replays the store after the version bump    [★★ TESTED] require_current_speech_rules tests; extend

COVERAGE: 2/21 paths tested today (both need extending) | GAPS: 19, 2 settled by D6
```

Legend: ★★★ behavior + edge + error | ★★ happy path | [GAP] no test

Regression risk, CRITICAL: PR 1 and PR 2 both change the parser that produced every held sitting. Decision D6 sets the contract.

#### D6: regression contract for the 716 held sittings
Finding: Section 3, regression rule, P1, confidence 9/10, `validate_dip_protocol.py:1358-1615`, reviewer: this review
Plan baseline: "withholding one unit leaves every other unit's id, sequence and text unchanged" (`TODOS.md:63`), sequence as settled by D3
Runtime evidence: `scripts/compare_store_values.py` compares two stores (`--cohort shared`); offline repersist of the A3 store takes about 22 minutes [measured 2026-11-05]; no test withholds a Rede today
Comparison grid:

| Choice | Current | A | B | C |
| --- | --- | --- | --- | --- |
| D6 contract | none | replay on the A3 store before and after each PR: 0 moved values except `speeches.sequence` (counted); PR 1 refuses none of the held sittings; plus a script that withholds one Rede per TOP in every WP 18/19 sitting held and asserts every other unit unchanged | the replays only, no withhold-one check | fixture unit tests only |
| S1, R10, D3, R11, D5 | approved | unchanged | unchanged | unchanged |

Question D6:
D6: How should we prove the build changes nothing it should not?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3), PR 1 and PR 2.
ELI10: Both PRs change the parser that produced all 716 sittings we hold. The promise is that the only differences are the intended ones: new sequence numbers and the withheld Reden. Unit tests on small fixtures cannot show that across real sittings. A replay of the whole store can, and a second script can withhold one Rede in each debate and check nothing else moved.
Stakes if we pick wrong: a held sitting quietly loses or changes a unit and the release says nothing.
Recommendation: A because the promise is about every held sitting, and the withhold-one check is the only direct proof of N1's central claim.
Completeness: A=10/10, B=8/10, C=5/10
Pros / cons:
A) Replays plus withhold-one check (recommended)
  ✅ Proves on all held sittings that only sequence numbers move, and that PR 1 refuses none of them.
  ✅ Directly tests that withholding one Rede leaves every other unit exactly as it was.
  ❌ About 22 minutes per replay plus the withhold-one run, outside the unit suite.
B) Replays only
  ✅ Catches any moved value in the held sittings at about half the run time.
  ✅ Uses the existing comparison script with no new tooling.
  ❌ The held sittings have no refusals, so the replay never exercises withholding next to other units.
C) Fixture tests only
  ✅ Fast, and runs in CI with every change.
  ✅ No dependence on a local store.
  ❌ Small fixtures cannot show that 716 real sittings are unchanged.
Net: proof across every held sitting against run time outside CI.
Header: Regression
Options:
A) Replays plus check
Replay the A3 store before and after each PR with `compare_store_values.py --cohort shared`: 0 moved values except `speeches.sequence`, counted; PR 1 refuses no held sitting. Plus a script that withholds one Rede per TOP across the WP 18/19 sittings held and asserts every other unit's id, text, speaker, kind and rede-based sequence unchanged. Effort: human ~1 day / CC ~2 h plus run time, estimated.
B) Replays only
The same before-and-after replays with 0 moved values except `speeches.sequence`; no withhold-one script. Effort: human ~half a day / CC ~1 h plus run time, estimated.
C) Fixture tests only
Unit tests on fixtures for each path in the coverage map; no store replay. Effort: included in the test work.

State: approved
Actual answer: A) Replays plus check, answered 2026-11-09 by the owner's adjudicator hook: "a replay alone … never exercises withholding next to other units … Only the withhold-one script tests that claim directly"
Accepted scope: before and after each PR, replay the A3 store and compare with `compare_store_values.py --cohort shared`: 0 moved values except `speeches.sequence` (counted); PR 1 refuses no held sitting. In PR 2, a script withholds one Rede per TOP across the WP 18/19 sittings held and asserts every other unit's id, text, speaker, kind and rede-based sequence unchanged
History: none

**Section 3 dispositions:** the 19 gaps are required proof of approved behavior and go into the tasks below; the regression contract is D6 A. Test plan artifact: `test-plan` file under the review state directory (see Review log below).

### Section 4: Performance

1. [P3] (confidence: 7/10) The inventory and the reconciliation are one more pass over each sitting's tree and its units, linear in the units of one sitting (largest about 300 Reden) [estimated]. No query, cache or loop over the store is added. Negligible.
2. [P3] (confidence: 7/10) The withhold-one script parses each WP 18/19 sitting held once per TOP, about 400 sittings and a few thousand TOPs [estimated]. That is minutes to tens of minutes, run before ship, not in the unit suite. Recorded.

No issues that need a decision.

### Outside voice (2026-11-09)

Codex could not start in the sandbox: "failed to initialize in-process app-server client: Operation not permitted", and `ab.chatgpt.com` was blocked. The bounded native fallback ran instead: one Plan subagent with a five-minute timer, which reported in 86 seconds. It is not outside coverage. Its prompt held the plan cut to 30 KB, so the end of Section 4 was missing. It read `validate_dip_protocol.py:1380-1620`, `persist_dip_pulse_store.py:1241-1260`, `stable_ids.py:45-72`, `audit_offline_turns.py:20-40` and the blockers file.

OUTSIDE VOICE (Claude subagent), condensed; each item checked here:

| # | Severity | Finding | Checked | Disposition |
| --- | --- | --- | --- | --- |
| 1 | High | Pass 1 moves text out of a Rede before pass 2 decides: `merged_rede` to the previous Rede, `merged_erwiderung` to the reply. A resumed Rede gives its resumed text to the previous Rede, and its remaining segments are marked `unsupported_reply` and raise at `:1556`. Withholding it leaves the moved text stored, and the plan has no rule for that | Confirmed, `validate_dip_protocol.py:1491,1499,1501-1503,1505` | **D7** |
| 2 | High | The one unverified premise, and the fallback trigger, can be tested before the build. Fetching the XML of the 85 is about 85 requests, not 2,200, and `audit_offline_turns.py` runs on it | Confirmed: `fetch_missing_xml` (`build_dip_pulse_site.py:1970`) needs no DIP key | **D8** |
| 3 | Medium | D5 A removes the only stop on parser drift in new sittings: a regression shows up only as more withheld units | Confirmed in kind. Reopens D5 on a new risk | **D9** |
| 4 | Medium | D3's "position among the TOP's `<rede>` elements" must mean after the split, the space Beiträge already use (`:1507`, `:1580`), not the PR 1 inventory. The report has no `sequence` on speeches today | Confirmed | Clarification of D3's accepted scope, recorded under D3: the position after `split_nested_reden`; the report gains the field; the synthetic-id test stays |
| 5 | Medium | `pages.append(page_ref)` runs before the refusal, so a withheld Rede's page stays in the TOP's page span. Commit-on-finish must be required | Confirmed, `:1520-1522` | The page stays in the span on purpose: the page range describes the printed source, and the withheld Rede is printed there. Commit-on-finish is required (Section 2 item 2) |
| 6 | Medium | Withholding the whole edited-tree Rede can cost a long speech: 18/1 `ID1800100100` is the Alterspräsident's opening speech, held back for a one-sentence election acceptance. The 87 understates the words withheld | Confirmed, blockers file row 1 | The ADR states it. The words withheld are measured on the fetched XML (D8) before the owner sets the N9 minimum |
| 7 | Low | Pass 1 reads neighbouring Reden (`reply`, `resumed`), so "no state crosses Reden" holds only for pass 2 | Confirmed. Withholding removes no Rede from `redes`, so pass 1 sees the same neighbours | D6's withhold-one script must also pick Reden next to a Kurzintervention/Erwiderung pair and next to a resumed pair. Recorded as required proof |
| 8 | Low | The audit script must switch to the typed exception in the same PR if it is kept | Confirmed | Goes with the TODO decision on the script |

Cross-model tension: none with the native review's settled choices except D5, which finding 3 reopens. Findings 1 and 2 are new.

#### D7: text pass 1 moved out of a withheld Rede
Finding: outside voice 1, High, confidence 9/10, `validate_dip_protocol.py:1491,1499,1505`, reviewer: Claude subagent (native fallback)
Plan baseline: no rule. Scope Challenge 5 covers only text merged into a withheld Rede
Runtime evidence: pass 1 moves resumed text to the same speaker's previous Rede (`merged_rede`, `:1499`, requires the same speaker, `:1493`) and a reply to its Erwiderung (`merged_erwiderung`, `:1491`), and empties the resumed Rede's own text (`:1505`). Its leftover segments raise at `:1556`. Round 2 reviewed these merges: 414, 1 wrong (`a3-wp18-19-round2-result.md:80-91`)
Comparison grid:

| Choice | Current | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| D7 rule | none | text pass 1 moved stays where pass 1 put it; the withheld record holds what was left; the source reconciles as "partly merged into X, rest withheld"; its pass-1 diagnostics stay | no rule (current) | count, on the fetched XML (D8), how many withheld Reden moved text in pass 1, then choose | leave the row open |
| Other choices | approved D1-D6 | unchanged | unchanged | unchanged | unchanged |

Question D7:
D7: What happens to text a withheld Rede gave away before it was refused?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3), PR 2.
ELI10: Before the parser refuses a Rede, an earlier step can already have moved part of its text elsewhere. A typical case: a speaker is interrupted and resumes, and the resumed words are joined back onto that speaker's earlier Rede. If the later Rede is then withheld, the joined words are already in the earlier Rede.
Stakes if we pick wrong: either the earlier, correct Rede loses words that are its own, or text from a withheld Rede is counted without the dataset saying so.
Recommendation: A because those moves were decided by reviewed rules before the refusal and put the words with the speaker who spoke them, so keeping them changes no other unit and the reconciliation shows where they went.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Keep the moves, document them (recommended)
  ✅ The earlier Rede keeps its speaker's own resumed words, so no correct unit changes.
  ✅ The reconciliation shows the source as partly merged and partly withheld, so nothing is hidden.
  ❌ Text that passed through a later-refused Rede counts, relying on round 2's merge review.
B) Keep the current value
  ✅ No rule to write or test now.
  ✅ Nothing changes in the parser's pass 1.
  ❌ The plan's "every other unit unchanged" proof stays unstated for these moves.
C) Investigate first
  ✅ Measures how often this happens on the 85 sittings' XML before choosing.
  ✅ Can still pick A or withholding the receiving Rede with real numbers.
  ❌ PR 2 waits for the fetch and the count before this rule is settled.
D) Defer this change
  ✅ Leaves the row open without blocking other decisions.
  ✅ No commitment until PR 2 is designed in detail.
  ❌ PR 2 would be built without a rule for a case the parser already produces.
Net: keep reviewed moves and say so, against counting first or leaving it open.
Header: Moved text
Options:
A) Keep moves, document
Text pass 1 moved out of a Rede stays where pass 1 put it, also when that Rede is withheld later; the withheld record holds what was left; the source reconciles as "partly merged into X, rest withheld"; its pass-1 diagnostics stay. A test covers a resumed Rede that is withheld. Effort: included in PR 2.
B) Keep current value
No written rule for text moved out of a withheld Rede; the plan stays as it is.
C) Investigate first
Count, on the fetched XML of the 85 (D8), how many withheld Reden moved text in pass 1, then choose a rule. Effort: human ~1 h / CC ~15 min after the fetch.
D) Defer this change
Leave the rule open; other decisions stay as they are.

State: approved
Actual answer: A) Keep moves, document, answered 2026-11-09 by the owner's adjudicator hook: "`merged_rede` … requires the same speaker as the previous Rede … Keeping them changes no other unit … Reconciling the source as 'partly merged, rest withheld' keeps it visible"
Accepted scope: text pass 1 moved out of a Rede stays where pass 1 put it when that Rede is withheld later; the withheld record holds what was left; the source reconciles as "partly merged into X, rest withheld"; its pass-1 diagnostics stay; a test covers a withheld resumed Rede. In PR 2
History: none

#### D8: fetch and audit the 85 sittings' XML before the build
Finding: outside voice 2, High, confidence 9/10, `build_dip_pulse_site.py:1970`, reviewer: Claude subagent (native fallback)
Plan baseline: T4 (fetch the 85, scan, rebuild, gate, compare) follows T3 (task list); gate step 6 says "Fetch the XML first and scan it"
Runtime evidence: `fetch_missing_xml` fetches Plenarprotokoll XML from the dserver with no DIP key, paced by `dip.XmlPacer` (`:1970`, `:14573`); `audit_offline_turns.py` parses past located refusals and re-raises the rest; the sandbox blocks the network, so the owner's terminal runs it
Comparison grid:

| Choice | Current | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| D8 order | XML fetched in T4, after the build | fetch only the XML of the 85 (about 85 requests, no DIP key) and run the offline audit before PR 1 if possible, required before PR 2; it measures refusal classes per sitting, whether each of the 69 parses once its located refusals are withheld, the unknown sitting's reason, words withheld (N9) and pass-1 moves out of refused Reden; the DIP metadata and votes of T4 stay after PR 2 | keep the current order | decide after PR 1 | leave the row open |
| Other choices | approved D1-D7 | unchanged | unchanged | unchanged | unchanged |

Question D8:
D8: Should we fetch and audit the 85 sittings' XML before building?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3), before PR 1 or PR 2.
ELI10: The whole build rests on one guess we have not checked: that the 85 left-out sittings become readable once their few bad Reden are held back. Their XML files are not on this machine. Downloading just those files is about 85 requests and needs no DIP key, and the existing audit script can then say how many sittings really come back.
Stakes if we pick wrong: weeks of work go into withholding before we learn that most of the 85 fail for a reason it does not fix.
Recommendation: A because it tests the plan's only unverified premise and its fallback trigger for about an hour of work, before the expensive part starts.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Fetch and audit first (recommended)
  ✅ Shows before PR 2 how many of the 85 come back, and why the others do not.
  ✅ Gives the words withheld that the N9 minimum needs, and real cases for the tests.
  ❌ Needs a network run in your terminal, because the sandbox blocks the dserver.
B) Keep the current order
  ✅ No extra step before the build starts.
  ✅ The fetch happens once, with T4's DIP metadata and votes.
  ❌ The premise and the fallback trigger stay untested until the build is done.
C) Decide after PR 1
  ✅ PR 1 can start now; the order is settled when PR 2 is planned.
  ✅ Leaves room to fold the fetch into PR 1's replay.
  ❌ PR 2's design still rests on the untested premise until then.
D) Defer this change
  ✅ Keeps the row open without changing any plan now.
  ✅ No network run needed yet.
  ❌ Most likely ends as B by default.
Net: one cheap network run now against learning the premise's truth after the build.
Header: Fetch first
Options:
A) Fetch and audit first
Fetch only the XML of the 85 (about 85 dserver requests, no DIP key), in the owner's terminal, and run `audit_offline_turns.py` on it before PR 1 if possible, required before PR 2. Report refusal classes per sitting, which of the 69 parse once located refusals are withheld, the unknown sitting's reason, words withheld, and pass-1 moves out of refused Reden. T4's DIP metadata and votes stay after PR 2. Effort: human ~2 h / CC ~30 min plus the run, estimated.
B) Keep current order
The XML of the 85 is fetched in T4, after PR 2.
C) Decide after PR 1
Start PR 1; settle the fetch order when PR 2 is planned.
D) Defer this change
Leave the order open.

State: approved
Actual answer: A) Fetch and audit first, answered 2026-11-09 by the owner's adjudicator hook: "The plan's own gate step … already says to fetch the XML first and scan it … It also tests the one unverified premise … before the multi-week PR 2 build"
Accepted scope: fetch only the XML of the 85 (about 85 dserver requests, no DIP key) in the owner's terminal and run `audit_offline_turns.py` on it, before PR 1 if possible and required before PR 2; report refusal classes per sitting, which of the 69 parse once located refusals are withheld, the unknown sitting's reason, words withheld, and pass-1 moves out of refused Reden. T4's DIP metadata and votes stay after PR 2
History: none

#### D9: a cap on newly withheld Reden per automatic release (reopens D5)
Finding: outside voice 3, Medium, confidence 8/10, `build_dip_pulse_site.py:278-281`, reviewer: Claude subagent (native fallback)
Plan baseline: D5 A (2026-11-09): the release goes out and lists each newly withheld Rede. Reopened on a new risk: a parser regression in new sittings would then show only as more withheld Reden, with nothing that stops a release
Runtime evidence: today a located refusal stops the run. In the WP 20 and 21 sittings acquired by A3, about 316, one located refusal occurred, 20/11 (`a3-phase3.md:323`) [estimated count]. So a new withheld Rede is rare, and several in one week point to drift
Comparison grid:

| Choice | Current | A | B | C | D |
| --- | --- | --- | --- | --- | --- |
| D9 cap | D5 A: release and list, no cap | D5 A, plus: the automatic release stops when it would add more than 2 newly withheld Reden in total; up to 2 are released and listed; the cap is a named constant, its changes go in the data changelog | D5 A unchanged | measure the WP 20/21 rate exactly first | leave the row open |
| D1-D8 | approved | unchanged | unchanged | unchanged | unchanged |

Question D9:
D9: Should an automatic release stop when many Reden are newly withheld?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3), PR 2; reopens D5.
ELI10: D5 lets a weekly release go out and list any newly withheld Rede. But a parser bug in new sittings would then only show as more withheld Reden, and nothing would stop. In the WP 20 and 21 sittings so far, only one Rede-level refusal happened, so one or two in a week is normal and several is a warning sign.
Stakes if we pick wrong: a parser regression withholds Reden week after week before anyone notices, or a harmless single case stops a release.
Recommendation: A because it keeps D5 for the normal case and turns the rare pile-up into a stop, at the cost of one constant and a test.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Cap at 2 per release (recommended)
  ✅ A real parser regression stops the weekly release instead of passing as a list.
  ✅ One or two odd Kurzinterventionen still go out, as D5 decided.
  ❌ The number 2 is a judgment from one case in about 316 sittings and may need tuning.
B) Keep D5 as it is
  ✅ No release ever stops for withheld Reden, which is simplest.
  ✅ Every withheld Rede is still listed in the run summary and changelog.
  ❌ Drift is caught only when someone reads the list or at the stable review.
C) Measure first
  ✅ Sets the cap from the exact WP 20/21 rate instead of an estimate.
  ✅ Can still choose A with a better number.
  ❌ Leaves the release without a stop until the count is done.
D) Defer this change
  ✅ Keeps D5 in force while PR 2 is designed.
  ✅ No commitment to a number yet.
  ❌ PR 2 may ship without any drift stop.
Net: a small, tunable stop against a release that never waits.
Header: Drift cap
Options:
A) Cap at 2
D5 stays; in addition the automatic release stops when it would add more than 2 newly withheld Reden in total, and the owner looks before it goes out. The cap is a named constant; changing it is recorded in the data changelog. Effort: human ~2 h / CC ~20 min, estimated.
B) Keep D5 as is
Release and list every newly withheld Rede; no cap.
C) Measure first
Count the located refusals in all WP 20/21 sittings acquired, then set a cap. Effort: human ~1 h / CC ~15 min.
D) Defer this change
Leave the cap open; D5 stays in force.

State: approved
Actual answer: A) Cap at 2, answered 2026-11-09 by the owner's adjudicator hook: "A cap keeps D5 for the normal one-or-two case and stops a pile-up. The number is a named, tunable constant and cheap to change before release"
Accepted scope: D5 stays; the automatic release also stops when it would add more than 2 newly withheld Reden in total, and the owner looks before it goes out; the cap is a named constant, and changing it is recorded in the data changelog. In PR 2
History: D5 answered A (release and list) by the adjudicator, 2026-11-09; this row adds to it and does not undo it

**Outside voice dispositions:** 1 accepted (D7 A). 2 accepted (D8 A). 3 accepted (D9 A). 4 to 8 recorded as clarifications or required proof, as in the table above.

### TODO decision

#### TD1: retire `scripts/audit_offline_turns.py`
Finding: Section 2 item 4 and outside voice 8, P3, confidence 7/10, `audit_offline_turns.py:1-6,30`, reviewer: this review and the Claude subagent
Plan baseline: the script stays; D8 runs it on the 85 sittings' XML before PR 2
Runtime evidence: it blanks a located refusal by matching the message text and parses on; its docstring says its counts "cannot certify or replace a report/database"; PR 2 makes the parser do this itself, with a typed exception
Comparison grid:

| Choice | Current | A | B | C |
| --- | --- | --- | --- | --- |
| TD1 | the script stays | add a TODO to retire it after PR 2 | skip | in PR 2: once D8's audit has run, delete the script and its tests, and point `docs/plans` references to the withheld table |
| D1-D9 | approved | unchanged | unchanged | unchanged |

Question D10:
D10: Should the old audit script go once the parser withholds by itself?
Project/branch/task: claude/strange-germain-01ea7e, the withholding build (T3), PR 2.
ELI10: An old helper script does a rough version of what PR 2 builds into the parser: it skips a refused passage and keeps reading. It recognises a refusal by the wording of the error message, and it says itself that its numbers cannot certify a store. D8 still needs it once, on the 85 sittings, before PR 2.
Stakes if we pick wrong: two tools give two different counts of what is held back, or a tool is kept that nobody should trust.
Recommendation: C because after D8 the parser's withheld table is the one source, and keeping a weaker second count invites confusion.
Note: options differ in kind, not coverage — no completeness score.
Pros / cons:
A) Add to TODOS.md
  ✅ Retirement is recorded without growing PR 2.
  ✅ The script stays available for any later audit.
  ❌ Two counts of refusals coexist until someone acts on the TODO.
B) Skip
  ✅ No work and no change to existing tests.
  ✅ The script keeps working for ad hoc audits.
  ❌ Its message matching drifts from the parser's typed exception.
C) Build it now in PR 2 (recommended)
  ✅ One source of truth for withheld Reden from PR 2 on.
  ✅ Removes message-matching code and its tests, so nothing drifts.
  ❌ PR 2 grows by a deletion and doc pointer updates.
Net: one trusted count against keeping an old tool around.
Header: Audit script
Options:
A) Add to TODOS.md
What: retire `scripts/audit_offline_turns.py` after PR 2. Why: the parser withholds natively and the script's counts cannot certify a store. Pros: PR 2 stays smaller. Cons: two counts coexist meanwhile. Context: D8 uses it once. Depends on: PR 2.
B) Skip
Keep the script as it is.
C) Build now in PR 2
After D8's audit has run, PR 2 deletes the script and its tests and updates the plan docs that cite it. Effort: human ~1 h / CC ~10 min, estimated.

State: approved
Actual answer: C) Build now in PR 2, answered 2026-11-09 by the owner's adjudicator hook: "Deleting is less work than rewriting … D8 still runs the script once before PR 2, so deleting it afterward loses nothing planned"
Accepted scope: after D8's audit has run, PR 2 deletes `scripts/audit_offline_turns.py` and its tests and updates the plan docs that cite it. No TODOS.md entry
History: none

Approval readiness: PASS. Checked S1 (D1 B), R10 (D2 A), D3 (B), R11 (D4 A), D5 (A), D6 (A), D7 (A), D8 (A), D9 (A), TD1 (D10 C), each with the adjudicator's answer of 2026-11-09 recorded above. Every other accepted item is required work or proof of these or of the CEO review's approved T3.

### Required outputs

**NOT in scope:**
- T4's DIP metadata and votes for the 85 sittings: they follow PR 2; only their XML moves ahead (D8).
- The N8 review and the T7 link review: separate tasks on the restored sittings.
- Withholding for Befragung, Fragestunde and conflicting-roles refusals: these cannot be narrowed to one Rede, so such a sitting stays out under the bar.
- Releasing a withheld Rede by review: parser rounds shrink the list, one owner-approved rule at a time (gate step 5).
- The N9 minimum itself: the owner sets it once D8 has measured the words withheld.

**What already exists:** listed under Scope Challenge. Reused: the per-Rede loop and its state reset, rede-keyed ids, the version gate, the reviewed-list pattern of `person_corrections.json`, `compare_store_values.py` for D6. Rebuilt: none. Retired: `audit_offline_turns.py` (D10).

**Failure modes:**

| New path | Realistic failure | Test or handling | What users see |
| --- | --- | --- | --- |
| Located refusal, withheld | A Rede's nested units leak into the store | commit-on-finish, rollback test | nothing wrong; the Rede is in `withheld_units` |
| Other refusal classes | Fetched sittings fail for an unnarrowable reason | sitting refused, as today; D8 measures first | the sitting stays out with a named reason |
| Reconciliation | A parser path drops a Rede | leftover id refuses the sitting; replay (D6) | the run stops, loudly |
| Reviewed list | An entry names a Rede the sitting lacks | refusal, test | the run stops, loudly |
| Parser drift in new sittings | A regression withholds several Reden a week | cap of 2 (D9), run summary (D5) | the release stops for the owner |
| Moved text (D7) | Text from a withheld Rede counts in a neighbour | documented; reconciled as partly merged | visible in the reconciliation and DATA.md |
| Sequence switch (D3) | A reader relied on 1..n | readers checked: order only; D6 counts the moves | none expected |

Critical gaps: 0.

**Worktree parallelization:**

| Step | Modules touched | Depends on |
| --- | --- | --- |
| W1 fetch and audit the 85's XML | data only, a report under `docs/plans/` | — |
| W2 PR 1, inventory and reconciliation | parser, tests, docs | the Reden fix landed |
| W3 PR 2, parser withholding | parser, reviewed list, tests | W1, W2 |
| W4 PR 2, storage and export | persist, build/export, data dictionary, comparison and gate scripts | W3 |
| W5 PR 2, release behaviour | build | W4 |
| W6 PR 2, regression contract | scripts, tests | W3, W4 |
| W7 PR 2, docs and retirement | docs, ADR, audit script | W3 |
| W8 PR 2, N7 reviewed entries | reviewed list | W3, the N8 review pass |

Lane A: W2 (parser). Lane B: W1 (the owner's network run), independent of the code. Launch A and B together. Then PR 2 runs sequentially (W3 → W4 → W5, then W6, W7, W8), because every step touches the parser or reads its report shape. Conflict flags: W2 and the Reden fix both touch `validate_dip_protocol.py`, so W2 starts from main after that fix lands.

## Implementation Tasks
Synthesized from this review's findings. They refine T3 above; T4's DIP part follows them.

- [ ] **W1 (P1, human: ~2h / CC: ~30min, plus the owner's network run)** — data — Fetch only the XML of the 85 and audit it
  - Surfaced by: Outside voice 2, D8
  - Files: run with `docs/plans/withholding-preflight/fetch_and_audit.py` (in the owner's terminal, with the Reden fix's `scripts/`); report under `docs/plans/withholding-preflight/`
  - Verify: the report lists refusal classes per sitting, which of the 69 parse once located refusals are withheld, finding 8's sitting, words withheld, and pass-1 moves out of refused Reden
- [ ] **W2 (P1, human: ~3d / CC: ~4h)** — parser — PR 1: raw XML inventory and reconciliation
  - Surfaced by: Scope Challenge, D1; N6
  - Files: `scripts/validate_dip_protocol.py`, a new test file, `docs/data-methods.md`
  - Verify: `python3 -m unittest`; A3 replay compared with `--cohort shared`: 0 moved values and no held sitting refused (D6)
- [ ] **W3 (P1, human: ~1w / CC: ~1d)** — parser — PR 2: withhold located refusals
  - Surfaced by: Scope Challenge 3-5, Section 2 items 1-3, D4, D7, D3
  - Files: `scripts/validate_dip_protocol.py`, a new reviewed list in `scripts/`, tests
  - Verify: tests for both located classes, the split part (D4), rollback, text merged in and moved out (D7), a stale list entry, unchanged refusal for every other class; speeches carry their source position
- [ ] **W4 (P1, human: ~2d / CC: ~3h)** — store/export — PR 2: `withheld_units` table and its outputs
  - Surfaced by: D2, D3, Section 1 items 2 and 4, N9
  - Files: `scripts/persist_dip_pulse_store.py`, `scripts/build_dip_pulse_site.py`, `scripts/data_dictionary.json`, `scripts/compare_store_values.py`, `scripts/validate_store_gate.py`
  - Verify: export test (`withheld_units.csv`, DATA.md coverage by words per year and Fraktion), replay equals fresh, schema, export format and rule version taken after both fix branches land
- [ ] **W5 (P1, human: ~1d / CC: ~1h)** — release — PR 2: list, cap and exclusion reasons
  - Surfaced by: D5, D9, Section 1 item 3
  - Files: `scripts/build_dip_pulse_site.py`, tests
  - Verify: run summary lists newly withheld Reden; more than 2 stops the automatic release; an exclusion with reason "excluded" or none is refused
- [ ] **W6 (P1, human: ~1d / CC: ~2h, plus run time)** — verification — PR 2: regression contract
  - Surfaced by: D6, outside voice 7
  - Files: a withhold-one script, tests
  - Verify: replays show 0 moved values except `speeches.sequence` (counted); withholding one Rede per TOP, including Reden next to Kurzintervention/Erwiderung and resumed pairs, leaves every other unit unchanged
- [ ] **W7 (P2, human: ~1d / CC: ~1h)** — docs — PR 2: ADR 0005, CONTEXT.md, data-methods, retire the audit script
  - Surfaced by: N1 ("record this in an ADR"), outside voice 6, D10
  - Files: `docs/adr/0005-…`, `CONTEXT.md`, `docs/data-methods.md`, `scripts/audit_offline_turns.py` and its tests (deleted)
  - Verify: the ADR states the grain, the cost of an opening withheld with its Rede, the moved-text rule and the cap; doc-link test
- [ ] **W8 (P1, human: ~1d / CC: ~1h, after the N8 review pass)** — data — PR 2: reviewed entries for 18/2, 18/29, 18/83, 19/25
  - Surfaced by: N7 A
  - Files: the reviewed list
  - Verify: each entry carries a reason; the four sittings reconcile; their known wrong units are in `withheld_units`, not in any count

The JSONL task artifact is written beside the test plan in the review state directory.

**Unresolved decisions that may bite you later:** none in this review. Every choice was answered by the owner's adjudicator hook, not by the owner in person. Any of D1 to D10 can be overruled before PR 1 starts.

**Completion summary:**
- Step 0: Scope Challenge — scope accepted as-is
- Reality rows: 7/7 applicable rows emitted (`PLAN_REALITY: phase=eng rows=7/7 missing=none`); 1 unverified premise, now tested first by D8
- Architecture Review: 4 issues found
- Code Quality Review: 4 issues found
- Test Review: diagram produced, 19 gaps identified
- Performance Review: 2 issues found (both P3, no action)
- NOT in scope: written
- What already exists: written
- TODOS.md updates: 1 item proposed to user (TD1, built in PR 2 instead)
- Failure modes: 0 critical gaps flagged
- Unresolved decisions: 0 in this review
- Outside voice: Codex unavailable (sandbox: "Operation not permitted", `ab.chatgpt.com` blocked); native fallback completed with 8 findings, not outside coverage
- Parallelization: 2 lanes, 2 parallel / 6 sequential
- Lake Score: 1/5 (D6 picked a 10/10 option; D2, D3, D4 and D5 picked the best-scored option below 10)

**Suppressed findings (confidence under 5):** none.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
| --- | --- | --- | --- | --- | --- |
| CEO Review | `/plan-ceo-review` | Scope and strategy | 2 | ISSUES OPEN | Run 1: 17 questions, 16 answered, 1 closed by correction. Run 2, mode HOLD SCOPE: 0 proposals, 5 critical gaps open until built, all owner decisions answered |
| Outside Review | Codex for the CEO plan, run by the owner; native fallback for the eng plan | Independent 2nd opinion | 2 | CEO: issues found. Eng: unavailable, fallback completed | CEO: 5 findings (3 confirmed, 2 in part). Eng: Codex could not start in the sandbox; the native fallback found 8, three became D7, D8 and D9 |
| Eng Review | `/plan-eng-review` | Architecture and tests (required) | 1 | ISSUES OPEN | 29 issues, 0 critical gaps; all mapped to tasks W1-W8; D1-D10 answered by the owner's adjudicator |
| Design Review | `/plan-design-review` | UI and UX gaps | 0 | not run | none |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | not run | none |

- **OUTSIDE COVERAGE:** CEO phase: Codex plan challenge completed 2026-11-07, run by the owner. Eng phase, 2026-11-09: Codex unavailable (sandbox), so no outside coverage; the native Plan-subagent fallback completed with 8 findings and does not count as outside coverage. The owner can run the eng challenge from a terminal with `codex exec`, using the prompt in the session scratchpad.
- **REVIEW HISTORY:** the eng review log is kept under a scratchpad state directory, because the sandbox blocks `~/.gstack`; it does not reach the dashboard on other machines.
- **VERDICT:** no review is CLEAR. The eng review answered every decision and mapped every finding to tasks; its status is ISSUES OPEN because those tasks are unbuilt. W1 and W2 can start, W2 once the Reden fix lands. eng review required (the dashboard's rule while Eng is not CLEAR).

**UNRESOLVED DECISIONS:**
- + 2 unresolved from prior reviews: the host provider and the reader test's pass rule (CEO review, `TODOS.md`).
