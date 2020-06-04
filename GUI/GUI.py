import datetime
import json
import logging
import os

import pygame
from PyQt5 import uic
from PyQt5.QtCore import QTimer, QSize, QRect, QModelIndex
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QCursor, QFont, QStandardItem
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QDialog, QDoubleSpinBox, QLineEdit, QPushButton, \
    QHBoxLayout, QSpinBox, QDialogButtonBox, QGridLayout, QSizePolicy, \
    QRadioButton, QGroupBox, QStyle, QPlainTextEdit, QTabWidget, QScrollArea, QInputDialog, QFrame, QApplication, \
    QCheckBox, QProxyStyle

from GUI.objects import DrugTableModel, Drug
from GUI.scope import ScopeLayoutWidget, PagedScope
from monitor.sampling import SurgeryFileStreamer

# if it hasn't been already, initialize the sound mixer
if pygame.mixer.get_init() is None:
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.mixer.init()

logger = logging.getLogger()


# noinspection PyTypeChecker
class IconProxyStyle(QProxyStyle):
    # from https://stackoverflow.com/questions/62172781/move-icon-to-right-side-of-text-in-a-qcheckbox/62174403#62174403
    # used to draw an icon on the right side of a QCheckBox
    def drawControl(self, element, option, painter, widget=None):
        if element == QStyle.CE_CheckBoxLabel:
            offset = 4
            icon = QIcon(option.icon)
            option.icon = QIcon()

            super().drawControl(element, option, painter, widget)

            alignment = self.visualAlignment(
                option.direction, Qt.AlignLeft | Qt.AlignVCenter
            )
            if not self.proxy().styleHint(QStyle.SH_UnderlineShortcut, option, widget):
                alignment |= Qt.TextHideMnemonic
            r = painter.boundingRect(
                option.rect, alignment | Qt.TextShowMnemonic, option.text
            )

            option.rect.setLeft(r.right() + offset)
            option.text = ""
            option.icon = icon

        super().drawControl(element, option, painter, widget)


