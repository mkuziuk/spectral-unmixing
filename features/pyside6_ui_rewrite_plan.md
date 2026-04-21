## Feature: UI rewrite to PySide6 with exact layout parity

### Goal
Rebuild the current tkinter UI in **PySide6** while preserving the **same visual layout, tab structure, control order, and interaction flow**.

This is a UI technology migration, not a processing rewrite.

---

## Migration scope

### In scope
1. Replace tkinter/ttk UI layer with PySide6 widgets.
2. Preserve main window geometry and high-level layout composition.
3. Preserve all existing tabs and controls in the same relative positions.
4. Keep current pipeline behavior, threading behavior, and status/progress updates.
5. Keep matplotlib embedded plots for all visualization tabs.
6. Add parity checks to verify layout/behavior against current app.

### Out of scope (for this phase)
1. Redesign/retheme UI.
2. Changes to spectral processing math or data model.
3. Feature additions unrelated to migration.

---

## Current UI baseline to reproduce (from existing tkinter app)

### Window-level
- Title: `Spectral Unmixing`
- Initial size: `1400 x 900`
- Minimum size: `1000 x 700`

### Top toolbar (left → right order must remain)
1. `📂 Select Root Folder` button
2. `🧪 Select Data Folder` button
3. `🔄 Use Default Data` button
4. `Chromophores` menu button (checkable entries + `Background`)
5. `Solver:` label + readonly combo (`ls`, `nnls`)
6. `Background:` label + numeric entry (`2500.0` default)
7. `▶ Run Unmixing` button
8. `💾 Save Results` button
9. Progress bar
10. Data source status label (`Data: default/custom ...`)
11. Main status label (`No folder selected`, `Processing...`, etc.)

### Main content split (horizontal)
- **Left sidebar**
  - `Folder Info` header + read-only text box
  - `Sample` header + readonly combo
  - `Warnings` header + read-only text (red)
- **Right content**: tab widget with 4 tabs
  1. `Maps`
  2. `Pixel Inspector`
  3. `Diagnostics`
  4. `Reflectance Stats`

### Tab internals
- **Maps**
  - Top controls: `View` combo (`Chromophore Maps`, `Derived Maps`, `Raw / Reflectance / OD`), `Band` combo
  - Embedded matplotlib figure canvas
  - Navigation toolbar at bottom
- **Pixel Inspector**
  - Internal horizontal split
  - Left: clickable preview image
  - Right: spectra chart + `Concentrations` text box
- **Diagnostics**
  - Top `Quality Metrics` text box
  - Bottom matplotlib figure (RMSE histogram + quality mask)
- **Reflectance Stats**
  - Top `Statistic` combo (`Mean`, `Median`)
  - Bottom matplotlib figure + nav toolbar

---

## Proposed PySide6 architecture

### UI package structure
```text
app/gui_qt/
  main_window.py           # QMainWindow equivalent of app_window.py
  panels/
    maps_panel.py
    inspector_panel.py
    diagnostics_panel.py
    stats_panel.py
  widgets/
    chromophore_menu.py    # helper for checkable chromophore actions
  mpl/
    canvas.py              # shared matplotlib Qt canvas helpers
```

### Mapping tkinter → PySide6
- `tk.Tk` → `QMainWindow`
- `ttk.Frame` → `QWidget` + `QVBoxLayout/QHBoxLayout`
- `ttk.PanedWindow` → `QSplitter`
- `ttk.Notebook` → `QTabWidget`
- `ttk.Button` → `QPushButton`
- `ttk.Combobox` → `QComboBox`
- `tk.Text` → `QPlainTextEdit` (read-only where needed)
- `ttk.Progressbar` → `QProgressBar`
- `tk.Menu` checkbuttons → `QMenu` + checkable `QAction`
- `filedialog/messagebox` → `QFileDialog/QMessageBox`
- `after(...)` UI callbacks → Qt signals/slots (`QMetaObject.invokeMethod` or signal emissions)

---

## Detailed UI element specification

### Toolbar (QToolBar / QWidget)

