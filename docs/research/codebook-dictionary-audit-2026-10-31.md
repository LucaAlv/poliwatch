<!-- Audit of the codebook inputs against the writing code, /ship run 6, 2026-10-31. All 20 false statements in section 1 were corrected in the same commit (wording only; the vote_fractions source avoids the word "Einzelstimme" pinned by tests). Section 3 items stay open. -->

# Audit der Codebook-Eingaben gegen den Schreibcode

Stand: Worktree `codebook` (HEAD 16d9b9a), Referenz-DB `ref/ref.sqlite` (Exportformat älter, 2026-10-23). Referenzwerte nie als Beleg für nach der Referenz hinzugekommene Spalten benutzt (`result_*`, `procedure_type`, `passage_state`, `debate_url`, `forderung*`, `sprechrolle`, `unattributed_char_count`); die Referenz hat außerdem keinen MdB-Kader (`is_mdb` überall 0).

Code-Referenzen: `P` = scripts/persist_dip_pulse_store.py, `F` = scripts/facts.py, `R` = scripts/person_registry.py, `V` = scripts/validate_dip_protocol.py, `B` = scripts/build_dip_pulse_site.py, `D` = scripts/derive.py, `S` = scripts/stable_ids.py.

Konfidenz: **hoch** = Zitat widerlegt den Text eindeutig; **mittel** = Zitat widerlegt den Text, hängt aber an einer Annahme über Eingaben; **niedrig** = Wortlautfrage, Text ist eher irreführend als falsch.

---

## 1. False statements

### F1. `mps.aw_match.meaning` (hoch)

Text: „Werte wie partitioned/conflicting markieren Sonderfälle.“

`conflicting` kann nie in `mps.aw_match` stehen. Die Registry entfernt bei zwei Treffern die Profil-ID, und `upsert_mp` schreibt `aw_match` nur bei gültiger ID:

- R:410-411 `out.update(trusted_aw_ids=sorted(trusted), aw_match=AW_CONFLICT)` / `out.pop("aw_politician_id", None)`
- P:754 `clean(aw_match) if isinstance(aw_politician_id, int) else None`
- R:490 gleiches für gesperrte Partitionen: `evidence.update(aw_politician_id=None, aw_match=PARTITIONED, profile_url=None)`; nur der Profilinhaber einer Partition behält `partitioned` samt ID (R:190-194 setzt `aw_match` und `profile_blocked = owner != profile_owner`).

Eigener Test (In-Memory, zwei `upsert_mp` mit `xml:7` und aw-IDs 111/222, beide `ext_id`): `person_records.evidence_json` enthält `"aw_match": "conflicting"`, `mps` hat `aw_politician_id = NULL, aw_match = NULL`. Referenz: `ext_id` 933, `name` 91, `partitioned` 1, sonst NULL (3273).

Vorschlag: „Art des abgeordnetenwatch-Abgleichs: ext_id (über die Redner-ID gefunden) oder name (über den Namen gefunden); partitioned markiert den Profilinhaber einer geprüften Aufteilung. NULL ohne Profil, auch wenn die Registry ein Profil als widersprüchlich oder gesperrt behandelt.“

### F2. `facts.baseline_kind.unit`, `facts.baseline_count.unit`, `facts.baseline_label.unit` (hoch)

Texte: „…; NULL ohne Vergleichsbasis.“ (kind), „…oder NULL ohne Vergleichsbasis.“ (count, label)

Der Writer setzt alle drei für jede Beobachtung mit Wert, auch bei leerer Vergleichsbasis; NULL nur ohne Beobachtung:

- F:1359 `return Baseline(kind="all", entries=tuple(prior))` (leeres `prior` ergibt kind `all`, count 0)
- F:1746-1750 `"baseline_kind": base.kind, "baseline_count": base.count, … "baseline_label": baseline_label(base, period, starts)` im Block `if observation is not None`
- `baseline_from`/`baseline_to` sind dann NULL (F:1748-1749), `percentile` NULL, `eligible` 0.

Referenz: 6 Zeilen `baseline_kind='all', baseline_count=0, baseline_label='seit Januar 2022', baseline_from/to NULL, percentile NULL, withheld='not_comparable'`; 236 Zeilen ohne Wert haben kind/count/label NULL.

Vorschläge:
- kind: „Textcode wp (eigene Wahlperiode) oder all (gesamte Abdeckung); ohne frühere Perioden steht all; NULL nur, wenn die Beobachtung keinen Wert hat.“
- count: „Anzahl historischer Beobachtungen als Ganzzahl (0 ohne frühere Perioden); NULL nur, wenn die Beobachtung keinen Wert hat.“
- label: „Anzeigetext des Vergleichszeitraums; NULL nur, wenn die Beobachtung keinen Wert hat.“

### F3. `fact_sources.rede_id.unit` (hoch)

Text: „Protokollinterne Rede-/Markerkennung als Text; synthetische Kennungen sind möglich; NULL, wenn der Beleg keine Rede ist.“

Synthetische Kennungen werden nie geschrieben; stattdessen NULL und Seitenanker:

- F:1489 `rede_id=None if synthetic else row["rede_id"],` (zusammen mit `page=row.get("page") if synthetic else None`, F:1490-1491)
- F:1453-1456 `is_synthetic_rede_id`: `not rede_id or str(rede_id).startswith(f"{protocol_id}{SYNTHETIC_REDE_ID_SEPARATOR}")`

