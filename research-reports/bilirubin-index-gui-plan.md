# Implementation Plan — Optional Bilirubin Index in PySide6 GUI

## Goal

Expose the existing `compute_bilirubin_index()` result as an optional derived diagnostic map in all PySide6 panels (Maps, Inspector, Stats, Export) behind a toolbar checkbox. Never overclaim it as a physical concentration.

---

## Context (what already exists)

- **`app/core/processing.py:1322`** — `compute_bilirubin_index()` is production-ready. Returns `bi_raw`, `bi_corrected`, `od_ref`, `indices_used`, `k_hb_correction`.
- **`tests/test_kubelka_munk.py:91`** — Two unit tests for the function already pass.
- **`scripts/bilirubin_index_report.py`** — Standalone CLI calibration report script for the A1–A6 phantoms. Not part of the GUI.
- **`app/gui_qt/main_window.py`** — Pipeline adapter already computes `derived` maps via `processing.compute_derived_maps()` and stores them in each sample result dict under keys `"derived"` and `"derived_maps"`. Currently only `THb` and `StO2` are produced.
- **`app/gui_qt/panels/maps_panel.py`** — `_draw_derived_map()` renders everything in `self._derived_maps` in a 1×N row. No code changes needed here; it will pick up new keys automatically.
- **`app/core/export.py`** — `save_results()` iterates all keys in `derived` dict and saves `.png` + `.npy`. No export changes needed.
- **`app/gui_qt/main_window.py:2290–2325`** — `_compute_global_scales()` **hardcodes** `["THb", "StO2"]` for derived scale computation. This must be extended.
- **`research-reports/two-band-bilirubin-index-plan.md`** — Design rationale, index formula, calibration references.

---

## Tasks

### 1. Add a "Compute Bilirubin Index" checkbox to the toolbar

- **File**: `app/gui_qt/main_window.py`
- **Where**: In `_build_run_toolbar()` (~line 397), after the `solver_combo` and before the `Run` button. Alternatively, add a new lightweight toolbar row (`BILIRUBIN_TOOLBAR_OBJECT_NAME`) between the solver toolbar row and the background toolbar. A simple checkbox avoids toolbar bloat. Place it in the run toolbar row, after `solver_combo` and a separator.
- **Changes**:
  - Import `QCheckBox` locally in `_build_run_toolbar`.
  - Create a `QCheckBox("Bilirubin Index")` with `objectName=BILIRUBIN_CHECKBOX_OBJECT_NAME` and `toolTip` explaining it computes `OD₄₅₀ − OD₅₁₇` from reflectance.
  - Default: unchecked.
  - Store the checkbox reference as `self._bilirubin_checkbox`.
  - Add optional `k_hb_correction` entry next to it (a small `QLineEdit` labeled "k_corr:" for the Hb correction factor). Default empty (= no correction). Valid values: float ≥ 0.
- **New object-name constants** (near top of file, with other constants):
  - `BILIRUBIN_CHECKBOX_OBJECT_NAME = "bilirubin_checkbox"`
  - `BILIRUBIN_K_ENTRY_OBJECT_NAME = "bilirubin_k_entry"`
- **Acceptance**: GUI smoke test finds the checkbox by object name; checkbox is unchecked on launch; enabled when data folder is loaded.

### 2. Validate bands at config-snapshot time

- **File**: `app/gui_qt/main_window.py`
- **Where**: `_build_config_snapshot()` (~line 1420)
- **Changes**:
  - Read the checkbox state and k_hb_correction entry value.
  - If bilirubin index is requested, verify that `450` and `517` are in `self.folder_info["wavelengths"]`. If not, raise `ValueError("Bilirubin index requires 450 nm and 517 nm bands.")`.
  - Optionally check if `671` is available for Hb correction; if not and `k_hb_correction` is set, warn (or error).
  - Add two keys to the snapshot dict:
    - `"compute_bilirubin_index": bool`
    - `"bilirubin_index_k_hb": float | None`
- **Acceptance**: Selecting the checkbox then clicking Run without 450/517 bands shows an error dialog. With valid bands, snapshot contains `compute_bilirubin_index=True`.

