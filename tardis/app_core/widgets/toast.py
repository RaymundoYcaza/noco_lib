from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QGraphicsOpacityEffect
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Slot, QEvent, QObject
import logging

class Toast(QWidget):
    _active_toasts = []

    def __init__(self, parent: QWidget, text: str, level: str = "info", duration_ms: int = 4000):
        super().__init__(parent)
        self.text = text
        self.level = level.lower()
        self.duration_ms = duration_ms
        
        self.init_ui()
        
        # Position self initially
        self.adjust_size_and_position()
        
        # Add to active toasts list
        Toast._active_toasts.append(self)
        
        # Reposition all active toasts (stack them)
        Toast.reposition_all()
        
        # Setup opacity effect for fade animation
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        
        # Show and start fade-in animation
        self.show()
        self.raise_()
        self.fade_in()
        
        # Start auto-close timer using QTimer.singleShot
        QTimer.singleShot(self.duration_ms, self.fade_out)
        
        # Install event filter on parent to follow resize events
        if parent:
            parent.installEventFilter(self)

    def init_ui(self):
        self.setObjectName("ToastWidget")
        
        # Transparent background for the widget so rounded borders show correctly
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Text label
        self.label = QLabel(self.text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: #ffffff; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.label)
        
        # Style based on level
        bg_colors = {
            "info": "rgba(37, 99, 235, 0.95)",    # Blue-ish
            "error": "rgba(220, 38, 38, 0.95)",   # Red-ish
            "success": "rgba(22, 163, 74, 0.95)"  # Green-ish
        }
        border_colors = {
            "info": "#3b82f6",
            "error": "#f87171",
            "success": "#4ade80"
        }
        
        bg_color = bg_colors.get(self.level, bg_colors["info"])
        border_color = border_colors.get(self.level, border_colors["info"])
        
        self.setStyleSheet(f"""
            QWidget#ToastWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
        """)

    def adjust_size_and_position(self):
        self.setMaximumWidth(350)
        self.setMinimumWidth(200)
        self.adjustSize()

    @classmethod
    def reposition_all(cls):
        """
        Stacks all active toasts vertically at the bottom-right corner of their parent window.
        """
        for i, toast in enumerate(cls._active_toasts):
            parent = toast.parentWidget()
            if not parent:
                continue
                
            parent_w = parent.width()
            parent_h = parent.height()
            
            # Start margin: 16px from bottom
            # Gap: 8px between toasts
            y_offset = 16
            for prev_toast in cls._active_toasts[:i]:
                y_offset += prev_toast.height() + 8
                
            x = parent_w - 16 - toast.width()
            y = parent_h - 16 - toast.height() - (y_offset - 16)
            
            toast.move(x, y)

    def fade_in(self):
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(250)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

    @Slot()
    def fade_out(self):
        # Prevent crash if widget is already being destroyed or has no opacity effect
        try:
            self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
            self.anim.setDuration(250)
            self.anim.setStartValue(1.0)
            self.anim.setEndValue(0.0)
            self.anim.setEasingCurve(QEasingCurve.InCubic)
            self.anim.finished.connect(self.close_and_remove)
            self.anim.start()
        except Exception:
            self.close_and_remove()

    def close_and_remove(self):
        try:
            self.close()
            if self in Toast._active_toasts:
                Toast._active_toasts.remove(self)
            Toast.reposition_all()
            self.deleteLater()
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in Toast.close_and_remove")

    def closeEvent(self, event):
        try:
            if self in Toast._active_toasts:
                Toast._active_toasts.remove(self)
            Toast.reposition_all()
        except Exception:
            pass
        super().closeEvent(event)

    def eventFilter(self, watched, event):
        try:
            if watched == self.parentWidget() and event.type() == QEvent.Resize:
                Toast.reposition_all()
        except Exception:
            pass
        return super().eventFilter(watched, event)