Damit ist auch „NULL, wenn der Beleg keine Rede ist“ unvollständig (NULL auch bei Reden ohne Quellkennung). Referenz: 0 synthetische Kennungen in `speeches`/`fact_sources` (Code-Befund, nicht Datenbefund).

Vorschlag: „Protokollinterne Rede-Kennung als Text; NULL, wenn der Beleg keine Rede ist oder die Rede keine Quellkennung hat (dann nennen page und page_quadrant die Belegstelle, soweit bekannt); synthetische Kennungen stehen hier nie.“

### F4. Herkunft der Abstimmungsdaten: „XLSX“ (hoch)

Betroffene `source`-Texte:
- `vote_fractions.vote_id`, `.party_id`: „Bundestags-XLSX der namentlichen Abstimmung: die Stimmen der MdB werden je Zusammenschluss summiert.“
- `vote_members.vote_id`, `.mp_id`, `.party_id`, `.vote`: „Bundestags-XLSX der namentlichen Abstimmung: veröffentlichtes Einzelvotum und Mitgliederangabe.“
- `votes.id, date, topic, title, description, detail_url, yes_count, no_count, abstain_count, absent_count, xlsx_url, debate_url`: „…(Detailseite/XLSX)…“
- `votes.result_raw, result_source, result_scope, inverted, inversion_source, inversion_excerpt, context_state`: „…aus der Bundestags-Abstimmungsseite/XLSX…“

Die XLSX-Datei wird nie geladen oder gelesen; nur ihr Link wird von der Namenslisten-Seite gescrapt:

- V:2429 `enriched_vote["fractions"] = parse_fraction_votes(detail_html)` (Diagramm-Werte `data-chart-values` je Fraktion, nicht aus Einzelstimmen summiert)
- V:2423 `member_html = fetch_html(f"{BT_BASE_URL}/apps/na/namensliste.form?id=…&ajax=true")` und V:2430 `parse_member_votes(member_html)` (HTML-Namensliste)
- V:2205-2217 (`parse_roll_call_list_page`): `id`, `date`, `topic`, `title`, `description`, `total` aus der Listenseite
- V:2062/2116 nur `_NAMENSLISTEN_XLSX_RE = re.compile(r'href="([^"]+\.xlsx)"')` für `xlsx_url`; weder `openpyxl` noch `zipfile` kommt in V, B oder P vor.
- Bestätigt durch TODOS.md „Take namentliche Abstimmungen from the official XLSX instead of the chart markup“ (heutiger Ingest liest bundestag.de-HTML).

Vorschläge:
- vote_fractions.vote_id/party_id source: „bundestag.de, Detailseite der namentlichen Abstimmung: Ja/Nein/Enthaltung/nicht abgegeben je Fraktion oder Gruppe aus den Diagrammwerten der Seite; die Zahlen werden nicht aus Einzelstimmen gebildet.“
- vote_members.* source: „bundestag.de, Namensliste der namentlichen Abstimmung (HTML-Liste, nicht die XLSX-Datei): Name, Fraktion und Einzelvotum je Mitglied.“
- votes.* (Detailseite/XLSX): „Bundestagsquelle zur namentlichen Abstimmung (Abstimmungsliste und Detailseite bundestag.de); abgeleitete Werte werden gesondert als Projektregel bezeichnet.“
- votes.xlsx_url source: „Namenslisten-Seite bundestag.de; der Link wird über Datum und Titel der Abstimmung zugeordnet, die Datei selbst wird nicht gelesen.“
- votes.result_* / inverted* / context_state: „…aus der Bundestags-Abstimmungsseite und – für Vorgangskontext – …“ (ohne „/XLSX“).

### F5. `docs/data-methods.md`, Absatz „Abdeckung und bekannte Grenzen“, letzter Satz (hoch)

Text: „Die Zuordnung von Abstimmungs-XLSX-Ergebnissen zu den im Protokoll gedruckten Endergebnissen ist laut `docs/adr/0003-licences-and-impressum.md` weiterhin offene Prüffrage; die mögliche Weitergabe der Bundestags-XLSX-Stimmenlisten bleibt laut Frage 5 derselben ADR und TODO „Settle the roll-call source for redistribution“ ebenfalls ungeklärt.“

Der Store enthält keine aus XLSX gelesenen Ergebnisse oder Stimmenlisten (siehe F4). ADR 0003 spricht in Frage 5 vom „bundestag.de roll-call scrape“ (Z. 117) und fragt, ob Nichtabstimmende auch im Protokoll stehen „or only in the XLSX“ (Z. 129); eine „Zuordnung von XLSX-Ergebnissen zu Protokoll-Endergebnissen“ steht dort nicht.

Vorschlag: „Ob die Weitergabe der von bundestag.de gelesenen namentlichen Stimmenlisten (Abstimmungsseiten, nicht die XLSX-Dateien) durch die Protokollgrundlage gedeckt ist, bleibt laut Frage 5 der ADR `docs/adr/0003-licences-and-impressum.md` und TODO „Settle the roll-call source for redistribution“ ungeklärt; `votes.xlsx_url` verweist nur auf die Bundestags-XLSX.“

### F6. `proceeding_positions.title.meaning` und `.unit` (hoch)

Texte: meaning „Titel des Dokuments bzw. der Aktivität, die diese DIP-Position im Vorgang beschreibt.“, unit „Positions-/Dokumenttitel als Text oder NULL.“

