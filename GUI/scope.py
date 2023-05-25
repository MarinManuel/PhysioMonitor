# -*- coding: utf-8 -*-
import collections
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
from pyqtgraph.Qt import QtCore, QtGui

from sampling.buffers import RollingBuffer

BACKGROUND_COLOR = (226, 226, 226)
AXES_COLOR = (0, 0, 0)

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
        windowSize=30,  # in secs
        sampleFreq=1000,  # in Hz
        bgColor="w",
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
        trendWindowSize=30 * 60,  # in seconds
        trendPeriod=30,  # in seconds
        trendFunction=None,
        trendFuncKwargs=None,
        trendUnits="",
        trendAutoscale=False,
        trendYmin=0.0,
        trendYmax=1.0,
        alarmEnabled=False,
        alarmLow=0.0,
        alarmHigh=1.0,
        alarmSoundFile=None,
        alarmBGColor=(255, 255, 200),
        *args,
        **kwargs
    ):
        super(ScrollingScope, self).__init__(*args, **kwargs)
        self._acqModIdx = acquisition_module_index
        self._channelIdx = channel_index
        self._windowSize = windowSize
        self._sampleFreq = sampleFreq
        self._bgColor = bgColor
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
        self._trendWindowSize = trendWindowSize
        self._trendPeriod = trendPeriod
        self._trendFunction = self._selectTrendFunction(trendFunction)
        self._trendFuncKwargs = trendFuncKwargs
        self._trendUnits = trendUnits
        self._trendAutoscale = trendAutoscale
        self._trendYmin = trendYmin
        self._trendYmax = trendYmax
        self._alarmEnabled = alarmEnabled
        self._alarmLow = alarmLow
        self._alarmHigh = alarmHigh
        self._alarmTripped = False
        self._alarmMuted = False
        self._alarmBGColor_alarm = alarmBGColor
        if alarmSoundFile is not None and os.path.isfile(alarmSoundFile):
            self._alarmSound = pygame.mixer.Sound(alarmSoundFile)
        else:
            self._alarmSound = None

        self._bufferSize = int(windowSize * sampleFreq)
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
        #  I'm not showing the top axis because it's taking a lot of screen real-estate
        # and it's not really useful anyway
        # self.scene().addItem(self._trendVB)
        # According to the example I'm following, I need to do this to add the second axis
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
        self._trendTimer = pg.QtCore.QTimer()
        # noinspection PyUnresolvedReferences
        self._trendTimer.timeout.connect(self.onTrendTimer)

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

    def showEvent(self, QShowEvent):
        super(ScrollingScope, self).showEvent(QShowEvent)
        self.scene().addItem(self._trendVB)

    def start(self):
        self._trendTimer.start(self._trendPeriod * 1000)

    def onResize(self):
        self._trendVB.setGeometry(self.vb.sceneBoundingRect())

    def onTrendTimer(self):
        # logger.debug("in ScrollingPlot.onTrendTimer()")
        if self.trendEnabled:
            retVal = self._trendFunction(
                self._trendBuffer.values().flatten(), **self._trendFuncKwargs
            )
            self._trendText.setPlainText("{:.1f} {!s}".format(retVal, self._trendUnits))
            self._trendData = np.roll(
                self._trendData, -1
            )  # shifts data along axis 1 N points to the left
            self._trendData[-1:] = retVal
            self._trendCurve.setData(x=self._trendXArray, y=self._trendData)

            # deal with alarm conditions
            if self.alarmEnabled:
                if retVal > self._alarmHigh and not np.isnan(retVal):
                    if not self._alarmTripped:
                        # logger.debug(
                        #     "Trend value reached %.2f, which is > %.2f. Tripping alarm" % (retVal, self.alarmHigh))
                        self.tripAlarm()
                elif retVal < self._alarmLow and not np.isnan(retVal):
                    if not self._alarmTripped:
                        # logger.debug(
                        #     "Trend value reached %.2f, which is < %.2f. Tripping alarm" % (retVal, self.alarmLow))
                        self.tripAlarm()
                else:
                    # value is between alarmLow and alarmHigh
                    if self._alarmTripped:
                        # logger.debug(
                        #     "Trend value: %.2f > %.2f > %.2f. resetting alarm" %
                        #     (self.alarmLow, retVal, self.alarmHigh))
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
    def _selectTrendFunction(functionName):
        retVal = None
        if functionName in knownTrendFunctions:
            retVal = knownTrendFunctions[functionName]
        elif functionName is not None:
            logger.error(
                "Trend function {} unknown. Valid functions are: {}. Continuing without trend function".format(
                    functionName, ", ".join(knownTrendFunctions.keys())
                )
            )
        return retVal

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
        N = chunk.size
        self._buffer = np.roll(
            self._buffer, -N
        )  # shifts data along axis 1 N points to the left
        self._buffer[-N:] = chunk
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
            # logger.debug("in tripAlarm(): ALARM ALARM ALARM ALARM ALARM ALARM ALARM ALARM ALARM ALARM")
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
            lowVal=self.alarmLow,
            highVal=self.alarmHigh,
            units=self._trendUnits,
            labelLow="Low threshold",
            labelHigh="High threshold",
            minVal=0.0,
            maxVal=float("inf"),
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
            lowVal=self.ymin,
            highVal=self.ymax,
            units=self._units,
            labelHigh="Y max",
            labelLow="Y min",
            minVal=float("-inf"),
            maxVal=float("inf"),
        )
        self.vb.menuYAxisLimits.lowSpin.valueChanged.connect(self._menuSetYMin)
        self.vb.menuYAxisLimits.highSpin.valueChanged.connect(self._menuSetYMax)
        self.vb.menuTrendAxisLimits = MenuLowHighSpinAction(
            lowVal=self._trendYmin,
            highVal=self._trendYmax,
            units=self._trendUnits,
            labelHigh="Trend max",
            labelLow="Trend min",
            minVal=float("-inf"),
            maxVal=float("inf"),
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


class MenuLowHighSpinAction(QWidgetAction):
    def __init__(
        self,
        parent=None,
        lowVal=0.0,
        highVal=0.0,
        units="",
        labelHigh="High value",
        labelLow="Low value",
        minVal=0.0,
        maxVal=10.0,
    ):
        super().__init__(parent)
        w = QWidget()
        layout = QFormLayout(w)
        layout.setContentsMargins(12, 0, 0, 0)
        layout.setSpacing(0)
        self.lowSpin = QDoubleSpinBox()
        self.lowSpin.setMinimum(minVal)
        self.lowSpin.setMaximum(maxVal)
        self.lowSpin.setValue(lowVal)
        self.lowSpin.setSuffix("" if len(units) == 0 else " " + units)
        self.highSpin = QDoubleSpinBox()
        self.highSpin.setMinimum(minVal)
        self.highSpin.setMaximum(maxVal)
        self.highSpin.setValue(highVal)
        self.highSpin.setSuffix("" if len(units) == 0 else " " + units)
        layout.addRow(labelHigh, self.highSpin)
        layout.addRow(labelLow, self.lowSpin)
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
        trigMode="AUTO",
        trigLevel=1.0,
        autoTrigLevel=True,
        *args,
        **kwargs
    ):
        RISING_TRIGGER_MARK = "△"
        FALLING_TRIGGER_MARK = "▽"
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
        self._trigMode = trigMode
        self._trigLevel = trigLevel
        self._autoTrigLevel = autoTrigLevel
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
        leftEdge = self.viewRange()[0][0]
        bottom = self.viewRange()[1][0]
        if self._trigMode.upper() == "RISING" or self._trigMode.upper() == "FALLING":
            self._trigMark.setPos(leftEdge, self._trigLevel)
        else:
            self._trigMark.setPos(leftEdge, bottom)

    def _autoDefineThreshold(self):
        # logger.debug("trying to determine threshold automatically")
        retVal = 0.0
        minValue = self._trigLevelBuffer.min()
        maxValue = self._trigLevelBuffer.max()

        # logger.debug("peeking into data [%f-%f]", minValue, maxValue)
        overallRange = maxValue - minValue

        if self._trigMode.upper() == "RISING":
            retVal = minValue + 0.75 * overallRange
        elif self._trigMode.upper() == "FALLING":
            retVal = maxValue - 0.75 * overallRange
        else:
            pass  # AUTO mode, no need for threshold

        return retVal

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
                return chunk[a[0] :]
            else:
                # logger.debug("Threshold NOT crossed. scrapping chunk.")
                return np.array([])
        elif self._trigMode.upper() == "FALLING":
            (a,) = np.where(chunk < self._trigLevel)
            if len(a) > 0 and a[0] > 0 and chunk[a[0] - 1] >= self._trigLevel:
                # logger.debug("Threshold crossed at index %d. returning %d points ", a[0], len(chunk[a[0]:]))
                return chunk[a[0] :]
            else:
                # logger.debug("Threshold NOT crossed. scrapping chunk.")
                return np.array([])
        else:
            return chunk  # AUTO mode

    def append(self, chunk):
        chunk = np.asarray(chunk)  # make sure we have a numpy array
        # logger.debug("[%s] in append(%s)", self._title, chunk.shape)
        N = chunk.size
        if N == 0:
            return

        scaled_chunk = self._rescaleData(chunk)  # converts data in real units

        self._trigLevelBuffer.append(
            scaled_chunk
        )  # keep a copy of the data for trigger level
        self._trendBuffer.append(scaled_chunk)  # add data to trend buffer

        if self._buffer.size == 0:  # no data in main curve yet
            scaled_chunk = self._waitForTrigger(scaled_chunk)

        if self._buffer.size + N <= self._bufferSize:
            self._buffer = np.concatenate([self._buffer, scaled_chunk])
            self._curve.setData(
                x=np.linspace(
                    0.0, float(self._buffer.size) / self._sampleFreq, self._buffer.size
                ),
                y=self._buffer,
            )
        else:
            pointsToAdd = self._bufferSize - self._buffer.size
            pointsLeft = N - pointsToAdd
            temp = np.concatenate([self._buffer, scaled_chunk[:pointsToAdd]])
            # create a new persistent curve
            curve = self.plot(x=self._xArray, y=temp)
            curve.setPen(color=self._lineColor, width=self._lineWidth / 2)
            self._persistCurves.append(curve)
            nCurves = len(self._persistCurves)
            for i, curve in enumerate(self._persistCurves):
                curve.setZValue(i)
                alpha = 1.0 - (i + 1) * 1.0 / (nCurves + 1)
                curve.setPen(self._lineColor)
                curve.setAlpha(alpha, alpha)

            if len(self._persistCurves) > self._persistence:
                curveToDelete = self._persistCurves.popleft()
                self.removeItem(curveToDelete)

            self._buffer = np.array([])
            self.append(chunk[-pointsLeft:])


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
def trend_random(inData, **kwargs):
    # logger.debug("in Scope.trend_random(). Received inData, kwargs=%s", kwargs)
    minVal = kwargs.pop("minVal", 0.0)
    maxVal = kwargs.pop("maxVal", 1.0)
    return (maxVal - minVal) * np.random.random_sample() + minVal


