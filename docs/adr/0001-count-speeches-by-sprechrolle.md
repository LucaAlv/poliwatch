---
status: accepted
---

# Count speeches per Zusammenschluss by Sprechrolle, not by Anrechnung

Every per-Zusammenschluss speech metric (Redeanteil, Wochenfakt, Daten recipes) needs a rule for speeches by members of the Bundesregierung and the Bundesrat, whose protocol XML carries a `<rolle>` and no `<fraktion>`. We count such a speech for its side (Bundesregierung or Bundesrat) and toward no Zusammenschluss. Every other speech counts for the Zusammenschluss the Plenarprotokoll names beside the speaker. Where the Plenarprotokoll names none, it counts for the speaker's Zugehörigkeit on the date of the Sitzung.

No law or rule assigns a speech to a Fraktion. Members of the Bundesregierung and Bundesrat speak under their own right to be heard (Art. 43 Abs. 2 GG), not on a Fraktion's behalf. The Bundestag's Anrechnung charges only their speaking time to "the corresponding Fraktion", and it does so through an Ältestenrat agreement renewed each Wahlperiode, not the GO-BT itself. The Bundestag's own speech statistics count all plenary speeches, including those by non-MdBs, without assigning them to a Fraktion.

The Plenarprotokoll is the authority for a speaker's Zusammenschluss because it is the Bundestag's own record of that speech, and because nothing finer is available: the XML timestamps only the start and end of a Sitzung, not each speech, and Zugehörigkeit dates carry no time of day. A speech after midnight therefore belongs to the date of its Sitzung.

## Considered Options

- **Anrechnung (rejected).** It follows the official time rule, but it counts speaking time, not speeches. It depends on the debate format, since government and Bundesrat time is not charged in the Aktuelle Stunde. It also needs the Partei of speakers who are not MdBs, such as Bundesrat members, which the store does not hold.
- **Zugehörigkeit on the calendar day of the speech (rejected).** Speeches carry no timestamp, so a speech after midnight cannot be placed on its calendar day.
- **The minister's own Zugehörigkeit (rejected).** This credits a Fraktion with speeches its member gave in a capacity that is explicitly not the Fraktion's.

## Consequences

- A metric that follows Anrechnung instead must say so in its Methodik text.
- When the Plenarprotokoll's Zusammenschluss for a speaker disagrees with that speaker's Zugehörigkeit on the date of the Sitzung, the Plenarprotokoll wins and the disagreement is flagged as a data issue, never resolved silently.
- Government-side speech counts are shown as their own row, never as a pseudo-Fraktion "Regierung".
- The code does not follow this rule yet. `speaker_party_name` (`scripts/persist_dip_pulse_store.py`) writes a "Regierung" party row, and the metrics use `COALESCE(NULLIF(s.fraktion, ''), pa.name)`.

## Sources

- Art. 43 GG: https://www.gesetze-im-internet.de/gg/art_43.html
- § 35, § 44 GO-BT: https://www.gesetze-im-internet.de/btgo_2025/__35.html, https://www.gesetze-im-internet.de/btgo_2025/__44.html
- Datenhandbuch Kap. 7.8, "Wortmeldungen von Bundesratsmitgliedern" (Anrechnung for Bundesrat and Bundesminister): https://www.bundestag.de/resource/blob/196282/961c06235e2eadb15edd21132d022b1c/Kapitel_07_08_Wortmeldungen_von_Bundesratsmitgliedern.pdf
- Datenhandbuch Kap. 7.11, "Regelungen zur Debattendauer" (Ältestenrat clause per Wahlperiode, Aktuelle Stunde exception): https://www.bundestag.de/resource/blob/196288/43813c36db743e410a0c0af63cdbfa9d/Kapitel_07_11_Regelungen_zur_Debattendauer.pdf
- Datenhandbuch Kap. 7.6, "Reden im Plenum": https://www.bundestag.de/resource/blob/196278/Kapitel_07_06_Redner_im_Plenum.pdf