# noinspection PyUnusedLocal
class clockWidget(QWidget):
    def __init__(self, showDate=True, timeSize=30, dateSize=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TIME_FORMAT = "%H:%M"
        self.DATE_FORMAT = "%x"

        self._timer = QTimer(self)
        # noinspection PyUnresolvedReferences
        self._timer.timeout.connect(self.onTimeEvent)
        self._timer.start(250)
        self._vbox = QVBoxLayout(self)
        self._vbox.setAlignment(Qt.AlignCenter)

        self._timeLabel = QLabel(self)
        f = QFont()
        f.setBold(True)
        f.setPointSize(timeSize)
        self._timeLabel.setFont(f)
        self._timeLabel.setText(datetime.datetime.now().strftime(self.TIME_FORMAT))

        self._dateLabel = QLabel(self)
        f.setBold(False)
        f.setPointSize(dateSize)
        self._dateLabel.setFont(f)
        self._dateLabel.setText(datetime.datetime.now().strftime(self.DATE_FORMAT))

        self._vbox.addStretch(1)
        self._vbox.addWidget(self._timeLabel, 0, Qt.AlignCenter)
        if showDate:
            self._vbox.addWidget(self._dateLabel, 0, Qt.AlignCenter)
        self._vbox.addStretch(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def onTimeEvent(self):
        self._timeLabel.setText(datetime.datetime.now().strftime(self.TIME_FORMAT))
        self._dateLabel.setText(datetime.datetime.now().strftime(self.DATE_FORMAT))


class customDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton))
        self.buttonBox.button(QDialogButtonBox.Ok).setIcon(
            QApplication.style().standardIcon(QStyle.SP_DialogCancelButton))
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def showEvent(self, event):
        super().showEvent(event)
        self.setFixedSize(self.size())

        # move the dialog to the cursor position
        cursor_pos = QCursor().pos()
        orig_rect = self.frameGeometry()
        new_rect = QRect(orig_rect)
        new_rect.moveTopLeft(cursor_pos)

        screen_rect = QApplication.primaryScreen().geometry()
        if not screen_rect.contains(new_rect):
            # the dialog is off screen,
            new_rect.moveBottomLeft(cursor_pos)

        self.setGeometry(new_rect)

    @staticmethod
    def getDouble(parent, value=0.0, minVal=0.0, maxVal=float('inf'), units=None, text=None, title="Enter a value"):
        dlg = customDialog()

        spinBox = QDoubleSpinBox(parent)
        spinBox.setMinimum(minVal)
        spinBox.setMaximum(maxVal)
        spinBox.setValue(value)
        spinBox.setMinimumWidth(50)
        spinBox.setAlignment(Qt.AlignRight)
        if units is not None:
            spinBox.setSuffix(' ' + units)

        dlg.layout.insertWidget(0, spinBox)
        if text is not None:
            txt = QLabel(text)
            dlg.layout.insertWidget(0, txt)
        dlg.setWindowTitle(title)

        lineEdit = spinBox.findChild(QLineEdit, 'qt_spinbox_lineedit')
        lineEdit.selectAll()
        spinBox.setFocus()

        result = dlg.exec()
        val = spinBox.value()
        return val, result == QDialog.Accepted

    @staticmethod
    def getTime(parent, value=0, text='Time before alarm', title='Enter the amount of time'):
        # noinspection PyUnusedLocal
        def onRadioClick(event):
            if m30Button.isChecked() or m10Button.isChecked():
                timeBox.setEnabled(False)
            else:
                timeBox.setEnabled(True)
                lineEdit = timeBox.findChild(QLineEdit, 'qt_spinbox_lineedit')
                lineEdit.selectAll()
                timeBox.setFocus()

        dlg = customDialog(parent)
        dlg.setWindowTitle(title)

        label = QLabel(text)
        m30Button = QRadioButton("30 min")
        m10Button = QRadioButton("10 min")
        customButton = QRadioButton("Custom:")
        timeBox = QSpinBox()
        timeBox.setMinimum(1)
        timeBox.setMaximum(2147483647)
        timeBox.setSuffix(' min')
        if value == 30:
            m30Button.setChecked(True)
        elif value == 10:
            m10Button.setChecked(True)
        else:
            customButton.setChecked(True)
        timeBox.setValue(1 if value is None else value)
        onRadioClick(None)

        m30Button.toggled.connect(onRadioClick)
        m10Button.toggled.connect(onRadioClick)
        customButton.toggled.connect(onRadioClick)

        layout = QGridLayout()
        layout.addWidget(label, 0, 0, 1, 2)
        layout.addWidget(m30Button, 1, 0, 1, 2)
        layout.addWidget(m10Button, 2, 0, 1, 2)
        layout.addWidget(customButton, 3, 0)
        layout.addWidget(timeBox, 3, 1)

        dlg.layout.insertLayout(0, layout)
        result = dlg.exec()
        if m30Button.isChecked():
            val = 30
        elif m10Button.isChecked():
            val = 10
        else:
            val = timeBox.value()
        return val, result == QDialog.Accepted

    @staticmethod
    def getDrug(parent, name, volume):
        dlg = customDialog(parent)
        dlg.setWindowTitle("Enter drug information")

        drugNameLabel = QLabel("Drug name:")
        drugNameInput = QLineEdit()
        drugNameInput.setText(name)
        drugVolumeLabel = QLabel("Volume:")
        drugVolumeInput = QSpinBox()
        drugVolumeInput.setValue(volume if volume > 1 else 1)
        drugVolumeInput.setMinimum(1)
        drugVolumeInput.setMaximum(2147483647)
        drugVolumeInput.setAlignment(Qt.AlignRight)
        drugVolumeInput.setSuffix(' μL')

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(0)
        layout.addWidget(drugNameLabel, 0, 0)
        layout.addWidget(drugVolumeLabel, 0, 1)
        layout.addWidget(drugNameInput, 1, 0)
        layout.addWidget(drugVolumeInput, 1, 1)

        dlg.layout.insertLayout(0, layout)
        result = dlg.exec()
        name = drugNameInput.text()
        volume = drugVolumeInput.value()
        return name, volume, result == QDialog.Accepted

    @staticmethod
    def getDrugInject(parent, name, volume):
        dlg = customDialog(parent)
        dlg.setWindowTitle("Enter drug information")

        drugNameLabel = QLabel("Drug name:")
        drugNameInput = QLineEdit()
        drugNameInput.setText(name)
        drugVolumeLabel = QLabel("Volume (μL):")
        drugVolumeInput = QSpinBox()
        drugVolumeInput.setValue(volume if volume > 1 else 1)
        drugVolumeInput.setMinimum(1)
        drugVolumeInput.setMaximum(2147483647)
        drugVolumeInput.setAlignment(Qt.AlignRight)
        drugVolumeInput.setSuffix(' μL')
        injectCheckBox = QCheckBox("Drug was injected")
        injectCheckBox.setChecked(True)

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(0)
        layout.addWidget(drugNameLabel, 0, 0)
        layout.addWidget(drugVolumeLabel, 0, 1)
        layout.addWidget(drugNameInput, 1, 0)
        layout.addWidget(drugVolumeInput, 1, 1)
        layout.addWidget(injectCheckBox, 2, 0, 1, 2)

        dlg.layout.insertLayout(0, layout)
        result = dlg.exec()
        name = drugNameInput.text()
        volume = drugVolumeInput.value()
        injected = injectCheckBox.isChecked()
        return name, volume, injected, result == QDialog.Accepted


