# Stable IDs, person URLs and build-store backups

Build-store schema **3** and export format **2** replace insertion-order IDs with source-derived text IDs. Existing stores require explicit replay:

```bash
python3 scripts/build_dip_pulse_site.py --offline --repersist --output-dir <site-dir>
```

Plain offline rendering and direct export reject the old schema with that instruction. A registry written by an unreleased A.2 draft (no `person_records.home_person_id`) cannot be carried forward: replay a schema 2 backup to re-mint it. Online updates use the same staged rebuild, including roster ingestion and fact recomputation. A missing report for a protocol already in the store, invalid JSON, invalid corrections, corrupt registry, failed persistence, failed facts or failed integrity checks stops replacement. Restore missing evidence rather than deleting its protocol from the store.

## Key dictionary

`stable_ids.stable_key(namespace, *source)` hashes canonical UTF-8 JSON `[1, namespace, source]` with SHA-256: sorted object keys, Unicode preserved, compact separators, no non-finite numbers. Output is `<namespace>-v1-<64 hex digits>`. Types are significant. Established person keys are never regenerated from updated attributes.

| Table / field | Identity |
|---|---|
| `parties.id` | Namespace `party`, normalized name |
| `agenda_items.id` | `agenda`, protocol ID and source item index |
| `documents.id` | `document`, document number and normalized URL |
| `speeches.id` | `speech`, protocol ID and Rede ID |
| Synthetic Rede ID | `<protocol_id>:<item_index>:<sequence>` |
| `mps.id` | `mp`, compact source identity; preserved by occurrence bindings when attributes or enrichment change |
| `mps.person_id` | Issued key in `persons.id` |
| `persons.id` | Initially `person` with unique XML Redner-ID, otherwise DIP person ID; otherwise `p-000001` allocation |
| `persons.ordinal` | Durable allocation order, used for default merge survivor |
| `person_records.id` | Source-record key, retained even after its current evidence disappears |
| `person_records.home_person_id` | The durable owner of the record: its issued person key, which a merge resolves to the survivor through its alias. `person_id` is the record's current person, which `reconcile` may move to a namesake's person by a guess it recomputes |
| `person_records.evidence_json` | Indexed record's matching evidence: trusted IDs, name, party, source side and partition |
| `person_bindings.id` | Speech key, `roster` with DIP person ID, or `vote-member` with vote ID, printed member name and faction |
| `person_aliases.id` | Retired issued person key; `person_id` resolves to its survivor |
| `facts.id` | `fact`, metric ID, period kind and period key |
| `fact_sources.id` | `fact-source`, fact ID and source-entity key; independent of receipt position |
| `fact_sources.source_entity_id` | Persisted speech/document/vote/protocol key when available; otherwise a `source-reference` key for the cited official reference |
| `fact_sources.position` | Presentation order, never row identity |
| `mp_canonical.mp_id` | Source-record key referencing `mps.id`; `canonical_id` references `persons.id`; `has_page` is 1 when that person has a page |
| `datenstand.tag` | Release metadata's primary key |

Protocols, proceedings, proceeding positions and votes keep their source IDs. Junction tables keep composite keys made from stable foreign keys. Schema migration versions and metric IDs are natural keys. Every text primary key is explicitly `NOT NULL`. CSV IDs must be read as strings. `source_entity_id` is polymorphic: use `entity_kind` and the citation columns to identify its source table or official reference.

## Registry and matching

`mps` remains a compact source-identity table. `person_records`, `person_bindings`, `persons` and `person_aliases` form the durable registry and are carried forward independently of roster preservation. Occurrences bind before source-record upserts. New enrichment (name, party, profile, an id the record did not have) updates evidence while the occurrence retains its established record and person key. A source that now names a different Redner-ID or DIP id for an occurrence is not enrichment: the occurrence moves to the record of the new identity (the earlier record and its person stay issued). Evidence is re-read from the source on a record's first touch in a build, so an id the source stopped supplying cannot keep linking records; `ever_mdb` is re-derived from the record's history. The first-touch rule is per connection: the staged rebuild binds every live occurrence on one connection. Persisting a single report into an existing store is therefore not offered (`persist_dip_pulse_store.py` refuses and points to `--offline --repersist`): it committed before reconciling and re-read each touched record from that one report.

