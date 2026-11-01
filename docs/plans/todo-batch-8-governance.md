# TODO batch 8: contribution governance (the half that needs no domain)

Status: plan, 2026-11-01. Not implemented. Eng review folded in (see Review log). Base: main 69ade54 (v0.26.1.0), branch `claude/todos-batching-subagents-aa0a61`.

Source item: TODOS.md, section **Community**, heading **"Contribution governance: SECURITY.md, conduct rules, issue forms, contact channels"**. It implements [ADR 0003](../adr/0003-licences-and-impressum.md) D5.

Read before implementing: `CLAUDE.md` (pre-release rule, fix-now-or-defer rule), ADR 0003 D5, `CONTRIBUTING.md`, `docs/agents/triage-labels.md`, `docs/agents/issue-tracker.md`.

## What the item asks, and what is actually in the code

The TODO lists five deliverables. Its done-criterion is: "a new issue can only be opened through one of the two forms and `security.txt` is served by the preview".

The code differs from what the TODO and ADR assume in three ways. Each one shapes this plan:

1. **There is no „Fehler melden" link on the site.**
   - `issues_url` exists only as the Daten page (`database.html`) footer link, labelled „Fragen und Fehler" (`render_database_page`, main line 4818).
   - Its value comes from the operator: `--data-issues-url` or `$BUNDESTAG_PULSE_DATA_ISSUES_URL` (`resolve_data_export_options`, main 12760–12773). No script in the repository sets either one.
   - `safe_issues_url` (main 12241–12248) checks the value and accepts any `https://` URL, query string included.
   - The value is stored in the export manifest (`_run_export`, main 4087) and fed into `_inputs_hash` (main 3069/3090).
   - It is off by default. None of the roughly 20 other page footers has a report link.
2. **The site has no base URL.** No setting knows the public domain. Only `--data-base-url` exists, and it is for downloads. So the absolute URL of a page is not known at build time, and that URL also waits on the domain.
3. **The repository is private.** `CITATION.cff` deliberately has no `repository-code`, and the codebook follow-up (TODOS.md, "Done (lane/release, 2026-10-31)" entry) says "the repository is private". This adds a third gate next to the domain and the Impressum. See the next section.

## What a private repository means

GitHub documentation, read 2026-11-01:
- [creating an issue from a URL](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue)
- [configuring templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)
- [form schema](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-githubs-form-schema)
- [issue-form syntax](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/syntax-for-issue-forms)
- [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/configuring-private-vulnerability-reporting-for-a-repository)

What follows from them:
- **Who can open issues.** Only people with access to the repository. Anyone else following a pre-filled `issues/new` link gets a 404.
  - So no public build may set `--data-issues-url` to the GitHub form until the repository is public.
  - This is already the default, because the flag is opt-in. The plan adds no default.
- **`validations: required` is enforced only in public repositories.** The schema marks required fields and required checkboxes „Only for public repositories".
  - While the repository is private, the required fields of the Datenfehler form are not enforced.
  - The forms still render, and the YAML is correct for the public repository.
- **Private vulnerability reporting (PVR) is for public repositories.** Only „owners and administrators of public repositories" can enable it.
  - The owner can switch PVR on only *after* the visibility flip.
  - Until then `SECURITY.md` describes a channel that does not exist yet, and must say so honestly (S1).
- **Templates take effect only on the default branch.** Forms and `config.yml` work once merged to `main`.
- **`blank_issues_enabled: false` is not absolute.**
  - Read and Triage roles see only the templates.
  - Write access and above still see a blank option marked „Maintainers only".
  - The API (`gh issue create --title … --body …`, which `docs/agents/issue-tracker.md` uses) is unaffected. Agent-filed issues keep working, without form structure or auto-labels.
  - So „can only be opened through one of the two forms" is true for the public and false for the owner. The revised done-criterion says so.
- **Template labels must already exist.** „If a label does not already exist in the repository, it will not be automatically added". A form naming a missing label silently files an unlabelled issue.
  - Creating labels is a repository change, so it is an owner step (O3). It is part of the done-criterion.
  - The implementer checks the labels with read-only `gh label list` (this planning session stayed offline).
- **`labels=` in a URL needs label permission.** So no link carries `labels=`. The form's own `labels:` key applies them.
- **Field pre-fill.** The form schema names `id` as „the canonical identifier for the field in URL query parameter prefills".
  - So `…/issues/new?template=datenfehler.yml&seite=…` fills the field whose `id` is `seite`.
  - Ids may use only alphanumerics, `-` and `_`, and must be unique within a form.

## Scope split

### Doable now (this batch)

| # | Deliverable | Files |
|---|---|---|
| S1 | `SECURITY.md`: scope section; reporting via GitHub PVR, stated as available from the public release on; no URL, no e-mail | `SECURITY.md` (new) |
| S2 | Issue form „Datenfehler" | `.github/ISSUE_TEMPLATE/datenfehler.yml` (new) |
| S3 | Issue form „Fehler auf der Seite" | `.github/ISSUE_TEMPLATE/seitenfehler.yml` (new) |
| S4 | `config.yml`: `blank_issues_enabled: false`; contact link for security only (real repository URL); private-matters link deferred (O5) | `.github/ISSUE_TEMPLATE/config.yml` (new) |
| S5 | DRAFT German conduct rules, linked from CONTRIBUTING | `CODE_OF_CONDUCT.md` (new, name per O2), `CONTRIBUTING.md` |
| S6 | Pre-fill by configuration: the documented `--data-issues-url` value opens the Datenfehler form with the page filled in; the footer label names its target (O7) | `docs/project-documentation.md` (one table row); with O7: `scripts/build_dip_pulse_site.py` (label in the footer, one comment, the flag help), `tests/test_daten_page.py` |
| S7 | Drift test: the documented pre-fill URL names a template and field ids that exist | `tests/test_issue_forms.py` (new) |
| S8 | ADR 0003 D5 amended to what this batch actually ships | `docs/adr/0003-licences-and-impressum.md` |

### Blocked on domain, Impressum or public visibility

