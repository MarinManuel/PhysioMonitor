# -*- coding: utf-8 -*-
import nidaqmx
import nidaqmx.constants
from nidaqmx.stream_readers import AnalogMultiChannelReader
from nidaqmx.stream_writers import AnalogMultiChannelWriter

from sampling import Streamer, AVAIL_ACQ_MODULES
import numpy as np
import pandas as pd

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


class NIStreamer(Streamer):
    def __init__(self, config, buffer_size=1000):
        self.buffer_size = buffer_size
        self.nbChannels = len(config['hardware']['physical-channels'])
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
        self.data = np.empty((self.nbChannels, 0))
        self.task.register_every_n_samples_acquired_into_buffer_event(self.buffer_size, self.reading_task_callback)

    # noinspection PyUnusedLocal
    def reading_task_callback(self, task_handle, every_n_samples_event_type, number_of_samples, callback_data):
        buffer = np.empty(shape=(self.nbChannels, number_of_samples))
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
        self.data = np.empty(shape=(self.nbChannels, 0))
        yield out

    def read(self):
        out = self.data
        self.data = np.empty(shape=(self.nbChannels, 0))
        return out


class NIStreamerSin(NIStreamer):
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
        super(NIStreamerSin, self).start()
        self.task_out.start()

    def stop(self):
        super(NIStreamerSin, self).stop()
        self.task_out.stop()

    def close(self):
        super(NIStreamerSin, self).close()
        self.task_out.close()


class NIStreamerPhysio(NIStreamer):
    def __init__(self, config, buffer_size=1000, nChan=1, sampleFreq=1000., filename="file_streamer_data.txt",
                 nPoints=10000):
        """
        Create a dummy streamer that outputs the values read from `filename` on the DAC(s) so that they can be read
        back using the ADCs

        :param config: configuration object to create the acquisition objects
        :param buffer_size: buffer size
        :param nChan: number of channels to output
        :param sampleFreq: output rate (Hz)
        :param filename: file containing the data to output
        :param nPoints: number of points to output
        """
        super(NIStreamerPhysio, self).__init__(config, buffer_size)

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
        super(NIStreamerPhysio, self).start()
        self.task_out.start()

    def stop(self):
        super(NIStreamerPhysio, self).stop()
        self.task_out.stop()

    def close(self):
        super(NIStreamerPhysio, self).close()
        self.task_out.close()


# noinspection SpellCheckingInspection
AVAIL_ACQ_MODULES = {**AVAIL_ACQ_MODULES, 'nidaqmx': NIStreamer}
