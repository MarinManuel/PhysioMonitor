import sys
import json
from PyQt5.QtWidgets import QApplication
sys.path.insert(0, "./")
from GUI.GUI import StartDialog

with open('./PhysioMonitor.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

app = QApplication(sys.argv)
dlg = StartDialog(config=config)
dlg.exec()
