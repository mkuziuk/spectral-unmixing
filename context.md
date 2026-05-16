# Documentation Update Scout — Findings

## Files Retrieved (scanned for analysis)

### Core documentation
1. `README.md` (206 lines) — user-facing feature/usage docs
2. `AGENT.md` (118 lines) — coding-agent guidance, path map, solver/model notes
3. `features/kubelka_munk_solver.md` (280 lines) — KM feature spec
4. `features/kubelka_munk_implementation_plan.md` (321 lines) — staged KM+bilirubin implementation plan
5. `features/spectral_unmixing.md` — high-level app spec
6. `features/nnls.md` — NNLS feature notes

### Backend changes (source of truth)
7. `app/core/processing.py` — KM solver, bilirubin index, `clip_negative_extinction`
8. `app/core/calibration.py` (NEW) — calibration model, fit/apply/save/load
9. `app/core/export.py` — calibration metadata in exports

### UI changes
10. `app/gui_qt/main_window.py` — toolbar controls, pipeline adapter, calibration state
11. `app/gui_qt/panels/chromophore_barcharts_panel.py` — bilirubin diagnostic subplots

### Test changes
12. `tests/test_main_window.py` — toolbar/object-name/snapshot tests for KM, bilirubin, calibration
13. `tests/test_chromophore_barcharts_panel.py` — bilirubin index and calibrated estimate subplot tests
14. `tests/test_calibration.py` (NEW) — calibration module tests
15. `tests/test_bilirubin_index_report.py` (NEW) — CLI calibration save/load tests

### Script changes
16. `scripts/bilirubin_index_report.py` — added `--save-calibration`, `--load-calibration`
17. `scripts/km_sensitivity_scan.py` — improved scoring/output

### Data
18. `data/calibrations/bilirubin_a1a6_log_linear.json` (NEW) — default calibration artifact

---

## 1. What changed: complete inventory

### 1.1 New backend module: `app/core/calibration.py`

**Purpose:** Log-linear bilirubin-index calibration model (OD450−OD517 domain fit → calibrated µM estimate).

**Key items to document:**
- `CalibrationModel` dataclass (schema_version, fit_type, coefficients, k_hb_correction, calibration_domain, fit_quality, disclaimer, independently_validated)
- `fit_calibration(index_values, truth_uM, ...)` → fits slope/intercept via `lstsq`, returns `CalibrationModel`
- `apply_calibration(index_values, model, clip_to_domain=True)` → inverts log-linear fit, clips to domain bounds
- `save_calibration(model, path)`, `load_calibration(path)` → JSON round-trip with schema validation
- `calibration_clamp_counts(index_values, model)` → counts pixels clamped low/high
- `model_summary_for_metadata(model)` → compact dict for export metadata
- `get_default_calibration_path()` → returns `data/calibrations/bilirubin_a1a6_log_linear.json`

**Schema:** JSON schema version 1, requires `"slope"` and `"intercept"` in coefficients, slope must be nonzero.

### 1.2 Core processing additions

| Function/Change | File | Line | Purpose |
|---|---|---|---|
| `SUPPORTED_UNMIXING_METHODS` adds `"km"` | `processing.py` | 16 | KM solver registered |
| `build_absorption_matrix(..., clip_negative_extinction=False)` | `processing.py` | 594 | Clips negative interpolated extinction to zero for KM |
| `solve_unmixing()` gains `method="km"` and `reflectance` param | `processing.py` | 1006, 1040-1046 | Dispatches to KM solver |
| `_reflectance_to_mu_a_km(reflectance, mus_prime)` | `processing.py` | 1205 | KM F(R) conversion: `μa = F(R) * μs' / 2` |
| `_mu_a_to_reflectance_km(mu_a, mus_prime)` | `processing.py` | 1235 | Inverse KM reflectance reconstruction |
| `solve_unmixing_km(reflectance, A, mus_prime)` | `processing.py` | 1261 | Per-pixel KM→μa→NNLS, returns (conc, RMSE, fitted_od) |
| `compute_bilirubin_index(...)` | `processing.py` | 1322 | OD450−OD517 diagnostic; optional k·OD671 Hb correction |
| `_compute_global_scales()` now iterates **all** derived keys | `main_window.py` | 2367 | Dynamic inclusion of bilirubin maps |

