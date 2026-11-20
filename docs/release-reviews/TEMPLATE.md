# Release review: data-<version>

Copy this file to `<version>.md` and fill it in while running `docs/release-review.md`. Leave no step empty: write "not run" and why.

- **Reviewed by:**
- **Date:**
- **Verdict:** stable / not stable

## Inputs

| Input | Version or path | SHA-256 |
|---|---|---|
| Candidate release directory (`SHA256SUMS` checked) | | |
| Last stable release (none for the first) | | |
| Source XML directory, number of files | | |
| CPP-BT speech metadata (version, Zenodo record) | | |

## 1. Coverage per year

- Exclusions and their Grund:
- Years whose sittings fell or whose withheld share rose, each explained:
- Sittings per Wahlperiode, ours against CPP-BT's:

## 2. Figures moved since the last stable

- `compare_store_values.py --cohort shared`:
- `compare_store_values.py --cohort all`:
- Every moved value and the correction or rule change that names it:

## 3. Spot checks against the protocols

- Seed and the five sittings drawn:
- Reden checked (Redner, Fraktion, TOP, opening and closing sentence):
- Withheld Reden checked:
- Named votes checked:
- Sittings that changed status since the last stable:

## 4. Comparison with CPP-BT

- Command and exit code:
- `ids_only_ours`:
- Ids only CPP-BT has, by class, and those read by hand:
- Surname and Fraktion differences not in `scripts/cpp_bt_known_differences.tsv`:
- The 20 largest ratio rows, each read:

## 5. Claims

- "Vergleich" table of DATA.md: date checked, and each cell that changed:
- Figures under "Verknüpfung über die Kennungen des Bundestages" against step 4's output:
- Licence section and the roll-call question:

## 6. Findings

| Finding | Fixed in release |
|---|---|

## Verdict

Stable or not, and why. If stable: the tag `stable-<version>` and, once it exists, the Zenodo DOI.
