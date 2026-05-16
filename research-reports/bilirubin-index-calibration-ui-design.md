# UI/UX Design: Calibrated Bilirubin Index Support

**Date:** 2026-05-16  
**Branch:** `feature/kubelka-munk-solver`  
**Context:** The GUI already computes a raw `Bilirubin Index (OD450−OD517)` as an optional derived map. This design adds calibrated µM estimation on top of that index, with strict guardrails against overclaiming.

---

## 1. Design Principles

1. **Never show µM without context.** The raw index is primary; calibrated µM is secondary and always annotated with domain/calibration source.
2. **Opt-in calibration.** The user must explicitly load a calibration file. No hidden default calibration.
3. **Fail safe.** If calibration is stale, missing bands, or outside domain, show the raw index and a warning — never a bogus µM value.
4. **Consistent vocabulary.**
   - "Bilirubin Index" = dimensionless diagnostic (always available)
   - "Estimated Bilirubin" = µM conversion from loaded calibration (only when calibration loaded)
   - "Calibrated on …" = provenance label attached to every estimate

---

## 2. Calibration File Format

A JSON file that the user loads via the GUI. Proposed schema:

```json
{
  "schema_version": "1.0",
  "calibration_type": "bilirubin_index_log_linear",
  "formula": "log10([Bili]_uM) = (BI - beta) / alpha",
  "coefficients": {
    "alpha": 0.01405,
    "beta": -0.00024
  },
  "units": {
    "alpha": "1 / log10(uM)",
    "beta": "dimensionless",
    "input": "OD450 - OD517 (dimensionless)",
    "output": "uM"
  },
  "calibration_domain": {
    "bilirubin_uM_min": 8.44,
    "bilirubin_uM_max": 270.0,
    "hemoglobin_uM": 100.0,
    "phantom_series": "A1-A6 liquid Lipofundin phantoms",
    "wavelengths_required": [450, 517],
    "wavelengths_optional": [671]
  },
  "fit_statistics": {
    "n_samples": 6,
    "r_squared_in_sample": 0.942,
    "r_squared_loo": -4.447,
    "rmse_log10": 0.12
  },
  "caveats": [
    "Calibrated on constant-Hb (100 uM) liquid phantoms only.",
    "LOO R² is poor; do not extrapolate outside A1-A6 domain.",
    "Hb variation will bias estimates.",
    "Scattering differences between phantom and sample will bias estimates."
  ],
  "created_by": "scripts/bilirubin_index_report.py",
  "created_date": "2026-05-16",
  "notes": "Optional free-text field for operator annotations."
}
```

**Validation rules on load:**
- `schema_version` must be `"1.0"` (forward compatibility).
- `coefficients.alpha` must be finite and non-zero.
- `coefficients.beta` must be finite.
- `calibration_domain.wavelengths_required` must be a subset of the current dataset's bands.

---

## 3. UI Controls

### 3.1 Toolbar Layout (main toolbar, after solver combo)

Current state already has:
```
[Bilirubin Index] [k_corr: ___]
```

Proposed additions (in a new lightweight sub-row or adjacent group):

```
[Bilirubin Index] [k_corr: ___] | [Load Calib…] [Clear Calib] [Calib: A1-A6 ✓]
```

| Control | Type | Behavior |
|---------|------|----------|
| `Bilirubin Index` checkbox | `QCheckBox` | Existing. Enables computation of raw index. |
| `k_corr` entry | `QLineEdit` | Existing. Optional Hb correction factor. |
| `Load Calibration…` button | `QPushButton` | Opens `QFileDialog` to select a `.json` calibration file. Validates schema and wavelength compatibility. On success, stores path in `self._bilirubin_calibration`. |
| `Clear Calibration` button | `QPushButton` | Removes loaded calibration. Reverts display to raw index only. |
| Calibration status label | `QLabel` | Shows `"Calib: <name>"` or `"Calib: none"`. Green checkmark if loaded and valid; yellow warning if loaded but current bands mismatch; red X if invalid file. |

**Object names:**
- `BILIRUBIN_CALIB_LOAD_BTN_OBJECT_NAME = "bilirubin_calib_load_btn"`
- `BILIRUBIN_CALIB_CLEAR_BTN_OBJECT_NAME = "bilirubin_calib_clear_btn"`
- `BILIRUBIN_CALIB_STATUS_LABEL_OBJECT_NAME = "bilirubin_calib_status_label"`

### 3.2 State Machine

