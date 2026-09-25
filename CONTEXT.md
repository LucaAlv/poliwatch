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
The ISO calendar week, and the period this project reports by. A Kalenderwoche counts only if at least one Sitzung was held in it, whether or not it was a Sitzungswoche.
_Avoid_: sitting week, Plenarwoche, "Sitzungswoche" for this period

### Counting speeches per Zusammenschluss

**Zählung nach Sprechrolle**:
The default way this project counts speeches per Zusammenschluss: a speech given in a Sprechrolle (Bundesregierung, Bundesrat) counts for that side and toward no Zusammenschluss; every other speech counts for the Zusammenschluss the Plenarprotokoll names beside the speaker, or, where it names none, for the speaker's Zugehörigkeit on the date of the Sitzung.
_Avoid_: Zurechnungsregel, counting ministers for "Regierung" as if it were a Fraktion

**Anrechnung**:
The Bundestag's own bookkeeping rule, agreed by the Ältestenrat each Wahlperiode: speaking time used by members of the Bundesregierung or the Bundesrat is charged to the Fraktion of their Partei, except in the Aktuelle Stunde. It concerns speaking time, not the speech itself, and a metric that follows it must say so.
_Avoid_: Zurechnung, attribution (for the official rule)
