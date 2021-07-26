from io import StringIO
import logging
import numpy as np
import serial
from sampling.sampling import Streamer

logger = logging.getLogger(__name__)


class SerialStreamer(Streamer):
    # noinspection SpellCheckingInspection
    def __init__(self, sampling_rate, port=None, baudrate=115200, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                 stopbits=serial.STOPBITS_ONE,
                 timeout=0.2, xonxoff=False, rtscts=False,
                 write_timeout=None, dsrdtr=False, inter_byte_timeout=None, genfromtxt_kws=None):
        self._serial = serial.Serial(port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts,
                                     write_timeout, dsrdtr, inter_byte_timeout)
        self._sampling_rate = sampling_rate
        self.__genfromtxt_kws = {} if genfromtxt_kws is None else genfromtxt_kws
        self.__paused = True
        self.start()
        self._remain = ''

    def read(self):
        if not self.__paused:
            n = self._serial.in_waiting
            if not n > 0:
                return self._empty
            logger.debug(f"serial {self._serial.port} has {n} bytes in waiting")
            lines = self._serial.read(n).decode('ascii')
            lines = self._remain + lines
            if '\n' not in lines:
                self._remain = lines
                return self._empty
            pos2 = lines.rfind('\n')
            # noinspection PyTypeChecker
            out = np.genfromtxt(StringIO(lines[:pos2]), **self.__genfromtxt_kws)
            out = np.atleast_2d(out).T
            self._remain = lines[pos2+1:]
            return out
        else:
            return self._empty

    def start(self):
        self._serial.reset_output_buffer()
        self._serial.reset_input_buffer()
        for _ in range(5):
            # discards a few lines to make sure the buffer does not contain partial lines
            self._serial.readline()
        self.__paused = False

    def stop(self):
        self.__paused = True
