from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool, Slot
import logging
from typing import Callable, Any

class WorkerSignals(QObject):
    """
    Señales utilizadas por el trabajador para comunicarse con el hilo de UI.
    """
    success = Signal(object)  # Emite el valor retornado por la función
    error = Signal(Exception) # Emite la excepción lanzada si hay un fallo no controlado

class Worker(QRunnable):
    """
    Trabajador genérico que ejecuta una función Callable en un hilo del QThreadPool.
    """
    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.success.emit(result)
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in run_async task: %s", self.fn.__name__ if hasattr(self.fn, "__name__") else str(self.fn))
            self.signals.error.emit(e)

class CallbackBridge(QObject):
    """
    Puente que recibe las señales del hilo trabajador y ejecuta los callbacks en el hilo de UI.
    Al ser un QObject creado en el hilo principal, PySide6 usará QueuedConnection de forma automática.
    """
    def __init__(self, on_success: Callable[[Any], None] | None, on_error: Callable[[Exception], None] | None, parent: QObject | None = None):
        if parent is None:
            from PySide6.QtWidgets import QApplication
            parent = QApplication.instance()
        super().__init__(parent)
        self.on_success = on_success
        self.on_error = on_error

    @Slot(object)
    def handle_success(self, result: Any) -> None:
        try:
            if self.on_success is not None:
                self.on_success(result)
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in run_async on_success callback")
        finally:
            self.deleteLater()

    @Slot(Exception)
    def handle_error(self, exc: Exception) -> None:
        try:
            if self.on_error is not None:
                self.on_error(exc)
        except Exception as e:
            logging.getLogger("tardis").exception("Exception in run_async on_error callback")
        finally:
            self.deleteLater()

def run_async(fn: Callable, *args,
              on_success: Callable[[Any], None] | None = None,
              on_error: Callable[[Exception], None] | None = None,
              **kwargs) -> None:
    """
    Ejecuta fn(*args, **kwargs) en QThreadPool.globalInstance().
    - on_success(result) se invoca en el hilo de UI con el retorno de fn.
    - on_error(exc) se invoca en el hilo de UI si fn lanza una excepción no controlada.
    """
    worker = Worker(fn, *args, **kwargs)
    
    bridge = CallbackBridge(on_success, on_error)
    worker.bridge = bridge  # Mantener referencia para evitar la recolección de basura
    
    worker.signals.success.connect(bridge.handle_success)
    worker.signals.error.connect(bridge.handle_error)
        
    QThreadPool.globalInstance().start(worker)