| # | Item | Waits on |
|---|---|---|
| B1 | `/.well-known/security.txt` (RFC 9116) served by the site, with `Contact:` lines for PVR and the Impressum e-mail, plus `Expires:` and `Canonical:` | final domain, dedicated Impressum e-mail |
| B2 | `config.yml` contact link „Private Anliegen" to the Impressum e-mail or page | Impressum (TODOS.md Impressum item) |
| B3 | Switching GitHub PVR on (owner, repository settings) | repository public: directly after the flip |
| B4 | Setting `--data-issues-url` in the public build to the documented S6 value | repository public |
| B5 | Absolute, per-page pre-fill on every page: a render-time helper that appends `seite=<page URL>`, threaded into each renderer. It is the O8 follow-up. | domain and a site base URL setting; A3 merged |
| B6 | `SECURITY.md`, the conduct rules (rule 4) and the forms' intro name the e-mail channel for private matters and for reporters without a GitHub account (ADR D5) | Impressum e-mail |
| B7 | The original done-criterion's second half: `security.txt` served by the preview | B1 |

B1, B2, B5 and B6 also need the final product name. „Bundestag-Puls" is not final (CITATION.cff); where text names the project, use what the site uses today.

### Revised done-criterion for the doable half

Done when all of the following hold:
- (a) The PR is merged to `main`.
- (b) On `github.com/LucaAlv/poliwatch/issues/new/choose` the chooser lists exactly the two forms, „Datenfehler" first and „Fehler auf der Seite" second, plus the one security contact link. A blank issue appears only as „Maintainers only".
  - If GitHub lists them the other way round, rename the files with an ordering prefix and update the S6 URL and S7 in the same change (DR7).
- (c) The labels named in the forms (O3) exist in the repository. A Daten page built locally with the documented `--data-issues-url` value has a footer link that opens the Datenfehler form with `seite` filled in, and a test issue filed through it carries those labels.
  - Only the owner can check this while the repository is private. It is a manual owner check, recorded in the PR; the test issue is then closed.
- (d) Viewing each form file on GitHub shows no template error. The text-match tests cannot check the form schema (S7).
- (e) `SECURITY.md` shows on the repository's Security tab as the security policy.
- (f) The drift test and the updated Daten-page test pass in CI.

The TODO entry stays open for B1–B7. The implementer rewrites it in place at ship time, keeping only the blocked remainder. Its new done-criterion: „security.txt is served by the preview; the private-matters contact link and the e-mail channel exist; PVR is on; the visibility-flip checklist (O9) is done".

## Design

### S1 `SECURITY.md`

Language: English, with a two-sentence German summary at the top (O4). The rest of the repository docs are English, and security reporters are mostly developers.

Sections:
1. **Reporting.**
   - Use GitHub's private vulnerability reporting („Report a vulnerability" on the Security tab).
   - Until the repository is public that button does not exist. Say so in one sentence: „Private reporting opens with the public release; until then the repository is not public."
   - That sentence is rewritten at the flip (O9).
   - No e-mail address and no URL. ADR D5's e-mail fallback for people without a GitHub account is B6.
   - Do not open a public issue for a vulnerability.
2. **Scope (in).** From ADR D5:
   - Injection through source text into HTML: DIP, protocol XML, bundestag.de or abgeordnetenwatch text that reaches a generated page unescaped, or a link `href` with a scheme that is not allowed.
   - Leaked keys: `DIP_API_KEY` or an LLM provider key in the repository, its history, build output, an export or a release asset.
   - A tampered download: a release asset or export file that does not match its published `SHA256SUMS` or manifest `sha256`. The release script writes both (`scripts/publish_dip_pulse_data.py`).
3. **Out of scope.**
   - A wrong figure, a wrong attribution or a misparsed speech. These are data errors: use the „Datenfehler" form.
   - Vulnerabilities in DIP, bundestag.de, abgeordnetenwatch or GitHub themselves. Report them to their operators.
   - Denial of service against static hosting.
   - Missing security headers on a static site without logins or forms. Revisit if the site gains any input.
   - Reports produced only by automated scanners, without a demonstrated impact.
4. **Supported versions.** Only the latest `main` and the latest data release (`data-<YYYY.MM.DD>`). Old releases are not patched; a fix ships in the next release.
5. **What to expect.** One person runs the project. Reports are read and answered at the operator's discretion. There is no bounty and no fixed response time.

### S2 `datenfehler.yml`

Field ids are ASCII and stable. The documented pre-fill URL (S6) depends on `seite`, and S7 pins it.

```yaml
name: Datenfehler
description: Eine Zahl, ein Name, eine Zuordnung oder ein Text stimmt nicht mit der Quelle überein – auf der Seite oder im Download.
title: "Datenfehler: "
labels: ["needs-triage", "datenfehler"]   # names per O3
body:
  - type: markdown
    attributes:
      value: |
        Danke für die Meldung. Ein Datenfehler lässt sich prüfen, wenn die Stelle auf der Seite und die Stelle in der Quelle nebeneinanderstehen.
        Bitte nur Daten, Methode und Code, keine Bewertung von Parteien oder Personen: [Regeln für Beiträge](https://github.com/LucaAlv/poliwatch/blob/main/CODE_OF_CONDUCT.md).
        Bestätigte Fehler werden korrigiert und das Issue geschlossen; eine persönliche Antwort ist nicht garantiert.
        Persönliche Anliegen (Datenschutz, Korrekturwünsche betroffener Personen, Presse) gehören nicht in ein öffentliches Issue.
  - type: input
    id: seite
    attributes:
      label: Seite
      description: Adresse aus der Adresszeile des Browsers. Über den Link auf der Daten-Seite steht hier schon „database.html"; liegt der Fehler auf einer anderen Seite, bitte deren Adresse eintragen.
      placeholder: https://…/sitzung/21-84.html
    validations:
      required: true
  - type: textarea
    id: angezeigt
    attributes:
      label: Was steht auf der Seite?
      description: Zahl oder Satz möglichst wörtlich.
    validations:
      required: true
  - type: textarea
    id: quelle
    attributes:
      label: Was steht in der Quelle?
      description: Die entsprechende Stelle aus Plenarprotokoll, Drucksache oder Abstimmungsliste, möglichst wörtlich.
    validations:
      required: true
  - type: input
    id: quelllink
    attributes:
      label: Link zur Quelle
      description: DIP-Vorgang, Plenarprotokoll (gern mit Seitenzahl) oder Abstimmungsliste auf bundestag.de.
      placeholder: https://dip.bundestag.de/…
    validations:
      required: true
  - type: input
    id: datenstand
    attributes:
      label: Datenstand (optional)
      description: Nur bei Fehlern im Download: das Release, zu finden auf der Daten-Seite unter „Rohdaten".
      placeholder: data-2026.10.31
  - type: textarea
    id: hinweise
    attributes:
      label: Weitere Hinweise (optional)
```

