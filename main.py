import os
import sys
import warnings
import json
from pathlib import Path
from PySide6.QtCore import QUrl, Qt
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtGui import QIcon

from bridge import TagGUIBridge

# version = 1.2.4

#  supress third party Syntax Warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Force hardware acceleration and GPU rasterization for smooth UI rendering
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--enable-gpu-rasterization --ignore-gpu-blocklist"
# os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu-rasterization --disable-gpu"


# ==============================================================================
# MAIN WINDOW CLASS
# ==============================================================================

class MainWindow(QMainWindow):

  def __init__(self):
    super().__init__()
    self.setWindowTitle("TagGUI Next")
    self.resize(1280, 800)

    # Setup WebChannel Bridge
    self.channel = QWebChannel(self)
    self.bridge = TagGUIBridge(parent_window=self)  # <--- Pass main window reference here
    self.channel.registerObject("backend", self.bridge)

    # Setup Web Engine View
    self.web_view = QWebEngineView(self)
    self.web_view.page().setWebChannel(self.channel)
    
    # --- DISABLE CHROMIUM CONTEXT MENU AT WEBENGINE LEVEL ---
    self.web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
    # --------------------------------------------------------

    # Point correctly to ./ui/frontend.html
    html_path = (Path(__file__).parent / "ui" / "frontend.html").resolve()
    print(f"[Loader] Loading UI from: {html_path}")
    self.web_view.setUrl(QUrl.fromLocalFile(str(html_path)))

    self.setCentralWidget(self.web_view)

    # Set the window icon (make sure 'icon.png' or 'icon.ico' is in your app directory)
    icon_path = os.path.join(os.path.dirname(__file__), "assets/icon.png")
    if os.path.exists(icon_path):
      self.setWindowIcon(QIcon(icon_path))


if __name__ == "__main__":
  app = QApplication(sys.argv)

  qss_path = Path(__file__).parent / "ui" / "style.qss"
  if qss_path.exists():
    app.setStyleSheet(qss_path.read_text(encoding="utf-8"))

  window = MainWindow()
  window.show()
  sys.exit(app.exec())