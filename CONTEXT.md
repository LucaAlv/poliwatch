# Bundestag Pulse

A public site and open dataset about what happens in the plenary sessions of the Deutscher Bundestag: sittings, speeches, votes and the people and groups behind them.

## Language

### Parliamentary groups and people

**Zusammenschluss**:
A parliamentary association of MdBs, either a Fraktion or a Gruppe, recognised for one Wahlperiode. This is the umbrella term wherever something is counted "per group" (seats, speeches, Zwischenrufe, votes).
_Avoid_: using "Fraktion" loosely for both, parlamentarische Gruppierung

**Zugehörigkeit**:
An MdB's membership in one Zusammenschluss over a date range. An MdB has at most one Zugehörigkeit at any date, and none while fraktionslos.
_Avoid_: Fraktionszugehörigkeit (too narrow), party membership

**Fraktion**:
An association of MdBs that meets the Fraktion minimum strength under § 10 GO-BT, recognised for one Wahlperiode. A Fraktion that dissolves and is later refounded under the same name counts as a new Fraktion.
_Avoid_: party, faction, Partei

**Gruppe**:
An association of MdBs recognised under § 10a GO-BT without reaching Fraktion minimum strength (e.g. Gruppe Die Linke, Gruppe BSW in WP 20). It has its own legal status and is not a kind of Fraktion.
_Avoid_: "Fraktion (Gruppe)", "BSW (Gruppe)"

**fraktionslos**:
The state of an MdB who belongs to no Fraktion and no Gruppe at a given date. It describes the absence of a membership, not an organisation.
_Avoid_: treating "fraktionslos" as a Fraktion

**Partei**:
A political party outside the Bundestag (CDU, CSU, SPD, …). Party membership and parliamentary membership are separate facts: CDU and CSU are two Parteien but form one Fraktion.
_Avoid_: using "Partei" for a Fraktion

**Sprechrolle**:
The capacity in which a speaker gives one speech, e.g. Bundesminister, Staatsministerin, Bundesratsmitglied. It belongs to the speech, never to the person, and does not change the speaker's parliamentary membership.
_Avoid_: "Regierung" as a Fraktion or Partei, role as a person attribute

**Person**:
One human being, the same across Wahlperioden, offices and data sources. Every MdB and every Redner is a Person.
_Avoid_: speaker or MP as the identity, one record per Wahlperiode

**Mandat**:
A Person's seat in the Bundestag over a date range. A Person who is re-elected holds one Mandat per Wahlperiode.
_Avoid_: treating "is an MdB" as a permanent fact about a Person

**MdB**:
A Person during one of their Mandate (Mitglied des Bundestages, Abgeordnete/Abgeordneter). A Person without a current Mandat is not an MdB, even if they were one earlier.
_Avoid_: MP, member (unqualified), "Abgeordnete" for anyone who speaks

**Redner**:
A Person giving a Rede in a Sitzung: an MdB or a member of the Bundesregierung or the Bundesrat. Being a Redner implies no Mandat.
_Avoid_: MP, MdB for every speaker

**Personenkennung**:
An identifier a source assigns to exactly one Person and keeps for them, such as the Bundestag's Redner-ID in the Plenarprotokoll or DIP's Person-ID. Two records sharing a Personenkennung describe the same Person. An identifier that was itself found by searching for a name is not a Personenkennung but the result of a Namensabgleich.
_Avoid_: treating a name, a Zusammenschluss or a profile link as proof of identity

**Namensabgleich**:
Treating two records as the same Person because their name and Zusammenschluss match. It is a guess, never proof: names and Zusammenschlüsse change, and namesakes exist. It may join records only when exactly one record on each side matches and no Personenkennung contradicts it.
_Avoid_: name match as identity, merging every record in a group of namesakes

**Zusammenführung**:
Joining records from different sources into one Person: by a shared Personenkennung, otherwise by Namensabgleich. A Person whose records could not be joined appears split, which is preferable to two Persons shown as one.
_Avoid_: deduplication (the records are not copies), merging on a guess to fill a page

