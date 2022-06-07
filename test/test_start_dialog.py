import sys
import json
from PyQt5.QtWidgets import QApplication
from GUI.GUI import StartDialog

sys.path.insert(0, "./GUI")

with open("./PhysioMonitor.json", "r", encoding="utf-8") as f:
    config = json.load(f)

app = QApplication(sys.argv)
dlg = StartDialog(config=config)
dlg.exec()
