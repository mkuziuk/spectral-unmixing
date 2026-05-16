# AGENT.md

Guidance for coding agents working in this repository.

## Project overview

This is a Python desktop application for biomedical hyperspectral spectral unmixing. It loads image cubes, computes reflectance and optical density, builds spectral model matrices from LED/chromophore/pathlength CSVs, solves chromophore concentration maps, and displays/exports results through a PySide6 GUI.

PySide6 is the only supported UI for release `0.2.2+`; do not reintroduce the removed tkinter/legacy fallback.

## Orchestration and subagents

When acting as the orchestrator, use subagents whenever practical instead of doing all analysis serially in the main thread. Prefer delegation for:

- codebase reconnaissance and impact analysis before broad edits;
- implementation plans for multi-file or scientific/modeling changes;
- independent review of code, docs, UI wording, and scientific claims;
- parallelizable coding tasks with clear file boundaries;
- post-change validation summaries.

Keep the main orchestrator responsible for final decisions, conflict resolution, edits that cross task boundaries, test execution, and commits. Summarize subagent outputs before acting on them, and preserve conservative scientific wording when subagents disagree.

## Important paths

- `app/main.py` — application entry point; launches the Qt UI.
- `app/core/io.py` — root/data folder validation, image loading, chromophore/LED/pathlength CSV loading.
- `app/core/processing.py` — reflectance/OD math, overlap and absorption matrices, LS/NNLS/`mu_a`/iterative/`km` solvers, bilirubin index helper, diagnostics.
- `app/core/calibration.py` — bilirubin-index forward calibration model: fit/apply/save/load JSON, domain clipping, clamp counts, schema validation, and metadata summaries.
- `app/core/export.py` — saves maps, arrays, and metadata; uses Matplotlib `Agg` backend and embeds bilirubin index/calibration disclaimers when relevant.
- `app/gui_qt/main_window.py` — main PySide6 window, pipeline adapter, toolbar/sidebar/tabs, stable object-name constants used by tests.
- `app/gui_qt/worker.py` — `QObject` worker and signals for background pipeline execution.
- `app/gui_qt/panels/`, `app/gui_qt/widgets/`, `app/gui_qt/mpl/` — Qt panels, widgets, and Matplotlib canvas helpers.
- `data/` — default spectral data (`leds_emission.csv`, `penetration_depth_digitized.csv`, `chromophores/*.csv`) plus optional calibration JSONs in `data/calibrations/`.
- `scripts/bilirubin_index_report.py` — CLI for computing the two-band bilirubin index, fitting calibration JSON (`--save-calibration`), and applying calibration JSON (`--load-calibration`).
- `tests/` — mixed `unittest` and `pytest` suite, including many Qt/headless tests.
- `features/` — feature notes, parity evidence, and implementation plans; inspect relevant files before changing related behavior.
- `.github/workflows/build-windows.yml` and `spectral-unmixing.spec` — Windows PyInstaller release build.

Ignore generated/cache content such as `__pycache__/`, `.pytest_cache/`, `.venv/`, `.DS_Store`, and ignored large sample-data folders.

## Environment and commands

Use the project virtual environment when present:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Useful development extras for the full test suite may be needed in a fresh env:

```bash
.venv/bin/python -m pip install pytest pytest-qt pyinstaller
```

Run the app:

```bash
.venv/bin/python app/main.py
# or
.venv/bin/python -m app.main
# or, if .venv exists
./run.sh
```

