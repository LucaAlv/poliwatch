# Release reviews

One record per reviewed release, `<version>.md`, written by the owner while running `docs/release-review.md`: the inputs and their SHA-256 digests, the result of each step, each finding with the release that fixed it, and the verdict ("stable" or not). The step 4 output can sit beside it as `<version>-cpp-bt.tsv`.

`cpp-bt-first-run-2026-11-14.md` is the first run of `scripts/compare_cpp_bt.py` on the reference store, kept for the calibration of its thresholds. It is not the record of a release.
