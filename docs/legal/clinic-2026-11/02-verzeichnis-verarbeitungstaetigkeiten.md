# Verzeichnis von Verarbeitungstätigkeiten (Art. 30 DSGVO), Entwurf

> Entwurf des Projekts, von der Clinic zu prüfen. Stand: 2026-11-22. Zahlen aus dem Referenzbestand des Projekts vom selben Tag.
>
> **Pflicht trotz Kleinstbetrieb.** Art. 30 Abs. 5 DSGVO befreit Stellen mit weniger als 250 Beschäftigten nicht, wenn die Verarbeitung nicht nur gelegentlich erfolgt, ein Risiko für die Rechte der Betroffenen birgt oder besondere Kategorien (Art. 9 Abs. 1) oder Daten über Straftaten (Art. 10) betrifft (Wortlaut nach dejure.org gelesen am 2026-11-22). Hier trifft das zu: Der Datensatz enthält regelmäßig, nicht nur gelegentlich, Angaben, die politische Meinungen erkennen lassen. Die Ausnahme für kleine Stellen gilt also nicht, auch nicht für eine einzelne Privatperson als Betreiber.

## Verantwortlicher (Art. 30 Abs. 1 lit. a)

- Luca Veh, Privatperson, kein Unternehmen, keine weitere Person (ADR 0003, D4).
- Anschrift und E-Mail: [KONTAKT: nur in der gedruckten oder versandten Fassung, nie im Repository]. Dieselben Angaben stehen im Impressum der Website.
- Gemeinsam Verantwortliche: keine. Datenschutzbeauftragter: keiner benannt (OFFEN: Der Betreiber prüft, ob § 38 BDSG eine Benennung verlangt; bei einer Person ohne Beschäftigte wohl nicht).
- Vertreter: keiner.

## Tätigkeiten

| Nr. | Tätigkeit | Zweck | Rechtsgrundlage (Vorschlag) |
|---|---|---|---|
| T1 | Datensatz „Datenstand“ erstellen und veröffentlichen (SQLite, CSV, Datenbeschreibung, Änderungsliste, Prüfsummen) | Die Arbeit des Bundestages nachvollziehbar und maschinenlesbar machen; Zitierbarkeit | Art. 6 Abs. 1 lit. f; Art. 9 Abs. 2 lit. e; für Dritte in Reden Art. 85 DSGVO i. V. m. § 23 MStV |
| T2 | Website mit vorberechneten Ansichten (Sitzungen, Abgeordnete, Abstimmungen) | wie T1 | wie T1 |
| T3 | Berechnete Kennzahlen über Abgeordnete (Fraktionsabweichung bei Abstimmungen, Fakten, Erste Reden) | Einordnung der öffentlichen Tätigkeit | Art. 6 Abs. 1 lit. f; Art. 9 ist offen (siehe `03-dsfa-schwellenwert.md`, Frage 2) |
| T4 | Korrespondenz mit Betroffenen und Lesern (E-Mail, Auskunft, Berichtigung, Widerspruch, Löschung) | Antworten; Pflichten nach Art. 12 bis 21 | Art. 6 Abs. 1 lit. c und f |
| T5 | Fehlermeldungen über GitHub Issues | Datenfehler beheben | Art. 6 Abs. 1 lit. f; GitHub ist für die Plattform selbst verantwortlich |
| T6 | Server-Logs beim Hoster der Website | technischer Betrieb | Sache des Hosters; Auftragsverarbeitung nach Art. 28 vor dem Start der Website. OFFEN: Hoster steht noch nicht fest (TODOS.md, „Site hosting plan“) |

Die Website setzt keine Cookies, enthält keine Analyse- oder Tracking-Werkzeuge und lädt nichts von fremden Servern; sie schreibt nur auf Klick die Wahl des Farbschemas in den `sessionStorage` des Browsers (`datenschutz.html`; Rechtsgrundlage dort § 25 Abs. 2 Nr. 2 TDDDG).

## Kategorien von Betroffenen und Daten (Abs. 1 lit. c)

| Betroffene | Daten | Herkunft | Besondere Kategorie |
|---|---|---|---|
| Abgeordnete des Bundestages der 18. bis 21. Wahlperiode (6.429 Personenaufzeichnungen im Bestand, darunter Ehemalige und Redner ohne Mandat) | Name, Titelzeile und Funktion (DIP), Redner-ID, Fraktion zur Zeit der Rede, Zugehörigkeitszeiträume (MdB-Stammdaten) | DIP, Plenarprotokoll-XML, Bundestag | Fraktion lässt politische Meinung erkennen (Art. 9) |
| dieselben | Geburtsjahr, Geschlecht, Beruf, Wahlkreis, Bundesland, abgeordnetenwatch-ID und Profil-URL | abgeordnetenwatch.de API (CC0) | nein |
| dieselben | Volltext ihrer Reden und Beiträge (eigene Worte), Seitenangabe | Plenarprotokoll-XML | ja: politische Meinung (Art. 9) |
| dieselben | Einzelstimme je namentlicher Abstimmung (Ja, Nein, Enthalten, nicht abgegeben), berechnete Fraktionsabweichung | bundestag.de (Abstimmungslisten), Berechnung des Projekts | ja: politische Meinung (Art. 9) |
| Redner ohne Mandat: Regierungsmitglieder, Mitglieder des Bundesrates, Gäste (nicht gezählt; das Feld `is_mdb` trennt sie nicht verlässlich, weil DIP nur das aktuelle Amt nennt) | Name wie gedruckt, Amtsangabe, Rede | Plenarprotokoll-XML, DIP | Rede: politische Meinung, soweit sie eine äußern |
| Dritte, die in Reden oder Zwischenfragen genannt werden (nicht gezählt, nicht gesucht) | Name und was der Redner über sie sagt, so wie das Protokoll es druckt | Plenarprotokoll-XML | möglich: Gesundheit, Religion, Straftaten (Art. 9, Art. 10); nicht prüfbar, weil das Projekt Namen im Text nicht erfasst |
| Absender von E-Mails und Meldungen | Adresse, Nachricht, Zeitpunkt | die Betroffenen selbst | nein |