### 1.3 Export changes

- `save_results()` gains `calibration_model` parameter (`export.py:25`)
- When bilirubin-index derived maps present: `metadata.json` gets `"bilirubin_index_note"` with disclaimer
- When calibrated-estimate derived maps present: `metadata.json` gets `"bilirubin_calibration"` block with coefficients, domain, fit_quality, clamp_counts, warning

### 1.4 GUI toolbar additions

**New object-name constants** in `main_window.py`:

| Constant | Widget | Tooltip/Purpose |
|---|---|---|
| `BILIRUBIN_CHECKBOX_OBJECT_NAME` | QCheckBox "Bilirubin Index" | Toggle OD450−OD517 diagnostic |
| `BILIRUBIN_K_ENTRY_OBJECT_NAME` | QLineEdit "k_corr" | Optional Hb correction factor |
| `CALIBRATION_CHECKBOX_OBJECT_NAME` | QCheckBox "Apply Calibration" | Apply loaded calibration to create µM estimate |
| `CALIBRATION_LOAD_BTN_OBJECT_NAME` | QPushButton "Load Calibration..." | File picker for calibration JSON |
| `CALIBRATION_PATH_LABEL_OBJECT_NAME` | QLabel | Shows loaded calibration filename + "⚠ unvalidated" if LOO R² < 0 |

**Toolbar order** (after solver_combo):
```
bilirubin_checkbox → bilirubin_k_entry → calibration_checkbox → calibration_load_btn → calibration_path_label
```

**New window state:**
- `self._calibration_model: Any = None`
- `self._calibration_path: str | None = None`

**New callback:**
- `_on_load_calibration_clicked()` — opens file dialog, loads JSON via `load_calibration()`, updates label with filename and validation warning

**Snapshot validation:**
- `compute_bilirubin_index=True` requires 450 nm and 517 nm bands present
- `apply_calibration=True` requires `compute_bilirubin_index=True` AND a loaded calibration model
- `bilirubin_index_k_hb` from manual entry overridden by loaded calibration's `k_hb_correction` when `apply_calibration=True`
- `k_hb_correction` usage requires 671 nm band

**Pipeline integration:**
- When `compute_bilirubin_index=True`: calls `processing.compute_bilirubin_index()`, stores `"Bilirubin Index (OD450-OD517)"` in derived maps
- When `apply_bilirubin_calibration=True`: calls `apply_calibration()` on the corrected index, stores `"Bilirubin est. (calibrated, see disclaimer)"` and `"Bilirubin est. clamp mask"` in derived maps
- Diagnostics warnings list extended with LOO R² warning when applicable

**Solver changes:**
- Solver combo now: `["ls", "nnls", "mu_a", "iterative", "km"]`
- `supports_background` now: `solver_method not in {"mu_a", "km"}`
- `_uses_fixed_scattering_solver()` now: `solver_method in {"mu_a", "iterative", "km"}`
- KM branch uses `build_absorption_matrix(..., clip_negative_extinction=True)`
- KM calls `processing.solve_unmixing_km(reflectance, A, mus_prime)`
- KM solver_info includes `{"method": "km", "base_method": "nnls", "scattering_parameters": ...}`

### 1.5 Bar chart panel changes

- `_compute_chart_data()` now returns **5-tuple**: `(sample_names, chromophore_names, means, medians, derived_stats)`
- Derived stats: dict mapping bilirubin diagnostic key → `(means_array, medians_array)`
- `_redraw()` adds diagnostic subplots after chromophore subplots when derived_stats present
- Figure title changes from `"Chromophore Comparison Across Samples"` to `"Chromophore Comparison Across Samples + Bilirubin Diagnostic"` when present
- Y-axis label: `"OD450 - OD517 (dimensionless)"` for index, `"domain-calibrated estimate (see disclaimer)"` for calibrated estimate
- New helpers: `_is_bilirubin_diagnostic_key(name)` and `_derived_y_label(name)`

### 1.6 Script changes

