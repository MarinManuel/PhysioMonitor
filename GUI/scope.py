# -*- coding: utf-8 -*-
import collections
import itertools
import logging
import os

import numpy as np
import pygame
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QMenu,
    QAction,
    QFormLayout,
    QDoubleSpinBox,
    QWidget,
    QWidgetAction,
)
from PyQt5 import QtCore, QtGui

from sampling.buffers import RollingBuffer

BACKGROUND_COLOR = (226, 226, 226)
AXES_COLOR = (0, 0, 0)

# these are the colors from matplotlib tab20 colormap
vline_colors = [
    (31., 119., 180.),
    (174., 199., 232.),
    (255., 127., 14.),
    (255., 187., 120.),
    (44., 160., 44.),
    (152., 223., 138.),
    (214., 39., 40.),
    (255., 152., 150.),
    (148., 103., 189.),
    (197., 176., 213.),
    (140., 86., 75.),
    (196., 156., 148.),
    (227., 119., 194.),
    (247., 182., 210.),
    (127., 127., 127.),
    (199., 199., 199.),
    (188., 189., 34.),
    (219., 219., 141.),
    (23., 190., 207.),
    (158., 218., 229.)]
vline_color_iterator = itertools.cycle(vline_colors)

pg.setConfigOption("background", BACKGROUND_COLOR)
pg.setConfigOption("foreground", AXES_COLOR)
pg.setConfigOptions(
    antialias=False
)  # WARNING: setting to True could slow down execution

# if it hasn't been already, initialize the sound mixer
if pygame.mixer.get_init() is None:
    pygame.mixer.pre_init(44100, -16, 2, 2048)
    pygame.mixer.init()

logger = logging.getLogger(__name__)