Notes:
- `datenstand` and `hinweise` are additions to ADR D5's list (recorded in S8). `datenstand` exists because a report about a download is only reproducible against a named release. The reader copies it from the page; nothing pre-fills it in this batch.
- No conduct checkbox. A required checkbox is unenforced while private, and a ticked box changes nothing about behaviour. The rules link sits in the intro instead (design question, O6; recorded in S8).
- Links in form markdown use the absolute repository URL. The docs do not say how relative links resolve in form markdown (R3).
- Wording is impersonal, with no „du" or „Sie". The site never addresses the reader directly (grep over both renderers finds no du-form), so the forms keep that register (design review DR5, O11).
- The `seite` description says what to do when the pre-filled „database.html" is not where the error is. The Daten page is the only report link, so readers may use it for errors they saw elsewhere (DR2).
- The intro states what happens after submitting: a fix and a closed issue, no promised reply. This matches ADR D5's „no promise of a reply" (DR3).
- The two chooser descriptions split by *what* is wrong: content against the source, or the page not working. „Falsch dargestellt" was dropped because a wrong number is also „falsch dargestellt" (DR1).
- The private-matters sentence has no alternative channel yet. That is acceptable only while the repository is private; B6 adds the channel, and O9 makes it a gate on the flip (R9).

### S3 `seitenfehler.yml`

```yaml
name: Fehler auf der Seite
description: Die Seite selbst funktioniert nicht: Darstellung, Links, Suche oder Bedienung.
title: "Seitenfehler: "
labels: ["needs-triage", "bug"]           # names per O3
body:
  - type: markdown   # "Stimmt eine Zahl oder ein Name nicht mit der Quelle überein, ist das ein Datenfehler: [Formular „Datenfehler"](https://github.com/LucaAlv/poliwatch/issues/new?template=datenfehler.yml)." + rules link (absolute URL) + the same reply sentence as Datenfehler
  - type: input       id: seite          required   label: Seite   description: Adresse aus der Adresszeile des Browsers.
  - type: textarea    id: beschreibung   required   label: Was passiert, und was wäre richtig?
  - type: input       id: umgebung       optional   label: Browser und Gerät (optional)   placeholder: z. B. Firefox 132, Android
```

### S4 `config.yml`

```yaml
blank_issues_enabled: false
contact_links:
  - name: Sicherheitslücke melden
    url: https://github.com/LucaAlv/poliwatch/security/policy
    about: Bitte nicht als öffentliches Issue melden. Der vertrauliche Weg steht in SECURITY.md.
```

- The private-matters link (B2) is **left out**, not put in as a placeholder (O5).
- The security link is a real URL. It resolves once `SECURITY.md` is on `main`.
- The repository URL is hard-coded, here and in the forms' links. If the repository is renamed (product name), these change along with CITATION.cff. A `grep -rn LucaAlv/poliwatch` finds them all.

### S5 Conduct rules (DRAFT; the owner approves the text, O1)

File: `CODE_OF_CONDUCT.md` at the root (O2). GitHub recognises this file name and links it from the new-issue page and the community profile, so readers filing an issue see it without opening CONTRIBUTING. Content is German.

Draft, as it would be committed:

```markdown
# Regeln für Beiträge

Dieses Projekt bereitet Daten des Deutschen Bundestags auf. Issues und Pull Requests sind für Daten, Methode und Code da.

1. **Sache statt Politik.** Es geht darum, ob die Seite die Quelle richtig wiedergibt – nicht darum, ob eine Partei, eine Fraktion oder ein Abgeordneter recht hat. Parteipolitische Debatten werden ohne Diskussion geschlossen.
2. **Keine herabwürdigenden Aussagen über Personen** – weder über Abgeordnete noch über andere Beteiligte. Die Daten stehen ohnehin unter den DIP-Nutzungsbedingungen, die eine herabwürdigende Verwendung ausschließen (Nr. 5).
3. **Belege statt Behauptungen.** Ein Datenfehler nennt die Stelle auf der Seite und die Stelle in der Quelle.
4. **Persönliches gehört nicht in ein Issue.** Datenschutzanfragen, Korrekturwünsche betroffener Personen und Presseanfragen bitte nicht öffentlich stellen. Ein eigener Kontaktweg folgt mit dem Impressum.

Das Projekt betreibt eine einzelne Person. Beiträge, die gegen diese Regeln verstoßen, werden ohne weitere Begründung geschlossen, gekürzt oder gelöscht; wer wiederholt dagegen verstößt, wird gesperrt. Antworten gibt es nach Ermessen.
```

- At B6, rule 4's last sentence becomes „…sondern an die E-Mail-Adresse im Impressum."
- `CONTRIBUTING.md` gets a short German section at the top, before the developer setup: „Fehler melden und Regeln". It links:
  - the two forms (`issues/new/choose`);
  - `CODE_OF_CONDUCT.md`;
  - `SECURITY.md`.

  It says in one sentence that filing an issue needs a free GitHub account (DR4). A non-developer who lands there finds the way out on the first screen.
- The existing English developer text stays unchanged below it.

### S6 Pre-fill by configuration (no new code)

