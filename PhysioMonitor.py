import logging
import sys

from PyQt5.QtWidgets import QApplication

from GUI.GUI import PhysioMonitorMainScreen, startDialog
from GUI.objects import Drug
import numpy as np

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

N = 5
drugList = [Drug(name=f'Drug #{i}', volume=j, concentration=k, dose=l) for i, j, k, l in zip(range(N),
                                                                                             np.random.random(N),
                                                                                             np.random.random(N),
                                                                                             np.random.random(N))]

app = QApplication(sys.argv)

scr = PhysioMonitorMainScreen()
scr.setEnabled(False)
scr.show()

# prev_lvl = logger.level
# logger.setLevel(logging.INFO)
startDlg = startDialog(mouse=None, drugList=drugList, exp=None, config=None)
# logger.setLevel(prev_lvl)
startDlg.show()

app.exec()
