import numpy as np
import logging
import threading
# noinspection PyUnresolvedReferences
import comedi as c
import os
import struct
from monitor.buffers import RollingBuffer
from monitor.sampling import Streamer


class ComediError(Exception):
    """Base class for exceptions in this module."""
    pass


class CmdComediError(ComediError):
    """Exception raised when a comedi command fails.

    Attributes:
        expr -- input expression in which the error occurred
        msg  -- explanation of the error
    """

    def __init__(self, msg):
        Exception.__init__(self, msg)


def de_interleave(inData, nChan):
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
    outData = np.array(inData[:nToKeep], dtype=int).reshape((-1, nChan)).transpose()
    remainData = inData[nToKeep:]
    return outData, remainData


class SamplingThread(threading.Thread):
    def __init__(self, aiConfig, bufferSize=10000):
        # logging.debug("in readerThread __init__")
        threading.Thread.__init__(self)
        self._aiConfig = aiConfig
        self._bufferSize = bufferSize
        self._data = RollingBuffer(self._bufferSize, self._aiConfig['self.nbChans'])
        self._stop = threading.Event()
        self._remaining = []

        # configure the comedi device
        self._dev = c.comedi_open(str(self._aiConfig['device']))
        if not self._dev:
            logging.error("FATAL ERROR: cannot open comedi device %s: %s",
                          (self._aiConfig['device'], c.comedi_strerror(c.comedi_errno())))
            raise IOError()

        # and get an appropriate subdevice
        self._subdev = self._aiConfig['subDevice']

        # get a file-descriptor for reading
        self._fd = c.comedi_fileno(self._dev)
        if self._fd <= 0:
            logging.error("Error obtaining comedi device file descriptor: %s",
                          (c.comedi_strerror(c.comedi_errno())))
            raise IOError()

        # create channel list
        myChanList = c.chanlist(int(self._aiConfig['self.nbChans']))
        for i in range(int(self._aiConfig['self.nbChans'])):
            myChanList[i] = c.cr_pack(self._aiConfig['channels'][i],
                                      self._aiConfig['gains'][i],
                                      self._aiConfig['refs'][i])
        # create a command structure
        cmd = c.comedi_cmd_struct()
        ret = c.comedi_get_cmd_generic_timed(self._dev,
                                             self._subdev,
                                             cmd,
                                             int(self._aiConfig['self.nbChans']),
                                             int(1.e9 / self._aiConfig['sampleFreq']))
        if ret:
            logging.error("comedi_get_cmd_generic failed")
            raise CmdComediError("comedi_get_cmd_generic failed")

        cmd.chanlist = myChanList  # adjust for our particular context
        cmd.chanlist_len = int(self._aiConfig['self.nbChans'])
        cmd.scan_end_arg = int(self._aiConfig['self.nbChans'])
        cmd.stop_src = c.TRIG_NONE  # never stop

        # test our comedi command a few times.
        for i in range(2):
            ret = c.comedi_command_test(self._dev, cmd)
            if ret < 0:
                logging.error("comedi_command_test failed: %s", c.comedi_strerror(c.comedi_errno()))
                raise CmdComediError(c.comedi_strerror(c.comedi_errno()))

        # Start the command
        ret = c.comedi_command(self._dev, cmd)
        if ret != 0:
            logging.error("comedi_command failed... %s", c.comedi_strerror(c.comedi_errno()))
            raise CmdComediError(c.comedi_strerror(c.comedi_errno()))

            # for chanNum, chanGain in zip(self._aiConfig['channels'], self._aiConfig['gains']):
            #     self.maxChanValues.append(c.comedi_get_maxdata(self._dev, self._subdev, chanNum))
            #     self.chanRanges.append(c.comedi_get_range(self._dev, self._subdev, chanNum, chanGain))

            # # start reader thread
            # logging.debug("creating reader thread")
            # self.helper = SamplingThread(self, self._fd, int(self._aiConfig['self.nbChans']))
            # self.helper.start()

    def stop(self):
        self._stop.set()
        c.comedi_close(self._dev)

    def isStopped(self):
        return self._stop.isSet()

    def run(self):
        # logging.debug("Reader thread running...")
        data = []
        while not self.isStopped():
            # logging.debug("reading...")
            line = os.read(self._fd, self._bufferSize)
            n = len(line) / 2  # 2 bytes per 'H'
            # logging.debug("read %s(...) (%d bytes). data is %d items", line[:5], len(line), len(data))
            unpack = struct.unpack('%dH' % n, line)
            # logging.debug("unpacking... got %d values", len(unpack))
            data.extend(unpack)
            # logging.debug("appending to data. data is now (%d items) %s", len(data), str(data))
            # logging.debug("de-interleaving...")
            out, data = de_interleave(data, self._aiConfig['self.nbChans'])
            # logging.debug(
            #     "returned a (%d,%d) array and kept %d for next round", out.shape[0], out.shape[1], len(data))
            self._data.append(out)
            # logging.debug("sampling buffer is now %s", self._buffer)


