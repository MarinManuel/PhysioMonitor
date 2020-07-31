import os
import struct
import time
import numpy as np
import pandas as pd
import logging
import serial

# noinspection PyBroadException
try:
    import comedi
except:
    pass

import nidaqmx
import nidaqmx.constants
from nidaqmx.stream_readers import AnalogMultiChannelReader
from nidaqmx.stream_writers import AnalogMultiChannelWriter


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
    def __init__(self, nChans=1, sampleFreq=1000., filename="./media/surgery.txt", start=True, pointsToReturn=None):
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


class ComediStreamer(Streamer):
    # noinspection PyMissingConstructor
    def __init__(self, config, bufferSize=10000, start=True):
        # logging.debug("in SurgeryFileStreamer __init__")
        self._remaining = []
        self._bufferSize = bufferSize
        self._config = config
        self.__chanMaxValues = []
        self.__chanRangeMins = []
        self.__chanRangeMaxs = []
        self.nbChans = len(self._config['channels'])
        self.__paused = not start

        # configure the comedi device
        self._dev = comedi.comedi_open(str(self._config['device']))
        if not self._dev:
            logging.error("FATAL ERROR: cannot open comedi device: %s", comedi.comedi_strerror(comedi.comedi_errno()))
            raise IOError(comedi.comedi_strerror(comedi.comedi_errno()))

        # and get an appropriate subdevice
        self._subdev = self._config['sub-device']

        for chan in self._config['channels']:
            self.__chanMaxValues.append(comedi.comedi_get_maxdata(self._dev, self._subdev, chan['channel-id']))
            temp = comedi.comedi_get_range(self._dev, self._subdev, chan['channel-id'], chan['gain'])
            self.__chanRangeMins.append(temp.min)
            self.__chanRangeMaxs.append(temp.max)

        # get a file-descriptor for reading
        self._fd = comedi.comedi_fileno(self._dev)
        if self._fd <= 0:
            logging.error("Error obtaining comedi device file descriptor: %s",
                          comedi.comedi_strerror(comedi.comedi_errno()))
            raise IOError(comedi.comedi_strerror(comedi.comedi_errno()))

        # create channel list
        myChanList = comedi.chanlist(self.nbChans)
        for i, chan in enumerate(self._config['channels']):
            myChanList[i] = comedi.cr_pack(chan['channel-id'],
                                           chan['gain'],
                                           chan['ref'])
        # create a command structure
        self._cmd = comedi.comedi_cmd_struct()
        ret = comedi.comedi_get_cmd_generic_timed(self._dev,
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
        self._cmd.stop_src = comedi.TRIG_NONE  # never stop

        # test our comedi command a few times.
        for i in range(2):
            ret = comedi.comedi_command_test(self._dev, self._cmd)
            if ret < 0:
                logging.error("comedi_command_test failed: %s", comedi.comedi_strerror(comedi.comedi_errno()))
                raise CmdComediError(comedi.comedi_strerror(comedi.comedi_errno()))

    def __del__(self):
        # logging.debug("in SurgeryFileStreamer.__del__()")
        self.stop()
        ret = comedi.comedi_close(self._dev)
        if ret:
            logging.error(comedi.comedi_strerror(comedi.comedi_errno()))
            raise CmdComediError(comedi.comedi_strerror(comedi.comedi_errno()))

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
        ret = comedi.comedi_command(self._dev, self._cmd)
        if ret != 0:
            logging.error("comedi_command failed... %s", comedi.comedi_strerror(comedi.comedi_errno()))
            raise CmdComediError(comedi.comedi_strerror(comedi.comedi_errno()))
        else:
            self.__paused = False

    def stop(self):
        ret = comedi.comedi_cancel(self._dev, self._subdev)
        if ret:
            logging.error(comedi.comedi_strerror(comedi.comedi_errno()))
            raise CmdComediError(comedi.comedi_strerror(comedi.comedi_errno()))
        else:
            self.__paused = True


# this streamer must be provided with a config['hardware']['module'] == 'nidaqmx'
# valid keys are:
#       "device": "Dev1", # name of the device
#       "physical-channels": [ # list of the ports to use
#         "ao0",
#         "ao1",
#         "ao2",
#         "ao3"],
#       "physical-channel-terminal": ["RSE","RSE","RSE","RSE"],
#                                   # Terminal configuration.
#                                   # valid names are "DEFAULT", "RSE", "NRSE", "DIFFERENTIAL", "PSEUDODIFFERENTIAL"
#       "physical-channel-range": [[-5,5],[-5,5], [-5,5], [-5,5]]

terminalConfig = {"DEFAULT": nidaqmx.constants.TerminalConfiguration.DEFAULT,
                  "RSE": nidaqmx.constants.TerminalConfiguration.RSE,
                  "NRSE": nidaqmx.constants.TerminalConfiguration.NRSE,
                  "DIFFERENTIAL": nidaqmx.constants.TerminalConfiguration.DIFFERENTIAL,
                  "PSEUDODIFFERENTIAL": nidaqmx.constants.TerminalConfiguration.PSEUDODIFFERENTIAL}


class nistreamer(Streamer):
    def __init__(self, config, buffer_size=1000):
        self.buffer_size = buffer_size
        self.n_chans = len(config['hardware']['physical-channels'])
        self.task = nidaqmx.Task()
        for channelPort, channelTerminal, channelRange in zip(config['hardware']["physical-channels"],
                                                              config['hardware']["physical-channel-terminal"],
                                                              config['hardware']["physical-channel-range"]):
            self.task.ai_channels.add_ai_voltage_chan(physical_channel='{}/{}'.format(config['hardware']['device'],
                                                                                      channelPort),
                                                      terminal_config=terminalConfig[channelTerminal],
                                                      min_val=min(channelRange),
                                                      max_val=max(channelRange))
        self.task.timing.cfg_samp_clk_timing(config['sample-rate'],
                                             sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
                                             samps_per_chan=self.buffer_size)
        self.stream = AnalogMultiChannelReader(self.task.in_stream)
        self.data = np.empty((self.n_chans, 0))
        self.task.register_every_n_samples_acquired_into_buffer_event(self.buffer_size, self.reading_task_callback)

    def reading_task_callback(self, task_handle, every_n_samples_event_type, number_of_samples, callback_data):
        buffer = np.empty(shape=(self.n_chans, number_of_samples))
        self.stream.read_many_sample(buffer, number_of_samples)
        self.data = np.append(self.data, buffer, axis=1)
        return 0

    def start(self):
        self.task.start()

    def stop(self):
        self.task.stop()

    def close(self):
        self.stop()
        self.task.close()

    def iterator(self):
        out = self.data
        self.data = np.empty(shape=(self.n_chans, 0))
        yield out

    def read(self):
        out = self.data
        self.data = np.empty(shape=(self.n_chans, 0))
        return out


class nistreamerSin(nistreamer):
    def __init__(self, config, buffer_size=1000, sin_freq=1.):
        super().__init__(config, buffer_size)
        self.task_out = nidaqmx.Task()
        out_dur = 2.
        n_out_points = int(out_dur * config['sample-rate'])
        t = np.linspace(0, out_dur, n_out_points)
        v = 5 * np.sin(t * sin_freq * 2 * np.pi)
        self.task_out.ao_channels.add_ao_voltage_chan('Dev1/ao0')
        self.task_out.timing.cfg_samp_clk_timing(rate=config['sample-rate'],
                                                 sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
                                                 samps_per_chan=n_out_points)
        self.writer = AnalogMultiChannelWriter(self.task_out.out_stream)
        v = np.reshape(v, (len(self.task_out.ao_channels), len(v)))
        self.writer.write_many_sample(v)

    def start(self):
        super(nistreamerSin, self).start()
        self.task_out.start()

    def stop(self):
        super(nistreamerSin, self).stop()
        self.task_out.stop()

    def close(self):
        super(nistreamerSin, self).close()
        self.task_out.close()


class nistreamerPhysio(nistreamer):
    def __init__(self, config, buffer_size=1000, nChan=1, sampleFreq=1000., filename="surgery.txt", nPoints=10000):
        super(nistreamerPhysio, self).__init__(config, buffer_size)

        self._nChan = nChan
        self._sampleFreq = sampleFreq
        self._nPoints = nPoints
        self._table = pd.read_csv(filename, sep='\t', index_col=0)
        self._data = np.array(self._table.iloc[:self._nPoints, :self._nChan].values.T, copy=True, order='C')

        self.task_out = nidaqmx.Task()
        for i in range(self._nChan):
            self.task_out.ao_channels.add_ao_voltage_chan(f'Dev1/ao{i}')
        self.task_out.timing.cfg_samp_clk_timing(rate=self._sampleFreq,
                                                 sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
                                                 samps_per_chan=self._nPoints)
        self.writer = AnalogMultiChannelWriter(self.task_out.out_stream)
        self.writer.write_many_sample(self._data)

    def start(self):
        super(nistreamerPhysio, self).start()
        self.task_out.start()

    def stop(self):
        super(nistreamerPhysio, self).stop()
        self.task_out.stop()

    def close(self):
        super(nistreamerPhysio, self).close()
        self.task_out.close()


AVAIL_ACQ_MODULES = {'nidaqmx': nistreamer,
                     'nidaqmxSin': nistreamerSin,
                     'nidaqmxPhysio': nistreamerPhysio,
                     'demo': SurgeryFileStreamer}