Der Wert ist der Vorgangstitel und fließt aus demselben DIP-Feld in `proceedings.title`:

- P:1052 und P:1094 `clean(position.get("titel"))` (einmal für `proceedings.title`, einmal für `proceeding_positions.title`)
- V:1316-1332 `compact_position`: `"titel": position.get("titel")`

Referenz: 3879 von 3879 Positionen haben `title = proceedings.title` des Vorgangs (z. B. „Haushaltsbegleitgesetz 2027“, `position_type` „1. Beratung“); alle `document_kind = 'Plenarprotokoll'`.

Vorschlag meaning: „Vorgangstitel laut DIP-Positionsdatensatz (derselbe DIP-Wert fließt in proceedings.title ein).“ unit: „Vorgangstitel als Text oder NULL.“

### F7. `proceeding_positions.document_number.unit` (hoch)

Text: „Drucksachennummer als Text oder NULL.“

Die Positionen stammen aus `/vorgangsposition?f.plenarprotokoll=<id>` (V:3161) und `document_number` ist die Fundstelle im Plenarprotokoll (P:1097 `clean(source.get("dokumentnummer"))`). Referenz: 3879 von 3879 Zeilen tragen Plenarprotokollnummern (z. B. `21/91`), `document_kind` immer `Plenarprotokoll`. (Das `meaning` „Drucksachen- oder Protokollnummer“ ist zutreffend, die Einheit nicht.)

Vorschlag: „Plenarprotokollnummer der Fundstelle als Text, z. B. 21/91, oder NULL.“

### F8. `proceedings.sachgebiet.meaning` (hoch)

Text: „…; NULL ohne Cacheeintrag, leere JSON-Liste bei bekanntem Vorgang ohne Sachgebiet.“

Nur Vorgänge, die über eine Position eines gespeicherten TOPs eingefügt werden, bekommen die Liste aus dem Cache (P:1038 `sachgebiet = None if record is None else dumps(record.get("sachgebiet") or [])`). Vorgänge, die nur über eine Abstimmung oder eine verknüpfte Drucksache in den Store kommen, bleiben NULL, auch wenn der Cache sie kennt:

- P:1001 `INSERT OR IGNORE INTO proceedings(id, created_at, updated_at)` (verknüpfte Drucksache, auch Mitberatung)
- P:1518 `INSERT INTO proceedings(id, title, abstract, created_at, updated_at)` (`persist_vote_context`, schreibt `records.get(proceeding_id)` nur für title/abstract, nie sachgebiet)

Referenz: 56 von 3111 `proceedings` mit `sachgebiet` NULL (dieselben 56 haben `proceeding_type` NULL, also ohne Position).

Vorschlag: „Unveränderte DIP-Sachgebietsliste aus dem zwischengespeicherten Vorgang, nur für Vorgänge mit einer Position in einem gespeicherten Tagesordnungspunkt; leere JSON-Liste, wenn der Cache für diesen Vorgang kein Sachgebiet hat; NULL, wenn der Vorgang nicht im Cache steht oder nur über eine Abstimmung oder eine verknüpfte Drucksache in den Store kam.“

### F9. `protocols.title.meaning` und `protocols.date.source` (mittel, Wortlaut hoch)

- `protocols.title.meaning`: „Offizieller Titel/name der Plenarsitzung aus DIP-Protokolldatensatz **und Protokollkopf**.“ Nur DIP: V:3612 `"titel": protocol.get("titel")`, P:881 `clean(protocol.get("titel"))`. Der Protokollkopf geht nur in `xml_header_json` (V:3616 `"xml_header": parsed_xml["xml_protocol"]`).
- `protocols.date.source`: „DIP-Katalogdatum der Sitzung; **Protokollkopf im XML ist Gegenprüfung.**“ Das XML-Datum (`sitzung_datum`, V:1245) wird nirgends verglichen (grep in scripts/ und scripts/features/ ohne weiteren Treffer); `check_xml_belongs_to_report` prüft nur Wahlperiode und Sitzungsnummer (V:3041-3045).

Vorschläge:
- title.meaning: „Offizieller Titel der Plenarsitzung aus dem DIP-Protokolldatensatz.“
- date.source: „DIP-Katalogdatum der Sitzung; der Protokollkopf im XML steht separat in xml_header_json, sein Datum wird nicht mit diesem Feld abgeglichen (geprüft werden nur Wahlperiode und Sitzungsnummer).“

### F10. NULL-Aussagen, die der Writer nie erfüllt: `votes.protocol_id.meaning`, `proceeding_positions.agenda_item_id.meaning` (hoch bzw. mittel)

- `votes.protocol_id`: „…; NULL, wenn nicht belegt.“ `persist_vote` bekommt die Protokollkennung immer vom Report (P:1265 `persist_vote`, Aufruf P:1612 `persist_vote(conn, vote, agenda_item_id, protocol_id, now)`), `persist_report` bricht ohne Kennung ab (P:1578 `raise ValueError("Report has no protocol.id")`); `DELETE FROM protocols` gibt es nirgends, `ON DELETE SET NULL` greift also nie. Referenz: 0 von 217 NULL. (hoch)
- `proceeding_positions.agenda_item_id`: „…; NULL, wenn nicht verknüpft.“ `persist_positions` setzt immer die Kennung des TOPs (P:1091 `agenda_item_id,` im INSERT). NULL entstünde nur über `ON DELETE SET NULL` aus `replace_protocol` (P:858 `DELETE FROM agenda_items WHERE protocol_id = ?`), also nur beim erneuten Speichern desselben Protokolls im selben Store; jeder speichernde Build startet mit frischem Store und speichert jedes Protokoll einmal. Referenz: 0 von 3879 NULL. (mittel)