class ScrollingScope(pg.PlotItem):
    def __init__(
            self,
            acquisition_module_index=0,
            channel_index=0,
            window_size=30,  # in secs
            sample_freq=1000,  # in Hz
            bg_color="w",
            line_color="b",
            line_width=2.0,
            scaling=1.0,
            offset=0.0,
            title="plot",
            units="V",
            autoscale=True,
            ymin=0.0,
            ymax=1.0,
            trend_line_color="r",
            trend_line_width=3,
            trend_window_size=30 * 60,  # in seconds
            trend_period=30,  # in seconds
            trend_function=None,
            trend_func_kwargs=None,
            trend_units="",
            trend_autoscale=False,
            trend_ymin=0.0,
            trend_ymax=1.0,
            alarm_enabled=False,
            alarm_low=0.0,
            alarm_high=1.0,
            alarm_sound_file=None,
            alarm_bg_color=(255, 255, 200),
            *args,
            **kwargs
    ):
        super(ScrollingScope, self).__init__(*args, **kwargs)
        self._acqModIdx = acquisition_module_index
        self._channelIdx = channel_index
        self._windowSize = window_size
        self._sampleFreq = sample_freq
        self._bgColor = bg_color
        self._lineColor = line_color
        self._lineWidth = line_width
        self._scaling = scaling
        self._offset = offset
        self._title = title
        self._units = units
        self._autoscale = autoscale
        self._ymin = ymin
        self._ymax = ymax
        self._trendLineColor = trend_line_color
        self._trendLineWidth = trend_line_width
        self._trendWindowSize = trend_window_size
        self._trendPeriod = trend_period
        self._trendFunction = self._selectTrendFunction(trend_function)
        self._trendFuncKwargs = trend_func_kwargs
        self._trendUnits = trend_units
        self._trendAutoscale = trend_autoscale
        self._trendYmin = trend_ymin
        self._trendYmax = trend_ymax
        self._alarmEnabled = alarm_enabled
        self._alarmLow = alarm_low
        self._alarmHigh = alarm_high
        self._alarmTripped = False
        self._alarmMuted = False
        self._alarmBGColor_alarm = alarm_bg_color
        if alarm_sound_file is not None and os.path.isfile(alarm_sound_file):
            self._alarmSound = pygame.mixer.Sound(alarm_sound_file)
        else:
            self._alarmSound = None

        self._bufferSize = int(window_size * sample_freq)
        self._buffer = np.zeros((self._bufferSize,))
        self._xArray = np.linspace(0, self._windowSize, num=self._bufferSize)
        self._curve = self.plot(x=self._xArray, y=self._buffer)
        self._leftAxis = self.getAxis("left")
        self._rightAxis = self.getAxis("right")
        self._bottomAxis = self.getAxis("bottom")
        self._topAxis = self.getAxis("top")

        # Disable mouse interaction on both axes
        self.vb.setMouseEnabled(x=False, y=False)
        # Monkey-patch the mouseClickEvent function in ViewBox with our own.
        # That way, we can disable right-click menu (or do whatever we want)
        self.vb.menu = None
        self.vb.menu = self._createMenu()
        self.vb.raiseContextMenu = self._raiseContextMenu
        # Remove the auto-scale button
        self.hideButtons()
        # Disable auto-scaling on all axes
        self.vb.enableAutoRange(enable=False)
        # Unless it is explicitly requested on the Y axis
        if self._autoscale:
            self.vb.enableAutoRange(axis=self.vb.YAxis)
        else:
            self.vb.setYRange(self._ymin, self._ymax, padding=0)
        self.getAxis("left").setStyle(
            autoExpandTextSpace=False, autoReduceTextSpace=False
        )
        self.vb.setXRange(0.0, self._windowSize, padding=0)
        self.setLabel(axis="left", text=self._title, units=self._units)
        self._curve.setPen({"color": self._lineColor, "width": self._lineWidth})
        self.setBackgroundColor(self._bgColor)
        self._leftAxis.setGrid(150)

        #
        # init Trend Plot
        #
        self._trendBuffer = RollingBuffer(size=self._trendPeriod * self._sampleFreq)
        self._trendData = np.zeros((round(self._trendWindowSize / self._trendPeriod),))
        self._trendXArray = np.linspace(
            0.0, self._trendWindowSize, num=self._trendData.size
        )

        self._trendVB = pg.ViewBox()
        self.showAxis("right")
        self.getAxis("right").setStyle(
            autoExpandTextSpace=False, autoReduceTextSpace=False
        )
        # self.showAxis('top')
        #  I'm not showing the top axis because it's taking a lot of screen real-estate,
        # and it's not really useful anyway
        # self.scene().addItem(self._trendVB)
        # According to the example I'm following, I need to do this to add the second axis,
        # but it does not work at this stage, because the scene() has
        # not been created yet. Delaying this to the showEvent() method
        self._trendAxis = self._rightAxis
        self._trendAxis.linkToView(self._trendVB)
        self._topAxis.linkToView(self._trendVB)
        self._trendCurve = pg.PlotDataItem(self._trendXArray, self._trendData)
        self._trendCurve.setPen(
            {"color": self._trendLineColor, "width": self._trendLineWidth}
        )
        self._trendCurve.setZValue(10)
        self._trendVB.addItem(self._trendCurve)
        self._trendVB.setMouseEnabled(x=False, y=False)
        self._trendVB.setMenuEnabled(False)
        self._trendVB.setXRange(0.0, self._trendWindowSize, padding=0)
        # Disable auto-scaling on all axes
        self._trendVB.enableAutoRange(enable=False)
        # Unless it is explicitly requested on the Y axis
        if self._trendAutoscale:
            self._trendVB.enableAutoRange(axis=self._trendVB.YAxis)
        else:
            self._trendVB.setYRange(self._trendYmin, self._trendYmax, padding=0)
        # we connect a function that is called whenever the window is resized
        # to keep the two plots in sync
        self.vb.sigResized.connect(self.onResize)
        # measurement display
        self._trendText = pg.TextItem(
            text="{:.1f} {!s}".format(0.0, self._trendUnits),
            color=self._trendLineColor,
            anchor=(1, 1),
        )
        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(18)
        self._trendText.setFont(font)
        # position the label at lower right
        self._trendText.setPos(
            self._trendVB.viewRange()[0][1], self._trendVB.viewRange()[1][0]
        )
        self._trendText.setVisible(self.trendEnabled)
        self._trendVB.addItem(self._trendText)
        self._trendAxis.setTextPen({"color": self._trendLineColor})
        self._trendTimer = QtCore.QTimer()
        # noinspection PyUnresolvedReferences
        self._trendTimer.timeout.connect(self.onTrendTimer)

        #
        # Trend vlines
        #
        self._trend_vlines = []

        self._alarmLineHigh = pg.InfiniteLine(
            pos=self._alarmHigh,
            angle=0,
            movable=False,
            pen=pg.mkPen("r", width=2, style=QtCore.Qt.DashLine),
        )
        self._alarmLineLow = pg.InfiniteLine(
            pos=self._alarmLow,
            angle=0,
            movable=False,
            pen=pg.mkPen("r", width=2, style=QtCore.Qt.DashLine),
        )
        self._trendVB.addItem(self._alarmLineHigh)
        self._trendVB.addItem(self._alarmLineLow)
        self._alarmLineHigh.setVisible(self._alarmEnabled & self.trendEnabled)
        self._alarmLineLow.setVisible(self._alarmEnabled & self.trendEnabled)
        self._muteButton = pg.TextItem(
            text="[muted]", color=self._trendLineColor, anchor=(1, 0)
        )
        self._muteButton.setFont(font)
        # position the label at upper right
        self._muteButton.setPos(
            self._trendVB.viewRange()[0][1], self._trendVB.viewRange()[1][1]
        )
        self._trendVB.addItem(self._muteButton)
        self._muteButton.setVisible(False)

    def showEvent(self, event):
        super(ScrollingScope, self).showEvent(event)
        self.scene().addItem(self._trendVB)

    def start(self):
        self._trendTimer.start(self._trendPeriod * 1000)

    def onResize(self):
        self._trendVB.setGeometry(self.vb.sceneBoundingRect())

    def onTrendTimer(self):
        # logger.debug("in ScrollingPlot.onTrendTimer()")
        if self.trendEnabled:
            ret_val = self._trendFunction(
                self._trendBuffer.values().flatten(), **self._trendFuncKwargs
            )
            self._trendText.setPlainText("{:.1f} {!s}".format(ret_val, self._trendUnits))
            self._trendData = np.roll(
                self._trendData, -1
            )  # shifts data along axis 1 N points to the left
            self._trendData[-1:] = ret_val
            self._trendCurve.setData(x=self._trendXArray, y=self._trendData)

            # move the trend_vlines
            for vline in self._trend_vlines:
                vline: pg.InfiniteLine
                old_x = vline.value()
                new_x = old_x - self._trendPeriod
                vline.setValue(new_x)

            # deal with alarm conditions
            if self.alarmEnabled:
                if ret_val > self._alarmHigh and not np.isnan(ret_val):
                    if not self._alarmTripped:
                        # logger.debug(
                        #     "Trend value reached %.2f, which is > %.2f. Tripping alarm" % (ret_val, self.alarmHigh))
                        self.tripAlarm()
                elif ret_val < self._alarmLow and not np.isnan(ret_val):
                    if not self._alarmTripped:
                        # logger.debug(
                        #     "Trend value reached %.2f, which is < %.2f. Tripping alarm" % (ret_val, self.alarmLow))
                        self.tripAlarm()
                else:
                    # value is between alarmLow and alarmHigh
                    if self._alarmTripped:
                        # logger.debug(
                        #     "Trend value: %.2f > %.2f > %.2f. resetting alarm" %
                        #     (self.alarmLow, ret_val, self.alarmHigh))
                        self.resetAlarm()

    def setBackgroundColor(self, color):
        self.vb.setBackgroundColor(color)
        self._leftAxis.setZValue(0)
        self._rightAxis.setZValue(0)
        self._bottomAxis.setZValue(0)
        self._rightAxis.setZValue(0)

    # noinspection PyUnusedLocal
    def mouseDoubleClickEvent(self, ev):
        if self._alarmEnabled and self._alarmTripped:
            if self._alarmMuted:
                self.unMuteAlarm()
            else:
                self.muteAlarm()

    @staticmethod
    def _selectTrendFunction(function_name):
        ret_val = None
        if function_name in knownTrendFunctions:
            ret_val = knownTrendFunctions[function_name]
        elif function_name is not None:
            logger.error(
                "Trend function {} unknown. Valid functions are: {}. Continuing without trend function".format(
                    function_name, ", ".join(knownTrendFunctions.keys())
                )
            )
        return ret_val

    @property
    def trendEnabled(self):
        return self._trendFunction is not None

    def _rescaleData(self, chunk):
        return np.array(self._offset + self._scaling * np.array(chunk))

    def append(self, chunk):
        """
        this function adds a chunk of data to the plots, shifting every plot to the left accordingly
        :param chunk: np array (must have the same dimension as the number of plots in the _vbox)
        :return: noting
        """
        chunk = self._rescaleData(chunk)  # converts data in real units
        chunk_length = chunk.size
        self._buffer = np.roll(
            self._buffer, -chunk_length
        )  # shifts data along axis 1 chunk_length points to the left
        self._buffer[-chunk_length:] = chunk
        self._curve.setData(x=self._xArray, y=self._buffer)

        # add data to trend buffer
        self._trendBuffer.append(chunk)

    @property
    def alarmEnabled(self):
        return self._alarmEnabled

    @alarmEnabled.setter
    def alarmEnabled(self, value):
        # logger.debug("in alarmEnabled: setting value to: %s" % value)
        self._alarmEnabled = value
        self._alarmLineHigh.setVisible(self._alarmEnabled)
        self._alarmLineLow.setVisible(self._alarmEnabled)
        if self._alarmTripped and not value:
            self.resetAlarm()

    def _menuToggleAlarm(self, state):
        self.alarmEnabled = state

    @property
    def alarmHigh(self):
        return self._alarmHigh

    @alarmHigh.setter
    def alarmHigh(self, value):
        # logger.debug("Setting alarm high threshold to %.2f", value)
        self._alarmHigh = value
        self._alarmLineHigh.setPos(self._alarmHigh)

    @property
    def alarmLow(self):
        return self._alarmLow

    @alarmLow.setter
    def alarmLow(self, value):
        # logger.debug("Setting alarm low threshold to %.2f", value)
        self._alarmLow = value
        self._alarmLineLow.setPos(self._alarmLow)

    def _menuSetAlarmLow(self, value):
        self.alarmLow = value

    def _menuSetAlarmHigh(self, value):
        self.alarmHigh = value

    def tripAlarm(self):
        if self.alarmEnabled:
            # logger.debug("in tripAlarm(): ALARM ALARM ALARM ALARM ALARM ALARM")
            self._alarmTripped = True
            self.setBackgroundColor(self._alarmBGColor_alarm)
            if self._alarmSound is not None:
                self._alarmSound.play(-1)
                self._alarmMuted = False

    def resetAlarm(self):
        # logger.debug("in resetAlarm()")
        self._alarmTripped = False
        self.setBackgroundColor(self._bgColor)
        if self._alarmSound is not None:
            self._alarmSound.stop()
            self._alarmMuted = False
            self._muteButton.setVisible(False)

    def muteAlarm(self):
        # logger.debug("in muteAlarm()")
        if self._alarmEnabled and self._alarmTripped:
            if self._alarmSound is not None:
                self._alarmSound.stop()
                self._alarmMuted = True
                self._muteButton.setVisible(True)

    def unMuteAlarm(self):
        # logger.debug("in unMuteAlarm()")
        if self._alarmEnabled and self._alarmTripped and self._alarmMuted:
            if self._alarmSound is not None:
                self._alarmSound.play(-1)
                self._alarmMuted = False
                self._muteButton.setVisible(False)

    @property
    def autoscale(self):
        return self._autoscale

    @autoscale.setter
    def autoscale(self, value):
        self._autoscale = value
        if self._autoscale:
            self.vb.enableAutoRange(axis=self.vb.YAxis)
        else:
            self.vb.setYRange(self._ymin, self._ymax, padding=0)

    def _menuToggleAutoscale(self, state):
        self.autoscale = state
        self.vb.menuYAxisLimits.lowSpin.setEnabled(not self.autoscale)
        self.vb.menuYAxisLimits.highSpin.setEnabled(not self.autoscale)

    @property
    def ymin(self):
        return self._ymin

    @ymin.setter
    def ymin(self, value):
        self._ymin = value
        self.vb.setYRange(self._ymin, self._ymax, padding=0)

    @property
    def ymax(self):
        return self._ymax

    @ymax.setter
    def ymax(self, value):
        self._ymax = value
        self.vb.setYRange(self._ymin, self._ymax, padding=0)

    def getLastTrendData(self):
        return self._trendData[-1]

    def getTrendUnits(self):
        return self._trendUnits

    def _menuSetYMin(self, value):
        self.ymin = value

    def _menuSetYMax(self, value):
        self.ymax = value

    def _menuSetTrendMin(self, value):
        self._trendYmin = value
        self._trendVB.setYRange(self._trendYmin, self._trendYmax)

    def _menuSetTrendMax(self, value):
        self._trendYmax = value
        self._trendVB.setYRange(self._trendYmin, self._trendYmax)

    def _createMenu(self):
        self.vb.menu = QMenu()
        self.vb.menuAlarm = QMenu("Alarm")
        # noinspection PyArgumentList
        self.vb.menuAlarmEnabled = QAction(
            "Alarm enabled", self.vb.menuAlarm, checkable=True
        )
        self.vb.menuAlarm.addAction(self.vb.menuAlarmEnabled)
        self.vb.menuAlarmEnabled.setChecked(self.alarmEnabled)
        self.vb.menuAlarmEnabled.toggled.connect(self._menuToggleAlarm)
        self.vb.menuAlarmLimits = MenuLowHighSpinAction(
            low_val=self.alarmLow,
            high_val=self.alarmHigh,
            units=self._trendUnits,
            label_low="Low threshold",
            label_high="High threshold",
            min_val=0.0,
            max_val=float("inf"),
        )
        self.vb.menuAlarmLimits.lowSpin.valueChanged.connect(self._menuSetAlarmLow)
        self.vb.menuAlarmLimits.highSpin.valueChanged.connect(self._menuSetAlarmHigh)
        self.vb.menuAlarm.addAction(self.vb.menuAlarmLimits)

        self.vb.menuYAxis = QMenu("Y-axis")
        # noinspection PyArgumentList
        self.vb.menuYAxisAutoscaleEnabled = QAction(
            "Autoscale", self.vb.menuYAxis, checkable=True
        )
        self.vb.menuYAxis.addAction(self.vb.menuYAxisAutoscaleEnabled)
        self.vb.menuYAxisAutoscaleEnabled.toggled.connect(self._menuToggleAutoscale)
        self.vb.menuYAxisLimits = MenuLowHighSpinAction(
            low_val=self.ymin,
            high_val=self.ymax,
            units=self._units,
            label_high="Y max",
            label_low="Y min",
            min_val=float("-inf"),
            max_val=float("inf"),
        )
        self.vb.menuYAxisLimits.lowSpin.valueChanged.connect(self._menuSetYMin)
        self.vb.menuYAxisLimits.highSpin.valueChanged.connect(self._menuSetYMax)
        self.vb.menuTrendAxisLimits = MenuLowHighSpinAction(
            low_val=self._trendYmin,
            high_val=self._trendYmax,
            units=self._trendUnits,
            label_high="Trend max",
            label_low="Trend min",
            min_val=float("-inf"),
            max_val=float("inf"),
        )
        self.vb.menuTrendAxisLimits.lowSpin.valueChanged.connect(self._menuSetTrendMin)
        self.vb.menuTrendAxisLimits.highSpin.valueChanged.connect(self._menuSetTrendMax)
        if self.autoscale:
            self.vb.menuYAxisAutoscaleEnabled.setChecked(True)
            self.vb.menuYAxisLimits.lowSpin.setEnabled(False)
            self.vb.menuYAxisLimits.highSpin.setEnabled(False)
        self.vb.menuYAxis.addAction(self.vb.menuYAxisLimits)
        self.vb.menuYAxis.addAction(self.vb.menuTrendAxisLimits)

        self.vb.menu.addMenu(self.vb.menuAlarm)
        self.vb.menu.addMenu(self.vb.menuYAxis)
        return self.vb.menu

    def _raiseContextMenu(self, ev):
        menu = self._createMenu()
        pos = ev.screenPos()
        menu.popup(QtCore.QPoint(int(pos.x()), int(pos.y())))

    @property
    def acquisition_module_index(self):
        return self._acqModIdx

    @property
    def channel_index(self):
        return self._channelIdx

    def add_trend_vline(self, legend="", color=None):
        if self.trendEnabled:
            if color is None:
                color = (200, 200, 100)
            vline = pg.InfiniteLine(movable=False, angle=90, label=legend, pen=pg.mkPen({'color': color, 'width': 3}),
                                    labelOpts={'rotateAxis': (1, 0), 'position': 0.5, 'color': color,
                                               'fill': (200, 200, 200, 50),
                                               'movable': True})
            vline.setPos(self._trendXArray[-1])
            self._trendVB.addItem(vline)
            self._trend_vlines.append(vline)


