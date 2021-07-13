import logging
import time
import numpy as np

from sampling import Streamer

logger = logging.getLogger(__name__)


class DemoStreamer(Streamer):
    def __init__(self, sampling_rate, filename="./media/file_streamer_data.txt", loadtxt_kws=None):
        loadtxt_kws = {} if loadtxt_kws is None else loadtxt_kws
        self._sampling_rate = sampling_rate
        self._data = np.loadtxt(filename, **loadtxt_kws)
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
            return

    def start(self):
        self.__paused = False

    def stop(self):
        self.__paused = True
