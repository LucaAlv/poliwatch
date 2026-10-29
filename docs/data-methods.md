# Datenstand und Auswertungsmethoden

Dieses in `DATA.md` eingebettete Dokument beschreibt den jeweiligen **konkreten Export**; es wird nicht als separate Datei ausgegeben. Der Export ist ein Snapshot, keine laufende Abfrage aktueller Bundestagsdaten. `DATA.md` nennt Release-Tag, Build-Revision, Exportformat, Schema-/Quellprüfsummen und Datenzeitpunkte; `local` bedeutet lokaler Export ohne Release-DOI. Die Schema- und Feldangaben werden aus dem Snapshot gelesen; die Bedeutungen stammen aus `scripts/data_dictionary.json`.

## Begriffe und Zählgrenzen

Die folgenden englischen Originaldefinitionen stammen aus `CONTEXT.md`; die deutsche Erläuterung daneben hält die festgelegte Zählregel für Leser dieses Codebooks fest.

> **Sitzung mit Dossier**: “A Sitzung this project has a Dossier for. Every count this project publishes — Redeanteil, Abweichung, Fakten and the like — ranges over Sitzungen mit Dossier only; a Sitzung without a Dossier is not counted as zero, it is absent.”

Das heißt: alle veröffentlichten Summen beziehen sich nur auf tatsächlich gebaute Dossiers; eine bekannte Sitzung ohne Dossier ist nicht als Nullbeobachtung vertreten.

> **Rede**: “One contribution to the debate for which a Redner is given the floor, as the Plenarprotokoll records it. It covers only that Redner's own words, not the Sitzungsleitung's words or Zwischenfragen recorded within it. A Kurzintervention and the Erwiderung to it are not Reden, and neither are the Fragen and Antworten of the Fragestunde and the Befragung der Bundesregierung; the Plenarprotokoll records the first three and the Befragung's Fragen and Antworten as `<rede>` elements like Reden, and the Fragestunde's as flat turns.”

Daher zählt die Exporttabelle `speeches` nur Reden; ähnlich markierte XML-Elemente können als Beiträge separiert sein.

> **Beitrag**: “Something said in a Sitzung that is not a Rede but that the Plenarprotokoll records with its Redner: a Zwischenfrage, a written submission, a Kurzintervention, an Erwiderung, a Frage or an Antwort of a Befragung der Bundesregierung or a Fragestunde. Each has a Kind (`zwischenfrage`, `zu_protokoll`, `kurzintervention`, `erwiderung`, `befragung_frage`, `befragung_antwort`, `fragestunde_frage`, `fragestunde_antwort`) and is stored in `contributions`, never in `speeches`. Beiträge are counted on their own by Kind and add to no figure defined over Reden, nor to the Zeichen of a Tagesordnungspunkt or Redner.”

> **Zu Protokoll gegebener Beitrag**: “A written submission explicitly identified in a typed annex as a zu Protokoll gegebene Rede. It is stored as `zu_protokoll`, displayed and counted separately, and adds to no Rede total, share or term series (decision 2026-09-30). A source-supported TOP is attached; uncertain associations remain sitting-level and missing source pages stay null. Declarations under §31 are a different source type and are excluded.”

Das schließt beliebige Anhangs-Reden und §31-Erklärungen aus; nur explizit identifizierte, quellengestützte Einreichungen werden separat als `zu_protokoll` geführt.

> **Sprechrolle**: “The capacity in which a speaker gives one speech, e.g. Bundesminister, Staatsministerin, Bundesratsmitglied. It belongs to the speech, never to the person, and does not change the speaker's parliamentary membership.”

Eine Rolle gehört also zur einzelnen Rede. Sie wird nicht als dauerhafte Eigenschaft der Person oder als Fraktion behandelt.

> **Period completeness**: “Whether every Sitzung the DIP catalog lists for a period — a Kalenderwoche or a calendar month — is in the store and has Sitzung completeness for a metric's Completeness basis; the current or a later calendar month is additionally never complete, however complete its sittings so far, and no such running-period rule applies to weeks. A Sitzung the catalog lists but the store lacks (its Dossier failed, was never built, or DIP has no XML for it yet) counts against its period, and a period with no Dossier at all is still judged, never complete. Periods run from the start of the week or month of the earliest Sitzung mit Dossier to the newest catalog Sitzung, and a Sitzung the catalog dates differently from the store holds both periods back until it is refreshed. Without an authoritative catalog — one fetched whole by an online build, not cut by --limit or --document-number — no period is complete. A period needs this to be observed and enter a Vergleichsbasis, but it alone does not guarantee publication.”

