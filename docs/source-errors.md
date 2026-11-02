# Errors in the source files

A list of places where an official source file says something wrong or files content in the wrong place. The point is to send these to the publishers for correction.

**In scope:** errors in what the Bundestag publishes:
- the Plenarprotokoll XML at `dserver.bundestag.de`;
- the DIP API;
- the roll-call pages at `www.bundestag.de`.

**Not in scope:** gaps in our own parser. A sitting our validator refuses is listed here only once a human has read the source and found the source itself wrong. Parser work lives in TODOS.md.

**Who to send it to:** not yet decided.
- The Plenarprotokoll XML and DIP are published by the Deutscher Bundestag.
- Find the right contact from the publishers' own pages before sending anything. Don't guess an address.
- Send nothing without an owner go: a report is outward-facing.

**Status values:**
- `candidate`: seen in our logs or audits, but the source passage has not been read for this list;
- `verified`: the source passage was read and quoted here;
- `reported`: sent, with date and channel;
- `corrected`: the source changed, with the date it was seen.

## Verified

### E1. 20/11: the chair's handover to the next speaker is filed inside the previous speech

- **Status:** verified 2026-10-28.
- **Source:** `https://dserver.bundestag.de/btp/20/20011.xml`, Tagesordnungspunkt 2, `<rede id="ID201100900">` (Dr. Matthias Miersch, SPD).
- **What is wrong:** after Miersch's closing "Vielen Dank." and the applause, the same `<rede>` goes on with the chair's handover to the next speaker:
  - Präsidentin Bärbel Bas: "Nächster Redner: für die AfD-Fraktion Karsten Hilse." and a remark to Hilse ("Sie haben gerade ein paar kreative Umbaumaßnahmen vorgenommen …");
  - Karsten Hilse (AfD), with his own `<p klasse="redner">`: "Das freut mich sehr.";
  - Präsidentin Bas: "Jetzt erteile ich Ihnen das Wort für Ihre Rede. – Herzlichen Dank."
  - Hilse's speech follows as its own `<rede id="ID201101000">`.
- **What it should be:** the exchange belongs before Hilse's `<rede>`, or at its start. It is not part of Miersch's speech.
- **Effect on poliwatch:** the validator refuses the sitting, because Hilse's line would otherwise count as an interjected question in Miersch's speech. 20/11 is excluded since 2026-10-28 (`docs/plans/a3-phase3.md`, 4.4).

### E2. 19/2: a minister's speech with an empty person id

- **Status:** verified 2026-10-29.
- **Source:** `https://dserver.bundestag.de/btp/19/19002.xml`, `<rede id="ID19205800">`: `<redner id=""><name><vorname>Peter</vorname><nachname>Altmaier</nachname><rolle><rolle_lang>Bundesminister der Finanzen</rolle_lang>…`.
- **What is wrong:** the `id` attribute is empty, here and in the table-of-contents entry for the same speech. Altmaier was an MdB with an id of his own. Across the 716 WP 18–21 files this is the only speech with an empty id. 19/6 has 18 empty ids for Dr. Ole Schröder (Parl. Staatssekretär), but only in its table of contents.
- **Effect on poliwatch:** the speech is stored with Sprechrolle `bundesregierung` but no person, so its 6,180 characters count as unattributed. It is the only unattributed speech in WP 18–21 (a3-phase4.md, step 3).

### E3. 18/104: a speech with no `<redner>` element

- **Status:** verified 2026-10-29.
- **Source:** `https://dserver.bundestag.de/btp/18/18104.xml`, `<rede id="ID1810402200">`. It opens with a bare `<name>Christian Kühn ( Tübingen) (BÜNDNIS 90/DIE GRÜNEN) : </name>` instead of `<p klasse="redner"><redner id="…">…</redner></p>`.
- **What is wrong:** the speaker's person id and Fraktion are not marked up. Their only trace is a free-text name, which also carries a stray space ("( Tübingen)").
- **Scale:** across the 716 WP 18–21 files, three `<rede>` elements have no `<redner>`. The other two (18/46 `ID1804617400`, 18/76 `ID1807611000`) are Anlage texts that begin with `<p klasse="N_Anlage">`.
- **Effect on poliwatch:** the speech has no Fraktion, so Redeanteil for WP 18 lists one Rede under "(ohne Zuordnung)". It is the only such Rede in WP 18–21 (a3-phase4.md, step 3).

