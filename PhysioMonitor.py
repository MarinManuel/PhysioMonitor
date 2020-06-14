import argparse
import json
import logging
import sys
from PyQt5.QtWidgets import QApplication
from GUI.GUI import PhysioMonitorMainScreen, StartDialog
from monitor.Objects import LogFile

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


parser = argparse.ArgumentParser()
parser.add_argument('-c', "--config", help="path of the configuration file to use (required)", required=True)
args = parser.parse_args()

try:
    with open(args.config, 'r') as f:
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    parser.error("filed passed to --config is not a valid configuration file")


app = QApplication(sys.argv)
startDlg = StartDialog(config=config)
if startDlg.exec():
    config = startDlg.config
    logFile = LogFile(startDlg.logFile)
    config['log-file'] = logFile

    scr = PhysioMonitorMainScreen(config)

    logFile.widget = scr.logBox
    if not startDlg.isResumed:
        logFile.append(logFile.getHeader(mouse=startDlg.mouse, drugList=startDlg.drugList))
    else:
        with open(startDlg.logFile, 'r') as f:
            previous_content = f.read()
        logFile.content = previous_content
        logFile.widget.setPlainText(previous_content)
        logFile.append('#### resumed from here\n')
    scr.show()
    scr.start()
    app.exec()
