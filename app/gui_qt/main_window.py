"""Main window implementation for the PySide6 GUI.

Import-safe: PySide6 is not imported until :class:`SpectralUnmixingMainWindow`
is instantiated.
"""

from __future__ import annotations

import os
import sys
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Dict, Sequence

if TYPE_CHECKING:  # pragma: no cover — type-checking only
    from PySide6.QtWidgets import QMainWindow, QTextEdit


# ---------------------------------------------------------------------------
# Stable object names
# ---------------------------------------------------------------------------

OBJECT_NAME: str = "SpectralUnmixingMainWindow"
SPLITTER_OBJECT_NAME: str = "MainSplitter"
SIDEBAR_OBJECT_NAME: str = "SidebarPanel"
TAB_WIDGET_OBJECT_NAME: str = "MainTabWidget"
FOLDER_INFO_TEXT_OBJECT_NAME: str = "FolderInfoText"
SAMPLE_COMBO_OBJECT_NAME: str = "SampleCombo"
WARNINGS_TEXT_OBJECT_NAME: str = "WarningsText"

# Tab object names
MAPS_TAB_OBJECT_NAME: str = "MapsTab"
INSPECTOR_TAB_OBJECT_NAME: str = "InspectorTab"
DIAGNOSTICS_TAB_OBJECT_NAME: str = "DiagnosticsTab"
STATS_TAB_OBJECT_NAME: str = "StatsTab"
BAR_CHARTS_TAB_OBJECT_NAME: str = "ChromophoreBarChartsTab"

# Tab labels (user-visible)
MAPS_TAB_LABEL: str = "Maps"
INSPECTOR_TAB_LABEL: str = "Pixel Inspector"
DIAGNOSTICS_TAB_LABEL: str = "Diagnostics"
STATS_TAB_LABEL: str = "Reflectance Stats"
BAR_CHARTS_TAB_LABEL: str = "Chromophore Bar Charts"

# Initial splitter sizes (left sidebar, right tab area)
INITIAL_SPLITTER_SIZES: list[int] = [280, 1120]

