import datetime
import json
import logging
import os
import threading
import time
import typing
from typing import List

import numpy as np
import pygame
import serial
# noinspection PyUnresolvedReferences
from PyQt5 import uic
from PyQt5.QtCore import QTimer, QRect, QModelIndex, QDate, QStringListModel, QSize
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QCursor, QFont, QCloseEvent
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QDialog,
    QDoubleSpinBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QDialogButtonBox,
    QGridLayout,
    QSizePolicy,
    QRadioButton,
    QStyle,
    QPlainTextEdit,
    QInputDialog,
    QApplication,
    QCheckBox,
    QProxyStyle,
    QHeaderView,
    QComboBox,
    QDateEdit,
    QButtonGroup,
    QTextEdit,
    QTableView,
    QMessageBox,
    QMainWindow,
    QProgressBar,
    QFrame,
)

from GUI.Models import DrugTableModel
from GUI.scope import ScopeLayoutWidget, PagedScope, ScrollingScope, vline_color_iterator
from misc import Drug, Sex, Subject, LogBox
from pumps import SyringePumps
from pumps.SyringePumps import SyringePumpException, AVAIL_PUMP_MODULES, SyringePump

# noinspection SpellCheckingInspection
from sampling import AVAIL_ACQ_MODULES

# if it hasn't been already, initialize the sound mixer
if pygame.mixer.get_init() is None:
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.mixer.init()

logger = logging.getLogger(__name__)

# noinspection SpellCheckingInspection
MIN_VAL_QDOUBLESPINBOX = 0.1
# noinspection SpellCheckingInspection
MAX_VAL_QDOUBLESPINBOX = 1e12


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
    def __init__(self, show_date=True, time_size=30, date_size=20, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.TIME_FORMAT = "%H:%M"
        self.DATE_FORMAT = "%x"

        self._timer = QTimer(self)
        # noinspection PyUnresolvedReferences
        self._timer.timeout.connect(self.on_time_event)
        self._timer.start(250)
        self._vbox = QVBoxLayout(self)
        self._vbox.setAlignment(Qt.AlignCenter)

        self._timeLabel = QLabel(self)
        f = QFont()
        f.setBold(True)
        f.setPointSize(time_size)
        self._timeLabel.setFont(f)
        self._timeLabel.setText(datetime.datetime.now().strftime(self.TIME_FORMAT))

        self._dateLabel = QLabel(self)
        f.setBold(False)
        f.setPointSize(date_size)
        self._dateLabel.setFont(f)
        self._dateLabel.setText(datetime.datetime.now().strftime(self.DATE_FORMAT))

        self._vbox.addStretch(1)
        self._vbox.addWidget(self._timeLabel, 0, Qt.AlignCenter)
        if show_date:
            self._vbox.addWidget(self._dateLabel, 0, Qt.AlignCenter)
        self._vbox.addStretch(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def on_time_event(self):
        self._timeLabel.setText(datetime.datetime.now().strftime(self.TIME_FORMAT))
        self._dateLabel.setText(datetime.datetime.now().strftime(self.DATE_FORMAT))


class CustomDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Ok).setIcon(
            QApplication.style().standardIcon(QStyle.SP_DialogOkButton)
        )
        self.buttonBox.button(QDialogButtonBox.Cancel).setIcon(
            QApplication.style().standardIcon(QStyle.SP_DialogCancelButton)
        )
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
            # the dialog is off-screen,
            new_rect.moveBottomLeft(cursor_pos)

        self.setGeometry(new_rect)

    @staticmethod
    def get_double(
            parent,
            value=0.0,
            min_val=0.0,
            max_val=float("inf"),
            units=None,
            text=None,
            title="Enter a value",
    ):
        dlg = CustomDialog()

        spin_box = QDoubleSpinBox(parent)
        spin_box.setDecimals(3)
        spin_box.setMinimum(min_val)
        spin_box.setMaximum(max_val)
        spin_box.setValue(value)
        spin_box.setMinimumWidth(50)
        spin_box.setAlignment(Qt.AlignRight)
        if units is not None:
            spin_box.setSuffix(" " + units)

        dlg.layout.insertWidget(0, spin_box)
        if text is not None:
            txt = QLabel(text)
            dlg.layout.insertWidget(0, txt)
        dlg.setWindowTitle(title)

        # noinspection SpellCheckingInspection
        line_edit = spin_box.findChild(QLineEdit, "qt_spinbox_lineedit")
        line_edit.selectAll()
        spin_box.setFocus()

        result = dlg.exec()
        val = spin_box.value()
        return val, result == QDialog.Accepted

    @staticmethod
    def get_time(
            parent, value=0, text="Time before alarm", title="Enter the amount of time"
    ):
        # noinspection PyUnusedLocal
        def on_radio_click(event):
            if m30_button.isChecked() or m10_button.isChecked():
                time_box.setEnabled(False)
            else:
                time_box.setEnabled(True)
                # noinspection SpellCheckingInspection
                line_edit = time_box.findChild(QLineEdit, "qt_spinbox_lineedit")
                line_edit.selectAll()
                time_box.setFocus()

        dlg = CustomDialog(parent)
        dlg.setWindowTitle(title)

        label = QLabel(text)
        m30_button = QRadioButton("30 min")
        m10_button = QRadioButton("10 min")
        custom_button = QRadioButton("Custom:")
        time_box = QSpinBox()
        time_box.setMinimum(1)
        time_box.setMaximum(2147483647)
        time_box.setSuffix(" min")
        if value == 30:
            m30_button.setChecked(True)
        elif value == 10:
            m10_button.setChecked(True)
        else:
            custom_button.setChecked(True)
        time_box.setValue(1 if value is None else value)
        on_radio_click(None)

        m30_button.toggled.connect(on_radio_click)
        m10_button.toggled.connect(on_radio_click)
        custom_button.toggled.connect(on_radio_click)

        layout = QGridLayout()
        layout.addWidget(label, 0, 0, 1, 2)
        layout.addWidget(m30_button, 1, 0, 1, 2)
        layout.addWidget(m10_button, 2, 0, 1, 2)
        layout.addWidget(custom_button, 3, 0)
        layout.addWidget(time_box, 3, 1)

        dlg.layout.insertLayout(0, layout)
        result = dlg.exec()
        if m30_button.isChecked():
            val = 30
        elif m10_button.isChecked():
            val = 10
        else:
            val = time_box.value()
        return val, result == QDialog.Accepted

    @staticmethod
    def get_drug_volume(parent, name, volume, add_inject=False):
        dlg = CustomDialog(parent)
        dlg.setWindowTitle("Enter drug information")

        drug_name_label = QLabel("Drug name:")
        drug_name_input = QLineEdit()
        drug_name_input.setText(name)
        drug_volume_label = QLabel("Volume:")
        drug_volume_input = QSpinBox()
        drug_volume_input.setMinimum(1)
        drug_volume_input.setMaximum(2147483647)
        drug_volume_input.setValue(volume)
        drug_volume_input.setAlignment(Qt.AlignRight)
        drug_volume_input.setSuffix(" μL")

        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(0)
        layout.addWidget(drug_name_label, 0, 0)
        layout.addWidget(drug_volume_label, 0, 1)
        layout.addWidget(drug_name_input, 1, 0)
        layout.addWidget(drug_volume_input, 1, 1)
        if add_inject:
            add_inject_button = QPushButton("Add and inject")
            add_inject_button.setIcon(
                QApplication.style().standardIcon(QStyle.SP_DialogOkButton)
            )
            add_inject_button.setDefault(True)
            add_inject_button.clicked.connect(
                lambda: dlg.done(QDialogButtonBox.YesToAll)
            )
            dlg.buttonBox.addButton(add_inject_button, QDialogButtonBox.ActionRole)
            dlg.buttonBox.button(QDialogButtonBox.Ok).setText("Add to panel")

        dlg.layout.insertLayout(0, layout)
        result = dlg.exec()
        name = drug_name_input.text()
        volume = drug_volume_input.value()
        return name, volume, result


class EditDrugPumpDialog(QDialog):
    def __init__(self, parent, drug_name, drug_volume, pump, pos=None):
        super(EditDrugPumpDialog, self).__init__(parent=parent)
        layout = QGridLayout()
        layout.addWidget(QLabel("Drug name:"), 0, 0)
        self.drugNameEdit = QLineEdit(drug_name)
        layout.addWidget(self.drugNameEdit, 0, 1)
        layout.addWidget(QLabel("Bolus volume:"), 1, 0)
        self.drugVolumeSpinBox = QDoubleSpinBox()
        self.drugVolumeSpinBox.setDecimals(2)
        self.drugVolumeSpinBox.setMinimum(MIN_VAL_QDOUBLESPINBOX)
        self.drugVolumeSpinBox.setMaximum(MAX_VAL_QDOUBLESPINBOX)
        self.drugVolumeSpinBox.setSuffix(" uL")
        self.drugVolumeSpinBox.setAlignment(Qt.AlignRight)
        self.drugVolumeSpinBox.setValue(drug_volume)
        layout.addWidget(self.drugVolumeSpinBox, 1, 1)
        widget = PumpConfigPanel(pump=pump)
        layout.addWidget(widget, 2, 0, 1, 2)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons, 3, 0, 1, 2)
        self.setLayout(layout)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        if pos is not None:
            self.move(pos)