# noinspection PyUnusedLocal
class drugTimer(QLabel):
    def __init__(self, parent, alarmThresh=None, alarmSoundFile=None):
        super().__init__(parent)
        self._duration = datetime.timedelta()
        self._startTime = None
        self.__FORMAT = """<p>
        <span style="font-family: monospace; font-size:24pt; font-weight:bold">{:02.0f}:{:02.0f}</span>
        <span style="font-family: monospace; font-size:10pt; font-weight:normal;">:{:02.0f}</span>
        </p>"""
        self.__FORMAT_COLOR_NORMAL = 'black'
        self.__FORMAT_COLOR_ALARM = 'red'
        self.__FORMAT_STYLESHEET = 'color: {:s}'
        self.setStyleSheet(self.__FORMAT_STYLESHEET.format(self.__FORMAT_COLOR_NORMAL))
        self.updateText()
        self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self._clockTimer = QTimer(self)
        self._clockTimer_PERIOD = 100  # ms
        self._alarmThresh = alarmThresh
        self._alarmTimer = QTimer(self)
        self._alarmTimer_PERIOD = 500  # ms
        self._alarmTimerCount = 0
        self._alarmTimerMaxCount = 10
        self._isAlarmTimerPastMaxDuration = False
        self._alarmTimer.timerEvent = self.onAlarmTimer
        self._clockTimer.timerEvent = self.onClockTimer
        self.mouseDoubleClickEvent = self.reset
        self._alarmSound = None
        if alarmSoundFile is not None and os.path.isfile(alarmSoundFile):
            self._alarmSound = pygame.mixer.Sound(alarmSoundFile)

    def start(self):
        self._startTime = datetime.datetime.today()
        self._clockTimer.start(self._clockTimer_PERIOD)

    def updateText(self):
        hrs = self._duration.seconds // (60 * 60)
        r = self._duration.seconds - hrs * 60 * 60
        mins = r // 60
        secs = r - mins * 60
        self.setText(self.__FORMAT.format(hrs, mins, secs))

    def reset(self, event):
        if self._clockTimer.isActive():  # timer is going
            self._clockTimer.stop()
            self._duration = datetime.timedelta()  # reset duration to 0
            self.updateText()
            if self._alarmTimer.isActive():
                self._alarmTimer.stop()
            self.setStyleSheet(self.__FORMAT_STYLESHEET.format(self.__FORMAT_COLOR_NORMAL))
            self._isAlarmTimerPastMaxDuration = False
            if self._alarmSound is not None:
                self._alarmSound.stop()

    def onClockTimer(self, event):
        self._duration = datetime.datetime.today() - self._startTime
        self.updateText()
        if self._alarmThresh is not None \
                and self._duration.seconds > self._alarmThresh \
                and not self._isAlarmTimerPastMaxDuration:
            if not self._alarmTimer.isActive():
                self.onAlarmTimer(None)
                self._alarmTimer.start(self._alarmTimer_PERIOD)
                if self._alarmSound is not None:
                    self._alarmSound.play(-1)

    def setAlarmThreshInMins(self, durInMins):
        if durInMins is not None:
            self._alarmThresh = durInMins * 60
        else:
            self._alarmThresh = None

    def onAlarmTimer(self, event):
        self.setStyleSheet(self.__FORMAT_STYLESHEET.format(
            self.__FORMAT_COLOR_ALARM if self._alarmTimerCount % 2 == 0 else self.__FORMAT_COLOR_NORMAL))
        self._alarmTimerCount += 1
        if self._alarmTimer.isActive() and self._alarmTimerCount > self._alarmTimerMaxCount:
            self.onAlarmPastMaxDuration()

    def onAlarmPastMaxDuration(self):
        self._isAlarmTimerPastMaxDuration = True
        self._alarmTimer.stop()
        self._alarmTimerCount = 0
        self.setStyleSheet(self.__FORMAT_STYLESHEET.format(self.__FORMAT_COLOR_ALARM))
        if self._alarmSound is not None:
            self._alarmSound.stop()

    @property
    def alarmThreshold(self):
        return self._alarmThresh


