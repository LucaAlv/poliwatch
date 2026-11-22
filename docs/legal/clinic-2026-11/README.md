# Paket für die Cyber Law Clinic, Universität Hamburg (ADR 0003, Frage 4)

Entwurf vom 2026-11-22. **Der Betreiber schickt es selbst.** Nichts hier ist abgeschickt; keine Stelle wurde kontaktiert. Es ist Recherche und ein Entwurf, den Juristen prüfen sollen, keine Rechtsberatung.

Anlass: ADR 0003, Änderung 2026-11-21, Frage 4. Die Rechtsgrundlagen für personenbezogene Daten von Abgeordneten und von Dritten, die in Reden genannt werden, sollen schriftlich geprüft sein, bevor der erste Datenstand mit `--publish` erscheint. Der Datenstand ist danach unveränderlich und zitiert. Quelle der Vorschläge: `docs/research/adr-0003-legal-questions-2026-11.md` (Frage 4, Zweitlesung).

| Datei | Inhalt |
|---|---|
| `01-anschreiben.md` | Anschreiben mit den Fragen, etwa zwei Seiten. Das einzige Schreiben, das die Clinic liest. |
| `02-verzeichnis-verarbeitungstaetigkeiten.md` | Verzeichnis nach Art. 30 DSGVO, eine Seite: Zwecke, Kategorien, Empfänger, Quellen, Fristen, Maßnahmen. |
| `03-dsfa-schwellenwert.md` | Schwellenwertprüfung nach Art. 35 DSGVO mit Schlussfolgerung, als Einschätzung des Projekts. |
| `04-takedown-verfahren.md` | Verfahren bei Löschungs- und Widerspruchsverlangen, mit dem, was der Code heute tut, und dem, was fehlt. |

## Was der Betreiber vor dem Versand tut

1. In allen vier Dateien jede Zeile mit `OFFEN:` lesen, entscheiden oder ausfüllen und streichen. Danach `grep -n "OFFEN" docs/legal/clinic-2026-11/0[1-4]-*.md` ohne Treffer (diese README nennt das Wort selbst und bleibt außen vor).
2. Platzhalter `[KONTAKT: …]`, `[DATUM]`, `[Land: …]` in der **versandten** Fassung füllen. Anschrift und E-Mail-Adresse des Betreibers stehen nie in einer Datei des Repositories. Die gefüllte Fassung bleibt außerhalb des Repositories.
3. Zahlen im Anschreiben und im Verzeichnis (Stand Referenzbestand 2026-11-22) neu lesen oder gerundet lassen.
4. Entscheiden, ob `04-takedown-verfahren.md` als gebaut oder als Vorschlag gilt. Heute ist es ein Vorschlag: ein Löschverlangen kann mit dem Code von 0.46.43.0 nicht erfüllt werden, weil zurückgehaltene Reden ihren Text im Export behalten (dort, „Was fehlt“, Punkt 1).
5. Die Antwort der Clinic (oder, bei Ablehnung, der Landesdatenschutzbeauftragten des Landes des Betreibers) in ADR 0003 eintragen.

Die Anlagen 02 bis 04 gehen der Clinic als Anlage zum Anschreiben mit. Das Anschreiben nennt sie.