class DrugEditDialog(QDialog):
    drugNameLineEdit: QLineEdit
    drugDoseSpinBox: QDoubleSpinBox
    drugConcentrationSpinBox: QDoubleSpinBox
    drugVolumeSpinBox: QSpinBox
    usePumpCheckBox: QCheckBox
    pumpComboBox: QComboBox

    def __init__(
            self, name="", dose=0.0, concentration=0.0, volume=0, pump_id=None, pumps=None
    ):
        super().__init__()
        pumps = [] if pumps is None else pumps
        uic.loadUi("./GUI/DrugEditDialog.ui", self)
        self.drugNameLineEdit.setText(name)
        self.drugDoseSpinBox.setValue(float(dose))
        self.drugConcentrationSpinBox.setValue(float(concentration))
        self.drugVolumeSpinBox.setValue(int(volume))
        self.usePumpCheckBox.toggled.connect(self.use_pump_toggled)
        self.pumpComboBox.clear()
        self.pumpComboBox.addItems(pumps)
        if pump_id is None or len(pumps) == 0:
            self.usePumpCheckBox.setChecked(False)
        else:
            self.usePumpCheckBox.setChecked(True)
            self.pumpComboBox.setCurrentIndex(pump_id)

    def use_pump_toggled(self, state):
        self.pumpComboBox.setEnabled(state)

    @staticmethod
    def get_drug_data(
            name="", dose=0.0, concentration=0.0, volume=0, pump_id=None, pumps=None
    ):
        dlg = DrugEditDialog(name, dose, concentration, volume, pump_id, pumps)
        result = dlg.exec()

        name = dlg.drugNameLineEdit.text()
        dose = dlg.drugDoseSpinBox.value()
        concentration = dlg.drugConcentrationSpinBox.value()
        volume = dlg.drugVolumeSpinBox.value()
        pump = (
            None
            if not dlg.usePumpCheckBox.isChecked()
            else dlg.pumpComboBox.currentIndex()
        )
        return name, dose, concentration, volume, pump, result == QDialog.Accepted


