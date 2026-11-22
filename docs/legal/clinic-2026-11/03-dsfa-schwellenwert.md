# Schwellenwertprüfung zur Datenschutz-Folgenabschätzung (Art. 35 DSGVO), Entwurf

> **Das ist die Einschätzung des Projekts, nicht die eines Juristen.** Die Clinic soll sie prüfen. Die Recherchenotiz des Projekts hat Art. 35 nicht zitiert (`docs/research/adr-0003-legal-questions-2026-11.md`, Frage 4, Punkt 3). Der Wortlaut von Art. 35 und Erwägungsgrund 91 unten wurde am 2026-11-22 über dejure.org und dsgvo-gesetz.de nachgelesen. Die Kriterienliste der Artikel-29-Gruppe (WP 248 rev.01) ist **nicht** nachgelesen, sondern aus dem Gedächtnis des Entwurfsverfassers eingesetzt. OFFEN: Der Betreiber oder die Clinic prüft sie am Original. Die Muss-Liste der zuständigen Aufsichtsbehörde nach Art. 35 Abs. 4 ist ebenfalls nicht gelesen. OFFEN: Sie ist die Liste der Landesdatenschutzbeauftragten des Betreibers [Land: OFFEN] und der DSK; nachsehen, ob die Verarbeitung dort vorkommt.

## Maßstab

- **Art. 35 Abs. 1:** Eine Folgenabschätzung ist nötig, wenn eine Form der Verarbeitung „voraussichtlich ein hohes Risiko für die Rechte und Freiheiten natürlicher Personen“ hat.
- **Art. 35 Abs. 3** nennt „insbesondere“ drei Fälle: (a) systematische und umfassende Bewertung persönlicher Aspekte durch automatisierte Verarbeitung einschließlich Profiling, wenn darauf Entscheidungen mit Rechtswirkung oder ähnlich erheblicher Wirkung beruhen; (b) umfangreiche Verarbeitung besonderer Kategorien nach Art. 9 Abs. 1 oder von Daten nach Art. 10; (c) systematische umfangreiche Überwachung öffentlich zugänglicher Bereiche.
- **Erwägungsgrund 91:** „umfangreich“ sind Verarbeitungen, die auf regionaler, nationaler oder supranationaler Ebene große Mengen personenbezogener Daten verarbeiten, viele Personen betreffen können und wahrscheinlich ein hohes Risiko bergen. Eine einzelne Ärztin oder ein einzelner Rechtsanwalt verarbeitet nicht schon deshalb umfangreich.
- **Kriterien nach WP 248 rev.01** (aus dem Gedächtnis, nicht nachgelesen): Bewertung oder Scoring; automatisierte Entscheidung mit Rechtswirkung; systematische Überwachung; sensible oder höchstpersönliche Daten; Verarbeitung in großem Umfang; Abgleich oder Zusammenführung von Datensätzen; schutzbedürftige Betroffene; innovative Nutzung oder neue technische Lösungen; Verarbeitung, die Betroffene an der Ausübung eines Rechts hindert. Als Faustregel nennt die Gruppe: Treffen zwei oder mehr zu, ist eine Folgenabschätzung in der Regel nötig, im Einzelfall darf der Verantwortliche aber auch bei zwei Kriterien davon absehen und muss es begründen.

## Prüfung, Kriterium für Kriterium