**Personenseite**:
The page for one Person who holds a current Mandat or has given at least one Rede. Only a Person with a current Mandat is shown as an Abgeordnete or Abgeordneter; everyone else is shown as a Redner, with the Sprechrolle they spoke in.
_Avoid_: calling every Personenseite an Abgeordnetenprofil, "Abgeordnete" as the heading for all Redner

### Sittings and their records

**Wahlperiode**:
The term of one elected Bundestag, from its constituent Sitzung to the constituent Sitzung of the next (Art. 39 GG), numbered consecutively (WP 21). Sitzungen, Drucksachen and Zusammenschlüsse are all numbered or recognised within one Wahlperiode.
_Avoid_: legislature, Legislaturperiode (colloquial), session

**Sitzung**:
One plenary meeting of the Bundestag, numbered within its Wahlperiode (the 94th Sitzung of WP 21). A Sitzung exists from the moment it is held, whether or not its record has been published yet.
_Avoid_: session, sitting day, "protocol" for the meeting

**Sondersitzung**:
A Sitzung convened outside the scheduled Sitzungswochen, for example because a third of the members, the Bundespräsident or the Bundeskanzler demands it (Art. 39 (3) GG). It is numbered in the same sequence as every other Sitzung and counts like any other.
_Avoid_: treating it as a separate kind of record or leaving it out of counts

**Plenarprotokoll**:
The official verbatim record of exactly one Sitzung, numbered Wahlperiode/Sitzungsnummer (21/94). A later Berichtigung amends the same Plenarprotokoll rather than creating a new one.
_Avoid_: "protocol" on its own, Stenografischer Bericht (only as its formal title)

**Dossier**:
This project's assembled account of one Sitzung: its Tagesordnungspunkte, Reden, Drucksachen and Abstimmungen, built from its Plenarprotokoll together with DIP data, and shown as one page. A Dossier can exist only once the Plenarprotokoll is published, and a build may make Dossiers for only some of the Sitzungen it knows of.
_Avoid_: report, entry, Sitzungsseite, Protokoll-Dossier, using it for the Plenarprotokoll itself

**Sitzung mit Dossier**:
A Sitzung this project has a Dossier for. Every count this project publishes — Redeanteil, Abweichung, Fakten and the like — ranges over Sitzungen mit Dossier only; a Sitzung without a Dossier is not counted as zero, it is absent.
_Avoid_: erfasste Sitzung ("erfasst" already names Presentation states and incomplete Fakt periods), implying a count covers every Sitzung held

**Rede**:
One contribution for which a Redner is given the floor, as the Plenarprotokoll records it. It covers only that Redner's own words, not the Sitzungsleitung's words or Zwischenfragen recorded within it.
_Avoid_: Wortbeitrag (too broad), counting a whole protocol section as one Redner's text

**Zwischenfrage**:
A question or remark another MdB makes during a Rede with the Redner's consent. It belongs to the MdB who asks it, not to the Redner.
_Avoid_: counting it as part of the Rede

**Zwischenruf**:
A remark called out from the floor during a Rede without being given the floor or asking the Redner's consent; the Plenarprotokoll records it in parentheses, with its author and Zusammenschluss where known. It is neither a Rede nor a Zwischenfrage, and it belongs to whoever called it out.
_Avoid_: Zwischenfrage, counting it as part of the Rede, Kommentar

**Sitzungsleitung**:
What the presiding Präsident or Vizepräsident says while chairing a Sitzung: giving the floor, Ordnungsrufe, procedural remarks. It is never a Rede; a Präsident who speaks from the lectern gives a Rede like any other Redner.
_Avoid_: attributing chairing remarks to the Redner or counting them as speeches

**Gastansprache**:
An address to the Bundestag by an invited guest, such as a foreign head of state or a speaker at a Gedenkstunde. It is shown with its Sitzung but is not a Rede: it counts toward no speech total and no Zusammenschluss.
_Avoid_: Gastrede, counting it as a Rede

**Sitzungswoche**:
A week the Ältestenrat schedules for plenary work in the Bundestag's Sitzungskalender. It is a plan, not a record: a Sondersitzung can fall outside any Sitzungswoche. A week with only a Sondersitzung is sitzungsfrei in the Sitzungskalender, yet a Kalenderwoche this project reports on.
_Avoid_: Plenarwoche, Tagungswoche; using it for a week this project reports on