class DrugTimer(QLabel):
    def __init__(self, parent, alarm_threshold=None, alarm_sound_file=None):
        super().__init__(parent)
        self._duration = datetime.timedelta()
        self._startTime = None
        self.__FORMAT = """<p>
        <span style="font-family: monospace; font-size:24pt; font-weight:bold">{:02.0f}:{:02.0f}</span>
        <span style="font-family: monospace; font-size:10pt; font-weight:normal;">:{:02.0f}</span>
        </p>"""
        self.__FORMAT_COLOR_NORMAL = "black"
        self.__FORMAT_COLOR_ALARM = "red"
        self.__FORMAT_STYLESHEET = "color: {:s}"
        self.setStyleSheet(self.__FORMAT_STYLESHEET.format(self.__FORMAT_COLOR_NORMAL))
        self.update_text()
        self.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self._clockTimer = QTimer(self)
        self._clockTimer_PERIOD = 100  # ms
        self._alarmThresh = alarm_threshold
        self._alarmTimer = QTimer(self)
        self._alarmTimer_PERIOD = 500  # ms
        self._alarmTimerCount = 0
        self._alarmTimerMaxCount = 10
        self._isAlarmTimerPastMaxDuration = False
        self._alarmTimer.timerEvent = self.on_alarm_timer
        self._clockTimer.timerEvent = self.on_clock_timer
        self.mouseDoubleClickEvent = self.reset
        self._alarmSound = None
        self.set_alarm_sound_file(alarm_sound_file)

    def start(self):
        self._startTime = datetime.datetime.today()
        self._clockTimer.start(self._clockTimer_PERIOD)

    def update_text(self):
        hrs = self._duration.seconds // (60 * 60)
        r = self._duration.seconds - hrs * 60 * 60
        minutes = r // 60
        secs = r - minutes * 60
        self.setText(self.__FORMAT.format(hrs, minutes, secs))

    # noinspection PyUnusedLocal
    def reset(self, event):
        if self._clockTimer.isActive():  # timer is going
            self._clockTimer.stop()
            self._duration = datetime.timedelta()  # reset duration to 0
            self.update_text()
            if self._alarmTimer.isActive():
                self._alarmTimer.stop()
            self.setStyleSheet(
                self.__FORMAT_STYLESHEET.format(self.__FORMAT_COLOR_NORMAL)
            )
            self._isAlarmTimerPastMaxDuration = False
            if self._alarmSound is not None:
                self._alarmSound.stop()

    # noinspection PyUnusedLocal
    def on_clock_timer(self, event):
        self._duration = datetime.datetime.today() - self._startTime
        self.update_text()
        if (
                self._alarmThresh is not None
                and self._duration.seconds > self._alarmThresh
                and not self._isAlarmTimerPastMaxDuration
                and not self._alarmTimer.isActive()
        ):
            self.trigger_alarm()

    def trigger_alarm(self):
        self.on_alarm_timer(None)
        self._alarmTimer.start(self._alarmTimer_PERIOD)
        if self._alarmSound is not None:
            self._alarmSound.play(-1)

    def set_alarm_threshold_in_minutes(self, duration_in_minutes):
        if duration_in_minutes is not None:
            self._alarmThresh = duration_in_minutes * 60
        else:
            self._alarmThresh = None

    # noinspection PyUnusedLocal
    def on_alarm_timer(self, event):
        self.setStyleSheet(
            self.__FORMAT_STYLESHEET.format(
                self.__FORMAT_COLOR_ALARM
                if self._alarmTimerCount % 2 == 0
                else self.__FORMAT_COLOR_NORMAL
            )
        )
        self._alarmTimerCount += 1
        if (
                self._alarmTimer.isActive()
                and self._alarmTimerCount > self._alarmTimerMaxCount
        ):
            self.on_alarm_past_max_duration()

    def on_alarm_past_max_duration(self):
        self._isAlarmTimerPastMaxDuration = True
        self._alarmTimer.stop()
        self._alarmTimerCount = 0
        self.setStyleSheet(self.__FORMAT_STYLESHEET.format(self.__FORMAT_COLOR_ALARM))
        if self._alarmSound is not None:
            self._alarmSound.stop()

    @property
    def alarm_threshold(self):
        return self._alarmThresh

    @property
    def alarm_sound(self):
        return self._alarmSound

    def set_alarm_sound_file(self, path):
        if path is not None and os.path.isfile(path):
            self._alarmSound = pygame.mixer.Sound(path)


class PumpTimer(DrugTimer):
    def __init__(self, parent, alarm_threshold=None, alarm_sound_file=None):
        super().__init__(
            parent=parent,
            alarm_threshold=alarm_threshold,
            alarm_sound_file=alarm_sound_file,
        )
        self.pumpPanel = None
        self._autoInject = False

    def setup(self, pump_panel, alarm_threshold=None, alarm_sound_file=None):
        self.pumpPanel = pump_panel
        self.set_alarm_threshold_in_minutes(alarm_threshold)
        self.set_alarm_sound_file(alarm_sound_file)

    @property
    def auto_inject(self):
        return self._autoInject

    @auto_inject.setter
    def auto_inject(self, value):
        self._autoInject = value

    def trigger_alarm(self):
        # logger.debug('in PumpTimer.triggerAlarm()')
        if self.auto_inject:
            # logger.debug('autoInject==True, injecting...')
            self.pumpPanel.on_full_dose_button_click(None)


