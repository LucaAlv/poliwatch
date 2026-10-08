# B4: daily-view Abstimmungen

Planning snapshot: 2026-10-07, main `0e50977`; inspected B3 branch
`feat-politikfelder` through `6c4d41c`. B3 and A2 follow-ups are still in progress.
This document starts B4 planning; it does not mark B4 implemented or validated.

## Existing pieces and ownership

| Piece | Evidence in the inspected code | B4 work |
| --- | --- | --- |
| Outcome, recommendation inversion, sources | B1 `interpret_vote`, `derive.vote_outcome`, `render_result_badge`, document/XLSX links | Reuse; retain raw Ja/Nein and provenance |
| Topic navigation | B3 archive chips, combined Fraktion/Politikfeld filter, `?politikfeld=` links | Integrate and verify; no second filter |
| Vorgang context acquisition | B3 `fetch_vorgaenge`, `vorgang_cache_record`, Drucksache-number resolution | Reuse cache's `abstract`; avoid extra requests for the same record |
| Context persistence | B3 stores `proceedings.sachgebiet`, but not `abstract` | Add raw abstract and its attributable source; include vote-only resolved Vorgänge |
| Abweichler | `r3-abweichler` SQL and `CONTEXT.md` define the rule | Show qualifying members per vote and Zusammenschluss |
| Profile links | Current main resolves roll-call occurrence IDs to internal person pages, with validated external fallback | Reuse final B2/A2 lookup; no identity-policy changes |
| Committee | `compact_drucksache_position` retains `urheber`; vote 1002 fixture names the Finanzausschuss | Verify source shape and attribution before selecting a field |

The roadmap's B2 heading still says external profiles only; main's merged B2
implementation now supports internal pages. B4 follows the merged behavior.

## Slice 1: named Abweichler

- Normalize fraction rows with `derive.merge_fractions` and member factions with
  `derive.zusammenschluss`. Compute the Mehrheitsvotum from reported fraction
  counts with `derive.majority_vote`, as persistence does. Do not trust cached
  `leading_vote` or derive a new majority from a partial member list.
- Include only Ja versus a Nein majority, or Nein versus a Ja majority. Exclude
  fraktionslos, unknown affiliation, abstentions, uncast votes, ties and
  abstention majorities. Recognized Gruppen follow the same rule as Fraktionen.
- Render a compact list per qualifying Zusammenschluss near its tally, using
  “Anders als die Mehrheit der eigenen Fraktion oder Gruppe”. Reuse the current
  occurrence-key/profile-link path and escaped names. Keep the full Einzelstimmen.
- Separate “no qualifying member” from missing individual-vote data. Partial
  acquisition must retain its warning and cannot establish a complete zero.
- Inversion changes the meaning of Ja/Nein, not who differs from their group's
  recorded majority. No second inversion of the dissent rule.

Checks: opposite Ja/Nein, ties/abstention/no-voters, fraktionslos/unknown,
group spelling variants, partial or missing members, profile-link fallback,
and inverted recommendation. Compare a complete fixture's qualifying set with
the store-side `r3-abweichler` predicate, without the recipe's top-five limit.

## Slice 2: context and committee after the B3 handoff

- Reuse B3's `vorgaenge` and `dokumentnummern` cache. Resolve the vote's own
  Drucksachen to Vorgänge; a bundled TOP's lead Vorgang alone is insufficient
  evidence for assigning context to every vote beneath it.
- Store the raw DIP abstract on the Vorgang. Retain the vote-to-document-to-
  Vorgang association needed to reproduce the selection from the release.
  Use existing relations where they suffice; add only the missing association.
- Present an attributable abstract as “Zum Vorhaben · Quelle: DIP”, alongside
  the distinct vote outcome and exact Abstimmungsgegenstand. Do not rewrite a
  procedure-wide abstract into a claim about this vote. Preserve the full source
  text through a native disclosure if it is too long for the panel.
- For multiple associated Vorgänge, label contexts separately or show an honest
  ambiguity note. A related motion's abstract must not describe a vote on an
  amendment or another document without evidence of that relationship.
- Inspect source-backed Beschlussempfehlung fixtures for responsible committee
  metadata. Prefer structured data on the matched recommendation; distinguish
  federführend from mitberatend. Carry the name, role and source document into
  persistence/export. Missing or ambiguous evidence gets an explicit note.
- Rendering must work offline, retain validated source links, and produce the
  same selection across repeated TOP links and sitting-level votes.

Checks: attributable abstract, absent/failed cache entry, bundled TOP with
different votes, amendment context, multiple Vorgänge, matched/unmatched
recommendation, committee roles, fresh/incremental migration, unchanged offline
replay, export round trip, and B1 outcome regression fixtures.

## Completion and deferred dependency

B4's source-backed slices are ready when topic filtering finds a vote and its
panel shows attributable proposal context, outcome, group tallies, named
Abweichler, responsible committee where known, and sources, with honest gaps.
Verify desktop/mobile readability and filter behavior after integration. For
live browser diagnostics, use the project's Chrome DevTools driver.

Run focused tests while implementing, then the repository suite on the final
integrated base:

```sh
/opt/miniconda3/bin/python3.13 -m unittest discover -s tests
```

The labelled AI fallback remains open until the deterministic validators TODO
is implemented. Missing abstracts must say so in this first slice. Do not call
the entire B4 TODO complete while that explicitly requested fallback remains
deferred. XLSX ingestion (B5), date filters, a new vote-detail route and the full
dataset/site split are outside this change.