Vorschläge:
- votes.protocol_id: „Kennung des Plenarprotokolls, in dem die Abstimmung stattfand; wird beim Speichern immer gesetzt.“
- proceeding_positions.agenda_item_id: „Kennung des Tagesordnungspunkts, auf dem diese Vorgangsposition behandelt wurde; wird beim Speichern immer gesetzt.“

### F11. Rezept `r1-meiste-reden`: `caveat` (hoch)

Text: „Mitglieder der Bundesregierung, Bundesratsmitglieder und weitere Redner in einer Sprechrolle erscheinen ohne Fraktion.“

Das Label kommt aus der repräsentativen Aufzeichnung, nicht aus der Rede (B:2819 `LEFT JOIN parties p ON p.id = m.party_id`, `m` = `representative`, B:2785 `ORDER BY is_mdb DESC, xml_redner_id IS NULL, identity_key`). Trägt die Aufzeichnung eine Zugehörigkeit (`party_id = COALESCE(excluded.party_id, mps.party_id)`, P:726), erscheint die Person mit Fraktion. Die eigene `method` räumt das ein („kann es deren Fraktion zeigen, auch für Reden in einer Sprechrolle“), der Caveat widerspricht ihr.

Referenz (Näherung über `speeches.fraktion IS NULL`, da `sprechrolle` fehlt): 78 von 146 Personen mit mindestens einer Rede ohne `fraktion` tragen auf ihrer mps-Zeile eine Partei, z. B. Baerbock (44 Reden, BÜNDNIS 90/DIE GRÜNEN), Lauterbach (44, SPD), Buschmann (43, FDP), Habeck (42), Scholz (37, SPD).

Vorschlag: „Reden in einer Sprechrolle (Bundesregierung, Bundesrat, weitere) zählen für die Person; das Fraktionslabel kommt aus der repräsentativen Aufzeichnung und fehlt nur, wenn diese keine Zugehörigkeit trägt.“

### F12. `mps.is_mdb.meaning`, `mps.title.unit`, `mps.dip_person_id.meaning/source`: „Roster“ (mittel)

Neben dem MdB-Kader schreibt `persist_sampled_people` (P:892-918) jede in den Aktivitäten einer Sitzung genannte DIP-Person (V:3511 `"sampled_people": [compact_person(person) …]`) mit `dip_person_id`, `title`, `function`, `wahlperiode`, aber ohne `is_mdb` (Default P:678 `is_mdb: bool = False`, P:756 `1 if is_mdb else 0`). Den Wert 1 setzen nur `ingest_mdb_roster` (B:8019, eine Wahlperiode, `--roster-wahlperiode`, Standard 21, B:12582-12585) und der Wiederaufbau gespeicherter Kaderzeilen (B:1365).

- `is_mdb.meaning`: „1, wenn eine DIP-Funktionsangabe der Person genau „MdB“ lautet…; sonst 0.“ Eine genannte DIP-Person mit Funktion `['MdB']` außerhalb des geladenen Kaders hat 0.
- `title.unit`: „…; NULL ohne DIP-Rostereintrag.“ Auch Regierungs- und Bundesratsmitglieder tragen die DIP-Titelzeile. Referenz: 107 Aufzeichnungen mit `dip_person_id` und Funktion ohne MdB, z. B. „Bärbel Bas, Bundesmin., Bundesministerium für Arbeit und Soziales“ (`['Bundesmin.']`); insgesamt 1061 Aufzeichnungen mit DIP-Titel, davon 914 mit `['MdB']` und `is_mdb = 0` (Referenz ohne Kader, nur als Beleg, dass das Schreiben ohne Kader möglich ist).
- `dip_person_id.meaning/source`: „…dem Abgeordneten-Roster-Eintrag zuweist.“ / „DIP-API-Rosterkennung der Person.“ gilt auch für diese Personen.
- (Verwandt, Auslassung: `mps` meaning „aus Abgeordnetenroster und Protokollrednern“ nennt weder genannte DIP-Personen noch Abstimmungsmitglieder.)

Vorschläge:
- is_mdb.meaning: „1 für Aufzeichnungen aus dem geladenen MdB-Kader (DIP-Roster einer Wahlperiode), deren DIP-Funktionsangabe genau „MdB“ lautet (derive.is_mdb_funktion; MdBR und Stellv. MdBR zählen nicht); sonst 0, auch für in einer Sitzung genannte DIP-Personen mit Funktion MdB, die nicht im geladenen Kader stehen. DIP nennt nur das aktuelle Amt, ein MdB in einem Regierungsamt kann 0 haben.“
- title.unit: „Titelzeile als Text, z. B. 'Marc Bernhard, MdB, AfD'; NULL ohne DIP-Personeneintrag (MdB-Kader oder in einer Sitzung genannte DIP-Person).“
- dip_person_id.meaning: „Personenkennung, die DIP der Person zuweist (MdB-Kader oder in einer Sitzung genannte DIP-Person, auch Regierungs- und Bundesratsmitglieder).“ source: „DIP-API: Personenkennung aus dem MdB-Kader oder den in einer Sitzung genannten Personen.“