### E4. WP 19/20 roll-calls file MdBs under the wrong group (Fraktion changes dated wrong)

- **Status:** verified 2026-11-01.
- **Sources:**
  - `https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=750` (2021-06-24, "Verwendung geschlechtergerechter Sprache"): AfD 86 Mitglieder, fraktionslos 10.
  - The earlier votes of the same day (`id=747`, `id=748`) list AfD 88 and fraktionslos 8.
  - `id=753` (2021-08-25, "Bundeswehreinsatz zur Evakuierung aus Afghanistan"): AfD 84, fraktionslos 12.
  - The store's member rows (`vote_members`) name the moved members:
    - Uwe Witt and Johannes Huber are listed as fraktionslos from `id=750` on.
    - Bruno Hollnagel and Heiko Heßenkemper are listed as fraktionslos on `id=753`.
- **What is wrong:** the Bundestag's own Textarchiv (`https://www.bundestag.de/dokumente/textarchiv/2024/kw32-fraktionslose-1014020`) dates these exits as follows:
  - Witt and Huber: "am 31. Dezember 2021", which is in WP 20.
  - Hollnagel: 25 June 2021.
  - Heßenkemper: 30 June 2021, and "trat allerdings am 24. August 2021 der AfD-Fraktion erneut bei".

  On 2021-06-24 the AfD-Fraktion therefore still had 88 members. On 2021-08-25 it had 87 (Hollnagel out, Heßenkemper back), with 9 fraktionslos. The roll-call pages show three members too few for the AfD from `id=750` to the end of WP 19.
- **What it should be:** each member listed under the Fraktion they belonged to on the vote's date.
- **Effect on poliwatch:**
  - **Vote data:** `vote_fractions` and `vote_members` copy the pages. These four MdBs' votes in the affected WP 19 roll-calls count for fraktionslos, not the AfD, which affects the vote panel's group blocks and Abweichler.
  - **Seat counts:** the planned seat counts derived from roll-calls (`docs/plans/c1-seat-counts.md`) inherit the error.
  - **Scale:** not measured beyond these votes. An independent membership source (the MdB-Stammdaten) is needed to find other cases.
- **Scale, measured 2026-11-01:** the MdB-Stammdaten (`MDB_STAMMDATEN.XML`, VERSION 1777449783, 29.04.2026) were compared with all 556 stored roll-calls. 47 roll-calls in WP 19 and WP 20 file six MdBs under the wrong group. In each case the Textarchiv dates agree with the Stammdaten and not with the roll-call page:
  - **Uwe Kamann:** listed as fraktionslos from 2017-12-12 to 2018-12-13 (31 roll-calls). Textarchiv: he left the AfD-Fraktion "am 2. Januar 2019".
  - **Marco Bülow:** listed as fraktionslos from 2017-12-12 to 2018-11-23 (29 roll-calls, in the same votes as Kamann). Textarchiv: he left the SPD-Fraktion "am 28. November 2018".
  - **Frank Pasemann:** listed as AfD from 2020-11-18 to 2020-12-11 (9 roll-calls). Textarchiv: he left "am 15. November 2020". This is the only case in the other direction.
  - **Witt and Huber:** listed as fraktionslos in WP 19 votes 750–754 and again in WP 20 votes 756–757 (2021-11-18).
  - **Heßenkemper:** listed as fraktionslos in votes 753–754 (above).

  No single pattern explains the errors. Most move an MdB to fraktionslos too early, while Pasemann's lags.