| Kriterium | Trifft zu? | Begründung (Stand 2026-11-22) |
|---|---|---|
| Art. 35 Abs. 3 lit. a: umfassende Bewertung mit Rechtswirkung | nein | Das Projekt entscheidet nichts über Personen und liefert niemandem Entscheidungsgrundlagen mit Rechtsfolge. Die Kennzahlen (Abweichung von der Fraktionsmehrheit, Erste Reden, Fakten) sind Beschreibungen öffentlichen Verhaltens, keine Bewertungen mit Folgen. |
| Art. 35 Abs. 3 lit. c: Überwachung öffentlicher Bereiche | nein | Es werden nur veröffentlichte amtliche Quellen gelesen. Es gibt keine Beobachtung von Personen im Raum und keine Verfolgung ihres Online-Verhaltens. |
| Art. 35 Abs. 3 lit. b: umfangreiche Verarbeitung von Art. 9/10-Daten | **offen, grenzwertig** | Art. 9: Fraktion, Reden und Abstimmungen lassen politische Meinungen erkennen. Über alle Betroffenen zusammen ist das viel (6.430 Personenaufzeichnungen, rund 61.600 Reden, rund 500.000 Einzelstimmen, seit 2013). Die Zahl der Betroffenen ist aber national klein im Vergleich mit dem, was Erwägungsgrund 91 vor Augen hat, und die Daten gehören Menschen, die ihr Amt öffentlich ausüben und die Äußerungen im Plenum selbst veröffentlicht haben. Art. 10 und Art. 9 bei Dritten: möglich, aber zufällig und nicht gesucht (siehe unten). |
| Bewertung oder Scoring (WP 248) | teilweise | Die berechnete Abweichung von der Fraktionslinie (`vote_members.abweichung`) und die Kennzahlen je Person bewerten Verhalten. Sie sind regelbasiert und tragen keine Entscheidung. |
| Systematische Überwachung | nein | wie oben, lit. c. |
| Sensible Daten | ja | Art. 9 (politische Meinungen); bei Dritten möglich Art. 9 und 10. |
| Großer Umfang | grenzwertig | viele Datensätze und ein langer Zeitraum, aber eine kleine, klar umrissene Gruppe von Betroffenen (Abgeordnete, Regierungsmitglieder, Gäste). Dritte: Zahl nicht bekannt, weil Namen im Text nicht erfasst werden. |
| Zusammenführung von Datensätzen | ja, begrenzt | Das Projekt führt DIP, bundestag.de und abgeordnetenwatch.de zu einer Person zusammen (Personenregister). Alles stammt aus öffentlichen Quellen zu denselben öffentlichen Personen. Es entsteht kein Merkmal, das die Quellen nicht schon einzeln nennen; neu ist die Verbindung und die Abweichungsrechnung. |
| Schutzbedürftige Betroffene | nein bei Abgeordneten; unbekannt bei Dritten | Kinder oder Patienten als namentlich Genannte sind möglich, aber nicht prüfbar. |
| Innovative Technik | nein | Regeln und Parser, keine KI im Datensatz (KI-Zusammenfassungen sind nicht Teil von v1). |
| Verhinderung der Rechtsausübung | nein | Betroffene können sich melden (Impressum-E-Mail), und es gibt ein Verfahren (`04-takedown-verfahren.md`). Weil Datenstände unveränderlich sind, wirkt ein Verlangen erst im nächsten Stand; das ist der Punkt, den die Clinic prüfen soll. |

Gezählt: sicher ein bis zwei Kriterien (sensible Daten; Zusammenführung), drei weitere grenzwertig oder teilweise (Umfang, Bewertung, lit. b).

## Schlussfolgerung des Projekts

1. **Eine förmliche Folgenabschätzung ist nach Einschätzung des Projekts nicht zwingend, aber der Fall ist grenzwertig.** Ausschlaggebend sind die Natur der Betroffenen (öffentliche Amtsträger, Äußerungen im Plenum, amtlich veröffentlicht), die fehlende Wirkung auf Entscheidungen über Personen und der Verzicht auf Auswertung von Namen Dritter. Das Risiko für Abgeordnete halten wir für niedrig.
2. **Das Risiko für Dritte ist höher und liegt in der Unveränderlichkeit.** Eine Person, die ein Redner nennt, hat nichts veröffentlicht. Der Volltext bleibt in zitierten Fassungen stehen. Dagegen setzen wir das Verfahren in `04-takedown-verfahren.md` und fragen die Clinic, ob es reicht.
3. **Wir halten die Prüfung trotzdem fest und führen sie nach**, damit der Betreiber zeigen kann, dass er sie gemacht hat. Auslöser einer neuen Prüfung: Zwischenrufe werden gelesen (neue Betroffenengruppe: Urheber von Zwischenrufen, TODOS.md), KI-Zusammenfassungen kehren zurück, jemand führt eine Suche nach Namen oder eine Sammlung aller Reden einer Person ein, ein Löschverfahren scheitert.
4. **Falls die Clinic oder eine Aufsichtsbehörde die Schwelle als überschritten ansieht,** ist die Folgenabschätzung kurz: Beschreibung der Verarbeitung (siehe `02-…`), Notwendigkeit und Verhältnismäßigkeit (Interessenabwägung, siehe Anschreiben), Risiken für Betroffene (Gruppen oben) und Abhilfen (Verfahren, Datenminimierung: keine Anschriften, keine Zwischenrufe, keine Namenssuche, kein Volltext je Person). Der Entwurf kann dann zu einer Folgenabschätzung ausgebaut werden.

OFFEN: Der Betreiber entscheidet, ob er diese Schlussfolgerung vor der Antwort der Clinic schon als Stand des Projekts führt.
