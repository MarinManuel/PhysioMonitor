# -*- coding: utf-8 -*-
import argparse
import json
import logging
import sys
from datetime import datetime
from PyQt5.QtWidgets import QApplication
from GUI.GUI import PhysioMonitorMainScreen, StartDialog

parser = argparse.ArgumentParser()
parser.add_argument(
    "-c",
    "--config",
    help="path of the configuration file to use (required)",
    required=True,
)
parser.add_argument(
    "--log-level",
    help="level of information to log. "
    "Can be one of [DEBUG,INFO,WARNING,ERROR,CRITICAL]. "
    "Default is WARNING",
    default="WARNING",
)
parser.add_argument(
    "--logfile",
    help="file in which the log is written. "
    "If absent or None, log is directed to stdout",
    default=None,
)
args = parser.parse_args()

# see https://docs.python.org/3/howto/logging.html#logging-to-a-file
numeric_level = getattr(logging, args.log_level.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError(f"Invalid log_box level: {args.log_level}")
logger = logging.getLogger(__name__)
logging.basicConfig(level=numeric_level, filename=args.logfile, filemode="w")
logging.getLogger("PyQt5").setLevel(logging.INFO)  # turn off DEBUG messages from PyQT5

try:
    with open(args.config, "r", encoding="utf-8") as f:
        logger.info(f"Reading configuration from <{args.config}>")
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    parser.error("filed passed to --config is not a valid configuration file")

app = QApplication(sys.argv)
startDlg = StartDialog(config=config)
if startDlg.exec():
    config = startDlg.config
    physio_monitor = PhysioMonitorMainScreen(
        config, pump_serial_ports=startDlg.serialPorts, pumps=startDlg.pumps
    )
    if not startDlg.isResumed:
        physio_monitor.logBox.append(
            physio_monitor.logBox.get_header(
                subject=startDlg.subject, drug_list=startDlg.drugList
            )
        )
    else:
        with open(startDlg.log_path, "r", encoding="utf-8") as f:
            previous_content = f.read()
        physio_monitor.logBox.content = previous_content
        physio_monitor.logBox.widget.setPlainText(previous_content)
        physio_monitor.logBox.append(
            f'#### PhysioMonitor resumed {datetime.now().isoformat(timespec="minutes")}\n'
        )
    physio_monitor.show()
    physio_monitor.start()
    app.exec()
