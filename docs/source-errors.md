# Errors in the source files

A list of places where an official source file says something wrong or files content in the wrong place. The point is to send these to the publishers for correction.

**In scope:** errors in what the Bundestag publishes:
- the Plenarprotokoll XML at `dserver.bundestag.de`;
- the DIP API;
- the roll-call pages at `www.bundestag.de`.

**Not in scope:** gaps in our own parser. A sitting our validator refuses is listed here only once a human has read the source and found the source itself wrong. Parser work lives in TODOS.md.

**Who to send it to:** the owner sends reports themselves. Read on the publishers' pages on 2026-11-24:
- The only contact DIP publishes is the Auskunfts- und Rechercheservice der Parlamentsdokumentation, parlamentsdokumentation@bundestag.de, +49 30 227-32350 (<https://dip.bundestag.de/über-dip/kontakt>).
- The Open Data page (<https://www.bundestag.de/services/opendata>) names no contact of its own. The general one is mail@bundestag.de or the Kontaktformular (<https://www.bundestag.de/services/kontakt>).
- No error channel and no address of the Stenografischer Dienst was found.
- The Plenarprotokoll XML and DIP are published by the Deutscher Bundestag.
- Don't guess any other address: take it from the publishers' own pages.
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
- **Scale:** across the 716 WP 18–21 files, three `<rede>` elements have no `<redner>`. The other two (18/46 `ID1804617400`, 18/76 `ID1807611000`) are Anlage texts that begin with `<p klasse="N_Anlage">`. The 806 files held on 2026-11-26 have six: besides these three, 18/63 `ID1806309700`, also an Anlage text, and 18/117 `ID1811703000` and 18/118 `ID1811802900`. Of the five Anlage texts, 18/63's and 18/76's are Reden zu Protokoll (E17); the other three are Erklärungen nach § 31 GO, which are not stored.
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

  On 2021-06-24 the AfD-Fraktion therefore still had 88 members. On 2021-08-25 it had 87 (Hollnagel out, Heßenkemper back), with 9 fraktionslos. The roll-call pages show two members too few for the AfD from `id=750` (86 against 88), and three from `id=753` (84 against 87) to the end of WP 19.
- **What it should be:** each member listed under the Fraktion they belonged to on the vote's date.
- **Effect on poliwatch:**
  - **Vote data, until the correction below:** `vote_fractions` and `vote_members` copied the pages. These four MdBs' votes in the affected WP 19 roll-calls counted for fraktionslos, not the AfD, which affected the vote panel's group blocks and Abweichler.
  - **Seat counts:** not affected. The seat tables come from the MdB-Stammdaten, not from roll-calls; until the correction below, the seat cross-check filed these roll-calls as `shift_between_groups` (see "Scale on the rebuilt store" below).
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
- **Corrected in poliwatch, 2026-11-05:** each of these Stimmen now counts for the group the Stammdaten prove on the vote's day (`derive.refile_vote_members`): 100 Stimmen in the 55 roll-calls. `vote_members.listed_party_id` keeps the page's group, and the page's totals can be read back from the store. The dossier panel names the difference. Old and new figures per vote and group are in `docs/plans/e4-refiled-votes-old-new.tsv`. Since 2026-11-26 the seat cross-check compares both the page's and the re-filed totals with the seat counts, files these roll-calls as `refiled` and lists every re-filed Stimme in its report. The fresh reference store of 2026-11-12, built online from main 28799ac, gives the same 100 Stimmen in 55 roll-calls. Rebuilt from its cached pages, its TSV equals the committed one byte for byte, and its moved rows name exactly these six MdBs, in these windows (`docs/plans/a3-phase4.md`). The Bundestag's pages still show these errors, so the entry stands for a correction request.
- **Scale after T4, 2026-11-18:** the 83 restored sittings bring 108 roll-calls, and the replay re-files **157 Stimmen in 87 roll-calls** (57 new in 32). All fall in the windows above and name no other MdB: Kamann 30 more (2018-02-22 to 2018-11-29), Bülow 24 (2018-02-22 to 2018-11-08), Pasemann 1 (vote 700), and Witt and Huber 1 each in vote 755 (2021-09-07), between 754 and 756. On 755 the page files Heßenkemper under the AfD again, so he is not re-filed there. The list is `docs/plans/t4-acquire/e4-refiled-new.tsv`.
- **Scale, 2026-11-26** (736 roll-calls, 2013-11-28 to 2026-11-13; MdB-Stammdaten Stand 29.04.2026): still **157 Stimmen in 87 roll-calls**, under the rule that the file proves a group only up to 90 days before its Stand and only on days a Fraktion, Gruppe or Fraktionslos record covers. The newest re-filed Stimme lies 1,623 days before the Stand, and every fraktionslos day of the six MdBs is covered by an explicit `Fraktionslos` record.

### E5. 2016-11-09: two CDU/CSU members missing from one roll-call list

- **Status:** verified 2026-11-01.
- **Source:** `https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=440` (Änderungsantrag Hilde Mattheis und Sabine Dittmar): CDU/CSU 308 Mitglieder, Gesamt 628.
- **What is wrong:** the votes before and after it on the same day (`id=439`, `id=441`) list CDU/CSU 310 and a total of 630. Veronika Bellmann and Michael Grosse-Brömer appear in both of those but not in `id=440`, not even as "nicht abgegeben".
- **What it should be:** CDU/CSU 310, with both members counted (as "nicht abgegeben" if they did not vote).
- **Effect on poliwatch:**
  - **Vote 440:** its absent count is two short for CDU/CSU.
  - **Seat counts:** not affected. The seat tables come from the MdB-Stammdaten; the seat cross-check files vote 440 as `roll_call_short`.

### E6. Vote 990: the roll-call box says "Antrag angenommen" where the Antrag was rejected

- **Status:** verified 2026-11-07.
- **Sources:**
  - `https://www.bundestag.de/parlament/plenum/abstimmung/abstimmung?id=990` (2025-12-19, Plenarprotokoll 21/51, Die Linke's Antrag 21/627, "Steuerprivilegien für höchste Erbschaften streichen").
  - `https://dserver.bundestag.de/btp/21/21051.xml`, the chair's announcement of the result.
  - DIP, the Vorgangsposition's `beschlussfassung` for Drucksache 21/627.
- **What is wrong:** the page says two opposite things about one ballot:
  - Its Beschluss list: "Beschlussempfehlung 21/2691 (Antrag 21/627 ablehnen) angenommen".
  - Its article: the Bundestag has "nach einstündiger Aussprache abgelehnt" the Antrag.
  - The roll-call box in the same Beschluss section, under "namentliche Abstimmung zu Antrag 21/627" and "Gesamt: 554 Ja: 507 Nein: 47 Enthaltungen: 0": "Antrag 21/627 angenommen".
- **Why the box is the wrong one:**
  - The ballot was on the Beschlussempfehlung, so 507 Ja rejected the Antrag.
  - The chair, in 21/51: "Die Beschlussempfehlung ist damit angenommen."
  - DIP: Beschlusstenor "Ablehnung der Vorlage", with "507:47:0 (Annahme der Beschlussempfehlung auf Ablehnung)".
- **What it should be:** the box names the Beschlussempfehlung, as on the pages of votes 774 ("Beschlussempfehlung 20/1890 Buchstabe b (Antrag 20/699 ablehnen) angenommen") and 777 ("Beschlussempfehlung 20/1835 angenommen").
- **Scale:** of the 619 stored roll-calls, 25 have an official result worded on the Antrag. In all 25 the word agrees with the Ja or Nein majority. Vote 990 is the only one of them on a Beschlussempfehlung to reject. Only the pages of votes 638, 695, 774, 777, 801, 883 and 990 were read. That count was taken on the A3 store's cached pages.
- **Scale on the fresh reference store, 2026-11-12:** every page was fetched again, and 35 of the 619 roll-calls are now worded on the Antrag: 990 and 34 others. 990 is stored as `proposition` since the correction below, so the store's `result_scope = application` count is 34. In 34 of the 35 the word agrees with the Ja or Nein majority. The exception is 996 (2026-03-25), a second Beschlussempfehlung to reject. Its box gives the right word ("abgelehnt" on a Ja majority for rejecting the Antrag), so the page is not in error there. Why the count rose by 10 is open (TODOS.md, "Vote direction: what the 2026-11-07 fix left open").
- **Effect on poliwatch:** vote 990 read "Antrag: Angenommen" and "der Antrag wurde angenommen (laut Beschluss auf bundestag.de)".
- **Corrected in poliwatch, 2026-11-07:** on a vote the chair's announcement or DIP's decision establishes as a Beschlussempfehlung to reject (since 2026-11-17 an inversion read only from a roll-call or Drucksache title no longer counts here), a Ja majority outranks the box's word "Antrag … angenommen": the word is read as the ballot's (`validate_dip_protocol._read_contradicted_official_result`). Vote 990 now reads "Antrag: Abgelehnt". `votes.result_scope` moved from `application` to `proposition`, and `result_raw` and `result_source` stay `accepted` and `official`. The Bundestag's page still shows the error, so the entry stands for a correction request.

### E7. Ten speaker ids are given to more than one person

- **Status:** verified 2026-11-07, on the 716 cached XML files of the A3 store, scanning every `<redner>`. The first scan on 2026-11-06 found two of these ids. The last three were found on 2026-11-17, when the T4 run's WP 18 rebuild refused on two of them: the build's name check, run offline over the parsed units of the 719 stored sittings and the XML of the 83 sittings T4 acquires, found those two and `11002190` in 19/1. 21/106's XML has not been fetched, so it was not scanned.
- **Source:** `https://dserver.bundestag.de/btp/<WP>/`, the files of the sittings named below.
- **What is wrong:** `<redner id>` is meant to identify one person.
  - `id="10000"`: "Marja-Liisa Völlers (SPD)" in 19/49 and 19/57; "Olaf in der Beek (FDP)" in 19/16; "Dr. Carsten Sieling, Bürgermeister (Bremen)" in 19/60. The Sieling entry also prints "Carsten Sieling," as `<vorname>`, "Bürgermeister" as `<nachname>` and "Bremen" as `<fraktion>`.
  - `id="999990141"`: Dr. Mehmet Daimagüler in 20/144; Judith Gerlach, Staatsministerin (Bayern), in 20/121 and 20/194.
  - `id="999990124"`: Annette Widmann-Mauz in 18/39, 18/53, 18/72, 18/84 and 18/91; Dr. Andreas Bovenschulte in 20/21.
  - `id="999990108"`: Anette Kramme in 18/53, 18/72 and 18/78; Maika Friemann-Jennert in 19/228.
  - `id="999990127"`: Enak Ferlemann in 18/44, 18/54, 18/59, 18/76, 18/81, 18/87 and 18/91; Peter Beuth in 20/46, 20/75 and 20/95.
  - `id="999990109"`: Gabriele Lösekrug-Möller in seven sittings of WP 18; Tim Ostermann in an annex of 19/234.
  - `id="11003609"`: Sibylle Pfeiffer; Michael Roth, once, in the speaker list of 18/230.
  - `id="11004105"`: Dr. Thomas de Maizière's own id, printed for him in 69 sittings of WP 18 and 19 (in part of WP 18 as "Dr. Thomas Maizière"); Bundespräsident Dr. Frank-Walter Steinmeier's address in 18/223 (`ID1822300400`), whose own id is `11004167`.
  - `id="11002190"`: Dr. Hermann Otto Solms's own id; Präsident Dr. Wolfgang Schäuble's inaugural address in 19/1 (`ID19101300`), whose own id is `11001938`. The table of contents of 19/1 also prints it for Dr. Marco Buschmann (FDP), whose own id is `11004023`; a table of contents is not stored.
  - `id="999990055"`: Monika Heinold, Ministerin (Schleswig-Holstein), in 18/180 (`ID1818001000`); Thomas Heilmann, Senator (Berlin), in 18/183 (`ID1818302300`), who has his own id `11004741` as an MdB from WP 19.
- **Outside confirmation:** the CPP-BT codebook (version 2026-09-19, section 5.3) documents id 10000 as assigned several times.
- **Our side:** fixed 2026-11-07. `scripts/person_corrections.json` says who each printed name is for the five ids with stored units, and the build refuses a Redner-ID printed with unrelated names until it has an entry (`docs/stable-ids.md`). `999990109` and `11003609` have no entry: their second person is in an annex and a speaker list that are not stored. `11004105`, `11002190` and `999990055` have an entry since 2026-11-17, before the T4 run stores their sittings. De Maizière and Solms hold their ids: their records keep them, and only the other speaker's Rede moves to that speaker's own id. Since 2026-11-17 the parser reads a Land's name in `<fraktion>` beside a Bundesrat member who speaks for that Land as no Fraktion (`derive.printed_fraktion`), so Sieling's Rede `ID196001500` counts for the Bundesrat with no Fraktion, as the store's other Bundesrat Reden do.

### E8. 19/36: a Zu-Protokoll continuation filed under the title of the absentee list

- **Status:** verified 2026-11-13, on the XML fetched 2026-11-12.
- **Source:** `https://dserver.bundestag.de/btp/19/19036.xml`, `<anlage>` "Anlage 2": `<anlagen-text anlagen-typ="Liste der entschuldigten Abgeordneten">`, holding `<rede id="ID193616800">` (Martina Stamm-Fibich, SPD).
- **What is wrong:** the `anlagen-typ` repeats the title of Anlage 1, the real list of absent members. Anlage 2 holds no list. Its own headings read "Zu Protokoll gegebene Fortsetzung des abgebrochenen Redebeitrages der Abgeordneten Martina Stamm-Fibich (SPD)" and "(Tagesordnungspunkt 5, Seite 3370 C)". In TOP 5 (`ID193602600`) Stamm-Fibich breaks off her speech for her voice, the chair offers to take the rest zu Protokoll, and a footnote points to Anlage 2. The protocol's Inhaltsverzeichnis lists Anlage 2 under the same heading.
- **What it should be:** an `anlagen-typ` for a written submission, as "Zu Protokoll gegebene Rede".
- **Scale:** of the 799 annex blocks with an "entschuldigt" title in 802 sittings of WP 18–21 (the 718 of the reference store and 84 excluded sittings: 50 of WP 18, 33 of WP 19 and 20/11), this is the only one holding a `<rede>`, and the only block in the 802 with a Zu-Protokoll heading under another title. Counted 2026-11-14.
- **Our side:** fixed 2026-11-13. `scripts/validate_dip_protocol.py` reads a block under that title by its first `Anlage_3` heading when the heading says "Zu Protokoll gegebene Rede(n)" or "… Fortsetzung" (`MISTITLED_ZU_PROTOKOLL`), so the text is a `zu_protokoll` Beitrag under TOP 5. Before #147 the parser dropped it without a word; from #147 until this fix the sitting refused (`docs/plans/withholding-preflight/report.md`, "19/36").

### E9. 18/158: the 37 declarations of Anlage 7 are printed in the Sitzungsverlauf

- **Status:** verified 2026-11-15, on the XML fetched 2026-11-12 (`~/agent-runs/w1/xml`, sha256 as in `docs/plans/withholding-preflight/preflight.json`).
- **Source:** `https://dserver.bundestag.de/btp/18/18158.xml`. After the sitting's close ("Die Sitzung ist geschlossen.", "(Schluss: 21.16 Uhr)") the `<sitzungsverlauf>` goes on with `<tagesordnungspunkt top-id="Geschaeftsordnung">`, which has no heading and holds 37 `<rede>`s, `ID18158106000` (Heike Baehrens, SPD) to `ID18158109600` (Gülistan Yüksel, SPD). Each opens with its Redner's marker and runs straight into the text, as an annex declaration does ("Heike Baehrens (SPD): Angesichts der großen Zahl der Flüchtlinge …").
- **What is wrong:** these are the Erklärungen nach § 31 GO to the vote on the Asylpaket II (TOP 3 a). `<anlage>` "Anlage 7" holds only their title, `<anlagen-text anlagen-typ="Erklärungen nach § 31 GO">` with its heading and the line "zu der namentlichen Abstimmung über … (Tagesordnungspunkt 3 a)", and no `<rede>`. The protocol's Inhaltsverzeichnis lists all 37 under "Anlage 7", from page 15617 C.
- **What it should be:** the 37 `<rede>`s inside Anlage 7, as Anlage 15 holds its 9 declarations. Anlagen 2 to 6 and 8 to 14 print theirs as paragraphs, without a `<rede>`.
- **Scale:** of the 802 sittings of WP 18–21 held (the 718 of the reference store and the 84 excluded files), 18/158 is the only one with a `<rede>` of the Sitzungsverlauf that the Inhaltsverzeichnis lists under an "Anlage" block. Counted 2026-11-15.
- **Our side:** fixed 2026-11-15, before the sitting is stored. `exclude_annex_reden_in_verlauf` in `scripts/validate_dip_protocol.py` gives such a `<rede>` the status of the annex it is listed under, when that annex is a single block an `ANNEX_EXCLUSIONS` rule keeps out and holds no `<rede>` of its own, and drops the TOP it leaves empty. The 37 are excluded as § 31 declarations, as the 9 in Anlage 15 are. They are not withheld, so they count against no coverage share. Without the rule they were 37 Reden (`docs/plans/t4-acquire/n8-review.md`, on branch `claude/clever-ellis-b1cafc`).

### E10. 19/13: the heading of the Befragung der Bundesregierung has a space inside a word

- **Status:** verified 2026-11-15, on the XML fetched 2026-11-12.
- **Source:** `https://dserver.bundestag.de/btp/19/19013.xml`, `<tagesordnungspunkt top-id="Tagesordnungspunkt 1">`: `<p klasse="T_fett">Befr agung der Bundesregierung</p>`. The Inhaltsverzeichnis spells it "Befragung der Bundesregierung: Verordnung zur Änderung der Schweinepest-Verordnung …". The same file also prints "Tagesordnung spunkt" in the chair's text.
- **What it should be:** "Befragung der Bundesregierung".
- **Scale:** in the 802 sittings of WP 18–21 held, no other heading that names a Befragung or a Fragestunde is broken this way. A scan for a word split by a space (both halves rare, the joined word common in the corpus) finds eight other headings in seven sittings, none of them in a word that decides what a turn counts as: 19/37 "Drucksach e 19/2509", 19/63 "h ier" (twice), 19/67 "Ver einbarte Debatte", 19/69 "Bun desregierung", 19/74 and 19/86 "Immissionsschutzgesetze s", 19/101 "Sammelübersich t 247". Counted 2026-11-15.
- **Our side:** fixed 2026-11-15, before the sitting is stored. `speech_kinds.heading_formats` compares a heading with all whitespace removed, so TOP 1 is a Befragung: the minister's report stays the one Rede and the 60 other `<rede>`s are Fragen and Antworten. Without the fix, 57 of them were Reden and 3 (`ID191304800`, `ID191305000`, `ID191306000`) were withheld as refused Zwischenfragen. The eight other split headings keep their spelling on the pages.

### E11. 18/62: one turn of the chair in the Fragestunde is filed as a speaker with a Fraktion

- **Status:** verified 2026-11-20, on the XML fetched 2026-11-12 (`~/agent-runs/w1/xml`).
- **Source:** `https://dserver.bundestag.de/btp/18/18062.xml`, `<tagesordnungspunkt top-id="Tagesordnungspunkt 2">` (Fragestunde), after the answer of Dr. Günter Krings to Petra Pau's Frage: `<p klasse="redner">` with `<redner id="11002800">`, `<fraktion>CDU/CSU</fraktion>` and `<rolle_lang>Vizepräsident</rolle_lang>`, printed "Johannes Singhammer (CDU/CSU):", followed by "Sie, Frau Kollegin, haben mit Sicherheit eine Nachfrage."
- **What is wrong:** Singhammer presides at this point. His turns before and after it are `<name>Vizepräsident Johannes Singhammer:</name>` ("Frau Kollegin, Sie haben eine weitere Nachfrage."). This one turn is marked as a speaker of the CDU/CSU.
- **What it should be:** `<name>Vizepräsident Johannes Singhammer:</name>`, as the chair's other turns in the Fragestunde.
- **Scale:** in the 803 sittings of WP 18–21 held (the 801 of the reference store, 18/62 and 18/90), five presidium markers stand outside a `<rede>`; this is the only one whose person presides. Counted 2026-11-20.
- **Our side:** read as Sitzungsleitung by `mark_presidium_markers_outside_reden` in `scripts/validate_dip_protocol.py` (ADR 0004, amendment of 2026-11-20). Without the rule it was a `fragestunde_antwort` with a role no Sprechrolle rule maps.

### E12. 20/25: a stage direction is printed in the chair's element inside a speech

- **Status:** verified 2026-11-20, on the XML cached 2026-11-12 in the reference store.
- **Source:** `https://dserver.bundestag.de/btp/20/20025.xml`, Tagesordnungspunkt 5, `<rede id="ID202506700">` (Lamya Kaddor, BÜNDNIS 90/DIE GRÜNEN): `<name>(Vizepräsident Wolfgang Kubicki räuspert sich)</name>`, followed by her own closing words, "– Sofort, Herr Präsident. – Eines ist aber auch klar: …" and "Ich danke Ihnen für Ihre Aufmerksamkeit."
- **What is wrong:** `<name>` holds the label of a chair turn ("Vizepräsident Wolfgang Kubicki:"). This one holds a stage direction in parentheses: Kubicki speaks no words, and Kaddor answers him and goes on. Elsewhere the source prints such stage directions as `<kommentar>`.
- **What it should be:** `<kommentar>(Vizepräsident Wolfgang Kubicki räuspert sich)</kommentar>`.
- **Scale:** in the 806 sittings of WP 18–21 held (the reference store, with 18/62, 18/90 and 21/107 to 21/109), this is the only `<name>` whose whole text stands in parentheses. Counted 2026-11-21.
- **Our side:** read as a `<kommentar>` by `mark_stage_direction_names` in `scripts/validate_dip_protocol.py` (ADR 0004, amendment of 2026-11-20, stage directions; approved by the owner on 2026-11-21). Without the rule her last two paragraphs (52 words) were read as chair text and stored nowhere.

### E13. WP 18/19: speakers who are not the chair are printed in the chair's element

- **Status:** verified 2026-11-20 (census of [name-tag-speakers.md](plans/name-tag-speakers.md)), on the XML of the reference store; rule built 2026-11-22.
- **Source:** for example `https://dserver.bundestag.de/btp/18/18030.xml`, Einzelplan 15, inside `<rede id="ID1803002900">` (Sönke Rix, SPD): after "Jetzt hat als nächste Rednerin die Kollegin Sylvia Pantel das Wort." the source prints `<name>Sylvia Pantel (CDU/CSU) : </name>` and her whole first Rede, then Gülistan Yüksel's and Alois Rainer's the same way. In 18/10, Tagesordnungspunkt 3, Alexander S. Neu's Rede stands as `<name>Dr. Alexander S. Neu (DIE LINKE) : </name>` outside any `<rede>`.
- **What is wrong:** `<name>` holds the label of a chair turn ("Vizepräsidentin Edelgard Bulmahn:"). These tags name a speaker who does not chair. Elsewhere the source prints such a speaker with a speaker marker, `<p klasse="redner"><redner id="…">`, and a Rede given the floor separately as a `<rede>` of its own.
- **What it should be:** a speaker marker with the person's Redner-ID, and for a whole Rede a `<rede>` of its own.
- **Scale:** 170 turns, 80,381 words, in 51 sittings: 167 in WP 18 (18/3 to 18/223), and 19/99, 19/104 and 19/125. WP 20 and 21 print none. Counted 2026-11-20 over 803 files and again 2026-11-22 over the 806 held.
- **Our side:** each turn is listed in `scripts/reviewed_units.json` (kinds `name_*`) and rewritten into a speaker marker by `mark_name_speakers` in `scripts/validate_dip_protocol.py` (ADR 0004, amendment of 2026-11-22). Before the rule, the words were stored nowhere, 18/6 `ID1800602300` and 18/36 `ID1803601400` were withheld, and 18/104 `ID1810402200` was an empty Rede with no speaker.

### E14. WP 18 to 21: speakers printed with a marker outside any `<rede>`

- **Status:** verified 2026-11-22 (census of [loose-speaker-markers.md](plans/loose-speaker-markers.md)), on the XML of the reference store; rule built 2026-11-22.
- **Source:** for example `https://dserver.bundestag.de/btp/18/18007.xml`, Zusatztagesordnungspunkt 1: after "Das Wort hat der Kollege Jan Korte für die Fraktion Die Linke." the source prints `<p klasse="redner"><redner id="11003790">…</redner>Jan Korte (DIE LINKE): </p>` and his 885-word Rede directly in the `<tagesordnungspunkt>`; the first `<rede>` of the TOP is the next speaker's. In 18/6 Tagesordnungspunkt 16, Golze's, Bär's and Brantner's Reden stand the same way.
- **What is wrong:** outside a Fragestunde, a speaker's words stand in a `<rede>`. These markers open a Rede, a reply or a Zwischenfrage with no `<rede>` around it.
- **What it should be:** a `<rede>` of its own for a Rede, and the turn inside the `<rede>` it belongs to for a reply.
- **Scale:** 74 markers, 19,686 words, in 31 sittings: 23 whole Reden in 11 WP 18 sittings, and short turns next to a `<rede>` in WP 18 to 21 (19/114 holds 18 markers). Counted 2026-11-22 over the 806 held files.
- **Our side:** each marker is listed in `scripts/reviewed_units.json` (kinds `loose_*`) and placed by `mark_loose_markers` in `scripts/validate_dip_protocol.py` (ADR 0004, amendment of 2026-11-22 on markers outside any `<rede>`). Before the rule, the words were stored nowhere.

### E15. WP 19 and 20: an MdB who joined mid-period is printed under a provisional Redner-ID first

- **Status:** verified 2026-11-23, on the 806 XML files of the reference store, scanning every `<redner>`, against the MdB-Stammdaten (Stand 2026-04-29).
- **Source:** `https://dserver.bundestag.de/btp/<WP>/`, for example `https://dserver.bundestag.de/btp/19/19194.xml`: `<redner id="999990105">` for Dr. Janosch Dahmen (BÜNDNIS 90/DIE GRÜNEN), whose mandate began on 2020-11-12. From 19/226 on he is `<redner id="11004962">`, his id in the MdB-Stammdaten.
- **What is wrong:** `<redner id>` is meant to be one id per person. These 14 MdBs have two: an id starting with 99999 (Manderla: 999980200) after joining, for one sitting (Bartz, Vontz) up to the rest of the Wahlperiode (Rinkert, 20/79 to 20/191), and the id of the MdB-Stammdaten afterwards. 999980200 stands for Gisela Manderla on her return to the Bundestag in WP 19; in WP 18 and from 19/89 on she is 11004348.
- **Which:** Manderla 999980200 → 11004348; Bubendorfer-Licht 999990089 → 11004956; Weingarten 999990085 → 11004950; Lehmann 999990088 → 11004953; Bach 999990092 → 11004957; Nölke 999990096 → 11004958; Schneidewind-Hartnagel 999990084 → 11004951; Ludwig 999990087 → 11004954; Martin 999990097 → 11004959; Dahmen 999990105 → 11004962; Bünger 999990123 → 11005289; Bartz 999990130 → 11005301; Rinkert 999990129 → 11005300; Vontz 999990132 → 11005302. The sittings of each are in `scripts/person_corrections.json` (`same_person`).
- **What it should be:** the id of the MdB-Stammdaten from the first sitting on.
- **Scale:** these 14 are the MdBs whose DIP roster record the second id kept apart. The other Redner-IDs of this form (MdBs the XML prints under no other id, such as Bettina Bähr-Losse 999980100, government members, Bundesrat members and guests) were not checked here (TODOS.md "Placeholder Redner ids put one speaker on two Personenseiten").
- **Our side:** joined since 2026-11-23: a reviewed `same_person` entry makes the two ids one Personenkennung. `mps.xml_redner_id` keeps the printed id on each record.

### E16. WP 19 to 21: 33 protocol files are first editions that stop before the sitting ends

- **Status:** verified 2026-11-23 on the cached XML, with five PDFs read against it.
- **Source:** for example `https://dserver.bundestag.de/btp/20/20147.xml`. The last `<rede>` of the Sitzungsverlauf is `ID2014714100` (Karsten Hilse, AfD, p. 18766 B), which ends "Jetzt rufe ich auf Michael Kruse für die FDP-Fraktion." Then comes `<p klasse="Ende">Der gesamte und damit endgültige Stenografische Bericht der 147. Sitzung wird am 23. Januar 2024 veröffentlicht.</p>`, and `<sitzungsende sitzung-ende-uhrzeit="23:31"/>`. The same notice closes the Inhaltsverzeichnis and the last annex. `https://dserver.bundestag.de/btp/20/20147.pdf` (Last-Modified 23 Jan 2024, md5 equal to DIP's `pdf_hash`) goes on with Michael Kruse at p. 18767 A, to "(Schluss: 23.31 Uhr)" on p. 18799, and has no such notice.
- **What is wrong:** the XML is the partial edition of a long sitting. The final one was published as PDF and the XML was never replaced. Missing are the rest of the Sitzungsverlauf and the annexes that belong to it, among them nearly all the sitting's Reden zu Protokoll: the PDF of 20/147 has 20 annexes, 12 of them "Zu Protokoll gegebene Rede(n)"; the XML has 9, with one.
- **What it should be:** the XML of the complete report at the same address, with its pages and annexes.
- **Scale:** 33 of the 806 held sittings: 19/55; 20/141, 147, 175, 178, 185, 191, 194, 203, 207, 209, 210; 21/14, 21, 31, 34, 37, 40, 47, 53, 56, 59, 65, 68, 80, 83, 86, 89, 96, 99, 102, 105, 108. After the last printed `<rede>`, DIP lists 1,189 Reden (WP 19: 41, WP 20: 389, WP 21: 759; without 23 farewells and greetings by the chair, all in WP 20, that DIP also types as "Rede") and, in all 33 sittings, 429 Reden zu Protokoll more than the XML prints (WP 20: 148, WP 21: 281). Per sitting: [per-sitting.tsv](plans/zu-protokoll-gap/per-sitting.tsv). 19/107 prints the notice too, but holds the whole sitting.
- **Checked elsewhere, 2026-11-23:** dserver serves all 33 files with the cached size, and each cached file's md5 is DIP's `xml_hash`. Read for 20/147 only: the XML on the Open Data page is byte-identical, and DIP's `plenarprotokoll-text` ends with the same notice, though its `pdf_hash` is the final PDF's. In the five PDFs read (20/147, 20/178, 21/40, 21/83, 21/99), the page DIP gives prints every one of the 262 Reden after the cut and the 157 Reden zu Protokoll (one label stands on the next page). Of the other 28 only the closing line was read, on 2026-11-24; all 28 have the md5 of DIP's `pdf_hash`.
- **20/210 also** prints its Inhaltsverzeichnis with empty page numbers (`<xref div="" pnr="" …>`) and two end times, 02:19 in the head and 02:15 at the end. Its PDF prints "(Schluss: 2.19 Uhr)".
- **End times:** in four more sittings the PDF's "(Schluss: …)" is not the XML's `sitzung-ende-uhrzeit`: 19/55 prints 1.28 (XML 01:30), 20/178 23.12 (23:11), 21/89 23:37 (23:36), 21/96 00:15 (00:16). Per sitting: [end-times.tsv](plans/zu-protokoll-gap/end-times.tsv).
- **Effect on poliwatch:** the Reden, Beiträge and Tagesordnungspunkte after the cut are stored nowhere.
- **Our side** ([ADR 0006](adr/0006-mark-cut-protocol-files.md), [cut-protocols.md](plans/cut-protocols.md)): each such file is marked (`protocols.xml_cut`) and its sitting kept; what DIP lists after the cut is in `unprinted_contributions` and counts nowhere; its weeks and months are *unvollständig erfasst* for Fakten on Reden; the four end times are corrected from the PDFs by a reviewed list (`scripts/reviewed_end_times.json`); the dossier, the Puls week, person pages, DATA.md and the Daten page name the gap; the store gate checks the mark against the notice. Reading the missing part from the PDFs comes after the first release.

### E17. WP 18: ten Reden zu Protokoll are printed without a `<rede>` of their own

- **Status:** verified 2026-11-23 on the XML of the reference store; read by a reviewed list since 2026-11-26.
- **Source:** `https://dserver.bundestag.de/btp/18/`, annexes titled "Zu Protokoll gegebene Rede(n)".
- **What is wrong:** three shapes.
  - A second speaker's text inside the previous speaker's `<rede>`, with a speaker marker: Charles M. Huber in 18/17 `ID1801712700` (Bernd Fabritius), Gabriele Schmidt (Ühlingen) in 18/66 `ID1806614200` (Martin Pätzold) and 18/112 `ID1811211800` (Matthäus Strebl), Özcan Mutlu in 18/115 `ID1811515000` (Rosemarie Hein).
  - The same without a marker, as plain text: Ralph Lenkert in 18/23 `ID1802308800` (Michael Thews; `<p klasse="J_Abstand">`), Michaela Engelmeier in 18/63 `ID1806311300` (Johannes Steiniger; `<p klasse="N_Anlage">`).
  - No `<rede>` around the text: Christian Petry in 18/34 Anlage 2, Armin Schuster in 18/46 Anlage 16, Hartmut Koschyk in 18/47 Anlage 4, Metin Hakverdi in 18/155 Anlage 2.

  The Inhaltsverzeichnis gives Huber and Lenkert a Rede-ID (`ID1801712800`, `ID1802308900`) that no `<rede>` carries.
- **What it should be:** a `<rede>` with a speaker marker for each.
- **Scale:** the annex blocks of that title in the 806 held files. 18/47 Anlage 5 prints Georg Kippels's Rede of 18/46 again without a `<rede>`; the store has it from 18/46. The Neudrucke in 18/192, 18/238 and 18/245 are reprints and not counted. A census of the 806 files on 2026-11-26 (`docs/plans/e17-wp18-texts.md`) found no other `<rede>` with two writers' markers, no other marker outside a `<rede>` and no other label paragraph. It found a further defect, not counted here: in 18/136, 18/206, 18/209, 18/243 and 19/104 the bullet points of a written Rede stand between two `<rede>`s (TODOS.md).
- **Effect on poliwatch until 2026-11-26:** Lenkert's and Engelmeier's words were stored as the other speaker's. The other eight were stored nowhere. 18/63 `ID1806309700` (Freudenstein) and 18/76 `ID1807611000` (Böhmer), both `N_Anlage` without a `<redner>` (E3), were stored with no speaker and no text.
- **Our side:** the ten texts and the two `<rede>`s without a marker are listed in `scripts/reviewed_units.json` (kind `annex_rede`) and placed by `mark_annex_texts` in `scripts/validate_dip_protocol.py`. Each text becomes a zu Protokoll gegebener Beitrag of its writer. A text inside another writer's `<rede>` is split off as `<id>:2`. Freudenstein's and Böhmer's `<rede>`s get their writer under their own id. A text in no `<rede>` becomes `annex:<block>:<place>`. A zu-Protokoll block where a `<rede>` holds two or more writers' markers or none, or a marker stands outside any `<rede>`, now refuses its sitting unless the list names it. Plain text with no marker gives no such sign.

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

### C5. Two people merged into one speaker in WP 20

- **Status:** candidate. Found 2026-11-07. Not checked against the PDF.
- **Source:** in 20/94 (`ID209407600`), 20/96 (`ID209614200`) and 20/116 (`ID2011606700`), among others: `<redner id="11005304">` with `<vorname>Dirk-UlrichAlexander</vorname>`, `<nachname>Mende Föhr</nachname>` and `<fraktion>SPDCDU/CSU</fraktion>`. The printed label in 20/94 reads "Dirk-Ulrich Mende (SPD):".
- **What looks wrong:** the names and Fraktionen of Dirk-Ulrich Mende and Alexander Föhr are run together, 23 times across the WP 20 files. In our files `11005304` also appears alone for each of them, 34 times for Föhr and 23 for Mende. CPP-BT's rows give Mende `11005303`, so the source files may have changed since we fetched ours.
- **To check before reporting:** who spoke in each case, against the PDF, and whether a fresh download still shows this. Our store files the three Reden above under Mende, CPP-BT files 20/94 under Föhr.

### C8. Two names run together in one speaker in 20/82

- **Status:** candidate. Found 2026-11-07. Not checked against the PDF.
- **Source:** 20/82, `ID208205200`: `<redner id="999990134">` with `<vorname>Dirk-UlrichLena</vorname>` and `<nachname>Mende Kreck</nachname>`, role "Senatorin (Berlin)". The printed label reads "Dr. Lena Kreck, Senatorin (Berlin):", and the chair gives "Frau Dr. Lena Kreck" the floor.
- **What looks wrong:** Dirk-Ulrich Mende's name fields run into Lena Kreck's, the pattern of C5. The id itself appears for no one else in our files.
- **Our side:** `scripts/person_corrections.json` names her, on her DIP record.

### C6. Spoken text inside `<fraktion>` in 18/222

- **Status:** candidate. Found 2026-11-07. Not checked against the PDF.
- **Source:** 18/222, `ID1822204600`: `<fraktion>CDU/CSU: Ich glaube, ich habe auch nicht gesagt – –</fraktion>` for Dr. Astrid Freudenstein.
- **What looks wrong:** the start of her reply sits inside the Fraktion element.
- **Our side:** since 2026-11-17 the parser reads a known Fraktion followed by a colon as that Fraktion (`derive.printed_fraktion`), so her Erwiderung counts for CDU/CSU, as CPP-BT has it, and no "CDU/CSU: Ich glaube, …" group or parties row is stored. The same shape, "SPD: Ja." in 19/30 (`<redner id="11004622">`), reaches no stored unit. Any other `<fraktion>` value that names no Fraktion we know refuses the sitting; on the 801 cached sittings none does.

### C7. Reden outside any `<tagesordnungspunkt>` in 18/44, 18/49 and 18/89

- **Status:** candidate. Found 2026-11-07.
- **Source:** 18/49: 26 of 51 `<rede>` elements sit directly under `<sitzungsverlauf>`, from `ID1804900100` (Dr. Wolfgang Schäuble, budget 2015) on. 18/44: 3 such elements, from `ID1804400100`. 18/89, stored since 2026-11-17: 15 such elements, which its Inhaltsverzeichnis lists under "Zusatztagesordnungspunkt 4".
- **What looks wrong:** every other `<rede>` outside the annexes in the 716 files sits inside a `<tagesordnungspunkt>`, and in the 801 files of 2026-11-17 every one outside these three sittings.
- **To check before reporting:** whether the schema allows this.
- **Our side:** since v0.36.0.0 each run is read under the item the protocol's Inhaltsverzeichnis names for it (`docs/data-methods.md`). Their DIP links: TODOS.md, "Give the agenda items of 18/49 and 18/44 adopted from the Inhaltsverzeichnis their DIP links".

### C3. Roll-call votes with no document number on www.bundestag.de

- **Status:** candidate. This may be how the pages are, not an error.
- **Source:** roll-call pages for some votes on Bundeswehr mandates, among others: 19/29 vote 510 (MINUSMA) and 19/4 vote 489 (IS), and others in WP 18, 19 and 20 (backfill warnings "matched no TOP").
- **To check:** whether the vote page or the XLSX names the Drucksache elsewhere. If neither does, the missing link is worth reporting.

### C4. Vote 798: DIP's tally has two digits swapped

- **Status:** candidate. Both passages were read, but it is one digit pair in a note, and the entry should be checked once more before it is sent.
- **Source:** DIP, the `beschlussfassung` for Drucksache 20/1849 in Plenarprotokoll 20/54: "612:38:1 (Annahme der Beschlussempfehlung auf Ablehnung der Vorlage)".
- **What looks wrong:** the protocol has 621 Ja: "Mit Ja haben gestimmt 621, mit Nein haben gestimmt 38" and "Endgültiges Ergebnis … davon ja:621". The 660 Stimmkarten and the stored member rows agree with 621.
- **Effect on poliwatch:** none on the figures. A DIP decision binds to a vote only with an exact tally, so this one binds to nothing; vote 798 is established from the chair's announcement.
