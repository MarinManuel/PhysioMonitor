import datetime
import json
import logging
import os
import pygame
from PyQt5 import uic
from PyQt5.QtCore import QTimer, QSize, QRect, QModelIndex, QDate, QStringListModel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QCursor, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QDialog, QDoubleSpinBox, QLineEdit, QPushButton, \
    QHBoxLayout, QSpinBox, QDialogButtonBox, QGridLayout, QSizePolicy, \
    QRadioButton, QGroupBox, QStyle, QPlainTextEdit, QTabWidget, QScrollArea, QInputDialog, QFrame, QApplication, \
    QCheckBox, QProxyStyle, QHeaderView, QFileDialog, QComboBox, QDateEdit, QButtonGroup, QTextEdit, QTableView, \
    QMessageBox
from GUI.Models import DoubleSpinBoxDelegate, DrugTableModel
from GUI.scope import ScopeLayoutWidget, PagedScope
from monitor.Objects import Drug, Sex, Mouse, Experiment, Config

PREVIOUS_VALUES_FILE = 'prev_vals.jsom'

# if it hasn't been already, initialize the sound mixer
if pygame.mixer.get_init() is None:
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.mixer.init()

logger = logging.getLogger()


class IconProxyStyle(QProxyStyle):
    # from https://stackoverflow.com/questions/62172781/move-icon-to-right-side-of-text-in-a-qcheckbox/62174403#62174403
    # used to draw an icon on the right side of a QCheckBox
    # noinspection PyTypeChecker
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
    def getDrugVolume(parent, name, volume):
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
    def getDrugVolumeAndInject(parent, name, volume):
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


class DrugEditDialog(QDialog):
    def __init__(self, name="", dose=0.0, concentration=0.0, volume=0):
        super().__init__()
        uic.loadUi('./GUI/DrugEditDialog.ui', self)
        self.drugNameLineEdit.setText(name)
        self.drugDoseSpinBox.setValue(float(dose))
        self.drugConcentrationSpinBox.setValue(float(concentration))
        self.drugVolumeSpinBox.setValue(int(volume))

    @staticmethod
    def getDrugData(name="", dose=0.0, concentration=0.0, volume=0):
        dlg = DrugEditDialog(name, dose, concentration, volume)

        result = dlg.exec()
        name = dlg.drugNameLineEdit.text()
        dose = dlg.drugDoseSpinBox.value()
        concentration = dlg.drugConcentrationSpinBox.value()
        volume = dlg.drugVolumeSpinBox.value()
        return name, dose, concentration, volume, result == QDialog.Accepted


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

    # noinspection PyUnusedLocal
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

    # noinspection PyUnusedLocal
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

    # noinspection PyUnusedLocal
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

    # noinspection PyUnusedLocal
    def onFullDoseButtonClick(self, event):
        self.doInjectDrug(self._drugVolume)

    # noinspection PyUnusedLocal
    def onHalfDoseButtonClick(self, event):
        self.doInjectDrug(self._drugVolume / 2)

    # noinspection PyUnusedLocal
    def onCustomDoseButtonClick(self, event):
        val, ok = customDialog.getDouble(self, value=self._drugVolume, text="Enter custom amount (μL)")
        if ok:
            self.doInjectDrug(val)

    # noinspection PyUnusedLocal
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

    # noinspection PyUnusedLocal
    def onDrugLabelClick(self, event):
        drugName, drugVolume, ok = customDialog.getDrugVolume(self, self._drugName, self._drugVolume)
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
    def __init__(self, config):
        super().__init__()

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

        # self.__stream = SurgeryFileStreamer(nChan=len(config['comedi']['channels']), filename="./media/surgery.txt",
        #                                     pointsToReturn=None)
        # self.__stream.start()
        #
        # self.__refreshTimer = QTimer()
        # self.__refreshTimer.timeout.connect(self.update)
        # self.__refreshTimer.start(50)

    def update(self):
        data = self.__stream.read()
        self._graphLayout.append(data)

    def addNote(self):
        text, ok = QInputDialog.getText(self, 'Add a note to the log', 'Note:')
        if ok and len(text) > 0:
            currTime = datetime.datetime.now().strftime("%H:%M:%S")
            self.logBox.appendPlainText('{:s}\t{:s}'.format(currTime, text))

    def addNewDrug(self):
        name, volume, injected, ok = customDialog.getDrugVolumeAndInject(self, name="", volume=0)
        if ok:
            newPanel = drugPanel(None, drugName=name, drugVolume=volume, logWidget=self.logBox)
            self.drugPanelsLayout.addWidget(newPanel)
            if injected:
                newPanel.onFullDoseButtonClick(None)


