# Partition removal and profile ownership

Implement the correction-removal decision in “A.2 third ship round: deferred findings” (1), after 01 lands.

Own the partition correction lifecycle in `person_registry.py`, `person_corrections.json` contract documentation and focused correction tests. Read `partition_identity`, `bind`, `corrected_speaker`, reconciliation and profile-owner selection.

1. Reproduce: build with the Föhr/Mende-style partition and shared profile, remove the correction, replay. Examine bindings, record partition, evidence flags, aliases, page heading and external profiles.
2. Resolve the contract explicitly. The current documented rule makes applied partitions durable. Prefer retaining enough durable partition/profile-owner metadata to keep removed file entries from restoring a shared profile to the wrong person. If a different policy is required for correctness, document why and implement its replay/key consequences consistently.
3. Exercise partition removal, label edits, profile-owner edits, adding a partition to an existing registry, and repeated replay. Distinguish ordinary attribute refresh from reviewed correction changes. Raw cached evidence remains unchanged.
4. Pin profile attribution and grouping across permutations and incremental replay. Compare fresh replay only under the same effective correction history: a fresh registry without a formerly applied correction is intentionally a different history under a durable policy.

Done when partition history and profile ownership agree after file edits, replay is a fixed point, and docs state how a deliberate undo works. Keep assignments/splits disabled.