class PhysioMonitorMainScreen(QMainWindow):
    logTextEdit: QPlainTextEdit
    clock: ClockWidget
    _graphLayout: ScopeLayoutWidget
    drugPanelsLayout: QVBoxLayout
    otherDrugButton: QPushButton
    addNoteButton: QPushButton

    def __init__(self, config: dict, pump_serial_ports=None, pumps=None):
        super().__init__()
        # Load the UI Page
        uic.loadUi("./GUI/MainScreen.ui", self)
        self.config = config
        self.setWindowIcon(QIcon("../media/icon.png"))

        ##
        # Plots
        ###
        for i, channel in enumerate(config["channels"]):
            plot = PagedScope(
                acquisition_module_index=channel["acquisition-module-index"],
                channel_index=channel["channel-index"],
                sample_freq=config["acquisition-modules"][
                    channel["acquisition-module-index"]
                ]["sampling-rate"],
                window_size=channel["window-size"],
                line_color=channel["line-color"],
                line_width=channel["line-width"],
                scaling=channel["scale"],
                offset=channel["offset"],
                title=channel["label"],
                units=channel["units"],
                autoscale=channel["autoscale"],
                ymin=channel["ymin"],
                ymax=channel["ymax"],
                persistence=channel["persistence"],
                trig_mode=channel["trigger-mode"],
                trig_level=channel["trigger-level"],
                auto_trig_level=channel["auto-trigger-level"],
                trend_window_size=channel["trend-window-size"],
                trend_period=channel["trend-period"],
                trend_function=channel["trend-function"],
                trend_func_kwargs=channel["trend-function-args"],
                trend_units=channel["trend-units"],
                trend_autoscale=channel["trend-autoscale"],
                trend_ymin=channel["trend-ymin"],
                trend_ymax=channel["trend-ymax"],
                alarm_enabled=channel["alarm-enabled"],
                alarm_low=channel["alarm-low"],
                alarm_high=channel["alarm-high"],
                alarm_sound_file=channel["alarm-sound-file"],
            )
            self._graphLayout.addItem(plot, i, 1)

        self.logBox = LogBox(
            path=config["log-path"],
            widget=self.logTextEdit,
            nb_measurements=len(config["channels"]),
        )

        ##
        # Configure acquisition system(s)
        ##
        self.__streams = []
        for acq_module in config["acquisition-modules"]:
            if acq_module["module-name"] not in AVAIL_ACQ_MODULES:
                # noinspection PyTypeChecker
                QMessageBox.critical(
                    None,
                    "Wrong acquisition module",
                    f'ERROR: wrong acquisition module {acq_module["module-name"]}.\n'
                    "Must be one of: " + ",".join(AVAIL_ACQ_MODULES.keys()),
                )
                raise ValueError("Wrong acquisition module in config file")
            acq_mod = AVAIL_ACQ_MODULES[acq_module["module-name"]]
            if acq_mod is None:
                raise ModuleNotFoundError(
                    f'ERROR: module {acq_module["module-name"]} cannot be loaded'
                )
            self.__streams.append(
                acq_mod(
                    sampling_rate=acq_module["sampling-rate"],
                    **acq_module["module-args"],
                )
            )

        ##
        # Serial port(s) for syringe pump
        ##
        self.serialPorts = [] if pump_serial_ports is None else pump_serial_ports
        ##
        # Syringe pump(s)
        ##
        self.pumps = [] if pumps is None else pumps

        for i, drug in enumerate(config["drug-list"]):
            if drug.pump is not None and self.pumps[drug.pump] is not None:
                panel = DrugPumpPanel(None, drug.name, drug.volume, pump=self.pumps[drug.pump],
                                      alarm_sound_file="./media/beep3x6.wav", main_window=self)
            else:
                panel = DrugPanel(
                    None,
                    drug.name,
                    drug.volume,
                    alarm_sound_filename="./media/beep3x6.wav",
                    main_window=self
                )
            self.drugPanelsLayout.addWidget(panel)

        # Timer with callback to update plots
        self.__refreshScopeTimer = QTimer()
        self.__refreshScopeTimer.timeout.connect(self.update)

        # Timer for dumping physio values to log_box
        self.__physioToLogTimer = QTimer()
        self.__physioToLogTimer.timeout.connect(self.write_physio_to_log)

        ##
        # Signals / Slots
        ##
        self.otherDrugButton.clicked.connect(self.add_new_drug)
        self.addNoteButton.clicked.connect(self.add_note)

    def start(self):
        for stream in self.__streams:
            stream.start()
        self.__refreshScopeTimer.start(50)
        self.__physioToLogTimer.start(
            self.config["measurements-output-period-min"] * 60 * 1000
        )
        for i in range(len(self._graphLayout.centralWidget.items)):
            plot = self._graphLayout.getItem(i, 1)
            plot.start()

    def update(self):
        data = [stream.read() for stream in self.__streams]
        for i in range(len(self._graphLayout.centralWidget.items)):
            plot: ScrollingScope = self._graphLayout.getItem(i, 1)
            d = data[plot.acquisition_module_index]
            if d is not None and np.asarray(d).size > 0:  # some data was returned
                d = d[plot.channel_index, :]
                plot.append(d)

    def get_physio_measurements(self) -> List:
        measurements = []
        for i in range(len(self._graphLayout.centralWidget.items)):
            plot: ScrollingScope = self._graphLayout.getItem(i, 1)
            if plot.trendEnabled:
                value = plot.getLastTrendData()
                measurements.append("{:.1f} {:s}".format(value, plot.getTrendUnits()))
            else:
                measurements.append("")
        return measurements

    def write_physio_to_log(self):
        self.write_to_log(self.get_physio_measurements())

    def write_to_log(self, measurements: typing.List, note=""):
        self.logBox.write_to_log(measurements, note)

    def add_note(self):
        text, ok = QInputDialog.getText(self, "Add a note to the log_box", "Note:")
        if ok and len(text) > 0:
            self.write_to_log(self.get_physio_measurements(), note=text)

    def add_new_drug(self):
        name, volume, ok = CustomDialog.get_drug_volume(
            self, name="", volume=0, add_inject=True
        )
        if ok == QDialog.Accepted or ok == QDialogButtonBox.YesToAll:
            new_panel = DrugPanel(
                None,
                drug_name=name,
                drug_volume=volume,
                main_window=self,
                alarm_sound_filename="media/beep3x6.wav",
            )
            self.drugPanelsLayout.addWidget(new_panel)
            if ok == QDialogButtonBox.YesToAll:
                new_panel.on_full_dose_button_click(None)

    def add_vline(self, legend):
        line_color = next(vline_color_iterator)
        for i in range(len(self._graphLayout.centralWidget.items)):
            plot: ScrollingScope = self._graphLayout.getItem(i, 1)
            if i == 0:  # only show the legend on the top plot
                plot.add_trend_vline(legend, color=line_color)
            else:
                plot.add_trend_vline("", color=line_color)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.__refreshScopeTimer.stop()
        self.__physioToLogTimer.stop()
        for stream in self.__streams:
            stream.close()
        event.accept()


def clear_layout(layout):
    while layout.count():
        child = layout.takeAt(0)
        if child.widget():
            child.widget().deleteLater()


class DrugPanel(QWidget):
    _fullDoseButton: QPushButton
    _halfDoseButton: QPushButton
    _customDoseButton: QPushButton
    _timer: DrugTimer
    _alarmButton: QPushButton
    _drugNameLabel: QLabel

    _drugName: str
    _drugVolume: float
    _main_window: PhysioMonitorMainScreen

    def __init__(
            self,
            parent,
            drug_name,
            drug_volume,
            alarm_sound_filename=None,
            main_window: PhysioMonitorMainScreen = None,
    ):
        super().__init__(parent)
        uic.loadUi("./GUI/DrugPanel.ui", self)

        self._LABEL_FORMAT = "{drugName} ({drugVolume:.0f} μL)"
        self._ALARM_LABEL_ON = "Alarm\n({:.0f} min)"
        self._ALARM_LABEL_OFF = "Set\nalarm"
        self._drugName = drug_name
        self._drugVolume = drug_volume
        self._injTime = None
        self._main_window = main_window

        self._drugNameLabel.setText(
            self._LABEL_FORMAT.format(
                drugName=self._drugName, drugVolume=self._drugVolume
            )
        )
        self._drugNameLabel.mouseDoubleClickEvent = self.on_drug_label_click
        self._timer.set_alarm_sound_file(alarm_sound_filename)

        ico = QIcon()
        ico.addFile("./media/alarm-clock-OFF.png", state=QIcon.Off)
        ico.addFile("./media/alarm-clock-ON.png", state=QIcon.On)
        self._alarmButton.setIcon(ico)
        self._alarmButton.setIconSize(QSize(20, 20))

        self._fullDoseButton.clicked.connect(self.on_full_dose_button_click)
        self._halfDoseButton.clicked.connect(self.on_half_dose_button_click)
        self._customDoseButton.clicked.connect(self.on_custom_dose_button_click)
        self._alarmButton.toggled.connect(self.on_choice_alarm)

    # noinspection DuplicatedCode
    def do_inject_drug(self, volume):
        output = self._LABEL_FORMAT.format(drugName=self._drugName, drugVolume=volume)
        if self._main_window is not None:
            self._main_window.write_to_log([], note=output)
        self._timer.reset(None)
        self._timer.start()

        self._main_window.add_vline(legend=self._drugName)

    # noinspection PyUnusedLocal
    def on_full_dose_button_click(self, event):
        self.do_inject_drug(self._drugVolume)

    # noinspection PyUnusedLocal
    def on_half_dose_button_click(self, event):
        self.do_inject_drug(self._drugVolume / 2)

    # noinspection PyUnusedLocal
    def on_custom_dose_button_click(self, event):
        val, ok = CustomDialog.get_double(
            self, value=self._drugVolume, text="Enter custom amount (μL)"
        )
        if ok:
            self.do_inject_drug(val)

    # noinspection PyUnusedLocal,DuplicatedCode
    def on_choice_alarm(self, event):
        if self._alarmButton.isChecked():
            val, ok = CustomDialog.get_time(
                self, value=self._timer.alarm_threshold, text="Time before alarm"
            )
            if ok:
                self._timer.set_alarm_threshold_in_minutes(val)
                self._alarmButton.setText(self._ALARM_LABEL_ON.format(val))
            else:
                self._alarmButton.setChecked(False)
        else:
            self._timer.set_alarm_threshold_in_minutes(None)
            self._alarmButton.setText(self._ALARM_LABEL_OFF)

    # noinspection PyUnusedLocal
    def on_drug_label_click(self, event):
        drug_name, drug_volume, ok = CustomDialog.get_drug_volume(
            self, self._drugName, self._drugVolume
        )
        if ok == QDialog.Accepted:
            self._drugName = drug_name
            self._drugVolume = drug_volume
            self._drugNameLabel.setText(
                self._LABEL_FORMAT.format(
                    drugName=self._drugName, drugVolume=self._drugVolume
                )
            )