class startDialog(QDialog):
    expInvestigatorComboBox: QComboBox
    mouseDoBBox: QDateEdit
    mouseSexButtonGroup: QButtonGroup
    mouseWeightSpinBox: QSpinBox
    mouseGenotypeComboBox: QComboBox
    mouseCommentsTextEdit: QTextEdit
    drugTable: QTableView
    editDrugButton: QPushButton
    addDrugButton: QPushButton
    delDrugButton: QPushButton
    configPathLineEdit: QLineEdit
    savePathLineEdit: QLineEdit

    def __init__(self, mouse=None, drugList=None, exp=None, config=None):
        super().__init__()
        uic.loadUi('./GUI/StartScreen.ui', self)

        self.buttonBox.button(QDialogButtonBox.Ok).setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton))
        self.buttonBox.button(QDialogButtonBox.Cancel).setIcon(
            QApplication.style().standardIcon(QStyle.SP_DialogCancelButton))

        # load previous values to pre-populate dialog
        try:
            with open(PREVIOUS_VALUES_FILE, 'r') as f:
                prev_values: dict = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            prev_values = {}
        if 'prevGen' not in prev_values.keys():
            prev_values['prevGen'] = []
        if 'prevDrugs' not in prev_values.keys():
            prev_values['prevDrugs'] = []
        if 'prevConfigFile' not in prev_values.keys():
            prev_values['prevConfigFile'] = ''
        if 'prevSavePath' not in prev_values.keys():
            prev_values['prevSavePath'] = ''
        temp = [Drug(name=drug['_name'],
                     dose=drug['_dose'],
                     concentration=drug['_concentration'],
                     volume=drug['_volume']) for drug in prev_values['prevDrugs']]
        prev_values['prevDrugs'] = temp

        if mouse is None:
            self.mouse = Mouse()
        else:
            self.mouse = mouse

        if drugList is None:
            self.drugList = prev_values['prevDrugs']
        else:
            self.drugList = drugList

        if exp is None:
            self.experiment = Experiment()
        else:
            self.experiment = exp

        if config is None:
            self.currConfig = Config(configFile=prev_values['prevConfigFile'], savePath=prev_values['prevSavePath'])
        else:
            self.currConfig = config
        if os.path.isfile(prev_values['prevConfigFile']):
            with open(prev_values['prevConfigFile'], 'r') as f:
                self.config = json.load(f)

        self.saveFolder = os.path.join(self.currConfig.savePath, datetime.date.today().isoformat())
        self.logFile = os.path.join(self.saveFolder, self.config['log-filename'])

        if os.path.isfile(self.logFile):
            # we already have a log file in the folder, ask whether to resume
            dlg = QMessageBox()
            dlg.setWindowTitle('Previous session detected')
            dlg.setIcon(QMessageBox.Question)
            dlg.setText("The folder already contains a log file.")
            dlg.setInformativeText('Do you want to resume the previous session?')
            dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            ok = dlg.exec()
            if ok == QMessageBox.Yes:
                self.parseLog(self.logFile)

        # MOUSE TAB
        # noinspection PyTypeChecker
        for but, butId in zip(self.mouseSexButtonGroup.buttons(), Sex):
            self.mouseSexButtonGroup.setId(but, butId)
        self.mouseDoBBox.setDate(QDate(self.mouse.dob.year, self.mouse.dob.month, self.mouse.dob.day))
        self.mouseSexButtonGroup.button(self.mouse.sex).setChecked(True)
        self.mouseWeightSpinBox.setValue(self.mouse.weight)
        self.mouseGenotypeComboBox.setModel(QStringListModel())
        self.mouseGenotypeComboBox.addItems(prev_values['prevGen'])
        existsId = self.mouseGenotypeComboBox.findText(self.mouse.genotype)
        if existsId >= 0:
            self.mouseGenotypeComboBox.removeItem(existsId)
        self.mouseGenotypeComboBox.insertItem(-1, self.mouse.genotype)
        self.mouseGenotypeComboBox.setCurrentIndex(0)
        self.mouseCommentsTextEdit.setText(self.mouse.comments)

        # DRUG LIST TAB
        self.tableModel = DrugTableModel(self.drugList)
        self.drugTable.setModel(self.tableModel)
        for i in range(1, self.tableModel.columnCount()):
            self.drugTable.setItemDelegateForColumn(i, DoubleSpinBoxDelegate(self))
        self.editDrugButton.clicked.connect(self.editEntry)
        self.addDrugButton.clicked.connect(self.addEntry)
        self.delDrugButton.clicked.connect(self.removeEntry)
        for i in range(1, self.tableModel.columnCount()):
            self.drugTable.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.drugTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        # CONFIG TAB
        self.configPathLineEdit.setText(self.currConfig.configFile)
        self.savePathLineEdit.setText(self.currConfig.savePath)
        self.configPathBrowseButton.clicked.connect(self.browseConfigFile)
        self.savePathBrowseButton.clicked.connect(self.browseSavePath)

    def addEntry(self):
        name, dose, concentration, volume, ok = DrugEditDialog.getDrugData()
        if ok:
            newDrug = Drug(name=name, dose=dose, concentration=concentration, volume=volume)
            newRow = self.tableModel.rowCount()
            self.tableModel.insertRows(newRow)

            for i, field in enumerate(self.tableModel.FIELDS):
                newRow = self.tableModel.rowCount() - 1
                ix = self.tableModel.index(newRow, i, QModelIndex())
                self.tableModel.setData(ix, getattr(newDrug, field), Qt.EditRole)

    def editEntry(self):
        selectionModel = self.drugTable.selectionModel()
        indexes = selectionModel.selectedRows()

        for index in indexes:
            row = index.row()
            drugData = []
            for i in range(self.tableModel.columnCount()):
                ix = self.tableModel.index(row, i, QModelIndex())
                drugData.append(self.tableModel.data(ix, Qt.EditRole))
            name, dose, concentration, volume, ok = DrugEditDialog.getDrugData(*drugData)
            if ok:
                for j, field in enumerate([name, dose, concentration, volume]):
                    ix = self.tableModel.index(row, j, QModelIndex())
                    self.tableModel.setData(ix, field, Qt.EditRole)

    def removeEntry(self):
        selectionModel = self.drugTable.selectionModel()
        indexes = selectionModel.selectedRows()

        for index in indexes:
            self.drugTable.model().removeRows(index.row(), count=1)

    # noinspection PyUnusedLocal
    def browseConfigFile(self, event):
        root = self.configPathLineEdit.text()
        if not os.path.exists(root):
            root = os.getcwd()
        fileName, _ = QFileDialog.getOpenFileName(self, 'Open config file', root, "Configuration file (*.json)")
        if len(fileName) > 0:
            self.configPathLineEdit.setText(fileName)

    # noinspection PyUnusedLocal
    def browseSavePath(self, event):
        root = self.savePathLineEdit.text()
        if not os.path.exists(root):
            root = os.getcwd()
        path = QFileDialog.getExistingDirectory(self, 'Select folder', root, QFileDialog.ShowDirsOnly)
        if len(path) > 0:
            self.savePathLineEdit.setText(path)

    def accept(self) -> None:
        # save the lists genotypes/investigators/drugs upon accepting
        # so they can be reloaded next time
        out = {'prevGen': self.mouseGenotypeComboBox.model().stringList(),
               'prevDrugs': [drug.__dict__ for drug in self.drugList],
               'prevConfigFile': self.configPathLineEdit.text(),
               'prevSavePath': self.savePathLineEdit.text()}
        with open(PREVIOUS_VALUES_FILE, 'w') as f:
            json.dump(out, f)
        super().accept()

    def parseLog(self, filename):
        pass