ADR D5 asks that the report link open the Datenfehler form with the page pre-filled. The only report link is the Daten page footer, so its page is always `database.html`. The operator's URL already reaches the footer unchanged through `safe_issues_url`. A fixed query string therefore does the whole job (R6):

```
--data-issues-url 'https://github.com/LucaAlv/poliwatch/issues/new?template=datenfehler.yml&seite=database.html'
```

- The value is documented in the `docs/project-documentation.md` row for `--data-issues-url` (main line 442), as the value to use once the repository is public (B4).
- `pulse_html.esc` already turns `&` into `&amp;` in the `href`.
- `seite=database.html` is site-relative. The reader sees „database.html" in the field, and the maintainer knows the host. B5 makes it absolute and per-page.
- Not touched: `_inputs_hash` (main 3061–3100), `export_distribution_data` (3681), `_run_export` (3833, 4087), `resolve_data_export_options`, `safe_issues_url` and the manifest field.
- **Label (O7).** „Fragen und Fehler" becomes „Datenfehler melden (GitHub)": with blank issues off there is no place for „Fragen", and „(GitHub)" tells a reader before the click that the report needs a GitHub account (DR4). The label occurs in four places, all changed together (R1):
  - the footer f-string (main 4818);
  - the comment above `_ISSUES_URL_RE` (main 12238);
  - the `--data-issues-url` help text (main 12709);
  - `tests/test_daten_page.py:360`.

  New help text: "Optional URL for the 'Datenfehler melden' link on the Daten page (or $BUNDESTAG_PULSE_DATA_ISSUES_URL); https://, http://, mailto: or a leading / only. docs/project-documentation.md gives the GitHub form URL that pre-fills the page."
- The footer f-string also calls `safe_issues_url` twice. Leave that as it is, because this batch changes only the label text.
- **Rejected:** a render-time helper that appends `template`, `seite` and the release tag.
  - For one page with a constant path it adds about 20 lines, three imports, a URL-rewriting contract, a hostile-tag threat model and an A3 import-line conflict.
  - Everything it gives today, a static query string gives too, apart from the release tag, which the reader can copy from the page.
  - The helper earns its place only when every page carries its own link: that is B5/O8.
- **Rejected:** a click-time script that appends `location.href`. It adds JS, it would put a local `file:///Users/…` path into a public issue from a preview, and it needs a browser check.

### S7 Tests (dependency-free, text match only)

This guards only the contract between the documented URL and the form ids. It cannot validate the form schema: PyYAML is not available and the repository adds no dependency. Schema validity is checked by the owner in done-criterion (d) (R8).

`tests/test_issue_forms.py` (new):
- Extract the `issues/new?…` URL from the `--data-issues-url` row of `docs/project-documentation.md`. Its `template` names an existing file under `.github/ISSUE_TEMPLATE/`. Every other query key appears in that file as a line matching `^\s*id: <key>\s*$`. No key is `labels`.
- In each form, every line matching `^\s*id:\s*(\S+)\s*$` has a value matching `^[A-Za-z0-9_-]+$`, and the values are unique within the file.
- Both forms' `labels:` lines contain `needs-triage`, the string `docs/agents/triage-labels.md` maps the `needs-triage` role to (read from its table, so a rename there fails the test).
- `config.yml` contains the line `blank_issues_enabled: false`.
- No file under `.github/ISSUE_TEMPLATE/`, nor `SECURITY.md` or `CODE_OF_CONDUCT.md`, contains a placeholder marker: `PLATZHALTER`, `TODO`, `example.invalid` or `[B` followed by a digit (R9).

`tests/test_daten_page.py` (only with O7):
- In `test_footer_issues_link_only_for_allowed_schemes` (main 350–361), replace the label string.
- Add one table row: the documented GitHub form URL renders as an `href` with `template=datenfehler.yml&amp;seite=database.html`.

### S8 ADR 0003 D5 amendment

Add an "Amended 2026-11-XX" paragraph under D5, in the style of D1's 2026-10-29 amendment. It records:
- the link label, and that the only report link is on the Daten page (per-page links are B5);
- that the page pre-fill is a configured query string;
- the extra fields `datenstand` and `hinweise`;
- no conduct checkbox;
- the private-matters contact link and the e-mail channel wait for the Impressum;
- PVR follows the visibility flip.

A3 does not touch this file (`git diff main...worktree-a3-plan -- docs/adr/0003-licences-and-impressum.md` is empty).

### Order of work

1. S5 draft and S1 text. These are public text, so they go to the owner for approval (O1, O4) before merge; implementation can proceed.
2. S2–S4 forms and config.
3. S6 doc row (and, with O7, the label in four places).
4. S7 drift test (red against a wrong id, then green).
5. S8 ADR amendment.
6. Full suite `python3 -m unittest discover -s tests`. No browser-check change: the footer is static HTML.
7. Ship (VERSION/CHANGELOG by `/gstack-ship`). Rewrite the TODO in place to the blocked remainder.
8. Owner: create labels (O3), then do the manual checks (b)–(e) after merge.

No figure, export format, schema or manifest field moves. The only user-facing change on the site is the footer link's label (old „Fragen und Fehler", new „Datenfehler melden"); the link's target remains whatever the operator configures.

## Conflict surface vs A3

`worktree-a3-plan` (tip 50e7dfd) branches from merge base 265e407, not main 69ade54. `git diff main...worktree-a3-plan` therefore shows A3 hunks in **merge-base line numbers**.

Main has changed `scripts/build_dip_pulse_site.py` since then, all from base line 3253 onward. Measured from `git show <rev>:scripts/build_dip_pulse_site.py`:
- `_inputs_hash` is at line 3062 in both.
- The footer is base 4777 / main 4818 (+41).
- `def safe_issues_url` is base 12200 / main 12244 (+44).
- The help text is base 12665 / main 12709 (+44).

