# A1 / A2 coordination contract

A1 is implemented on `a1-followups`; Claude owns A2 on `right-counts`.

A1 retains schema 3, key version 1, all native Rede/contribution keys, and the existing registry resolution boundary. It does not change `person_registry.py` or A2's `upsert_mp` behavior.

- A nested segment uses `rede_id = nested:<containing native rede ID>:<speaker-marker ordinal>`. The ordinal includes every source marker, including resumptions. `parent_rede_id` names its containing source unit (Rede or Beitrag). It is passed through the existing `contribution_occurrence_id` function; native and flat-turn key vectors remain unchanged.
- Explicitly typed written annex submissions use their native rede ID. An ID-less annex uses `annex:<annex-block ordinal>:<rede ordinal>`. A report's top-level `xml_contributions` holds submissions with no unambiguous source TOP. These persist with `agenda_item_id = NULL` and use source item index 0.
- The optional `speech_rule_inputs(protocol_id, version)` table records the version on each actually persisted report. It neither replaces A2's schema version nor uses the distribution-copy PRAGMA sentinel. Missing/stale records prevent output; low-level persistence remains available for repair.
- Sitting-level contributions traverse the same source-role checks and `resolve_speaker` boundary. Contribution-only people qualify for pages through persisted contribution bindings. Silent askers receive an XML ID only from a unique source candidate, with ambiguous names kept unresolved.

A2's ongoing changes to registry evidence and `upsert_mp` can be overlaid for scratch integration without altering this contract. Final merged-branch readiness must wait for Claude's completed A2 commit and combined validation. Never copy an in-progress registry into the reference store.

On 2026-10-05 the user reported Claude's three-day usage-limit pause and instructed A1 to finish without waiting. No new registry decision is required by A1. The in-progress A2 overlay is validated now; final merged validation is tracked as a P1 TODO before A3. This handoff has not been reviewed by Claude.