**Kalenderwoche**:
The ISO calendar week, and this project's primary reporting period; a few metrics report by calendar month instead. A Kalenderwoche counts only if at least one Sitzung was held in it, whether or not it was a Sitzungswoche.
_Avoid_: sitting week, Plenarwoche, "Sitzungswoche" for this period

### Parliamentary business

**Tagesordnungspunkt**:
One item on the Tagesordnung of one Sitzung, including a Zusatzpunkt added to it. Every Rede is given under exactly one Tagesordnungspunkt, and that Tagesordnungspunkt is what the Rede addresses. One Tagesordnungspunkt can deal with several Vorgänge at once (verbundene Beratung).
_Avoid_: agenda item in public text, "Thema" for the item itself, Debatte (a Tagesordnungspunkt can pass without any Rede)

**Vorgang**:
One parliamentary procedure as DIP records it, such as a Gesetzgebung or an Antrag, from its first Drucksache to its conclusion. A Vorgang can be dealt with under several Tagesordnungspunkte in several Sitzungen (erste Beratung, then zweite und dritte Beratung). A Rede is never attributed to a Vorgang: it addresses its Tagesordnungspunkt, whichever Vorgänge that Tagesordnungspunkt deals with.
_Avoid_: bill (only Gesetzgebung is legislation), proceeding in public text, crediting a bundled Tagesordnungspunkt's Reden to one of its Vorgänge

**Vorgangsposition**:
One step in a Vorgang as DIP records it, such as a Beratung in a Sitzung or a Beschlussempfehlung, citing the Drucksache or Plenarprotokoll pages it rests on. A Vorgangsposition is how a Tagesordnungspunkt is linked to a Vorgang.
_Avoid_: position (unqualified), treating it as a Vorgang

**Drucksache**:
An official printed paper of the Bundestag, numbered Wahlperiode/number (21/1234): a Gesetzentwurf, Antrag, Beschlussempfehlung, Bericht and the like. A Vorgang usually spans several Drucksachen.
_Avoid_: document (unqualified), confusing it with a Plenarprotokoll

**Gesetzgebung**:
A Vorgang whose DIP Vorgangstyp is Gesetzgebung: the procedure on one Gesetzentwurf, whether it ends in a Gesetz, is rejected, is withdrawn or lapses at the end of the Wahlperiode. Only a Gesetzgebung is legislation. An Entschließungsantrag or Antrag that accompanies it is a separate Vorgang, and a Rechtsverordnung is not a Gesetzgebung even when the Bundestag must consent to it. In public text a Gesetzgebung is called a Gesetzesvorhaben.
_Avoid_: Gesetz for a Gesetzgebung, bill, deciding by whether "Gesetz" appears in a title (Anträge, Aktuelle Stunden and Wahlen that cite the Grundgesetz are not legislation)

**Gesetzentwurf**:
The Drucksache that proposes a Gesetz and opens a Gesetzgebung. Its title usually reads "Entwurf eines Gesetzes …" or names the Gesetz it would become.
_Avoid_: Gesetz for the proposal

**Gesetz**:
What a Gesetzgebung produces once the Gesetzentwurf has passed the Bundestag and the Bundesrat stage and has been verkündet. Most Gesetzgebungen shown on the site are not Gesetze yet, and some never will be.
_Avoid_: Gesetz for a Gesetzgebung still underway or failed

**Thema**:
What a Tagesordnungspunkt is about, in readers' words: the title of the Vorgang it chiefly deals with, preferring a Gesetzgebung, else its heading in the Plenarprotokoll without procedural boilerplate. Where it deals with several Vorgänge of equal weight, all their titles name it alike. Thema only names a Tagesordnungspunkt; it never decides which Vorgang a Rede counts for.
_Avoid_: topic as a counting unit, "lead Vorgang" as an attribution rule

### Votes

**Abstimmung**:
A decision the Bundestag takes by voting in a Sitzung, by any method: Handzeichen, Aufstehen oder Sitzenbleiben, Hammelsprung or namentlich.
_Avoid_: "vote" on its own