**`scripts/bilirubin_index_report.py`:**
- New flags: `--save-calibration <path.json>`, `--load-calibration <path.json>`
- Uses `app.core.calibration.fit_calibration()` and `apply_calibration()`
- `--save-calibration` writes the corrected-index model as JSON
- `--load-calibration` loads an existing JSON and applies it to phantom medians
- Reports loaded model slope/intercept and formula
- Unchanged backward-compatible default behavior

**`scripts/km_sensitivity_scan.py`:**
- Scoring improvements: strict bilirubin decreases, Hb must be nonzero for CoV credit, meaningful positivity threshold
- Clearer top-row output with separate best calibration/scattering per-scan-type summaries
- `build_scattering_profile()` function docstring clarified

### 1.7 New default calibration artifact

Path: `data/calibrations/bilirubin_a1a6_log_linear.json`

- Coefficients: slope=0.01405, intercept=−0.000240
- In-sample R²=0.942, LOO R²=−4.45 (unvalidated, small-N)
- Calibration domain: bilirubin 8.4–270 µM, Hb=100 µM, A1–A6 phantoms
- Disclaimer embedded in JSON

### 1.8 Features/*.md state

- `features/kubelka_munk_solver.md` — covers Stages 1-4 planning; does **not** document bilirubin index, calibration module, or bar chart integration
- `features/kubelka_munk_implementation_plan.md` — updated through Stage D (bilirubin index report); needs **Stage D GUI integration** additions for calibration module, bar charts, and export metadata

---

## 2. README sections requiring updates

### Section: "Capabilities" (line ~26)
**Missing from list:**
- Kubelka-Munk solver (`km`)
- Model-free two-band bilirubin diagnostic index (OD450−OD517)
- Bilirubin-index calibration via `app/core/calibration.py`
- Calibrated domain-specific bilirubin estimate maps
- Chromophore Bar Charts diagnostic bilirubin subplot

### Section: "The Math and Physics Model" (line ~35)
**Needs addition:**
- Kubelka-Munk remission function: `F(R) = (1-R)²/(2R)`, `μa ≈ F(R)μs'/2`
- KM forward/inverse model reference
- Two-band bilirubin index: `OD450 − OD517`

### Section: "Basic Usage Flow" (line ~200)
**Update step 6** to mention:
- Solver options include `km`
- New toolbar controls for bilirubin index and calibration

### Section: "Common Errors and Solutions" (line ~212)
**Add entries for:**
- `"Bilirubin index requires 450 nm and 517 nm bands."`
- `"Enable Bilirubin Index before applying calibration."`
- `"Load a calibration file to apply bilirubin calibration."`
- `"Bilirubin index k correction must be a number."`

### NEW section needed: Bilirubin Diagnostic Index
Explain:
- What it is: OD450−OD517 (dimensionless diagnostic)
- How to enable: checkbox in toolbar
- Hb correction via k_corr
- Calibration: load JSON → get domain-calibrated estimate
- Disclaimer: not physical concentration, interpret within domain
- Bar Charts tab shows diagnostic subplot when enabled

### NEW section needed: Kubelka-Munk Solver
Brief explanation of KM remission model and when to use it vs LS/NNLS/mu_a.

---

## 3. AGENT.md sections requiring updates

### "Important paths" (line ~15)
**Add:**
- `app/core/calibration.py` — bilirubin-index calibration model, fit/apply/save/load

### "Solver/model notes" (line ~98)
**Update supported solver methods from `ls, nnls, mu_a, iterative` to `ls, nnls, mu_a, iterative, km`:**
- `km` uses Kubelka-Munk remission function, `clip_negative_extinction=True`, `build_absorption_matrix()`, NNLS
- `km` does not support background
- `km` uses fixed-scattering controls like `mu_a`

**Add bilirubin index notes:**
- `compute_bilirubin_index()` in `processing.py` for model-free two-band diagnostic
- `CalibrationModel` in `calibration.py` for domain-calibrated estimates
- Both require 450 nm and 517 nm bands; optional 671 nm for Hb correction

