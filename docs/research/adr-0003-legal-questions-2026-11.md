# ADR 0003 open legal questions 1–4 and 6–8: research pass

Research note, 2026-11-21. It works through the questions in `docs/adr/0003-licences-and-impressum.md` ("Open questions for a lawyer before launch"), except question 5. Question 5 (redistributing the bundestag.de roll-call data) was put to parlamentsdokumentation@bundestag.de on 2026-11-21 and is out of scope here.

> **This is research, not legal advice.** It was written by an AI agent for the project owner, who decided on 2026-11-21 to replace a lawyer with a research pass plus an independent second read. It reads statutes, terms, official guidance and a few decisions. It does not replace a lawyer's opinion. Where research is not enough, the note says so (see "Where research is not enough").

**Evidence kinds.**
- **Read** means the text was fetched on 2026-11-21 and the quote was checked against that text.
- **Secondary** means it was seen only through another page that reports it.
- **Not found** means the search did not turn it up. It does not mean the thing does not exist.

Quotes keep the source's spelling.

**Status on main, 2026-11-22.** The research below was written on 2026-11-21 and its text is unchanged. Owner decisions and PR #204 (v0.46.39.0) landed after it, so a few of its statements about the repository describe the state before them. Each such place carries an *Update 2026-11-22* line, and the section "Status on main, 2026-11-22" before the short-answer table lists what is done and what is still open. The positions and risk ratings are not changed.