| Widget Name | Placement | Default Value/State | Interactions/Events | Data Dependencies | Parity Checks |
|-------------|-----------|---------------------|---------------------|-------------------|---------------|
| `select_root_btn` | Left side | Enabled, text `📂 Select Root Folder` | `clicked()` → `_on_select_folder()` | None | Must match tkinter button order, padding |
| `select_data_btn` | Left of `use_default_btn` | Enabled, text `🧪 Select Data Folder` | `clicked()` → `_on_select_data_folder()` | None | Same position, same padding |
| `use_default_btn` | Left of `chromophore_menu` | Enabled, text `🔄 Use Default Data` | `clicked()` → `_on_reset_data_folder()` | None | Same position, same padding |
| `chromophore_menu` | Left of `solver_label` | Text `Chromophores`, checkable menu items | `triggered(QAction)` → toggle chromophore | `data_dir`, `chrom_vars` dict | Menu items must match tkinter order |
| `chromophore_menu.background_action` | Nested in menu | Checked (`True`) | `toggled(bool)` → update `background_var` | `background_var` | Background always present, always checked initially |
| `solver_label` | Left of `solver_combo` | Text `Solver:` | None | None | Label text, spacing |
| `solver_combo` | Left of `background_label` | `ls`, readonly, width 8 | `currentIndexChanged(str)` → update `solver_var` | `solver_var` (default `"ls"`) | Same values, state, width |
| `background_label` | Left of `bg_entry` | Text `Background:` | None | None | Label text, spacing |
| `bg_entry` | Left of `run_btn` | Text `2500.0`, width 8 | `editingFinished()` → parse and update `background_value_var` | `background_value_var` (default `"2500.0"`) | Same default, width, validation behavior |
| `run_btn` | Left of `save_btn` | Initially disabled, text `▶ Run Unmixing` | `clicked()` → `_on_run()` | `root_dir` (enabled if set) | Same initial disabled state |
| `save_btn` | Left of `progress_bar` | Initially disabled, text `💾 Save Results` | `clicked()` → `_on_save()` | `results` dict (enabled if non-empty) | Same initial disabled state |
| `progress_bar` | Left of `data_source_label` | Mode `determinate`, max 100 | `valueChanged(int)` | Pipeline progress signals | Length ~200px, same mode |
| `data_source_label` | Left of `status_label` | Text `Data: default (xxx)` or `Data: custom (xxx)` | None | `data_dir` path | Same initial text format |
| `status_label` | Rightmost | Text `No folder selected` | None | Pipeline status signals | Same text updates |

**Sidebar (QSplitter left pane)**

| Widget Name | Placement | Default Value/State | Interactions/Events | Data Dependencies | Parity Checks |
|-------------|-----------|---------------------|---------------------|-------------------|---------------|
| `folder_info_header` | Top | Text `Folder Info`, bold font | None | None | Same header style |
| `folder_info_text` | Below header | Read-only, `QPlainTextEdit`, width ~30, height ~12 | None | `folder_info` dict | Same content format, read-only |
| `sample_header` | Below info | Text `Sample`, bold font | None | None | Same header style |
| `sample_combo` | Below header | Read-only, width ~25, empty initially | `currentIndexChanged(str)` → `_on_sample_selected()` | `sample_names` list | Same behavior, width |
| `warnings_header` | Below sample | Text `Warnings`, bold font | None | None | Same header style |
| `warnings_text` | Bottom, expands | Read-only, red text, `QPlainTextEdit` | None | `diagnostics.warnings` list | Same red color, same read-only behavior |

**Tab Widget (QTabWidget)**

#### Tab 1: Maps

| Widget Name | Placement | Default Value/State | Interactions/Events | Data Dependencies | Parity Checks |
|-------------|-----------|---------------------|---------------------|-------------------|---------------|
| `view_label` | Top-left | Text `View:` | None | None | Same label text |
| `view_combo` | Right of view_label | `Chromophore Maps`, readonly, width 25 | `currentIndexChanged(str)` → `_on_view_changed()` | `view_var` (default `"Chromophore Maps"`) | Same values, same order |
| `band_label` | Right of view_combo | Text `Band:` | None | None | Same label text |
| `band_combo` | Right of band_label | Empty initially, width 10 | `currentIndexChanged(str)` → `_on_view_changed()` | `wavelengths` list | Same width, same event binding |
| `mpl_canvas` | Center, expands | `FigureCanvasQTAgg`, embedded | Click events, resize | Current view data | Same size, same DPI |
| `mpl_nav_toolbar` | Bottom | `NavigationToolbar2QT` | Zoom, pan, save | Canvas | Same toolbar buttons |

#### Tab 2: Pixel Inspector

| Widget Name | Placement | Default Value/State | Interactions/Events | Data Dependencies | Parity Checks |
|-------------|-----------|---------------------|---------------------|-------------------|---------------|
| `left_split` | Left of `right_split` | Weight 1, `QSplitter` | Drag to resize | None | Same split ratio |
| `inspector_click_label` | Top-left | Text `Click a pixel on the image below:` | None | None | Same label text |
| `img_canvas` | Below label in left_split | `FigureCanvasQTAgg`, 4x4 fig, gray | `mousePressEvent` → `_on_click()` | `sample_cube` | Same size, click handler |
| `right_split` | Right of `left_split` | Weight 2, `QSplitter` | Drag to resize | None | Same split ratio |
| `spec_canvas` | Top-right, expands | `FigureCanvasQTAgg`, 7x4 fig | None | Spectra data | Same size, DPI |
| `conc_label_frame` | Below spec_canvas | Text `Concentrations`, padding 4 | None | None | Same frame title, padding |
| `conc_text` | Inside label_frame | Read-only, height 8, width 50 | None | Concentration values | Same read-only behavior |
| `inspector_crosshair` | Drawn on img_canvas | Red line + plus marker | None | `selected_pixel` | Same visual style |

#### Tab 3: Diagnostics