| File | A3 change | Nearest A3 hunk (base lines) | This plan's edit (main lines) | Verdict |
|---|---|---|---|---|
| `_inputs_hash` (main 3069, 3090) | adds `excluded_sittings` param and `"excluded"` key | `@@ -3070,6`, `@@ -3090,6` (main 3070/3090, same) | **none** | Untouched by design (S6 is configuration). |
| `export_distribution_data` / `_run_export` (main 3681, 3732, 3767, 3833, 4087) | `excluded_sittings` threading, `split_rede_ids` | `@@ -3640`, `-3692`, `-3721`, `-3787`, `-3877`, `-4080` | **none** | No overlap. |
| `render_daten_datenstand`, `_daten_page_styles` | excluded-sittings line, scope line, one CSS line | `@@ -4231`, `-4247`, `-4606` | none | No overlap. |
| Daten footer label (O7) | none | nearest A3 hunks are `@@ -4606` (171 lines before) and `@@ -7962` | main 4818 (base 4777) | Clean. |
| comment above `_ISSUES_URL_RE` (O7) | none | `@@ -12094` (`apply_to_args`), `@@ -12511` | main 12238 (base 12194) | ~100 lines of clearance. Clean. |
| `--data-issues-url` help text (O7) | `parse_args` inserts two lines after `args = parser.parse_args()` | `@@ -12665,6`: base 12665 is this help line, as hunk context | main 12709 (base 12665) | **Nearest collision.** Two unchanged lines (`)` and `args = parser.parse_args()`) separate the edits, so git should merge cleanly. If it conflicts, keep A3's two inserted lines and this plan's help string. |
| `tests/test_daten_page.py` (O7) | r5 column list | `@@ -181,7` (line 184) | ~350–361 | Clean. |
| `docs/project-documentation.md` | export format 11 prose | `@@ -441,9` changes lines 444 and 446; line 442 is its context | line 442 (`--data-issues-url` row) | **Second collision.** One unchanged line (443) separates the edits, so git should merge cleanly. If it conflicts, take A3's 444/446 and this plan's 442 (independent rows). |
| `TODOS.md` | heavy | nearest hunks `@@ -416,12` (ends ~428) and `@@ -601,7` | Community section, main 451–470, rewritten at ship time | Between A3 hunks, no overlap. Rewrite only that heading's body. |
| `docs/adr/0003-licences-and-impressum.md` | none | — | D5 amendment | No conflict. |
| `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/ISSUE_TEMPLATE/*`, `tests/test_issue_forms.py` | none (A3 touches none; its `.github/` diff is empty) | — | new / top-of-file | No conflict. |

**Decision:** the pre-fill is configuration plus documentation, so it needs neither a helper nor a deferral. The only code edits are label text (O7), none inside an A3 hunk. Merge order does not matter. Re-run the `git diff main...worktree-a3-plan -- <file>` checks at implementation time if A3 has moved.

Kept out of scope because of A3: the ~15 other page footers (abgeordnete near base 8492/8597 and facts near base 9554–9780 are A3 hunks). See O8/B5.

## Owner decisions

**Answered by the owner on 2026-11-01. Every recommendation is accepted:**
- O1: the S5 text is approved as drafted.
- O2: `CODE_OF_CONDUCT.md`.
- O3: `needs-triage` plus `datenfehler`/`bug`.
- O4: English, with a German summary.
- O5: omit the placeholder link.
- O6: form wording approved as drafted, including the reply sentence; no checkbox.
- O7: „Datenfehler melden (GitHub)".
- O8: after A3 merges and before the flip, recorded as a TODO.
- O9: the checklist as written.
- O10: merge now.
- O11: impersonal register.

Label check, 2026-11-01: `needs-triage` and `bug` exist; `datenfehler` does not yet.

The original options follow for the record.

All public text is the owner's call. AskUserQuestion was not available in this planning session, so each recommendation below is the working assumption until the owner answers. **(rec.)** marks the recommendation.

| # | Decision | Options | Recommendation |
|---|---|---|---|
| O1 | Conduct rules text | the S5 draft as is / edited / shorter | **(rec.)** S5 draft. It covers ADR D5's three rules, plus „Belege statt Behauptungen" and the enforcement sentence. The owner reads and approves it before merge. |
| O2 | Conduct file name | `CODE_OF_CONDUCT.md` (GitHub-recognised, linked on the new-issue page) / `docs/regeln.md` / section inside CONTRIBUTING | **(rec.)** `CODE_OF_CONDUCT.md` with the German title „Regeln für Beiträge". |
| O3 | Label names auto-applied by the forms | `needs-triage` only / `needs-triage` + kind labels | **(rec.)** `needs-triage` on both (the triage role in `docs/agents/triage-labels.md`), plus `datenfehler` on Datenfehler and GitHub's default `bug` on Fehler auf der Seite. **Owner step:** create any missing label, or the form silently skips it. This is part of done-criterion (c). |
| O4 | `SECURITY.md` language | English / German / both | **(rec.)** English with a two-sentence German summary at the top. |
| O5 | A placeholder private-matters contact link before the Impressum | placeholder now, replaced before going public / omit until the Impressum exists | **(rec.)** Omit it. A placeholder URL in `config.yml` is a live, clickable link that can survive the visibility flip unnoticed. Adding the real link later is one YAML entry (B2), and S7 guards against placeholder markers. Either way, the flip waits for B2. |
| O6 | Form wording (S2/S3 labels, descriptions, intro, the reply sentence); a required „Ich halte mich an die Regeln" checkbox | as drafted / edited; checkbox yes/no | **(rec.)** As drafted after the design review (DR1–DR3), no checkbox (unenforced while private, no behavioural value). The reply sentence „Bestätigte Fehler werden korrigiert und das Issue geschlossen; eine persönliche Antwort ist nicht garantiert" is a public commitment, so the owner confirms it. |
| O7 | Footer link label on the Daten page | „Fragen und Fehler" (today) / „Fehler melden" (ADR wording) / „Datenfehler melden" / „Datenfehler melden (GitHub)" | **(rec.)** „Datenfehler melden (GitHub)" (changed by the design review, DR4). It names where the link goes. „(GitHub)" warns before the click that the report happens on GitHub and needs an account; most readers are not developers (ADR D5). „Fragen" has no form. If the owner keeps today's label, S6 is documentation only and no code changes. |
| O8 | A per-page report link on every page (B5) | now / after A3 merges and the domain exists / never | **(rec.)** After A3 merges, as a new TODO, together with the site base URL. It touches ~15 footers, several inside A3 hunks, and needs `issues_url` threaded into every renderer. The design review rates this the largest remaining journey gap (DR6): a reader who sees a wrong figure on a sitting or vote page has no report link there. Schedule it before the flip, not after. |
| O9 | Visibility-flip checklist | — | **(rec.)** Before the flip: B2 and B6 are in place (the private channel exists), labels exist (O3), and the public build is ready to set `--data-issues-url` (B4). Directly after the flip: switch on PVR (B3), and rewrite the S1 sentence „until then the repository is not public". Between flip and PVR, the window is minutes. B1 (`security.txt`) follows the domain. |
| O11 | Register of the public German text (forms, chooser, CONTRIBUTING section) | impersonal / „du" / „Sie" | **(rec.)** Impersonal, matching the site, which never addresses the reader (DR5). CODE_OF_CONDUCT.md is already impersonal. |
| O10 | Merge this batch now, or hold it until the flip is scheduled | merge now / hold | **(rec.)** Merge now. While private, everything is inert for the public, and the owner sees the forms working before strangers do. Holding would only move the review and the label setup to launch week. |

