# -*- coding: utf-8 -*-
import datetime
import json
import logging
import os
import threading
import time

import pygame
import serial
from PyQt5 import uic
from PyQt5.QtCore import QTimer, QSize, QRect, QModelIndex, QDate, QStringListModel
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QCursor, QFont, QFontDatabase, QCloseEvent
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QDialog, QDoubleSpinBox, QLineEdit, QPushButton, \
    QHBoxLayout, QSpinBox, QDialogButtonBox, QGridLayout, QSizePolicy, \
    QRadioButton, QGroupBox, QStyle, QPlainTextEdit, QTabWidget, QScrollArea, QInputDialog, QFrame, QApplication, \
    QCheckBox, QProxyStyle, QHeaderView, QFileDialog, QComboBox, QDateEdit, QButtonGroup, QTextEdit, QTableView, \
    QMessageBox

from GUI.Models import DoubleSpinBoxDelegate, DrugTableModel
from GUI.scope import ScopeLayoutWidget, PagedScope
from monitor import SyringePumps
# from monitor.ComediObjects import ComediStreamer
from monitor.Objects import Drug, Sex, Mouse, LogFile
from monitor.SyringePumps import SyringePumpException, AVAIL_PUMPS
from monitor.sampling import AVAIL_ACQ_MODULES

PREVIOUS_VALUES_FILE = 'prev_vals.json'

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


class ClockWidget(QWidget):
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


class CustomDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton))
        self.buttonBox.button(QDialogButtonBox.Cancel).setIcon(
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
        dlg = CustomDialog()

        spinBox = QDoubleSpinBox(parent)
        spinBox.setDecimals(3)
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

        dlg = CustomDialog(parent)
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
    def getDrugVolume(parent, name, volume, addInject=False):
        dlg = CustomDialog(parent)
        dlg.setWindowTitle("Enter drug information")

        drugNameLabel = QLabel("Drug name:")
        drugNameInput = QLineEdit()
        drugNameInput.setText(name)
        drugVolumeLabel = QLabel("Volume:")
        drugVolumeInput = QSpinBox()
        drugVolumeInput.setMinimum(1)
        drugVolumeInput.setMaximum(2147483647)
        drugVolumeInput.setValue(volume)
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
        if addInject:
            addInjectButton = QPushButton("Add and inject")
            addInjectButton.setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton))
            addInjectButton.setDefault(True)
            addInjectButton.clicked.connect(lambda: dlg.done(QDialogButtonBox.YesToAll))
            dlg.buttonBox.addButton(addInjectButton, QDialogButtonBox.ActionRole)
            dlg.buttonBox.button(QDialogButtonBox.Ok).setText("Add to panel")

        dlg.layout.insertLayout(0, layout)
        result = dlg.exec()
        name = drugNameInput.text()
        volume = drugVolumeInput.value()
        return name, volume, result


class DrugEditDialog(QDialog):
    drugNameLineEdit: QLineEdit
    drugDoseSpinBox: QDoubleSpinBox
    drugConcentrationSpinBox: QDoubleSpinBox
    drugVolumeSpinBox: QSpinBox
    usePumpCheckBox: QCheckBox
    pumpIdSpinBox: QSpinBox

    def __init__(self, name="", dose=0.0, concentration=0.0, volume=0, pump=None):
        super().__init__()
        uic.loadUi('./GUI/DrugEditDialog.ui', self)
        self.drugNameLineEdit.setText(name)
        self.drugDoseSpinBox.setValue(float(dose))
        self.drugConcentrationSpinBox.setValue(float(concentration))
        self.drugVolumeSpinBox.setValue(int(volume))
        self.usePumpCheckBox.toggled.connect(self.usePumpToggled)
        if pump is None:
            self.usePumpCheckBox.setChecked(False)
        else:
            self.usePumpCheckBox.setChecked(True)
            self.pumpIdSpinBox.setValue(pump)

    def usePumpToggled(self, state):
        self.pumpIdSpinBox.setEnabled(state)

    @staticmethod
    def getDrugData(name="", dose=0.0, concentration=0.0, volume=0, pump=None):
        dlg = DrugEditDialog(name, dose, concentration, volume, pump)

        result = dlg.exec()
        name = dlg.drugNameLineEdit.text()
        dose = dlg.drugDoseSpinBox.value()
        concentration = dlg.drugConcentrationSpinBox.value()
        volume = dlg.drugVolumeSpinBox.value()
        pump = None if not dlg.usePumpCheckBox.isChecked() else dlg.pumpIdSpinBox.value()
        return name, dose, concentration, volume, pump, result == QDialog.Accepted


