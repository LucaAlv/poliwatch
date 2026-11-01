---
status: accepted
---

# The Präsident, Vizepräsidenten and the Alterspräsident have no Sprechrolle of their own

A member of the Bundestag who holds the office of Präsident, Vizepräsident(in) or Alterspräsident is not given an additional Sprechrolle because of that office. When they take part in a debate as an Abgeordneter, their Rede counts for their Zusammenschluss, like any other MdB's (ADR 0001). What they say while exercising the Sitzungsleitung is never a Rede and is excluded. That includes the turns that WP 18/19 XML prints inside another speaker's `<rede>`. Official addresses given on behalf of the Bundestag, for example a Gedenkstunde opened by the Präsident, are told apart from ordinary debate contributions and are not counted as Reden of a Fraktion automatically.

Decided 2026-10-20 by the project owner. The option, cross-checked with Codex, and its wording are the owner's. It was found in the A3 pilot ([a3-pilot.md](../plans/a3-pilot.md)). WP 20/21 XML marks the chair with a `<name>` element, which the parser already treats as Sitzungsleitung. WP 18/19 XML instead marks the chair inside a member's `<rede>` with a `<p klasse="redner">` marker whose `<rolle_lang>` is Präsident, Vizepräsident(in) or Alterspräsident. That covers, for example, Lammert's floor-giving in 18/100 and Solms and Schäuble at the constituent sitting 19/1.

## Considered Options

- **For the Fraktion (chosen).** CONTEXT.md already says a Präsident at the lectern "gives a Rede like any other Redner"; the office is held by an MdB of a Zusammenschluss.
- **A weitere Sprechrolle (rejected).** It would have treated the presidium as an organ of the Bundestag, like the Wehrbeauftragte, and taken their debate Reden out of their Zusammenschluss.

## Consequences

- `SPRECHROLLE_RULES` gets no presidium rule. A presidium role on a marker is evidence of Sitzungsleitung: it is never mapped to a side.
- The WP 18/19 extension of speech rule 5 classifies those markers as Sitzungsleitung (excluded). An official address on behalf of the Bundestag needs its own detection and treatment. Until that exists, such a turn is refused rather than counted as a Fraktionsrede.