**What the project does today.** Each question depends on these facts, taken from the repository on 2026-11-21:
- The export ships the full text of every Rede (`speeches.text`) and Beitrag, with the paragraphs joined by single spaces (`LICENSE-DATA.md`, "What we changed").
- `speeches.text` holds only the speaker's own words: „Chair text and comments never become speaker text“ (`speech_segments`, `scripts/validate_dip_protocol.py`). Applause, Zwischenrufe and the chair's remarks are left out. `LICENSE-DATA.md` does not say so (second read, challenge 16). *Update 2026-11-22: it says so now, in "What we changed" and in the `text` entry of `scripts/data_dictionary.json` (PR #204).*
- The repository has been public since 2026-11-06. It already carries full Plenarprotokoll XML files in `tests/fixtures/` and MP names with protocol URLs in `scripts/person_corrections.json`. No DIP source notice covers them (second read, challenge 6). *Update 2026-11-22: the root `LICENSE` now names the source and terms of this material (PR #204).*
- An MP's profile page lists that MP's speeches as a 240-character snippet (`text[:240]`, `scripts/validate_dip_protocol.py`) with a link, not as full texts (`scripts/build_dip_pulse_site.py`, "Reden im Bundestag").
- The site writes two localStorage keys (as of 2026-11-21), each only after a click (`DATENSCHUTZ_STORAGE_KEYS`). The AI-summary key is written only on pages that carry an AI summary toggle. AI summaries are out of v1 (`PRODUCT.md`), so the v1 site writes only the theme key. `datenschutz.html` still says „Zwei Einstellungen speichert die Website“, which is not true of v1. *Update 2026-11-22: both settings are in `sessionStorage` and `datenschutz.html` was reworded (PR #204). It still lists both keys, because per `TODOS.md` the reference build's pages carry the AI-summary toggle; the key leaves the list when the AI summaries leave the surface.*
- There are no cookies, no tracking and no third-party resources (`datenschutz.html`).
- There is no advertising and no payment. Fakt der Woche and the AI summaries are off the v1 site.

## Status on main, 2026-11-22

Checked against main (v0.46.43.0). The decisions are in ADR 0003, "Amendment 2026-11-21"; the build changes came in PR #204.

**Done since the note was written:**
- **Q1:** the owner chose the home address for the Impressum. That settles the question; a c/o service would reopen it.
- **Q2, public repository:** the root `LICENSE` names the source and terms of the Bundestag material held in `tests/fixtures/`, `scripts/` and `docs/`, and says the DIP terms apply as conditions of the source, not as terms the project adds.
- **Q7, omissions:** `LICENSE-DATA.md` ("What we changed") and the codebook entry for `text` in `scripts/data_dictionary.json` say that `speeches.text` and `contributions.text` hold only the speaker's own words. The paragraph breaks are not kept, and that is stated too.
- **Q8:** the theme and AI-summary collapse state are stored in `sessionStorage` (`scripts/render_dip_pulse_html.py`). `datenschutz.html`, built by `render_datenschutz_page` in `scripts/build_dip_pulse_site.py`, names § 25 Abs. 2 Nr. 2 TDDDG and says the values live in the tab's session storage.
- **Q4, text:** `datenschutz.html` ("Personen in den Daten") now names Art. 6 Abs. 1 lit. f, Art. 9 Abs. 2 lit. e and Art. 85 with § 23 MStV, the recipients, the archive, and the right to object (Art. 21).

**Still open, as the note says:**
- **Q4:** the written inquiry to the Cyber Law Clinic of Universität Hamburg (or, if it declines, to the Landesdatenschutzbeauftragte), the Art. 30 record with the Art. 35 threshold note, and the takedown and erasure process. `TODOS.md`, "ADR 0003 legal questions: what the research leaves to do", tracks them. The owner decided this route on 2026-11-21; it is not yet sent.
- **Q2:** the sentence in `LICENSE-DATA.md` „The DIP terms, in particular no. 5, continue to apply to any reuse of the DIP layer“ is unchanged, and so is the layer note for the three quoting columns (`documents.forderung`, `vote_passages`, `votes.inversion_excerpt`).
- **Q7:** the paragraph breaks are still joined with single spaces. The note's cost estimate stands, with one correction: `clean(` is called 86 times in `scripts/persist_dip_pulse_store.py` on main, not 85.
- **Q8:** `datenschutz.html` still lists the AI-summary key (see above). Its wording about the tab (a duplicated tab copies `sessionStorage`) is tracked in `TODOS.md`.
- **Q6:** unchanged. The Impressum names the operator as Verantwortlicher under § 18 Abs. 2 MStV (ADR 0003 D4).
- **Hosting:** the Art. 28 DSGVO agreement with the host stays open with the hosting decision.

---

## Short answer

| Q | Position | Risk | Removable by engineering | Needed before |
|---|---|---|---|---|
| 1 Impressum address | A c/o or office-service address is enough only if the operator can be served there, which takes a written Zustellungsbevollmächtigung. A Postfach or a bare mail-forwarding address is not enough. | Low with the home address. Medium with a c/o service. | No | Public site |
| 2 DIP clause 5 next to CC layers | Follow clause 5 in good faith, although its enforceability is doubtful. Pass it on as a notice of the source, never as the project's own term. Columns of the CC BY layer that quote source wording keep that wording under the DIP layer. | Low. Medium if the site ranks or labels MPs judgmentally. | Partly: a notice for the public repository's fixtures, and the layer of three quoting columns | Now, for the public repository; otherwise the first data release |
| 3 Speeches: § 5 or § 48 UrhG | Ship the full corpus. It is covered whether the speeches are amtliches Werk (§ 5 Abs. 2) or the speakers' works used under § 48 Abs. 1 Nr. 2. Never publish a file or page that collects one MP's speeches in full. | Low as built | Yes. Per-MP views stay snippets and links, which they already are. | First data release; the line holds for every later feature |
| 4 GDPR basis | For MP data: Art. 6 Abs. 1 lit. f, plus Art. 9 Abs. 2 lit. e for votes, speeches and Fraktion. For third parties named in speeches (Art. 9 and 10 data), lean on Art. 85 / § 23 MStV as the BGH now reads it. State the bases, keep a record of processing, and decide how erasure works against fixed releases. | Low for MP data. Medium for third-party data in the full-text corpus. | Partly. The Datenschutz text and the record are about a day's writing. The corpus question cannot be removed without dropping texts. | First data release |
| 6 Journalistisch-redaktionell? | Uncertain. The BGH's wide reading may reach a curated „Aktuell“ view. Act as if it does: keep naming the § 18 Abs. 2 Verantwortlicher and meet the § 19 diligence duty, which source tracing already does. | Low | Not needed. Editorial texts (AI summaries, Fakt der Woche) would make it certain. | Public site |
| 7 Paragraph breaks and § 62 UrhG | Joining paragraphs is very likely no „Änderung an dem Werk“. The real gap is that the export leaves out Zwischenrufe and chair text without saying so: a „Kürzung“ that § 63 and DIP 4b require to be marked. Fix the change notice, and keep the paragraph breaks. | Low once the notice is fixed. Medium until then. | Yes: a notice text now, and paragraph breaks in the export | First data release |
| 8 localStorage and § 25 TDDDG | No consent is needed for storing the choice. But the DSK reads „unbedingt erforderlich“ as one session for a service without login. Store the theme in `sessionStorage` and state § 25 Abs. 2 Nr. 2 TDDDG in `datenschutz.html`. | Low with `sessionStorage`. Medium as built. | Yes: one storage call and one sentence | Public site |

**Where research is not enough:** question 1 if the owner wants a c/o address, and question 4 for third-party data in the full-text corpus and for erasure against fixed releases. Details and free routes are under "Where research is not enough".

**Fix-now actions the research turned up** (the owner decides; this note changes none of them). *Update 2026-11-22: all three are done, see "Status on main".*
- **Public repository:** add a DIP source and change notice for `tests/fixtures/*.xml` and the protocol-derived data in `scripts/` (question 2).
- **`LICENSE-DATA.md` "What we changed":** say that `speeches.text` leaves out Zwischenrufe, applause and chair text (question 7). Its silence on this is a misleading statement in user-facing output.
- **`datenschutz.html`:** stop listing the AI-summary key while v1 does not write it (question 8). Add the legal bases (questions 4 and 8).

---

## Question 1: is a c/o or Impressum-service address enough under § 18 MStV?

### Law and terms

- **§ 18 Abs. 1 MStV** (Read, [gesetze-bayern.de](https://www.gesetze-bayern.de/Content/Document/MStV-18)): „Anbieter von Telemedien, die nicht ausschließlich persönlichen oder familiären Zwecken dienen, haben folgende Informationen leicht erkennbar, unmittelbar erreichbar und ständig verfügbar zu halten: 1. Name und Anschrift […]“.
- **§ 18 Abs. 2 MStV** adds, for journalistic-editorial offers, „einen Verantwortlichen mit Angabe des Namens und der Anschrift“. That person must have a „ständigen Aufenthalt im Inland“.
- **§ 5 DDG** (Read, [gesetze-im-internet.de](https://www.gesetze-im-internet.de/ddg/__5.html)) covers only „geschäftsmäßige, in der Regel gegen Entgelt angebotene digitale Dienste“. A site without ads, payments or sales is not one. The NLM guide below says a free service also counts as „geschäftsmäßig, wenn darin regelmäßig Werbung zur Kostendeckung geschaltet wird“, and there is none here. The same section also says „Ein Telemedium ist auch dann ein digitaler Dienst, wenn mit der angebotenen Leistung zwar Geld verdient werden kann, der Anbieter dies aber nicht tut.“ That reading would pull in § 5 DDG too. It changes nothing in practice, because the built Impressum already gives name, address and e-mail under the heading „§ 5 DDG und § 18 Abs. 1 MStV“. On either reading, the address rule is the same.
- **Sanction.** Under § 115 Abs. 1 Satz 2 Nr. 1 MStV (Read, [gesetze-bayern.de](https://www.gesetze-bayern.de/Content/Document/MStV-115)), it is an Ordnungswidrigkeit if someone „entgegen § 18 Abs. 1 bei Telemedien den Namen oder die Anschrift […] nicht oder nicht richtig verfügbar hält“. § 115 Abs. 2 sets the fine at up to 50,000 euros in that case.
  - § 18 Abs. 2 is not in that list. The Wissenschaftliche Dienste conclude that the Abs. 2 duty is „eine sanktionslose Obliegenheit“ ([WD 10 - 3000 - 035/22](https://bundestag.de/resource/blob/944576/fe2087b8762a42290d4172c6358e17cf/WD-10-035-22-pdf-data.pdf), 2023, Read).

### Guidance and precedent

- **Niedersächsische Landesmedienanstalt**, „Leitfaden zur Impressumspflicht im Internet“ (Read, [nlm.de PDF](https://www.nlm.de/fileadmin/dateien/pdf/leitfaden_impressumspflicht_2024.pdf)). Section 2.3.2 is the case for non-commercial offers under § 18 Abs. 1 MStV. It requires a „ladungsfähige Anschrift“ and continues:
  - „Dies kann auch die Anschrift einer Agentur, eines Büroservices, Rechtsanwalts oder Familienangehörigen sein, wenn dort z.B. eine Klage wirksam zugestellt werden kann. Voraussetzung hierfür ist die Erteilung einer Zustellungsbevollmächtigung […]. Die Angabe einer bloßen Drittanschrift bzw. eines Postfachs reicht nicht.“
  - It also says private use is „sehr eng ausgelegt“.
  - Section 4 says competitors may send a warning letter.
- **Medienanstalt NRW**, „Infos kompakt: Impressumspflicht“ (Read through the research agent, not re-checked, [PDF](https://www.medienanstalt-nrw.de/fileadmin/user_upload/lfm-nrw/Regulierung/Beschwerde/Infos_kompakt/Infos_kompakt-Impressumspflicht.pdf)): „Ein Postfach reicht nicht, denn bei der Adresse muss es sich um eine ladungsfähige Anschrift handeln.“ The leaflet predates the MStV and cites § 55 RStV.
- **OLG Hamm, 07.05.2015, 27 W 51/15** (Secondary, via [e-recht24.de](https://www.e-recht24.de/impressum/8369-impressum-c-o-adresse.html)) allowed a c/o addition for a GmbH, where it helps to find a person who can accept service. The decision itself was not read.
- **Open Parliament TV** (Read, [openparliament.tv/imprint](https://openparliament.tv/imprint/)) names itself „c/o Center for the Cultivation of Technology gemeinnützige GmbH“, an organisation's address. Its responsible person is named under the old „§ 5 TMG, § 55 RStV“.
- **plenarwatch.de** (Read, [impressum](https://plenarwatch.de/impressum/)) names a GbR i. G. One partner is named „Redaktionell verantwortlich (§ 18 Abs. 2 MStV)“. The address is a street address shared with a sole proprietorship that receives the donations. This note does not judge whether it is a home address.
- **offenesparlament.de** points to the Open Knowledge Foundation Deutschland e. V. (Read, [impressum](https://offenesparlament.de/impressum/)). **Open Discourse** is run by a GmbH (agent report, [limebit.de/legal](https://www.limebit.de/legal)). Neither is a private person, so neither is a precedent for one.
- **Not found:** any court decision that accepts or rejects a commercial „Impressum-Service“ for a private person under § 18 Abs. 1 MStV. One search summary named a BGH case on virtual offices, but its Aktenzeichen did not check out, so it is not used here.

### Position

Publish an address where documents can actually be served on the operator. That means the home address, or a third-party address (office service, lawyer, family member) that holds a written Zustellungsbevollmächtigung. A Postfach or a plain mail-forwarding service without that authority is not enough.

**Evidence:** the wording „Anschrift“ in § 18 Abs. 1, the § 115 sanction for an address that is „nicht richtig“, and the NLM guide, which is the enforcing authority's own reading.

**Risk that remains:**
- **Low** with the home address.
- **Medium** with a c/o service. Only one Landesmedienanstalt's guidance was read. Which Landesmedienanstalt is competent depends on where the operator lives (§ 106 Abs. 1 MStV, per WD 10-035/22). No court has tested such a service for a private person. A fine of up to 50,000 euros is possible in principle.
- Abmahnungen by competitors under the UWG need a „geschäftliche Handlung“. That makes them unlikely against a non-commercial site, but this point was not verified against a source.

### Engineering way out

None. This is an organisational choice. The repository side is already done: the address comes from the local `--operator-file` and never enters git (ADR 0003, amendment of 2026-11-01). That keeps a later switch from home address to c/o, or back, free of history.

### When it applies

Before the public site. The data release on Zenodo or GitHub carries the operator's name and the licence, not an Impressum.

*Update 2026-11-22: the owner decided on the home address (ADR 0003, amendment 2026-11-21), so the c/o question is closed for now.*

---

## Question 2: can DIP clause 5 be passed on, and how does it sit next to CC BY and CC0 layers?

### Law and terms

- **DIP Nutzungsbedingungen**, signed 27 February 2023, page header dated 6 March 2023 (Read, [PDF](https://dip.bundestag.de/documents/nutzungsbedingungen_dip.pdf)):
  - **4b:** „Die über die API zur Verfügung gestellten maschinenlesbaren Daten dürfen umfassend in jeglicher Form genutzt und weiterverarbeitet werden. […] Eine Weitergabe oder sonstige Verbreitung dieser verarbeiteten Daten ist jedoch immer mit Quellenangabe zu versehen. Möglicherweise vorgenommene Veränderungen müssen als solche kenntlich gemacht werden.“
  - **5:** „Jegliche Nutzung von DIP-Daten, die in einem sinnentstellenden Zusammenhang erfolgt oder die zur Herabwürdigung von Mitgliedern des Deutschen Bundestages, des Bundesrates, der Bundesregierung oder sonstigen Personen führen könnte, ist untersagt.“
  - **6:** „Soweit Urheber- bzw. Nutzungsrechte des Deutschen Bundestages […] an den DIP-Daten bestehen, ist die Nutzung der DIP-Daten im Rahmen dieser Nutzungsbedingungen zulässig.“
- **§ 5 Abs. 2 UrhG** (Read, [gesetze-im-internet.de](https://www.gesetze-im-internet.de/urhg/__5.html)): other amtliche Werke „genießen keinen urheberrechtlichen Schutz“, subject only to §§ 62 and 63. The Bundestag's own terms say Plenarprotokolle are such works ([bundestag.de Impressum](https://www.bundestag.de/services/impressum), Read).
- **§§ 87a, 87b UrhG** give a database maker's right (Read, [§ 87a](https://www.gesetze-im-internet.de/urhg/__87a.html)). This is the only right the Bundestag could hold in DIP as a database. CPP-BT says „§ 5 UrhG ist auf amtliche Datenbanken analog anzuwenden“ and cites „BGH, Beschluss vom 28.09.2006 - I ZR 261/03“ (Read, [Zenodo API record 22844952](https://zenodo.org/api/records/22844952)).
  - That Beschluss is a referral, not a ruling (Read, [lexetius.com](https://lexetius.com/2006,3989)): „Dem Gerichtshof der Europäischen Gemeinschaften werden folgende Fragen zur Vorabentscheidung vorgelegt“. It asks whether the Database Directive rules out exactly that analogy.
  - How the referral ended was not verified. So whether § 87b applies to DIP is **open**.
  - It matters little here, because DIP 6 grants use „im Rahmen dieser Nutzungsbedingungen“ for any rights the Bundestag holds. If a database right exists, the terms are the licence, which is one more reason to follow them.
- **CC BY 4.0**, Section 2(a)(5)(B), "No downstream restrictions" (Read, [legal code](https://creativecommons.org/licenses/by/4.0/legalcode.en)): "You may not offer or impose any additional or different terms or conditions on […] the Licensed Material if doing so restricts exercise of the Licensed Rights by any recipient of the Licensed Material."
  - Section 1 defines "Licensed Material" as the material "to which the Licensor applied this Public License". The clause is lettered (B) in CC BY 4.0; the (C) in some secondary sources is from CC BY-SA.

### Precedent

- **CPP-BT, Open Discourse and BTVote** release under CC0 (Read: Zenodo record; Dataverse API for [FIKIBO](https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/FIKIBO) and [24U1FR](https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/24U1FR)). **ParlLawSpeech** releases under CC BY 4.0 (agent report, [parllawspeech.org](https://www.parllawspeech.org)).
  - None of the pages read passes on DIP clause 5 or any "no distorting use" condition.
  - Open Discourse grounds its openness in the E-Government-Gesetz (agent report, [opendiscourse.de/daten-und-methodik](https://opendiscourse.de/daten-und-methodik)).
- **plenarwatch.de** names the DIP source line and says „amtliche Werke gemäß § 5 UrhG gemeinfrei sind“, without passing on clause 5 (Read).
- **Not found:** any statement by the Bundestag on enforcing clause 5 against downstream users, and any decision on the clause.

### Position

**Follow clause 5 in good faith, although whether it can bind anyone is doubtful.**
- It is a condition set by a state organ on the use of copyright-free works.
- It bars uses that „zur Herabwürdigung … führen könnte“, which sits uneasily with the freedom to criticise office-holders (Art. 5 GG).
- It comes as a PDF attached to a public API key that needs no registration.
- No decision on the clause was found.

The practical lever is clause 3, not a lawsuit: „Ein Verstoß gegen die DIP-Nutzungsbedingungen … kann zu einer Sperrung dieses API-Schlüssels führen.“

**Do not make the clause bind downstream users, and do not try to.** Pass it on as a notice of the source, never as the project's own term.
- `LICENSE-DATA.md` says „It is a condition of the source, not an additional term we impose.“ That is right.
- Its preceding sentence, „The DIP terms, in particular no. 5, continue to apply to any reuse of the DIP layer“, reads like a term. Rewording it as „Die Nutzungsbedingungen des DIP gelten nach ihrem Wortlaut auch für Weiterverwendungen; wir geben diesen Hinweis weiter, ohne eigene Bedingungen hinzuzufügen“ removes that reading.

**Where the layers meet.** The CC BY layer is not free of DIP material.
- `documents.forderung`, `vote_passages` and `votes.inversion_excerpt` are tagged `derived`, but they quote Drucksache wording.
- DIP 4b also calls processed output „diese verarbeiteten Daten“.
- So CC BY 4.0's ban on downstream restrictions and clause 5 can meet on these columns. The fix is to say what CC BY covers there: the project's selection and extraction, while the quoted wording stays under the DIP layer.

**Test the project's own outputs against clause 5.** That is where the real exposure lies.
- Per-MP figures such as deviation from the Fraktion line (`vote_fractions.leading_vote`) or absence-style counts are exactly what someone might call disparaging.
- What keeps them outside „sinnentstellend“ and „Herabwürdigung“ is what the project already does: neutral wording, the figure next to its source, and no ranking framed as a judgment.

**Evidence:**
- CC BY 4.0 Sections 1 and 2(a)(5)(B) restrict only what the licensor imposes on the material it licenses.
- Nothing in DIP clauses 4 to 6 requires the user to impose clause 5 on its own recipients.
- Every comparable project redistributes the same material under CC0 or CC BY without restating clause 5.

**Risk that remains: low.**
- It rises to **medium** if the site labels or ranks MPs judgmentally („die faulsten Abgeordneten“).
- The worst realistic outcome is a blocked API key. The pipeline would then need the personalised key route or the bulk downloads.

### Engineering way out

Partly. The layered notice, the "Lizenzschicht" column and the `LICENSE_LAYER_SOURCES` check already keep the layers apart. Three small additions close the gaps:
1. **The three quoting columns.** *Update 2026-11-22: still open (`TODOS.md`).* Either move them to the DIP layer, or add a sentence in `LICENSE-DATA.md` that their quoted wording stays under the DIP terms. Cost: a data-dictionary entry or one sentence.
2. **The public repository.** `tests/fixtures/*.xml` (full Plenarprotokolle) and protocol-derived data in `scripts/` are published on GitHub without the DIP source line or a change notice. The root `LICENSE` says MIT „covers the code in this repository only“ and sends generated data and exports to `LICENSE-DATA.md`. Source files kept as test fixtures are neither, so nothing names their terms. Add a short notice: either a line in `LICENSE`, or a README in `tests/fixtures/`, giving „Quelle: Deutscher Bundestag/Bundesrat – DIP“ and saying the MIT licence does not cover them. Cost: a few lines. This applies now, not at the release. *Update 2026-11-22: done as a paragraph in the root `LICENSE` (PR #204).*
3. **The short string.** Optionally scope it: „eigene Auswertungen (Lizenzschicht derived): CC BY 4.0“. Cost: one string and its quote in `DATA.md`.

### When it applies

Now for the public repository (item 2). Before the first data release for the rest.

---

## Question 3: are speeches in a Plenarprotokoll amtliches Werk (§ 5) or the speaker's own work (§ 48), and where is the line for per-MP views?

### Law and terms

- **§ 5 Abs. 2 UrhG** (Read): „andere amtliche Werke, die im amtlichen Interesse zur allgemeinen Kenntnisnahme veröffentlicht worden sind“ are unprotected, with §§ 62 and 63 applying.
- **§ 48 UrhG** (Read, [gesetze-im-internet.de](https://www.gesetze-im-internet.de/urhg/__48.html)):
  - Abs. 1 Nr. 2 permits „die Vervielfältigung, Verbreitung und öffentliche Wiedergabe von Reden, die bei öffentlichen Verhandlungen vor staatlichen, kommunalen oder kirchlichen Organen gehalten worden sind“.
  - Abs. 2: „Unzulässig ist jedoch die Vervielfältigung und Verbreitung der in Absatz 1 Nr. 2 bezeichneten Reden in Form einer Sammlung, die überwiegend Reden desselben Urhebers enthält.“
- **§ 63 Abs. 1 and 2 UrhG** (Read): § 48 uses require a clear source line. For public communication under § 48, it requires the source „einschließlich des Namens des Urhebers“.
- **InfoSoc Directive 2001/29/EC, Art. 5(3)(f)** (agent report, [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32001L0029)) allows "use of political speeches as well as extracts of public lectures […] to the extent justified by the informatory purpose and provided that the source, including the author's name, is indicated".
  - § 48 is read in its light. Its limit, "to the extent justified by the informatory purpose", is the one an open-ended reuse licence would test.
  - The CJEU's 2019 decisions on how strictly such exceptions are read (C-469/17 Funke Medien, C-516/17 Spiegel Online) were not read here.
- **Bundestag** (Read, [Impressum](https://www.bundestag.de/services/impressum)): „Drucksachen und Plenarprotokolle genießen als amtliche Werke keinen urheberrechtlichen Schutz“. It also says: „Der Deutsche Bundestag übernimmt keine Gewähr dafür, dass keine Rechte Dritter bestehen.“ DIP 6 says the same thing in other words.

### Precedent

- **CPP-BT** ships every speech in full under CC0 and grounds this on „An den Plenarprotokollen besteht gem. § 5 Abs. 2 UrhG kein Urheberrecht, da sie amtliche Werke sind.“ (Read, Zenodo API record).
- Its speech table has speaker ids. A per-MP selection is a filter on that table, not a separate file (agent report).
- **Open Discourse** (CC0), **ParlLawSpeech** (CC BY 4.0, Bundestag speeches 2009–2021) and **GermaParl** (CC BY or CC BY-SA, see `docs/research/bundestag-corpora-landscape-2026-11.md`) also ship full speech texts.
- **plenarwatch.de** names MPs only to attribute a quote: „Namen erscheinen deshalb ausschließlich dort, wo sie ein Zitat zuordnen — nie im Fließtext.“ (agent report, [methodik](https://plenarwatch.de/methodik/)).
- **Not found:**
  - a Wissenschaftliche Dienste paper or a court decision on whether a speech printed in a Plenarprotokoll stays the speaker's work;
  - commentary on whether § 48 Abs. 2, which names only Vervielfältigung and Verbreitung, also limits making available online (§ 19a).
  - The standard commentaries (Dreier/Schulze, Schricker/Loewenheim) are behind a paywall and were not read.

### Position

The question does not need an answer for the corpus as built, because both readings lead to the same result:
- **If the speeches are part of the amtliches Werk,** they are free under § 5 Abs. 2 with §§ 62 and 63. That is the Bundestag's own reading of the Plenarprotokoll.
- **If they remain the speakers' works,** § 48 Abs. 1 Nr. 2 permits copying, distributing and making them public, because they were held „bei öffentlichen Verhandlungen“ before a „staatlichen Organ“. The full-corpus file is not a collection „die überwiegend Reden desselben Urhebers enthält“. Every row names its speaker and protocol, which meets § 63. A parliamentary record kept for the public is close to the core of the directive's "informatory purpose".

The convergence is strongest on the § 5 branch, which is the Bundestag's own reading. The § 48 branch carries the extra limit of the informatory purpose, which nothing read has tested against a bulk reuse licence.

The line falls at a collection of one person's speeches, and it is firm:
- **Data:** a per-MP export file of full texts, or a page that prints them in full, is such a collection on the § 48 reading. Putting it online needs a copy on the server, which is a „Vervielfältigung“ (§ 16), and § 48 Abs. 2 bans that in a collection. So whether Abs. 2 reaches § 19a does not need deciding: **do not build it.** The ADR already flags this (D2).
- **Site:** an MP page lists 240-character snippets with links. That these snippets are not „Reden“ in the sense of Abs. 2 is an assumption, not a finding; it is probably right, because a snippet is the opening of a speech and not the speech. It is what the site does today.

**Risk that remains: low** for the release and site as built. Several academic projects have redistributed the same material in full for years.

### Engineering way out

Yes, and it is already in place: per-MP views show snippets and links, and the export is one corpus. Keep it that way. A feature that assembles one person's speeches in full is ruled out on the § 48 reading. Only a lawyer's opinion confirming the § 5 reading, written for that feature, would reopen it.

Cost: nothing today. It rules out a per-MP full-text download.

### When it applies

Before the first data release, for the corpus. Before any per-MP full-text feature, for the line.

---

## Question 4: what is the legal basis for publishing MPs' personal data, and does Art. 85 DSGVO apply?

### Law and terms

- **DSGVO** (Read, [EUR-Lex](https://eur-lex.europa.eu/legal-content/DE/TXT/HTML/?uri=CELEX:32016R0679)):
  - **Art. 2 Abs. 2 lit. c:** the household exemption covers only „ausschließlich persönlicher oder familiärer Tätigkeiten“. A public site and dataset are outside it.
  - **Art. 6 Abs. 1 lit. f:** processing is lawful where it is „zur Wahrung der berechtigten Interessen des Verantwortlichen oder eines Dritten erforderlich, sofern nicht die Interessen oder Grundrechte und Grundfreiheiten der betroffenen Person […] überwiegen“.
  - **Art. 9 Abs. 1:** processing of data „aus denen […] politische Meinungen […] hervorgehen“ is prohibited, unless an exception applies. **Abs. 2 lit. e** is the exception for data „die die betroffene Person offensichtlich öffentlich gemacht hat“.
  - **Art. 10:** data on criminal convictions and offences may be processed under Art. 6 Abs. 1 „nur unter behördlicher Aufsicht“ or where Union or Member State law allows it with safeguards.
  - **Art. 17 Abs. 3 lit. a:** no erasure duty where processing is necessary „zur Ausübung des Rechts auf freie Meinungsäußerung und Information“.
  - **Art. 85 Abs. 1 and 2:** Member States reconcile data protection with free expression, „einschließlich der Verarbeitung zu journalistischen Zwecken und zu wissenschaftlichen, künstlerischen oder literarischen Zwecken“, and provide derogations.
- **German Art. 85 implementation for Telemedien: § 23 Abs. 1 MStV** (Read, [gesetze-bayern.de](https://www.gesetze-bayern.de/Content/Document/MStV-23)). It privileges processing „zu journalistischen Zwecken“ by broadcasters and „Unternehmen und Hilfsunternehmen der Presse als Anbieter von Telemedien“. For them, only a few DSGVO provisions apply, not Art. 6.
- **BGH, Urteil vom 29. Juli 2025, VI ZR 426/24** (Read, [PDF](https://curia.europa.eu/site/upload/docs/application/pdf/2026-02/vi_zr_426-24.pdf)):
  - Leitsatz d: „Der Begriff "Unternehmen der Presse" im Sinne von § 23 Abs. 1 Satz 4 MStV ist […] dahingehend auszulegen, dass er alle Anbieter von Telemedien zu journalistischen Zwecken erfasst.“
  - Leitsatz e: „zu journalistischen Zwecken“ is to be read „weit und in Anlehnung an die unionsrechtliche Terminologie in Art. 85 DSGVO“. The reasons cite the CJEU's definition: processing to disseminate „Informationen, Meinungen oder Ideen, mit welchem Übertragungsmittel auch immer, in der Öffentlichkeit“ (C-345/17 Buivids, C-73/07 Satamedia).
  - In the same passage: „Dies bedeutet aber nicht, dass auf das Erfordernis eines Mindestmaßes an eigener inhaltlicher Bearbeitung der bereitgestellten Informationen verzichtet werden kann“, and „Art. 85 Abs. 2 DSGVO enthält kein allgemeines Meinungsprivileg“.
- **BGH, 23.06.2009, VI ZR 196/08 („spickmich“)** (agent report from [lexetius.com](https://lexetius.com/2009,1764), not re-checked). The Medienprivileg did not cover a rating portal. An automated averaging of entries was held not to be „journalistisch-redaktionelle Bearbeitung“.
- **BDSG § 27** (Read, [gesetze-im-internet.de](https://www.gesetze-im-internet.de/bdsg_2018/__27.html)) covers Art. 9 data for research. Its Abs. 4 allows publication only with consent or where „unerlässlich“ for presenting research on „Ereignisse der Zeitgeschichte“. It is not the basis for a public site, and is noted only for completeness.

### Precedent

- **abgeordnetenwatch.de** publishes per-MP named votes and profiles. Its Datenschutzerklärung and Impressum returned HTTP 403 to every automated fetch on 2026-11-21, so its stated basis is **not read**. Search snippets suggest Art. 6 Abs. 1 lit. f, unverified. The CC0 statement on its API page was read on 2026-09-28 (ADR 0003).
- **BTVote** publishes every MP's vote in every roll call for WP 1–19 under CC0 (Read, Dataverse API). No data-protection statement was found in the record.
- **CPP-BT** publishes speeches with speaker ids under CC0. No data-protection statement was found in the record (Read).
- **plenarwatch.de, Open Parliament TV and Open Discourse** state legal bases only for server logs, newsletters and embeds (Read or agent report). None of them states a basis for publishing MP data.
- **Not found:**
  - any DSK or Landesdatenschutzbeauftragte statement on Art. 9 for MPs' recorded votes;
  - any authority applying Art. 9 Abs. 2 lit. e to them;
  - any German Land with a general journalistic exemption outside the press.

### Position

**For MPs, rely on Art. 6 Abs. 1 lit. f and Art. 9 Abs. 2 lit. e.**
- **Art. 6 Abs. 1 lit. f** covers all MP data. The legitimate interest is making the work of the Bundestag traceable. The data is the public conduct of office-holders, taken from the official public record.
  - That includes `gender`, `birth_year`, `profession`, `wahlkreis` and `bundesland` from abgeordnetenwatch. CC0 settles copyright, not data protection, so the project needs its own basis for them, and this is it.
- **Art. 9 Abs. 2 lit. e** covers the parts that reveal „politische Meinungen“: votes, Fraktion, and the speeches themselves. A speech in plenary is the clearest political opinion there is, and the clearest deliberate act of making it public.
  - The reviewer cites the CJEU (C-252/21 Meta, on a "clear" deliberate act; C-184/20 OT, on data that reveals sensitive information indirectly). Both were not read here; on the reviewer's account both fit an MP's recorded votes and speeches.
  - The weak spot is the project's own inferences, such as deviation from the Fraktion line. The MP made the votes public, not the comparison. An inference computed only from manifestly public data is arguably covered, but nothing read decides it.

**For third parties named in speeches, the full-text corpus has a real gap.**
- Speakers name private persons. Sometimes this is with health or religion (Art. 9 data), sometimes with crimes or convictions. Art. 10 requires that such processing „nur unter behördlicher Aufsicht vorgenommen werden [darf] oder wenn dies nach dem Unionsrecht oder dem Recht der Mitgliedstaaten … zulässig ist“.
- These persons made nothing public, so Art. 9 Abs. 2 lit. e does not help. And these bans apply before publication, so an objection afterwards does not cure them.
- The only fitting German rule is Art. 85 as implemented in § 23 MStV, read as the BGH now reads it: any Telemedien provider processing „zu journalistischen Zwecken“.
- The full-text corpus of the official record, published so the public can read what was said, fits the CJEU's definition (disseminating information to the public). It fits better than the computed statistics do. The BGH's „Mindestmaß an eigener inhaltlicher Bearbeitung“ is the open point: selecting, structuring and linking the record is some processing, but not much.
- So the position is: claim Art. 85 / § 23 MStV for the publication of the record, as a second basis next to Art. 6 Abs. 1 lit. f. Do not rely on it for the computed figures about MPs, which do not need it.
- Every comparable corpus (CPP-BT, Open Discourse, ParlLawSpeech, GermaParl) carries the same third-party data. None of them states a basis.

**Do before the first release:**
1. **State the bases in `datenschutz.html`.** *Update 2026-11-22: done in PR #204; the section now names the bases, the recipients, the archive and Art. 21.* The „Personen in den Daten“ section named the purpose but no legal basis. Art. 13 and 14 require more than one paragraph:
   - the bases (Art. 6 Abs. 1 lit. f, Art. 9 Abs. 2 lit. e, Art. 85 with § 23 MStV);
   - the legitimate interest pursued;
   - the source of the data;
   - how long the data is kept: indefinitely, as a versioned archive;
   - the recipients: the public, Zenodo, GitHub;
   - the right to object (Art. 21).
   - Art. 14 Abs. 5 lit. b lets the project skip writing to each person where that „einen unverhältnismäßigen Aufwand erfordern würde“. In that case it must publish the information instead (Read).
2. **Keep a record of processing (Art. 30).** The small-organisation exemption in Art. 30 Abs. 5 does not apply where processing is „nicht nur gelegentlich“ or includes Art. 9 or Art. 10 data (Read). Both are true here. A one-page record is enough.
3. **Run a short DPIA threshold check (Art. 35).** Note in that record why a full impact assessment is or is not needed. Art. 35 was not quoted here.
4. **Decide how erasure works against fixed releases.**
   - A Zenodo version with a DOI cannot be changed.
   - Art. 17 Abs. 3 lit. a lifts the erasure duty where processing is „zur Ausübung des Rechts auf freie Meinungsäußerung und Information“ necessary (Read). That is the argument for keeping the official record intact.
   - Have a stated process anyway: correct the data in the next main release, and document the case. For a stable release, ask Zenodo to restrict that version. Whether Zenodo does this on request was not checked.

**Zwischenruf authors**, named in the question, are not in the data today. The `<kommentar>` elements are not parsed (`TODOS.md`, Zwischenrufe item). When they are, they are MP data under the same bases.

**Evidence:**
- The wording of Art. 9 Abs. 2 lit. e and Art. 10.
- The balancing under Art. 6 Abs. 1 lit. f: public office, public sitting, official publication, a stated transparency purpose.
- BGH VI ZR 426/24 on the reach of § 23 MStV.
- BTVote and abgeordnetenwatch have published per-MP votes for years.

**Risk that remains:**
- **Low** for MP data.
- **Medium** for third-party data in the full-text corpus. The Art. 85 route is plausible after the BGH's 2025 judgment, but untested for a data corpus. Art. 10 has no other door for a private publisher.

### Engineering way out

Partly:
- **Datenschutz text and record:** about a day's writing. They do not remove risk, they show compliance.
- **Third-party data:** the exposure cannot be removed without changing the record.
  - Redacting names of non-MPs from speech text would breach § 62 and DIP 4b's marking duty unless marked. It would also break fidelity, the product's core. Not recommended.
  - What is cheap is a takedown path: withhold a single Rede on a justified request, with a reason, the way refused passages are already withheld (`PRODUCT.md`, decided 2026-11-07).
- **Dropping per-MP votes:** would remove the Art. 9 question for votes, but they are the product. Not recommended.

### When it applies

Before the first data release. The release itself publishes the personal data, so the bases, the record and the erasure process are needed before then. The `datenschutz.html` text is needed before the public site.

---

## Question 6: is the site „journalistisch-redaktionell gestaltet“?

### Law and terms

- **§ 18 Abs. 2 MStV:** a named Verantwortlicher for „Telemedien mit journalistisch-redaktionell gestalteten Angeboten, in denen insbesondere vollständig oder teilweise Inhalte periodischer Druckerzeugnisse in Text oder Bild wiedergegeben werden“ (Read).
- **§ 19 Abs. 1 MStV** (Read, [gesetze-bayern.de](https://www.gesetze-bayern.de/Content/Document/MStV-19)):
  - The diligence duties reach „andere geschäftsmäßig angebotene, journalistisch-redaktionell gestaltete Telemedien, in denen regelmäßig Nachrichten oder politische Informationen enthalten sind“.
  - „Nachrichten sind vom Anbieter vor ihrer Verbreitung mit der nach den Umständen gebotenen Sorgfalt auf Inhalt, Herkunft und Wahrheit zu prüfen.“
- **§ 20 MStV** (Gegendarstellung) also attaches to journalistic-editorial offers. It was not quoted here.
- **Sanction:** a breach of § 18 Abs. 2 is not an Ordnungswidrigkeit, and the Landesmedienanstalten have no supervisory power over it (WD 10-035/22, Read: „eine sanktionslose Obliegenheit“).

### Guidance and precedent

- **WD 10 - 3000 - 035/22** (Read) lists the case-law markers of a journalistic-editorial offer:
  - „eine gewisse Selektivität und Strukturierung“;
  - a selection by presumed social relevance „mit dem Ziel des Anbieters, zur öffentlichen Kommunikation beizutragen“;
  - „Faktizität“;
  - „ein hohes Maß an Aktualität“;
  - „ein hoher Grad an Professionalisierung der Arbeitsweise“;
  - „ein gewisser Grad an organisierter Verfestigung“.
  - It cites OVG Berlin-Brandenburg (13.08.2014) and OLG Bremen (14.01.2011, 2 U 115/10).
- **NLM guide** (Read): indicators can be „eine strukturierte bzw. aktuelle Themenauswahl, eine Aufbereitung von Themen für Nutzer*innen und ein professioneller Auftritt“. Weblogs are listed as journalistic-editorial.
- **BGH VI ZR 196/08 (spickmich)** and **BGH VI ZR 426/24** (see question 4): automated compilation or computation is not editorial processing, and Art. 85 needs „ein Mindestmaß an eigener inhaltlicher Bearbeitung“.
- **Precedent:**
  - plenarwatch.de writes AI-assisted texts that are „redaktionell verantwortet“, and names a § 18 Abs. 2 person (Read). That is a site with editorial texts, unlike v1 here.
  - Open Parliament TV and offenesparlament.de name responsible persons under the old § 55 RStV (Read).

### Position

**Uncertain, so act as if the site is journalistic-editorial.**

There is a case that it is not:
- The site shows the official record in views chosen by fixed rules.
- It has no editorial texts or commentary.
- The WD criteria and the NLM indicators point to selection by newsworthiness, which a rule-built site lacks.
- spickmich (2009) held automated computation is not editorial processing.

The case that it is has grown:
- In VI ZR 426/24 the BGH reads „journalistische Zwecke“ widely. It found them in a party's Telegram post that listed named persons.
- Satamedia, which the BGH follows, accepted the publication of public tax records as journalism.
- A curated „Aktuell“ page, a chosen set of headline figures and the linking of debate to votes are a selection made to contribute to public debate.
- spickmich predates both the DSGVO and that broad reading.

**Acting as if it is costs little:**
- Keep naming the § 18 Abs. 2 Verantwortlicher, as ADR D4 decided. It is the same person at the same address.
- Meet the § 19 diligence duty. Checking „Inhalt, Herkunft und Wahrheit“ is the project's source-tracing method already.
- Be ready to print a Gegendarstellung (§ 20) on a justified request. On the v1 site, the only facts about persons are those from the record.
- It also supports the Art. 85 basis that question 4 needs for third-party data in the corpus. The two answers should be given consistently.

**Evidence:** the WD criteria, the NLM indicators, BGH VI ZR 426/24 and spickmich. The design facts are in `PRODUCT.md`.

**Risk that remains: low.**
- The § 19 duty is not exempt from supervision: § 109 Abs. 1 MStV exempts only „§ 17, § 18 Abs. 2 und 4, § 20 und § 23 Abs. 2“ (quoted in WD 10-035/22, Read). A Landesmedienanstalt may therefore issue a „Beanstandung“ if diligence fails.
- § 19 Abs. 1 Satz 2 applies to „geschäftsmäßig angebotene“ offers. The reviewer says this is usually read as "on a lasting basis" rather than "for money"; that was not verified here. On that reading the site is covered.
- The risk stays low because the duty is one the project meets by design.

### Engineering way out

Not needed. Two features would make the site clearly journalistic-editorial and should get a diligence check before they ship:
- the AI summaries, which are written texts about the debate;
- a rebuilt Fakt der Woche, which selects by newsworthiness.

Cost: none today.

### When it applies

Before the public site, and again before AI summaries or Fakt der Woche return.

---

## Question 7: do joined paragraphs and normalised whitespace count as a change under § 62 UrhG?

### Law and terms

- **§ 62 Abs. 1 UrhG** (Read, [gesetze-im-internet.de](https://www.gesetze-im-internet.de/urhg/__62.html)): „Soweit nach den Bestimmungen dieses Abschnitts die Benutzung eines Werkes zulässig ist, dürfen Änderungen an dem Werk nicht vorgenommen werden. § 39 gilt entsprechend.“ § 5 Abs. 2 applies § 62 Abs. 1 to 3 to amtliche Werke „entsprechend“.
- **§ 39 Abs. 2 UrhG** (agent report, [gesetze-im-internet.de](https://www.gesetze-im-internet.de/urhg/__39.html)): changes „zu denen der Urheber seine Einwilligung nach Treu und Glauben nicht versagen kann, sind zulässig“.
- **§ 63 Abs. 1 Satz 2 UrhG** (Read) requires marking „ob an dem Werk Kürzungen oder andere Änderungen vorgenommen worden sind“ when whole Sprachwerke are reproduced.
- **DIP 4a** (Read) concerns the PDF documents: „PDF-Dokumente von Drucksachen und Plenarprotokollen […] dürfen grundsätzlich nicht verändert werden“. Excerpts and „Markierungen, Annotationen o. ä.“ are allowed if marked.
- **DIP 4b** (Read) concerns machine-readable data: data from the API, „Gleiches gilt für Daten, die aus einzelnen PDF-Dokumenten extrahiert werden“, may be processed „umfassend in jeglicher Form“, provided „Möglicherweise vorgenommene Veränderungen müssen als solche kenntlich gemacht werden.“

### Precedent

- **Not found:** any commentary or decision on whether removing line or paragraph breaks or normalising spaces is an „Änderung an dem Werk“. Haufe's article on the Änderungsverbot (agent report) gives no definition.
- The text corpora all re-segment the protocol: CPP-BT into speeches, GermaParl into turns and sentences, ParlLawSpeech into speeches. None of the records read discusses § 62.

### Position

**The paragraph joins are not the problem.** Joining paragraphs with spaces and normalising whitespace leaves wording, punctuation and order untouched. That is very likely no „Änderung an dem Werk“ in the sense of § 62, a rule that protects a work's content and integrity. Even on a strict reading, the export is not a reproduction of the PDF (DIP 4a). It is machine-readable data extracted from the protocol XML, which DIP 4b lets the user process „umfassend in jeglicher Form“, provided changes are marked. `LICENSE-DATA.md` marks this change: „paragraph breaks are not kept“.

**The unmarked omissions are the problem** (found by the second read):
- `speeches.text` leaves out what the protocol prints inside a Rede but which is not the speaker's: applause, Zwischenrufe and the chair's remarks („Chair text and comments never become speaker text“, `speech_segments`). The codebook says text the rules attached to a Rede is included.
- That is a „Kürzung“. § 63 Abs. 1 Satz 2 requires it to be marked when whole Sprachwerke are reproduced, and DIP 4b requires every change to be marked.
- `LICENSE-DATA.md` does not mark it. Leaving out the interjection a speaker answers can also make a passage read differently. That is the „sinnentstellend“ test of DIP clause 5, not just § 62.
- The fix is a sentence in „What we changed“ and the codebook (*done 2026-11-22, PR #204*), for example: „`speeches.text` enthält nur die Worte des Redners; Beifall, Zwischenrufe und Bemerkungen der Sitzungsleitung, die das Protokoll innerhalb der Rede druckt, sind nicht enthalten.“
- Better still, link each Rede to its place in the protocol, which the rows already do through the protocol id and page.

**Keep the paragraph breaks anyway.** Paragraph structure is part of the record researchers want, and it removes the smaller question entirely.

**Evidence:** the DIP 4a/4b distinction between PDF and processed data, § 63 Abs. 1 Satz 2, the code comment in `speech_segments`, and the change notice in `LICENSE-DATA.md`.

**Risk that remains:**
- **Medium until the omission is marked.** It is an unmarked Kürzung in a published change notice.
- **Low after.**
- Separately, 4b names API data and „Daten, die aus einzelnen PDF-Dokumenten extrahiert werden“, while the speech texts come from the protocol XML on the DIP document server. Reading the XML as API-like machine-readable data is natural, but the text does not say so.

### Engineering way out

Yes, two pieces:
1. **Mark the omission:** two sentences in `LICENSE-DATA.md` and the `speeches.text` entry in `scripts/data_dictionary.json`. No figure moves. An hour. *Update 2026-11-22: done (PR #204).*
2. **Keep the paragraph breaks** in `speeches.text` and `contributions.text`, for example by joining paragraphs with `\n\n` as `proceedings.abstract` already does. The paragraphs are already parsed (`speech_text_and_paragraphs`), and `paragraphs_json` holds them until it is dropped at export.

The cost of piece 2, in plain words:
- `persist_dip_pulse_store.clean` collapses all whitespace and is called 85 times on many fields (86 on main on 2026-11-22). It cannot simply change: speech text needs its own cleaner that keeps `\n\n`. `contribution_unit` joins with a space too.
- A re-run of the store and the replay.
- Updating „What we changed“ and the codebook.
- Reporting the figures that move: `char_count` is `len(text)`, so every Rede with more than one paragraph gains one character per extra break. Word counts and anything computed on words should not move. Check that on the replay.

About a day with the replay. Do it before the first data release, so no published release ever has the joined text.

### When it applies

Before the first data release. The omission notice also applies to any export that already circulates.

---

## Question 8: do the click-triggered localStorage entries need consent or a stated basis under § 25 TDDDG?

### Law and terms

- **§ 25 TDDDG** (Read, [gesetze-im-internet.de/ttdsg/__25.html](https://www.gesetze-im-internet.de/ttdsg/__25.html); the URL keeps the old abbreviation):
  - Abs. 1: storing information in the user's terminal equipment is allowed only with consent.
  - Abs. 2 Nr. 2: no consent is needed where storage „unbedingt erforderlich ist, damit der Anbieter eines digitalen Dienstes einen vom Nutzer ausdrücklich gewünschten digitalen Dienst zur Verfügung stellen kann“.
- **DSK, „Orientierungshilfe der Aufsichtsbehörden für Anbieter:innen von Digitalen Diensten“**, Version 1.2, November 2024 (Read, [PDF](https://datenschutzkonferenz-online.de/media/oh/OH_Digitale_Dienste.pdf)):
  - Rn. 21: storage under § 25 includes „Web-Storage-Objekte (Local- und Session-Storage-Objekte)“. So localStorage is in scope.
  - Rn. 79: the necessity test has a time, content and recipient dimension, each to be reduced „auf das erforderliche Minimum“.
  - Rn. 80: storage for an extra function is necessary only once „eine entsprechende Nutzerinteraktion stattgefunden hat“. „Auch wird bei individualisierten Cookies die Gültigkeit häufig nur für eine Session erforderlich sein.“
  - Rn. 81: „Gleiches gilt für das Speichern von Einstellungen zur Sprache oder Hintergrund-Farbe. Hierfür ist kein ein eindeutiges Identifizierungsmerkmal wie eine eindeutige User-ID erforderlich, sondern es reicht die Speicherung einer jeweils nicht identifizierenden Angabe wie z. B. „background-color: black“ oder „language: de“.“
- **Article 29 Working Party, Opinion 04/2012 (WP194)**, section 3.6 "UI customization cookies" (agent report, [PDF via datenschutz.hessen.de](https://Datenschutz.Hessen.de/sites/datenschutz.hessen.de/files/2022-11/wp_194.pdf)):
  - Such storage is exempt when "the user has explicitly requested the service to remember a certain piece of information, for example, by clicking on a button".
  - For persistence beyond the session, it suggests a visible note next to the control.
- **EDPB Guidelines 2/2023 v2.0** (agent report, [PDF](https://edpb.europa.eu/system/files/2024-10/edpb_guidelines_202302_technical_scope_art_53_eprivacydirective_v2_en_0.pdf)):
  - Para. 37: storage counts regardless of duration.
  - Para. 44: local processing that never leaves the device is not "gaining access".

### Precedent

- **plenarwatch.de:** „Wir setzen keine Cookies“. It says nothing on localStorage (Read).
- **Open Parliament TV** states consent by use and cites the TMG (Read). That is outdated, and not a model.
- **Not found:** any comparable project that states a § 25 basis for a theme setting.

### Position

**Storing the theme choice needs no consent if it lasts one session.** The value is written only after the visitor clicks the toggle (DSK Rn. 80's interaction test). It is a non-identifying value of exactly the kind Rn. 81 names („Hintergrund-Farbe“), and it is never transmitted. That is § 25 Abs. 2 Nr. 2.

**The duration is the open point** (corrected after the second read). Rn. 81 is about content, not duration. Rn. 80 settles duration, and it continues past the sentence quoted above:
- „Gemäß § 19 Abs. 1 TDDDG ist grundsätzlich davon auszugehen, dass unter der Nutzung eines digitalen Dienstes ein einzelner Nutzungsvorgang zu verstehen ist, also eine Session.“
- „Eine regelmäßige Nutzung des digitalen Dienstes durch bestimmte Endnutzer:innen kann grundsätzlich nur dann unterstellt werden, wenn es sich um einen anmeldepflichtigen Dienst handelt.“

The site has no login. On the DSK's reading, keeping the choice in `localStorage` beyond the session is not „unbedingt erforderlich“.

**Recommendation: store the theme in `sessionStorage`, and name the basis in `datenschutz.html`:**

> Rechtsgrundlage ist § 25 Abs. 2 Nr. 2 TDDDG; die Speicherung ist unbedingt erforderlich, um die von Ihnen gewählte Einstellung bereitzustellen. Sie gilt nur bis zum Schließen des Browsers.

- The theme already follows `prefers-color-scheme` without a click, so few visitors need the toggle at all.
- The alternative, keeping `localStorage` with a „Auswahl in diesem Browser merken“ note at the toggle, follows WP194 but not the DSK, and the DSK is the German supervisor.

**Fix the page text.** *Update 2026-11-22: reworded in PR #204; the AI-summary key is still listed while pages carry its toggle.* `datenschutz.html` listed the AI-summary key and said „Zwei Einstellungen speichert die Website“. The v1 site writes only the theme key, so the sentence was untrue for v1. List a key only while some page can write it.

The DSGVO probably does not apply to the value at all: it stays on the visitor's device, is never sent, and identifies no one. So no Art. 6 basis is needed.

**Evidence:** DSK Rn. 21, 80 and 81; WP194 section 3.6; the code, which writes only on click and never reads the value server-side.

**Risk that remains:**
- **Low** with `sessionStorage` and the basis sentence.
- **Medium** as built: persistent storage without login, against the DSK's reading, on a page whose storage text is also inaccurate. In practice a supervisor acting on a theme toggle is unlikely, but the rating follows the guidance.

### Engineering way out

Yes:
1. **Switch** the two `localStorage` calls for the theme in `render_dip_pulse_html.py` to `sessionStorage`. *Update 2026-11-22: done for the theme and the AI-summary collapse state (PR #204).* Cost: a few lines and a test. Visitors who pick the non-default theme pick it again in each new browser session.
2. **Add the basis sentence, and list only the keys the build can write** (`DATENSCHUTZ_STORAGE_KEYS`). Cost: a sentence and a condition.
3. **Removing storage entirely** (the toggle changes only the current page) is not needed.

When AI summaries return, their collapse key gets the same treatment. *Update 2026-11-22: it already has the `sessionStorage` treatment.*

### When it applies

Before the public site.

---

## Where research is not enough

1. **Question 1, if the owner wants a c/o address.** *Update 2026-11-22: the owner chose the home address, so this item is closed unless that changes.* The rule is clear only for the home address. Whether a given Impressum service is acceptable turns on its contract (a real Zustellungsbevollmächtigung) and on the practice of the one competent Landesmedienanstalt.
   - **Free route:** ask that Landesmedienanstalt in writing whether the specific arrangement meets § 18 Abs. 1. It is the authority that would fine, and it is competent by the operator's place of residence (§ 106 Abs. 1 MStV, per WD 10-035/22). The NLM's guide shows these authorities publish advice to providers.
   - With the home address, research is enough.
2. **Question 4: third-party data in the full-text corpus, and erasure against fixed releases.** *Update 2026-11-22: the owner decided the route (the Cyber Law Clinic first, then the Landesdatenschutzbeauftragte); the inquiry is not yet sent (`TODOS.md`).*
   - Whether Art. 85 / § 23 MStV, read as in BGH VI ZR 426/24, carries a private publisher's corpus of the official record, including Art. 9 and Art. 10 data about persons the speakers name, is untested. Every comparable corpus has the same exposure and none states a basis.
   - How Art. 17 and 21 requests meet immutable DOI releases also needs an answer that holds up.
   - **Route:** a short written opinion from a data-protection lawyer, or the free clinic below, before the first data release. Bring the bases, the record of processing and the takedown process this note proposes, and ask whether they hold.
   - The free alternative to a lawyer is to ask the competent Landesdatenschutzbeauftragte. That is the authority for a private controller in the operator's Land. Whether it answers individual questions was not checked.

Research is enough for the rest:
- **Questions 2, 3, 6, 7 and 8** and the MP part of question 4 are answered well enough by the primary sources for a non-commercial project at this scale.
- **Question 3's line** (no per-MP full-text collection) follows from the wording of § 48 Abs. 2 and § 16. It needs a lawyer only if the owner wants to build such a feature.
- **Clause 5's enforceability (question 2)** and the database right are open, but following the terms makes the answer irrelevant in practice.
- **Question 8's duration point** disappears with `sessionStorage`.

**Outside these questions:** the Datenschutz page presupposes a hosting contract. Under Art. 28 DSGVO, an order-processing agreement with the host is needed before launch. If the host or a CDN is outside the EU, the transfer rules apply too. This belongs to the open host decision (`PRODUCT.md`).

**Free alternatives, verified on their own pages:**
- **Cyber Law Clinic, Universität Hamburg** ([beratung](https://www.jura.uni-hamburg.de/studium/lehrprojekte/law-clinics/cyber-law-clinic/beratung.html), Read).
  - It offers „eine kostenlose aber dennoch rechtlich fundierte Beratung“ and advises „Privatperson zu Fragstellungen rund um das Internet, sei es Social-Media, Blogs […]“.
  - It is „nicht vertretungsbefugt“ and states „Wir können keine Haftung für unseren Rechtsrat übernehmen.“
  - Its process lists „Bedürftigkeit“ as a step, without criteria. Whether an open-data project qualifies has to be asked.
- **Checked and not suitable:**
  - Prototype Fund: „Der Prototype Fund bietet keine individuelle Rechtsberatung an.“ ([kb.prototypefund.de](https://kb.prototypefund.de/books/rechtliche-grundlagen), agent report).
  - GFF does strategic litigation only ([freiheitsrechte.org](https://freiheitsrechte.org/ueber-die-gff/), agent report).
  - No advice offer was found for the Open Knowledge Foundation Deutschland, iRights, Wikimedia Deutschland, Digitale Gesellschaft or D64. That does not mean none exists.
- **Not verified, so not recommended:** other university law clinics that appeared only in search snippets (LMU, Düsseldorf, Saarland, HU Berlin, TH Köln).

---

## Second read

**How it was done.** On 2026-11-21 a fresh subagent with no part in the research got:
- the first draft of this note;
- ADR 0003, `LICENSE-DATA.md` and `PRODUCT.md`;
- the downloaded source texts: DIP terms, NLM guide, BGH VI ZR 426/24, WD 10-035/22, DSK guidance, the DSGVO, and the MStV, UrhG, DDG and TDDDG sections;
- the precedent pages.

It was asked to attack each position, check every quote, and look for contrary law, wrong risk ratings, misstated engineering costs and wrong timing. It could also search the web. It was not given the author's reasoning beyond what the draft says. Codex was not used.

It found every quote it checked matched its source. It raised 21 challenges. Each is listed below with how it was settled. "Accepted" means the note above now reflects it; the reviewer's own claims were checked where the outcome depended on them.

| # | Q | Challenge (short) | Settled |
|---|---|---|---|
| 1 | 1 | The NLM guide's next sentence says a free service can still be a DDG digital service; the draft left it out. | Accepted, wording. The sentence is now quoted. Nothing changes, because the built Impressum already cites § 5 DDG and gives an e-mail. |
| 2 | 2 | "Clause 5 binds the project" skips whether it binds anyone. It is a state organ restricting criticism of office-holders in copyright-free works, through browse-wrap terms on a public key. | Accepted. The position is now: follow in good faith, enforceability doubtful, and the practical lever is the key block in clause 3. |
| 3 | 2 | The real exposure is the project's own per-MP metrics, not downstream use. | Accepted. The note now tests the project's own outputs. Risk stays low, and becomes medium if the site labels or ranks MPs judgmentally. |
| 4 | 2 | CC BY and clause 5 do meet: three `derived` columns quote Drucksache wording, and `LICENSE-DATA.md` reads as imposing clause 5. | Accepted. Checked against `LICENSE-DATA.md`'s derived row. Fixes proposed: a layer note for the three columns, and rewording one sentence. |
| 5 | 2 | BGH I ZR 261/03 is a referral to the CJEU, not a ruling, so the database right is open. | Accepted. Checked on lexetius.com: „… werden folgende Fragen zur Vorabentscheidung vorgelegt“. How the referral ended was not verified. Risk unchanged, because DIP 6 licenses use under the terms either way. |
| 6 | 2, 3 | The repository is already public and holds full Plenarprotokoll XML fixtures and MP data with no DIP notice, so the timing has already passed. | Accepted. Verified: `tests/fixtures/` holds 14 protocol XML files, and `LICENSE` covers code only. Now a fix-now action. Not done here, because this task may not touch `tests/`. |
| 7 | 3 | Online making-available needs a server copy (§ 16), which § 48 Abs. 2 bans in a collection, so the per-MP answer is "don't", not "ask a lawyer". | Accepted. Question 3 left the "research not enough" list; the line is firm. |
| 8 | 3 | Art. 5(3)(f) limits use "to the extent justified by the informatory purpose", which the draft ignored; the claim that both readings converge is too strong. | Partly accepted. The limit is now stated. Risk stays low: the § 5 branch, the Bundestag's own reading, is unaffected, and a public parliamentary record sits near the core of that purpose. The CJEU cases were not read. |
| 9 | 3 | That 240-character snippets are not „Reden“ under § 48 Abs. 2 is an assumption. | Accepted, wording. Now stated as untested but probable. |
| 10 | 4 | Art. 10 (crime data) and third parties' Art. 9 data in speeches are missing; Art. 9 Abs. 2 lit. e does not cover third parties; these bans apply before publication. | Accepted, and the most material change. Q4 is now medium for third-party data, and Art. 85 / § 23 MStV, per the BGH's 2025 reading, is claimed for the corpus. Added to "Where research is not enough". |
| 11 | 4 | Art. 9 should cover speeches too, and the project's derived inferences were never made public by the MP. | Accepted. The CJEU cases cited (C-252/21, C-184/20) were not read and are attributed to the reviewer. |
| 12 | 4 | "One paragraph" understates Art. 13/14; Art. 30 Abs. 5 does not exempt; DPIA threshold; erasure against immutable releases. | Accepted. Art. 14 Abs. 5 lit. b, Art. 30 Abs. 5 and Art. 17 Abs. 3 lit. a checked against the DSGVO text; the to-do list and cost were revised. |
| 13 | 4 | Zwischenruf authors (named in the question), `profession` and `wahlkreis` were not covered. | Accepted. Zwischenrufe are not parsed today; the abgeordnetenwatch fields are named under Art. 6 Abs. 1 lit. f. |
| 14 | 6 | BGH VI ZR 426/24 cuts the other way: it found journalistic purposes in a party's Telegram list; Satamedia covers raw public records; spickmich is pre-DSGVO. | Accepted. Q6 is now "uncertain, act as if it is", consistent with Q4's Art. 85 claim. |
| 15 | 6 | § 19 is not exempt from supervision under § 109, and „geschäftsmäßig“ means lasting, not paid. | Partly accepted. The § 109 exemption list was checked in WD 10-035/22 and § 19 is not on it. The „geschäftsmäßig“ reading was not verified and is attributed to the reviewer. Risk stays low, because the project meets § 19 by design. |
| 16 | 7 | `speeches.text` leaves out Zwischenrufe and chair text without saying so: an unmarked „Kürzung“, and a clause 5 „sinnentstellend“ risk. | Accepted, and the main correction to Q7. Verified in `speech_segments`. Now medium until the notice is fixed; listed as a fix-now action. |
| 17 | 7 | `clean` is called 85 times; changing it changes every field; `contribution_unit` also joins with spaces. | Accepted. Verified the 85 calls. The cost is now about a day, with a separate speech-text cleaner. |
| 18 | 8 | Rn. 81 is about content, not duration; Rn. 80 reads necessity as one session for a service without login. | Accepted. The full Rn. 80 was checked in `dsk.txt`. The recommendation is now `sessionStorage`; as built, the risk is medium. |
| 19 | 8 | `datenschutz.html` says two keys are stored, but v1 writes only one. | Accepted. Verified in `DATENSCHUTZ_STORAGE_KEYS`. Listed as a fix-now action. |
| 20 | all | The table should follow the revisions. | Accepted. The table was rewritten. |
| 21 | all | The "not enough" list is incomplete: Art. 10 and erasure, clause 5 enforceability, database right, hosting contract, Q8 duration. | Partly accepted. Art. 10 and erasure were added as a lawyer item. Clause 5, the database right and Q8 are settled by following the terms and by `sessionStorage`, so research suffices. The hosting contract was added as outside these questions. |

**What the second read did not cover:**
- It did not reach abgeordnetenwatch's own Datenschutz and Impressum pages (HTTP 403 throughout), or the paywalled UrhG commentaries.
- Its CJEU citations (C-252/21, C-184/20, C-469/17, C-516/17) were not read by either side.
- These remain open as stated in each question.