Owner steps (no code): approve O1/O4/O6 text; create labels (O3); run the manual checks (b)–(e) after merge; the flip checklist (O9).

## Review log

### Eng review (`/gstack-plan-eng-review`, 2026-11-01)

AskUserQuestion was not available to this planning agent. Per the caller's instruction, each choice took the recommended option, and every public-text choice is also listed under Owner decisions.

**Scope Challenge.**
- The plan touches ~12 files: 6 new (SECURITY.md, CODE_OF_CONDUCT.md, 3 form/config files, tests/test_issue_forms.py) and 6 edited (CONTRIBUTING.md, project-documentation.md, ADR 0003, TODOS.md at ship, plus build_dip_pulse_site.py and test_daten_page.py only with O7). It adds 0 new classes or services. That trips the 8-file complexity gate.
- D1, structure: the original arrangement was kept. Each new file is a GitHub-recognised path or a test, and no smaller arrangement delivers the same artifacts. The R6 cut (below) removed the only code module from scope.
- Result: scope accepted as-is; R6 is a smaller arrangement of the same feature, not a feature cut.

**Reality rows.**
- premise-table pass. Every premise in "What the item asks" and "What a private repository means" carries a file:line or a docs quote (unverified=0). The label list is measured by grep.
- already-done pass. `git log --all -- SECURITY.md CODE_OF_CONDUCT.md .github/ISSUE_TEMPLATE` is empty (local refs; no fetch, offline).
- surface-check pass. `--data-issues-url` is at main 12707, `safe_issues_url` at 12244, `_ISSUES_URL_RE` at 12241. Its regex accepts a query string.
- binding-decisions pass. ADR 0003 D5 is the binding decision, and S8 records every deviation. `gstack-decision-search` returned nothing for this branch.
- numbers pass. Line offsets are measured from `git show` of both revisions; the ~15 footers are counted from grep `<footer` (20 matches).
- deferred-asks: finding, resolved. The TODO's own asks left out are B1–B7, each with its reason.
- pr-count pass. One PR.

**Findings and dispositions.**

| ID | Sev / conf | Source | Finding | Disposition |
|---|---|---|---|---|
| R1 | P2 / 9 | native, `build_dip_pulse_site.py:12238,12709`, `test_daten_page.py:360` | The label rename missed the comment and the help text. The plan claimed the help text "stays valid". | accepted (recommended), folded into S6 and the conflict table |
| R2 | P3 / 8 | native | A hostile release tag in the helper's URL needed a test | superseded by R6 (no helper, no tag in the URL) |
| R3 | P3 / 6 | native | It is undocumented whether relative links resolve in form markdown | accepted: absolute URLs |
| R6 | High / 9 | outside voice #2, verified: `_ISSUES_URL_RE = re.compile(r"^(https?://\|mailto:\|/)")` passes a query string, and the footer has a constant page | The render-time helper duplicates what a configured query string already does | accepted (recommended): S6 is configuration plus docs; the helper moves to B5/O8 |
| R7 | High / 9 | outside voice #1 | O9 put PVR before the flip, which is impossible, and never rewrote the S1 sentence | accepted: O9 reordered |
| R8 | Medium / 8 | outside voice #4 | Text-match tests cannot catch a malformed form | accepted: S7 states its limit; owner check (d) added |
| R9 | Medium / 8 | outside voice #5 | The private-matters dead end; the placeholder guard missed the root Markdown files | accepted: guard extended; B6 is a flip gate |
| R10 | Medium / 8 | outside voice #6 | ADR D5 drifts from what ships | accepted: S8 |
| R11 | Medium / 8 | outside voice #7 | Label existence was not in the done-criterion | accepted: criterion (c) |
| OV3 | High | outside voice #3 | Hold the whole batch until the flip | partly accepted: O10 asks the owner; recommendation is merge now |
| OV8 | Low | outside voice #8 | A relative `seite` is ambiguous between preview and production | accepted as known limit; B5 |
| OV9 | Low | outside voice #9 | The A3 section is oversized | rejected: the caller required an exact conflict check |
| OV10 | Low | outside voice #10 | Nothing pins the hard-coded repository URL | rejected: grep-able, changes with the rename sweep |

**Section results.**
- Architecture: R1, R6 (after the outside voice).
- Code quality: R3.
- Tests: R2 (superseded), R8, R9. The coverage diagram is below.
- Performance: no issues found. The change is static text plus one rendered link.