> **zurückgehalten**: “A period without Period completeness is not zurückgehalten but unvollständig erfasst.”

Die erste Definition beschreibt die genaue Katalog-/Dossierprüfung. Die zweite macht klar: unvollständige Abdeckung ist kein zurückgehaltener Kennzahlenwert; eine fehlende Beobachtungszeile ist kein Nullwert.

Die vollständigen fachlichen Festlegungen stehen in `CONTEXT.md`, insbesondere „Rede“, „Beitrag“, „Zu Protokoll gegebener Beitrag“, „Period completeness“, „Abweichung“ und „Abweichler“. Die Umsetzung steht in `scripts/derive.py` (Sprechrollen), `scripts/speech_kinds.py` und `scripts/validate_dip_protocol.py` (Beitragserkennung), `scripts/person_registry.py` (Personenzusammenführung) sowie `scripts/facts.py` (Periodenvollständigkeit und Kennzahlen).

ADR 0001 (`docs/adr/0001-count-speeches-by-sprechrolle.md`) sagt: “We count such a speech for its side (Bundesregierung or Bundesrat) and toward no Zusammenschluss.” Das heißt, eine Sprechrolle wird der entsprechenden Seite zugerechnet und nicht der Fraktion.

ADR 0002 (`docs/adr/0002-kurzinterventionen-are-not-reden.md`) sagt: “We do not count them as Reden: every figure defined over Reden (Redeanteil, Rangfolge nach Reden, Reden per Person, the Fakt der Woche metrics that count Reden) excludes them, and where they are shown they are counted on their own.” Das heißt, Beiträge dieser Arten bleiben außerhalb der Redezahlen und werden nur separat ausgewiesen. Die Klassifikation ist eine projektseitige Auswertung der Protokollstruktur und kann Fehler enthalten.

Redentext ist whitespace-normalisiert; Absatzgrenzen gehen verloren. `char_count` zählt Zeichen, keine Redezeit. Beiträge, die keiner Person sicher zugeordnet werden, können ohne `mp_id` vorkommen. Rede-/Beitragszuordnungen sind keine Vollständigkeitsbescheinigung.

## Personen und Abstimmungen

Personenkennungen sind dauerhafte Projektkennungen. `docs/stable-ids.md` beschreibt Quellkennungen, Namensabgleich, geprüfte Zusammenführungen und Aliasse. Gemeinsame Quellkennungen führen nur nach den dortigen Regeln zusammen; unsichere Fälle bleiben getrennt. `mp_canonical` ordnet Quellaufzeichnungen einer konsolidierten Kennung zu. Eine Personenseite ist kein Beweis für ein aktuelles Mandat.

Für Zeilenverknüpfungen die deklarierten Primär-/Fremdschlüssel verwenden, nicht die CSV-Zeilennummer. Projekt-Hashschlüssel enthalten ihre Schlüsselversion und werden deterministisch aus Quellkennungen gebildet; Quellkennungen wie DIP-Vorgangs-IDs bleiben Quellkennungen. `mps.id` identifiziert eine Quellpersonenaufzeichnung, `persons.id` eine konsolidierte Person; `mp_canonical.mp_id → canonical_id` verbindet sie für diese Generation. Früher ausgestellte Personenkennungen vor einem generationsübergreifenden Join über `person_aliases.id → person_id` bis zur fortgeführten Kennung auflösen. `person_records` und `person_bindings` bewahren die zugrunde liegenden Quellenaufzeichnungen und Vorkommensbindungen. Reine Namenszusammenführungen können revidiert werden; nicht jede momentane Gruppierung erzeugt deshalb einen dauerhaften Alias.

> **Abweichung**: “A Stimme of Ja where the Mehrheitsvotum of the MdB's Zusammenschluss is Nein, or of Nein where it is Ja. An Enthaltung or a Stimme nicht abgegeben is never an Abweichung, and where the Mehrheitsvotum is Enthaltung or there is none, no Stimme is. A fraktionslos MdB has no Zusammenschluss and so cannot make one.”

> **Abweichler**: “An MdB who makes an Abweichung in a namentliche Abstimmung. In public text this is said as "stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe".”

