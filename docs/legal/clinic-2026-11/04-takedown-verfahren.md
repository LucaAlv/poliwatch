# Verfahren bei Löschungs-, Widerspruchs- und Berichtigungsverlangen (Entwurf)

> Entwurf des Projekts, von der Clinic zu prüfen. Stand: 2026-11-22, Code auf `main` bei Version 0.46.43.0. Der Abschnitt „Was der Code heute tut“ beschreibt den Code, den der Verfasser gelesen hat. Der Abschnitt „Was fehlt“ nennt, was zwischen diesem Verfahren und dem Code noch nicht gebaut ist. Das Verfahren darf erst als zugesagt gelten, wenn es gebaut ist (siehe dort).

## Ziel

Auf begründetes Verlangen einer betroffenen Person wird **eine einzelne Rede** aus den Zählungen und aus dem veröffentlichten Text genommen, mit einem genannten Grund, so wie ADR 0005 (`docs/adr/0005-withhold-refused-reden.md`) Reden zurückhält, die der Parser nicht eindeutig lesen kann. Die Berichtigung erscheint im nächsten Datenstand („main“). Für eine bereits bei Zenodo archivierte „stable“-Fassung bittet der Betreiber Zenodo, sie nicht mehr öffentlich zu zeigen.

## Fälle

| Fall | Beispiel | Weg |
|---|---|---|
| A. Dritter in einer Rede genannt | Eine Privatperson verlangt, dass ihr Name und das, was ein Redner über sie sagt, nicht mehr im Datensatz steht (Art. 17, 21) | Prüfung nach unten; bei Erfolg die Rede zurückhalten |
| B. Redner oder anderer Abgeordneter zu seiner eigenen Rede | Widerspruch nach Art. 21 oder Löschung nach Art. 17 | derselbe Weg; Abwägung fällt wegen des öffentlichen Amtes und der Äußerung im Plenum in der Regel gegen die Löschung aus, ausgenommen Kernbereich Privatleben |
| C. Sachlicher Fehler (falsche Zuordnung, falscher Name, falsche Abstimmung) | Art. 16 | kein Löschverfahren: Berichtigung im nächsten Stand, bei veröffentlichtem Wert mit Eintrag unter `corrections` in `changes.json` (`docs/release-policy.md`) |
| D. Das Verlangen betrifft die Quelle, nicht das Projekt | Name im Plenarprotokoll selbst | Verweis an den Deutschen Bundestag (Quelle); das Projekt gibt nur wieder |

## Wer entscheidet, in welcher Zeit

- **Entscheidung:** der Betreiber allein (Privatperson, ADR 0003 D4). Es gibt keinen zweiten Prüfer. OFFEN: Soll der Betreiber bei Fall A und B eine zweite, sachkundige Stelle fragen (die Clinic oder die Landesdatenschutzbeauftragte)? Der Entwurf rät davon ab, jeden Fall vorzulegen, und empfiehlt es nur bei Art.-9- oder Art.-10-Bezug.
- **Eingang:** die E-Mail-Adresse des Impressums, die für „Berichtigungs- oder Löschwünsche betroffener Personen“ genannt ist (ADR 0003 D5; `impressum.html`). OFFEN: Die Adresse steht noch nicht fest; sie kommt mit der Betreiberdatei (ADR 0003, Änderung 2026-11-01).
- **Bestätigung des Eingangs:** innerhalb von sieben Tagen. OFFEN: Der Betreiber nimmt die Frist an oder ändert sie.
- **Entscheidung und Antwort an die Person:** unverzüglich, spätestens einen Monat nach Eingang. Das ist die Frist des Art. 12 Abs. 3 DSGVO (zwei Monate Verlängerung bei Komplexität möglich, mit Mitteilung). OFFEN: Der Verfasser hat Art. 12 nicht nachgelesen; die Clinic oder der Betreiber prüft den Wortlaut.
- **Wirkung in den Daten:** im nächsten Hauptdatenstand (main). Hauptdatenstände entstehen heute von Hand, später je Sitzungswoche (TODOS.md, „Scheduled data-release workflow“). OFFEN: Soll ein dringender Fall (Art.-9-/Art.-10-Bezug zu einem Privatmenschen) einen Datenstand außer der Reihe auslösen? Der Entwurf schlägt vor: ja, innerhalb von 14 Tagen nach Entscheidung.
- **Wirkung bei Zenodo:** nach der Entscheidung, in derselben Woche, sobald es eine archivierte Fassung gibt.

## Prüfung (Fälle A und B)