| Widget Name | Placement | Default Value/State | Interactions/Events | Data Dependencies | Parity Checks |
|-------------|-----------|---------------------|---------------------|-------------------|---------------|
| `stats_frame` | Top, padding 8 | Text `Quality Metrics`, padding 8 | None | None | Same frame title |
| `stats_text` | Inside frame | Read-only, height 6 | None | `diagnostics` dict | Same content format |
| `diag_canvas` | Below frame, expands | `FigureCanvasQTAgg`, 10x4 fig | None | `rmse_map`, `diagnostics` | Same size, DPI |
| `rmse_histogram_ax` | Left subplot | Histogram (50 bins) | None | `rmse_map` | Same bin count, color |
| `quality_mask_ax` | Right subplot | `cmap="Reds"` | None | `rmse_map`, median threshold | Same threshold logic |

#### Tab 4: Reflectance Stats

| Widget Name | Placement | Default Value/State | Interactions/Events | Data Dependencies | Parity Checks |
|-------------|-----------|---------------------|---------------------|-------------------|---------------|
| `stat_label` | Top-left | Text `Statistic:` | None | None | Same label text |
| `stat_combo` | Right of stat_label | `Median`, readonly, width 15 | `currentIndexChanged(str)` → `_on_stat_changed()` | `stat_var` (default `"Median"`) | Same values, same order |
| `stat_canvas` | Center, expands | `FigureCanvasQTAgg`, 8x5 fig | None | `reflectance` | Same size, DPI |
| `stat_nav_toolbar` | Bottom | `NavigationToolbar2QT` | Zoom, pan, save | Canvas | Same toolbar buttons |

---

## Review findings (completeness + corrections)

### Completeness verdict
The plan is strong on widget inventory and tab composition, but implementation risk remained in parity details that were implicit rather than testable. This revision adds explicit parity non-negotiables, state matrices, signal/data contracts, and per-ticket test specs.

### Gaps identified and resolved
1. **Control-state parity was underspecified** (idle vs running vs results-ready).
   - Added explicit enable/disable matrix and acceptance hooks in backlog/tests.
2. **Splitter proportions and resize behavior lacked measurable constraints.**
   - Added required baseline capture and tolerance checks (`±2%`) for main and inspector splitters.
3. **Redraw behavior was ambiguous** (colorbar duplication, excessive redraws, stale axes).
   - Added redraw non-negotiables and dedicated validation in map/plot tickets.
4. **Data dependency and signal wiring contracts were partial.**
   - Added event contract section with producer/consumer payloads.
5. **Empty/error states were not explicit.**
   - Added required default text/placeholder behavior and failure-path assertions in test matrix.
6. **Some ticket difficulty labels understated integration effort.**
   - Relabeled integration-heavy tasks (notably QT-013, QT-014, and QT-001).

### Added parity non-negotiables
1. **Widget identity for testing:** every key control listed in spec must have stable `objectName`.
2. **State matrix parity:** button/combo enabled states must match tkinter behavior for `startup`, `data_loaded`, `running`, `run_complete`, `error`.
3. **Splitter parity:**
   - Main splitter (sidebar/content) and inspector splitter (image/spectra) must initialize to tkinter-equivalent proportions.
   - Proportions captured from baseline screenshots and accepted within `±2%`.
4. **Tab order lock:** `Maps`, `Pixel Inspector`, `Diagnostics`, `Reflectance Stats` order is immutable.
5. **Redraw correctness:** each selector change updates exactly one active figure state (no stacked colorbars/axes leakage).
6. **Status semantics parity:**
   - `data_source_label` format remains `Data: default/custom (...)`.
   - `status_label` transitions include at minimum: `No folder selected`, `Processing...`, success/failure terminal message.
7. **Thread boundary rule:** worker thread emits data-only signals; widget mutation occurs only on GUI thread.

### Event wiring and data contract addendum

| Event/Signal | Producer | Consumer | Contract | Notes |
|---|---|---|---|---|
| `root_selected(path)` | Toolbar callback | Main window state + sidebar refresh | Absolute existing directory path | Enables `run_btn` only when valid sample set exists |
| `data_source_changed(mode, path)` | Data folder/default actions | Toolbar labels + model refresh | `mode ∈ {default, custom}`, normalized path | Updates `data_source_label` immediately |
| `sample_changed(sample_id)` | `sample_combo` | All tab panels | Stable sample key/string | Must trigger synchronized redraw across tabs |
| `run_requested(config)` | `run_btn` | Worker thread | Immutable config (`solver`, `background`, selected chromophores, folders) | Snapshot config at click time |
| `progress_updated(percent, message)` | Worker thread | Progress/status widgets | `percent: int[0..100]`, `message: str` | Monotonic percent; GUI-thread slot only |
| `results_ready(results)` | Worker thread | All tab presenters + save enablement | Non-empty result bundle with wavelengths/maps/diagnostics | Enables `save_btn`; refreshes all tabs |
| `run_failed(error_text)` | Worker thread | Status + warnings surfaces | Human-readable error string | Resets run state; save remains disabled |
| `pixel_selected(x, y)` | Maps/Inspector canvas click | Inspector renderer | Integer pixel coordinates in-bounds | Updates crosshair, spectra, concentrations |

---

## Ticket Backlog

