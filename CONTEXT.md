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

### Counting speeches per Zusammenschluss

**Zählung nach Sprechrolle**:
The default way this project counts speeches per Zusammenschluss: a speech given in a Sprechrolle (Bundesregierung, Bundesrat) counts for that side and toward no Zusammenschluss; every other speech counts for the speaker's Zugehörigkeit on the day of the speech.
_Avoid_: Zurechnungsregel, counting ministers for "Regierung" as if it were a Fraktion

**Anrechnung**:
The Bundestag's own bookkeeping rule, agreed by the Ältestenrat each Wahlperiode: speaking time used by members of the Bundesregierung or the Bundesrat is charged to the Fraktion of their Partei, except in the Aktuelle Stunde. It concerns speaking time, not the speech itself, and a metric that follows it must say so.
_Avoid_: Zurechnung, attribution (for the official rule)