**Namentliche Abstimmung**:
An Abstimmung in which each MdB's Stimme is recorded by name. It is the only kind with a per-MdB record and the only kind this project holds.
_Avoid_: roll-call vote, "vote" for this specifically

**Wahl**:
An election held by the Bundestag, such as the Kanzlerwahl, usually secret and sometimes with Namensaufruf. It is not a namentliche Abstimmung and records no Stimme per MdB.
_Avoid_: calling it an Abstimmung

**Abstimmungsgegenstand**:
The exact text a namentliche Abstimmung decides on. Every Stimme answers it: when it is a Beschlussempfehlung that recommends rejecting an Antrag, Ja means rejecting the Antrag.
_Avoid_: reading Ja as support for the Antrag behind a Beschlussempfehlung

**Stimme**:
One MdB's recorded result in one namentliche Abstimmung: Ja, Nein, Enthaltung, ungültig or nicht abgegeben.
_Avoid_: vote (for the single entry)

**nicht abgegeben**:
The Stimme recorded for an MdB who cast no voting card. It says nothing about whether the MdB was in the room.
_Avoid_: abwesend, absent, "hat nicht teilgenommen" as a claim about presence

**entschuldigt**:
An MdB the Plenarprotokoll lists among the Entschuldigte Abgeordnete of a Sitzung. It is the only published statement about an MdB's absence; the Anwesenheitsliste itself is not published.
_Avoid_: abwesend (for anyone not listed), inferring presence from a Stimme

**Mehrheitsvotum**:
The Stimme most MdBs of one Zusammenschluss gave in a namentliche Abstimmung, among Ja, Nein and Enthaltung. There is none when two of them tie or when no MdB of the Zusammenschluss voted.
_Avoid_: Fraktionslinie, Fraktionsdisziplin, "Votum der Fraktion" (implies a group decision we cannot see)

**Abweichung**:
A Stimme of Ja where the Mehrheitsvotum of the MdB's Zusammenschluss is Nein, or of Nein where it is Ja. An Enthaltung or a Stimme nicht abgegeben is never an Abweichung, and where the Mehrheitsvotum is Enthaltung or there is none, no Stimme is. A fraktionslos MdB has no Zusammenschluss and so cannot make one.
_Avoid_: Enthaltung as a vote against the group, "Abweichung" for a fraktionslos MdB voting unlike other fraktionslose, "gegen die Linie" or "gegen die eigene Fraktion" (implies a group decision we cannot see, and leaves out Gruppen)

**Abweichler**:
An MdB who makes an Abweichung in a namentliche Abstimmung. In public text this is said as "stimmt anders als die Mehrheit der eigenen Fraktion oder Gruppe".
_Avoid_: Dissident, Rebell; Fraktionslinie in public text

### Counting speeches per Zusammenschluss

**Zählung nach Sprechrolle**:
The default way this project counts speeches per Zusammenschluss: a speech given in a Sprechrolle (Bundesregierung, Bundesrat) counts for that side and toward no Zusammenschluss; every other speech counts for the Zusammenschluss the Plenarprotokoll names beside the speaker, or, where it names none, for the speaker's Zugehörigkeit on the date of the Sitzung.
_Avoid_: Zurechnungsregel, counting ministers for "Regierung" as if it were a Fraktion

**Anrechnung**:
The Bundestag's own bookkeeping rule, agreed by the Ältestenrat each Wahlperiode: speaking time used by members of the Bundesregierung or the Bundesrat is charged to the Fraktion of their Partei, except in the Aktuelle Stunde. It concerns speaking time, not the speech itself, and a metric that follows it must say so.
_Avoid_: Zurechnung, attribution (for the official rule)

### Puls

**Redeanteil**:
A share of Reden by number, always within a stated scope: a Tagesordnungspunkt's Redeanteil an der Sitzung, a Zusammenschluss's Redeanteil an der Woche. It says nothing about how long anyone spoke.
_Avoid_: Redeanteil for a share of characters, Redeanteil without its scope, Redezeitanteil (speaking time is not measured)