### 3. Compute bilirubin index in the pipeline adapter

- **File**: `app/gui_qt/main_window.py`
- **Where**: `_make_pipeline_adapter()` inner `_pipeline()` (~line 1555), inside the per-sample loop after `compute_derived_maps()` is called.
- **Changes**:
  - After the `derived = processing.compute_derived_maps(...)` call (line ~1603), add:
    ```python
    if snapshot.get("compute_bilirubin_index"):
        idx_450 = wls.index(450)
        idx_517 = wls.index(517)
        idx_ref = wls.index(671) if 671 in wls else None
        bilirubin_result = processing.compute_bilirubin_index(
            reflectance,
            wavelength_index_450=idx_450,
            wavelength_index_517=idx_517,
            wavelength_index_ref=idx_ref,
            k_hb_correction=snapshot.get("bilirubin_index_k_hb"),
        )
        derived["Bilirubin Index (OD450-OD517)"] = bilirubin_result["bi_corrected"]
        if snapshot.get("bilirubin_index_k_hb") is not None:
            derived["Bili Index (raw)"] = bilirubin_result["bi_raw"]
    ```
  - Update `derived_maps` assignment (currently `"derived_maps": derived`) — no change needed, it already copies the dict.
- **Key naming**: `"Bilirubin Index (OD450-OD517)"` is the primary key. Keep it verbose and descriptive. The `(raw)` variant is only added when Hb correction is active.
- **Acceptance**: After running with checkbox checked, a sample result dict's `derived` contains the bilirubin key. Unit test: mock pipeline with a simple reflectance and verify.

### 4. Extend `_compute_global_scales` to include bilirubin index

- **File**: `app/gui_qt/main_window.py`
- **Where**: `_compute_global_scales()` (~line 2290)
- **Changes**:
  - The loop currently iterates `["THb", "StO2"]`. Dynamically discover derived keys from the first result's `derived` dict, then iterate over all keys (including any new ones).
  - **Implementation**: Before the loop, gather all keys:
    ```python
    derived_keys = list(next(iter(results.values())).get("derived", {}).keys())
    ```
    This handles `THb`, `StO2`, and any bilirubin keys without hardcoding.
  - Keep the existing RMSE scale logic unchanged.
- **Acceptance**: Global scales for the bilirubin index are computed and stored in `self._derived_scales` alongside `THb`/`StO2`. Verify in test that min/max are finite for bilirubin maps.

### 5. Display in Maps Panel (automatic)

- **File**: `app/gui_qt/panels/maps_panel.py` — **no changes needed**
- **Why**: `_draw_derived_map()` iterates all keys in `self._derived_maps` with `list(self._derived_maps.keys())`. Any new key added to the dict renders automatically as a subplot in the 1×N row.
- **Verification**: With a result containing `"Bilirubin Index (OD450-OD517)"` in `derived_maps`, switch to "Derived Maps" view and verify the bilirubin map appears alongside THb and StO2. The title will show the key name and μ/med statistics (via existing `_format_map_title`).

### 6. Display in Pixel Inspector (optional enhancement)

- **File**: `app/gui_qt/panels/inspector_panel.py`
- **Where**: `_render_concentrations()` (~line 375)
- **Changes**:
  - After the chromophore concentration lines and RMSE line, if `self._data` contains derived map values, append a separator and show the derived values for the selected pixel:
    ```python
    derived = self._data.get("derived")
    if derived and row < next(iter(derived.values())).shape[0]:
        lines.append("")
        lines.append("Derived Maps:")
        for name, data_map in derived.items():
            val = float(data_map[row, col])
            lines.append(f"  {name}: {val:.6g}")
    ```
  - This also automatically surfaces THb/StO2 at the pixel level, which is currently missing.
- **Acceptance**: Click a pixel → "Concentrations" text area shows derived maps (including bilirubin index if present).

### 7. Export metadata enrichment

