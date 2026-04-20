"""Chromophore menu widget with checkable chromophore actions.

Import-safe: PySide6 is deferred until instantiation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:  # pragma: no cover
    from PySide6.QtWidgets import QWidget


OBJECT_NAME: str = "ChromophoreMenu"
BUTTON_TEXT: str = "Chromophores"
BACKGROUND_LABEL: str = "Background"


class ChromophoreMenu:
    """Checkable QToolButton + QMenu for chromophore selection."""

    def __init__(self, parent: Any = None) -> None:
        self._impl = _make_tool_button()(parent)
        self._impl.setObjectName(OBJECT_NAME)
        self._menu: Any = None
        self._chromophores: list[str] = []
        self._chromophore_actions: dict[str, Any] = {}
        self._background_action: Any = None
        self._setup_ui()

    # -- public interface (stubs) -------------------------------------------

    def set_chromophores(self, names: Sequence[str]) -> None:
        """Populate the menu with the given chromophore names."""
        unique_names = {str(name).strip() for name in names if str(name).strip()}
        self._chromophores = sorted(unique_names)
        self.refresh_menu()

    def get_selected(self, include_background: bool = False) -> list[str]:
        """Return checked chromophore names in deterministic order.

        Args:
            include_background: Include ``Background`` when enabled.
        """
        selected = [
            name for name in self._chromophores
            if name in self._chromophore_actions and self._chromophore_actions[name].isChecked()
        ]
        if include_background and self._background_action is not None and self._background_action.isChecked():
            selected.append(BACKGROUND_LABEL)
        return selected

    def refresh_menu(self) -> None:
        """Rebuild the menu UI from the current chromophore list."""
        if self._menu is None:
            return

        existing_background_checked = True
        if self._background_action is not None:
            existing_background_checked = bool(self._background_action.isChecked())

        old_states = {
            name: action.isChecked()
            for name, action in self._chromophore_actions.items()
        }

        self._menu.clear()
        self._chromophore_actions = {}

        for name in self._chromophores:
            action = self._menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(old_states.get(name, True))
            self._chromophore_actions[name] = action

        if self._chromophores:
            self._menu.addSeparator()

        background_action = self._menu.addAction(BACKGROUND_LABEL)
        background_action.setCheckable(True)
        background_action.setChecked(existing_background_checked)
        self._background_action = background_action

    # -- internal -----------------------------------------------------------

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        from PySide6.QtWidgets import QMenu, QToolButton

        self._impl.setText(BUTTON_TEXT)
        self._impl.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self._menu = QMenu(self._impl)
        self._impl.setMenu(self._menu)

        self.refresh_menu()


# ---------------------------------------------------------------------------
def _make_tool_button() -> type:
    """Return a QToolButton subclass."""
    try:
        from PySide6.QtWidgets import QToolButton
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "PySide6 is required to instantiate ChromophoreMenu"
        ) from exc

    class _ChromophoreMenuButton(QToolButton):
        def __init__(self, parent: Any = None) -> None:
            super().__init__(parent)

    return _ChromophoreMenuButton
