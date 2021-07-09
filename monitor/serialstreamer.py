from sampling import Streamer, AVAIL_ACQ_MODULES
import serial


class SerialStreamer(Streamer):
    def __init__(self, port=None, baudrate=9600, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                 stopbits=serial.STOPBITS_ONE,
                 timeout=None, xonxoff=False, rtscts=False,
                 write_timeout=None, dsrdtr=False, inter_byte_timeout=None):
        self._serial = serial.Serial(port, baudrate, bytesize, parity, stopbits, timeout, xonxoff, rtscts,
                                     write_timeout, dsrdtr, inter_byte_timeout)
        self._data = 0
        self.__paused = False

    def read(self):
        pass

    def start(self):
        self.__paused = False

    def stop(self):
        self.__paused = True


AVAIL_ACQ_MODULES = {**AVAIL_ACQ_MODULES, 'serial': SerialStreamer}