### F13. `documents.herausgeber.source` (und `document_number.source`, `url.source`) (mittel)

Text: „DIP-API: herausgeber aus dem Vorgangs-/Dokumentdatensatz; …“ (ebenso `document_number`, `url`).

Für Nummern, die nur das Protokoll-XML oder eine Abstimmungsliste nennt, gibt es keinen DIP-Datensatz: P:966-970 `upsert_document(… document_number=doc.get("dokumentnummer"), url=doc.get("url"))` (XML) und P:1363 `upsert_document(conn, now=now, document_number=number)` (Abstimmung) ohne `herausgeber`; `document_issuer` setzt dann BT oder, bei `/brd/`-Pfad, BR (S:105-116 „A number with neither (an XML anchor without a link, a roll-call document number) is a Bundestag Drucksache.“). Referenz: 1244 von 8117 `documents` ohne `document_type`, `date`, `title` (nur Nummer und gegebenenfalls XML-URL).

Vorschlag herausgeber.source: „DIP-API: herausgeber des Dokuments; für Nummern, die nur das Protokoll-XML oder eine Abstimmungsliste nennt, aus dem URL-Pfad (/brd/ ergibt BR), sonst als BT gesetzt.“ document_number/url.source analog: „…; für nur im Protokoll-XML oder in einer Abstimmungsliste genannte Drucksachen aus dieser Quelle.“

### F14. `documents.document_type.meaning` und `.unit` (hoch)

Texte: „DIP-Dokumenttyp, etwa Drucksache oder Beschlussempfehlung.“ / „DIP-Dokumentart als Text/Code.“

Der Wert ist der Drucksachentyp (`fundstelle.drucksachetyp`, V:1383 `"drucksachetyp": fundstelle.get("drucksachetyp")`, P:987 `document_type=doc.get("drucksachetyp")`). „Drucksache“ ist die DIP-Dokumentart, die alle diese Dokumente teilen (V:3208 `position.get("dokumentart") == "Drucksache"`), und kommt als `document_type` nie vor. Referenz: 0 von 8117 mit `document_type = 'Drucksache'`; Werte u. a. Antrag 1511, Beschlussempfehlung und Bericht 1077, Gesetzentwurf 950; 1244 NULL.

Vorschlag: meaning „Drucksachentyp laut DIP, etwa Antrag, Gesetzentwurf oder Beschlussempfehlung; NULL bei nur aus Protokoll-XML oder Abstimmungsliste bekannten Nummern.“ unit „DIP-Drucksachentyp als Text.“

### F15. `facts.value.meaning` (mittel)

Text: „Von der Kennzahl-SQL berechneter Beobachtungswert…“

Nur bei Aggregation `extreme` ist es der Wert der SQL-Zeile. Bei `count` und `grouped_extreme` rechnet `observe()` in Python: F:1236-1243 `value=float(len(ordered))` (erste-reden), `_observe_grouped_extreme` summiert `value` je `group_id` über die Periode (F:1256ff., die zwei Monatskennzahlen). Verwandt, schwächer: `fact_metrics.sql.meaning` „SQL-Abfrage, die die Kennzahl … berechnet“; die SQL liefert Kandidatenzeilen (F:1198-1209 `candidate_rows`).

Vorschlag: „Beobachtungswert in der fachlichen Einheit aus fact_metrics.unit: bei Extremwert-Kennzahlen der Wert der gewählten Zeile der Kennzahl-SQL, bei Zähl- und Gruppenkennzahlen die in scripts/facts.py aus den Zeilen der Kennzahl-SQL gezählte bzw. je Gruppe summierte Zahl.“

### F16. `facts.wahlperiode.meaning` (mittel)

Text: „Wahlperiodennummer, deren historische Vergleichsbasis bei dieser Beobachtung verwendet wird.“

Der Wert ist immer die Wahlperiode der Periode (F:1713 `"wahlperiode": period.wahlperiode`, bei Monaten die der meisten Sitzungen, F:852-908), auch ohne Beobachtung und bei `baseline_kind = 'all'`, wo die Basis alle Wahlperioden umfasst (F:1359 `Baseline(kind="all", entries=tuple(prior))`). Referenz: 88 Zeilen mit `baseline_kind='all'` und Wert.

Vorschlag: „Wahlperiode der Periode (bei Monaten die der meisten Sitzungen). Nur bei baseline_kind = wp ist es die Wahlperiode der Vergleichsbasis.“

### F17. `mps.aw_politician_id.meaning` (niedrig)

Text: „…Profilattribut, kein eigenständiger projektweiter Identitätsbeweis.“

Bei Treffern über die Redner-ID ist sie der Identitätsschlüssel: P:631-653 `mp_identity`: `if aw_politician_id and aw_match == derive.TRUSTED_AW_MATCH: return f"aw:{aw_politician_id}"`; D:329 nennt diese ID „a Personenkennung“.

Vorschlag: „Politikerkennung des abgeordnetenwatch-Profils; bei Treffern über die Redner-ID (aw_match = ext_id) dient sie als Identitätsschlüssel (identity_key aw:<id>), bei Namenstreffern nur als Hinweis.“

### F18. `agenda_items.page_start.source`, `.page_end.source` (niedrig, widerspricht dem eigenen meaning)

Text: „Plenarprotokoll-XML: Seitenmarkierung am Anfang/Ende des Tagesordnungspunkts.“

