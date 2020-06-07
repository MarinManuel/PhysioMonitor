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
    logFile = LogFile(startDlg.logFile)
    config['log-file'] = logFile

    scr = PhysioMonitorMainScreen(config)

    logFile.widget = scr.logBox
    logFile.append(logFile.getHeader(mouse=startDlg.mouse, drugList=startDlg.drugList, exp=startDlg.experiment))
    scr.show()
    app.exec()