Run tests headlessly, especially before/after GUI changes:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests
```

Targeted tests for common edit areas:

```bash
.venv/bin/python -m pytest -q tests/test_data_folder_selection.py
.venv/bin/python -m pytest -q tests/test_processing_fixed_scattering.py
.venv/bin/python -m pytest -q tests/test_background_consistency.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q tests/test_gui_qt_smoke.py tests/test_main_window.py
```

The tests include both `unittest` and `pytest` styles; `pytest` can run both. Some Qt tests create a `QApplication` at import time, so set `QT_QPA_PLATFORM=offscreen` before invoking tests in headless environments.

Build the Windows executable locally only when needed:

```bash
pyinstaller spectral-unmixing.spec --clean --noconfirm
```

If adding new import-only modules used at runtime by the packaged app, update `spectral-unmixing.spec` hidden imports as needed.

## Data and pipeline assumptions

A processing root folder contains sample subfolders plus required `ref/` and `dark_ref/` folders. Image filenames must start with the wavelength prefix, e.g. `450nm...`; wavelengths are parsed as integers and sorted.

A spectral data folder must contain:

```text
leds_emission.csv
penetration_depth*.csv
chromophores/*.csv
```

`io._find_penetration_depth_file()` intentionally prefers `penetration_depth_digitized.csv`, then falls back to the lexicographically first `penetration_depth*.csv`. Preserve this deterministic behavior.

Supported image loading:

- JPEG/PNG and similar PIL-readable files via `PIL.Image`.
- `.dng` via `rawpy`; keep the graceful `ImportError` when `rawpy` is unavailable.

The core pipeline in `SpectralUnmixingMainWindow._make_pipeline_adapter()` loads refs once, then processes each sample into a result payload. Keep payload keys stable (`sample_cube`, `reflectance`, `od_cube`, `concentrations`, `fitted_od`, `rmse_map`, `derived`, `derived_maps`, `diagnostics`, `A`, `chromophore_names`, solver/config keys) because panels and tests consume them.

## Solver/model notes

Supported solver methods are `ls`, `nnls`, `mu_a`, `iterative`, and `km`.

- `ls` and `nnls` use the overlap matrix from LED emission, chromophore spectra, and penetration depth.
- `mu_a` uses the band-averaged absorption matrix plus fixed-scattering profile and does not support background.
- `iterative` uses NNLS with an iteratively updated effective pathlength and may return fallback metadata in `solver_info`.
- `km` uses the Kubelka-Munk remission transform on reflectance, the band-averaged absorption matrix with `clip_negative_extinction=True`, and fixed scattering before NNLS. It does not support background.
- Background parameters are supported for LS/NNLS/iterative only. UI selection uses `Background`; export metadata/maps use `background`.
- Derived maps `THb` and `StO2` are produced only when chromophore names include exactly `HbO2` and `Hb`.
- Optional bilirubin derived maps include `Bilirubin Index (OD450-OD517)`, `Bili Index (raw)`, `Bilirubin est. (calibrated, see disclaimer)`, and `Bilirubin est. clamp mask`.

Keep validation logic in `app/core/processing.py` as the source of truth for background, scattering, iterative solver, KM solver, and bilirubin-index parameters. Route UI/API inputs through those validators instead of duplicating constraints.

## Bilirubin index and calibration notes

- `processing.compute_bilirubin_index()` computes a model-free two-band diagnostic: `OD450 - OD517`, optionally `OD450 - OD517 - k*OD671` when `k_corr` is supplied.
- The bilirubin index is dimensionless and separate from spectral unmixing. Do not describe it as a physical concentration or as a replacement for a chromophore map.
- The default calibration file is `data/calibrations/bilirubin_a1a6_log_linear.json`. It was fitted on the A1-A6 DNG-derived Lipofundin phantom series with Hb fixed at 100 µM and `k_hb_correction=None`.
- The default calibration has strong in-sample trend but poor/negative leave-one-out validation. Keep labels/disclaimers conservative: "domain-calibrated estimate" or "diagnostic estimate", not validated concentration.
- If a user enters `k_corr`, the loaded calibration must have been fitted with the same `k_hb_correction`. The default calibration assumes the `k_corr` field is empty.
- KM may produce zero-valued `bili_agat` maps on the current 8-band LED set; this is a known identifiability limitation. The bilirubin index derived map is the intended bilirubin contrast diagnostic for these phantoms.

## Qt GUI conventions

- Preserve deferred PySide6 imports where modules are intended to be import-safe.
- Keep stable object-name constants in `app/gui_qt/main_window.py`; tests find widgets by these names. Bilirubin/calibration toolbar constants include `BILIRUBIN_CHECKBOX_OBJECT_NAME`, `BILIRUBIN_K_ENTRY_OBJECT_NAME`, `CALIBRATION_CHECKBOX_OBJECT_NAME`, `CALIBRATION_LOAD_BTN_OBJECT_NAME`, and `CALIBRATION_PATH_LABEL_OBJECT_NAME`.
- Do not mutate Qt widgets from worker/background code. `app/gui_qt/worker.py` should communicate through signals, and UI updates should happen in main-window slots.
- Reuse existing panel/widget modules for UI changes rather than adding large logic blocks to tests or the entry point.
- The Chromophore Bar Charts panel may render separate bilirubin diagnostic subplots from derived maps. Do not label these diagnostic axes as concentration.
- Be careful with `QApplication` singletons in tests; create one only if `QApplication.instance()` is `None`.
- For Matplotlib in GUI code, respect the existing Qt canvas helpers; for export code, keep the non-interactive `Agg` backend.

## Coding and testing guidance

- Prefer small, targeted edits and keep public function signatures stable unless tests/docs are updated together.
- Preserve deterministic ordering: sorted folders/files, sorted chromophore CSV loading, sorted wavelengths.
- Use explicit validation errors for bad input files, ragged CSV rows, non-numeric CSV values, and shape mismatches.
- Keep numerical code finite-safe (`np.isfinite`, clipping, `nan_to_num`) where existing code already hardens behavior.
- Avoid committing generated outputs, caches, virtual environments, local sample datasets, or binary test artifacts.
- When changing defaults or release behavior, update both `README.md` and `pyproject.toml` if version/user-facing instructions change.
- After core math changes, run focused core tests plus at least one GUI smoke test to catch payload/contract regressions.
- Calibration-related focused tests: `tests/test_calibration.py`, `tests/test_bilirubin_index_report.py`, `tests/test_chromophore_barcharts_panel.py`, `tests/test_kubelka_munk.py`, and `tests/test_main_window.py`.
- Calibration JSON schema is versioned (`schema_version == 1`, `fit_type == "log_linear"`, coefficients `slope`/`intercept`, fit quality including `loo_r2`, and a required disclaimer). Reject unknown schema versions.
