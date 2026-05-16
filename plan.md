# Documentation Update Plan — `feature/kubelka-munk-solver` Branch

**Date:** 2026-05-16

**Status:** Implemented. See `progress.md` for completion notes and validation results.

Branch includes: KM solver, bilirubin index diagnostic, forward calibration module (backend, CLI, UI), bar chart integration, tests/validation, and scientific caveats.

---

## Files to Update

### 1. `README.md` — HIGH priority (user-facing)

| Section | Changes |
|---------|---------|
| **Capabilities** bullet list | Add: "**Kubelka-Munk (KM) Solver:** Physically motivated diffuse reflectance unmixing with fixed reduced scattering via `mu_a` → NNLS path." |
| | Add: "**Bilirubin Diagnostic Index:** Model-free two-band bilirubin diagnostic map (OD450 − OD517) with optional Hb correction and forward log-linear calibration." |
| **The Math and Physics Model** after §4 | Add §5: "Kubelka-Munk Reflectance Model" with the forward/inverse KM equations, F(R) transform, absorption linearization, scattering power-law, and note that KM is a physical alternative to Beer-Lambert overlap matrix. |
| | Add §6 or sub-bullet: "OD450 − OD517 Bilirubin Index" with formula, what it measures, and caveat paragraph that it is a diagnostic index, not an absolute concentration. |
| **Custom Data Folder Support** | Add entry for `data/calibrations/` — calibration JSON files for bilirubin-index forward models. |
| **Basic Usage Flow** step 6 | Update solver list: add "km" to solver options. |
| **Release / version note** (top) | Add current branch features as "Development (branch feature/kubelka-munk-solver)", not a release version. |

**New scientific caveats to add:**

```
⚠ The Bilirubin Index is a dimensionless two-band diagnostic (OD450−OD517).
  It is NOT a physical bilirubin concentration in µM. A forward calibration
  can be loaded, but calibration is validated only on the A1–A6 phantom
  series and has poor leave-one-out performance on 6 points. Treat
  calibrated estimates as domain-limited diagnostic indicators only.
```

---

### 2. `AGENT.md` — HIGH priority (developer guidance)

| Section | Changes |
|---------|---------|
| **Important paths** | Add: `app/core/calibration.py` — bilirubin-index forward calibration (CalibrationModel, fit/apply/save/load). |
| | Add: `data/calibrations/` — calibration JSON artifacts. |
| | Add: `scripts/bilirubin_index_report.py` — CLI calibration report, fit, save/load. |
| **Data and pipeline assumptions** — `Supported image loading` | Add `.dng` via `rawpy` already listed; confirm. |
| **Solver/model notes** | Update solver methods to: `ls`, `nnls`, `mu_a`, `iterative`, `km`. |
| | Add KM sub-section: "`km` — uses absorption matrix + fixed scattering, disables background, operates on reflectance via KM remission transform, then NNLS." |
| | Add bilirubin paragraph: "Bilirubin Index (`OD450−OD517`) is a derived diagnostic, not a chromophore concentration. The `Apply Calibration` checkbox loads JSON from `data/calibrations/`. Calibrated maps are always annotated with a disclaimer." |
| | Update derived map note: "Derived maps now include `THb`, `StO2`, and (optionally) `Bilirubin Index (OD450-OD517)`, `Bili Index (raw)`, `Bilirubin est. (calibrated, see disclaimer)`, and `Bilirubin est. clamp mask`." |
| **Coding and testing guidance** | Add: "Calibration JSON uses schema v1 with `fit_type='log_linear'`, `coefficients.slope` and `.intercept`, `fit_quality.loo_r2`, and a disclaimer field." |
| | Add: "When adding new derived maps, keep key names stable; tests, export, bar charts, and global scale computation all consume them." |

---

### 3. `features/kubelka_munk_solver.md` — MEDIUM priority

Already a good feature doc. Needs updates:

| Section | Changes |
|---------|---------|
| **Proposed inverse formulation** → rename to **"Implemented formulation (classic KM + fixed scattering)"** | Describe the actual path: reflectance → `F(R) = (1−R)²/(2R)` → `μa ≈ F·μs'/2` → NNLS on A@c≈μa → fitted reflectance reconstruction. |
| After **Validation plan** | Add "Implemented stages" summary referencing stages A–D that were actually built (from implementation plan). |
| Add section: **"GUI Exposure"** | Solver combo includes `km`. Bilirubin Index checkbox + calibration checkbox. Derived maps. Bar chart diagnostic. Export metadata. |
| Add section: **"Validation Outcome"** | Note: KM does NOT recover bili_agat on A1–A6 with current LED set. Bilirubin index is primary diagnostic. |

