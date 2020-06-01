import time
import numpy as np
import pandas as pd
import logging
import serial


class Streamer(object):
    def iterator(self):
        raise NotImplementedError()

    def read(self):
        raise NotImplementedError()

    def start(self):
        raise NotImplementedError()

    def stop(self):
        raise NotImplementedError()


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

    # noinspection PyTypeChecker
    def iterator(self):
        if not self.__paused:
            # logging.debug("in DummyComedi.iterator()")
            t = np.linspace(self.__t, self.__t + self.nbPointsReturned * self.__dt, self.nbPointsReturned,
                            endpoint=False)
            # logging.debug("time array is from %f to %f: %s", t[0], t[-1], t)
            self.__t += self.nbPointsReturned * self.__dt
            # logging.debug("next time value will be %f", self.__t)

            out = self.amp * np.sin(2 * np.pi * self.freq * t + self.phase) + self.offset
            out = np.reshape(out, (1, self.nbPointsReturned))
            # logging.debug("returned array [%s]: %s", out.shape, out)
            yield out
        else:
            yield

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
    def __init__(self, nChan=1, sampleFreq=1000., filename="surgery.txt", start=True, pointsToReturn=None):
        self._nChan = nChan
        self._sampleFreq = sampleFreq
        self._table = pd.read_table(filename, index_col=0)
        self._data = np.array(self._table.iloc[:, :self._nChan]).transpose()
        self.__lastTime = time.time()
        self.__paused = not start
        self.__pointsToReturn = pointsToReturn
        logging.debug('created SurgeryFileStreamer(nChan=%d, sampleFreq=%d, filename=%s). data=%s', nChan, sampleFreq,
                      filename, self._data.shape)

    def iterator(self):
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
            yield out
        else:
            yield

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


class SerialStreamer(Streamer):
    def __init__(self, port=None, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                 stopbits=serial.STOPBITS_ONE,
                 timeout=None, xonxoff=False, rtscts=False,
                 write_timeout=None, dsrdtr=False, inter_byte_timeout=None):
        self._serial = serial.Serial(port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts,
                                    write_timeout, dsrdtr, inter_byte_timeout)
        self._data = 0
        self.__paused = False

    def iterator(self):
        pass

    def read(self):
        pass

    def start(self):
        self.__paused = False

    def stop(self):
        self.__paused = True