Geschrieben wird die kleinste/größte Seite der Seitenverweise der Reden des TOPs aus dem Inhaltsverzeichnis: V:1217 `sorted_pages = sorted(pages, key=page_sort_key)`, V:1228-1229 `"start": sorted_pages[0] …, "end": sorted_pages[-1]` mit `pages.append(page_ref)` je Rede (V:1140) und `rid_pages` aus `parse_toc` (V:604-608 `xref`). Eine Seitenmarkierung am TOP-Anfang wird nicht gelesen. Das `meaning` beschreibt es richtig.

Vorschlag: „Plenarprotokoll-XML: Seitenverweise der Reden dieses TOPs im Inhaltsverzeichnis; kleinste (page_start) bzw. größte (page_end) Seite.“ (Quadranten analog: „Quadrant dieser Seite“.)

### F19. `votes.inversion_excerpt.unit` (niedrig)

Text: „Kurzer wörtlicher Belegausschnitt als Text oder NULL.“

- Protokollbeleg: `clamp_text(clause, 300)` (V:1584), Leerraum normalisiert, bei Überlänge „…“ angehängt (V:479-483).
- Textbeleg: das ganze Feld Titel/Beschreibung/Überschrift der Abstimmung oder der DIP-Drucksachentitel (`rejection = (source, text)` V:1663, `return "reject", rejection[0], rejection[1]` V:1665), ungekürzt; die Felder der Kopien einer Abstimmung werden vorher mit `"\n"` verbunden (V:1791), `clean` (P:101) macht daraus Leerzeichen.

Vorschlag: „Belegausschnitt als Text oder NULL: bei Protokollbeleg die Klausel der Ansage des Sitzungsleiters (Leerraum normalisiert, auf 300 Zeichen mit „…“ gekürzt), sonst der Text des Titels, der Beschreibung oder des DIP-Drucksachentitels, der die Ablehnungsempfehlung enthält.“

### F20. `votes.context_state.unit` (niedrig, „oder NULL“)

Text: „Projektstatuscode für Kontextzuordnung oder NULL.“

`persist_vote_context` setzt den Status für jede gespeicherte Abstimmung (P:1531 `UPDATE votes SET context_state = ? WHERE id = ?` in der Schleife über alle `iter_report_votes`), Werte per CHECK genau `resolved`, `none`, `not_fetched` (P:346). Referenz: 217 von 217 `resolved`, 0 NULL.

Vorschlag: „Textcode resolved, none oder not_fetched; wird für jede gespeicherte Abstimmung gesetzt.“

---

## 2. Checked, true (Klassen: 1 NULL, 2 Herkunft/Normalisierung, 3 Zeitpunkte, 4 Wertemengen/Einheiten, 5 Rezepte, 6 data-methods)

