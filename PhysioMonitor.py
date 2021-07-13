# -*- coding: utf-8 -*-
import argparse
import json
import logging
import sys
from PyQt5 import Qt
from PyQt5.QtWidgets import QApplication
from GUI.GUI import PhysioMonitorMainScreen, StartDialog
from monitor.Objects import LogFile

parser = argparse.ArgumentParser()
parser.add_argument('-c', "--config", help="path of the configuration file to use (required)", required=True)
parser.add_argument('--log_level', help='level of information to log. '
                                        'Can be one of [DEBUG,INFO,WARNING,ERROR,CRITICAL]. '
                                        'Default is WARNING',
                    default='WARNING')
parser.add_argument('--logfile', help='file in which the log is written. '
                                      'If absent or None, log is directed to stdout',
                    default=None)
args = parser.parse_args()

# see https://docs.python.org/3/howto/logging.html#logging-to-a-file
numeric_level = getattr(logging, args.log_level.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError(f'Invalid log level: {args.log_level}')
logfile = '/dev/stdout'
if args.logfile is not None:
    logfile = args.logfile
logger = logging.getLogger(__name__)
logging.basicConfig(level=numeric_level, filename=logfile, filemode='w')

try:
    with open(args.config, 'r', encoding='utf-8') as f:
        logger.info(f'Reading configuration from <{args.config}>')
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    parser.error("filed passed to --config is not a valid configuration file")


app = QApplication(sys.argv)
startDlg = StartDialog(config=config)
if startDlg.exec():
    config = startDlg.config
    logFile = LogFile(startDlg.logFile)
    config['log-file'] = logFile

    physio_monitor = PhysioMonitorMainScreen(config)

    logFile.widget = physio_monitor.logBox
    if not startDlg.isResumed:
        logFile.append(logFile.getHeader(mouse=startDlg.mouse, drugList=startDlg.drugList))
    else:
        with open(startDlg.logFile, 'r', encoding='utf-8') as f:
            previous_content = f.read()
        logFile.content = previous_content
        logFile.widget.setPlainText(previous_content)
        logFile.append('#### resumed from here\n')
    physio_monitor.show()
    physio_monitor.start()
    app.exec()
