# CLI, writer and page-write robustness

Implement robustness findings in “A.2 third ship round: deferred findings” (3), (6), (11), and “A.2 second-round review leftovers” (4).

Own offline schema/open error handling, `_first_touch` error handling, rebuild staging/lock locations and `write_abgeordnete_pages`, plus targeted failure tests. Base on 03; coordinate with 04's build/persist edits.

1. Put read-only store opening inside the CLI's diagnostic boundary. Test a directory path and a genuinely unreadable file where supported. Return a nonzero exit and actionable message without traceback; preserve the source store.
2. `_first_touch` must initialize its temp table deliberately or catch only the missing-table condition. Unrelated `OperationalError` must propagate through staged failure handling rather than being treated as initialization.
3. Define private staging/lock placement so temporary databases and locks cannot enter public output. Keep a single deterministic lock identity shared by rebuild and standalone facts, including equivalent database paths. Retain crash recovery, stale sidecar cleanup, same-filesystem atomic replacement and source file mode. Review deployment exclusions before choosing the least disruptive change.
4. Validate person and alias filename keys at the page writer boundary. Remove existing target symlinks before writing, and verify the generated path stays within the expected directory. Test detail/alias targets and an outside sentinel that must remain untouched.

Done when failure paths have tested diagnostics, unexpected DB errors preserve the store, concurrent writers still exclude each other, temporary artifacts are excluded from publication, and page writes cannot follow existing symlinks outside their directory.