| ID | Title | Scope | Dependencies | Difficulty | Acceptance Criteria |
|----|-------|-------|--------------|------------|---------------------|
| QT-001 | Add import-safe module stubs in `gui_qt` | Architecture | QT-023 | MEDIUM | `main_window.py`, panel modules, widget helpers, and mpl helpers exist and import without side effects |
| QT-002 | Implement `QMainWindow` shell with title/geometry | Shell | QT-001 | EASY | Window title `"Spectral Unmixing"`, initial size 1400x900, min size 1000x700 |
| QT-003 | Build toolbar layout with spacer/padding parity | Toolbar | QT-002 | MEDIUM | All 11 toolbar elements in exact order with stable `objectName`s; padding/spacing visually aligned to baseline screenshots |
| QT-004 | Implement chromophore checkable menu | Toolbar | QT-003 | MEDIUM | Menu shows all chromophores + Background, toggles update backend state |
| QT-005 | Implement background entry parsing/validation | Toolbar | QT-003, QT-024 | MEDIUM | Background numeric parsing/validation wired to state; invalid value reverts/flags without crashing |
| QT-006 | Build main splitter (sidebar + tab widget) | Shell | QT-002 | MEDIUM | Horizontal `QSplitter` with baseline-matched initial proportions (`±2%`) and same spacing |
| QT-007 | Implement folder info sidebar | Sidebar | QT-006 | MEDIUM | Info text, sample combo, warnings text with same read-only behavior |
| QT-008 | Implement Maps tab (view/band selectors + canvas) | Maps | QT-006 | MEDIUM | Three view modes, band selector updates, matplotlib canvas embedded |
| QT-009 | Implement Pixel Inspector tab layout | Inspector | QT-006 | MEDIUM | Left/right splitter, clickable image canvas, spectra canvas, concentrations frame |
| QT-010 | Implement Diagnostics tab layout | Diagnostics | QT-006 | MEDIUM | Stats text frame, RMSE histogram + quality mask plot |
| QT-011 | Implement Reflectance Stats tab layout | Stats | QT-006 | MEDIUM | Stat selector combo, line plot canvas, navigation toolbar |
| QT-012 | Implement pipeline thread and progress signals | Threading | QT-003 | HARD | Worker in QThread, progress/status signals, run/save button state transitions |
| QT-013 | Wire toolbar callbacks to backend | Callbacks | QT-003, QT-007, QT-012 | HARD | Folder/data selection, run pipeline, save results, sample selection wired with explicit state transitions and error-path handling |
| QT-014 | Implement Maps view/redraw logic | Maps | QT-008 | HARD | Chromophore/derived/raw view switching, band selection, single colorbar policy, no stale artists |
| QT-015 | Implement Pixel Inspector click handler | Inspector | QT-009 | MEDIUM | Pixel click → crosshair, spectra plot, concentration table update |
| QT-016 | Implement Diagnostics plot updates | Diagnostics | QT-010, QT-025 | MEDIUM | RMSE histogram and quality mask update correctly from diagnostics payload |
| QT-017 | Implement Reflectance Stats plot updates | Stats | QT-011 | MEDIUM | Mean/Median toggle, wavelength line plot, grid |
| QT-018 | Add basic UI smoke tests with pytest-qt | Tests | QT-001, QT-002 | MEDIUM | Window launches, tabs exist, key widgets present, no crashes |
| QT-019 | Add interaction tests for key flows | Tests | QT-013, QT-014, QT-015, QT-016, QT-017, QT-018 | HARD | Sample selection, view toggles, run/save button states, save export |
| QT-020 | Execute parity evidence capture against checklist | Documentation | All tabs, QT-026 | MEDIUM | Before/after screenshots captured for required states; completed checklist maps each parity criterion to pass/block evidence |
| QT-021 | Add cutover entrypoint and legacy flag | Cutover | QT-019, QT-020 | HARD | `app/main.py` launches Qt UI, legacy tkinter behind flag, rollback path |
| QT-022 | Clean up tkinter UI after validation | Cutover | QT-021 | MEDIUM | Remove legacy tkinter files only after stable validation period |
| QT-023 | Create `gui_qt` package skeleton directories/files | Architecture | None | EASY | `app/gui_qt/`, `panels/`, `widgets/`, `mpl/`, and package `__init__.py` files are created in expected paths |
| QT-024 | Add readonly solver combo defaults/options | Toolbar | QT-003 | EASY | Solver combo is readonly with ordered options `ls`, `nnls`; default selection is `ls` |
| QT-025 | Populate warnings text from diagnostics list | Diagnostics | QT-007, QT-010 | EASY | Warnings panel renders diagnostics warnings as read-only red text and clears when warnings are empty |
| QT-026 | Author parity checklist template | Documentation | QT-003, QT-006, QT-008, QT-009, QT-010, QT-011 | EASY | Checklist template exists with required sections: toolbar order, tab order, splitter ratios, state matrix, and status-label semantics |

---

## Ticket-to-test matrix (primary test per ticket)

> One primary test is defined per ticket (`QT-001`..`QT-026`). Tests are intentionally practical and can be expanded later.

