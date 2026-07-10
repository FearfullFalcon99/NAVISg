import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)
    
    window = MainWindow()
    window.show()
    
    # PySide6 uses exec() instead of exec_()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()