```
CODE PATHS                                         USER FLOWS
[+] render_database_page footer (main 4818)          [+] Reader reports a data error
  ├── issues_url unsafe/empty → no link                ├── [★★ TESTED] link hidden w/o flag — test_daten_page:350
  │     [★★★ TESTED] test_daten_page:350 table          ├── [GAP→S7/test row] link opens Datenfehler w/ seite
  └── issues_url safe → <a href=esc(url)>              │     (owner manual check (c) for GitHub side)
        └── [GAP→add row] query string &amp; escaping  └── [MANUAL] private repo: non-member gets 404
[+] .github/ISSUE_TEMPLATE/*.yml (GitHub renders)    [+] Reader opens chooser
  ├── [GAP→S7] documented URL keys == form ids         ├── [MANUAL (b)] two forms + security link
  ├── [GAP→S7] ids valid + unique, needs-triage label  └── [MANUAL (d)] no template error shown
  └── [MANUAL (d)] schema validity (no YAML parser)
COVERAGE after plan: code paths 5/5 by test or named manual check; schema validity manual only.
```

**Failure modes.**
- An invalid form YAML: GitHub drops or flags the template silently in CI. Covered by manual check (d). It is not silent to the owner, who looks.
- A missing label: issues arrive unlabelled. Covered by criterion (c).
- The flag is set before the flip: public readers get a 404. Mitigation: the flag is opt-in, and B4 plus O9 gate it.
- **Critical gaps: 0.**

**NOT in scope:**
- B1–B7, each with its reason above;
- per-page links (O8);
- an issue type, projects or assignees in the forms;
- Discussions (ADR D5: off until demand).

**What already exists:**
- `safe_issues_url` plus `esc` already deliver a configured URL safely; reused, not rebuilt.
- `docs/agents/triage-labels.md` names the triage label strings.
- The release script's `SHA256SUMS` backs the "tampered download" scope.

**Parallelization:** sequential implementation, no parallelization opportunity. It is mostly text files, plus one small test file.

**Outside voice.** Codex was not run: `codex_reviews` is unset, but the caller forbade going online. A native fallback (Plan subagent, Sonnet, 5-minute timer) completed within the timer. Its 10 findings are above.

### Design review (`/gstack-plan-design-review`, 2026-11-01)

AskUserQuestion was not available to this planning agent. Each finding took the recommended option, and every public-text choice is also listed under Owner decisions (O6, O7, O8, O11).

**System audit.**
- UI scope: the two GitHub issue forms, the `config.yml` chooser, the German text readers see there and in CONTRIBUTING/CODE_OF_CONDUCT, and the Daten page footer link label.
- GitHub renders the forms. Layout, typography, focus, labels and mobile behaviour are GitHub's, so the design surface is information architecture, wording and journey.
- No `DESIGN.md` exists (docs/designs/ holds per-feature design docs only). This batch adds no visual component, so `/design-consultation` is not needed for it.
- Mockups were skipped: the gstack designer needs a network model, which the caller forbade, and GitHub renders the forms anyway.
- Outside design voices were skipped for the same offline reason.

**Classifier.** OPERATE. The reader finishes one task, filing a checkable report. Utility language beats mood.

**Findings and dispositions.**

