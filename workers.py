import time
from PySide6.QtCore import QThread, Signal

class GeneralWorker(QThread):
    # PySide6 uses Signal instead of pyqtSignal
    status_signal = Signal(str)

    def run(self):
        counter = 1
        while True:
            self.status_signal.emit(f"General system checks completed: {counter}")
            counter += 1
            time.sleep(3)

class GasLiftWorker(QThread):
    pressure_signal = Signal(float)

    def run(self):
        simulated_pressure = 100.0
        while True:
            simulated_pressure += 0.5 
            self.pressure_signal.emit(simulated_pressure)
            time.sleep(1)