# Toolbar object names (QT-003)
TOOLBAR_OBJECT_NAME: str = "main_toolbar"
SELECT_ROOT_BTN_OBJECT_NAME: str = "select_root_btn"
SELECT_DATA_BTN_OBJECT_NAME: str = "select_data_btn"
USE_DEFAULT_BTN_OBJECT_NAME: str = "use_default_btn"
CHROMOPHORE_MENU_OBJECT_NAME: str = "chromophore_menu"
SOLVER_LABEL_OBJECT_NAME: str = "solver_label"
SOLVER_COMBO_OBJECT_NAME: str = "solver_combo"
BACKGROUND_LABEL_OBJECT_NAME: str = "background_label"
BG_MODEL_COMBO_OBJECT_NAME: str = "bg_model_combo"
BG_ENTRY_OBJECT_NAME: str = "bg_entry"
BG_EXP_START_LABEL_OBJECT_NAME: str = "bg_exp_start_label"
BG_EXP_START_ENTRY_OBJECT_NAME: str = "bg_exp_start_entry"
BG_EXP_END_LABEL_OBJECT_NAME: str = "bg_exp_end_label"
BG_EXP_END_ENTRY_OBJECT_NAME: str = "bg_exp_end_entry"
RUN_BTN_OBJECT_NAME: str = "run_btn"
SAVE_BTN_OBJECT_NAME: str = "save_btn"
PROGRESS_BAR_OBJECT_NAME: str = "progress_bar"
DATA_SOURCE_LABEL_OBJECT_NAME: str = "data_source_label"
STATUS_LABEL_OBJECT_NAME: str = "status_label"
SCATTERING_TOOLBAR_OBJECT_NAME: str = "scattering_toolbar"
SCATTERING_TITLE_OBJECT_NAME: str = "scattering_title"
SCATTERING_LAMBDA0_LABEL_OBJECT_NAME: str = "scattering_lambda0_label"
SCATTERING_LAMBDA0_ENTRY_OBJECT_NAME: str = "scattering_lambda0_entry"
SCATTERING_MU_S_500_LABEL_OBJECT_NAME: str = "scattering_mu_s_500_label"
SCATTERING_MU_S_500_ENTRY_OBJECT_NAME: str = "scattering_mu_s_500_entry"
SCATTERING_POWER_LABEL_OBJECT_NAME: str = "scattering_power_label"
SCATTERING_POWER_ENTRY_OBJECT_NAME: str = "scattering_power_entry"
SCATTERING_LIPOFUNDIN_LABEL_OBJECT_NAME: str = "scattering_lipofundin_label"
SCATTERING_LIPOFUNDIN_ENTRY_OBJECT_NAME: str = "scattering_lipofundin_entry"
SCATTERING_ANISOTROPY_LABEL_OBJECT_NAME: str = "scattering_anisotropy_label"
SCATTERING_ANISOTROPY_ENTRY_OBJECT_NAME: str = "scattering_anisotropy_entry"
ITERATIVE_TOOLBAR_OBJECT_NAME: str = "iterative_toolbar"
ITERATIVE_TITLE_OBJECT_NAME: str = "iterative_title"
ITERATIVE_MAX_ITER_LABEL_OBJECT_NAME: str = "iterative_max_iter_label"
ITERATIVE_MAX_ITER_ENTRY_OBJECT_NAME: str = "iterative_max_iter_entry"
ITERATIVE_TOL_REL_LABEL_OBJECT_NAME: str = "iterative_tol_rel_label"
ITERATIVE_TOL_REL_ENTRY_OBJECT_NAME: str = "iterative_tol_rel_entry"
ITERATIVE_TOL_RMSE_LABEL_OBJECT_NAME: str = "iterative_tol_rmse_label"
ITERATIVE_TOL_RMSE_ENTRY_OBJECT_NAME: str = "iterative_tol_rmse_entry"
ITERATIVE_DAMPING_LABEL_OBJECT_NAME: str = "iterative_damping_label"
ITERATIVE_DAMPING_ENTRY_OBJECT_NAME: str = "iterative_damping_entry"
ITERATIVE_INITIAL_CONC_LABEL_OBJECT_NAME: str = "iterative_initial_conc_label"
ITERATIVE_INITIAL_CONC_ENTRY_OBJECT_NAME: str = "iterative_initial_conc_entry"
ITERATIVE_RESET_BTN_OBJECT_NAME: str = "iterative_reset_btn"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class SpectralUnmixingMainWindow:
    """Main application window for the spectral unmixing tool.

    Deferred-import pattern — the actual QMainWindow subclass is created
    lazily so that importing this module never triggers a PySide6 import.
    """

    def __init__(self, parent: Any = None) -> None:
        self._impl = _make_main_window()(parent)
        self._impl.setObjectName(OBJECT_NAME)

        # -- app-level state -------------------------------------------------
        self.root_dir: str | None = None
        self.folder_info: Dict[str, Any] | None = None
        self.data_dir: str | None = self._find_default_data_dir()
        self._default_data_dir: str | None = self.data_dir
        self._results: Dict[str, Dict[str, Any]] = {}
        self._chrom_scales: Dict[str, tuple[float, float]] = {}
        self._derived_scales: Dict[str, tuple[float, float]] = {}
        self._last_config_snapshot: Dict[str, Any] | None = None

        # Keep panel instances for cross-tab refresh callbacks.
        self._maps_panel: Any = None
        self._inspector_panel: Any = None
        self._diagnostics_panel: Any = None
        self._stats_panel: Any = None
        self._barcharts_panel: Any = None

        # Keep non-blocking dialog references alive briefly.
        self._dialogs: list[Any] = []

        self._chromophore_menu: Any = None
        self._background_label_action: Any = None
        self._background_model_action: Any = None
        self._background_entry_action: Any = None
        self._background_exp_start_label_action: Any = None
        self._background_exp_start_entry_action: Any = None
        self._background_exp_end_label_action: Any = None
        self._background_exp_end_entry_action: Any = None
        self._bg_value: float = 2500.0
        self._background_params: Dict[str, float | str] = self._default_background_parameters()
        self._scattering_params: Dict[str, float] = self._default_scattering_parameters()
        self._iterative_params: Dict[str, float | int] = self._default_iterative_parameters()
        self._set_window_properties()
        self._setup_ui()

        # Initialize toolbar/sidebar text from discovered default data dir.
        self._refresh_chromophore_menu()
        self._set_data_source_label_from_state()
        self._set_status("No folder selected")

        # -- QT-012: pipeline threading state --------------------------------
        self._worker: Any = None          # PipelineWorker instance
        self._thread: Any = None          # QThread instance
        self._is_running: bool = False
        self._last_results: Dict[str, Any] | None = None
        self._pipeline_fn: Callable[[], Dict[str, Any]] | None = None

    def set_chromophores(self, names: Sequence[str]) -> None:
        """Populate toolbar chromophore menu entries."""
        if self._chromophore_menu is None:
            return
        self._chromophore_menu.set_chromophores(names)

    def get_selection(self, include_background: bool = False) -> list[str]:
        """Return selected chromophores from the toolbar menu."""
        if self._chromophore_menu is None:
            return []
        return self._chromophore_menu.get_selected(include_background=include_background)

    # -- sidebar update hooks (QT-007) -------------------------------------

    def set_folder_info(self, text: str) -> None:
        """Set the Folder Info sidebar text."""
        from PySide6.QtWidgets import QTextEdit

        widget = self._impl.findChild(QTextEdit, FOLDER_INFO_TEXT_OBJECT_NAME)
        if widget is None:
            return
        widget.setPlainText(text)

    def set_samples(self, samples: list[str]) -> None:
        """Populate the Sample combo with names."""
        from PySide6.QtWidgets import QComboBox

        combo = self._impl.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
        if combo is None:
            return

        combo.clear()
        if samples:
            combo.addItems(samples)
            combo.setEnabled(True)
            combo.setCurrentIndex(0)
        else:
            combo.addItem("— none —")
            combo.setEnabled(False)

    def select_sample(self, name: str) -> None:
        """Select a sample by display name if present."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QComboBox

        combo = self._impl.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
        if combo is None:
            return

        idx = combo.findText(name, Qt.MatchFlag.MatchExactly)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _set_window_properties(self) -> None:
        """Set window title and geometry (import-safe)."""
        self._impl.setWindowTitle("Spectral Unmixing")
        self._impl.resize(1400, 900)
        self._impl.setMinimumSize(1000, 700)

    def _setup_ui(self) -> None:
        """Set up the two-pane splitter shell with sidebar and tab widget."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QSplitter

        # Toolbar (QT-003) lives above the central splitter.
        toolbar = self._build_toolbar(self._impl)
        self._impl.addToolBar(Qt.TopToolBarArea, toolbar)
        scattering_toolbar = self._build_scattering_toolbar(self._impl)
        self._impl.addToolBarBreak(Qt.TopToolBarArea)
        self._impl.addToolBar(Qt.TopToolBarArea, scattering_toolbar)
        iterative_toolbar = self._build_iterative_toolbar(self._impl)
        self._impl.addToolBarBreak(Qt.TopToolBarArea)
        self._impl.addToolBar(Qt.TopToolBarArea, iterative_toolbar)

        # -- central splitter ------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal, self._impl)
        splitter.setObjectName(SPLITTER_OBJECT_NAME)

        # -- left sidebar ----------------------------------------------------
        sidebar = self._build_sidebar(splitter)
        splitter.addWidget(sidebar)

        # -- right tab widget ------------------------------------------------
        tab_widget = self._build_tab_widget(splitter)
        splitter.addWidget(tab_widget)

        self._impl.setCentralWidget(splitter)

        # Sidebar sample selection updates all tabs.
        from PySide6.QtWidgets import QComboBox

        sample_combo = self._impl.findChild(QComboBox, SAMPLE_COMBO_OBJECT_NAME)
        if sample_combo is not None:
            sample_combo.currentTextChanged.connect(self._on_sample_combo_changed)

        # -- apply initial proportions ---------------------------------------
        # Apply after attaching as central widget to keep deterministic sizes
        # with an attached toolbar.
        splitter.setSizes(INITIAL_SPLITTER_SIZES)
        # Stretch factors preserve ratio when the window is resized.
        splitter.setStretchFactor(0, 0)  # sidebar: fixed
        splitter.setStretchFactor(1, 1)  # tab area: expands

        self._set_solver_dependent_controls("ls")

    def _build_toolbar(self, parent: Any):
        """Construct top toolbar with stable QT-003 control ordering."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QComboBox,
            QLabel,
            QLineEdit,
            QProgressBar,
            QPushButton,
            QToolBar,
        )
        from app.gui_qt.widgets import ChromophoreMenu

        toolbar = QToolBar("Main Toolbar", parent)
        toolbar.setObjectName(TOOLBAR_OBJECT_NAME)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)

        # 1) select_root_btn
        select_root_btn = QPushButton("Select Root", toolbar)
        select_root_btn.setObjectName(SELECT_ROOT_BTN_OBJECT_NAME)
        select_root_btn.clicked.connect(self._on_select_root_clicked)
        toolbar.addWidget(select_root_btn)

        # 2) select_data_btn
        select_data_btn = QPushButton("Select Data", toolbar)
        select_data_btn.setObjectName(SELECT_DATA_BTN_OBJECT_NAME)
        select_data_btn.clicked.connect(self._on_select_data_clicked)
        toolbar.addWidget(select_data_btn)

        # 3) use_default_btn
        use_default_btn = QPushButton("Use Default", toolbar)
        use_default_btn.setObjectName(USE_DEFAULT_BTN_OBJECT_NAME)
        use_default_btn.clicked.connect(self._on_use_default_data_clicked)
        toolbar.addWidget(use_default_btn)

        # 4) chromophore_menu
        chromophore_menu = ChromophoreMenu(toolbar)
        chromophore_menu._impl.setObjectName(CHROMOPHORE_MENU_OBJECT_NAME)
        self._chromophore_menu = chromophore_menu
        toolbar.addWidget(chromophore_menu._impl)

        # 5) solver_label
        solver_label = QLabel("Solver:", toolbar)
        solver_label.setObjectName(SOLVER_LABEL_OBJECT_NAME)
        toolbar.addWidget(solver_label)

        # 6) solver_combo
        solver_combo = QComboBox(toolbar)
        solver_combo.setObjectName(SOLVER_COMBO_OBJECT_NAME)
        solver_combo.setEditable(False)
        solver_combo.addItems(["ls", "nnls", "mu_a", "iterative"])
        solver_combo.setCurrentIndex(0)
        solver_combo.currentTextChanged.connect(self._on_solver_method_changed)
        toolbar.addWidget(solver_combo)

        # 7) background_label
        background_label = QLabel("Background:", toolbar)
        background_label.setObjectName(BACKGROUND_LABEL_OBJECT_NAME)
        self._background_label_action = toolbar.addWidget(background_label)

        # 8) bg_model_combo
        bg_model_combo = QComboBox(toolbar)
        bg_model_combo.setObjectName(BG_MODEL_COMBO_OBJECT_NAME)
        bg_model_combo.setEditable(False)
        bg_model_combo.addItems(["constant", "exponential"])
        bg_model_combo.setCurrentText(str(self._background_params["model"]))
        bg_model_combo.currentTextChanged.connect(self._on_background_model_changed)
        self._background_model_action = toolbar.addWidget(bg_model_combo)

        # 9) bg_entry
        bg_entry = QLineEdit(toolbar)
        bg_entry.setObjectName(BG_ENTRY_OBJECT_NAME)
        bg_entry.setText(str(self._background_params["value"]))
        bg_entry.setMaximumWidth(92)
        bg_entry.setAlignment(Qt.AlignmentFlag.AlignRight)
        bg_entry.editingFinished.connect(self._on_bg_editing_finished)
        self._background_entry_action = toolbar.addWidget(bg_entry)

        # 10) exponential background controls
        bg_exp_start_label = QLabel("exp start:", toolbar)
        bg_exp_start_label.setObjectName(BG_EXP_START_LABEL_OBJECT_NAME)
        self._background_exp_start_label_action = toolbar.addWidget(bg_exp_start_label)

        bg_exp_start_entry = QLineEdit(toolbar)
        bg_exp_start_entry.setObjectName(BG_EXP_START_ENTRY_OBJECT_NAME)
        bg_exp_start_entry.setText(str(self._background_params["exp_start"]))
        bg_exp_start_entry.setMaximumWidth(72)
        bg_exp_start_entry.setAlignment(Qt.AlignmentFlag.AlignRight)
        bg_exp_start_entry.editingFinished.connect(partial(self._on_background_exp_editing_finished, "exp_start"))
        self._background_exp_start_entry_action = toolbar.addWidget(bg_exp_start_entry)

        bg_exp_end_label = QLabel("exp end:", toolbar)
        bg_exp_end_label.setObjectName(BG_EXP_END_LABEL_OBJECT_NAME)
        self._background_exp_end_label_action = toolbar.addWidget(bg_exp_end_label)

        bg_exp_end_entry = QLineEdit(toolbar)
        bg_exp_end_entry.setObjectName(BG_EXP_END_ENTRY_OBJECT_NAME)
        bg_exp_end_entry.setText(str(self._background_params["exp_end"]))
        bg_exp_end_entry.setMaximumWidth(72)
        bg_exp_end_entry.setAlignment(Qt.AlignmentFlag.AlignRight)
        bg_exp_end_entry.editingFinished.connect(partial(self._on_background_exp_editing_finished, "exp_end"))
        self._background_exp_end_entry_action = toolbar.addWidget(bg_exp_end_entry)

        self._set_background_model_controls(str(self._background_params["model"]))

        # 11) run_btn
        run_btn = QPushButton("Run", toolbar)
        run_btn.setObjectName(RUN_BTN_OBJECT_NAME)
        run_btn.setEnabled(False)
        run_btn.clicked.connect(self._on_run_clicked)
        toolbar.addWidget(run_btn)

        # 12) save_btn
        save_btn = QPushButton("Save", toolbar)
        save_btn.setObjectName(SAVE_BTN_OBJECT_NAME)
        save_btn.setEnabled(False)
        save_btn.clicked.connect(self._on_save_clicked)
        toolbar.addWidget(save_btn)

        # 13) progress_bar
        progress_bar = QProgressBar(toolbar)
        progress_bar.setObjectName(PROGRESS_BAR_OBJECT_NAME)
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        toolbar.addWidget(progress_bar)

        # 14) data_source_label
        data_source_label = QLabel("Data: default (not found)", toolbar)
        data_source_label.setObjectName(DATA_SOURCE_LABEL_OBJECT_NAME)
        toolbar.addWidget(data_source_label)

        # 15) status_label
        status_label = QLabel("Ready", toolbar)
        status_label.setObjectName(STATUS_LABEL_OBJECT_NAME)
        toolbar.addWidget(status_label)

        return toolbar

    def _build_scattering_toolbar(self, parent: Any):
        """Construct a secondary toolbar with fixed-scattering controls."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLabel, QLineEdit, QToolBar

        toolbar = QToolBar("Scattering Toolbar", parent)
        toolbar.setObjectName(SCATTERING_TOOLBAR_OBJECT_NAME)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        toolbar.setVisible(False)

        title = QLabel("Fixed scattering:", toolbar)
        title.setObjectName(SCATTERING_TITLE_OBJECT_NAME)
        title.setStyleSheet("font-weight: 600;")
        toolbar.addWidget(title)

        fields = [
            (
                "lambda0 (nm):",
                SCATTERING_LAMBDA0_LABEL_OBJECT_NAME,
                SCATTERING_LAMBDA0_ENTRY_OBJECT_NAME,
                "lambda0_nm",
                "Reference wavelength for the fixed-scattering power law. "
                "The scattering scale is normalized relative to this wavelength; "
                "500 nm is the usual reference for the current model.",
            ),
            (
                "mu_s_500 (cm^-1):",
                SCATTERING_MU_S_500_LABEL_OBJECT_NAME,
                SCATTERING_MU_S_500_ENTRY_OBJECT_NAME,
                "mu_s_500_cm1",
                "Scattering coefficient scale at the reference wavelength. "
                "Increasing it strengthens the scattering prior used by mu_a and iterative solvers.",
            ),
            (
                "b:",
                SCATTERING_POWER_LABEL_OBJECT_NAME,
                SCATTERING_POWER_ENTRY_OBJECT_NAME,
                "power_b",
                "Power-law exponent for wavelength-dependent scattering. "
                "Larger values make scattering decrease faster at longer wavelengths.",
            ),
            (
                "lipo frac:",
                SCATTERING_LIPOFUNDIN_LABEL_OBJECT_NAME,
                SCATTERING_LIPOFUNDIN_ENTRY_OBJECT_NAME,
                "lipofundin_fraction",
                "Multiplicative lipofundin fraction applied to the scattering prior. "
                "Larger values increase the modeled scattering contribution.",
            ),
            (
                "g:",
                SCATTERING_ANISOTROPY_LABEL_OBJECT_NAME,
                SCATTERING_ANISOTROPY_ENTRY_OBJECT_NAME,
                "anisotropy_g",
                "Scattering anisotropy factor in the range [0, 1). "
                "The reduced scattering term is scaled by (1 - g), so values closer to 1 reduce it.",
            ),
        ]

        for label_text, label_name, entry_name, key, tooltip in fields:
            label = QLabel(label_text, toolbar)
            label.setObjectName(label_name)
            toolbar.addWidget(label)
            toolbar.addWidget(self._make_help_label(toolbar, tooltip, f"{label_name}_help"))

            entry = QLineEdit(toolbar)
            entry.setObjectName(entry_name)
            entry.setText(str(self._scattering_params[key]))
            entry.setMaximumWidth(88)
            entry.setAlignment(Qt.AlignmentFlag.AlignRight)
            entry.editingFinished.connect(partial(self._on_scattering_editing_finished, key))
            toolbar.addWidget(entry)

        return toolbar

    def _build_iterative_toolbar(self, parent: Any):
        """Construct an iterative-solver toolbar shown only for the iterative method."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QToolBar

        toolbar = QToolBar("Iterative Solver Toolbar", parent)
        toolbar.setObjectName(ITERATIVE_TOOLBAR_OBJECT_NAME)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        toolbar.setVisible(False)

        title = QLabel("Iterative solver:", toolbar)
        title.setObjectName(ITERATIVE_TITLE_OBJECT_NAME)
        title.setStyleSheet("font-weight: 600;")
        toolbar.addWidget(title)

        fields = [
            (
                "Max iter:",
                ITERATIVE_MAX_ITER_LABEL_OBJECT_NAME,
                ITERATIVE_MAX_ITER_ENTRY_OBJECT_NAME,
                "max_iter",
                "Maximum number of pathlength/overlap-matrix update cycles. "
                "Higher values can improve convergence but increase runtime.",
            ),
            (
                "Path tol:",
                ITERATIVE_TOL_REL_LABEL_OBJECT_NAME,
                ITERATIVE_TOL_REL_ENTRY_OBJECT_NAME,
                "tol_rel",
                "Relative pathlength-change tolerance. "
                "The solver stops when the updated pathlength changes by less than this threshold.",
            ),
            (
                "RMSE improvement tol:",
                ITERATIVE_TOL_RMSE_LABEL_OBJECT_NAME,
                ITERATIVE_TOL_RMSE_ENTRY_OBJECT_NAME,
                "tol_rmse",
                "Minimum mean-RMSE improvement required to continue after the first iteration. "
                "Larger values stop earlier; smaller values demand more refinement.",
            ),
            (
                "Damping:",
                ITERATIVE_DAMPING_LABEL_OBJECT_NAME,
                ITERATIVE_DAMPING_ENTRY_OBJECT_NAME,
                "damping",
                "Blend factor for each new modeled pathlength. "
                "Lower values are more stable but slower; 1.0 fully replaces the previous pathlength.",
            ),
            (
                "Initial conc:",
                ITERATIVE_INITIAL_CONC_LABEL_OBJECT_NAME,
                ITERATIVE_INITIAL_CONC_ENTRY_OBJECT_NAME,
                "initial_concentration",
                "Initial chromophore concentration used to seed the first pathlength estimate. "
                "Background, if enabled, is not used for pathlength updates.",
            ),
        ]

        for label_text, label_name, entry_name, key, tooltip in fields:
            label = QLabel(label_text, toolbar)
            label.setObjectName(label_name)
            toolbar.addWidget(label)
            toolbar.addWidget(self._make_help_label(toolbar, tooltip, f"{label_name}_help"))

            entry = QLineEdit(toolbar)
            entry.setObjectName(entry_name)
            entry.setText(str(self._iterative_params[key]))
            entry.setMaximumWidth(92)
            entry.setAlignment(Qt.AlignmentFlag.AlignRight)
            entry.editingFinished.connect(partial(self._on_iterative_editing_finished, key))
            toolbar.addWidget(entry)

        reset_btn = QPushButton("Reset defaults", toolbar)
        reset_btn.setObjectName(ITERATIVE_RESET_BTN_OBJECT_NAME)
        reset_btn.clicked.connect(self._on_iterative_reset_clicked)
        toolbar.addWidget(reset_btn)

        return toolbar

    @staticmethod
    def _noop(*args: Any, **kwargs: Any) -> None:
        """No-op placeholder callback for QT-003 controls."""
        return None

    @staticmethod
    def _make_help_label(parent: Any, tooltip: str, object_name: str):
        """Create a compact '?' label with a hover tooltip."""
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLabel

        label = QLabel("?", parent)
        label.setObjectName(object_name)
        label.setToolTip(tooltip)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(16, 16)
        label.setStyleSheet(
            "QLabel {"
            " border: 1px solid #8a8a8a;"
            " border-radius: 8px;"
            " color: #555;"
            " font-size: 10px;"
            " font-weight: 600;"
            " background: #f7f7f7;"
            "}"
        )
        return label

    # -- QT-013: toolbar callbacks and state transitions --------------------

    def _on_select_root_clicked(self) -> None:
        """Choose root folder and populate folder/sample sidebar state."""
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(
            self._impl,
            "Select root folder with image cubes",
        )
        if not path:
            return

        try:
            from app.core import io as loader
        except Exception as exc:
            self._set_status("Core I/O module unavailable")
            self._show_error("Initialization Error", str(exc))
            return

        try:
            info = loader.detect_folders(path)
        except Exception as exc:
            self._set_status("Failed to load root folder")
            self._show_error("Invalid Root Folder", str(exc))
            return

        self.root_dir = path
        self.folder_info = info
        self._results.clear()
        self._last_results = None
        self._chrom_scales = {}
        self._derived_scales = {}

        self.set_folder_info(self._format_folder_info(path, info))
        self.set_samples(list(info.get("sample_names", [])))
        self.update_warnings(None)

        self._set_save_enabled(False)
        self._set_status(f"Loaded root: {os.path.basename(path)}")

        if self._pipeline_fn is None:
            self._set_run_enabled(self._can_run_pipeline())

    def _on_select_data_clicked(self) -> None:
        """Choose and validate a custom data directory."""
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(
            self._impl,
            "Select data folder",
        )
        if not path:
            return

        try:
            from app.core import io as loader
        except Exception as exc:
            self._set_status("Core I/O module unavailable")
            self._show_error("Initialization Error", str(exc))
            return

        try:
            loader.validate_data_directory(path)
        except Exception as exc:
            self._set_status("Invalid data folder")
            self._show_error("Invalid Data Folder", str(exc))
            return

        self.data_dir = path
        self._refresh_chromophore_menu()
        self._set_data_source_label(f"Data: custom ({os.path.basename(path)})")
        self._set_status(f"Selected data: {os.path.basename(path)}")

        if self._pipeline_fn is None:
            self._set_run_enabled(self._can_run_pipeline())

    def _on_use_default_data_clicked(self) -> None:
        """Reset data directory to auto-discovered default."""
        self.data_dir = self._find_default_data_dir()
        self._default_data_dir = self.data_dir
        self._refresh_chromophore_menu()
        self._set_data_source_label_from_state()

        if self.data_dir:
            self._set_status(f"Using default data: {os.path.basename(self.data_dir)}")
        else:
            self._set_status("Default data folder not found")
            self._show_error(
                "Default Data Not Found",
                "Could not locate a default data/ folder.",
            )

        if self._pipeline_fn is None:
            self._set_run_enabled(self._can_run_pipeline())

    def _on_save_clicked(self) -> None:
        """Choose output directory and export current results."""
        from PySide6.QtWidgets import QFileDialog

        if not self._results:
            self._set_status("No results to save")
            self._show_error("Save Results", "No results are available yet.")
            return

        out_dir = QFileDialog.getExistingDirectory(
            self._impl,
            "Select output directory",
        )
        if not out_dir:
            return

        from app.core import export

        try:
            for sample_name, res in self._results.items():
                self._set_status(f"Saving {sample_name}...")
                export.save_results(
                    out_dir,
                    sample_name,
                    res["concentrations"],
                    res["chromophore_names"],
                    res.get("derived", res.get("derived_maps", {})),
                    res["rmse_map"],
                    res.get("diagnostics", {}),
                    chrom_scales=self._chrom_scales,
                    derived_scales=self._derived_scales,
                )
        except Exception as exc:
            self._set_status("Save failed")
            self._show_error("Save Failed", str(exc))
            return

        self._set_status(f"Saved {len(self._results)} samples")
        self._show_info("Export Complete", f"Results saved to:\n{out_dir}")

    def _on_sample_combo_changed(self, name: str) -> None:
        """Refresh tabs and warnings when selected sample changes."""
        if not name or name == "— none —":
            return

        result = self._results.get(name)
        if result is None:
            self.update_warnings([f"No processed data for sample: {name}"])
            return

        diagnostics = result.get("diagnostics", {}) if isinstance(result, dict) else {}
        warnings = diagnostics.get("warnings") if isinstance(diagnostics, dict) else None
        self.update_warnings(warnings)

        if self._maps_panel is not None:
            self._maps_panel.show_results(result)
        if self._inspector_panel is not None:
            self._inspector_panel.set_data(result)
        if self._diagnostics_panel is not None:
            self._diagnostics_panel.set_data({
                "diagnostics": diagnostics,
                "rmse_map": result.get("rmse_map"),
            })
        if self._stats_panel is not None:
            self._stats_panel.set_data(result)
        if self._barcharts_panel is not None:
            self._barcharts_panel.set_data(self._results)

        self._set_status(f"Showing sample: {name}")

    # -- QT-012: pipeline threading and state transitions --------------------

    def set_pipeline_fn(self, fn: Callable[[], Dict[str, Any]] | None) -> None:
        """Register (or clear) the callable that the Run button will execute.

        When a callable is registered the Run button is enabled; when cleared
        it is disabled (unless a run is already in progress).
        """
        self._pipeline_fn = fn
        if not self._is_running:
            self._set_run_enabled(fn is not None or self._can_run_pipeline())

    def _on_run_clicked(self) -> None:
        """Start the pipeline on a background thread."""
        if self._is_running:
            return

        pipeline_fn = self._pipeline_fn
        if pipeline_fn is None:
            try:
                snapshot = self._build_config_snapshot()
                self._last_config_snapshot = snapshot
            except Exception as exc:
                self._set_status("Cannot start run")
                self._show_error("Run Configuration Error", str(exc))
                return
            pipeline_fn = self._make_pipeline_adapter(snapshot)

        self._start_pipeline(pipeline_fn)

    def _start_pipeline(self, pipeline_fn: Callable[[], Dict[str, Any]]) -> None:
        """Launch *pipeline_fn* on a dedicated QThread.

        State transitions:
            IDLE -> RUNNING  (buttons disabled, progress reset)
            RUNNING -> IDLE  (on success or failure, buttons re-enabled)
        """
        from PySide6.QtCore import Qt, QThread
        from app.gui_qt.worker import PipelineWorker

        # Reset UI state
        self._set_run_enabled(False)
        self._set_save_enabled(False)
        self._set_progress(0)
        self._set_status("Running pipeline...")
        self._is_running = True
        self._last_results = None

        # Create worker + thread
        worker = PipelineWorker(pipeline_fn)
        thread = QThread()

        worker.moveToThread(thread)

        # Route signals to main-window slots (queued across threads)
        worker.progress_updated.connect(self._on_progress_updated)
        worker.results_ready.connect(self._on_results_ready)
        worker.run_failed.connect(self._on_run_failed)

        # Clean up thread when worker finishes.
        # Use DirectConnection for thread.quit() because QThread.quit() is
        # thread-safe and we must avoid a deadlock: if the main thread is
        # blocked in thread.wait() the queued quit signal would never fire.
        thread.started.connect(worker.run)
        worker.results_ready.connect(thread.quit, type=Qt.ConnectionType.DirectConnection)
        worker.run_failed.connect(thread.quit, type=Qt.ConnectionType.DirectConnection)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        self._worker = worker
        self._thread = thread

        thread.start()

    def _on_progress_updated(self, percent: int, message: str) -> None:
        """Slot: update progress bar and status label from worker signal."""
        self._set_progress(percent)
        self._set_status(message)

    def _on_results_ready(self, results: Dict[str, Any]) -> None:
        """Slot: handle successful pipeline completion."""
        self._is_running = False
        self._last_results = results

        self._set_progress(100)
        self._set_status("Pipeline complete.")
        self._set_run_enabled(True)

        # Default for generic pipelines (QT-012 tests use plain payloads).
        has_data = bool(results)

        # QT-013 adapter payload: refresh sidebar + panels from sample results.
        samples = results.get("samples") if isinstance(results, dict) else None
        if isinstance(samples, dict):
            self._results = samples
            self._chrom_scales = dict(results.get("chrom_scales", {}))
            self._derived_scales = dict(results.get("derived_scales", {}))

            names = list(samples.keys())
            self.set_samples(names)
            if names:
                self.select_sample(names[0])
            else:
                self.update_warnings(None)

            has_data = bool(names)

        self._set_save_enabled(has_data)

    def _on_run_failed(self, error_text: str) -> None:
        """Slot: handle pipeline failure."""
        self._is_running = False
        self._last_results = None

        self._set_progress(0)
        self._set_status(error_text)
        self._show_error("Pipeline Error", error_text)
        self._set_run_enabled(True)
        self._set_save_enabled(False)

    def _build_config_snapshot(self) -> Dict[str, Any]:
        """Capture a validated immutable run-configuration snapshot."""
        if not self.folder_info or not self.root_dir:
            raise RuntimeError("Select a root folder before running.")
        if not self.data_dir:
            raise RuntimeError("Select a valid data folder before running.")

        from PySide6.QtWidgets import QComboBox

        solver_combo = self._impl.findChild(QComboBox, SOLVER_COMBO_OBJECT_NAME)

        solver_method = solver_combo.currentText() if solver_combo is not None else "ls"
        use_fixed_scattering = self._uses_fixed_scattering_solver(solver_method)
        supports_background = solver_method != "mu_a"
        background_parameters = None
        scattering_parameters = None
        iterative_parameters = None

        if supports_background:
            try:
                background_parameters = self._read_background_params_from_ui()
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid background parameters: {exc}") from exc
            bg_value = float(background_parameters["value"])
        else:
            bg_value = self._bg_value

        if use_fixed_scattering:
            try:
                scattering_parameters = self._read_scattering_params_from_ui()
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid scattering parameters: {exc}") from exc
            if solver_method == "iterative":
                try:
                    iterative_parameters = self._read_iterative_params_from_ui()
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid iterative solver parameters: {exc}") from exc

        selected = self.get_selection(include_background=True)
        include_background = "Background" in selected
        selected_chroms = [name for name in selected if name != "Background"]
        if solver_method == "mu_a":
            include_background = False
            if not selected_chroms:
                raise ValueError(
                    f"Select at least one chromophore for the {solver_method} solver."
                )
        elif not selected_chroms and not include_background:
            raise ValueError("Select at least one chromophore or enable Background.")

        return {
            "root_dir": self.root_dir,
            "data_dir": self.data_dir,
            "folder_info": dict(self.folder_info),
            "solver_method": solver_method,
            "background_value": bg_value,
            "background_parameters": background_parameters,
            "scattering_parameters": scattering_parameters,
            "iterative_parameters": iterative_parameters,
            "include_background": include_background,
            "selected_chromophores": selected_chroms,
        }

    def _make_pipeline_adapter(self, snapshot: Dict[str, Any]) -> Callable[[], Dict[str, Any]]:
        """Return a pragmatic QT pipeline callable reusing legacy core logic."""

        def _pipeline() -> Dict[str, Any]:
            from app.core import io as loader
            from app.core import processing

            info = snapshot["folder_info"]
            wls = info["wavelengths"]
            data_dir = snapshot["data_dir"]

            loader.validate_data_directory(data_dir)

            ref_cube = loader.load_image_cube(info["ref_dir"], wls)
            dark_cube = loader.load_image_cube(info["dark_ref_dir"], wls)

            chrom_spectra = loader.load_chromophore_spectra(data_dir)
            led_wl, led_em = loader.load_led_emission(data_dir, wls)
            pen_wl, pen_depth = loader.load_penetration_depth(data_dir)

            mus_prime = None
            if snapshot["solver_method"] == "mu_a":
                A, chrom_names = processing.build_absorption_matrix(
                    led_wl,
                    led_em,
                    chrom_spectra,
                    wls,
                    chromophore_names=snapshot["selected_chromophores"],
                )
                mus_prime = processing.build_fixed_scattering_profile(
                    led_wl,
                    led_em,
                    wls,
                    **snapshot["scattering_parameters"],
                )
            elif snapshot["solver_method"] == "iterative":
                background_parameters = snapshot["background_parameters"]
                A, chrom_names = processing.build_overlap_matrix(
                    led_wl,
                    led_em,
                    chrom_spectra,
                    pen_wl,
                    pen_depth,
                    wls,
                    chromophore_names=snapshot["selected_chromophores"],
                    include_background=snapshot["include_background"],
                    background_value=background_parameters["value"],
                    background_model=background_parameters["model"],
                    background_exp_start=background_parameters["exp_start"],
                    background_exp_end=background_parameters["exp_end"],
                )
            else:
                background_parameters = snapshot["background_parameters"]
                A, chrom_names = processing.build_overlap_matrix(
                    led_wl,
                    led_em,
                    chrom_spectra,
                    pen_wl,
                    pen_depth,
                    wls,
                    chromophore_names=snapshot["selected_chromophores"],
                    include_background=snapshot["include_background"],
                    background_value=background_parameters["value"],
                    background_model=background_parameters["model"],
                    background_exp_start=background_parameters["exp_start"],
                    background_exp_end=background_parameters["exp_end"],
                )

            results: Dict[str, Dict[str, Any]] = {}
            for sample_dir, sample_name in zip(info["samples"], info["sample_names"]):
                sample_cube = loader.load_image_cube(sample_dir, wls)
                reflectance = processing.compute_reflectance(sample_cube, ref_cube, dark_cube)
                od_cube = processing.compute_optical_density(reflectance)
                solver_info = None
                active_A = A
                if snapshot["solver_method"] == "iterative":
                    concentrations, rmse_map, fitted_od, solver_info = (
                        processing.solve_unmixing_iterative(
                            od_cube,
                            A,
                            led_wl,
                            led_em,
                            chrom_spectra,
                            wls,
                            chromophore_names=chrom_names,
                            include_background=snapshot["include_background"],
                            background_value=background_parameters["value"],
                            background_model=background_parameters["model"],
                            background_exp_start=background_parameters["exp_start"],
                            background_exp_end=background_parameters["exp_end"],
                            scattering_parameters=snapshot["scattering_parameters"],
                            **(snapshot.get("iterative_parameters") or {}),
                        )
                    )
                    active_A = solver_info.get("A_used", A)
                else:
                    concentrations, rmse_map, fitted_od = processing.solve_unmixing(
                        od_cube,
                        A,
                        method=snapshot["solver_method"],
                        mus_prime=mus_prime,
                    )
                derived = processing.compute_derived_maps(concentrations, chrom_names)
                diagnostics = processing.compute_diagnostics(
                    reflectance,
                    od_cube,
                    rmse_map,
                    active_A,
                )

                results[sample_name] = {
                    "sample_cube": sample_cube,
                    "reflectance": reflectance,
                    "od_cube": od_cube,
                    "concentrations": concentrations,
                    "fitted_od": fitted_od,
                    "rmse_map": rmse_map,
                    "derived": derived,
                    "derived_maps": derived,
                    "diagnostics": diagnostics,
                    "A": active_A,
                    "chromophore_names": chrom_names,
                    "include_background": snapshot["include_background"],
                    "background_value": snapshot["background_value"],
                    "background_parameters": snapshot["background_parameters"],
                    "scattering_parameters": snapshot["scattering_parameters"],
                    "iterative_parameters": snapshot["iterative_parameters"],
                    "solver_info": solver_info,
                    "solver_method": snapshot["solver_method"],
                    "wavelengths": wls,
                }

            chrom_scales, derived_scales = self._compute_global_scales(
                results,
                chrom_names,
                include_background=snapshot["include_background"],
            )

            return {
                "samples": results,
                "chrom_scales": chrom_scales,
                "derived_scales": derived_scales,
                "config": snapshot,
            }

        return _pipeline

    # -- internal UI mutators (all safe to call from any thread via slots) --

    def _set_run_enabled(self, enabled: bool) -> None:
        from PySide6.QtWidgets import QPushButton

        btn = self._impl.findChild(QPushButton, RUN_BTN_OBJECT_NAME)
        if btn is not None:
            btn.setEnabled(enabled)

    def _set_save_enabled(self, enabled: bool) -> None:
        from PySide6.QtWidgets import QPushButton

        btn = self._impl.findChild(QPushButton, SAVE_BTN_OBJECT_NAME)
        if btn is not None:
            btn.setEnabled(enabled)

    def _set_progress(self, value: int) -> None:
        from PySide6.QtWidgets import QProgressBar

        bar = self._impl.findChild(QProgressBar, PROGRESS_BAR_OBJECT_NAME)
        if bar is not None:
            bar.setValue(value)

    def _set_status(self, text: str) -> None:
        from PySide6.QtWidgets import QLabel

        label = self._impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
        if label is not None:
            label.setText(text)

    @staticmethod
    def _default_scattering_parameters() -> Dict[str, float]:
        """Return the default scattering parameter set used by fixed-scattering solvers."""
        from app.core import processing

        return processing.get_default_scattering_parameters()

    @staticmethod
    def _default_background_parameters() -> Dict[str, float | str]:
        """Return the default background basis parameters."""
        from app.core import processing

        return processing.get_default_background_parameters()

    @staticmethod
    def _default_iterative_parameters() -> Dict[str, float | int]:
        """Return the default convergence parameter set used by the iterative solver."""
        from app.core import processing

        return processing.get_default_iterative_solver_parameters()

    @staticmethod
    def _uses_fixed_scattering_solver(solver_method: str) -> bool:
        """Return True when a solver uses the fixed-scattering controls."""
        return solver_method in {"mu_a", "iterative"}

    @staticmethod
    def _scattering_entry_specs() -> tuple[tuple[str, str, str], ...]:
        """Return ordered scattering parameter specs: key, label, objectName."""
        return (
            ("lambda0_nm", "lambda0", SCATTERING_LAMBDA0_ENTRY_OBJECT_NAME),
            ("mu_s_500_cm1", "mu_s_500", SCATTERING_MU_S_500_ENTRY_OBJECT_NAME),
            ("power_b", "b", SCATTERING_POWER_ENTRY_OBJECT_NAME),
            ("lipofundin_fraction", "lipo_frac", SCATTERING_LIPOFUNDIN_ENTRY_OBJECT_NAME),
            ("anisotropy_g", "g", SCATTERING_ANISOTROPY_ENTRY_OBJECT_NAME),
        )

    @staticmethod
    def _iterative_entry_specs() -> tuple[tuple[str, str, str], ...]:
        """Return ordered iterative parameter specs: key, label, objectName."""
        return (
            ("max_iter", "max_iter", ITERATIVE_MAX_ITER_ENTRY_OBJECT_NAME),
            ("tol_rel", "path_tol", ITERATIVE_TOL_REL_ENTRY_OBJECT_NAME),
            ("tol_rmse", "rmse_improvement_tol", ITERATIVE_TOL_RMSE_ENTRY_OBJECT_NAME),
            ("damping", "damping", ITERATIVE_DAMPING_ENTRY_OBJECT_NAME),
            ("initial_concentration", "initial_conc", ITERATIVE_INITIAL_CONC_ENTRY_OBJECT_NAME),
        )

    def _read_background_params_from_ui(self) -> Dict[str, float | str]:
        """Read, validate, and cache background basis parameters from toolbar entries."""
        from PySide6.QtWidgets import QComboBox, QLineEdit
        from app.core import processing

        model_combo = self._impl.findChild(QComboBox, BG_MODEL_COMBO_OBJECT_NAME)
        value_entry = self._impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        exp_start_entry = self._impl.findChild(QLineEdit, BG_EXP_START_ENTRY_OBJECT_NAME)
        exp_end_entry = self._impl.findChild(QLineEdit, BG_EXP_END_ENTRY_OBJECT_NAME)

        model = model_combo.currentText() if model_combo is not None else self._background_params["model"]
        raw_params = {
            "model": model,
            "value": value_entry.text().strip() if value_entry is not None else self._background_params["value"],
            "exp_start": self._background_params["exp_start"],
            "exp_end": self._background_params["exp_end"],
        }
        if model == "exponential":
            raw_params["exp_start"] = (
                exp_start_entry.text().strip()
                if exp_start_entry is not None
                else self._background_params["exp_start"]
            )
            raw_params["exp_end"] = (
                exp_end_entry.text().strip()
                if exp_end_entry is not None
                else self._background_params["exp_end"]
            )

        validated = processing.validate_background_parameters(raw_params)
        self._background_params = validated
        self._bg_value = float(validated["value"])
        return dict(validated)

    def _set_background_model_controls(
        self,
        model: str | None = None,
        background_enabled: bool = True,
    ) -> None:
        """Toggle constant vs exponential background controls."""
        if model is None:
            model = str(self._background_params.get("model", "constant"))
        use_exponential = model == "exponential"

        if self._background_label_action is not None:
            self._background_label_action.setVisible(background_enabled)
        if self._background_model_action is not None:
            self._background_model_action.setVisible(background_enabled)
        if self._background_entry_action is not None:
            self._background_entry_action.setVisible(background_enabled and not use_exponential)

        exp_visible = background_enabled and use_exponential
        for action in (
            self._background_exp_start_label_action,
            self._background_exp_start_entry_action,
            self._background_exp_end_label_action,
            self._background_exp_end_entry_action,
        ):
            if action is not None:
                action.setVisible(exp_visible)

    def _read_scattering_params_from_ui(self) -> Dict[str, float]:
        """Read, validate, and cache scattering parameters from toolbar entries."""
        from PySide6.QtWidgets import QLineEdit
        from app.core import processing

        raw_params = {}
        for key, _label, object_name in self._scattering_entry_specs():
            entry = self._impl.findChild(QLineEdit, object_name)
            raw_params[key] = entry.text().strip() if entry is not None else self._scattering_params[key]

        validated = processing.validate_scattering_parameters(raw_params)
        self._scattering_params = validated
        return dict(validated)

    def _read_iterative_params_from_ui(self) -> Dict[str, float | int]:
        """Read, validate, and cache iterative solver parameters from toolbar entries."""
        from PySide6.QtWidgets import QLineEdit
        from app.core import processing

        raw_params = {}
        for key, _label, object_name in self._iterative_entry_specs():
            entry = self._impl.findChild(QLineEdit, object_name)
            raw_params[key] = entry.text().strip() if entry is not None else self._iterative_params[key]

        validated = processing.validate_iterative_solver_parameters(raw_params)
        self._iterative_params = validated
        return dict(validated)

    def _set_solver_dependent_controls(self, solver_method: str) -> None:
        """Toggle background vs fixed-scattering controls based on solver."""
        from PySide6.QtWidgets import QToolBar

        use_fixed_scattering = self._uses_fixed_scattering_solver(solver_method)
        use_iterative_controls = solver_method == "iterative"
        use_background_controls = solver_method != "mu_a"

        scattering_toolbar = self._impl.findChild(QToolBar, SCATTERING_TOOLBAR_OBJECT_NAME)
        iterative_toolbar = self._impl.findChild(QToolBar, ITERATIVE_TOOLBAR_OBJECT_NAME)

        self._set_background_model_controls(background_enabled=use_background_controls)
        if scattering_toolbar is not None:
            scattering_toolbar.setVisible(use_fixed_scattering)
        if iterative_toolbar is not None:
            iterative_toolbar.setVisible(use_iterative_controls)

    def _on_solver_method_changed(self, solver_method: str) -> None:
        """Update solver-specific controls when the dropdown selection changes."""
        self._set_solver_dependent_controls(solver_method)

    # -- background entry validation (QT-005) --------------------------------

    def get_background_value(self) -> float:
        """Return the last validated background value."""
        return self._bg_value

    def get_background_parameters(self) -> Dict[str, float | str]:
        """Return the last validated background basis parameters."""
        return dict(self._background_params)

    def _on_background_model_changed(self, model: str) -> None:
        """Update visible background parameter controls when the model changes."""
        from PySide6.QtWidgets import QComboBox, QLabel

        combo = self._impl.findChild(QComboBox, BG_MODEL_COMBO_OBJECT_NAME)
        status_label = self._impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
        previous = str(self._background_params["model"])

        try:
            params = self._read_background_params_from_ui()
        except (TypeError, ValueError) as exc:
            if combo is not None:
                combo.setCurrentText(previous)
            if status_label is not None:
                status_label.setText(f"Invalid background model: {exc}")
            return

        self._set_background_model_controls(str(params["model"]))
        if status_label is not None and model != previous:
            status_label.setText(f"Background model = {params['model']}")

    def _on_bg_editing_finished(self) -> None:
        """Parse and validate the background QLineEdit on editingFinished.

        On success the internal state is updated and the status label shows
        a concise confirmation.  On failure the QLineEdit text is reverted
        to the last valid value and the status label shows an error message.
        """
        from PySide6.QtWidgets import QLineEdit, QLabel

        bg_entry = self._impl.findChild(QLineEdit, BG_ENTRY_OBJECT_NAME)
        status_label = self._impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)

        if bg_entry is None:
            return

        raw = bg_entry.text().strip()
        try:
            params = self._read_background_params_from_ui()
        except (ValueError, TypeError) as exc:
            # Revert to last valid value
            bg_entry.setText(str(self._bg_value))
            if status_label is not None:
                status_label.setText(f"Invalid background: {exc}")
            return

        previous = self._bg_value
        value = float(params["value"])
        bg_entry.setText(str(value))

        # Avoid clobbering more important status messages (for example,
        # pipeline failure text) when editingFinished is emitted on focus
        # transitions but the value itself did not change.
        if status_label is not None and value != previous:
            status_label.setText(f"Background = {value}")

    def _on_background_exp_editing_finished(self, key: str) -> None:
        """Validate one exponential background parameter."""
        from PySide6.QtWidgets import QLineEdit, QLabel

        entry_map = {
            "exp_start": BG_EXP_START_ENTRY_OBJECT_NAME,
            "exp_end": BG_EXP_END_ENTRY_OBJECT_NAME,
        }
        label_map = {
            "exp_start": "exp_start",
            "exp_end": "exp_end",
        }

        entry = self._impl.findChild(QLineEdit, entry_map[key])
        status_label = self._impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
        if entry is None:
            return

        previous = self._background_params[key]
        try:
            params = self._read_background_params_from_ui()
        except (TypeError, ValueError) as exc:
            entry.setText(str(self._background_params[key]))
            if status_label is not None:
                status_label.setText(f"Invalid {label_map[key]}: {exc}")
            return

        value = params[key]
        entry.setText(str(value))
        if status_label is not None and value != previous:
            status_label.setText(f"{label_map[key]} = {value}")

    def _on_scattering_editing_finished(self, key: str) -> None:
        """Validate one scattering entry while preserving the rest of the config."""
        from PySide6.QtWidgets import QLineEdit, QLabel

        entry_map = {entry_key: object_name for entry_key, _label, object_name in self._scattering_entry_specs()}
        label_map = {entry_key: label for entry_key, label, _object_name in self._scattering_entry_specs()}

        entry = self._impl.findChild(QLineEdit, entry_map[key])
        status_label = self._impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
        if entry is None:
            return

        previous = self._scattering_params[key]
        try:
            params = self._read_scattering_params_from_ui()
        except (TypeError, ValueError) as exc:
            entry.setText(str(self._scattering_params[key]))
            if status_label is not None:
                status_label.setText(f"Invalid {label_map[key]}: {exc}")
            return

        value = params[key]
        entry.setText(str(value))
        if status_label is not None and value != previous:
            status_label.setText(f"{label_map[key]} = {value}")

    def _on_iterative_editing_finished(self, key: str) -> None:
        """Validate one iterative entry while preserving the rest of the config."""
        from PySide6.QtWidgets import QLineEdit, QLabel

        entry_map = {entry_key: object_name for entry_key, _label, object_name in self._iterative_entry_specs()}
        label_map = {entry_key: label for entry_key, label, _object_name in self._iterative_entry_specs()}

        entry = self._impl.findChild(QLineEdit, entry_map[key])
        status_label = self._impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
        if entry is None:
            return

        previous = self._iterative_params[key]
        try:
            params = self._read_iterative_params_from_ui()
        except (TypeError, ValueError) as exc:
            entry.setText(str(self._iterative_params[key]))
            if status_label is not None:
                status_label.setText(f"Invalid {label_map[key]}: {exc}")
            return

        value = params[key]
        entry.setText(str(value))
        if status_label is not None and value != previous:
            status_label.setText(f"{label_map[key]} = {value}")

    def _on_iterative_reset_clicked(self) -> None:
        """Reset iterative solver entries to core defaults."""
        from PySide6.QtWidgets import QLineEdit, QLabel

        defaults = self._default_iterative_parameters()
        self._iterative_params = dict(defaults)

        for key, _label, object_name in self._iterative_entry_specs():
            entry = self._impl.findChild(QLineEdit, object_name)
            if entry is not None:
                entry.setText(str(defaults[key]))

        status_label = self._impl.findChild(QLabel, STATUS_LABEL_OBJECT_NAME)
        if status_label is not None:
            status_label.setText("Iterative solver defaults restored")

    # -- sidebar builder ----------------------------------------------------

    @staticmethod
    def _build_sidebar(parent: QWidget) -> QFrame:
        """Construct the left sidebar with placeholder sections."""
        from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QTextEdit, QVBoxLayout

        sidebar = QFrame(parent)
        sidebar.setObjectName(SIDEBAR_OBJECT_NAME)
        sidebar.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # --- Folder Info section ---
        layout.addWidget(QLabel("<b>Folder Info</b>"))
        folder_info = QTextEdit(sidebar)
        folder_info.setObjectName(FOLDER_INFO_TEXT_OBJECT_NAME)
        folder_info.setReadOnly(True)
        folder_info.setPlainText("No folder loaded.")
        layout.addWidget(folder_info)

        # --- Sample section ---
        layout.addWidget(QLabel("<b>Sample</b>"))
        sample_combo = QComboBox(sidebar)
        sample_combo.setObjectName(SAMPLE_COMBO_OBJECT_NAME)
        sample_combo.setEditable(False)
        sample_combo.setEnabled(False)
        sample_combo.addItem("— none —")
        layout.addWidget(sample_combo)

        # --- Warnings section ---
        layout.addWidget(QLabel("<b>Warnings</b>"))
        warnings_text = QTextEdit(sidebar)
        warnings_text.setObjectName(WARNINGS_TEXT_OBJECT_NAME)
        warnings_text.setReadOnly(True)
        warnings_text.setStyleSheet("color: red;")
        warnings_text.setPlainText("No warnings.")
        layout.addWidget(warnings_text)

        # Spacer to push everything to the top
        layout.addStretch()

        return sidebar

    # -- tab widget builder -------------------------------------------------

    def _build_tab_widget(self, parent: QWidget) -> QTabWidget:
        """Construct the right-side QTabWidget with four panels."""
        from PySide6.QtWidgets import QTabWidget

        from app.gui_qt.panels import (
            ChromophoreBarChartsPanel,
            DiagnosticsPanel,
            InspectorPanel,
            MapsPanel,
            StatsPanel,
        )

        tab_widget = QTabWidget(parent)
        tab_widget.setObjectName(TAB_WIDGET_OBJECT_NAME)

        # Tab order is significant — must match the spec exactly.
        maps_panel = MapsPanel(tab_widget)
        maps_panel._impl.setObjectName(MAPS_TAB_OBJECT_NAME)
        tab_widget.addTab(maps_panel._impl, MAPS_TAB_LABEL)

        inspector_panel = InspectorPanel(tab_widget)
        inspector_panel._impl.setObjectName(INSPECTOR_TAB_OBJECT_NAME)
        tab_widget.addTab(inspector_panel._impl, INSPECTOR_TAB_LABEL)

        diagnostics_panel = DiagnosticsPanel(tab_widget)
        diagnostics_panel._impl.setObjectName(DIAGNOSTICS_TAB_OBJECT_NAME)
        tab_widget.addTab(diagnostics_panel._impl, DIAGNOSTICS_TAB_LABEL)

        stats_panel = StatsPanel(tab_widget)
        stats_panel._impl.setObjectName(STATS_TAB_OBJECT_NAME)
        tab_widget.addTab(stats_panel._impl, STATS_TAB_LABEL)

        barcharts_panel = ChromophoreBarChartsPanel(tab_widget)
        barcharts_panel._impl.setObjectName(BAR_CHARTS_TAB_OBJECT_NAME)
        tab_widget.addTab(barcharts_panel._impl, BAR_CHARTS_TAB_LABEL)

        self._maps_panel = maps_panel
        self._inspector_panel = inspector_panel
        self._diagnostics_panel = diagnostics_panel
        self._stats_panel = stats_panel
        self._barcharts_panel = barcharts_panel

        return tab_widget

    def _find_default_data_dir(self) -> str | None:
        """Locate data/ relative to bundle or repository root."""
        if hasattr(sys, "_MEIPASS"):
            bundle_dir = getattr(sys, "_MEIPASS")
            bundle_data = os.path.join(bundle_dir, "data")
            if os.path.isdir(bundle_data):
                return bundle_data

        candidates = [
            os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "data")),
            os.path.normpath(os.path.join(os.getcwd(), "data")),
        ]
        for path in candidates:
            if os.path.isdir(path):
                return path
        return None

    def _refresh_chromophore_menu(self) -> None:
        """Refresh chromophore selections from the active data directory."""
        if self._chromophore_menu is None:
            return

        if not self.data_dir:
            self.set_chromophores([])
            return

        try:
            from app.core import io as loader
        except Exception:
            self.set_chromophores([])
            return

        try:
            spectra = loader.load_chromophore_spectra(self.data_dir)
        except Exception:
            self.set_chromophores([])
            return

        self.set_chromophores(sorted(spectra.keys()))

    def _set_data_source_label(self, text: str) -> None:
        from PySide6.QtWidgets import QLabel

        label = self._impl.findChild(QLabel, DATA_SOURCE_LABEL_OBJECT_NAME)
        if label is not None:
            label.setText(text)

    def _set_data_source_label_from_state(self) -> None:
        if self.data_dir:
            self._set_data_source_label(f"Data: default ({os.path.basename(self.data_dir)})")
        else:
            self._set_data_source_label("Data: default (not found)")

    def _show_error(self, title: str, message: str) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self._impl)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setModal(False)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.finished.connect(lambda _r, b=box: self._dialogs.remove(b) if b in self._dialogs else None)
        self._dialogs.append(box)
        box.show()

    def _show_info(self, title: str, message: str) -> None:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self._impl)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setModal(False)
        box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        box.finished.connect(lambda _r, b=box: self._dialogs.remove(b) if b in self._dialogs else None)
        self._dialogs.append(box)
        box.show()

    def _can_run_pipeline(self) -> bool:
        return bool(self.folder_info) and bool(self.data_dir)

    def _format_folder_info(self, root_path: str, info: Dict[str, Any]) -> str:
        """Create user-facing sidebar text from folder detection output."""
        sample_names = list(info.get("sample_names", []))
        wavelengths = list(info.get("wavelengths", []))
        lines = [
            f"Root: {os.path.basename(root_path)}",
            f"Samples: {len(sample_names)}",
        ]
        lines.extend([f"  • {name}" for name in sample_names])
        lines.extend([
            "",
            f"LEDs: {len(wavelengths)}",
            f"  {wavelengths} nm",
            "",
            "Ref: ✓",
            "Dark ref: ✓",
        ])
        return "\n".join(lines)

    def _compute_global_scales(
        self,
        results: Dict[str, Dict[str, Any]],
        chrom_names: list[str],
        include_background: bool,
    ) -> tuple[Dict[str, tuple[float, float]], Dict[str, tuple[float, float]]]:
        """Compute deterministic global map scales across all samples."""
        import numpy as np

        all_names = chrom_names.copy()
        if include_background:
            all_names.append("background")

        chrom_scales: Dict[str, tuple[float, float]] = {}
        for idx, name in enumerate(all_names):
            vals = []
            for res in results.values():
                conc = np.asarray(res["concentrations"])
                if conc.ndim != 3 or idx >= conc.shape[2]:
                    continue
                finite = conc[:, :, idx][np.isfinite(conc[:, :, idx])]
                if finite.size > 0:
                    vals.append(finite)
            if vals:
                merged = np.concatenate(vals)
                chrom_scales[name] = (float(merged.min()), float(merged.max()))
            else:
                chrom_scales[name] = (0.0, 1.0)

        derived_scales: Dict[str, tuple[float, float]] = {}
        for res in results.values():
            derived = res.get("derived", {})
            for key in ["THb", "StO2"]:
                arr = derived.get(key)
                if arr is None:
                    continue
                finite = np.asarray(arr)[np.isfinite(arr)]
                if finite.size == 0:
                    continue
                cur = derived_scales.get(key)
                mn, mx = float(finite.min()), float(finite.max())
                derived_scales[key] = (mn, mx) if cur is None else (min(cur[0], mn), max(cur[1], mx))

            rmse = res.get("rmse_map")
            if rmse is not None:
                finite = np.asarray(rmse)[np.isfinite(rmse)]
                if finite.size > 0:
                    cur = derived_scales.get("RMSE")
                    mn, mx = float(finite.min()), float(finite.max())
                    derived_scales["RMSE"] = (mn, mx) if cur is None else (min(cur[0], mn), max(cur[1], mx))

        return chrom_scales, derived_scales

    # -- internal self-check ------------------------------------------------

    def update_warnings(self, warnings: list[str] | None) -> None:
        """Populate the warnings sidebar text from a diagnostics list.

        Args:
            warnings: List of warning strings, or None to clear.
        """
        from PySide6.QtWidgets import QTextEdit

        widget = self._impl.findChild(QTextEdit, WARNINGS_TEXT_OBJECT_NAME)
        if widget is None:
            return
        if not warnings:
            widget.setPlainText("No warnings ✓")
        else:
            widget.setPlainText("\n".join(warnings))

    def _check_invariants(self) -> bool:
        """Internal self-check for pytest-qt compatibility.

        Returns True if window properties match expectations.
        """
        impl = self._impl
        checks = [
            impl.windowTitle() == "Spectral Unmixing",
            impl.width() == 1400,
            impl.height() == 900,
            impl.minimumWidth() == 1000,
            impl.minimumHeight() == 700,
            impl.objectName() == OBJECT_NAME,
            impl.centralWidget() is not None,
        ]
        return all(checks)


# ---------------------------------------------------------------------------
# Lazy factory (keeps PySide6 out of module-level namespace)
# ---------------------------------------------------------------------------

def _make_main_window() -> type:
    """Return the concrete QMainWindow subclass."""
    try:
        from PySide6.QtWidgets import QMainWindow
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PySide6 is required to instantiate SpectralUnmixingMainWindow"
        ) from exc

    class _MainWindow(QMainWindow):
        """Concrete main window."""

        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)

    return _MainWindow
