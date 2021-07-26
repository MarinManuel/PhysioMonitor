import logging
import time
import numpy as np
from .sampling import Streamer
logger = logging.getLogger(__name__)


class DemoStreamer(Streamer):
    # noinspection SpellCheckingInspection
    def __init__(self, sampling_rate=1000, filename="./media/demostreamer_data.txt", genfromtxt_kws=None):
        genfromtxt_kws = {} if genfromtxt_kws is None else genfromtxt_kws
        self._sampling_rate = sampling_rate
        self._data = np.genfromtxt(filename, **genfromtxt_kws).T
        self.__lastTime = time.time()
        self.__paused = False
        logger.debug('created DemoStreamer(sampling_rate=%f, filename=%s). data=%s', sampling_rate,
                     filename, self._data.shape)

    def read(self):
        if not self.__paused:
            currTime = time.time()
            nbPoints = int((currTime - self.__lastTime) * self._sampling_rate)
            out = self._data[:, :nbPoints]
            self._data = np.roll(self._data, -1 * nbPoints, 1)
            self.__lastTime = currTime
            # logging.debug('DemoStreamer.iterator returning %d points [%s...]', nbPoints, out[10:, 10:])
            return out
        else:
            return self._empty

    def start(self):
        self.__paused = False
        self.__lastTime = time.time()

    def stop(self):
        self.__paused = True
