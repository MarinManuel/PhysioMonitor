import time
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def deinterleave(inData, nChan, dtype=int):
    """
    takes a linear array with data points interleaved
    [a1,b1,c1,a2,b2,c2,....aN-1,bN-1,cN-1,aN,bN]
    and return a (nChan,N) numpy.array with the data de-interleaved
    [[a1,a2,a3,...aN-1],
     [b1,b2,b3,...bN-1],
     [c1,c2,c3,...cN-1]]

    if the length of the input array was not a multiple of nChan,
    the remaining points are returned in remainData.
    Otherwise, remainData is an empty array

    Args:
        nChan:
        inData:
    """
    n = len(inData)
    nToKeep = n - (n % nChan)
    outData = np.array(inData[:nToKeep], dtype=dtype).reshape((-1, nChan)).transpose()
    remainData = inData[nToKeep:]
    return outData, remainData


class Streamer(object):
    def read(self):
        return np.array([])

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


class SinusoidStreamer(Streamer):
    """
    This is a dummy object that provides an iterator yielding a section of sinusoid

    out = amp * sin(2*pi*f*t + phi)
    """

    def __init__(self, sampleFreq, size=100, amplitude=1.0, frequency=2.0, offset=0.0, phase=0.0, start=True):
        self.amp = amplitude
        self.freq = frequency
        self.offset = offset
        self.phase = phase
        self.nbPointsReturned = size
        self.__t = 0
        self.__dt = 1. / sampleFreq
        self.__paused = not start

    def read(self):
        if not self.__paused:
            # logging.debug("in DummyComedi.iterator()")
            t = np.linspace(self.__t, self.__t + self.nbPointsReturned * self.__dt, self.nbPointsReturned,
                            endpoint=False)
            # logging.debug("time array is from %f to %f: %s", t[0], t[-1], t)
            self.__t += self.nbPointsReturned * self.__dt
            # logging.debug("next time value will be %f", self.__t)

            # noinspection PyTypeChecker
            out = self.amp * np.sin(2 * np.pi * self.freq * t + self.phase) + self.offset
            # noinspection PyTypeChecker
            out = np.reshape(out, (1, self.nbPointsReturned))
            # logging.debug("returned array [%s]: %s", out.shape, out)
            return out
        else:
            return

    def start(self):
        self.__paused = False

    def stop(self):
        self.__paused = True


class SurgeryFileStreamer(Streamer):
    def __init__(self, nChans=1, sampleFreq=1000., filename="./media/file_streamer_data.txt", start=True,
                 pointsToReturn=None):
        self._nChan = nChans
        self._sampleFreq = sampleFreq
        self._table = pd.read_table(filename, index_col=0)
        self._data = np.array(self._table.iloc[:, :self._nChan]).transpose()
        self.__lastTime = time.time()
        self.__paused = not start
        self.__pointsToReturn = pointsToReturn
        logging.debug('created SurgeryFileStreamer(nChan=%d, sampleFreq=%d, filename=%s). data=%s', nChans, sampleFreq,
                      filename, self._data.shape)

    def read(self):
        if not self.__paused:
            currTime = time.time()
            if self.__pointsToReturn is None:
                nbPoints = int((currTime - self.__lastTime) * self._sampleFreq)
            else:
                nbPoints = self.__pointsToReturn
            out = self._data[:, :nbPoints]
            self._data = np.roll(self._data, -1 * nbPoints, 1)
            self.__lastTime = currTime
            # logging.debug('SurgeryFileStreamer.iterator returning %d points [%s...]', nbPoints, out[10:, 10:])
            return out
        else:
            return

    def start(self):
        self.__paused = False

    def stop(self):
        self.__paused = True


AVAIL_ACQ_MODULES = {'demo': SurgeryFileStreamer}
