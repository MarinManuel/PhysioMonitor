import logging
import sys
from PyQt5.QtWidgets import QApplication
from GUI.GUI import PhysioMonitorMainScreen, startDialog
from monitor.Objects import LogFile

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

app = QApplication(sys.argv)

startDlg = startDialog()
if startDlg.exec():
    config = startDlg.config
    config['logFile'] = LogFile(startDlg.logFile)
    out = config['logFile'].getHeader(mouse=startDlg.mouse, drugList=startDlg.drugList, exp=startDlg.experiment)

    scr = PhysioMonitorMainScreen(config)
    scr.show()
    app.exec()
