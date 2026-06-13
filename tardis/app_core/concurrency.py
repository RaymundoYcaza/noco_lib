from PySide6.QtCore import QObject, Signal, QRunnable, QThreadPool
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
            self.signals.error.emit(e)

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
    
    if on_success is not None:
        worker.signals.success.connect(on_success)
        
    if on_error is not None:
        worker.signals.error.connect(on_error)
        
    QThreadPool.globalInstance().start(worker)
