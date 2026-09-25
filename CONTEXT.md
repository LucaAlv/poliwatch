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

### Sittings and their records

**Sitzung**:
One plenary meeting of the Bundestag, numbered within its Wahlperiode (the 94th Sitzung of WP 21). A Sitzung exists from the moment it is held, whether or not its record has been published yet.
_Avoid_: session, sitting day, "protocol" for the meeting

**Plenarprotokoll**:
The official verbatim record of exactly one Sitzung, numbered Wahlperiode/Sitzungsnummer (21/94). A later Berichtigung amends the same Plenarprotokoll rather than creating a new one.
_Avoid_: "protocol" on its own, Stenografischer Bericht (only as its formal title)

**Rede**:
One contribution for which a Redner is given the floor, as the Plenarprotokoll records it. It covers only that Redner's own words, not the Sitzungsleitung's words or Zwischenfragen recorded within it.
_Avoid_: Wortbeitrag (too broad), counting a whole protocol section as one Redner's text

**Zwischenfrage**:
A question or remark another MdB makes during a Rede with the Redner's consent. It belongs to the MdB who asks it, not to the Redner.
_Avoid_: counting it as part of the Rede

**Sitzungsleitung**:
What the presiding Präsident or Vizepräsident says while chairing a Sitzung: giving the floor, Ordnungsrufe, procedural remarks. It is never a Rede; a Präsident who speaks from the lectern gives a Rede like any other Redner.
_Avoid_: attributing chairing remarks to the Redner or counting them as speeches

**Gastansprache**:
An address to the Bundestag by an invited guest, such as a foreign head of state or a speaker at a Gedenkstunde. It is shown with its Sitzung but is not a Rede: it counts toward no speech total and no Zusammenschluss.
_Avoid_: Gastrede, counting it as a Rede

**Sitzungswoche**:
A week the Ältestenrat schedules for plenary work in the Bundestag's Sitzungskalender. It is a plan, not a record: a Sondersitzung can fall outside any Sitzungswoche.
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

### Counting speeches per Zusammenschluss

**Zählung nach Sprechrolle**:
The default way this project counts speeches per Zusammenschluss: a speech given in a Sprechrolle (Bundesregierung, Bundesrat) counts for that side and toward no Zusammenschluss; every other speech counts for the Zusammenschluss the Plenarprotokoll names beside the speaker, or, where it names none, for the speaker's Zugehörigkeit on the date of the Sitzung.
_Avoid_: Zurechnungsregel, counting ministers for "Regierung" as if it were a Fraktion

**Anrechnung**:
The Bundestag's own bookkeeping rule, agreed by the Ältestenrat each Wahlperiode: speaking time used by members of the Bundesregierung or the Bundesrat is charged to the Fraktion of their Partei, except in the Aktuelle Stunde. It concerns speaking time, not the speech itself, and a metric that follows it must say so.
_Avoid_: Zurechnung, attribution (for the official rule)

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
Whether every Sitzung the store holds for a period — a Kalenderwoche or a calendar month — has Sitzung completeness for a metric's Completeness basis; the current or a later calendar month is additionally never complete, however complete its sittings so far, and no such running-period rule applies to weeks. A period needs this to be observed and enter a baseline, but it alone does not guarantee publication. A Sitzung missing from the store entirely — such as one whose dossier fetch failed — is invisible to this check rather than counted against it, a known gap tracked in TODOS.md.
_Avoid_: week completeness (calendar months use the same rule), "complete" alone, treating this as sufficient for publication