Der Betreiber hält die Gründe schriftlich fest. Kriterien: wer ist die Person (öffentliche Funktion oder Privatmensch); was steht über sie da und in welchem Zusammenhang (Plenardebatte, Sachbezug); ob besondere Kategorien (Art. 9) oder Straftaten (Art. 10) betroffen sind; was der Text für das Verständnis der Debatte beiträgt; ob der Name im Protokoll des Bundestages selbst weiter steht (die Quelle bleibt öffentlich); die Folgen der Zurückhaltung: die Rede fehlt in allen Zählungen und die Sitzung gilt für Reden als „unvollständig erfasst“ (ADR 0005, „Facts“).

Ablehnung: begründete Antwort mit Hinweis auf die Beschwerde bei der Aufsichtsbehörde (Art. 77 DSGVO; `datenschutz.html`, „Ihre Rechte“).

## Was der Code heute tut

Der Mechanismus ist die **geprüfte Liste** `scripts/reviewed_units.json` (Kind `withhold`, ADR 0005, „What is withheld“). Gelesen in `scripts/reviewed_units.py`, `scripts/validate_dip_protocol.py` (Zeile 2255 bis 2272), `scripts/persist_dip_pulse_store.py` (`persist_withheld`).

1. **Eintrag.** Ein Eintrag hat genau die Felder `sitting` (z. B. `18/29`), `rede_id` (die Kennung des `<rede>`-Elements im Protokoll oder eines vom Parser abgespaltenen Teils `<id>:<n>`), `redner_id` (die erste Redner-ID des Redners dieser Rede), `kind: "withhold"` und `reason` (freier Text, nicht leer). Der Eintrag nennt die **Rede und ihren Sprecher**, nicht die Person, die das Verlangen stellt. Passt der Eintrag nicht zur Sitzung, bricht der Lauf ab. Es gibt heute 15 Einträge dieser Art, alle für Reden, die der Parser sonst falsch einordnen würde.
2. **Wirkung beim Neuaufbau.** Der Parser nimmt die Rede aus `speeches` und `contributions` und schreibt sie mit Grund `reviewed` in `withheld_units`. Sie zählt nirgends mit: nicht als Rede, nicht als Beitrag, nicht für eine Person oder Fraktion. Die Sitzung behält ihre übrigen Reden, Tagesordnungspunkte, Drucksachenverweise und Abstimmungen. Die Website nennt je Tagesordnungspunkt Redner, Fraktion und Grundbezeichnung der zurückgehaltenen Reden, ohne den Text. Mit `--offline --repersist` liest der Betreiber die Sitzung neu aus dem zwischengespeicherten Protokoll-XML; ein Online-Lauf tut es von selbst. Ohne Neuaufbau verweigern Fakten, Export und Seiten einen Bestand, dessen Eintragsprüfsumme von der Datei abweicht (ADR 0005, „The list and the store“).
3. **Veröffentlichung.** Jeder Datenstand führt jede zurückgehaltene Rede in seinem Manifest (`withheld_reden`); der Datenstand-Skript lehnt ein Manifest ohne diese Liste oder mit einer abweichenden Liste ab. `CHANGES.md` und `changes.json` nennen die neu zurückgehaltenen Reden nach Sitzung, Rede-Kennung und Grund (`scripts/release_changes.py`). Mehr als zwei neu zurückgehaltene Reden in einem Datenstand stoppen die Veröffentlichung, bis der Betreiber jede mit `--confirm-withheld WP/NR:REDE_ID` bestätigt hat (`WITHHELD_CAP = 2`). Der erste Datenstand führt alle auf und hat keine Obergrenze.
4. **Zurückgehaltene Reden in den Daten.** DATA.md und die Daten-Seite nennen die Abdeckung und den zurückgehaltenen Anteil nach Eigenwörtern je Jahr, Fraktion und Sitzung (ADR 0005, „Coverage“). Eine zurückgehaltene erste Rede einer Person verhindert, dass sie in „Erste Reden“ als Debüt zählt.

## Was fehlt

