# Data changelog per release

Every data release carries two files that say what changed since the previous release:

- `CHANGES.md`: the text a reader sees (German, like `DATA.md`).
- `changes.json`: the same content for a program. A researcher checks with it whether a figure they cited from version N was touched by a later release.

Both are produced by `scripts/release_changes.py`; the release script (`scripts/publish_dip_pulse_data.py`) writes them into the release directory and lists them in `SHA256SUMS`. The version scheme is in `scripts/release_version.py`.

## Two sources

What the two manifests (`datenstand.json` of this and of the previous release) say is **derived**, so it cannot be forgotten: the previous version, `export_format`, `store_schema`, `key_version`, `schema_hash`, and the old and new value of the protocol, vote, vote-member and row counts.

What only a person knows is **authored** in a JSON file passed as `--changes`:

```json
{
  "summary": "Sitzungen 21/85 bis 21/90 ergänzt; zwei Abstimmungsergebnisse korrigiert.",
  "schema_changes": [
    {"table": "votes", "column": "inverted", "change": "added", "description": "neue Spalte"}
  ],
  "coverage_added": [
    {"description": "Plenarprotokolle 21/85 bis 21/90 der 21. Wahlperiode"}
  ],
  "corrections": [
    {"table": "votes", "key": "v-4711", "column": "yes_count", "old": 301, "new": 310,
     "reason": "Endgültiges Ergebnis statt vorläufigem Ergebnis"}
  ],
  "notes": ["optional free text"]
}
```

- `summary` is required. `schema_changes`, `coverage_added`, `corrections` and `notes` default to empty. Unknown fields are refused.
- `schema_changes[].change` is one of `added`, `removed`, `renamed`, `retyped`, `meaning`, `table-added`, `table-removed`, `other`; `column` may be `null` for a whole table.
- A correction names the `table`, the stable row `key`, the `column`, the `old` and `new` value (text, number, true/false or `null`; they must differ) and the `reason`. Every correction that moved a figure published in an earlier release belongs here. It is the public form of the old/new report the project writes into commit messages.

## Rules the release script enforces

- **First release:** no authored file is needed; the changelog says "Erste Veröffentlichung." (an authored file may give another summary, but no corrections or schema changes). The release script needs `--initial` for this; it never guesses "initial" from missing tags.
- **Later release:** `--changes` and `--previous-manifest` are required, and the previous version must be earlier than this one.
- **Schema change:** if `export_format`, `store_schema`, `key_version` or `schema_hash` differ between the two manifests, the release is refused until `schema_changes` describes them. A schema change does not change the version scheme; it is named in the changelog and in `changes.json` (`schema_changed`, `detected`).

## `changes.json`

```
changes_format   1
version, tag     "2026.11.08", "data-2026.11.08"
released         ISO date
previous_version null for the initial release
initial_release  true/false
export_format, store_schema, key_version, schema_hash   of this release
summary
schema_changed   true when a manifest field above differs
detected         {field: {old, new}} for each such field
schema_changes   authored, see above
coverage         {protocols, first_protocol, last_protocol, last_protocol_date,
                  votes, vote_members, total_rows}: each {old, new}; old is null for the initial release
coverage_added   authored
corrections      authored
notes            authored
```

A change of `changes_format` is itself a schema change of the changelog and is called out in the release that makes it.