class MenuLowHighSpinAction(QWidgetAction):
    def __init__(
            self,
            parent=None,
            low_val=0.0,
            high_val=0.0,
            units="",
            label_high="High value",
            label_low="Low value",
            min_val=0.0,
            max_val=10.0,
    ):
        super().__init__(parent)
        w = QWidget()
        layout = QFormLayout(w)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(0)
        self.lowSpin = QDoubleSpinBox()
        self.lowSpin.setMinimum(min_val)
        self.lowSpin.setMaximum(max_val)
        self.lowSpin.setValue(low_val)
        self.lowSpin.setSuffix("" if len(units) == 0 else " " + units)
        self.highSpin = QDoubleSpinBox()
        self.highSpin.setMinimum(min_val)
        self.highSpin.setMaximum(max_val)
        self.highSpin.setValue(high_val)
        self.highSpin.setSuffix("" if len(units) == 0 else " " + units)
        layout.addRow(label_high, self.highSpin)
        layout.addRow(label_low, self.lowSpin)
        # see https://stackoverflow.com/q/70691792/1356000
        w.setFocusPolicy(self.lowSpin.focusPolicy())
        w.setFocusProxy(self.lowSpin)
        w.setFocusPolicy(self.highSpin.focusPolicy())
        w.setFocusProxy(self.highSpin)
        w.setLayout(layout)
        self.setDefaultWidget(w)