**Durable and recomputed merges.** Merges that rest on a shared Personenkennung (trusted abgeordnetenwatch id, DIP person id, Redner-ID) and reviewed merges are durable: the retired key stays as an alias of the survivor. The name-based guesses (corroborated name, unique name+party) are recomputed on every reconcile: they move a record's current person without retiring any key, so a guess that stops holding, or arrives in another order, leaves no trace. An incremental replay and a fresh replay of the same reports therefore group records identically. The guess phase (`_guess_merges`) is a pure function of the registry's rows: it matches only *live* records (a record nothing touched in the staged rebuild is stale evidence: it keeps its person and its published page but takes part in no match), but it moves whole persons, so it cannot tear a durable merge apart. A group that would join two partitions, or persons whose DIP or abgeordnetenwatch ids contradict, stays split; otherwise the person issued first keeps its key. `tests/test_registry_invariants.py` checks, over seeded random two-build sequences, that a replay is a fixed point, a reviewed merge holds, no person gets two DIP ids, and an incremental build groups occurrences like a fresh one. Two known limits: a roster record the staged rebuild did not touch is stale and takes part in no guess, so a speaker + roster pair joined by an earlier build splits again when the roster no longer lists the person; and a record's name and party are the last occurrence persisted, so a record whose occurrences print different names or parties can group differently by persist order (both in TODOS.md). A person whose only occurrence moved to another identity (a corrected Redner-ID) keeps its row but no longer has a page: its old URL is not redirected, because the source now says that evidence belonged to someone else.

**Person keys are file names.** A key must be filename-safe, must not be a reserved page name (`index`) and must not differ from an issued key only by case. `validate()` and page collection both check this.

Reconciliation runs before fact recomputation and optional page collection. It retains the existing trusted-ID, corroborated-name and conservative unique-name rules, using indexed bindings and component evidence. Matching never runs inside page collection or rendering. Biography selection prefers roster evidence, while speech and vote histories pool all records assigned to that person. Facts and SQL recipes use the persisted assignment even when MP pages are disabled.

Pages live at `abgeordnete/<person_id>.html`. Previously eligible person pages remain available from historical registry evidence when current input disappears. Retired keys, and keys whose records a name-based guess moved to another person, receive redirects to the current person; obsolete integer files are removed. Dossier and bill speaker links use the speech occurrence, and fact speaker links use the persisted person assignment. An ambiguous external ID alone does not select a page.

## Corrections

Edit version-controlled `scripts/person_corrections.json`, then replay. Its version 1 object has `partitions` and `merges` entries, plus `assignments` and `splits` arrays that must stay empty (the file is refused otherwise):

- `partitions`: `xml_redner_id` (each Redner-ID at most once), `labels` mapping printed names to partition owners (one owner per name, titles aside), optional reviewed `occurrences` object mapping `<protocol_id>/<rede_id>` to `display_name` and `source_url`, and optional `profile_owner`, one of the label owners, identifying whose shared-ID profile is valid. The partition applies before persistence.
- `assignments` (an occurrence placed on another person) and `splits` (records of one person moved to a new key) must be empty. Both are disabled until the placed-record redesign recorded in TODOS.md: every review of the first design found a placed record leaking its biography onto the owner's page, disabling the owner's name guesses or aborting the build. Use a partition or a merge instead.
- `merges`: `persons`, with optional `survivor`. Default survivor is the oldest allocation ordinal; explicit survivor may promote a previously issued alias. All retired keys remain resolvable.

Record and occurrence IDs are available in the SQLite/CSV registry tables. Unknown persons, malformed corrections and alias cycles abort with a diagnostic. The Föhr/Mende correction for Redner-ID `11005304` includes six reviewed XML occurrences; the shared ext-ID profile cannot join the two partitions or supply Mende's biography link. Every record of a partitioned Redner-ID carries `mps.aw_match = 'partitioned'` (besides `ext_id` for a Redner-ID lookup and `name` for a name search): its abgeordnetenwatch id is never a join key. The profile owner keeps the shared `aw_politician_id` and `profile_url` as attributes; the other partitions carry none.

Corrections are applied durably and are not reverted when an entry is removed from the file: a partition or merge that was applied stays in the registry. To undo one, re-mint the registry from a schema 2 backup.

## Backup and recovery

Back up the **build store**, not only the distribution download. The build store holds all issued keys, aliases, historical source evidence and occurrence bindings. Also retain the cached reports, authoritative catalog and the version-controlled correction file. Losing the registry loses person-key continuity even if the reports can be downloaded again.

Use SQLite's backup API or `.backup` to obtain a consistent copy. Restore it with its cached evidence before replay. Distribution copies are marked with `user_version` and cannot be used as writable build stores.

A nonblocking kernel writer lock `<database>.writer.lock` covers registry snapshot, allocation, roster ingestion, reconciliation, facts and replacement. Standalone fact computation shares that lock. Kernel locks release on process exit or crash; the lock file may remain. Each rebuild uses its own temporary database, so abandoned temporary files cannot replace the store or discard registry history; the next rebuild deletes them under the writer lock, and the replacement keeps the file mode of the store it replaces. After interruption, rerun replay against the unchanged store. Database replacement is atomic; whole-site publication remains separate.

See [A.2 reference validation](a2-validation.md) for the full-cache comparison and observed ordering changes.