- **File**: `app/core/export.py`
- **Where**: `save_results()` (~line 19)
- **Changes**:
  - The export loop already saves all `derived` dict entries. **No code change needed for saving maps/arrays.**
  - Optionally add a `"bilirubin_index_warning"` string to the `metadata.json`:
    ```python
    if any("Bilirubin Index" in k for k in derived):
        meta["bilirubin_index_note"] = (
            "The Bilirubin Index is a dimensionless ratiometric indicator (OD450−OD517). "
            "It is calibrated against the A1–A6 liquid phantom halving series (Hb=100 µM) "
            "and should not be interpreted as an absolute bilirubin concentration."
        )
    ```
- **Acceptance**: When bilirubin index is computed and exported, `metadata.json` contains the disclaimer note.

### 8. Tooltip and label warnings in the UI

- **File**: `app/gui_qt/main_window.py`
- **Where**: The checkbox `toolTip` text in Task 1.
- **Text for checkbox tooltip**:
  ```
  "Compute a model-free two-band bilirubin diagnostic index (OD₄₅₀ − OD₅₁₇). "
  "This is a dimensionless trend indicator, NOT a physical bilirubin concentration. "
  "Requires 450 nm and 517 nm bands. Optional Hb correction via 671 nm reference."
  ```
- **Text for status bar** (optional): When bilirubin index is computed and a sample is selected, append to status: `"; Bili index: 2-band diagnostic"`.
- **Acceptance**: Hovering the checkbox shows the disclaimer tooltip.

### 9. Unit tests for GUI integration

- **File**: `tests/test_bilirubin_index_gui.py` (new)
- **Tests**:
  1. `test_checkbox_present_and_unchecked` — Verify `BILIRUBIN_CHECKBOX_OBJECT_NAME` exists and starts unchecked.
  2. `test_checkbox_toggles_config_snapshot` — Capture a snapshot with checkbox checked → `compute_bilirubin_index=True`.
  3. `test_pipeline_produces_bilirubin_key` — Feed synthetic reflectance (with 450/517 bands) through a minimal pipeline or directly test the adapter logic → result dict contains `"Bilirubin Index (OD450-OD517)"`.
  4. `test_missing_bands_raises` — Config snapshot with bilirubin requested but no 450 nm band → `ValueError`.
  5. `test_derived_scales_include_bilirubin` — After a multi-sample run, `_compute_global_scales` includes bilirubin key.
  6. `test_export_metadata_contains_disclaimer` — Mock export with bilirubin key in derived → `metadata.json` has disclaimer.

- **File**: `tests/test_maps_panel.py` — extend
  - Add `test_derived_view_renders_bilirubin_map` — `show_results()` with a derived_maps dict containing a bilirubin key → rendered axes include that title.
  - Add `test_derived_view_handles_extra_keys` — derived_maps with 5 keys (THb, StO2, RMSE, and two bilirubin variants) → 5 subplots rendered.

- **File**: `tests/test_inspector_panel_qt009.py` — extend
  - Add `test_derived_values_shown_for_selected_pixel` — set_data with derived dict → conc text includes derived map lines.

### 10. Smoke / integration test

- **File**: `tests/test_gui_qt_smoke.py` — extend
  - If the smoke test already runs a full pipeline on fixture data, add an assertion that the bilirubin checkbox is findable. Optionally run with checkbox enabled and verify bilirubin maps appear in the maps panel's derived view.

### 11. Calibration report reference in UI (ancillary)

- **File**: `app/gui_qt/main_window.py` sidebar or help section
- **Change**: Add a small note in the sidebar or a QLabel below the bilirubin checkbox: `"Calibrated on A1–A6 phantoms (Hb=100 µM). See research-reports/bilirubin-index-validation.md."`
- **Acceptance**: Note is visible when checkbox is checked.

---

## Files to Modify