```
[Checkbox unchecked]
    → Raw index NOT computed. Calibration controls disabled/greyed.

[Checkbox checked, no calibration loaded]
    → Raw index computed. Derived map: "Bilirubin Index (OD450-OD517)".
    → Pixel inspector shows raw value.
    → Export saves raw index arrays/maps.

[Checkbox checked, calibration loaded]
    → Raw index computed + calibrated µM computed.
    → Derived maps:
        - "Bilirubin Index (OD450-OD517)" (raw)
        - "Estimated Bilirubin (uM)" (calibrated, only if calib loaded)
    → Pixel inspector shows:
        - Raw index value
        - Estimated µM with "est." prefix and domain caveat
    → Export saves both maps + calibration provenance in metadata.
```

---

## 4. Labels and Warnings

### 4.1 Map Titles (Maps Panel)

| Key | Title shown |
|-----|-------------|
| `Bilirubin Index (OD450-OD517)` | `"Bilirubin Index (OD450−OD517)\nμ=…, med=…"` |
| `Estimated Bilirubin (uM)` | `"Estimated Bilirubin (µM)\nCalib: A1-A6 phantoms\nμ=…, med=…"` |

The calibrated map title **always** includes the calibration source on a second line. This prevents screenshots from being misinterpreted.

### 4.2 Colorbar Labels

- Raw index: `"Index (dimensionless)"`
- Estimated µM: `"µM (estimated)"`

### 4.3 Pixel Inspector

```
Concentrations:
  Hb_agat_extr:  …
  bili_agat:     …

Derived Maps:
  THb:                    …
  StO2:                   …
  Bilirubin Index:        0.0245
  Est. Bilirubin (µM):    ~57 µM
    └─ Calib: A1-A6, Hb=100 µM assumed
    └─ Domain: 8.4–270 µM
```

If pixel index is outside calibration domain (e.g., negative raw index, or converted µM < 8 or > 300):
```
  Est. Bilirubin (µM):    ~5 µM
    ⚠ Outside calibration domain (8.4–270 µM). Estimate unreliable.
```

### 4.4 Status Bar

When a sample with calibrated bilirubin is selected:
```
Ready | Bili index: 2-band diagnostic | Calib: A1-A6 phantoms (Hb=100 µM)
```

If calibration loaded but bands mismatch:
```
Warning | Calibration requires 450+517 nm; current dataset missing 517 nm
```

### 4.5 Tooltip on Load Calibration Button

```
"Load a bilirubin-index calibration JSON (schema v1.0). "
"The calibration converts the raw OD450−OD517 index into approximate µM. "
"Only load calibrations that match your phantom/sample type and Hb level."
```

### 4.6 Export Metadata (`metadata.json`)

When calibrated map is exported:
```json
{
  "bilirubin_index_note": "...",
  "bilirubin_calibration": {
    "loaded": true,
    "file": "/path/to/calib.json",
    "alpha": 0.01405,
    "beta": -0.00024,
    "domain_uM": [8.44, 270.0],
    "caveats": ["..."],
    "fit_r2_in_sample": 0.942,
    "fit_r2_loo": -4.447
  }
}
```

If no calibration loaded, `"bilirubin_calibration": {"loaded": false}`.

---

## 5. Computation Layer Changes

### 5.1 `app/core/processing.py`

Add:

```python
def apply_bilirubin_calibration(
    bilirubin_index: np.ndarray,
    calibration: dict,
) -> dict:
    """
    Convert raw bilirubin index to estimated µM using a loaded calibration.

    Returns dict with:
        'estimated_uM': np.ndarray — same shape as input
        'valid_domain_mask': np.ndarray — bool, True where index is within
            the calibration's plausible input range (alpha*log10(min)+beta
            to alpha*log10(max)+beta).
        'outside_domain_fraction': float — fraction of pixels outside domain
    """
    alpha = calibration["coefficients"]["alpha"]
    beta = calibration["coefficients"]["beta"]
    log10_bili = (bilirubin_index - beta) / alpha
    estimated_uM = 10.0 ** log10_bili
    # Domain mask: exclude negative index, or extreme µM
    domain = calibration["calibration_domain"]
    bi_min = alpha * np.log10(domain["bilirubin_uM_min"]) + beta
    bi_max = alpha * np.log10(domain["bilirubin_uM_max"]) + beta
    valid = (bilirubin_index >= bi_min) & (bilirubin_index <= bi_max) & np.isfinite(estimated_uM)
    return {
        "estimated_uM": estimated_uM,
        "valid_domain_mask": valid,
        "outside_domain_fraction": float(1.0 - valid.mean()),
    }
```

### 5.2 Pipeline Adapter (`app/gui_qt/main_window.py`)

After computing `bilirubin_index`, if calibration is loaded:

```python
if snapshot.get("bilirubin_calibration") is not None:
    calib_result = processing.apply_bilirubin_calibration(
        bilirubin_index["bi_corrected"],
        snapshot["bilirubin_calibration"],
    )
    derived["Estimated Bilirubin (uM)"] = calib_result["estimated_uM"]
    diagnostics["bilirubin_outside_domain_fraction"] = calib_result["outside_domain_fraction"]
```

Add to diagnostics warnings if `outside_domain_fraction > 0.1`:
```python
warnings.append(
    f"{calib_result['outside_domain_fraction']*100:.1f}% of pixels are outside "
    f"the bilirubin calibration domain ({domain['bilirubin_uM_min']:.1f}–"
    f"{domain['bilirubin_uM_max']:.1f} µM). Estimates in those regions are unreliable."
)
```

---

## 6. User Workflow

### 6.1 First-Time User (no calibration)

1. Open app → load hypercubes folder.
2. Select chromophores `bili_agat` + `hb_agat_extr`.
3. Check **Bilirubin Index** checkbox.
4. Click **Run**.
5. Switch Maps panel to **Derived Maps**.
6. See map: `"Bilirubin Index (OD450−OD517)"` with dimensionless colorbar.
7. Interpret as trend: higher = more bilirubin-like absorption.

### 6.2 Calibrated User (with A1-A6 calibration file)

1–4. Same as above.
5. Click **Load Calibration…** → select `a1_a6_bili_calibration.json`.
6. Status label shows `"Calib: A1-A6 ✓"`.
7. Click **Run** (or re-run if already run).
8. Switch Maps panel to **Derived Maps**.
9. See two maps:
   - `"Bilirubin Index (OD450−OD517)"` (raw)
   - `"Estimated Bilirubin (µM)"` (calibrated, title notes calibration source)
10. Click a pixel → Inspector shows raw index + estimated µM with domain caveat.
11. Save → `metadata.json` contains calibration provenance + caveats.

### 6.3 Wrong Dataset Warning

1. User loads calibration requiring 450+517 nm.
2. User switches to a dataset with only 500–900 nm bands.
3. Status label turns yellow: `"Calib: bands mismatch (needs 450, 517)"`.
4. Run is blocked with dialog: `"Calibration requires 450 nm and 517 nm bands."`

---

## 7. File Changes Summary

| File | Change |
|------|--------|
| `app/core/processing.py` | Add `apply_bilirubin_calibration()` |
| `app/gui_qt/main_window.py` | Add load/clear calib buttons + status label; validate calib on load; compute calibrated map in pipeline; add calib metadata to diagnostics |
| `app/gui_qt/panels/maps_panel.py` | No changes — auto-renders new derived keys |
| `app/gui_qt/panels/inspector_panel.py` | Append calibrated estimate with caveat text |
| `app/core/export.py` | Write `bilirubin_calibration` block to metadata.json |
| `tests/test_main_window.py` | Tests for calib load/clear, snapshot, validation, domain warnings |
| `tests/test_processing_bilirubin_calibration.py` | Unit tests for `apply_bilirubin_calibration` (domain mask, inverses, edge cases) |
| `scripts/bilirubin_index_report.py` | Output `research-reports/bilirubin-index-calibration.json` in v1.0 schema |

---

## 8. Non-Goals

- Do NOT auto-generate a calibration from the current run. Calibration must come from an external, validated source.
- Do NOT store calibration coefficients in the app config / preferences. Each dataset may need a different calibration.
- Do NOT add a "Calibrate Now" button that fits A1-A6 on the fly. The fitting script exists; the GUI consumes its output.
- Do NOT modify chromophore concentration maps. The calibrated estimate lives only in derived maps.
- Do NOT support multiple simultaneous calibrations. One active calibration at a time.

---

## 9. Risk Register

| Risk | Mitigation |
|------|-----------|
| User loads wrong calibration (e.g., Hb=150 µM calib on Hb=100 µM data) | Schema includes `calibration_domain.hemoglobin_uM`; warning shown if mismatch is detectable |
| User screenshots "Estimated Bilirubin" without the calibration caveat | Map title always includes calibration source; pixel inspector includes domain warning |
| Calibration JSON is hand-edited to garbage coefficients | Validate `alpha != 0`, finite coefficients, and `r_squared_loo` present (even if negative) |
| Negative raw index produces `log10` of negative → NaN | `apply_bilirubin_calibration` uses `np.isfinite` mask; NaN pixels shown as transparent/gray in map |
| Domain mask too aggressive (flags good pixels as outside) | Use calibration's min/max as inclusive bounds; allow 10% slack before warning |

---

*End of design document.*