class ComediStreamer(Streamer):
    # noinspection PyMissingConstructor
    def __init__(self, config, bufferSize=10000, start=True):
        # logging.debug("in SurgeryFileStreamer __init__")
        self._remaining = []
        self._bufferSize = bufferSize
        self._config = config['comedi']
        self.__chanMaxValues = []
        self.__chanRangeMins = []
        self.__chanRangeMaxs = []
        self.nbChans = len(self._config['channels'])
        self.__paused = not start

        # configure the comedi device
        self._dev = c.comedi_open(str(self._config['device']))
        if not self._dev:
            logging.error("FATAL ERROR: cannot open comedi device: %s", c.comedi_strerror(c.comedi_errno()))
            raise IOError(c.comedi_strerror(c.comedi_errno()))

        # and get an appropriate subdevice
        self._subdev = self._config['sub-device']

        for chan in self._config['channels']:
            self.__chanMaxValues.append(c.comedi_get_maxdata(self._dev, self._subdev, chan['channel-id']))
            temp = c.comedi_get_range(self._dev, self._subdev, chan['channel-id'], chan['gain'])
            self.__chanRangeMins.append(temp.min)
            self.__chanRangeMaxs.append(temp.max)

        # get a file-descriptor for reading
        self._fd = c.comedi_fileno(self._dev)
        if self._fd <= 0:
            logging.error("Error obtaining comedi device file descriptor: %s",
                          c.comedi_strerror(c.comedi_errno()))
            raise IOError(c.comedi_strerror(c.comedi_errno()))

        # create channel list
        myChanList = c.chanlist(self.nbChans)
        for i, chan in enumerate(self._config['channels']):
            myChanList[i] = c.cr_pack(chan['channel-id'],
                                      chan['gain'],
                                      chan['ref'])
        # create a command structure
        self._cmd = c.comedi_cmd_struct()
        ret = c.comedi_get_cmd_generic_timed(self._dev,
                                             self._subdev,
                                             self._cmd,
                                             self.nbChans,
                                             int(1.e9 / self._config['sample-rate']))
        if ret:
            logging.error("comedi_get_cmd_generic failed")
            raise CmdComediError("comedi_get_cmd_generic failed")

        self._cmd.chanlist = myChanList  # adjust for our particular context
        self._cmd.chanlist_len = self.nbChans
        self._cmd.scan_end_arg = self.nbChans
        self._cmd.stop_src = c.TRIG_NONE  # never stop

        # test our comedi command a few times.
        for i in range(2):
            ret = c.comedi_command_test(self._dev, self._cmd)
            if ret < 0:
                logging.error("comedi_command_test failed: %s", c.comedi_strerror(c.comedi_errno()))
                raise CmdComediError(c.comedi_strerror(c.comedi_errno()))

    def __del__(self):
        # logging.debug("in SurgeryFileStreamer.__del__()")
        self.stop()
        ret = c.comedi_close(self._dev)
        if ret:
            logging.error(c.comedi_strerror(c.comedi_errno()))
            raise CmdComediError(c.comedi_strerror(c.comedi_errno()))

    def iterator(self):
        out = np.empty((self.nbChans,))
        if not self.__paused:
            # logging.debug("in SamplingThread.iterator... reading next values")
            line = os.read(self._fd, self._bufferSize)
            n = len(line) / 2  # 2 bytes per 'H'
            # logging.debug("read %s(...) (%d bytes). data is %d items", line[:-5], len(line))
            unpack = struct.unpack('%dH' % n, line)
            # logging.debug("unpacking... got %d values", len(unpack))
            self._remaining.extend(unpack)
            # logging.debug("de-interleaving...")
            out, self._remaining = de_interleave(self._remaining, self.nbChans)
            # logging.debug("returned a (%d,%d) array and kept %d for next round",
            #               out.shape[0], out.shape[1], len(self._remaining))
            out = self.to_physical(out)
        yield out

    def read(self):
        out = np.empty((self.nbChans,))
        if not self.__paused:
            # logging.debug("in SamplingThread.read... reading next values")
            line = os.read(self._fd, self._bufferSize)
            n = len(line) / 2  # 2 bytes per 'H'
            # logging.debug("read %s(...) (%d bytes). data is %d items", line[:-5], len(line))
            unpack = struct.unpack('%dH' % n, line)
            # logging.debug("unpacking... got %d values", len(unpack))
            self._remaining.extend(unpack)
            # logging.debug("de-interleaving...")
            out, self._remaining = de_interleave(self._remaining, self.nbChans)
            # logging.debug("returned a (%d,%d) array and kept %d for next round",
            #               out.shape[0], out.shape[1], len(self._remaining))
            out = self.to_physical(out)
        return out

    def to_physical(self, inData):
        out = inData.astype(np.float64)
        out /= np.reshape(self.__chanMaxValues, (self.nbChans, 1))
        out *= np.reshape((np.array(self.__chanRangeMaxs) - np.array(self.__chanRangeMins)),
                          (self.nbChans, 1))
        out += np.reshape(self.__chanRangeMins, (self.nbChans, 1))
        return out

    def start(self):
        # Start the command
        ret = c.comedi_command(self._dev, self._cmd)
        if ret != 0:
            logging.error("comedi_command failed... %s", c.comedi_strerror(c.comedi_errno()))
            raise CmdComediError(c.comedi_strerror(c.comedi_errno()))
        else:
            self.__paused = False

    def stop(self):
        ret = c.comedi_cancel(self._dev, self._subdev)
        if ret:
            logging.error(c.comedi_strerror(c.comedi_errno()))
            raise CmdComediError(c.comedi_strerror(c.comedi_errno()))
        else:
            self.__paused = True