# noinspection PyUnusedLocal
class drugPanel(QGroupBox):
    def __init__(self, parent, drugName, drugVolume, alarmSoundFile=None, logWidget=None):
        super().__init__(parent)
        self._LABEL_FORMAT = "{drugName} ({drugVolume:.0f} μL)"
        self.setStyleSheet("""
        QGroupBox {
            margin-top: 1.5em; /* leave space at the top for the title */
            font-size: large;
            font-weight: bold;
        }
        
        QGroupBox::title {
            bottom: 1em;
        }
        """)
        self._ALARM_LABEL_ON = "Alarm\n({:.0f} min)"
        self._ALARM_LABEL_OFF = "Alarm\n(...)"
        self._drugName = drugName
        self._drugVolume = drugVolume
        self._injTime = None
        self._logWidget = logWidget
        self._LOG_FORMAT = "{time}\t{drugName} ({drugVolume} μL)"
        if alarmSoundFile is not None and os.path.isfile(alarmSoundFile):
            self._alarmSound = pygame.mixer.Sound(alarmSoundFile)
        else:
            self._alarmSound = None

        self.setTitle(self._LABEL_FORMAT.format(drugName=self._drugName, drugVolume=self._drugVolume))
        self.mouseDoubleClickEvent = self.onDrugLabelClick

        self._fullDoseButton = QPushButton(self)
        self._fullDoseButton.setText('Full dose')
        self._halfDoseButton = QPushButton(self)
        self._halfDoseButton.setText('1/2 dose')
        self._customDoseButton = QPushButton(self)
        self._customDoseButton.setText('...')
        self._fullDoseButton.clicked.connect(self.onFullDoseButtonClick)
        self._halfDoseButton.clicked.connect(self.onHalfDoseButtonClick)
        self._customDoseButton.clicked.connect(self.onCustomDoseButtonClick)

        self._timer = drugTimer(self, alarmSoundFile=alarmSoundFile)

        self._enableAlarmButton = QPushButton(self._ALARM_LABEL_OFF, self)
        self._enableAlarmButton.setCheckable(True)
        self._enableAlarmButton.setFlat(True)
        ico = QIcon()
        ico.addFile("./media/alarm-clock-OFF.png", state=QIcon.Off)
        ico.addFile("./media/alarm-clock-ON.png", state=QIcon.On)
        self._enableAlarmButton.setIcon(ico)
        self._enableAlarmButton.setIconSize(QSize(25, 25))
        self._enableAlarmButton.clicked.connect(self.onChoiceAlarm)

        box = QGridLayout()
        box.setSpacing(0)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self._fullDoseButton, 0, 0)
        box.addWidget(self._halfDoseButton, 0, 1)
        box.addWidget(self._customDoseButton, 0, 2)
        box.addWidget(self._timer, 1, 0)
        box.addWidget(self._enableAlarmButton, 1, 1, 1, 2)
        self.setLayout(box)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def doInjectDrug(self, volume):
        currTime = datetime.datetime.now().strftime("%H:%M:%S")
        output = self._LOG_FORMAT.format(time=currTime, drugName=self._drugName, drugVolume=volume)
        if self._logWidget is not None:
            self._logWidget.appendPlainText(output)
        else:
            print(output)
        self._timer.start()

    def onFullDoseButtonClick(self, event):
        self.doInjectDrug(self._drugVolume)

    def onHalfDoseButtonClick(self, event):
        self.doInjectDrug(self._drugVolume / 2)

    def onCustomDoseButtonClick(self, event):
        val, ok = customDialog.getDouble(self, value=self._drugVolume, text="Enter custom amount (μL)")
        if ok:
            self.doInjectDrug(val)

    def onChoiceAlarm(self, event):
        if self._enableAlarmButton.isChecked():
            val, ok = customDialog.getTime(self, value=self._timer.alarmThreshold,
                                           text='Time before alarm')
            if ok:
                self._timer.setAlarmThreshInMins(val)
                self._enableAlarmButton.setText(self._ALARM_LABEL_ON.format(val))
            else:
                self._enableAlarmButton.setChecked(False)
        else:
            self._timer.setAlarmThreshInMins(None)
            self._enableAlarmButton.setText(self._ALARM_LABEL_OFF)

    def onDrugLabelClick(self, event):
        drugName, drugVolume, ok = customDialog.getDrug(self, self._drugName, self._drugVolume)
        if ok:
            self._drugName = drugName
            self._drugVolume = drugVolume
            self.setTitle(self._LABEL_FORMAT.format(drugName=self._drugName, drugVolume=self._drugVolume))


