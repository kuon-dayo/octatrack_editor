 # アプリ起動／依存注入

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
import sys

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(800, 480)
    w.show()
    sys.exit(app.exec())