class PagedScope(ScrollingScope):
    def __init__(
            self,
            persistence=0,
            trig_mode="AUTO",
            trig_level=1.0,
            auto_trig_level=True,
            *args,
            **kwargs
    ):
        # noinspection PyPep8Naming
        RISING_TRIGGER_MARK = "△"
        # noinspection PyPep8Naming
        FALLING_TRIGGER_MARK = "▽"
        # noinspection PyPep8Naming
        AUTO_TRIGGER_MARK = "❖"

        super(PagedScope, self).__init__(*args, **kwargs)
        # handles cases where persistence is set to None
        self._persistence = persistence if persistence is not None else 0
        self._buffer = np.array([])
        self._curve.setZValue(
            self._persistence + 10
        )  # ensure main curves stays on top of the persistent ones
        self._trendVB.setZValue(
            self._persistence + 11
        )  # ensures the trend plot stays above the other curves
        self._trendCurve.setZValue(self._persistence + 12)
        self._persistCurves = collections.deque()

        self._trigLevelBuffer = RollingBuffer(
            size=self._bufferSize * (self._persistence + 1)
        )

        # Trigger Marker
        self._trigMode = trig_mode
        self._trigLevel = trig_level
        self._autoTrigLevel = auto_trig_level
        self._trigMark = pg.TextItem(color="k", anchor=(0.25, 0.5))
        if self._trigMode.upper() == "RISING":
            self._trigMark.setPlainText(RISING_TRIGGER_MARK)
        elif self._trigMode.upper() == "FALLING":
            self._trigMark.setPlainText(FALLING_TRIGGER_MARK)
        else:
            self._trigMark.setPlainText(AUTO_TRIGGER_MARK)
        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(10)
        self._trigMark.setFont(font)
        self._trigMark.setZValue(self._persistence + 100)
        self.addItem(self._trigMark)
        left_edge = self.viewRange()[0][0]
        bottom = self.viewRange()[1][0]
        if self._trigMode.upper() == "RISING" or self._trigMode.upper() == "FALLING":
            self._trigMark.setPos(left_edge, self._trigLevel)
        else:
            self._trigMark.setPos(left_edge, bottom)

    def _autoDefineThreshold(self):
        # logger.debug("trying to determine threshold automatically")
        ret_val = 0.0
        min_value = self._trigLevelBuffer.min()
        max_value = self._trigLevelBuffer.max()

        # logger.debug("peeking into data [%f-%f]", min_value, max_value)
        overall_range = max_value - min_value

        if self._trigMode.upper() == "RISING":
            ret_val = min_value + 0.75 * overall_range
        elif self._trigMode.upper() == "FALLING":
            ret_val = max_value - 0.75 * overall_range
        else:
            pass  # AUTO mode, no need for threshold

        return ret_val

    def _waitForTrigger(self, chunk):
        # if self._trigMode.upper() == 'RISING' or self._trigMode.upper() == 'FALLING':
        #     logger.debug("[%s] in _waitForTrigger(%s) - %s" % (self._title,
        #                                                         chunk.shape,
        #                                                         self._trigMode))
        if self._autoTrigLevel and (
                self._trigMode.upper() == "RISING" or self._trigMode == "FALLING"
        ):
            self._trigLevel = self._autoDefineThreshold()
            self._trigMark.setPos(0, self._trigLevel)
        if self._trigMode.upper() == "RISING":
            (a,) = np.where(chunk > self._trigLevel)
            if len(a) > 0 and a[0] > 0 and chunk[a[0] - 1] <= self._trigLevel:
                # logger.debug("Threshold crossed at index %d. returning %d points ", a[0], len(chunk[a[0]:]))
                return chunk[a[0]:]
            else:
                # logger.debug("Threshold NOT crossed. scrapping chunk.")
                return np.array([])
        elif self._trigMode.upper() == "FALLING":
            (a,) = np.where(chunk < self._trigLevel)
            if len(a) > 0 and a[0] > 0 and chunk[a[0] - 1] >= self._trigLevel:
                # logger.debug("Threshold crossed at index %d. returning %d points ", a[0], len(chunk[a[0]:]))
                return chunk[a[0]:]
            else:
                # logger.debug("Threshold NOT crossed. scrapping chunk.")
                return np.array([])
        else:
            return chunk  # AUTO mode

    def append(self, chunk):
        chunk = np.asarray(chunk)  # make sure we have a numpy array
        # logger.debug("[%s] in append(%s)", self._title, chunk.shape)
        chunk_length = chunk.size
        if chunk_length == 0:
            return

        scaled_chunk = self._rescaleData(chunk)  # converts data in real units

        self._trigLevelBuffer.append(
            scaled_chunk
        )  # keep a copy of the data for trigger level
        self._trendBuffer.append(scaled_chunk)  # add data to trend buffer

        if self._buffer.size == 0:  # no data in main curve yet
            scaled_chunk = self._waitForTrigger(scaled_chunk)

        if self._buffer.size + chunk_length <= self._bufferSize:
            self._buffer = np.concatenate([self._buffer, scaled_chunk])
            self._curve.setData(
                x=np.linspace(
                    0.0, float(self._buffer.size) / self._sampleFreq, self._buffer.size
                ),
                y=self._buffer,
            )
        else:
            points_to_add = self._bufferSize - self._buffer.size
            points_left = chunk_length - points_to_add
            temp = np.concatenate([self._buffer, scaled_chunk[:points_to_add]])
            # create a new persistent curve
            curve = self.plot(x=self._xArray, y=temp)
            curve.setPen(color=self._lineColor, width=self._lineWidth / 2)
            self._persistCurves.append(curve)
            n_curves = len(self._persistCurves)
            for i, curve in enumerate(self._persistCurves):
                curve.setZValue(i)
                alpha = 1.0 - (i + 1) * 1.0 / (n_curves + 1)
                curve.setPen(self._lineColor)
                curve.setAlpha(alpha, alpha)

            if len(self._persistCurves) > self._persistence:
                curve_to_delete = self._persistCurves.popleft()
                self.removeItem(curve_to_delete)

            self._buffer = np.array([])
            self.append(chunk[-points_left:])