| Ticket | Test Type | Scope | Setup / Fixtures | Steps | Assertions | Failure Signals |
|---|---|---|---|---|---|---|
| QT-001 | Unit | Import-safe Qt module stubs | Temp import environment, `importlib` | Import `app.gui_qt.main_window` and panel/widget/mpl stubs | Imports succeed without starting app/event loop or other side effects | ImportError, side-effect startup, missing stub module |
| QT-002 | UI (`pytest-qt`) | Main window shell geometry | `qapp`, instantiate MainWindow | Show window; read title, initial size, min size | Title exact; size/min-size exact or platform-safe tolerance | Wrong title, wrong geometry, crash on show |
| QT-003 | UI (`pytest-qt`) | Toolbar order/presence parity | MainWindow with objectNames | Query toolbar children by order | 11 controls present in required left→right order; objectNames stable | Missing/reordered controls, unnamed widgets |
| QT-004 | Integration | Chromophore menu + state wiring | Fixture with sample chromophore list + state store | Open menu; toggle item + Background | State updates match toggles; item order equals baseline; Background initially checked | Toggle ignored, order mismatch, incorrect default check |
| QT-005 | Integration | Background parsing/validation behavior | MainWindow + validation hooks | Edit background with valid and invalid values | Valid number commits to state; invalid input reverts/flags without crash | Invalid parse accepted silently, crash on invalid edit |
| QT-006 | UI (`pytest-qt`) | Main splitter parity | MainWindow with baseline ratio fixture | Show window; inspect splitter sizes | Sidebar/content ratio matches baseline within `±2%`; splitter exists and resizes | Ratio drift beyond tolerance, missing splitter |
| QT-007 | UI (`pytest-qt`) | Sidebar rendering/behavior | Fixture with folder info, samples, warnings | Load fixture state into sidebar | Headers present; text widgets read-only; warnings styled red; sample combo readonly | Editable text areas, missing style, sample control mismatch |
| QT-008 | UI (`pytest-qt`) | Maps tab structure | MainWindow with Maps tab | Activate Maps tab | `view_combo`, `band_combo`, canvas, nav toolbar present; default view correct | Missing controls, wrong default view, canvas init error |
| QT-009 | UI (`pytest-qt`) | Pixel Inspector layout split | MainWindow with Inspector tab | Activate tab; inspect nested splitter and widgets | Left image canvas + right spectra/conc widgets present; initial split ratio baseline-aligned | Missing panel elements, wrong split setup |
| QT-010 | UI (`pytest-qt`) | Diagnostics tab layout | MainWindow + Diagnostics tab | Activate tab | Quality metrics text + diagnostics canvas with 2 subplot axes initialized | Missing frame/text/axes, figure init failure |
| QT-011 | UI (`pytest-qt`) | Reflectance Stats layout | MainWindow + Stats tab | Activate tab | `stat_combo`, canvas, nav toolbar present; default stat set to parity value | Missing toolbar/combo/canvas, wrong default |
| QT-012 | Integration | Worker-thread signaling + state transitions | Fake worker emitting progress/results/fail signals | Start run; emit progress then complete/fail branches | UI updates via signals; run disabled during run; save enabled only on success; no direct worker→widget calls | Frozen UI, illegal thread access, wrong button states |
| QT-013 | Integration | End-to-end toolbar callback wiring | Mock backend service + file dialogs | Trigger select root/data/default/run/save/sample actions | Correct backend methods called with expected args; status labels update on success/error paths | Callback not invoked, wrong payloads, stale status text |
| QT-014 | Integration/UI | Maps redraw correctness | Fixture result bundle with multiple views/bands | Switch view modes and bands repeatedly | Canvas updates each switch; exactly one active colorbar; no stale artists or duplicated axes | Layered colorbars, stale image, exceptions on repeat toggles |
| QT-015 | Integration/UI | Pixel click interaction | Inspector with deterministic sample cube | Click known pixel coordinates | Crosshair moves to clicked pixel; spectra and concentration text update consistently | Crosshair mismatch, unchanged spectra/text, out-of-bounds crash |
| QT-016 | Integration/UI | Diagnostics rendering update | Diagnostics fixture (`rmse_map`) | Apply diagnostics update | Histogram bins and quality mask rendered from payload | Empty plot with valid data, incorrect mask/histogram behavior |
| QT-017 | Integration/UI | Reflectance stat switching | Reflectance fixture with known mean/median differences | Toggle `Mean`/`Median` | Curve changes to expected statistic; axes labels/grid retained | Toggle no-op, incorrect curve, formatting regression |
| QT-018 | UI smoke | App boot and critical widgets | Test app launch fixture | Launch and close main window | No crash; all four tabs + core toolbar widgets discoverable | Startup crash, missing core widgets |
| QT-019 | Integration/UI | Critical user flow | Mock pipeline + temp output dir | Select sample, change view, run, wait completion, save | State transitions valid; file save invoked; plots refresh | Save before results, run not gated, stale plots |
| QT-020 | Manual + visual regression | Parity evidence capture execution | Baseline tkinter screenshots + checklist template (QT-026) | Capture Qt screenshots for required states; fill checklist evidence columns | Required screenshots attached; each checklist row has pass/block disposition and evidence reference | Missing screenshot states, incomplete evidence mapping |
| QT-021 | Integration | Cutover entrypoint and fallback | CLI/entrypoint fixture with feature flag | Launch default and legacy-flag modes | Default starts Qt UI; legacy flag starts tkinter path; rollback path documented | Wrong UI launched, missing fallback behavior |
| QT-022 | Manual + CI hygiene | Legacy removal safety | Branch with cleanup candidate | Run full test suite and startup checks after removals | No tkinter runtime references remain; Qt path passes regression suite | Broken imports, hidden tkinter dependency, startup failure |
| QT-023 | Unit | Package skeleton existence | Filesystem assertion fixture | Check expected `app/gui_qt` package paths | Expected directories and package `__init__.py` files exist | Missing folder/file, wrong package path |
| QT-024 | UI (`pytest-qt`) | Solver combo defaults/options | MainWindow with toolbar initialized | Inspect solver combo properties and options | Combo is readonly; options are exactly `ls`, `nnls` in order; default is `ls` | Editable combo, wrong option set/order, wrong default |
| QT-025 | Integration/UI | Diagnostics warnings text population | Diagnostics fixture with warnings list and empty list | Apply diagnostics payload with warnings then without warnings | Warning lines appear in red read-only widget; cleared state shown for empty warnings | Warnings not shown/cleared, widget becomes editable |
| QT-026 | Documentation review | Parity checklist template completeness | Template path fixture | Open checklist template and inspect sections | Required sections present: toolbar/tab order, splitter ratio, state matrix, status semantics | Missing required section, ambiguous checklist fields |

