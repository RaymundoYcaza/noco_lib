from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor

from app_core.widgets.nav_button import NavButton

import logging

logger = logging.getLogger("tardis")


class NavBar(QWidget):
    """App Switcher bar — a narrow fixed column (52px) at the far left
    of ``MainWindow``, containing module icon buttons.

    Layout structure::

        ┌──────────────┐
        │  TOP ZONE    │  ← fixed, always visible (LocalMail)
        │──────────────│
        │  MIDDLE      │  ← QScrollArea (no visible scrollbar,
        │  (scrollable)│     mouse-wheel scrolls)
        │              │
        │  ······      │
        │              │
        │──────────────│
        │  SpacerItem  │  ← expanding, pushes bottom zone down
        │──────────────│
        │  BOTTOM ZONE │  ← fixed, always visible (Settings)
        └──────────────┘

    Signals
    -------
    module_activated(module_id: str)
        Emitted when a nav button is clicked. The bar manages mutual
        exclusion — all other buttons are unchecked automatically.
    """

    module_activated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setFixedWidth(52)
        self.setObjectName("NavBar")

        # ── Main layout ────────────────────────────────────────────
        self._layout = QVBoxLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # ── Top zone (always visible) ──────────────────────────────
        self._top_widget = QWidget(self)
        self._top_widget.setObjectName("NavBarTopZone")
        self._top_layout = QVBoxLayout(self._top_widget)
        self._top_layout.setSpacing(0)
        self._top_layout.setContentsMargins(0, 0, 0, 0)
        self._top_layout.addStretch()  # buttons pack toward bottom of top zone
        self._layout.addWidget(self._top_widget)

        # ── Middle zone (scrollable) ───────────────────────────────
        self._scroll_area = QScrollArea(self)
        self._scroll_area.setObjectName("NavBarScrollArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QScrollArea.NoFrame)

        # Inner widget that holds the middle buttons
        self._middle_widget = QWidget()
        self._middle_widget.setObjectName("NavBarMiddleZone")
        self._middle_layout = QVBoxLayout(self._middle_widget)
        self._middle_layout.setSpacing(0)
        self._middle_layout.setContentsMargins(0, 0, 0, 0)
        self._middle_layout.addStretch()  # buttons pack toward top

        self._scroll_area.setWidget(self._middle_widget)
        self._layout.addWidget(self._scroll_area)

        # ── Expanding spacer ───────────────────────────────────────
        self._layout.addStretch(1)

        # ── Bottom zone (always visible) ───────────────────────────
        self._bottom_widget = QWidget(self)
        self._bottom_widget.setObjectName("NavBarBottomZone")
        self._bottom_layout = QVBoxLayout(self._bottom_widget)
        self._bottom_layout.setSpacing(0)
        self._bottom_layout.setContentsMargins(0, 0, 0, 0)
        self._bottom_layout.addStretch()  # buttons pack toward bottom
        self._layout.addWidget(self._bottom_widget)

        # ── internal state ─────────────────────────────────────────
        self._buttons: dict[str, NavButton] = {}  # module_id → button

    # ── Public API ────────────────────────────────────────────────────

    def add_button(self, button: NavButton, position: str = "middle") -> None:
        """Register a nav button in the specified zone.

        Parameters
        ----------
        button : NavButton
            The button to add.
        position : {"top", "middle", "bottom"}
            Which zone to place the button in.
        """
        module_id = button.module_id
        if module_id in self._buttons:
            logger.warning(
                "NavBar: button with module_id '%s' already registered — skipping",
                module_id,
            )
            return

        self._buttons[module_id] = button

        if position == "top":
            # Insert before the stretch so buttons pack toward the bottom
            self._top_layout.insertWidget(
                self._top_layout.count() - 1, button
            )
        elif position == "bottom":
            # Insert before the stretch so buttons pack toward the top of the bottom zone
            self._bottom_layout.insertWidget(
                self._bottom_layout.count() - 1, button
            )
        else:  # "middle" (default)
            self._middle_layout.insertWidget(
                self._middle_layout.count() - 1, button  # before stretch
            )

        # Connect click → mutual exclusion + signal emission
        button.clicked.connect(lambda checked, mid=module_id: self._on_clicked(mid))

    def set_active(self, module_id: str) -> None:
        """Mark the given module as active, unchecking all others.

        Parameters
        ----------
        module_id : str
            The module identifier of the button to activate.
        """
        for mid, btn in self._buttons.items():
            btn.active = (mid == module_id)

    # ── Internal helpers ──────────────────────────────────────────────

    def _on_clicked(self, module_id: str) -> None:
        """Handle a button click: activate the clicked module."""
        # Uncheck all other buttons, check the clicked one
        self.set_active(module_id)
        self.module_activated.emit(module_id)

    def __repr__(self) -> str:
        return f"NavBar(buttons={list(self._buttons.keys())})"