class ScopeLayoutWidget(pg.GraphicsLayoutWidget):
    def __init__(self, *args, **kwargs):
        super(ScopeLayoutWidget, self).__init__(*args, **kwargs)


# noinspection SpellCheckingInspection
def peakdet(v, delta, x=None):
    """
    Converted from MATLAB script at http://billauer.co.il/peakdet.html

    Returns two arrays

    function [maxtab, mintab]=peakdet(v, delta, x)
    %PEAKDET Detect peaks in a vector
    %        [MAXTAB, MINTAB] = PEAKDET(V, DELTA) finds the local
    %        maxima and minima ("peaks") in the vector V.
    %        MAXTAB and MINTAB consists of two columns. Column 1
    %        contains indices in V, and column 2 the found values.
    %
    %        With [MAXTAB, MINTAB] = PEAKDET(V, DELTA, X) the indices
    %        in MAXTAB and MINTAB are replaced with the corresponding
    %        X-values.
    %
    %        A point is considered a maximum peak if it has the maximal
    %        value, and was preceded (to the left) by a value lower by
    %        DELTA.

    % Eli Billauer, 3.4.05 (Explicitly not copyrighted).
    % This function is released to the public domain; Any use is allowed.
    :param x:
    :param delta:
    :param v:

    """
    maxtab = []
    mintab = []

    if x is None:
        x = np.arange(len(v))

    v = np.asarray(v)

    if len(v) != len(x):
        raise ValueError("Input vectors v and x must have same length")

    if not np.isscalar(delta):
        raise ValueError("Input argument delta must be a scalar")

    if delta < 0:
        raise ValueError("Input argument delta must be positive")

    mn, mx = np.Inf, -np.Inf
    mnpos, mxpos = np.NaN, np.NaN

    lookformax = True

    for i in np.arange(len(v)):
        this = v[i]
        if this > mx:
            mx = this
            mxpos = x[i]
        if this < mn:
            mn = this
            mnpos = x[i]

        if lookformax:
            if this < (mx - delta):
                maxtab.append((mxpos, mx))
                mn = this
                mnpos = x[i]
                lookformax = False
        else:
            if this > (mn + delta):
                mintab.append((mnpos, mn))
                mx = this
                mxpos = x[i]
                lookformax = True

    return np.array(maxtab), np.array(mintab)