---

## Parallel workstreams (dependency-aware)

### WS-A: Shell/Foundation
- **Tickets**: QT-023, QT-001, QT-002, QT-006, QT-007
- **Prerequisites**:
  - QT-001 after QT-023
  - QT-002 after QT-001
  - QT-006 after QT-002
  - QT-007 after QT-006
- **Can run concurrently**:
  - QT-003 (WS-B) can start as soon as QT-002 lands (in parallel with QT-006)
  - QT-008/009/010/011 (WS-C) can run in parallel once QT-006 is complete

### WS-B: Toolbar/Controls
- **Tickets**: QT-003, QT-024, QT-004, QT-005
- **Prerequisites**:
  - QT-003 after QT-002
  - QT-024/QT-004/QT-005 after QT-003
- **Can run concurrently**:
  - QT-024, QT-004, QT-005 can run in parallel
  - QT-012 (WS-D) can start after QT-003 without waiting for QT-004/QT-005

### WS-C: Tabs/Layout
- **Tickets**: QT-008, QT-009, QT-010, QT-011, QT-025
- **Prerequisites**:
  - QT-008/009/010/011 after QT-006
  - QT-025 after QT-007 and QT-010
- **Can run concurrently**:
  - QT-008, QT-009, QT-010, QT-011 are fully parallel after QT-006
  - QT-014/015/016/017 (WS-D) can start per-tab as each tab layout lands

### WS-D: Threading/Wiring/Behavior
- **Tickets**: QT-012, QT-013, QT-014, QT-015, QT-016, QT-017
- **Prerequisites**:
  - QT-012 after QT-003
  - QT-013 after QT-003, QT-007, QT-012
  - QT-014 after QT-008
  - QT-015 after QT-009
  - QT-016 after QT-010 and QT-025
  - QT-017 after QT-011
- **Can run concurrently**:
  - QT-014, QT-015, QT-017 can proceed in parallel once their tab layouts are done
  - QT-013 can proceed in parallel with tab behavior tickets once QT-012 and QT-007 are done

### WS-E: Test Infrastructure/Automation
- **Tickets**: QT-018, QT-019
- **Prerequisites**:
  - QT-018 after QT-001 and QT-002
  - QT-019 after QT-013/014/015/016/017 and QT-018
- **Can run concurrently**:
  - Author tests for QT-003/006/008/009/010/011/012/024 early using mocks/fixtures while implementation is in-flight

### WS-F: Docs/Parity/Cutover
- **Tickets**: QT-026, QT-020, QT-021, QT-022
- **Prerequisites**:
  - QT-026 after QT-003, QT-006, QT-008, QT-009, QT-010, QT-011
  - QT-020 after all tabs and QT-026
  - QT-021 after QT-019 and QT-020
  - QT-022 after QT-021
- **Can run concurrently**:
  - QT-026 drafting can begin as soon as foundational layout tickets complete, before full integration

## Critical path and bottlenecks

- **Critical path (longest chain)**:
  - QT-023 → QT-001 → QT-002 → QT-003 → QT-012 → QT-013 → QT-019 → QT-021 → QT-022
- **Secondary gating path for sign-off**:
  - QT-002 → QT-006 → (QT-008, QT-009, QT-010, QT-011) → QT-026 → QT-020 → QT-021
- **Primary bottlenecks**:
  1. **QT-003 (toolbar shell)**: gates QT-004/005/024 and QT-012.
  2. **QT-012 (threading contract)**: gates callback integration QT-013.
  3. **QT-019 (interaction suite)**: hard gate before cutover QT-021.
  4. **QT-020 (manual parity evidence)**: can delay cutover even when automation is green.

