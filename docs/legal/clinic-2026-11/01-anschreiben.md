# Anschreiben an die Cyber Law Clinic (Entwurf)

> Entwurf für den Betreiber. Der Betreiber schickt ihn selbst. Platzhalter in eckigen Klammern und alle `OFFEN:`-Zeilen vor dem Versand füllen und streichen. Anschrift und E-Mail-Adresse des Betreibers stehen nie in dieser Datei.

---

**An:** Cyber Law Clinic, Universität Hamburg (Beratung für Privatpersonen)
**Von:** Luca Veh, [KONTAKT: E-Mail-Adresse und Postanschrift des Betreibers, nur im versandten Schreiben]
**Datum:** [DATUM]
**Betreff:** Anfrage zur Rechtsgrundlage für ein Open-Data-Projekt zum Deutschen Bundestag (DSGVO, Art. 6, 9, 85)

Sehr geehrte Damen und Herren,

ich betreibe als Privatperson, ohne Unternehmen und ohne Einnahmen, ein Open-Data-Projekt zum Deutschen Bundestag, Arbeitstitel „poliwatch“ (auf der Website „Bundestag-Puls“; Quellcode unter https://github.com/LucaAlv/poliwatch). Ich kann mir keine anwaltliche Beratung leisten. [OFFEN: Ein Satz zur Bedürftigkeit nach Wunsch des Betreibers; das Verfahren der Clinic nennt dafür keine Kriterien.] Ich bitte Sie um eine rechtliche Einschätzung zu einer Frage, die ich vor der ersten Veröffentlichung beantwortet haben möchte.

**Was veröffentlicht wird.** Ein Datensatz (SQLite-Datei und CSV-Tabellen mit Datenbeschreibung) und eine statische Website. Beide enthalten, aus öffentlichen Quellen (DIP und Plenarprotokolle des Bundestages, namentliche Abstimmungen auf bundestag.de, Profildaten von abgeordnetenwatch.de unter CC0):

- Namen, Funktion und Fraktion der Abgeordneten sowie Geburtsjahr, Geschlecht, Beruf, Wahlkreis und Bundesland (die letzten fünf aus abgeordnetenwatch.de);
- den Volltext jeder Rede und jedes Redebeitrags der 18. bis 21. Wahlperiode (seit Oktober 2013, rund 61.600 Reden in 806 Sitzungen), nur die eigenen Worte des Redners, ohne Zwischenrufe und Beifall;
- jedes namentliche Abstimmungsergebnis jedes Mitglieds (rund 500.000 Einzelstimmen in 736 Abstimmungen) und daraus berechnete Kennzahlen, etwa ob jemand von der Fraktionsmehrheit abwich;
- Redner ohne Mandat (Regierungsmitglieder, Bundesrat, Gäste), soweit sie im Protokoll sprechen.

Dazu kommen **Dritte, die in Reden genannt werden.** Das Projekt wertet Namen im Redetext nicht aus und bietet keine Volltextsuche auf der Website. Die Namen stehen aber im veröffentlichten Redetext, so wie das Protokoll sie nennt. Darunter können Gesundheits-, Religions- oder Strafverfahrensangaben über Privatpersonen sein (Art. 9, Art. 10 DSGVO).

Eine Veröffentlichung (Datenstand) wird nie geändert. Jede Fassung erhält einen Prüfsummen-Eintrag und wird auf GitHub abgelegt; geprüfte Fassungen („stable“, etwa vierteljährlich) sollen zusätzlich bei Zenodo mit einer DOI archiviert werden, damit Zitate nachprüfbar bleiben. Wissenschaftliche Arbeiten sollen sie zitieren können. Deshalb brauche ich die Antwort vor der ersten Veröffentlichung: Später lässt sich eine zitierte Fassung nicht mehr ändern. Eine Korrektur erscheint in der jeweils nächsten Fassung (`docs/release-policy.md` im Repository).

**Die Rechtsgrundlagen, auf die ich mich stützen will.** Ich habe sie selbst recherchiert (Recherchenotiz im Repository, `docs/research/adr-0003-legal-questions-2026-11.md`); das ist ausdrücklich keine Rechtsberatung.

1. **Daten der Abgeordneten:** Art. 6 Abs. 1 lit. f DSGVO. Das berechtigte Interesse ist, das öffentliche Handeln der Abgeordneten aus dem amtlichen Protokoll nachvollziehbar zu machen.
2. **Politische Meinungen** (Abstimmungen, Fraktion, Reden): zusätzlich Art. 9 Abs. 2 lit. e DSGVO, weil die Abgeordneten sie im Plenum offensichtlich öffentlich gemacht haben.
3. **Dritte, die in Reden genannt werden:** Art. 85 DSGVO in Verbindung mit § 23 MStV, in der Lesart des BGH (Urteil vom 29.07.2025, VI ZR 426/24: „zu journalistischen Zwecken“ weit verstanden), als zweite Grundlage neben Art. 6 Abs. 1 lit. f. Für die berechneten Kennzahlen über Abgeordnete beanspruche ich Art. 85 nicht.

**Meine Fragen.**

1. Tragen diese drei Grundlagen die Veröffentlichung? Wo sehen Sie die größte Schwäche? Mir ist besonders unsicher, ob Art. 85 DSGVO / § 23 MStV einen Volltext-Datensatz des amtlichen Protokolls trägt, den eine Privatperson mit nur wenig eigener Bearbeitung bereitstellt (Mindestmaß eigener inhaltlicher Bearbeitung), und ob die eigenen Berechnungen (Abweichung von der Fraktionslinie) von Art. 9 Abs. 2 lit. e gedeckt sind.
2. Fehlt eine Grundlage oder eine Pflicht? Insbesondere Art. 10 DSGVO bei Straftatbezügen Dritter in Reden.
3. Genügt das Löschverfahren (Anlage `04-takedown-verfahren.md`; ein Vorschlag, der Teil davon ist noch nicht umgesetzt): auf begründetes Verlangen eine einzelne Rede mit Begründung zurückhalten, im nächsten Datenstand berichtigen, bei Zenodo die betroffene Fassung aus der öffentlichen Ansicht nehmen lassen (ob Zenodo das für eine veröffentlichte Fassung erlaubt, ist noch nicht geklärt)? Trägt Art. 17 Abs. 3 lit. a DSGVO, dass unveränderliche, zitierte Fassungen bis dahin stehen bleiben?
4. Reichen Verzeichnis der Verarbeitungstätigkeiten und Schwellenwertprüfung für die Datenschutz-Folgenabschätzung (Anlagen `02` und `03`)? Wo irre ich?

**Anlagen** (alle als Entwurf des Projekts, zur Prüfung durch Sie):
- `02-verzeichnis-verarbeitungstaetigkeiten.md` (Art. 30 DSGVO)
- `03-dsfa-schwellenwert.md` (Art. 35 DSGVO)
- `04-takedown-verfahren.md`
- Datenschutzerklärung der Website (Text im Repository: `scripts/build_dip_pulse_site.py`, `render_datenschutz_page`) und `LICENSE-DATA.md`

Ich weiß, dass Sie nicht vertretungsbefugt sind und keine Haftung für Ihren Rat übernehmen. Eine Einschätzung auch in Stichworten hilft mir. [OFFEN: Wunschtermin für die Antwort, falls der Betreiber einen nennen will. Vorschlag des Entwurfs: keiner; die erste Veröffentlichung wartet auf die Antwort.]

Mit freundlichen Grüßen
Luca Veh

---

**Hinweise für den Betreiber, nicht Teil des Schreibens:**

- Länge: etwa zwei Seiten ohne diese Hinweise.
- Alle Zahlen stammen aus dem Referenzbestand vom 2026-11-22 (806 Sitzungen, 61.637 Reden, 736 Abstimmungen, 502.697 Einzelstimmen) und ändern sich mit jedem Update. Vor dem Versand neu lesen, oder die gerundeten Werte lassen.
- OFFEN: Soll die Antwort der Clinic an eine Adresse gehen, die nicht die öffentliche Impressum-Adresse ist? Das Impressum nennt die Wohnanschrift (ADR 0003, Änderung 2026-11-21); die Clinic braucht nur einen Rückkanal.
- OFFEN: Falls die Clinic ablehnt, geht dieselbe Frage an die Landesdatenschutzbeauftragte des Landes des Betreibers (ADR 0003, Änderung 2026-11-21). [OFFEN: Land des Betreibers.] Das Schreiben passt dafür fast unverändert; die Anrede und der Satz zur Haftung ändern sich.
