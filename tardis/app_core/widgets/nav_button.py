from PySide6.QtWidgets import QPushButton, QWidget, QSizePolicy
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

import qtawesome as qta

import logging


class NavButton(QPushButton):
    """Individual icon button for the App Switcher bar.

    A fixed-size (52×52px) flat button displaying a qtawesome icon.
    Supports a checked/active state managed by the parent NavBar for
    mutual exclusion across nav items.

    QSS selectors:
      - ``NavButton`` — base style (transparent background, no border)
      - ``NavButton:hover`` — hover highlight
      ``NavButton:checked`` — active module indicator (accent left border)

    El color del icono se actualiza dinámicamente desde Python:
    - Inactivo: ``#5a5a56`` (``color.nav.icon``)
    - Activo: ``#e9290c`` (``color.nav.icon.active``)
    """

    # Colores del tema Inorizonti para los iconos de navegación
    _COLOR_INACTIVE = "#5a5a56"
    _COLOR_ACTIVE = "#e9290c"

    def __init__(
        self,
        icon_name: str,
        label: str,
        module_id: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the NavButton.

        Parameters
        ----------
        icon_name : str
            qtawesome icon identifier, e.g. ``"fa5s.envelope"``.
        label : str
            Tooltip text and human-readable name for the module.
        module_id : str | None
            Optional unique module identifier emitted when clicked.
        parent : QWidget | None
            Optional parent widget.
        """
        super().__init__(parent)
        self._module_id = module_id or label
        self._label = label
        self._icon_name = icon_name

        self.setFixedSize(52, 52)
        self.setFlat(True)
        self.setCheckable(True)
        self.setToolTip(label)

        # Build the icon with the inactive color (tema Inorizonti claro)
        self._update_icon_color()
        self.setIconSize(QSize(28, 28))

        # Ensure the button can shrink properly inside the nav bar
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Conectar señal toggled a la actualización de color del icono
        self.toggled.connect(self._update_icon_color)

        # Initial active state
        self._active = False

    def _update_icon_color(self) -> None:
        """Actualiza el color del icono según el estado activo/inactivo."""
        color = self._COLOR_ACTIVE if self.isChecked() else self._COLOR_INACTIVE
        try:
            self._icon = qta.icon(self._icon_name, color=color)
        except Exception:
            logging.getLogger("tardis").exception(
                "Failed to update qtawesome icon '%s' for NavButton '%s'",
                self._icon_name,
                self._label,
            )
            self._icon = QIcon()
        self.setIcon(self._icon)

    # ── active property ────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        """Whether this nav button represents the currently active module."""
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        """Set the active state and trigger QSS re-polishing."""
        if self._active == value:
            return
        self._active = value
        self.setProperty("active", value)
        # Force Qt to re-evaluate QSS selectors on this widget
        if self.style() is not None:
            self.style().unpolish(self)
            self.style().polish(self)
        self.setChecked(value)

    @property
    def module_id(self) -> str:
        """Return the module identifier for this button."""
        return self._module_id

    def __repr__(self) -> str:
        return f"NavButton(module_id={self._module_id!r}, label={self._label!r})"