Eine Abweichung ist also nur Ja gegen ein Nein-Mehrheitsvotum oder Nein gegen ein Ja-Mehrheitsvotum; Enthaltungen, nicht abgegebene Stimmen, ein fehlendes Mehrheitsvotum und fraktionslose Mitglieder ergeben keine. Wie das Rezept `r3-abweichler` daraus zählt, steht im Abschnitt „Veröffentlichte SQL-Rezepte“.

## Abdeckung und bekannte Grenzen

`DATA.md` weist beobachtete Protokolle, Sitzungsdaten, Reden, Beiträge und Abstimmungen je Wahlperiode ausschließlich aus der exportierten SQLite-Datei aus. Diese beobachtete Abdeckung ist von DIP-Katalogzahlen, gebauten Dossiers und Beschaffungs-/Periodenvollständigkeit getrennt. Wo erwartete Sollzahlen oder Erwerbsnachweise fehlen, ist Vollständigkeit **unbekannt**; fehlende Abstimmungen bedeuten nicht, dass keine Abstimmung stattfand. Kein Zeitraum ab WP 18 bis heute darf allein aus dem Export als vollständig gelten. Bei leerem Store ist Abdeckung ausdrücklich leer.

Bekannte projektweite Grenzen sind die teilweise historische Protokollabdeckung, begrenzte Erfassung zeremonieller Sitzungen, Klassifikationsfehler bei Reden/Beiträgen und offene Abstimmungszuordnungen. Der Snapshot belegt nur, was tatsächlich in ihm enthalten ist. `docs/stable-ids.md` beschreibt verbleibende Identitätsunsicherheiten. Die exportierte Distribution speichert keinen Erwerbs-/Acquisition-Status je Sitzung und keinen vollständigen Erwerbsverlauf. Nicht jede Lücke lässt sich deshalb ohne externen Sollkatalog oder Erwerbsnachweis quantifizieren. Die Zuordnung von Abstimmungs-XLSX-Ergebnissen zu den im Protokoll gedruckten Endergebnissen ist laut `docs/adr/0003-licences-and-impressum.md` weiterhin offene Prüffrage; die mögliche Weitergabe der Bundestags-XLSX-Stimmenlisten bleibt laut Frage 5 derselben ADR und TODO „Settle the roll-call source for redistribution“ ebenfalls ungeklärt.

## Quellen, Weitergabe und Zitieren

Die Manifest-Spaltenquelle (`dip`, `bundestag.de`, `abgeordnetenwatch`, `derived`) ist eine grobe Layer-Klassifikation, keine vollständige Feldherkunft. Einzelne DIP-Felder werden aus XML extrahiert oder transformiert; Projektbuchhaltung wie `created_at`/`updated_at` und einige ausgestellte Kennungen wird im Dictionary ausdrücklich als generiert beschrieben, auch wenn der bestehende Manifest-Fallback kein eigenes Tag dafür hat. Auch mps-Felder können mehrere Quellen enthalten: Anzeigename und Zugehörigkeit kommen je nach Aufzeichnung aus DIP-API, XML oder der Bundestags-Abstimmungsliste; profile_url kann statt abgeordnetenwatch eine Bundestagsbiografie enthalten. Die bestehenden groben Tags bleiben unverändert. Die Feldherkunft ist im Dictionary offengelegt; diese Unschärfe wird hier dokumentiert und schafft keine neuen Lizenzrechte.

Die Lizenzhinweise sind geschichtet und folgen `docs/data-license.md` sowie `docs/adr/0003-licences-and-impressum.md`: DIP-Daten unter DIP-Nutzungsbedingungen, namentliche Abstimmungen aus Bundestagsquellen, abgeordnetenwatch-Profildaten CC0 1.0, eigene Auswertungen CC BY 4.0. Transformationen ändern die Herkunftsbedingungen der Eingangsdaten nicht. Die dort genannte Frage, ob die Weitergabe der Bundestag-Abstimmungsdaten durch die Protokollgrundlage gedeckt ist oder eine schriftliche Zustimmung braucht, ist offen. Dieser Datenstand schafft keine neue Weitergabeberechtigung und ersetzt keine Klärung.

Zitieren Sie den tatsächlichen Release-Tag, die Build-Revision und den Dateinamen der verwendeten Generation aus `datenstand.json`/`DATA.md`; nennen Sie bei einer veröffentlichten Generation den dort verlinkten unveränderlichen Download. Ein lokaler Export hat keinen Release-Tag mit DOI und keine DOI. Produktname, DOI und `CITATION.cff` sind nicht festgelegt.