- **agenda_item_documents**: 2, 4 (`source` xml/api, `proceeding_id`/`proceeding_position_id` NULL bei xml; Referenz 4699 xml mit beiden NULL).
- **agenda_item_politikfelder / vote_politikfelder**: 4 (13 Felder + `untagged`, höchstens 3, `source`-Werte je Tabelle: Items sachgebiet/drucksache/einzelplan/einzelplan_unknown/untagged/not_fetched, Abstimmungen drucksache/top/not_fetched/untagged; `tags_for_agenda_item`, `tags_for_vote`), Rangregel `_union`.
- **agenda_item_votes, vote_documents, vote_proceedings, vote_passages**: 2, 4 (rank-Semantik, `vote_passages` nimmt alle Kandidaten, zitiert wird nur `extracted`); Herkunftsangaben ohne „XLSX“ stimmen (zu vote_documents siehe „Nicht verifizierbar“).
- **agenda_items**: 1 (`heading`, `page_*` NULL: Referenz 162/488), 3 (`created_at` = `updated_at`, P:858/P:925-950 `INSERT … now, now`), 4 (Quadrant A–D oder NULL, `item_index` ab 1). `top_id` siehe „Nicht verifizierbar“.
- **contributions**: 1 (`agenda_item_id` NULL bei unsicherer Zuordnung: Referenz 301 `zu_protokoll`; `rede_id` NULL genau bei Fragestunde: 2687+2701 und sonst 0; `mp_id`/`speaker_name`/`fraktion` NULL), 2 (Whitespace-Normalisierung, `char_count = len(text)`, `fraktion` über `derive.speech_zusammenschluss` mit Gruppe-Die-Linke-Regel ab 2023-12-06), 3 (created_at = updated_at, Sitzung wird gelöscht und neu geschrieben, `--repersist` behält Store über `keep_if_unchanged`), 4 (`sprechrolle` bundesregierung/bundesrat/weitere, `kind` aus `speech_kinds`).
- **datenstand**: 2, 4 (`schema_hash` = SHA-256 über sortierte CREATE-Anweisungen nach `mp_canonical`, vor `datenstand`, B:3822; `tag` Standard `local`; `export_format` = `EXPORT_FORMAT`; `source_sha256` der Build-Store-Datei, kann aus Vormanifest wiederverwendet werden, wenn mtime/Größe gleich).
- **documents**: 1 (`url` leerer Text, `forderung`/`forderung_state`/`forderung_version` NULL für nie geprüft, `date` kann fehlen), 2 (`forderung`: Layout entfernt, Wortlaut, Absätze mit Leerzeile, `antrag_text.Forderung.text`), 3 (`created_at` neu je speicherndem Build, `updated_at` bei erneutem Upsert), 4 (`forderung_state` extracted/no_passage/not_fetched, Referenz-Datum ISO). Falsch nur F13, F14.
- **fact_metrics**: 1, 4 (`depends_on` votes oder NULL, `caveat` NULL bei 5 von 8, `unit`-Beispiele existieren, `min_history_weeks`, `sql_sha256` = SHA-256 des SQL-Textes). `sql` siehe F15.
- **fact_sources**: 1 (`document_number` nie NULL: Metrik-SQL und `documents.document_number` NOT NULL), 4 (`entity_kind` speech/document/agenda_item/vote/protocol; Referenz 161 agenda_item, 95 protocol, 1282 speech). `rede_id` siehe F3.
- **facts**: 1 (`iso_year`/`iso_week` NULL bei month, `week_n` NULL nur bei `complete = 0`, sonst 0 oder Anzahl, `rank` nur veröffentlichbar, `withheld` NULL nur bei `publishable`, `denominator`), 4 (`percentile` strikt übertroffener Anteil F:1302-1311, `period_key`-Formate, `eligible`, `baseline_kind`-Werte wp/all). Falsch nur F2, F15, F16.
- **mp_canonical**: 2, 4 (`mp_id` → `mps.id`, `canonical_id` aus `mps.person_id`, `has_page` 0/1, B:3801-3810).
- **mps**: 1 (`person_roles_json` nur bei Roster-Zeilen: Sampled-Personen übergeben es nie), 2 (`function`/`wahlperiode` als Python-Literal, `person_roles_json` als JSON, `display_name`-Repräsentant durch `_fold`/`_representative_pair`, `profile_url` über `derive.member_profile_url`), 3 (`created_at`/`updated_at`: staged frischer Store, `now` je `persist_report`), 4 (`is_mdb` 0/1, `aw_politician_id` Ganzzahl). Falsch nur F1, F12, F17.
- **parties**: 2, 3 (`name` über `derive.zusammenschluss`; `created_at`, `updated_at` per Upsert P:605-619). „Parserfehler“ siehe „Nicht verifizierbar“.
- **person_aliases, person_bindings, person_records, persons**: 1, 4 (`partition` NULL ohne Partition, `ordinal` fortlaufend, `id` URL-tauglich `valid_person_key`, R:233-248).
- **proceeding_positions**: 1 (`page` immer NULL in Referenz, sonst Text), 4 (`page_start`/`page_end` TEXT aus Ziffern: Referenz 0 Abweichungen, `typeof` text), 2 (`id` = DIP-ID per `clean`). Falsch nur F6, F7, F10.
- **proceedings**: 1 (`title`/`proceeding_type` NULL möglich), 2 (`abstract`: HTML bereinigt, Absätze mit Leerzeile, `dip_text.abstract_text`). Falsch nur F8.
- **protocols**: 1 (`title`, `verteildatum` NULL möglich), 2 (`xml_header_json` als JSON des XML-Kopfes), 3, 4 (`date` ISO). Falsch nur F9.
- **schema_migrations**: 3, 4 (`applied_at` P:442, `INSERT OR IGNORE` im frischen Store).
- **speech_rule_inputs**: 2, 4 (`version` = `speech_kinds_version`, P:1585).
- **speeches**: 1 (`mp_id` nie NULL: `resolve_speaker` liefert immer eine Record-ID, Referenz 0 NULL; `unattributed_char_count` NULL nur für alte Berichte, P:1190-1194), 2 (`text`/`snippet`: `clean_text`, erste 240 Zeichen V:1150; `fraktion` wie bei contributions; `rede_id` synthetisch `<protocol_id>:<item_index>:<sequence>`, S:52), 3, 4 (`sprechrolle`-Werte, `page_quadrant` A–D oder NULL, `sequence` ab 1).
- **vote_fractions**: 1, 4 (`leading_vote` = `derive.majority_vote`: Gleichstand/keine Stimmen NULL; `total_count` inkl. nicht abgegebener); Herkunft siehe F4.
- **vote_members**: 1 (`party_id` immer gesetzt, sonst „Unbekannt“: P:1414 `derive.zusammenschluss(member.get("faction")) or "Unbekannt"`; Referenz 0 NULL), 4 (`vote` yes/no/abstain/absent, Referenz genau diese 4); Herkunft siehe F4.
- **votes**: 1 (`inverted` 1 oder NULL, nie 0: `recommendation_inversion` liefert nur True/None; `result_*` NULL bei Sonderverfahren/0:0; `xlsx_url` NULL), 2, 3, 4 (`result_source` official/derived, `result_scope` application/proposition, `procedure_type` vier Codes aus `special_majority_procedure`, `passage_state`/`context_state`-Semantik gegen `antrag_text.vote_passages` und `politikfelder.vote_vorgang_ids`). Falsch nur F4 (Herkunft), F10, F19, F20.
- **Rezepte**: r1 (SQL, Sortierung, Spalten bis auf Caveat F11), r2 (Nenner, Gruppierung, Sortierung, Caveat; die Klausel „Reden ohne Redneraufzeichnung fehlen“ ist leer, nie erfüllt, aber nicht falsch), r3 (Zählregel, Join auf `vote_fractions`, Ausschlüsse, Sortierung), r4 (Datum, Sortierung, Abstimmungen ohne TOP), r5 (alle Spalten, Projektionsreihenfolge), r6 (Typ-Filter `LIKE 'Beschlussempfehlung%'`, nur BT, Sortierung, Caveat). Ausgenommen wie beauftragt: TODOS „Recipe SQL disagrees…“.
- **docs/data-methods.md**: Aussagen zu `speeches` nur Reden, zu_protokoll (Anhang-Typ „zu Protokoll gegebene Reden“, V:933), Redentext whitespace-normalisiert und Absatzgrenzen weg (`paragraphs_json` entfällt, B:3799-3800), `paragraph_count` bleibt, Beiträge ohne `mp_id`, Schlüsselversion/Hashschlüssel (`stable_key`), `mps.id`/`persons.id`/`mp_canonical`/`person_aliases`, Manifest-Tags dip/bundestag.de/abgeordnetenwatch/derived (B:2710-2721), Abschnitt „Veröffentliche SQL-Rezepte“ existiert (B:3554), Abdeckungs-Tabelle ausschließlich aus der SQLite-Datei, leerer Store (`_codebook_coverage`), kein Erwerbsstatus im Store, `CITATION.cff` fehlt. Falsch nur F5.
- **Zeitpunkte (Klasse 3), neu verifiziert**: `now = utc_now()` je `persist_report` (P:1573); jeder speichernde Build stagt einen frischen Store (B:1216 `_staged_store_path`, `registry.copy_previous` kopiert nur Registry-Tabellen); `--repersist` verwirft den Neuaufbau, wenn `_same_content` gleich ist (B:1393, `_content_digests` ohne `created_at`/`updated_at`/`applied_at`, B:1134-1171). Die vorhandenen created_at/updated_at-Texte sind damit wahr, auch „daher gleich updated_at“ für agenda_items, speeches, contributions.