**Textanteil**:
A share of the characters of Rede text within a stated scope. Characters are not speaking time.
_Avoid_: Redeanteil, Redezeit, "nach Zeichen" under a Redeanteil heading

**Redeanteil je Zusammenschluss**:
The Redeanteil of each Zusammenschluss under Zählung nach Sprechrolle. Reden in the Sprechrolle of the Bundesregierung and of the Bundesrat are two separate rows outside the Zusammenschlüsse, and Reden by fraktionslose MdBs a row of their own.
_Avoid_: Redeanteil der Fraktionen (Gruppen are not Fraktionen), "Regierung" as a Fraktion row, one row for Bundesregierung and Bundesrat together

**Rangfolge nach Reden**:
Tagesordnungspunkte ordered by their number of Reden, within one Sitzung or one Kalenderwoche. It shows where the most Reden were given, which mostly follows the debate length agreed in advance, not how much attention a subject drew.
_Avoid_: Aufmerksamkeitsrang, Aufmerksamkeitsranking, ranking by Zeichen

**Wochenradar**:
The top of the Rangfolge nach Reden of one Kalenderwoche across all its Sitzungen, each row a Tagesordnungspunkt named by its Thema. Question formats such as the Fragestunde and the Befragung der Bundesregierung are listed apart but still count toward the week's Reden. A Vorgang dealt with under two Tagesordnungspunkte in one week appears as two rows.
_Avoid_: "Themen" as the unit counted, merging rows by Vorgang, copying the Sitzung ranking of a dossier

**Wochenvergleich**:
The comparison of one Kalenderwoche with the nearest earlier Kalenderwoche that had a Sitzung, at most twelve weeks back; if the nearest one is further back, there is no Wochenvergleich. When the two hold different numbers of Sitzungen, every figure is compared per Sitzung.
_Avoid_: Vorwoche (the compared week can be weeks earlier), comparing raw totals of weeks with different numbers of Sitzungen

### Acquisition and publication

**Publication domain**:
One of the seven named areas of data a build publishes — catalog, dossiers, votes, profiles, roster, bills, summaries — each carrying its own Acquisition state and Presentation state.
_Avoid_: domain (unqualified; conflicts with the bounded-context sense of "domain")

**Acquisition state**:
Whether one attempt to fetch a Publication domain's data got everything it went looking for: not_requested, complete, partial or failed. Recorded once per Publication domain per build, and additionally per Sitzung for its votes.
_Avoid_: "complete" alone — the word also names unrelated things elsewhere in this codebase (see TODOS.md); fetch status, download state