- **Scale on the rebuilt store, 2026-11-02:** the C1 replay (`docs/plans/c1-seat-counts.md`, "Step 9 result") ran through the build's own cross-check. Repersisting the 716 cached reports gives 619 roll-calls, against the 556 in the store file measured above. **55 roll-calls** file the same six MdBs under the wrong group:
  - Kamann: 38 roll-calls, 2017-12-12 to 2018-12-13.
  - Bülow: 36, 2017-12-12 to 2018-11-23.
  - Pasemann: 10, 2020-11-18 to 2020-12-11.
  - Witt and Huber: 7 each (750–754, 756–757).
  - Heßenkemper: 2 (753–754).

  The 8 roll-calls added since the first measurement (489, 490, 510, 531–533, 556 and 705) fall in the same windows. No other MdB appears.

### E5. 2016-11-09: two CDU/CSU members missing from one roll-call list

- **Status:** verified 2026-11-01.
- **Source:** `https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=440` (Änderungsantrag Hilde Mattheis und Sabine Dittmar): CDU/CSU 308 Mitglieder, Gesamt 628.
- **What is wrong:** the votes before and after it on the same day (`id=439`, `id=441`) list CDU/CSU 310 and a total of 630. Veronika Bellmann and Michael Grosse-Brömer appear in both of those but not in `id=440`, not even as "nicht abgegeben".
- **What it should be:** CDU/CSU 310, with both members counted (as "nicht abgegeben" if they did not vote).
- **Effect on poliwatch:**
  - **Vote 440:** its absent count is two short for CDU/CSU.
  - **Seat counts:** the planned rule takes a day's last roll-call, so this one does not reach the seat counts.

## Candidates

### C1. Whole speeches and replies filed inside the previous speaker's `<rede>` (WP 18/19)

- **Status:** candidate. The pattern is recorded in the audits but not yet quoted here per passage.
- **Pattern:** a speech the chair gives the floor to separately is printed as nested content of the preceding `<rede>`, not as a `<rede>` of its own:
  - whole Reden after "Nächster Redner ist …", 30 cases in the audit, 7 of them in 18/26;
  - Erwiderungen on a Kurzintervention: 18/11, 18/20, 18/42, 18/88, 18/127, 19/12, 19/14;
  - persönliche Erklärungen and Erklärungen nach § 30 / § 31 GO: 18/29, 18/97, 18/98, 18/117, 18/118;
  - Geschäftsordnung statements: 18/2, 18/3, 18/67, 18/89.
- **Evidence:** `docs/plans/a3-wp18-19-blockers.tsv` (groups `6c-floor-wording`, `erwiderung-nested`, `erklaerung-nested`, `go-debate`), `docs/plans/a3-wp18-19-audit.md`, TODOS.md "WP 18/19: nested Erwiderung, Erklärung and Geschäftsordnung turns".
- **Open question before reporting:** whether the Bundestag treats this as an error or as a markup convention of that period. The printed protocol reads correctly; only the XML structure is off. Pick two or three clear cases, quote them, and ask about the convention first.

### C2. Two person ids in one `<redner id>` (WP 21)

- **Status:** candidate.
- **Source:** `<redner id="11005217 999990074">` for Svenja Schulze (SPD) in 21/18 (ID211802600, ID211807500), 21/24 (ID212409300), 21/25 (ID212501900, ID212504800), 21/28 (ID212802500, ID212809700), 21/44 (ID214402100) and 21/45 (ID214502600, ID214505400).
- **What looks wrong:** the id attribute holds two ids. The schema expects one. We use the first.
- **To check before reporting:** what `999990074` is (an id outside the MdB number range), and whether the Stammdaten list both.

### C3. Roll-call votes with no document number on www.bundestag.de

- **Status:** candidate. This may be how the pages are, not an error.
- **Source:** roll-call pages for some votes on Bundeswehr mandates, among others: 19/29 vote 510 (MINUSMA) and 19/4 vote 489 (IS), and others in WP 18, 19 and 20 (backfill warnings "matched no TOP").
- **To check:** whether the vote page or the XLSX names the Drucksache elsewhere. If neither does, the missing link is worth reporting.