---

## 3. Could not verify

- **`agenda_items.top_id.unit` „nicht NULL“**: Der Writer hat keine Absicherung (`top.attrib.get("top-id")` V:1221; `clean()` macht leeren Text zu NULL; `top_format` toleriert fehlendes `top_id`, speech_kinds.py:127-139). Ob das XML das Attribut immer führt, ist hier nicht prüfbar; Referenz 0 von 2912 NULL.
- **Quadrant „vereinzelt Parserreste wie 'S' oder '4038'“** (`agenda_items.page_*_quadrant`, `speeches.page_quadrant`) und **`parties.name` „Parserfehler… 'Bremen'“**: Der Quadrant ist das rohe XML-Attribut (V:604 `xref.attrib.get("div")`), `zusammenschluss` lässt unbekannte Namen durch (derive.py:~115-125); die Referenz zeigt aber nur A–D und nur die zehn bekannten Zusammenschlüsse. Der Text kann für ältere Stores gestimmt haben.
- **`vote_members.vote` „unknown als Fallback“**: P:1439 `clean(member.get("vote")) or "unknown"` existiert, aber `parse_member_votes` verwirft Mitglieder ohne Votum-Element (V:2332 `if not name_match or not faction_match or not vote_match: continue`), also entsteht `unknown` aus dem heutigen Parser nie. Umgekehrt reicht der Parser unbekannte Klassen unverändert durch (V:2345 `.get(vote_match.group(1), vote_match.group(1))`, etwa ein `ungueltig`); die Wertemenge yes/no/abstain/absent/unknown ist damit nicht zwingend vollständig. Referenz: nur die vier Werte.
- **`votes.result_raw.meaning` „NULL, wenn das Verfahren ohne Ergebnis bleibt“**: mehrdeutig. Der Writer schreibt NULL bei Sonderverfahren (Grundgesetzänderung, Vertrauensfrage, …) ohne amtliches Ergebnis und bei 0:0 (V:1440-1451), nicht nur bei Verfahren ohne Ergebnis.
- **`votes.result_scope.unit` „NULL nur in Zeilen aus Berichten, die vor Einführung des Felds gespeichert wurden“**: Beim Interpretieren wird der Wert immer gesetzt (V:1722, V:1820, `official_vote_result` liefert immer einen Scope). Ob ein Build alte zwischengespeicherte Berichte neu interpretiert, wurde nicht durchverfolgt.
- **`vote_documents.*.source` „Drucksachennummern“**: P verknüpft jede im Listenblock gefundene Nummer ohne `plausible_document_number`; Referenz: 1 von 512 Verknüpfungen auf `76/787` (Fragment). Datenmangel, kein Textfehler.
- **`proceedings.abstract` „Textinhalt erhalten“**: `dip_text.abstract_text` liest nur 10.000 Zeichen (`MAX_ABSTRACT_CHARS`) und verwirft `<script>`/`<style>`-Text; längster Abstract im Referenz-Cache 5111 Zeichen, also latent.
- **`contributions.fraktion` NULL-Gründe**: P:1224 schreibt `fraktion = None` für jeden Beitrag ohne Redner-ID (`else: mp_id, fraktion, sprechrolle = None, None, None`) (7 Fragestunde-Fragen in der Referenz), unabhängig davon, ob das Protokoll eine Fraktion nennt; ob es dort eine nennt, ist nicht prüfbar.
- **Spalten, die nach der Referenz entstanden sind** (`votes.result_*`, `procedure_type`, `passage_state`, `debate_url`, `documents.forderung*`, `speeches.sprechrolle`, `unattributed_char_count`): nur gegen den Code geprüft, keine Zahlen.