# noinspection PyUnusedLocal
def trend_random(in_data, **kwargs):
    # logger.debug("in Scope.trend_random(). Received in_data, kwargs=%s", kwargs)
    min_val = kwargs.pop("min_val", 0.0)
    max_val = kwargs.pop("max_val", 1.0)
    return (max_val - min_val) * np.random.random_sample() + min_val


# noinspection PyUnusedLocal
def trend_get_HR(in_data, **kwargs):
    # logger.debug("in trend_get_HR(%s). got data: %s" % (in_data.shape, in_data.__repr__()))
    b = np.diff(in_data)  # Differentiate
    c = np.square(b)  # square
    d = np.convolve(c, np.ones(10), "same")  # smooth
    # get RMS value to use in the peak detection algorithm
    rms = np.sqrt(np.mean(np.square(d)))
    # print 'RMS value:', rms.EKG
    e_max, e_min = peakdet(d, rms)

    # noinspection PyTypeChecker
    freq = 1.0 / np.diff(e_max[:, 0] * 1e-3)
    e = np.mean(freq)
    return e * 60.0


# noinspection PyUnusedLocal
def trend_get_max(in_data, **kwargs):
    return np.max(in_data)


# noinspection PyUnusedLocal
def trend_get_min(in_data, **kwargs):
    return np.min(in_data)