class drugPumpPanel(drugPanel):
    def __init__(self, parent, drugName, drugVolume, alarmSoundFile=None, logWidget=None):
        super().__init__(parent, drugName, drugVolume, alarmSoundFile, logWidget)
        self.setStyleSheet(self.styleSheet() + """
            QGroupBox {
                background-color: #C1C9E2;
            }
            """)
        self._autoInjectCheckBox = QCheckBox("Auto-inject")
        self._autoInjectCheckBox.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self._autoInjectCheckBox.setStyle(IconProxyStyle(self._autoInjectCheckBox.style()))
        self.layout().addWidget(self._autoInjectCheckBox)

    def showEvent(self, event):
        super().showEvent(event)
        # this code adds an icon to the button to distinguish them from the "manual" drug panel buttons
        # unfortunately, that increases their size and messes up the layout.
        # so we're saving their size before the icon, and restoring the original size after inserting the icon
        full_size = self._fullDoseButton.size()
        half_size = self._halfDoseButton.size()
        self._fullDoseButton.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self._fullDoseButton.setFixedSize(full_size)
        self._halfDoseButton.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self._halfDoseButton.setFixedSize(half_size)


class PhysioMonitorMainScreen(QFrame):
    def __init__(self):
        super().__init__()

        with open('./PhysioMonitor.json', 'r') as config_file:
            config = json.load(config_file)

        # LOG BOX
        self.logBox = QPlainTextEdit()
        self.logBox.setLineWrapMode(False)
        self.logBox.setStyleSheet("font-family: monospace;")

        layout00 = QHBoxLayout()
        layout10 = QVBoxLayout()

        # Create some widgets to be placed inside
        clock = clockWidget()
        panel1 = drugPumpPanel(None, "test drug", 10.0, alarmSoundFile='./media/beep3x6.wav', logWidget=self.logBox)
        panel2 = drugPanel(None, "test drug 2", 20.0, alarmSoundFile='./media/beep3x6.wav', logWidget=self.logBox)

        self._graphLayout = ScopeLayoutWidget()

        notebook = QTabWidget()
        notebook.addTab(self._graphLayout, "Graphs")
        notebook.addTab(self.logBox, "Log")

        layout10.addWidget(clock, stretch=0)
        scrollarea = QScrollArea()
        scrollarea.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.MinimumExpanding)
        scrollarea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scrollarea.setWidgetResizable(True)
        widget = QWidget()
        scrollarea.setWidget(widget)
        self.drugPanelsLayout = QVBoxLayout()
        self.drugPanelsLayout.setContentsMargins(0, 0, 0, 0)
        self.drugPanelsLayout.setSpacing(0)
        self.drugPanelsLayout.addWidget(panel1)
        self.drugPanelsLayout.addWidget(panel2)
        for i in range(2, 3):
            panel = drugPanel(None, f"test drug {i + 1}", 20.0, alarmSoundFile='./media/beep3x6.wav',
                              logWidget=self.logBox)
            self.drugPanelsLayout.addWidget(panel)
        self.drugPanelsLayout.setAlignment(Qt.AlignTop)
        widget.setLayout(self.drugPanelsLayout)
        layout10.addWidget(scrollarea)

        self.newDrugButton = QPushButton("Other drug")
        self.newDrugButton.clicked.connect(self.addNewDrug)

        self.addNoteButton = QPushButton("Add note")
        self.addNoteButton.clicked.connect(self.addNote)
        layout11 = QHBoxLayout()
        layout11.addWidget(self.newDrugButton)
        layout11.addWidget(self.addNoteButton)
        layout10.addLayout(layout11)

        layout00.addLayout(layout10, stretch=0)
        layout00.addWidget(notebook, stretch=1)

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
            self._graphLayout.addItem(plot, i, 1)

        self.setLayout(layout00)

        self.__stream = SurgeryFileStreamer(nChan=len(config['comedi']['channels']), filename="./media/surgery.txt",
                                            pointsToReturn=None)
        self.__stream.start()

        self.__refreshTimer = QTimer()
        self.__refreshTimer.timeout.connect(self.update)
        self.__refreshTimer.start(50)

    def update(self):
        data = self.__stream.read()
        self._graphLayout.append(data)

    def addNote(self):
        text, ok = QInputDialog.getText(self, 'Add a note to the log', 'Note:')
        if ok and len(text) > 0:
            currTime = datetime.datetime.now().strftime("%H:%M:%S")
            self.logBox.appendPlainText('{:s}\t{:s}'.format(currTime, text))

    def addNewDrug(self):
        name, volume, injected, ok = customDialog.getDrugInject(self, name="", volume=0)
        if ok:
            newPanel = drugPanel(None, drugName=name, drugVolume=volume, logWidget=self.logBox)
            self.drugPanelsLayout.addWidget(newPanel)
            if injected:
                newPanel.onFullDoseButtonClick(None)


class startDialog(QDialog):
    def __init__(self, mouse, drugList, exp, config):
        super().__init__()
        self._drugList = drugList

        uic.loadUi('./GUI/StartScreen.ui', self)

        self.buttonBox.button(QDialogButtonBox.Ok).setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton))
        self.buttonBox.button(QDialogButtonBox.Cancel).setIcon(
            QApplication.style().standardIcon(QStyle.SP_DialogCancelButton))

        self.drugTable.setModel(DrugTableModel(self._drugList))
        self.addDrugButton.clicked.connect(self.addDrug)

    def addDrug(self):
        name, volume, ok = customDialog.getDrug(self, name="", volume=0)
        if ok:
            newDrug = Drug(name=name, volume=volume)
            self.drugTable.model().addDrug(newDrug)