class DrugPumpPanel(QWidget):
    _fullDoseButton: QPushButton
    _halfDoseButton: QPushButton
    _customDoseButton: QPushButton
    _timer: PumpTimer
    _alarmButton: QPushButton
    _drugNameLabel: QLabel
    _autoInjectCheckBox: QCheckBox
    _perfRateSpinBox: QDoubleSpinBox
    _perfUnitComboBox: QComboBox
    _startPerfButton: QPushButton
    _pumpLabel: QLabel
    _waitThread: threading.Thread

    def __init__(self, parent, drug_name, drug_volume, pump: SyringePumps.SyringePump, alarm_sound_file=None,
                 main_window: PhysioMonitorMainScreen = None):
        super().__init__(parent)
        uic.loadUi("./GUI/DrugPumpPanel.ui", self)

        drug_volume = float(drug_volume)
        self._LABEL_FORMAT = "{drugName} ({drugVolume:.1f} μL)"
        self._ALARM_LABEL_ON = "Alarm\n({:.0f} min)"
        self._ALARM_LABEL_OFF = "Set\nalarm"
        self._drugName = drug_name
        self._drugVolume = drug_volume
        self._injTime = None
        self._main_window = main_window

        self._drugNameLabel.setText(
            self._LABEL_FORMAT.format(
                drugName=self._drugName, drugVolume=self._drugVolume
            )
        )
        self._drugNameLabel.mouseDoubleClickEvent = self.on_drug_label_click
        self._timer.setup(
            pump_panel=self, alarm_threshold=None, alarm_sound_file=alarm_sound_file
        )

        ico = QIcon()
        ico.addFile("./media/alarm-clock-OFF.png", state=QIcon.Off)
        ico.addFile("./media/alarm-clock-ON.png", state=QIcon.On)
        self._alarmButton.setIcon(ico)
        self._alarmButton.setIconSize(QSize(20, 20))

        self._fullDoseButton.clicked.connect(self.on_full_dose_button_click)
        self._halfDoseButton.clicked.connect(self.on_half_dose_button_click)
        self._customDoseButton.clicked.connect(self.on_custom_dose_button_click)
        self._alarmButton.toggled.connect(self.on_choice_alarm)

        self._START_PERF_FORMAT = ">> Start perf {drugName} ({rate:.2f} {units})"
        self._STOP_PERF_FORMAT = "<< End perf\t{drugName}"
        self._pump = pump
        self._drugName = drug_name
        self._drugVolume = drug_volume
        self._injTime = None
        self._timer.setup(pump_panel=self, alarm_sound_file=alarm_sound_file)
        self._pumpLabel.setText(self._pump.display_name)

        # FIXME: this does not work??
        for widget in [
            self._autoInjectCheckBox,
            self._fullDoseButton,
            self._halfDoseButton,
            self._startPerfButton,
        ]:
            widget.setStyle(IconProxyStyle(widget.style()))
        self._perfRateSpinBox.setMinimum(self._pump.min_val)
        self._perfRateSpinBox.setMaximum(self._pump.max_val)

        self._abortInjectButton = QPushButton("Abort", parent=self)
        self._abortInjectButton.setIcon(
            self.style().standardIcon(QStyle.SP_BrowserStop)
        )
        self._abortInjectButton.setVisible(False)
        self._abortInjectButton.clicked.connect(self.abort_injection)

        self._startPerfButton.toggled.connect(self.on_toggle_perf)
        self._autoInjectCheckBox.toggled.connect(self.on_toggle_auto_inject)

        self._perfUnitComboBox.addItems(self._pump.get_possible_units())
        self.update_from_pump()

    def on_toggle_perf(self):
        if self._pump.is_running():
            self._pump.stop()
            self._main_window.write_to_log(
                [], note=self._STOP_PERF_FORMAT.format(drugName=self._drugName)
            )
            self._main_window.add_vline(f"STOP: {self._drugName}")
        else:
            try:
                self._pump.set_rate(
                    self._perfRateSpinBox.value(), self._perfUnitComboBox.currentIndex()
                )
                self._pump.clear_target_volume()
                self._pump.start()
                note = self._START_PERF_FORMAT.format(
                    drugName=self._drugName,
                    rate=self._perfRateSpinBox.value(),
                    units=self._perfUnitComboBox.currentText(),
                )
                self._main_window.write_to_log(
                    [],
                    note=note
                )
                self._main_window.add_vline(note)
            except SyringePumps.SyringePumpValueOORException:
                # noinspection PyTypeChecker
                QMessageBox.information(
                    None, "Value OOR", "ERROR: value is out of range for pump"
                )
                self._perfRateSpinBox.setFocus()
        self.update_from_pump()

    def on_toggle_auto_inject(self, checked):
        self._timer.auto_inject = checked

    def update_from_pump(self):
        curr_rate = self._pump.get_rate()
        curr_units = self._pump.get_units()
        self._perfRateSpinBox.setValue(curr_rate)
        self._perfUnitComboBox.setCurrentIndex(curr_units)
        if not self._pump.is_running():
            self._startPerfButton.setChecked(False)
            self.enable_perfusion_buttons(True)
        else:
            self._startPerfButton.blockSignals(True)
            self._startPerfButton.setChecked(True)
            self._startPerfButton.blockSignals(False)
            self.enable_perfusion_buttons(False)

    # noinspection DuplicatedCode
    def do_inject_drug(self, volume):
        # in case the pump is currently infusing, we store the current values to restore after the
        # end of the injection
        curr_rate = self._pump.get_rate()
        if not self._pump.is_running():
            curr_dir = self._pump.STATE.STOPPED
        else:
            curr_dir = self._pump.get_direction()
        curr_units = self._pump.get_units()

        try:
            if self._pump.is_running():
                self._pump.stop()
            self._pump.set_direction(self._pump.STATE.INFUSING)
            self._pump.set_rate(self._pump.bolus_rate, self._pump.bolus_rate_units)
            self._pump.set_target_volume_uL(volume)
            self._pump.start()
        except SyringePumps.SyringePumpValueOORException:
            # noinspection PyTypeChecker
            QMessageBox.warning(
                None, "Value out of range", "Cannot inject, value out of range"
            )
            return

        output = self._LABEL_FORMAT.format(drugName=self._drugName, drugVolume=volume)
        self._main_window.write_to_log([], note=output)
        self._main_window.add_vline(legend=self._drugName)
        self._timer.start()
        # disable buttons to avoid double injections, and start a thread to wait for the injection
        # to finish
        self.enable_inject_buttons(False)
        self._waitThread = threading.Thread(
            target=self.wait_for_end_of_injection,
            args=(curr_rate, curr_units, curr_dir),
        )
        self._waitThread.start()

    # noinspection PyUnusedLocal
    def on_full_dose_button_click(self, event):
        self.do_inject_drug(self._drugVolume)

    # noinspection PyUnusedLocal
    def on_half_dose_button_click(self, event):
        self.do_inject_drug(self._drugVolume / 2)

    # noinspection PyUnusedLocal
    def on_custom_dose_button_click(self, event):
        val, ok = CustomDialog.get_double(
            self, value=self._drugVolume, text="Enter custom amount (μL)"
        )
        if ok:
            self.do_inject_drug(val)

        # noinspection PyUnusedLocal

    # noinspection PyUnusedLocal,DuplicatedCode
    def on_choice_alarm(self, event):
        if self._alarmButton.isChecked():
            val, ok = CustomDialog.get_time(
                self, value=self._timer.alarm_threshold, text="Time before alarm"
            )
            if ok:
                self._timer.set_alarm_threshold_in_minutes(val)
                self._alarmButton.setText(self._ALARM_LABEL_ON.format(val))
            else:
                self._alarmButton.setChecked(False)
        else:
            self._timer.set_alarm_threshold_in_minutes(None)
            self._alarmButton.setText(self._ALARM_LABEL_OFF)

    def enable_inject_buttons(self, enabled: bool):
        self._fullDoseButton.setEnabled(enabled)
        self._halfDoseButton.setEnabled(enabled)
        self._customDoseButton.setEnabled(enabled)
        # show the abort button
        geom = (
            self._fullDoseButton.geometry()
            .united(self._halfDoseButton.geometry())
            .united(self._customDoseButton.geometry())
        )
        self._abortInjectButton.setGeometry(geom)
        self._abortInjectButton.setVisible(not enabled)

    def enable_perfusion_buttons(self, enabled: bool):
        self._perfRateSpinBox.setEnabled(enabled)
        self._perfUnitComboBox.setEnabled(enabled)

    # noinspection PyUnusedLocal
    def abort_injection(self, event):
        if self._pump.is_running():
            self._pump.stop()
        while self._waitThread.is_alive():
            # wait for thread to finish
            time.sleep(0.01)
        self.enable_inject_buttons(True)

    def wait_for_end_of_injection(self, restore_rate, restore_units, restore_dir):
        # logger.debug("in waitForEndOfInjection()")
        while self._pump.is_running():
            time.sleep(0.1)
            pass
            logger.debug("pump is still running")
        logger.debug("pump is finished pumping")
        self.enable_inject_buttons(True)
        logger.debug("restoring previous pump state")
        self._pump.set_rate(restore_rate, restore_units)
        if not restore_dir == self._pump.STATE.STOPPED:
            self._pump.set_direction(restore_dir)
            self._pump.clear_target_volume()
            self._pump.start()
        self.update_from_pump()

    # noinspection PyUnusedLocal
    def on_drug_label_click(self, event):
        pos = event.globalPos()
        # dlg = QDialog()
        # layout = QVBoxLayout()
        # widget = PumpConfigPanel(pump=self._pump)
        # buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        # layout.addWidget(widget)
        # layout.addWidget(buttons)
        # dlg.setLayout(layout)
        # dlg.move(pos)
        # buttons.accepted.connect(dlg.accept)
        # dlg.exec()
        dlg = EditDrugPumpDialog(
            None, self._drugName, self._drugVolume, self._pump, pos=pos
        )
        ok = dlg.exec()
        if ok == QDialog.Accepted:
            self._drugName = dlg.drugNameEdit.text()
            self._drugVolume = dlg.drugVolumeSpinBox.value()
            self._drugNameLabel.setText(
                self._LABEL_FORMAT.format(
                    drugName=self._drugName, drugVolume=self._drugVolume
                )
            )