## Execution waves (parallel-first)

### Wave 0 — Bootstrap and scaffolding
- **Tickets**: QT-023, QT-001
- **Parallel starts**: establish `pytest-qt` harness skeleton for QT-018 while UI stubs are being created.

### Wave 1 — Dual-lane foundation
- **Tickets**: QT-002, QT-003, QT-006
- **Parallel starts**: after QT-002, split into two lanes immediately:
  - Lane 1: toolbar base (QT-003)
  - Lane 2: splitter/container shell (QT-006)

### Wave 2 — Fan-out implementation
- **Tickets**: QT-024, QT-004, QT-005, QT-012, QT-007, QT-008, QT-009, QT-010, QT-011
- **Parallel starts**:
  - From QT-003: run QT-024/QT-004/QT-005/QT-012 in parallel
  - From QT-006: run QT-007/QT-008/QT-009/QT-010/QT-011 in parallel

### Wave 3 — Behavior wiring by panel
- **Tickets**: QT-013, QT-014, QT-015, QT-025, QT-016, QT-017
- **Parallel starts**:
  - QT-014, QT-015, QT-017 run independently per tab
  - QT-025 can be completed as soon as QT-007 + QT-010 are done; then unlock QT-016
  - QT-013 proceeds in parallel once QT-012 + QT-007 are ready

### Wave 4 — Validation and cutover
- **Tickets**: QT-018, QT-019, QT-026, QT-020, QT-021, QT-022
- **Parallel starts**:
  - QT-018 should already be active from earlier waves and finalized here
  - QT-026 starts immediately after layout tickets complete; do not wait for all integration
  - QT-019 and QT-020 run in parallel when prerequisites are met, then converge into QT-021/QT-022

### Wave 5 — Visual parity bugfix backlog (new)
- **Tickets**: QT-027, QT-028, QT-029, QT-030
- **Parallel starts**:
  - QT-027 and QT-030 can proceed in parallel (different panels)
  - QT-028 can proceed in parallel with QT-027/QT-030 (layout-only)
  - QT-029 depends on QT-028 visual layout baseline and can begin once inspector axes are stabilized

---

## Visual bug tickets (user-reported parity gaps)

| ID | Title | Scope | Dependencies | Difficulty | Acceptance Criteria |
|---|---|---|---|---|---|
| QT-027 | Maps tab: render full map grids per view | `app/gui_qt/panels/maps_panel.py` | QT-014 | HARD | For each view mode, render all relevant outputs in a grid at once (not one-at-a-time via band): (a) Chromophore Maps shows all chromophore maps; (b) Derived Maps shows all derived maps; (c) Raw/Reflectance/OD shows full set of wavelength panels for each data type in grid layout. Band selector behavior must no longer act as chromophore switch. |
| QT-028 | Inspector tab: rebalance layout to center pixel-selection plot | `app/gui_qt/panels/inspector_panel.py` | QT-009 | MEDIUM | Left pixel-selection image is repositioned toward horizontal center of its pane (improves visual balance), while preserving split structure and usability; no clipping/overlap across common window sizes. |
| QT-029 | Inspector tab: OD and residual plots must be bar charts | `app/gui_qt/panels/inspector_panel.py` | QT-028, QT-015 | MEDIUM | Inspector right-side spectral visualizations match legacy UI style: measured/fitted OD displayed as bar charts and residual displayed as bar chart; wavelengths shown on x-axis; updates correctly on pixel change. |
| QT-030 | Diagnostics tab: enforce left-right subplot layout | `app/gui_qt/panels/diagnostics_panel.py` | QT-016 | MEDIUM | Diagnostics panel displays RMSE histogram on the left and quality mask on the right (`1x2` layout), not top-bottom stacking; titles/labels remain readable and update correctly with data refresh. |

---

## Ticket-to-test addendum for visual bug tickets

| Ticket | Test Type | Scope | Setup / Fixtures | Steps | Assertions | Failure Signals |
|---|---|---|---|---|---|---|
| QT-027 | Integration/UI | Maps multi-panel grid rendering parity | Deterministic results fixture with multiple chromophores, derived maps, and wavelengths | Switch across 3 Maps views and trigger redraw | Each view renders expected number of subplots in a grid; chromophores are all visible simultaneously; band control does not act as chromophore selector | Only single panel shown, incorrect subplot counts, view mismatch |
| QT-028 | UI | Inspector layout balance/placement | Inspector panel fixture + standard window sizes | Render inspector and inspect widget geometry/alignment metrics | Pixel-selection image area is visually centered within left pane bounds and remains visible across tested sizes | Image anchored too far left/right, clipping/overlap |
| QT-029 | Integration/UI | Inspector bar-chart parity | Inspector fixture with measured/fitted/residual arrays and wavelength labels | Select pixel and refresh inspector | OD plot uses bar artists for measured/fitted; residual plot uses bars; axis labels/ticks reflect wavelength bins | Line plots shown instead of bars, missing bars/ticks |
| QT-030 | Integration/UI | Diagnostics subplot orientation parity | Diagnostics fixture with valid `rmse_map` | Refresh diagnostics panel | Figure contains two axes in left-right arrangement (histogram left, mask right) | Vertical stacking, swapped panels, malformed layout |

