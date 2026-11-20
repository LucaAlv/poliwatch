# Release policy: main and stable releases

How data releases are cut, which of them count as stable, and what may change between them. Owner decision Q3 (`docs/plans/v1-scope-review.md`, 2026-11-06). Written 2026-11-20, when no release was published yet. It applies from the first release on.

## Two kinds of release

**Main release.** A directory `data-<YYYY.MM.DD>/`, built by `scripts/publish_dip_pulse_data.py` from an export that carries a release tag. It holds the export's files, `CHANGES.md`, `changes.json` and `SHA256SUMS`, and `--publish` creates one GitHub release for it.
- It is published only if every check of the release script passes.
- Every main release is kept, with its date and checksums.
- Until "Scheduled data-release workflow" (TODOS.md) is built, each main release is cut by hand. After that, one is cut for each completed Sitzungswoche.

**Stable release.** A main release the owner has reviewed with `docs/release-review.md`, about every three months.
- It is a marker on that main release, not a second database: the annotated tag `stable-<version>` on the commit of `data-<version>`, and the record `docs/release-reviews/<version>.md` with the verdict "stable".
- The DOI goes on stable releases only, once the Zenodo account exists (TODOS.md, "A DOI per release and a citation file").
- The first release is reviewed in full and is the first stable.

**A bug found in review.** The candidate is not patched and does not become stable. The fix goes into a new main release, the change is checked on a copy of the store (README, "Validate a data correction"), and that release becomes stable after the affected review steps have run again. Until then the last stable stays the stable one. The steps are in `docs/release-review.md`, "A bug found in review".

**Why main and stable can differ.** Main is newer: it holds the sittings and corrections since the last review. Stable is older and has been checked by a person. A figure can differ between the two because main added sittings, or because main carries a correction that the next stable will also carry; the `CHANGES.md` of the main releases in between names each one. Cite stable for published work, and main when the newest sittings matter.

## What a release fixes

- **A release never changes.** No release, file or tag is edited or replaced. A fix ships in the next main release. The release script refuses a version that already exists and never overwrites a release directory; nothing stops a person with write access from editing a GitHub release by hand, so this stays a rule.
- **Every moved published figure is recorded.** When a change moves a value that a release has published, the next release's `changes.json` names it under `corrections`: table, key, column, old value, new value and reason. The script checks the shape of each entry. It cannot find a correction nobody wrote down, so the comparison in step 2 of the review is what catches one.
- **Ids keep their meaning.** Stable keys follow `docs/stable-ids.md`; a retired person key stays as an alias. A change to the export format, the store schema, the key version or the schema hash is allowed only in a release whose changes file describes it under `schema_changes`; the script refuses the release otherwise.
- **Withheld Reden are listed.** Each release lists every Rede it newly withholds or releases. A release that adds more than two newly withheld Reden is refused until the owner has read each one and confirmed it (ADR 0005, "The cap"). The first release lists all of them and has no cap.
- **Accuracy first.** A change that makes a figure more correct goes in, however much it moves. Stability means the change is recorded, not that it is avoided.

## The `CLAUDE.md` section after the first release

Until the first `--publish` nothing is published, and the section "Project stage: pre-release" in `CLAUDE.md` is the true one (owner decision 2026-11-14, `docs/plans/release-readiness.md`, 2d). The first PR after the first successful `--publish`, on the same day, replaces that section with this text:

> ## Project stage: released data, pre-release site
>
> Data releases (`data-<YYYY.MM.DD>`) are published and cited. The site is not public yet. Code, pages and the site's URLs still change in place, with no compatibility shims. What a release says about the data is fixed, by the rules of `docs/release-policy.md`:
>
> - A release never changes. A fix ships in the next main release.
> - When a change moves a value that any release has published, the next release's `changes.json` names it: table, key, column, old value, new value, reason. The commit still reports old and new values.
> - Stable keys keep their meaning (`docs/stable-ids.md`). A change to the export format, the store schema or the key version needs a `schema_changes` entry.
> - A change that makes a figure more correct goes in, however much it moves. Stability means it is recorded, not that it is avoided.
>
> When the site goes public, a second paragraph covers page URLs and the Daten page.

The same PR:
- changes "Review findings: fix now or defer" in `CLAUDE.md`: a correctness defect in a published release becomes a correction in the next main release;
- re-reads the two test comments that cite the pre-release rule (`tests/test_daten_page.py`, "Pre-release: no older manifest shape is rendered", and `tests/test_sitzungskalender.py`, "pre-release rule (no output moves)") and the sentence in `PRODUCT.md`, "Evidence on Hand", that calls the product pre-release;
- removes this section's first paragraph and the block quote, which have then been applied.

## What waits for the site

These parts of Q3 are site work of stage 2 and are tracked in TODOS.md, "Main and stable releases":
- both downloads on the Daten page, the newest main release and the newest stable one, with the last review date and the paragraph "Why main and stable can differ" above;
- each page naming the main release it was built from;
- the site showing the age of its data;
- automatic main releases ("Scheduled data-release workflow").
