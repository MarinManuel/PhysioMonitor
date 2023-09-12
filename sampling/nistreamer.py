import nidaqmx
import nidaqmx.constants
import nidaqmx.stream_readers
import numpy as np
from sampling.sampling import Streamer

# noinspection SpellCheckingInspection
terminalConfig = {
    "DEFAULT": nidaqmx.constants.TerminalConfiguration.DEFAULT,
    "RSE": nidaqmx.constants.TerminalConfiguration.RSE,
    "NRSE": nidaqmx.constants.TerminalConfiguration.NRSE,
    "DIFFERENTIAL": nidaqmx.constants.TerminalConfiguration.DIFF,
    "PSEUDODIFFERENTIAL": nidaqmx.constants.TerminalConfiguration.PSEUDO_DIFF,
}


class NIStreamer(Streamer):
    def __init__(self, sampling_rate, device, channels, input_modes, buffer_size=1000):
        self.buffer_size = buffer_size
        self.nbChannels = len(channels)
        self.task = nidaqmx.Task()
        for channel, mode in zip(channels, input_modes):
            if mode.upper() not in nidaqmx.constants.TerminalConfiguration.__members__:
                raise ValueError(
                    f'Invalid input mode "{mode}". Must be one of '
                    f'{", ".join(nidaqmx.constants.TerminalConfiguration.__members__.keys())}'
                )
            self.task.ai_channels.add_ai_voltage_chan(
                physical_channel=f"{device}/{channel}",
                terminal_config=terminalConfig[mode],
            )
        self.task.timing.cfg_samp_clk_timing(
            sampling_rate,
            sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS,
            samps_per_chan=self.buffer_size,
        )
        self.stream = nidaqmx.stream_readers.AnalogMultiChannelReader(
            self.task.in_stream
        )
        self.data = np.empty((self.nbChannels, 0))
        self.task.register_every_n_samples_acquired_into_buffer_event(
            self.buffer_size, self.reading_task_callback
        )

    # noinspection PyUnusedLocal
    def reading_task_callback(
        self, task_handle, every_n_samples_event_type, number_of_samples, callback_data
    ):
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

    def read(self):
        out = self.data
        self.data = np.empty(shape=(self.nbChannels, 0))
        return out