**1. Der Text bleibt im Datensatz. Das ist der entscheidende Mangel.** `withheld_units.text` (die eigenen Worte des Redners) und `withheld_turns.text` (die Beiträge anderer Redner darin) werden mit exportiert (`scripts/data_dictionary.json`, Tabellen `withheld_units` und `withheld_turns`; ADR 0005: „A withheld Rede keeps its text and its reason“). Der Mechanismus nimmt die Rede also aus den Zählungen und aus `speeches`, **nicht aus dem veröffentlichten Text**. Für einen Parser-Lesefehler ist das richtig; für ein Löschverlangen ist es wirkungslos. Fehlt: eine zweite Art Zurückhaltung, die den Text nicht speichert (`text` und die `text`-Spalten von `withheld_turns` bleiben NULL), den Redner, die Seite und die Wortzahl behält und einen eigenen Grundcode trägt (in `speech_kinds.WITHHELD_REASONS` und im Datenwörterbuch, die genau dieselben Codes führen müssen). Dazu gehören ein Gate-Test, dass keine solche Zeile Text trägt, und die Änderung der Texte in ADR 0005, DATA.md und `LICENSE-DATA.md`. Bis das gebaut ist, kann der Betreiber ein Löschverlangen nicht wirksam erfüllen. **OFFEN: Der Betreiber beauftragt den Bau, bevor er das Verfahren der Clinic als vorhanden darstellt.** Das Anschreiben beschreibt das Verfahren als Vorschlag, nicht als gebaut.

**2. Der Grund steht öffentlich.** `reason` im Eintrag steht in einer öffentlichen Datei des Repositories und wird als `reason_detail` exportiert. Er darf keinen Namen und kein Detail der antragstellenden Person enthalten. Vorgeschlagene Formel: „Löschungs-/Widerspruchsverlangen nach DSGVO, Einzelfallentscheidung, Az. [laufende Nummer des privaten Registers]“. Die Commit-Nachricht gilt dasselbe.

**3. Die Einheit ist die ganze Rede.** Ein Eintrag zieht ein `<rede>`-Element oder einen vom Parser abgespaltenen Teil zurück, nie eine Textstelle. Nennt eine Rede eine Person, wird die ganze Rede des Redners zurückgehalten, einschließlich aller sonstigen Aussagen. Die Alternative, nur den Namen durch eine markierte Auslassung zu ersetzen, widerspricht der Treue zur Quelle und dem Kennzeichnungsgebot (Recherchenotiz, Frage 4, „Engineering way out“: nur mit Markierung vertretbar). OFFEN: Entscheidung des Betreibers, ob für Fall A eine markierte Auslassung des Namens besser ist als der Verlust der ganzen Rede; die Clinic kann dazu gefragt werden. Ungeprüft: ob ein einzelnes Beitrags-Element (Kurzintervention, Zwischenfrage) ohne seine Rede aufgeführt werden kann. Kurzinterventionen und Erwiderungen sind eigene `<rede>`-Elemente, eine eingebettete Zwischenfrage ist es nicht.

**4. Frühere Datenstände bleiben, wie sie sind.** `docs/release-policy.md`: „A release never changes.“ Ein Löschverlangen wirkt damit erst im nächsten Stand. Die GitHub-Datenstände früherer Fassungen enthalten den Text weiter; das Skript überschreibt nie ein Release, aber „nothing stops a person with write access from editing a GitHub release by hand“. OFFEN: Soll das Projekt für Fälle mit Art.-9-/Art.-10-Bezug eine **Ausnahme von der Unveränderlichkeit** zulassen, also das Asset des betroffenen Hauptdatenstands auf GitHub ersetzen oder entfernen? Das ändert `docs/release-policy.md`, das ADR 0003 und die Aussage in `datenschutz.html` („Eine veröffentlichte Version wird nicht nachträglich geändert“). Der Entwurf legt es der Clinic vor, statt es zu entscheiden. Kopien, die jemand schon heruntergeladen hat, kann kein Verfahren zurückrufen; die Lizenz (CC BY 4.0 für die eigenen Teile) erlaubt Weitergabe.

