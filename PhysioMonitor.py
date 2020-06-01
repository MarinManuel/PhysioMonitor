import pyqtgraph as pg
import logging
import json

from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLineEdit, QListWidget, QTabWidget, QGridLayout, \
    QHBoxLayout, QVBoxLayout, QScrollArea, QSizePolicy

from GUI.main import clockWidget, drugPumpPanel, drugPanel
from GUI.scope import ScopeLayoutWidget, PagedScope
from monitor.sampling import SurgeryFileStreamer

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

with open('./PhysioMonitor.json', 'r') as config_file:
    config = json.load(config_file)

# Always start by initializing Qt (only once per application)
app = QApplication([])

# Define a top-level widget to hold everything
layout00 = QHBoxLayout()
layout10 = QVBoxLayout()

# Create some widgets to be placed inside
clock = clockWidget()
panel1 = drugPumpPanel(None, "test drug", 10.0, alarmSoundFile='./media/beep3x6.wav')
panel2 = drugPanel(None, "test drug 2", 20.0, alarmSoundFile='./media/beep3x6.wav')

graphLayout = ScopeLayoutWidget()

notebook = QTabWidget()
notebook.addTab(graphLayout, "Graphs")
notebook.addTab(QWidget(), "Log")

layout10.addWidget(clock, stretch=0)
scrollarea = QScrollArea()
scrollarea.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
layout20 = QVBoxLayout()
for i in range(2):
    panel = drugPanel(None, f"test drug {i+1}", 20.0, alarmSoundFile='./media/beep3x6.wav')
    layout20.addWidget(panel)
layout20.addStretch(1)
scrollarea.setLayout(layout20)
layout10.addWidget(scrollarea)

layout00.addLayout(layout10, stretch=0)
layout00.addWidget(notebook)


for i, chan in enumerate(config['comedi']['channels']):
    plot = PagedScope(
        sampleFreq=config['comedi']['sample-rate'],
        windowSize=chan['window-size'],
        linecolor=chan['line-color'],
        linewidth=chan['line-width'],
        scaling=chan['scale'],
        offset=chan['offset'],
        title=chan['label'],
        units=chan['units'],
        autoscale=chan['autoscale'],
        ymin=chan['ymin'],
        ymax=chan['ymax'],
        remanence=chan['remanence'],
        trigMode=chan['trigger-mode'],
        trigLevel=chan['trigger-level'],
        autoTrigLevel=chan['auto-trigger-level'],
        trendWindowSize=chan['trend-window-size'],
        trendPeriod=chan["trend-period"],
        trendFunction=chan["trend-function"],
        trendFuncKwargs=chan["trend-function-args"],
        trendUnits=chan["trend-units"],
        trendAutoscale=chan["trend-autoscale"],
        trendYmin=chan["trend-ymin"],
        trendYmax=chan["trend-ymax"],
        alarmEnabled=chan['alarm-enabled'],
        alarmLow=chan['alarm-low'],
        alarmHigh=chan['alarm-high'],
        alarmSoundFile=chan['alarm-sound-file']
    )
    graphLayout.addItem(plot, i, 1)


w = QWidget()
w.setLayout(layout00)
w.show()

a = SurgeryFileStreamer(nChan=len(config['comedi']['channels']), filename="./media/surgery.txt", pointsToReturn=None)
# a = SurgeryFileStreamer(config=config)
a.start()


def update():
    global graphLayout
    data = a.read()
    graphLayout.append(data)


timer = pg.QtCore.QTimer()
# noinspection PyUnresolvedReferences
timer.timeout.connect(update)
timer.start(50)
# noinspection PyUnresolvedReferences
# btn.clicked.connect(update)

# Start the Qt event loop
app.exec_()