| ID | Pass | Finding | Disposition |
|---|---|---|---|
| DR1 | 1 Info arch | The chooser descriptions overlapped. „Etwas wird falsch dargestellt" (Seitenfehler) also describes a wrong number, so readers would satisfice into the wrong form. | accepted: the split is now content-vs-source against page-not-working; the Seitenfehler intro points to Datenfehler |
| DR2 | 2 States | The pre-filled `seite=database.html` is wrong whenever the error is on another page, and the only report link is on the Daten page. The old description („ist sie schon eingetragen") implied it was right. | accepted: the description tells the reader to replace it |
| DR3 | 2 States | No success expectation. After submitting, the reader hears nothing, and the goodwill reservoir drains. | accepted: one sentence on what happens next (O6 confirms the commitment) |
| DR4 | 3 Journey / 6 A11y | A GitHub account wall. Most readers have none (ADR D5). The footer link drops them on a login page without warning. | accepted: footer label „Datenfehler melden (GitHub)" (O7) and an account sentence in CONTRIBUTING |
| DR5 | 4/5 Copy, consistency | The forms said „du", but the site never addresses the reader directly. | accepted: impersonal wording throughout (O11) |
| DR6 | 3 Journey | The link exists only on the Daten page, so errors seen on sitting, vote or MP pages have no entry point. | deferred, as already decided in O8; reinforced to „before the flip" |
| DR7 | 1 Info arch | Datenfehler must be listed first. GitHub's chooser order is not documented in the pages read. | accepted as verification: criterion (b), with an ordering-prefix fallback |

**Journey storyboard (Datenfehler, after fixes).**

```
STEP | USER DOES                          | USER FEELS             | PLAN SPECIFIES?
-----|------------------------------------|------------------------|-----------------------------------------
1    | Sees a figure that contradicts     | doubt, mild annoyance  | only on the Daten page today (DR6/O8)
     | the Plenarprotokoll                |                        |
2    | Clicks "Datenfehler melden (GitHub)"| knows where it goes    | label O7; account warning DR4
3    | Lands in the form, page pre-filled | guided, low effort     | seite pre-fill S6; replace hint DR2
4    | Pastes site text, source text, link| competent ("I have     | field order: page, site, source, link
     |                                    | proof")                |
5    | Submits                            | wants acknowledgment   | reply sentence DR3; labels O3
6    | Fix ships, issue closed            | trust ("they listen")  | closing is the acknowledgment (DR3)
```

**Interaction states.**

```
FEATURE               | EMPTY / OFF             | ERROR                          | SUCCESS               | PARTIAL
----------------------|-------------------------|--------------------------------|-----------------------|-----------------------------
Footer link           | no flag: no link        | repo private: GitHub 404 (B4   | form opens, seite     | error on another page: the
                      | (existing test)         | gates the flag)                | filled                | DR2 hint
Datenfehler form      | fields empty without    | required fields unenforced     | issue with labels     | datenstand blank unless the
                      | the link                | while private                  | (O3)                  | download is affected
Chooser               | n/a                     | missing label: silently        | two forms + security  | n/a
                      |                         | unlabelled (criterion c)       | link (b)              |
```

**Pass scores.** Initial impression (Step 0): 6/10.

| Pass | Before | After | Remaining gap |
|---|---|---|---|
| 1 Info architecture | 6 | 8 | chooser order unverified until merge (DR7) |
| 2 States | 5 | 8 | the private-repo window is inherent |
| 3 Journey | 5 | 7 | no per-page entry point (DR6, deferred to O8) |
| 4 AI slop / copy | 7 | 8 | none material; GitHub renders the UI |
| 5 Design system | 6 | 7 | no DESIGN.md; the register is now aligned |
| 6 Responsive / a11y | 6 | 8 | GitHub owns form a11y; the footer link inherits site link styles |

Pass 7 (unresolved design decisions): resolved DR1–DR5 and DR7; deferred DR6 (O8). The public-text calls O6, O7 and O11 await owner confirmation.

**NOT in scope:**
- per-page links (O8/B5);
- a GitHub-free report path for data errors (it needs the Impressum e-mail, B6);
- a visual redesign of the footer;
- an issue `type` or project boards.

**What already exists:**
- the footer's „ · "-separated link row (main 4818), reused as-is;
- the impersonal register of the site copy;
- GitHub's form rendering, labels and validation messages.

## Implementation Tasks

- [ ] **T1 (P1, human: ~2h / CC: ~15min):** forms and config. Write S2, S3 and S4 with absolute links.
  - Surfaced by: S2–S4, R3, O5; design review DR1–DR3, DR5, DR7.
  - Files: `.github/ISSUE_TEMPLATE/{datenfehler,seitenfehler,config}.yml`.
  - Verify: S7 tests; owner checks (b) and (d).
- [ ] **T2 (P1, human: ~1h / CC: ~10min):** docs. Write `SECURITY.md` and the `CODE_OF_CONDUCT.md` draft, plus the CONTRIBUTING section.
  - Surfaced by: S1, S5, R7, R9; design review DR4 (GitHub-account sentence in CONTRIBUTING).
  - Files: `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`.
  - Verify: owner approval of O1/O4; placeholder-guard test.
- [ ] **T3 (P1, human: ~1h / CC: ~10min):** drift test. Add `tests/test_issue_forms.py`.
  - Surfaced by: R8, R9.
  - Files: `tests/test_issue_forms.py`.
  - Verify: red with a mistyped id, then green.
- [ ] **T4 (P2, human: ~30min / CC: ~5min):** pre-fill documentation and label. Document the S6 flag value; with O7, change the label in all four places and add the test row.
  - Surfaced by: R1, R6; design review DR4 (label per O7).
  - Files: `docs/project-documentation.md`, `scripts/build_dip_pulse_site.py`, `tests/test_daten_page.py`.
  - Verify: `python3 -m unittest tests.test_daten_page tests.test_issue_forms`.
- [ ] **T5 (P2, human: ~20min / CC: ~5min):** ADR. Write the D5 amendment.
  - Surfaced by: R10.
  - Files: `docs/adr/0003-licences-and-impressum.md`.
  - Verify: read against S8.
- [ ] **T6 (P3, owner):** labels and manual checks (b)–(e) after merge; the flip checklist O9.

## Design Review Completion Summary

```
+====================================================================+
|         DESIGN PLAN REVIEW: COMPLETION SUMMARY                     |
+====================================================================+
| System Audit         | no DESIGN.md; UI = GitHub forms, chooser,   |
|                      | German copy, Daten footer label             |
| Step 0               | 6/10 initial; all 7 passes, no focus cut    |
| Pass 1  (Info Arch)  | 6/10 -> 8/10 after fixes                    |
| Pass 2  (States)     | 5/10 -> 8/10 after fixes                    |
| Pass 3  (Journey)    | 5/10 -> 7/10 after fixes                    |
| Pass 4  (AI Slop)    | 7/10 -> 8/10 after fixes                    |
| Pass 5  (Design Sys) | 6/10 -> 7/10 after fixes                    |
| Pass 6  (Responsive) | 6/10 -> 8/10 after fixes                    |
| Pass 7  (Decisions)  | 6 resolved, 1 deferred (DR6 -> O8)          |
+--------------------------------------------------------------------+
| NOT in scope         | written (4 items)                           |
| What already exists  | written                                     |
| TODOS.md updates     | 0 proposed (DR6 is already O8's TODO)       |
| Approved Mockups     | 0 generated (offline; GitHub renders forms) |
| Decisions made       | 6 added to plan (auto, recommended option)  |
| Decisions deferred   | 1 (DR6)                                     |
| Overall design score | 5/10 -> 7/10                                |
+====================================================================+
```

Below 8 overall: Pass 3 stays at 7 because the only report link is on the Daten page (DR6, deferred to O8). Pass 5 stays at 7 because there is no DESIGN.md, which this batch does not need.

**Unresolved design decisions:**
- O6, O7 and O11 (form wording with the reply sentence, footer label, register) were auto-decided to the recommendation and await the owner.
- DR6 is deferred to O8.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Outside Review | native Plan subagent (Codex not run: offline constraint) | Independent 2nd opinion | 1 | unavailable (in-host fallback completed) | 10 findings, 7 accepted, 1 partly, 2 rejected |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES OPEN (not persisted) | 6 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | ISSUES OPEN (not persisted) | score: 5/10 → 7/10, 6 decisions |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

- **OUTSIDE COVERAGE:**
  - Eng phase: codex unavailable (network forbidden by the caller); the native Plan fallback completed.
  - Design phase: outside design voices skipped (offline), so there is no outside design coverage.
- **VERDICT:** no review CLEAR.
  - All eng and design findings are folded into the plan, and none blocks implementation.
  - The review logs could not be written, because the sandbox denied writes under `~/.gstack/`. eng review required.

**UNRESOLVED DECISIONS:**
- O1 to O11 were auto-decided to the recommendation (AskUserQuestion unavailable) and await the owner's confirmation. They cover public text, label names, the footer label, the register and merge timing.
- DR6 (a report link on every page) is deferred to O8.
