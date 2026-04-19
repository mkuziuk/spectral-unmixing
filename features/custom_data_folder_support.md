## Feature: User-selectable spectral data folder

### Goal
Allow the user to select and use a custom spectral `data/` folder at runtime, containing:
- `leds_emission.csv`
- `penetration_depth*.csv` (pattern-based filename support)
- `chromophores/` folder with one or more `*.csv` spectra files

The app must continue to work with the default bundled/project `data/` folder when no custom folder is selected.

---

## Scope

### In scope
1. **Processing logic updates**
   - Add robust validation for required files/folders in selected data directory.
   - Support `penetration_depth*.csv` discovery (instead of only one hardcoded filename).
   - Keep backward compatibility with existing `penetration_depth_digitized.csv`.
   - Surface actionable errors when files are missing or malformed.

2. **UI updates**
   - Add controls to select and reset a custom data folder.
   - Display current data source (default vs custom path).
   - Refresh chromophore list after selecting a new data folder.
   - Preserve user workflow: select root folder → run unmixing.

3. **Tests**
   - Add tests for data-folder validation and penetration-depth file discovery.
   - Add a regression test for custom-folder path usage.
   - Run test suite and ensure no existing behavior regresses.

4. **Documentation**
   - Update README with custom data-folder usage and expected folder structure.
   - Add troubleshooting notes for common custom-data errors.

---

## Proposed design

### A) Core I/O changes (`app/core/io.py`)
- Add `validate_data_dir(data_dir: str) -> dict`:
  - verify `leds_emission.csv` exists
  - verify `chromophores/` exists and contains at least one `*.csv`
  - verify at least one `penetration_depth*.csv` exists
  - return resolved file paths and discovered chromophore names

- Add helper `find_penetration_depth_file(data_dir: str) -> str`:
  - prefer exact `penetration_depth_digitized.csv` if present
  - else choose deterministic first match among `penetration_depth*.csv` (sorted)
  - raise clear `FileNotFoundError` if no match

- Update `load_penetration_depth(data_dir)` to use file discovery helper.

### B) App-window integration (`app/gui/app_window.py`)
- Toolbar additions:
  - `📁 Select Data Folder` button
  - `↺ Use Default Data` button
  - status label showing active data folder source

- Runtime behavior:
  - on custom-folder selection: validate folder, set `self.data_dir`, refresh chromophore menu
  - on reset: restore auto-found default folder and refresh chromophore menu
  - guard `_on_run` / pipeline start with validation and user-friendly messagebox errors

### C) Testing strategy
- New tests in `tests/test_data_folder_selection.py`:
  - validation succeeds for default fixture-like structure
  - missing `leds_emission.csv` fails with clear message
  - missing `chromophores/` or empty folder fails
  - penetration-depth wildcard resolution works deterministically

- Optional integration-level check:
  - run a minimal pipeline setup using selected data folder and ensure overlap matrix builds.

### D) Docs updates
- README:
  - add “Custom Data Folder” section
  - include required structure snippet
  - mention filename wildcard semantics for penetration depth

---

## Execution plan (delegated)
1. **Processing logic** — implement I/O validation + wildcard discovery.
2. **UI** — add custom data-folder controls and dynamic chromophore refresh.
3. **Tests** — add/execute tests for new behavior and regression safety.
4. **Docs** — update README and feature notes.

---

## Acceptance criteria
- User can run unmixing with either default or custom data folder.
- App accepts custom penetration file named `penetration_depth*.csv`.
- Chromophore list reflects selected data folder contents.
- Clear errors are shown for invalid custom data folders.
- Tests pass and documentation reflects the new workflow.
