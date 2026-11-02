# Security policy

**Deutsch:** Sicherheitslücken bitte nicht als öffentliches Issue melden, sondern über die private Meldefunktion von GitHub („Report a vulnerability" im Reiter Security). Diese steht mit der öffentlichen Veröffentlichung des Repositorys zur Verfügung; bis dahin ist das Repository nicht öffentlich. Falsche Zahlen oder Zuordnungen sind keine Sicherheitslücken, sondern Datenfehler: dafür gibt es das Formular „Datenfehler".

## Reporting

- Use GitHub's private vulnerability reporting („Report a vulnerability" on the repository's Security tab).
- Private reporting opens with the public release; until then the repository is not public.
- Do not open a public issue for a vulnerability.

## In scope

- **Injection through source text into HTML.** DIP, protocol XML, bundestag.de or abgeordnetenwatch text that reaches a generated page unescaped, or a link `href` with a scheme that is not allowed.
- **Leaked keys.** `DIP_API_KEY` or an LLM provider key in the repository, its history, build output, an export or a release asset.
- **A tampered download.** A release asset or export file that does not match its published `SHA256SUMS` or manifest `sha256`. The release script (`scripts/publish_dip_pulse_data.py`) writes both.

## Out of scope

- A wrong figure, a wrong attribution or a misparsed speech. These are data errors: use the „Datenfehler" form.
- Vulnerabilities in DIP, bundestag.de, abgeordnetenwatch or GitHub themselves. Report them to their operators.
- Denial of service against static hosting.
- Missing security headers on a static site without logins or forms. Revisit if the site gains any input.
- Reports produced only by automated scanners, without a demonstrated impact.

## Supported versions

Only the latest `main` and the latest data release (`data-<YYYY.MM.DD>`). Old releases are not patched; a fix ships in the next release.

## What to expect

One person runs the project. Reports are read and answered at the operator's discretion. There is no bounty and no fixed response time.
