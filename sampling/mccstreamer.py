import logging
from uldaq import (get_daq_device_inventory, DaqDevice, AInScanFlag,
                   AiInputMode, AiQueueElement, create_float_buffer,
                   ScanOption, InterfaceType, Range, ScanStatus)
from .sampling import Streamer, deinterleave
import numpy as np

logger = logging.getLogger(__name__)


def get_rolling_data(buffer, last_index, current_index):
    """
    Extracts the part of the data that is between last_index and index
    This function is able to deal with a rolling buffer where new data can
    wrap to the beginning of the buffer when reaching the end.

    :param buffer: the rolling buffer
    :param last_index: the last index read
    :param current_index: the current index
    :return: numpy array
    """
    return np.roll(buffer, -last_index)[:(current_index - last_index)]


class MCCStreamer(Streamer):
    def __init__(self, sampling_rate, device, channels, input_modes, input_ranges, buffer_size=1000) -> None:
        super().__init__()
        self._buffer_size = buffer_size
        self._sampling_rate = sampling_rate

        devices = get_daq_device_inventory(InterfaceType.ANY)
        self._daq_device = DaqDevice(devices[device])
        self._ai_device = self._daq_device.get_ai_device()
        self._daq_device.connect(connection_code=0)
        self._ai_info = self._ai_device.get_info()
        logger.debug(f"created MCC DAQ device: {self._ai_info}")

        self._queue_list = []
        for channel, in_mode, in_range in zip(channels, input_modes, input_ranges):
            if in_mode.upper() not in AiInputMode.__members__:
                raise ValueError(f'Invalid input mode "{in_mode}". Must be one of '
                                 f'{", ".join(AiInputMode.__members__.keys())}')
            if in_range.upper() not in Range.__members__:
                raise ValueError(f'Invalid input range "{in_range}". Must be one of '
                                 f'{", ".join(Range.__members__.keys())}')
            queue_element = AiQueueElement()
            queue_element.channel = channel
            queue_element.input_mode = getattr(AiInputMode, in_mode.upper())
            queue_element.range = getattr(Range, in_range.upper())
            self._queue_list.append(queue_element)

        # some MCC devices--including USB-201--require that the channels in the queue be in ascending order
        # we're sorting `_queue_list` using the channel number, but we keep track of the original position
        # so we can extract the relevant row from the __data when it is time to use the __data
        self._row_pos = range(len(self._queue_list))
        self._sorted_queue, self._row_pos = zip(*sorted(zip(self._queue_list, self._row_pos),
                                                        key=lambda x: x[0].channel))

        self._ai_device.a_in_load_queue(self._sorted_queue)
        self.__data = create_float_buffer(len(channels), self._buffer_size)
        self._last_index = 0
        self._empty = np.empty(shape=(len(channels),))

    def start(self):
        scan_options = ScanOption.DEFAULTIO | ScanOption.CONTINUOUS
        flags = AInScanFlag.DEFAULT
        # noinspection PyTypeChecker
        self._sampling_rate = self._ai_device.a_in_scan(0, 0, 0, 0,  # arguments are ignored if using queues
                                                        self._buffer_size,
                                                        self._sampling_rate, scan_options, flags, self.__data)
        logger.debug(f"Started sampling at {self._sampling_rate} Hz...")

    def read(self):
        status, transfer_status = self._ai_device.get_scan_status()
        index = transfer_status.current_index
        if index != self._last_index:
            out, _ = deinterleave(get_rolling_data(self.__data, self._last_index, index),
                                  len(self._queue_list),
                                  dtype=float)
            self._last_index = index
            return out[self._row_pos, :]
        else:
            return self._empty

    def stop(self):
        status, transfer_status = self._ai_device.get_scan_status()
        if status == ScanStatus.RUNNING:
            self._ai_device.scan_stop()

    def close(self):
        self.stop()
        if self._daq_device.is_connected():
            self._daq_device.disconnect()
        self._daq_device.release()
