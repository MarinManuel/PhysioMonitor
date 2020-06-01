import os
import pygame
from PyQt5 import QtCore
from PyQt5.QtGui import QPixmap, QIcon, QCursor, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QDialog, QDoubleSpinBox, QLineEdit, QPushButton, \
    QHBoxLayout, QSpinBox, QDialogButtonBox, QGridLayout, QFrame, QGroupBox, QButtonGroup, QRadioButton, QSizePolicy
import datetime

# if it hasn't been already, initialize the sound mixer
if pygame.mixer.get_init() is None:
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.mixer.init()


class clockWidget(QWidget):
    def __init__(self, showDate=True, timeSize=30, dateSize=20, *args, **kwargs):
        super(clockWidget, self).__init__(*args, **kwargs)
        self.TIME_FORMAT = "%H:%M"
        self.DATE_FORMAT = "%x"

        self._timer = QtCore.QTimer(self)
        # noinspection PyUnresolvedReferences
        self._timer.timeout.connect(self.onTimeEvent)
        self._timer.start(250)
        self._vbox = QVBoxLayout(self)
        self._vbox.setAlignment(QtCore.Qt.AlignCenter)

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
        self._vbox.addWidget(self._timeLabel, 0, QtCore.Qt.AlignCenter)
        if showDate:
            self._vbox.addWidget(self._dateLabel, 0, QtCore.Qt.AlignCenter)
        self._vbox.addStretch(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def onTimeEvent(self):
        self._timeLabel.setText(datetime.datetime.now().strftime(self.TIME_FORMAT))
        self._dateLabel.setText(datetime.datetime.now().strftime(self.DATE_FORMAT))


class customValueDialog(QDialog):
    def __init__(self, parent, value=0.0, min=0.0, max=1000.0, text=None):
        super(customValueDialog, self).__init__(parent)
        self.inputBox = QDoubleSpinBox(self)
        self.inputBox.setValue(value)
        self.inputBox.setMinimum(min)
        self.inputBox.setMaximum(max)
        self.inputBox.setMinimumWidth(50)
        self.inputBox.setAlignment(QtCore.Qt.AlignRight)
        lineEdit = self.inputBox.findChild(QLineEdit, 'qt_spinbox_lineedit')
        lineEdit.selectAll()

        okPixmap = QPixmap('./media/button_ok.png')
        okButton = QPushButton(self)
        okButton.setIcon(QIcon(okPixmap))
        okButton.setIconSize(okPixmap.size())
        okButton.setMaximumSize(okPixmap.width(), okPixmap.height())

        cancelPixmap = QPixmap('./media/button_cancel.png')
        cancelButton = QPushButton(self)
        cancelButton.setIcon(QIcon(cancelPixmap))
        cancelButton.setIconSize(cancelPixmap.size())
        cancelButton.setMaximumSize(cancelPixmap.width(), cancelPixmap.height())

        okButton.clicked.connect(self.accept)
        cancelButton.clicked.connect(self.reject)

        layout = QVBoxLayout(None)
        layout.setContentsMargins(5, 0, 5, 5)
        layout.setSpacing(0)
        buttonLayout = QHBoxLayout(None)
        buttonLayout.setSpacing(20)
        buttonLayout.addStretch(1)
        buttonLayout.addWidget(okButton)
        buttonLayout.addWidget(cancelButton)

        if text is not None:
            layout.addWidget(QLabel(text=text))
        layout.addWidget(self.inputBox)
        layout.addLayout(buttonLayout)

        self.setLayout(layout)

    def showEvent(self, event):
        geom = self.frameGeometry()
        geom.moveTopLeft(QCursor().pos())
        self.setGeometry(geom)
        super(customValueDialog, self).showEvent(event)

    @staticmethod
    def getCustomValue(parent, value=0.0, min=0.0, max=1000.0, text=None):
        dialog = customValueDialog(parent, value, min, max, text)
        result = dialog.exec_()
        value = dialog.inputBox.value()
        return value, result == QDialog.Accepted


class drugEntryDialog(QDialog):
    def __init__(self, parent, drugName, drugDose):
        super(drugEntryDialog, self).__init__(parent)
        self.setWindowTitle("Edit Drug")
        drugNameLabel = QLabel("Drug name:")
        self.drugNameInput = QLineEdit(self)
        self.drugNameInput.setText(drugName)
        drugDoseLabel = QLabel("Dose (μL):")
        self.drugDoseInput = QSpinBox(self)
        self.drugDoseInput.setValue(drugDose)
        self.drugDoseInput.setAlignment(QtCore.Qt.AlignRight)

        buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(0)
        layout.addWidget(drugNameLabel, 0, 0)
        layout.addWidget(drugDoseLabel, 0, 1)
        layout.addWidget(self.drugNameInput, 1, 0)
        layout.addWidget(self.drugDoseInput, 1, 1)
        layout.addWidget(buttonBox, 2, 0, 1, -1, QtCore.Qt.AlignRight)

    def showEvent(self, event):
        geom = self.frameGeometry()
        geom.moveTopLeft(QCursor().pos())
        self.setGeometry(geom)
        super(drugEntryDialog, self).showEvent(event)

    # static method to create the dialog and return (date, time, accepted)
    @staticmethod
    def getDrugEntry(parent, drugName, drugDose):
        dialog = drugEntryDialog(parent, drugName, drugDose)
        result = dialog.exec_()
        drugName = dialog.drugNameInput.text()
        drugDose = dialog.drugDoseInput.value()
        return drugName, drugDose, result == QDialog.Accepted


class drugTimer(QLabel):
    def __init__(self, parent, alarmThresh=None, alarmSoundFile=None):
        super(drugTimer, self).__init__(parent)
        self._duration = datetime.timedelta()
        self._startTime = None
        self.__FORMAT = "{:02.0f}:{:02.0f}"
        self.__FORMAT_LONG = "{:02.0f}:{:02.0f}:{:02.0f}"
        self.__FORMAT_COLOR_NORMAL = 'black'
        self.__FORMAT_COLOR_ALARM = 'red'
        self.__FORMAT_STYLESHEET = """* {{
            font-family: monospace;
            font-size : 24pt;
            font-weight : bold;
            color : {};
        }}"""
        self.setStyleSheet(self.__FORMAT_STYLESHEET.format(self.__FORMAT_COLOR_NORMAL))
        self.updateText()
        self.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        self._clockTimer = QtCore.QTimer(self)
        self._clockTimer_PERIOD = 100  # ms
        self._alarmThresh = alarmThresh
        self._alarmTimer = QtCore.QTimer(self)
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
        if hrs == 0:
            self.setText(
                self.__FORMAT.format(mins, secs))
        else:
            self.setText(
                self.__FORMAT_LONG.format(hrs, mins, secs))

    def reset(self, event=None):
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


class drugPanel(QFrame):
    def __init__(self, parent, drugName, drugDose, alarmSoundFile=None, logWidget=None):
        self._LABEL_FORMAT = "{drugName} ({drugDose:.0f} μL)"
        self._drugName = drugName
        self._drugDose = drugDose
        self._injTime = None
        self._alarmTimes = [None, 30., 10., 0.0]
        self._logWidget = logWidget
        self._LOG_FORMAT = "{time}\t{drugName} ({drugDose} μL)\n"
        if alarmSoundFile is not None and os.path.isfile(alarmSoundFile):
            self._alarmSound = pygame.mixer.Sound(alarmSoundFile)
        else:
            self._alarmSound = None

        super(drugPanel, self).__init__(parent)
        vbox = QGridLayout(None)
        vbox.setSpacing(0)
        vbox.setContentsMargins(0, 0, 0, 0)
        self._drugLabel = QLabel(self)
        self._drugLabel.setText(self._LABEL_FORMAT.format(drugName=self._drugName, drugDose=self._drugDose))
        self._drugLabel.mouseDoubleClickEvent = self.onDrugLabelClick
        self._fullDoseButton = QPushButton(self)
        self._fullDoseButton.setText('Full dose')
        self._halfDoseButton = QPushButton(self)
        self._halfDoseButton.setText('1/2 dose')
        self._quartDoseButton = QPushButton(self)
        self._quartDoseButton.setText('1/4 dose')
        self._customDoseButton = QPushButton(self)
        self._customDoseButton.setText('...')
        self._fullDoseButton.clicked.connect(self.onFullDoseButtonClick)
        self._halfDoseButton.clicked.connect(self.onHalfDoseButtonClick)
        self._quartDoseButton.clicked.connect(self.onQuartDoseButtonClick)
        self._customDoseButton.clicked.connect(self.onCustomDoseButtonClick)

        self._timerLabel = drugTimer(self, alarmSoundFile=alarmSoundFile)

        self._alarmBox = QGroupBox("Alarms:", self)
        self._alarmGroup = QButtonGroup(self)
        alarmBoxLayout = QHBoxLayout(None)
        self._alarmChoiceNone = QRadioButton("None", self)
        self._alarmChoiceNone.setChecked(True)
        self._alarmChoice30m = QRadioButton("30m", self)
        self._alarmChoice10m = QRadioButton("10m", self)
        self._alarmChoiceCustom = QRadioButton("...", self)
        alarmBoxLayout.addWidget(self._alarmChoiceNone)
        alarmBoxLayout.addWidget(self._alarmChoice30m)
        alarmBoxLayout.addWidget(self._alarmChoice10m)
        alarmBoxLayout.addWidget(self._alarmChoiceCustom)
        self._alarmGroup.addButton(self._alarmChoiceNone, 0)
        self._alarmGroup.addButton(self._alarmChoice30m, 1)
        self._alarmGroup.addButton(self._alarmChoice10m, 2)
        self._alarmGroup.addButton(self._alarmChoiceCustom, 3)
        self._alarmBox.setLayout(alarmBoxLayout)
        self._alarmGroup.buttonClicked.connect(self.onChoiceAlarm)

        vbox.addWidget(self._drugLabel, 0, 0, 1, -1)  # first row, span all columns
        vbox.addWidget(self._fullDoseButton, 1, 0)  # 2nd row, 1st col
        vbox.addWidget(self._halfDoseButton, 1, 1)  # 2nd row, 2nd col
        vbox.addWidget(self._quartDoseButton, 1, 2)  # 2nd row, 3rd col
        vbox.addWidget(self._customDoseButton, 1, 3)  # 2nd row, 4th col
        vbox.addWidget(self._timerLabel, 2, 0)
        vbox.addWidget(self._alarmBox, 2, 1, 1, -1)  # 3rd row, 2nd col, span 3 cols
        self.setLayout(vbox)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        #self.setFixedSize(355, 115)

    def doInjectDrug(self, dose):
        currTime = datetime.datetime.now().strftime("%H:%M:%S")
        output = self._LOG_FORMAT.format(time=currTime, drugName=self._drugName, drugDose=dose)
        if self._logWidget is not None:
            self._logWidget.append(output)
        else:
            print(output)
        self._timerLabel.start()

    def onFullDoseButtonClick(self, event):
        self.doInjectDrug(self._drugDose)

    def onHalfDoseButtonClick(self, event):
        self.doInjectDrug(self._drugDose / 2)

    def onQuartDoseButtonClick(self, event):
        self.doInjectDrug(self._drugDose / 4)

    def onCustomDoseButtonClick(self, event):
        val, ok = customValueDialog.getCustomValue(self, value=self._drugDose, text="Enter custom amount (μL)")
        if ok:
            self.doInjectDrug(val)

    def onChoiceAlarm(self, event):
        id = self._alarmGroup.checkedId()
        but = self._alarmGroup.checkedButton()
        if 0 <= id <= 2:
            self._timerLabel.setAlarmThreshInMins(self._alarmTimes[id])
        else:
            value, ok = customValueDialog.getCustomValue(self, value=self._alarmTimes[3], text="Enter time to alarm ("
                                                                                               "minutes)")
            if ok:
                print(value)
                but.setText('{:.0f}m'.format(value))
                self._timerLabel.setAlarmThreshInMins(value)
                self._alarmTimes[3] = value

    def onDrugLabelClick(self, event):
        drugName, drugDose, ok = drugEntryDialog.getDrugEntry(self, self._drugName, self._drugDose)
        if ok:
            self._drugName = drugName
            self._drugDose = drugDose
            self._drugLabel.setText(self._LABEL_FORMAT.format(drugName=self._drugName, drugDose=self._drugDose))


class drugPumpPanel(drugPanel):
    def __init__(self, parent, drugName, drugDose, alarmSoundFile=None, logWidget=None):
        super(drugPumpPanel, self).__init__(parent, drugName, drugDose, alarmSoundFile, logWidget)
