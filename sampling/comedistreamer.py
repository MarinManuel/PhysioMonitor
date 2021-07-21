import os
import struct
import comedi
import numpy as np
import logging
from sampling.sampling import Streamer, deinterleave

logger = logging.getLogger(__name__)


class ComediError(Exception):
    """Base class for exceptions in this module."""
    pass


class CmdComediError(ComediError):
    """Exception raised when a comedi command fails."""
    def __init__(self, msg):
        Exception.__init__(self, msg)


class ComediStreamer(Streamer):
    def __init__(self, config, bufferSize=10000, start=True):
        # logger.debug("in DemoStreamer __init__")
        self._remaining = []
        self._bufferSize = bufferSize
        self._config = config
        self.__channelMaxValues = []
        self.__channelRangeMinValues = []
        self.__channelRangeMaxValues = []
        self.nbChannels = len(self._config['channels'])
        self.__paused = not start

        # configure the comedi device
        self._dev = comedi.comedi_open(str(self._config['device']))
        if not self._dev:
            logging.error("FATAL ERROR: cannot open comedi device: %s", comedi.comedi_strerror(comedi.comedi_errno()))
            raise IOError(comedi.comedi_strerror(comedi.comedi_errno()))

        # and get an appropriate subdevice
        self._subdevice = self._config['sub-device']

        for channel in self._config['channels']:
            self.__channelMaxValues.append(comedi.comedi_get_maxdata(self._dev, self._subdevice, channel['channel-id']))
            temp = comedi.comedi_get_range(self._dev, self._subdevice, channel['channel-id'], channel['gain'])
            self.__channelRangeMinValues.append(temp.min)
            self.__channelRangeMaxValues.append(temp.max)

        # get a file-descriptor for reading
        self._fd = comedi.comedi_fileno(self._dev)
        if self._fd <= 0:
            logging.error("Error obtaining comedi device file descriptor: %s",
                          comedi.comedi_strerror(comedi.comedi_errno()))
            raise IOError(comedi.comedi_strerror(comedi.comedi_errno()))

        # create channel list
        myChanList = comedi.chanlist(self.nbChannels)
        for i, channel in enumerate(self._config['channels']):
            myChanList[i] = comedi.cr_pack(channel['channel-id'],
                                           channel['gain'],
                                           channel['ref'])
        # create a command structure
        self._cmd = comedi.comedi_cmd_struct()
        ret = comedi.comedi_get_cmd_generic_timed(self._dev,
                                                  self._subdevice,
                                                  self._cmd,
                                                  self.nbChannels,
                                                  int(1.e9 / self._config['sample-rate']))
        if ret:
            logging.error("comedi_get_cmd_generic failed")
            raise CmdComediError("comedi_get_cmd_generic failed")

        # noinspection SpellCheckingInspection
        self._cmd.chanlist = myChanList  # adjust for our particular context
        # noinspection SpellCheckingInspection
        self._cmd.chanlist_len = self.nbChannels
        self._cmd.scan_end_arg = self.nbChannels
        self._cmd.stop_src = comedi.TRIG_NONE  # never stop

        # test our comedi command a few times.
        for i in range(2):
            ret = comedi.comedi_command_test(self._dev, self._cmd)
            if ret < 0:
                logging.error("comedi_command_test failed: %s", comedi.comedi_strerror(comedi.comedi_errno()))
                raise CmdComediError(comedi.comedi_strerror(comedi.comedi_errno()))

    def __del__(self):
        # logger.debug("in DemoStreamer.__del__()")
        self.stop()
        ret = comedi.comedi_close(self._dev)
        if ret:
            logging.error(comedi.comedi_strerror(comedi.comedi_errno()))
            raise CmdComediError(comedi.comedi_strerror(comedi.comedi_errno()))

    def read(self):
        out = np.empty((self.nbChannels,))
        if not self.__paused:
            # logger.debug("in SamplingThread.read... reading next values")
            line = os.read(self._fd, self._bufferSize)
            n = len(line) / 2  # 2 bytes per 'H'
            # logger.debug("read %s(...) (%d bytes). data is %d items", line[:-5], len(line))
            unpack = struct.unpack('%dH' % n, line)
            # logger.debug("unpacking... got %d values", len(unpack))
            self._remaining.extend(unpack)
            # logger.debug("de-interleaving...")
            out, self._remaining = deinterleave(self._remaining, self.nbChannels)
            # logger.debug("returned a (%d,%d) array and kept %d for next round",
            #               out.shape[0], out.shape[1], len(self._remaining))
            out = self.to_physical(out)
        return out

    def to_physical(self, inData):
        out = inData.astype(np.float64)
        out /= np.reshape(self.__channelMaxValues, (self.nbChannels, 1))
        out *= np.reshape((np.array(self.__channelRangeMaxValues) - np.array(self.__channelRangeMinValues)),
                          (self.nbChannels, 1))
        out += np.reshape(self.__channelRangeMinValues, (self.nbChannels, 1))
        return out

    def start(self):
        # Start the command
        ret = comedi.comedi_command(self._dev, self._cmd)
        if ret != 0:
            logging.error("comedi_command failed... %s", comedi.comedi_strerror(comedi.comedi_errno()))
            raise CmdComediError(comedi.comedi_strerror(comedi.comedi_errno()))
        else:
            self.__paused = False

    def stop(self):
        ret = comedi.comedi_cancel(self._dev, self._subdevice)
        if ret:
            logging.error(comedi.comedi_strerror(comedi.comedi_errno()))
            raise CmdComediError(comedi.comedi_strerror(comedi.comedi_errno()))
        else:
            self.__paused = True