class DrugTimer(QLabel):
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
        if self._alarmThresh is not None and \
                self._duration.seconds > self._alarmThresh and \
                not self._isAlarmTimerPastMaxDuration and \
                not self._alarmTimer.isActive():
            self.triggerAlarm()

    def triggerAlarm(self):
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


class DrugPanel(QGroupBox):
    def __init__(self, parent, drugName, drugVolume, alarmSoundFile=None, logFile: LogFile = None):
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
        self._logFile = logFile
        self._LOG_FORMAT = "{time}\t{drugVolume} μL\t{drugName}\n"
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

        self._timer = DrugTimer(self, alarmSoundFile=alarmSoundFile)

        self._enableAlarmButton = QPushButton(self._ALARM_LABEL_OFF, self)
        self._enableAlarmButton.setCheckable(True)
        self._enableAlarmButton.setFlat(True)
        ico = QIcon()
        ico.addFile("./media/alarm-clock-OFF.png", state=QIcon.Off)
        ico.addFile("./media/alarm-clock-ON.png", state=QIcon.On)
        self._enableAlarmButton.setIcon(ico)
        self._enableAlarmButton.setIconSize(QSize(25, 25))
        self._enableAlarmButton.clicked.connect(self.onChoiceAlarm)

        hbox1 = QHBoxLayout()
        hbox2 = QHBoxLayout()
        vbox = QVBoxLayout()
        for box in [hbox1, hbox2, vbox]:
            box.setSpacing(0)
            box.setContentsMargins(0, 0, 0, 0)

        hbox1.addWidget(self._fullDoseButton)
        hbox1.addWidget(self._halfDoseButton)
        hbox1.addWidget(self._customDoseButton)
        hbox2.addWidget(self._timer)
        hbox2.addWidget(self._enableAlarmButton)
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)
        self.setLayout(vbox)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def doInjectDrug(self, volume):
        currTime = datetime.datetime.now().strftime("%H:%M:%S")
        output = self._LOG_FORMAT.format(time=currTime, drugName=self._drugName, drugVolume=volume)
        if self._logFile is not None:
            self._logFile.append(output)
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
        val, ok = CustomDialog.getDouble(self, value=self._drugVolume, text="Enter custom amount (μL)")
        if ok:
            self.doInjectDrug(val)

    # noinspection PyUnusedLocal
    def onChoiceAlarm(self, event):
        if self._enableAlarmButton.isChecked():
            val, ok = CustomDialog.getTime(self, value=self._timer.alarmThreshold,
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
        drugName, drugVolume, ok = CustomDialog.getDrugVolume(self, self._drugName, self._drugVolume)
        if ok == QDialog.Accepted:
            self._drugName = drugName
            self._drugVolume = drugVolume
            self.setTitle(self._LABEL_FORMAT.format(drugName=self._drugName, drugVolume=self._drugVolume))


class DrugPumpPanel(DrugPanel):
    def __init__(self, parent, drugName, drugVolume, pump: SyringePumps.SyringePump, alarmSoundFile=None, logFile=None):
        drugVolume = float(drugVolume)
        super().__init__(parent, drugName, drugVolume, alarmSoundFile, logFile)
        self._START_PERF_FORMAT = "{time}\t>> Start perf ({rate:.2f} {units})\t{drugName}\n"
        self._STOP_PERF_FORMAT = "{time}\t<< End perf\t{drugName}\n"
        self.pump = pump
        self.setStyleSheet(self.styleSheet() + """
            QGroupBox {
                background-color: #C1C9E2;
            }
            """)

        newTimer = PumpTimer(parent=self, pumpPanel=self, alarmSoundFile=alarmSoundFile)
        self.layout().replaceWidget(self._timer, newTimer)
        self._timer.deleteLater()
        self._timer = newTimer

        self._autoInjectCheckBox = QCheckBox("Auto-inject")
        self._autoInjectCheckBox.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self._autoInjectCheckBox.setStyle(IconProxyStyle(self._autoInjectCheckBox.style()))
        self._autoInjectCheckBox.toggled.connect(self.onToggleAutoInject)
        self.layout().addWidget(self._autoInjectCheckBox)

        self._perfRateSpinBox = QDoubleSpinBox()
        self._perfRateSpinBox.setDecimals(3)
        self._perfRateSpinBox.setMinimum(self.pump.minVal)
        self._perfRateSpinBox.setMaximum(self.pump.maxVal)
        self._perfRateUnitsComboBox = QComboBox()
        self._perfStartButton = QPushButton("Start Perf")
        self._perfStartButton.setCheckable(True)
        self._perfStartButton.clicked.connect(self.onTogglePerf)

        self._abortInjectButton = QPushButton('Abort')
        self._abortInjectButton.setIcon(self.style().standardIcon(QStyle.SP_BrowserStop))
        self._abortInjectButton.setVisible(False)
        self._abortInjectButton.clicked.connect(self.abortInjection)

        box = QHBoxLayout()
        box.addWidget(self._perfRateSpinBox)
        box.addWidget(self._perfRateUnitsComboBox)
        box.addWidget(self._perfStartButton)
        self.layout().insertWidget(1, self._abortInjectButton)
        self.layout().insertLayout(2, box)

        self._perfRateUnitsComboBox.addItems(self.pump.getPossibleUnits())
        self.updateFromPump()

    def onTogglePerf(self):
        currTime = datetime.datetime.now().strftime("%H:%M:%S")
        if self.pump.isRunning():
            self.pump.stop()
            self._logFile.append(self._STOP_PERF_FORMAT.format(time=currTime, drugName=self._drugName))
        else:
            try:
                self.pump.setRate(self._perfRateSpinBox.value(), self._perfRateUnitsComboBox.currentIndex())
                self.pump.clearTargetVolume()
                self.pump.start()
                self._logFile.append(self._START_PERF_FORMAT.format(time=currTime,
                                                                    drugName=self._drugName,
                                                                    rate=self._perfRateSpinBox.value(),
                                                                    units=self._perfRateUnitsComboBox.currentText()))
            except SyringePumps.valueOORException:
                # noinspection PyTypeChecker
                QMessageBox.information(None, 'Value OOR', 'ERROR: value is out of range for pump')
                self._perfRateSpinBox.setFocus()
        self.updateFromPump()

    def onToggleAutoInject(self, checked):
        self._timer.autoInject = checked

    def updateFromPump(self):
        currRate = self.pump.getRate()
        currUnits = self.pump.getUnits()
        currDir = self.pump.getDirection()
        self._perfRateSpinBox.setValue(currRate)
        self._perfRateUnitsComboBox.setCurrentIndex(currUnits)
        if currDir != 0:
            self._perfStartButton.setChecked(True)
            self.enablePerfusionButtons(False)
        else:
            self._perfStartButton.setChecked(False)
            self.enablePerfusionButtons(True)

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

    def doInjectDrug(self, volume):
        # in case the pump is currently infusing, we store the current values to restore after the
        # end of the injection
        currRate = self.pump.getRate()
        currDir = self.pump.getDirection()
        currUnits = self.pump.getUnits()

        try:
            if self.pump.isRunning():
                self.pump.stop()
            self.pump.setDirection(self.pump.STATE.INFUSING)
            self.pump.setRate(SyringePumps.BOLUS_RATE, SyringePumps.BOLUS_RATE_UNITS)
            self.pump.setTargetVolume(volume / 1000)  # volume is in uL but TargetVolume is in mL
            self.pump.start()
            super().doInjectDrug(volume)
        except SyringePumps.valueOORException:
            # noinspection PyTypeChecker
            QMessageBox.warning(None, "Value out of range", 'Cannot inject, value out of range')
        finally:
            # disable buttons to avoid double injections, and start a thread to wait for the injection
            # to finish
            self.enableInjectButtons(False)
            th = threading.Thread(target=self.waitForEndOfInjection, args=(currRate, currUnits, currDir))
            th.start()

    def enableInjectButtons(self, enabled: bool):
        self._fullDoseButton.setEnabled(enabled)
        self._halfDoseButton.setEnabled(enabled)
        self._customDoseButton.setEnabled(enabled)

        self._abortInjectButton.setVisible(not enabled)

    def enablePerfusionButtons(self, enabled: bool):
        self._perfRateSpinBox.setEnabled(enabled)
        self._perfRateUnitsComboBox.setEnabled(enabled)

    # noinspection PyUnusedLocal
    def abortInjection(self, event):
        if self.pump.isRunning():
            self.pump.stop()
        self.enableInjectButtons(True)

    def waitForEndOfInjection(self, restoreRate, restoreUnits, restoreDir):
        # logger.debug("in waitForEndOfInjection()")
        while self.pump.isRunning():
            time.sleep(0.1)
            pass
            logger.debug('pump is still running')
        # logger.debug('pump is finished pumping')
        self.enableInjectButtons(True)
        # logger.debug("restoring previous pump state")
        self.pump.setRate(restoreRate, restoreUnits)
        if restoreDir != 0:
            self.pump.setDirection(restoreDir)
            self.pump.start()
        self.updateFromPump()

    def onCustomDoseButtonClick(self, event):
        val, ok = CustomDialog.getDouble(self, value=self._drugVolume, text="Enter custom amount (μL)",
                                         minVal=0.001, maxVal=9999.)
        if ok:
            self.doInjectDrug(val)


class PumpTimer(DrugTimer):
    def __init__(self, parent, pumpPanel: DrugPumpPanel, alarmThresh=None, alarmSoundFile=None):
        super().__init__(parent=parent, alarmThresh=alarmThresh, alarmSoundFile=alarmSoundFile)
        self.pumpPanel = pumpPanel
        self._autoInject = False

    @property
    def autoInject(self):
        return self._autoInject

    @autoInject.setter
    def autoInject(self, value):
        self._autoInject = value

    def triggerAlarm(self):
        # logger.debug('in PumpTimer.triggerAlarm()')
        if self.autoInject:
            # logger.debug('autoInject==True, injecting...')
            self.pumpPanel.onFullDoseButtonClick(None)


class PhysioMonitorMainScreen(QFrame):
    def __init__(self, config):
        super().__init__()

        self.config = config

        # Acquisition system
        module = config['acquisition']['module']
        if module not in AVAIL_ACQ_MODULES:
            # noinspection PyTypeChecker
            QMessageBox.critical(None, 'Wrong acquisition module',
                                 f'ERROR: wrong acquisition module {module}.\n'
                                 'Must be one of: ' + ','.join(AVAIL_ACQ_MODULES.keys()))
            raise ValueError('Wrong acquisition module in config file')
        self.__stream = AVAIL_ACQ_MODULES[module](**config['acquisition']['module-args'])

        # Serial communication
        self.serialPorts = []
        for serial_conf in self.config['serial-ports']:
            try:
                ser = serial.serial_for_url(serial_conf['port'], serial_conf['baud-rate'],
                                            bytesize=serial_conf['byte-size'], parity=serial_conf['parity'],
                                            stopbits=serial_conf['stop-bits'],
                                            timeout=serial_conf['timeout'])
            except serial.SerialException:
                ser = None
            if ser is None:
                # noinspection PyTypeChecker
                QMessageBox.warning(None, 'Serial port error',
                                    'Cannot open serial port "{:s}"!\n'
                                    'Serial connection will not be available'.format(serial_conf['port']))
            self.serialPorts.append(ser)

        self.pumps = []
        for pump_conf in self.config['pumps']:
            model = pump_conf['model']
            pump = None
            if model not in AVAIL_PUMPS:
                raise ValueError('Incorrect pump model: {}'.format(model))
            # sometimes, it takes a couple of tries for the pump to answer,
            # so we'll try in a loop and test if it was successful
            success = False
            while not success:
                for _ in range(3):
                    try:
                        pump = AVAIL_PUMPS[model](serialport=self.serialPorts[pump_conf['serial-port']])
                        pump.isRunning()  # check that pump is working, should raise Exception if not
                        success = True
                        pump.doBeep()
                        break
                    except SyringePumpException:
                        pump = None
                if not success:
                    # noinspection PyTypeChecker
                    ans = QMessageBox.question(None, "Pump not responding",
                                               f"Cannot communicate with the pump {model}, maybe it is off?\nRetry?")
                    if ans == QMessageBox.No:
                        success = True
            self.pumps.append(pump)

        # Timer with callback to update plots
        self.__refreshTimer = QTimer()
        self.__refreshTimer.timeout.connect(self.update)

        #
        # UI elements
        #
        # LOG BOX
        self.logBox = QPlainTextEdit()
        self.logBox.setLineWrapMode(False)
        f = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        f.setPointSize(12)
        self.logBox.setFont(f)

        self.logFile = config['log-file']

        layout00 = QHBoxLayout()
        layout10 = QVBoxLayout()

        # Create some widgets to be placed inside
        clock = ClockWidget()
        self._graphLayout = ScopeLayoutWidget()

        notebook = QTabWidget()
        notebook.addTab(self._graphLayout, "Graphs")
        notebook.addTab(self.logBox, "Log")

        layout10.addWidget(clock, stretch=0)
        scrollArea = QScrollArea()
        scrollArea.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.MinimumExpanding)
        scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scrollArea.setWidgetResizable(True)
        widget = QWidget()
        scrollArea.setWidget(widget)
        self.drugPanelsLayout = QVBoxLayout()
        self.drugPanelsLayout.setContentsMargins(0, 0, 0, 0)
        self.drugPanelsLayout.setSpacing(0)
        for i, drug in enumerate(config['drug-list']):
            if drug.pump is not None and self.pumps[drug.pump - 1] is not None:
                panel = DrugPumpPanel(None, drug.name, drug.volume, pump=self.pumps[drug.pump - 1],
                                      # FIXME should pumps be zero indexed?
                                      alarmSoundFile='./media/beep3x6.wav', logFile=self.logFile)
            else:
                panel = DrugPanel(None, drug.name, drug.volume,
                                  alarmSoundFile='./media/beep3x6.wav', logFile=self.logFile)
            self.drugPanelsLayout.addWidget(panel)
        self.drugPanelsLayout.setAlignment(Qt.AlignTop)
        widget.setLayout(self.drugPanelsLayout)
        layout10.addWidget(scrollArea)

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

        for i, chan in enumerate(config['channels']):
            plot = PagedScope(
                sampleFreq=config['acquisition']['sample-rate'],
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
        self.setWindowIcon(QIcon('../media/icon.png'))

    def start(self):
        self.__stream.start()
        self.__refreshTimer.start(50)
        for i in range(len(self._graphLayout.centralWidget.items)):
            plot = self._graphLayout.getItem(i, 1)
            plot.start()

    def update(self):
        data = self.__stream.read()
        self._graphLayout.append(data)

    def addNote(self):
        text, ok = QInputDialog.getText(self, 'Add a note to the log', 'Note:')
        if ok and len(text) > 0:
            currTime = datetime.datetime.now().strftime("%H:%M:%S")
            self.logFile.append('{:s}\t{:s}\n'.format(currTime, text))

    def addNewDrug(self):
        name, volume, ok = CustomDialog.getDrugVolume(self, name="", volume=0, addInject=True)
        if ok == QDialog.Accepted or ok == QDialogButtonBox.YesToAll:
            newPanel = DrugPanel(None, drugName=name, drugVolume=volume, logFile=self.logFile)
            self.drugPanelsLayout.addWidget(newPanel)
            if ok == QDialogButtonBox.YesToAll:
                newPanel.onFullDoseButtonClick(None)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.__stream.close()
        event.accept()


class StartDialog(QDialog):
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

    def __init__(self, config):
        super().__init__()
        uic.loadUi('./GUI/StartScreen.ui', self)
        self.setWindowIcon(QIcon('../media/icon.png'))

        self.buttonBox.button(QDialogButtonBox.Ok).setIcon(QApplication.style().standardIcon(QStyle.SP_DialogOkButton))
        self.buttonBox.button(QDialogButtonBox.Cancel).setIcon(
            QApplication.style().standardIcon(QStyle.SP_DialogCancelButton))

        # load previous values to pre-populate dialog
        try:
            with open(PREVIOUS_VALUES_FILE, 'r', encoding='utf-8') as f:
                prev_values: dict = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            prev_values = {}
        if 'genotypes' not in prev_values.keys():
            prev_values['genotypes'] = []
        if 'drugs' not in prev_values.keys():
            prev_values['drugs'] = []
        if 'config-file' not in prev_values.keys():
            prev_values['config-file'] = ''
        if 'save-path' not in prev_values.keys():
            prev_values['save-path'] = ''
        temp = [Drug(name=drug['_name'],
                     dose=drug['_dose'],
                     concentration=drug['_concentration'],
                     volume=drug['_volume'],
                     pump=drug['_pump']) for drug in prev_values['drugs']]
        prev_values['drugs'] = temp

        self.mouse = Mouse()
        self.drugList = prev_values['drugs']
        self.configFile = prev_values['config-file']
        self.savePath = prev_values['save-path']
        self.config = config
        self.saveFolder = os.path.join(prev_values['save-path'], datetime.date.today().isoformat())
        if 'log-filename' not in self.config:
            self.logFile = ''
        else:
            self.logFile = os.path.join(self.saveFolder, self.config['log-filename'])

        self.isResumed = False
        if os.path.isfile(self.logFile):
            # we already have a log file in the folder, ask whether to resume
            dlg = QMessageBox()
            dlg.setWindowTitle('Previous session detected')
            dlg.setIcon(QMessageBox.Question)
            dlg.setText("The folder already contains a log file.")
            dlg.setInformativeText('Do you want to resume the previous session?')
            dlg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            if dlg.exec() == QMessageBox.Yes:
                mouse, drugs = LogFile.parse(self.logFile)
                if mouse is None:
                    # noinspection PyTypeChecker
                    QMessageBox.information(None, "Could not parse", "Failed to parse previous log file.")
                else:
                    self.mouse = mouse
                    self.drugList = drugs
                    self.isResumed = True

        # MOUSE TAB
        # noinspection PyTypeChecker
        for but, butId in zip(self.mouseSexButtonGroup.buttons(), Sex):
            self.mouseSexButtonGroup.setId(but, butId)
        self.mouseDoBBox.setDate(QDate(self.mouse.dob.year, self.mouse.dob.month, self.mouse.dob.day))
        self.mouseSexButtonGroup.button(self.mouse.sex).setChecked(True)
        self.mouseWeightSpinBox.setValue(self.mouse.weight)
        self.mouseGenotypeComboBox.setModel(QStringListModel())  # Convenient to get a list of strings at the end
        self.mouseGenotypeComboBox.addItems(prev_values['genotypes'])
        existsId = self.mouseGenotypeComboBox.findText(self.mouse.genotype)
        if existsId >= 0:
            self.mouseGenotypeComboBox.removeItem(existsId)
        self.mouseGenotypeComboBox.insertItem(-1, self.mouse.genotype)
        self.mouseGenotypeComboBox.setCurrentIndex(0)
        self.mouseCommentsTextEdit.setText(self.mouse.comments)

        # DRUG LIST TAB
        self.tableModel = DrugTableModel(self.drugList)
        self.drugTable.setModel(self.tableModel)
        for i in range(1, self.tableModel.columnCount() - 1):
            self.drugTable.setItemDelegateForColumn(i, DoubleSpinBoxDelegate(self))
        self.editDrugButton.clicked.connect(self.editEntry)
        self.addDrugButton.clicked.connect(self.addEntry)
        self.delDrugButton.clicked.connect(self.removeEntry)
        for i in range(1, self.tableModel.columnCount()):
            self.drugTable.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.drugTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        # CONFIG TAB
        self.savePathLineEdit.setText(self.savePath)
        self.savePathBrowseButton.clicked.connect(self.browseSavePath)

    def addEntry(self):
        name, dose, concentration, volume, pump, ok = DrugEditDialog.getDrugData()
        if ok:
            newDrug = Drug(name=name, dose=dose, concentration=concentration, volume=volume, pump=pump)
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
            name, dose, concentration, volume, pump, ok = DrugEditDialog.getDrugData(*drugData)
            if ok:
                for j, field in enumerate([name, dose, concentration, volume, pump]):
                    ix = self.tableModel.index(row, j, QModelIndex())
                    self.tableModel.setData(ix, field, Qt.EditRole)

    def removeEntry(self):
        selectionModel = self.drugTable.selectionModel()
        indexes = selectionModel.selectedRows()

        for index in indexes:
            self.drugTable.model().removeRows(index.row(), 1)

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

    def exec(self) -> int:
        # if the content of the dialog was imported from previous session
        # then skip showing it altogether and accept the values
        if self.isResumed:
            self.accept()
            return self.Accepted
        else:
            return super().exec()

    def accept(self) -> None:
        # Accept new entry in genotype list if necessary
        text = self.mouseGenotypeComboBox.lineEdit().text()
        pos = self.mouseGenotypeComboBox.findText(text)
        if pos >= 0:
            self.mouseGenotypeComboBox.removeItem(pos)
        self.mouseGenotypeComboBox.insertItem(0, text)

        # save data
        self.mouse.genotype = self.mouseGenotypeComboBox.itemText(0)
        if self.mouseSexButtonGroup.checkedId() == Sex.MALE:
            self.mouse.sex = Sex.MALE
        elif self.mouseSexButtonGroup.checkedId() == Sex.FEMALE:
            self.mouse.sex = Sex.FEMALE
        else:
            self.mouse.sex = Sex.UNKNOWN
        self.mouse.weight = self.mouseWeightSpinBox.value()
        self.mouse.dob = self.mouseDoBBox.date().toPyDate()
        self.mouse.comments = self.mouseCommentsTextEdit.toPlainText()

        self.savePath = self.savePathLineEdit.text()
        self.logFile = os.path.join(self.savePath, datetime.date.today().isoformat(), self.config['log-filename'])
        self.config['drug-list'] = self.drugList

        # save the lists genotypes/investigators/drugs upon accepting
        # so they can be reloaded next time
        out = {'genotypes': self.mouseGenotypeComboBox.model().stringList(),
               'drugs': [drug.__dict__ for drug in self.drugList],
               'save-path': self.savePath
               }
        with open(PREVIOUS_VALUES_FILE, 'w', encoding='utf-8') as f:
            json.dump(out, f)

        super().accept()
