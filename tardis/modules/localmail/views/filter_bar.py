from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QComboBox
from PySide6.QtCore import Signal, Slot

class FilterBarView(QWidget):
    filter_changed = Signal(str, str)

    def __init__(self, main_window: QWidget, parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 1. QLineEdit for searching subject or sender
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search subject or sender...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #ffffff;
                color: #1a1a18;
                border: 1px solid #dddad6;
                border-radius: 4px;
                padding: 6px 10px;
            }
            QLineEdit:focus {
                border-color: #e9290c;
            }
        """)
        self.search_input.textChanged.connect(self._on_filter_changed)

        # 2. QComboBox for priority selection
        self.priority_combo = QComboBox()
        self.priority_combo.addItems(["All", "Baja", "Media", "Alta"])
        self.priority_combo.setStyleSheet("""
            QComboBox {
                background-color: #ffffff;
                color: #1a1a18;
                border: 1px solid #dddad6;
                border-radius: 4px;
                padding: 6px 10px;
                min-width: 100px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                color: #1a1a18;
                selection-background-color: #ede9e4;
            }
        """)
        self.priority_combo.currentTextChanged.connect(self._on_filter_changed)

        layout.addWidget(self.search_input, 1) # stretch search box to fill space
        layout.addWidget(self.priority_combo)

        # Nota: El botón Refresh/Actualizar se mantiene en EmailListView por compatibilidad
        # con la suite de pruebas unitarias existentes (decisión documentada de la sección 9.3.3).

    @Slot()
    def _on_filter_changed(self) -> None:
        search_text = self.search_input.text()
        priority = self.priority_combo.currentText()
        self.filter_changed.emit(search_text, priority)