**Presentation state**:
The public-facing state shown for a Publication domain — ready, domain_empty, partial, unavailable or omitted — derived from its Acquisition state and record count, never set directly.
_Avoid_: acquisition state (Presentation state is what the public sees; Acquisition state is the pipeline's own record of what happened)

**Completeness basis**:
The per-Sitzung signal a metric's period must be complete for: votes (that Sitzung's votes Acquisition state) or speeches (that Sitzung's Plenarprotokoll XML was parsed, including agenda-item times, not only its Reden). Declared per metric.
_Avoid_: coverage (also names the archive span behind the "all" baseline, and the same word other code uses for unrelated week/radar display flags), coverage domain, domain

**Sitzung completeness**:
Whether one Sitzung's data can be trusted for a given Completeness basis, derived from Acquisition state: for votes, that Sitzung's votes Acquisition state is exactly complete, or it carries no votes acquisition record at all; for speeches, a parsed Plenarprotokoll report exists for it. A Sitzung with no report is never complete.
_Avoid_: "complete" alone, treating this as a status parallel to (rather than derived from) Acquisition state

**Period completeness**:
Whether every Sitzung the store holds for a period — a Kalenderwoche or a calendar month — has Sitzung completeness for a metric's Completeness basis; the current or a later calendar month is additionally never complete, however complete its sittings so far, and no such running-period rule applies to weeks. A period needs this to be observed and enter a Vergleichsbasis, but it alone does not guarantee publication. A Sitzung without a Dossier — such as one whose Dossier could not be built — is invisible to this check rather than counted against it, a known gap tracked in TODOS.md.
_Avoid_: week completeness (calendar months use the same rule), "complete" alone, treating this as sufficient for publication

### Fakt der Woche

**Kennzahl**:
One registered measure the Fakt der Woche rule runs on, such as the closest namentliche Abstimmung of a period. Each Kennzahl has a direction (a higher or a lower value is more unusual) and a period, a Kalenderwoche or a calendar month.
_Avoid_: metric in public text

**Beobachtung**:
One Kennzahl's value in one period: its most extreme case, or for some Kennzahlen a count or the largest total per Abgeordnete or Vorgang. A period without Period completeness has no Beobachtung, and neither does a complete period with nothing to measure, such as a week without a namentliche Abstimmung. Whether a Beobachtung is published is a separate question: most are not.
_Avoid_: calling every Beobachtung a Fakt

**Vergleichsbasis**:
The earlier Beobachtungen of the same Kennzahl that a Beobachtung is compared with: those of its own Wahlperiode once they reach the Mindesthistorie, otherwise every earlier one in the archive. Only periods before the observed one count, so a later period never changes an earlier comparison.
_Avoid_: baseline in public text, "the current Wahlperiode" (a 2023 week is compared within WP 20), comparing with later periods

**Perzentil**:
The share of its Vergleichsbasis that a Beobachtung beats in its Kennzahl's direction. A tie does not count as beaten. Readers see it as a percentage, never under this name.
_Avoid_: rank, reading it as the share of all periods ever

**Mindesthistorie**:
The number of earlier Beobachtungen a Vergleichsbasis needs: eight Kalenderwochen or six calendar months. The fallback to the whole archive needs it too; a Beobachtung with too few earlier ones either way is "noch nicht vergleichbar".
_Avoid_: floor (names three different thresholds in this codebase); in public text, Vergleichbarkeit

**Veröffentlichungsschwelle**:
The Perzentil a Beobachtung must reach to be published, the same for every Kennzahl.
_Avoid_: floor, threshold (unqualified)

**Mindestwert**:
An absolute value some Kennzahlen require before a Beobachtung can be published, however unusual it is, such as a minimum number of Abweichler.
_Avoid_: floor, min value in public text

**Fakt**:
A Beobachtung that is published: comparable, at or above the Veröffentlichungsschwelle and any Mindestwert, and with a Thema where its Kennzahl needs one. A period can have several Fakten or none. Fakten of the monthly Kennzahlen appear as Fakt des Monats, under the same Fakt der Woche rubric.
_Avoid_: "Fakt" for a withheld Beobachtung, one Fakt per period

**Rang**:
The order of a period's Fakten: the higher Perzentil first, a fixed order of Kennzahlen breaking ties. Shown to readers as Platz.
_Avoid_: using Perzentil and Rang interchangeably

**zurückgehalten**:
The state of a Kennzahl in a period with Period completeness that yields no Fakt, shown to readers by one reason: nicht messbar, noch nicht vergleichbar, zu wenige, um daraus einen Fakt zu machen, Thema nicht bestimmbar, or nicht ungewöhnlich genug. A period without Period completeness is not zurückgehalten but unvollständig erfasst.
_Avoid_: rejected, hidden, suppressed; "zurückgehalten" in public text (readers see only the reason)

**Hinweis**:
A fixed caution some Kennzahlen must carry wherever their Fakt is shown, such as that more namentliche Abstimmungen in a week make a close one likelier.
_Avoid_: footnote, disclaimer

**Karte**:
The shareable image of exactly one Fakt, naming its subject and its Perzentil against its Vergleichsbasis; its Belege are on the Fakt's page, not on the Karte. Later periods never change a Karte; a correction to the data or a change to the rule can.
_Avoid_: card in public text, one Karte per period

**Beleg**:
One record a Fakt rests on: a Rede, Abstimmung, Tagesordnungspunkt, Plenarprotokoll or Drucksache. A Fakt about one record has it as its first Beleg, which Drucksachen may support; a Fakt that counts Reden or Tagesordnungspunkte rests on all of them equally.
_Avoid_: Quelle (names this site's data sources), receipt in public text
