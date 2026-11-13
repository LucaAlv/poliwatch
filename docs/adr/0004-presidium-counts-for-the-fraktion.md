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

## Amendment 2026-11-13: three kinds, a reviewed list, and the procedural turns

Decided by the owner as Q13 A (2026-11-06, [v1-scope-review.md](../plans/v1-scope-review.md)) and built from [adr-0004-presidium-kinds.md](../plans/adr-0004-presidium-kinds.md), whose census read every candidate in WP 18-21. A `<rede>` whose owner carries a presidium role is one of three kinds:

- **Fraktionsrede**: a Vizepräsident(in) printed with a Fraktion speaks for it (unchanged, `mark_presidium_fraktionsreden`).
- **Ansprache**: an address given for the Bundestag, or by a guest or another constitutional organ at a ceremonial or joint sitting. A Beitrag of Kind `ansprache`, shown with the printed role, counted in no Reden figure and for no side. One kind for presidium and guest addresses: their treatment is the same, and the role on the card says in what capacity the speaker spoke.
- **Sitzungsleitung**: chairing printed as a `<rede>` of its own. Not stored; recorded as a procedural turn.

The code cannot tell an address from a debate Rede or from chairing, so the kind of each case is reviewed data: `scripts/reviewed_units.json`, keyed by sitting and source `<rede>` id, with the owner's Redner-ID as the proof of identity. A third list kind, `procedural`, covers the acceptance of an election and the answer to an oath where the protocol prints them as the elected or sworn person's own `<rede>`: they are no contribution to a debate (ADR 0002), and 82 of them were counted as Reden in the 718 kept sittings.

Nothing is counted unread. A presidium `<rede>` the list does not name (a Präsident(in) or Alterspräsident(in) printed with a Fraktion included, since only the Vizepräsident role is stripped), and a short `<rede>` that reads like an oath answer or an acceptance but is not listed, are withheld with the Rede named (reason `unreviewed_presidium`, ADR 0005); the sitting stays. The list is the one file ADR 0005 introduced for withheld units: a stale entry stops the run, as a malformed list does, because the list and not the source needs correcting, and an edit re-reads exactly the sittings it touches. A guest role no Sprechrolle rule maps still fails the Sprechrolle check unless the guest's `<rede>` is listed as an Ansprache.