class StartDialog(QDialog):
    expInvestigatorComboBox: QComboBox
    subjectDoBBox: QDateEdit
    subjectSexButtonGroup: QButtonGroup
    subjectWeightSpinBox: QSpinBox
    subjectGenotypeComboBox: QComboBox
    subjectCommentsTextEdit: QTextEdit
    drugTable: QTableView
    editDrugButton: QPushButton
    addDrugButton: QPushButton
    delDrugButton: QPushButton
    buttonBox: QDialogButtonBox
    pumpComboBox: QComboBox
    pumpPanelFrame: QFrame

    def __init__(self, config, prev_values_file):
        super().__init__()
        uic.loadUi("./GUI/StartScreen.ui", self)
        self.setWindowIcon(QIcon("../media/icon.png"))
        self.config = config
        self._prev_values_file = prev_values_file

        self.buttonBox.button(QDialogButtonBox.Ok).setIcon(
            QApplication.style().standardIcon(QStyle.SP_DialogOkButton)
        )
        self.buttonBox.button(QDialogButtonBox.Cancel).setIcon(
            QApplication.style().standardIcon(QStyle.SP_DialogCancelButton)
        )

        if "syringe-pump" in self.config:
            ##
            # Serial port(s) for syringe pump
            ##
            self.serialPorts = []
            if "serial-ports" in self.config["syringe-pump"]:
                for serial_conf in self.config["syringe-pump"]["serial-ports"]:
                    try:
                        ser = serial.Serial(**serial_conf)
                    except serial.SerialException:
                        ser = None
                    if ser is None:
                        # noinspection PyTypeChecker
                        QMessageBox.warning(
                            None,
                            "Serial port error",
                            'Cannot open serial port "{:s}"!\n'
                            "Serial connection will not be available".format(
                                serial_conf["port"]
                            ),
                        )
                    self.serialPorts.append(ser)

            ##
            # Syringe pump(s)
            ##
            self.pumps = []
            if "pumps" in self.config["syringe-pump"]:
                for pump_conf in self.config["syringe-pump"]["pumps"]:
                    model = pump_conf["module-name"]
                    if model not in AVAIL_PUMP_MODULES:
                        raise ValueError(
                            f'Invalid module "{model}". Must be one of {", ".join(AVAIL_PUMP_MODULES.keys())}'
                        )
                    model = AVAIL_PUMP_MODULES[model]
                    pump = None
                    # sometimes, it takes a couple of tries for the pump to answer,
                    # so we'll try in a loop and test if it was successful
                    success = False
                    while not success:
                        for _ in range(3):
                            try:
                                pump = model(
                                    display_name=pump_conf["display-name"],
                                    serial_port=self.serialPorts[pump_conf["serial-port"]],
                                    **pump_conf["module-args"],
                                )
                                pump.is_running()  # check that pump is working, should raise Exception if not
                                success = True
                                break
                            except SyringePumpException:
                                pump = None
                        if not success:
                            # noinspection PyTypeChecker
                            ans = QMessageBox.question(
                                None,
                                "Pump not responding",
                                f"Cannot communicate with the pump {model}, maybe it is off?\nRetry?",
                            )
                            if ans == QMessageBox.No:
                                success = True
                    self.pumps.append(pump)

        # load previous values to pre-populate dialog
        try:
            with open(self._prev_values_file, "r", encoding="utf-8") as f:
                prev_values: dict = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            prev_values = {}
        if "genotypes" not in prev_values.keys():
            prev_values["genotypes"] = []
        if "drugs" not in prev_values.keys():
            prev_values["drugs"] = []
        temp = [
            Drug(
                name=drug["_name"],
                dose=drug["_dose"],
                concentration=drug["_concentration"],
                volume=drug["_volume"],
                pump=drug["_pump"],
            )
            for drug in prev_values["drugs"]
        ]
        prev_values["drugs"] = temp

        if "pumps" in prev_values.keys():
            for prev_pump, pump in zip(prev_values["pumps"], self.pumps):
                pump.bolus_rate = prev_pump["bolus_rate"]
                pump.bolus_rate_units = prev_pump["bolus_rate_units"]

        self.subject = Subject()
        self.drugList = prev_values["drugs"]

        self.saveFolder = os.path.normpath(self.config["base-folder"])
        if self.config["create-sub-folder"]:
            self.saveFolder = os.path.join(
                self.saveFolder, datetime.date.today().isoformat()
            )
        if "log-filename" not in self.config:
            self.log_path = os.path.join(self.saveFolder, "LOGFILE.TXT")
        else:
            self.log_path = os.path.join(self.saveFolder, self.config["log-filename"])
        self.config["log-path"] = self.log_path

        self.isResumed = False
        if os.path.isfile(self.log_path):
            # we already have a surgical log file in the folder, ask whether to resume
            # noinspection PyTypeChecker
            dlg = QMessageBox.question(
                None,
                "Previous session detected",
                "Do you want to resume the previous session?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if dlg == QMessageBox.Yes:
                subject, drugs = LogBox.parse(self.log_path)
                if subject is None:
                    # noinspection PyTypeChecker
                    QMessageBox.information(
                        None, "Could not parse", "Failed to parse previous log file."
                    )
                else:
                    self.subject = subject
                    self.drugList = drugs
                    self.isResumed = True

        # SUBJECT TAB
        # noinspection PyTypeChecker
        for but, butId in zip(self.subjectSexButtonGroup.buttons(), Sex):
            self.subjectSexButtonGroup.setId(but, butId)
        self.subjectDoBBox.setDate(
            QDate(self.subject.dob.year, self.subject.dob.month, self.subject.dob.day)
        )
        self.subjectSexButtonGroup.button(self.subject.sex).setChecked(True)
        self.subjectWeightSpinBox.setValue(self.subject.weight)
        self.subjectGenotypeComboBox.setModel(
            QStringListModel()
        )  # Convenient to get a list of strings at the end
        self.subjectGenotypeComboBox.addItems(prev_values["genotypes"])
        exists_id = self.subjectGenotypeComboBox.findText(self.subject.genotype)
        if exists_id >= 0:
            self.subjectGenotypeComboBox.removeItem(exists_id)
        self.subjectGenotypeComboBox.insertItem(-1, self.subject.genotype)
        self.subjectGenotypeComboBox.setCurrentIndex(0)
        self.subjectCommentsTextEdit.setText(self.subject.comments)

        # DRUG LIST TAB
        self.tableModel = DrugTableModel(data=self.drugList, pumps=self.pumps)
        self.drugTable.setModel(self.tableModel)

        self.drugTable.doubleClicked.connect(self.edit_entry)
        self.editDrugButton.clicked.connect(self.edit_entry)
        self.addDrugButton.clicked.connect(self.add_entry)
        self.delDrugButton.clicked.connect(self.remove_entry)
        for i in range(1, self.tableModel.columnCount()):
            self.drugTable.horizontalHeader().setSectionResizeMode(
                i, QHeaderView.ResizeToContents
            )
        self.drugTable.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        # PUMPS TAB
        if len([p for p in self.pumps if p is not None]) > 0:
            self.pumpComboBox.clear()
            self.pumpComboBox.addItems(
                [p.display_name for p in self.pumps if p is not None]
            )
            self.pumpComboBox.currentIndexChanged.connect(self.on_pump_combo_changed)
            self.on_pump_combo_changed(0)  # populate with first item in list

    def on_pump_combo_changed(self, index):
        for idx, p in enumerate([q for q in self.pumps if q is not None]):
            self.pumpComboBox.setItemText(idx, p.display_name)
        clear_layout(self.pumpPanelFrame.layout())
        pumps = [p for p in self.pumps if p is not None]
        panel = PumpConfigPanel(pump=pumps[index])
        self.pumpPanelFrame.layout().addWidget(panel)

    def add_entry(self):
        name, dose, concentration, volume, pump, ok = DrugEditDialog.get_drug_data(
            pumps=[p.display_name for p in self.pumps]
        )
        if ok:
            new_drug = Drug(
                name=name,
                dose=dose,
                concentration=concentration,
                volume=volume,
                pump=pump,
            )
            new_row = self.tableModel.rowCount()
            self.tableModel.insertRows(new_row)

            for i, field in enumerate(self.tableModel.FIELDS):
                new_row = self.tableModel.rowCount() - 1
                ix = self.tableModel.index(new_row, i, QModelIndex())
                self.tableModel.setData(ix, getattr(new_drug, field), Qt.EditRole)

    def edit_entry(self):
        selection_model = self.drugTable.selectionModel()
        indexes = selection_model.selectedRows()

        for index in indexes:
            row = index.row()
            drug_data = []
            for i in range(self.tableModel.columnCount()):
                ix = self.tableModel.index(row, i, QModelIndex())
                drug_data.append(self.tableModel.data(ix, Qt.EditRole))
            name, dose, concentration, volume, pump, ok = DrugEditDialog.get_drug_data(
                *drug_data, pumps=[p.display_name for p in self.pumps]
            )
            if ok:
                for j, field in enumerate([name, dose, concentration, volume, pump]):
                    ix = self.tableModel.index(row, j, QModelIndex())
                    self.tableModel.setData(ix, field, Qt.EditRole)

    def remove_entry(self):
        selection_model = self.drugTable.selectionModel()
        indexes = selection_model.selectedRows()

        for index in indexes:
            self.drugTable.model().removeRows(index.row(), 1)

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
        text = self.subjectGenotypeComboBox.lineEdit().text()
        pos = self.subjectGenotypeComboBox.findText(text)
        if pos >= 0:
            self.subjectGenotypeComboBox.removeItem(pos)
        self.subjectGenotypeComboBox.insertItem(0, text)

        # save data
        self.subject.genotype = self.subjectGenotypeComboBox.itemText(0)
        if self.subjectSexButtonGroup.checkedId() == Sex.MALE:
            self.subject.sex = Sex.MALE
        elif self.subjectSexButtonGroup.checkedId() == Sex.FEMALE:
            self.subject.sex = Sex.FEMALE
        else:
            self.subject.sex = Sex.UNKNOWN
        self.subject.weight = self.subjectWeightSpinBox.value()
        self.subject.dob = self.subjectDoBBox.date().toPyDate()
        self.subject.comments = self.subjectCommentsTextEdit.toPlainText()

        self.config["drug-list"] = self.drugList

        # save the lists genotypes/investigators/drugs upon accepting,
        # so they can be reloaded next time
        out = {
            "genotypes": self.subjectGenotypeComboBox.model().stringList(),
            "drugs": [drug.__dict__ for drug in self.drugList],
            "pumps": [
                {
                    "bolus_rate": pump.bolus_rate,
                    "bolus_rate_units": pump.bolus_rate_units,
                }
                for pump in self.pumps
            ],
        }
        with open(self._prev_values_file, "w", encoding="utf-8") as f:
            json.dump(out, f)

        super().accept()


class PumpConfigPanel(QWidget):
    diameterSpinBox: QDoubleSpinBox
    bolusRateSpinBox: QDoubleSpinBox
    bolusRateComboBox: QComboBox
    doPrimeButton: QPushButton
    primeFlowRateComboBox: QComboBox
    primeFlowRateSpinBox: QDoubleSpinBox
    primeProgressBar: QProgressBar
    primeTargetVolSpinBox: QDoubleSpinBox

    def __init__(self, pump: SyringePump):
        super().__init__()
        uic.loadUi("./GUI/SyringePumpPanel.ui", self)
        self.pump = pump
        self._waitThread = threading.Thread()
        self.refresh()
        self.doPrimeButton.clicked.connect(self.on_prime_toggled)
        self.diameterSpinBox.editingFinished.connect(self.update_pump)
        self.bolusRateSpinBox.editingFinished.connect(self.update_pump)
        self.bolusRateComboBox.currentIndexChanged.connect(self.update_pump)
        self.primeFlowRateComboBox.currentIndexChanged.connect(self.update_pump)
        self.primeFlowRateSpinBox.editingFinished.connect(self.update_pump)
        self.primeTargetVolSpinBox.editingFinished.connect(self.update_pump)

    def refresh(self):
        possible_units = self.pump.get_possible_units()
        self.bolusRateComboBox.clear()
        self.bolusRateComboBox.addItems(possible_units)
        self.primeFlowRateComboBox.clear()
        self.primeFlowRateComboBox.addItems(possible_units)

        self.diameterSpinBox.setValue(self.pump.get_diameter_mm())
        self.bolusRateSpinBox.setValue(self.pump.bolus_rate)
        self.bolusRateComboBox.setCurrentIndex(self.pump.bolus_rate_units)
        self.primeTargetVolSpinBox.setValue(self.pump.get_target_volume_uL() / 1e3)
        self.primeFlowRateSpinBox.setValue(self.pump.get_rate())
        self.primeFlowRateComboBox.setCurrentIndex(self.pump.get_units())

    # noinspection PyUnusedLocal
    def update_pump(self, event=None):
        # we use this function with editingFinished, which sends no arguments
        # and with currentIndexChanged, which sends an argument, so we provide a default value for the argument
        self.pump.bolus_rate = self.bolusRateSpinBox.value()
        self.pump.bolus_rate_units = self.bolusRateComboBox.currentIndex()
        self.pump.set_rate(
            self.primeFlowRateSpinBox.value(), self.primeFlowRateComboBox.currentIndex()
        )
        self.pump.set_target_volume_uL(self.primeTargetVolSpinBox.value() * 1e3)

    # noinspection PyUnusedLocal
    def on_prime_toggled(self, clicked):
        if clicked:
            try:
                if self.pump.is_running():
                    self.pump.stop()
                    # wait for thread to finish
                    while self._waitThread.is_alive():
                        time.sleep(0.1)
                self.pump.set_direction(SyringePump.STATE.INFUSING)
                self.pump.clear_accumulated_volume()
                self.pump.set_rate(
                    self.primeFlowRateSpinBox.value(),
                    self.primeFlowRateComboBox.currentIndex(),
                )
                self.pump.set_target_volume_uL(
                    self.primeTargetVolSpinBox.value() * 1e3
                )  # volume is in uL but dlg box is in mL
                self.pump.start()
            except SyringePumps.SyringePumpValueOORException:
                # noinspection PyTypeChecker
                QMessageBox.warning(
                    None, "Value out of range", "Cannot inject, value out of range"
                )
                self.primeFlowRateSpinBox.setFocus()

            if self.primeTargetVolSpinBox.value() > 0:
                # if target vol is zero, continuous perfusion, so we don't run the
                # progress bar and don't wait for the perfusion to end.
                self.primeProgressBar.setValue(0)
                self._waitThread = threading.Thread(
                    target=self.wait_for_end_of_injection,
                    args=(),
                )
                self._waitThread.start()
        else:
            if self.pump.is_running():
                self.pump.stop()
                # wait for thread to finish
                while self._waitThread.is_alive():
                    time.sleep(0.1)
            self.enable_prime_controls(True)

    def wait_for_end_of_injection(
            self,
    ):
        while self.pump.is_running():
            self.primeProgressBar.setValue(
                round(
                    100
                    * self.pump.get_accumulated_volume_uL()
                    / (
                            self.primeTargetVolSpinBox.value() * 1e3
                    )  # convert mL for dialog box to uL
                )
            )
            time.sleep(0.1)

        # return to zero when finished
        self.primeProgressBar.setValue(0)
        self.doPrimeButton.setChecked(False)
        self.enable_prime_controls(True)

    def enable_prime_controls(self, enabled: bool):
        self.primeTargetVolSpinBox.setEnabled(enabled)
        self.primeFlowRateSpinBox.setEnabled(enabled)
        self.primeFlowRateComboBox.setEnabled(enabled)
