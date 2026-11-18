# Agent instructions

## Testing

Use Python 3.11 or newer. Run `python3 -m unittest discover -s tests` from the repository root. Tests live in `tests/` and use Python's standard-library unittest framework with local fixtures. The suite does not require network access.

See CONTRIBUTING.md and `.github/workflows/ci.yml` for the development and CI checks.

`tests/test_code_rules.py` holds code rules for `scripts/`: how SQLite is opened, absent vs zero, and import layers. When one fails, its message says why the rule exists and how to fix the cause. Fix the cause; don't add a baseline entry to make it pass.

On this macOS machine, system `python3` is 3.9; use uv's CPython: `uv run --python 3.13.18 python -m unittest discover -s tests` (3.11.18 is installed too, for the supported floor).

## Claude reviews

Claude's review runner can report an authentication failure inside the sandbox even when the user is logged in. Before declaring Claude reviews unavailable or asking the user to log in again, retry the same runner outside the sandbox using the normal escalation/approval mechanism. Verified on 2026-10-28: the sandboxed smoke test failed authentication; the same invocation outside the sandbox completed successfully.