Nicht im Datensatz: Zwischenrufe und Beifall (`<kommentar>` wird nicht gelesen), Anschriften, Kontaktdaten, Fotos, Social-Media-Konten der Abgeordneten. KI-Zusammenfassungen sind nicht Teil von v1.

Umfang am 2026-11-22: 806 Sitzungen (2013-10-22 bis 2026-11-13), 61.637 Reden, 45.991 Beiträge, 100 zurückgehaltene Reden, 736 namentliche Abstimmungen mit 502.697 Einzelstimmen.

## Empfänger (Abs. 1 lit. d, e)

| Empfänger | Was | Drittland |
|---|---|---|
| Alle, die Website oder Download abrufen | alles Veröffentlichte | offen für jeden |
| GitHub (Repository, Releases, Issues) | Quellcode, Testdaten, Datenstände | GitHub Inc., USA. OFFEN: Der Betreiber prüft Zertifizierung unter dem EU-US Data Privacy Framework oder Standardvertragsklauseln und trägt das Ergebnis ein |
| Zenodo (CERN) | geprüfte Datenstände mit DOI; **vorgesehen, noch nicht gebaut** (TODOS.md, „A DOI per release“) | CERN, Schweiz. OFFEN: Angemessenheitsbeschluss für die Schweiz bestätigen |
| Hoster der Website | Seiten; Zugriffe | Deutschland geplant (TODOS.md). OFFEN: Anbieter, Auftragsverarbeitungsvertrag (Art. 28) |
| Quellen (DIP, bundestag.de, abgeordnetenwatch.de) | nur Abrufe durch das Projekt; keine personenbezogenen Daten von Betroffenen | – |

Auch das öffentliche Repository enthält Daten: 14 vollständige Plenarprotokoll-XML-Dateien unter `tests/fixtures/` und Namen mit Protokoll-URLs in `scripts/person_corrections.json` (öffentlich seit 2026-11-06). Was das für Löschverlangen heißt, steht in `04-takedown-verfahren.md`, „Was fehlt“, Punkt 6.

## Fristen für die Löschung (Abs. 1 lit. f)

- Datenstände: unbefristet, als versioniertes Archiv, damit Zitate nachprüfbar bleiben (`datenschutz.html`; `docs/release-policy.md`: „A release never changes“). Das ist die Rechtfertigung nach Art. 17 Abs. 3 lit. a DSGVO, die die Clinic prüfen soll.
- Lokaler Bestand des Betreibers (Store und Cache, einschließlich des Protokoll-XML): bleibt, solange das Projekt läuft; wird bei jedem Neuaufbau ersetzt.
- E-Mails von Betroffenen: [OFFEN: Vorschlag des Entwurfs: drei Jahre nach Abschluss des Falls, weil Löschungen nachweisbar sein müssen; der Betreiber entscheidet].
- Hoster-Logs: [OFFEN: Die Dauer nennt der Hoster; im Betreiberdatei-Feld `hosting.log_retention`].
- Einzelne Reden auf begründetes Verlangen: nach `04-takedown-verfahren.md`.

## Technische und organisatorische Maßnahmen (Abs. 1 lit. g, Art. 32), soweit im Repository belegt

- Die Website ist statisch; sie verarbeitet keine Eingaben der Besucher und kennt kein Login.
- Der Aufbau des Bestands läuft lokal beim Betreiber. Der Bestand liegt in einem eigenen privaten Verzeichnis und wird nicht vollständig auf den Server kopiert (TODOS.md, „Site hosting plan“: `data/` is not deployed wholesale).
- Datenstände tragen eine Prüfsummendatei (`SHA256SUMS`). Das Veröffentlichungsskript überschreibt nie ein vorhandenes Verzeichnis oder einen vorhandenen Tag (`scripts/publish_dip_pulse_data.py`).
- Zugangsdaten (Zenodo-Tokens) liegen im Schlüsselbund des Betreibers, nie im Repository (TODOS.md).
- Meldung von Sicherheitslücken: GitHub Private Vulnerability Reporting, `SECURITY.md`.
- OFFEN: Festplattenverschlüsselung des Rechners, auf dem der Bestand liegt; Sicherungskopien (wo, wie lange, verschlüsselt); Zwei-Faktor-Anmeldung bei GitHub, Zenodo und beim Hoster. Das Repository belegt nichts davon; der Betreiber trägt es ein.
- OFFEN: Wer außer dem Betreiber Zugriff hat (Annahme: niemand).

## Änderungen an diesem Verzeichnis

Neu fassen bei jeder neuen Quelle, jedem neuen Empfänger und jeder neuen Datenkategorie, zum Beispiel wenn Zwischenrufe gelesen werden (TODOS.md, „Zwischenrufe“) oder KI-Zusammenfassungen zurückkommen. [OFFEN: Datum der ersten Fassung durch den Betreiber.]