# noinspection PyUnusedLocal
def trend_get_lastPeakValue(in_data, **kwargs):
    min_size = 0.0
    if "peakSize" in kwargs:
        min_size = kwargs["peakSize"]
    else:
        # get RMS value to use in the peak detection algorithm
        min_size = np.sqrt(np.mean(np.square(in_data)))
    e_max, e_min = peakdet(in_data, min_size)
    if len(e_max) > 0:
        ret = e_max[-1, 1]
    else:
        ret = np.nan
    return ret


# noinspection PyUnusedLocal
def trend_get_avgPeakValue(in_data, **kwargs):
    min_size = 0.0
    if "peakSize" in kwargs:
        min_size = kwargs["peakSize"]
    else:
        # get RMS value to use in the peak detection algorithm
        min_size = np.sqrt(np.mean(np.square(in_data)))
    e_max, e_min = peakdet(in_data, min_size)
    if len(e_max) > 0:
        ret = np.mean(e_max[:, 1])
    else:
        ret = np.nan
    return ret


# noinspection PyUnusedLocal
def trend_get_avg(in_data, **kwargs):
    return np.mean(in_data)


knownTrendFunctions = {
    "random": trend_random,
    "HR": trend_get_HR,
    "max": trend_get_max,
    "min": trend_get_min,
    "lastPeak": trend_get_lastPeakValue,
    "avgPeak": trend_get_avgPeakValue,
    "average": trend_get_avg,
}