---

## Medium-to-easy decomposition decisions

### Split from MEDIUM into MEDIUM + EASY
1. **QT-001 → + QT-023**
   - **Why split**: Creating package folders/init files is a discrete filesystem task (1–2 straightforward steps) and can be completed independently of import-safe stub authoring.
2. **QT-005 → + QT-024**
   - **Why split**: Solver combo defaults/options are a simple standalone control setup, while background parsing/validation remains integration-focused.
3. **QT-016 → + QT-025**
   - **Why split**: Warning text population/clearing is a direct data-to-widget mapping; plot rendering logic remains separate and more complex.
4. **QT-020 → + QT-026**
   - **Why split**: Authoring the checklist template is a short documentation task; evidence capture and pass/block adjudication remains broader manual validation.

### Kept as MEDIUM (not split)
- **QT-003, QT-004, QT-006, QT-007, QT-008, QT-009, QT-010, QT-011, QT-015, QT-017, QT-018, QT-022**
  - **Why kept MEDIUM**: Each still requires multi-part UI composition or integration verification that exceeds a 1–2-step atomic task under the strict EASY rule.

---

## Layout parity acceptance criteria

1. All 4 tabs exist with the same names and ordering.
2. Toolbar controls appear in the same order and perform the same actions.
3. Sidebar sections (`Folder Info`, `Sample`, `Warnings`) remain in same arrangement.
4. Each tab keeps same internal composition (controls at top, plots/content positions).
5. Window sizing behavior (initial/minimum) matches current app.
6. Main and nested splitters match baseline proportions within `±2%`.
7. Enable/disable state matrix matches baseline across startup, running, completed, and error states.
8. Plot redraws do not duplicate colorbars/artists and remain stable after repeated toggles.
9. Run pipeline flow and result rendering are functionally identical from user perspective.

---

## Risks and mitigations

1. **Thread/UI race conditions in Qt**
   - Mitigation: strict signal/slot boundary; never mutate widgets from worker thread.
2. **Matplotlib backend behavior differences**
   - Mitigation: switch to `QtAgg` backend early and verify all panels before full wiring.
3. **Slight spacing/style drift from ttk**
   - Mitigation: parity screenshots + geometry tuning pass before sign-off.
4. **Regression in callback wiring**
   - Mitigation: panel-level smoke tests + manual checklist on each milestone.

---

## Testing strategy for migration

1. Use the **Ticket-to-test matrix** as the required minimum (`QT-001`..`QT-026`, 1:1 coverage).
2. Prefer `pytest-qt` for deterministic UI tests; isolate backend with mocks/fakes for integration tests.
3. Keep existing core tests as-is; this migration introduces no spectral math changes.
4. Run manual parity QA with baseline screenshots for visual/sign-off items (QT-020, QT-022).
5. Gate cutover (QT-021/QT-022) on passing smoke + interaction + regression suite.

### Test parallelization guidance (author early vs blocked)

**Can be authored before feature completion (with mocks/stubs/fixtures):**
- **Foundational/UI structure tests**: QT-001, QT-002, QT-003, QT-006, QT-007, QT-008, QT-009, QT-010, QT-011, QT-018, QT-023, QT-024.
- **Behavior tests with contract-first fixtures**:
  - QT-012 via fake worker signal emitter and thread-boundary assertions.
  - QT-013 via mocked dialogs/backend service and callback payload assertions.
  - QT-014/QT-015/QT-016/QT-017 via deterministic result bundles (no live pipeline required).
  - QT-025 via diagnostics payload fixture (warnings/non-warnings branches).
- **Documentation test**: QT-026 can be drafted and reviewed once layout tickets are stable.

**Blocked until integration milestones:**
- **QT-019** blocked on functional completion of QT-013 + QT-014 + QT-015 + QT-016 + QT-017 (plus smoke baseline QT-018).
- **QT-020** blocked on completed UI parity states and checklist template QT-026.
- **QT-021** blocked on QT-019 and QT-020 sign-off.
- **QT-022** blocked on QT-021 cutover readiness and full regression pass.

**Execution rule for maximum throughput:**
- Implement tests in the same wave as their upstream contracts (not after feature completion), then switch from mocked fixtures to real wiring as soon as each dependency closes.

---

## Discovery questions to confirm before implementation

1. Do you want to keep a temporary dual-UI period (tkinter + PySide6) for rollback safety?
2. Is `pytest-qt` acceptable as the UI testing framework?
3. Should we keep default native OS styling, or mimic ttk as closely as possible with Qt stylesheet tuning?
4. Do you want Qt Designer `.ui` files, or pure Python widget construction only?

---

## Deliverables

1. New PySide6 UI module set under `app/gui_qt/`.
2. Updated app entrypoint to launch PySide6 UI.
3. Parity checklist + before/after screenshots.
4. UI smoke/integration tests for critical flows.