### "Qt GUI conventions" (line ~110)
**Add:**
- Toolbar includes `Bilirubin Index` checkbox, `k_corr` entry, `Apply Calibration` checkbox, `Load Calibration...` button
- Calibration state stored in `self._calibration_model` and `self._calibration_path`
- Object-name constants added for all new toolbar widgets
- Bar Charts panel now renders bilirubin diagnostic subplots when bilirubin-derived maps present

### "Coding and testing guidance" (line ~118)
**Add:**
- Calibration tests in `tests/test_calibration.py`
- CLI calibration tests in `tests/test_bilirubin_index_report.py`
- New fixture: calibration JSON artifacts in `data/calibrations/`

---

## 4. Features docs requiring updates

### `features/kubelka_munk_solver.md`
Currently documents planning stages 1–4. **Add:** Stage D (bilirubin index) and Stage E (calibration module + GUI integration + bar charts).

### `features/kubelka_munk_implementation_plan.md`
Currently documents Stage D bilirubin index report. **Update Stage D** to include:
- GUI checkbox integration
- Calibration module (`app/core/calibration.py`)
- Export metadata
- Bar chart panel integration
- Save/load calibration in CLI script

**Optionally add Stage E** for:
- Variable Hb/validation phantom series design (from `research-reports/forward-calibration-plan.md`)

---

## 5. New/changed key facts for docs

| Fact | Details |
|---|---|
| KM solver combo value | `"km"`, 5th option in `["ls", "nnls", "mu_a", "iterative", "km"]` |
| KM uses absorption matrix | Same `build_absorption_matrix()` path as `mu_a`, with `clip_negative_extinction=True` |
| KM uses fixed scattering | Same scattering toolbar/controls as `mu_a` |
| KM disables background | Same as `mu_a`: `supports_background not in {"mu_a", "km"}` |
| Bilirubin index formula | `OD450 − OD517` (raw) or `OD450 − OD517 − k·OD671` (Hb-corrected) |
| Bilirubin index type | Dimensionless diagnostic, **not** concentration |
| Calibration model form | `log_linear`: `BI = slope × log₁₀([Bili]) + intercept` |
| Calibration domain limit | 8.4–270 µM bilirubin, Hb=100 µM, A1–A6 phantoms |
| Calibration disclaimer | Always embedded in JSON and export metadata |
| Bar chart diagnostic axis | Label: `"OD450 - OD517 (dimensionless)"` or `"domain-calibrated estimate (see disclaimer)"` |
| Required bands | 450 nm and 517 nm for bilirubin index; 671 nm additionally for Hb correction |
| Derived map keys added | `"Bilirubin Index (OD450-OD517)"`, `"Bilirubin est. (calibrated, see disclaimer)"`, `"Bilirubin est. clamp mask"` |
| New stable object names | 7 new constants in `main_window.py` (see §1.4) |

---

## 6. Proposed document update checklist

### README.md
- [ ] Add `km` to solver capabilities list
- [ ] Add bilirubin diagnostic index to capabilities
- [ ] Add calibration backend to capabilities (with disclaimer)
- [ ] Add KM remission F(R) formula to Math section
- [ ] Add bilirubin index formula to Math section
- [ ] Update Usage Flow step 6 for new toolbar controls
- [ ] Add Error entries for bilirubin/calibration validation errors
- [ ] New subsection: "Bilirubin Diagnostic Index" (checkbox, k_corr, calibration load, bar chart subplot)
- [ ] New subsection: "Kubelka-Munk Solver" (what it is, when to use)

### AGENT.md
- [ ] Add `app/core/calibration.py` to Important paths
- [ ] Update Solver/model notes: add `km`, add bilirubin index, add calibration
- [ ] Update Qt GUI conventions: add calibration state, new toolbar widget names
- [ ] Update Coding guidance: add calibration test references, data/calibrations/

### features/kubelka_munk_solver.md
- [ ] Add Stage D (bilirubin index, export metadata)
- [ ] Add Stage E (calibration module, GUI calibration integration)

### features/kubelka_munk_implementation_plan.md
- [ ] Update Stage D with calibration module, bar chart integration, export metadata
- [ ] Optionally add Stage E (expanded validation, from `forward-calibration-plan.md`)