---

### 4. `features/kubelka_munk_implementation_plan.md` — MEDIUM priority

Already has stages A–D implemented. Needs:

| Section | Changes |
|---------|---------|
| After Stage D | Add **Stage E: Forward Calibration Backend** referencing `app/core/calibration.py`. |
| After Stage E | Add **Stage F: CLI Calibration Save/Load** referencing updated `scripts/bilirubin_index_report.py` with `--save-calibration` and `--load-calibration`. |
| After Stage F | Add **Stage G: GUI Calibration Controls** referencing toolbar changes (Apply Calibration checkbox, Load Calibration button, status label) and new derived maps (`Bilirubin est. (calibrated, see disclaimer)`, `Bilirubin est. clamp mask`). |
| After Stage G | Add **Stage H: Bar Chart Diagnostic Integration** referencing `chromophore_barcharts_panel.py` update to render bilirubin diagnostic subplots. |
| **Next steps** at bottom | Replace with current summary: "Current branch is feature-complete. Remaining open work: ..." with forward validation phantom series design from `forward-calibration-plan.md`. |

---

### 5. New file: `features/bilirubin_index_calibration.md` — MEDIUM priority

Create a single reference doc synthesizing the bilirubin index + calibration work.

Content outline:

```markdown
# Feature: Bilirubin Index and Forward Calibration

## Overview
- Two-band diagnostic: OD450 − OD517
- Optional Hb correction: k_corr × OD671
- Forward log-linear calibration via JSON

## UI Controls
- Bilirubin Index checkbox (toolbar)
- k_corr entry (toolbar)
- Apply Calibration checkbox (toolbar)
- Load Calibration... button (toolbar)
- Calibration status label

## Derived Maps
- Bilirubin Index (OD450-OD517)
- Bili Index (raw) [only when k_corr enabled]
- Bilirubin est. (calibrated, see disclaimer) [only when calibration loaded]
- Bilirubin est. clamp mask [only when calibration loaded]

## Calibration Format (schema v1, log_linear)

## CLI
- scripts/bilirubin_index_report.py --save-calibration / --load-calibration

## Scientific Caveats
- ...
```

---

### 6. `features/spectral_unmixing.md` — LOW priority

Original umbrella feature doc. Quick touch:

| Section | Changes |
|---------|---------|
| Add solver list entry | KM solver. |
| Add derived map entry | Bilirubin index, calibrated estimate. |

---

### 7. Research reports — NO changes needed

The research reports in `research-reports/` are design/plan artifacts and review notes. They do not need updates — they capture decisions at the time they were written. The plan and implementation docs in `features/` are the canonical forward-facing documentation.

---

## Files NOT to Change

| File | Reason |
|------|--------|
| `pyproject.toml` | Unrelated author metadata diff; keep separate from KM work. |
| `research-reports/*.md` | Historical design/plan artifacts; preserved as-is. |
| `subagent-reports/*.md` | Historical subagent task outputs. |

---

## Update Sequence (Recommended Order)

1. **`README.md`** — user-facing, most visible.
2. **`AGENT.md`** — developer guidance, next most important.
3. **`features/kubelka_munk_implementation_plan.md`** — add stages E–H, current state.
4. **`features/kubelka_munk_solver.md`** — update with actual implementation details and validation outcome.
5. **New: `features/bilirubin_index_calibration.md`** — consolidated feature doc.
6. **`features/spectral_unmixing.md`** — minimal touch (optional, low priority).

---

## Key Scientific Caveats to Embed in Every Doc

These must appear in README, AGENT.md, and any feature doc:

1. KM solver does NOT recover bilirubin as a chromophore on the A1–A6 series with the current 8-band LED set.
2. The bilirubin index `OD450−OD517` is a dimensionless diagnostic, not physical concentration.
3. The log-linear calibration yields in-sample R² ≈ 0.942 but negative LOO R² (−4.45); it does not generalize even within the A1–A6 series.
4. Calibrated µM estimates are domain-calibrated diagnostic indicators only.
5. The calibration domain is: 8–270 µM bilirubin, Hb = 100 µM, DNG-derived images, specific camera/LED setup.
6. Do NOT interpret the bilirubin index or calibrated estimate as a replacement for spectral unmixing or as a validated concentration measurement.