**5. Zenodo ist noch nicht gebaut.** Der Upload nach Zenodo steht in TODOS.md („A DOI per release and a citation file“) noch aus; es gibt kein Konto-Verfahren, das eine Fassung beschränkt. Was Zenodo selbst sagt (gelesen am 2026-11-22 auf `about.zenodo.org/policies/` und `/privacy-policy/`):
- Rücknahme („Withdrawal“) ist „an exceptional action, which normally should be requested and fully justified by the original uploader“. Wir wären der Uploader. Der Grund erscheint auf einer Hinweisseite an der Stelle des Objekts; „The DOI and the URL of the original object are retained.“
- Datensätze können „retracted from public view“ werden; „the data files and record are preserved“. Das heißt: Zenodo verbirgt die Fassung, löscht sie aber nicht.
- Gefunden wurde **kein** Verfahren, einen veröffentlichten Datensatz selbst zu löschen, **keine** Beschreibung, wie ein Uploader die Dateien einer veröffentlichten Fassung auf „eingeschränkt“ setzt, und **keine** Antwortfrist. Der Kontakt ist `zenodo.org/support` (nicht aufgerufen).
- OFFEN: Vor dem ersten Upload bei Zenodo anfragen, ob und wie eine Fassung nach Veröffentlichung nicht mehr öffentlich gezeigt werden kann, und die Antwort hier eintragen. Wortwahl im Anschreiben: „beschränken lassen“; die Zenodo-Richtlinie spricht von „Rücknahme“ und „aus der öffentlichen Ansicht nehmen“.
- Die Aufbewahrungsregel in Zenodos Datenschutzerklärung (ein Monat nach Veröffentlichung für Löschverlangen, danach nur in Ausnahmefällen) betrifft Zenodos eigene Verarbeitung von Konto-Daten und ist hier nur ein Hinweis, dass Zenodo spätere Löschungen als Ausnahme behandelt.

**6. Wo der Text sonst steht.** Ein Löschverlangen erreicht nicht (a) die 14 vollständigen Protokoll-XML-Dateien in `tests/fixtures/` des öffentlichen Repositories und deren Git-Verlauf, (b) den Git-Verlauf von `scripts/reviewed_units.json` und `scripts/person_corrections.json`, (c) den lokalen Cache des Betreibers (`data/xml/`; er ist die Quelle des Neuaufbaus und bleibt, öffentlich ist er nicht), (d) die Quelle selbst (DIP, bundestag.de). OFFEN: Vor der Prüfung eines Falls nachsehen, ob die Person in einer Fixture steht; wenn ja, müsste die Datei ersetzt und der Verlauf umgeschrieben werden. Der Entwurf nimmt an, dass der Betreiber das nur bei Art.-9-/Art.-10-Bezug tut.

**7. Abgleich mit Datenschutz-Seite.** `datenschutz.html` sagt: „Einen Widerspruch nach Art. 21 DSGVO prüfen wir; gibt er Anlass zu einer Änderung, erscheint sie in der nächsten Version.“ Das passt zu diesem Entwurf. Die Seite verspricht kein Löschen des Textes. Mit dem Bau von Punkt 1 muss der Satz Art. 17 und die Zurückhaltung benennen (TODOS.md, „ADR 0003 legal questions“, (d): die Sätze zu Art. 85 und zu unveränderlichen Datenständen nach der Antwort der Clinic neu lesen).

## Dokumentation jedes Falls

- **Privat, nicht im Repository** (enthält Daten der antragstellenden Person): Register mit laufender Nummer, Eingangsdatum und -kanal, wer was verlangt hat, Prüfung und Gründe, Entscheidung, Antwortdatum, Datenstand mit der Änderung, Datum der Zenodo-Anfrage und -Antwort. OFFEN: Ort und Form des Registers (Vorschlag: eine verschlüsselte Datei auf dem Rechner des Betreibers, Löschfrist siehe `02-verzeichnis-verarbeitungstaetigkeiten.md`).
- **Öffentlich:** der Eintrag in `scripts/reviewed_units.json` mit neutralem Grund; `CHANGES.md` und `changes.json` des Datenstands (neu zurückgehalten: Sitzung, Rede-Kennung, Grund); die Zählung zurückgehaltener Reden in DATA.md. Weitere Angaben zur Person stehen dort nicht.
- Sobald die Clinic geantwortet hat, nimmt der Betreiber ein Ergebnis in ADR 0003 auf (ADR 0003, Änderung 2026-11-21).

## Ablauf eines Falls (nach dem Bau von „Was fehlt“, Punkt 1)

1. Eingang, Registernummer, Eingangsbestätigung (sieben Tage).
2. Fall und Rede bestimmen: Sitzung, Rede-Kennung und Redner-ID aus dem Protokoll des Bundestages.
3. Prüfung und Entscheidung (ein Monat).
4. Bei Zurückhaltung: Eintrag in `scripts/reviewed_units.json` (Kind der Löschung, neutraler Grund), Neuaufbau mit `--offline --repersist`, Vorher-Nachher-Vergleich der Zählungen (`scripts/compare_store_values.py`), Datenstand mit Änderungsliste, bei mehr als zwei neuen zurückgehaltenen Reden `--confirm-withheld`.
5. Antwort an die Person, Eintrag im Register.
6. Gibt es eine archivierte „stable“-Fassung mit dem Text: Anfrage an Zenodo, Antwort ins Register.