| File | Change |
|------|--------|
| `app/gui_qt/main_window.py` | i) New object-name constants; ii) Checkbox + k_hb entry in run toolbar; iii) Config snapshot reads checkbox/k_hb + validates bands; iv) Pipeline adapter computes bilirubin index from reflectance; v) `_compute_global_scales` dynamically discovers derived keys |
| `app/gui_qt/panels/inspector_panel.py` | `_render_concentrations()` — append derived map values for the selected pixel |
| `app/core/export.py` | `save_results()` — add disclaimer note to `metadata.json` when bilirubin index is present |
| `tests/test_maps_panel.py` | Two new tests for bilirubin-derived map rendering |
| `tests/test_inspector_panel_qt009.py` | One new test for derived values in pixel inspector |
| `tests/test_gui_qt_smoke.py` | Optional bilirubin checkbox presence assertion |

## New Files

| File | Purpose |
|------|---------|
| `tests/test_bilirubin_index_gui.py` | 6 unit tests for checkbox → config → pipeline → export integration |

## No Changes Needed

- `app/core/processing.py` — `compute_bilirubin_index()` and `compute_derived_maps()` are already complete.
- `app/gui_qt/panels/maps_panel.py` — `_draw_derived_map()` auto-renders all keys.
- `scripts/bilirubin_index_report.py` — standalone CLI script; unchanged.
- `data/` — no new spectral data files needed.

---

## Dependencies

- Task 2 depends on Task 1 (need checkbox reference to read state).
- Task 3 depends on Task 2 (need snapshot flag to branch in pipeline).
- Task 4 depends on Task 3 (need actual bilirubin keys in derived dict to test scale computation).
- Task 6 depends on Task 3 (need derived keys in result dict).
- Tasks 5, 7, 8, 9, 10, 11 are independent of each other and can be done in parallel after Tasks 1–3 are complete.

---

## Risks

| Risk | Mitigation |
|------|-----------|
| **Bands 450/517/671 not present** in a given dataset | Pre-validate in config snapshot (Task 2); show clear error. Checkbox disabled or warning shown if bands missing. |
| **Index has very small dynamic range** (0.015–0.036 in phantom data) — colorbar may be uninformative | Use a perceptually uniform colormap (viridis is default). Add per-sample median annotation to the map title (already done in `_format_map_title`). |
| **Users interpret index as µM concentration** | Strong UI labeling everywhere: checkbox tooltip, export metadata, map title uses full formula phrase. Never use "µM" or "concentration" in bilirubin map labels. |
| **`k_hb_correction` entry parsing errors** | Validate as `float ≥ 0` in config snapshot; re-use the same `QLineEdit` editing-finished validation pattern used for background/scattering entries. |
| **`_compute_global_scales` dynamic key discovery may produce wrong order or miss keys** | Gather keys from first result's `derived` keys in insertion order (Python 3.7+ dicts are ordered). Test with multiple samples to confirm coverage. |
| **Inspector panel change (`_render_concentrations`) breaks existing tests** | The extension only appends lines; existing `CONC_TEXT_OBJECT_NAME` assertions should remain valid. Add a new test for the new behavior. |

---

## Non-Goals (explicitly out of scope)

- **Do NOT add "bilirubin index" as a new solver method** in the solver dropdown. The index piggybacks on any solver as a derived map (per existing plan decision, Approach B).
- **Do NOT compute calibration curves inside the GUI** (α, β, LOO predictions). That belongs in `scripts/bilirubin_index_report.py` or a future calibration panel, not in the live pipeline.
- **Do NOT convert the index to approximate µM** inside the maps panel or pixel inspector. The raw OD difference value is shown. Any µM conversion would require calibration coefficients not available in the GUI pipeline.
- **Do NOT add a separate tab** for bilirubin index. It lives in the existing Maps panel under the "Derived Maps" view.
- **Do NOT change the existing `compute_derived_maps()` function signature**. The bilirubin index is a separate computation that augments the `derived` dict, not a replacement for THb/StO2.
- **Do NOT modify `chromophore_barcharts_panel.py`** to show bilirubin index. The barcharts panel compares chromophore concentrations across samples; bilirubin index is a derived map, not a chromophore.
- **Do NOT modify `stats_panel.py`** — it shows reflectance spectra statistics, not derived maps.
- **Do NOT modify `diagnostics_panel.py`** — the bilirubin index is not a quality diagnostic.