# noinspection PyUnusedLocal
def trend_get_HR(inData, **kwargs):
    # logger.debug("in trend_get_HR(%s). got data: %s" % (inData.shape, inData.__repr__()))
    b = np.diff(inData)  # Differentiate
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
def trend_get_max(inData, **kwargs):
    return np.max(inData)


# noinspection PyUnusedLocal
def trend_get_min(inData, **kwargs):
    return np.min(inData)


# noinspection PyUnusedLocal
def trend_get_lastPeakValue(inData, **kwargs):
    minSize = 0.0
    if "peakSize" in kwargs:
        minSize = kwargs["peakSize"]
    else:
        # get RMS value to use in the peak detection algorithm
        minSize = np.sqrt(np.mean(np.square(inData)))
    e_max, e_min = peakdet(inData, minSize)
    if len(e_max) > 0:
        ret = e_max[-1, 1]
    else:
        ret = np.nan
    return ret


# noinspection PyUnusedLocal
def trend_get_avgPeakValue(inData, **kwargs):
    minSize = 0.0
    if "peakSize" in kwargs:
        minSize = kwargs["peakSize"]
    else:
        # get RMS value to use in the peak detection algorithm
        minSize = np.sqrt(np.mean(np.square(inData)))
    e_max, e_min = peakdet(inData, minSize)
    if len(e_max) > 0:
        ret = np.mean(e_max[:, 1])
    else:
        ret = np.nan
    return ret


# noinspection PyUnusedLocal
def trend_get_avg(inData, **kwargs):
    return np.mean(inData)


knownTrendFunctions = {
    "random": trend_random,
    "HR": trend_get_HR,
    "max": trend_get_max,
    "min": trend_get_min,
    "lastPeak": trend_get_lastPeakValue,
    "avgPeak": trend_get_avgPeakValue,
    "average": trend_get_avg,
}
