import logging
import sys

import serial
from PyQt5.QtWidgets import QApplication, QFrame

from GUI.GUI import SyringePumpPanel
from pumps.SyringePumps import DummyPump, AladdinPump, SyringePumpException

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG, filename=None, filemode="w")
logging.getLogger("PyQt5").setLevel(logging.INFO)  # turn off DEBUG messages from PyQT5

app = QApplication(sys.argv)


b = serial.Serial(port="/dev/ttyUSB1", baudrate=19200)
for _ in range(3):
    try:
        a = AladdinPump(serial_port=b, display_name="Pump #A")
        break
    except SyringePumpException:
        a = None


s = SyringePumpPanel(pump=a)
s.show()
sys.exit(app.exec_())
