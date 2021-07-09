import logging

from uldaq import (get_daq_device_inventory, DaqDevice, AInScanFlag,
                   AiInputMode, AiQueueElement, create_float_buffer,
                   ScanOption, InterfaceType, Range, ScanStatus)
from sampling import Streamer, deinterleave
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
    def __init__(self) -> None:
        super().__init__()
        channel_list = [7, 3, 0]
        self.bufferSz = 500
        self._sampling_rate = 100

        devices = get_daq_device_inventory(InterfaceType.ANY)
        self._daq_device = DaqDevice(devices[0])
        self._ai_device = self._daq_device.get_ai_device()
        self._daq_device.connect(connection_code=0)
        self._ai_info = self._ai_device.get_info()

        self._queue_list = []
        for channel in channel_list:
            queue_element = AiQueueElement()
            queue_element.channel = channel
            queue_element.input_mode = AiInputMode.SINGLE_ENDED
            queue_element.range = Range.BIP10VOLTS
            self._queue_list.append(queue_element)

        # some MCC devices--including USB-201--require that the channels in the queue be in ascending order
        # we're sorting `_queue_list` using the channel number, but we keep track of the original position
        # so we can extract the relevant row from the __data when it is time to use the __data
        self._row_pos = range(len(self._queue_list))
        self._sorted_queue, self._row_pos = zip(*sorted(zip(self._queue_list, self._row_pos),
                                                        key=lambda x: x[0].channel))

        self._ai_device.a_in_load_queue(self._sorted_queue)
        self.__data = create_float_buffer(len(channel_list), self.bufferSz)
        self._last_index = 0

    def start(self):
        scan_options = ScanOption.DEFAULTIO | ScanOption.CONTINUOUS
        flags = AInScanFlag.DEFAULT
        self._sampling_rate = self._ai_device.a_in_scan(0, 0, AiInputMode.SINGLE_ENDED, Range.UNI10VOLTS, self.bufferSz,
                                                        self._sampling_rate, scan_options, flags, self.__data)

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
            return

    def stop(self):
        status, transfer_status = self._ai_device.get_scan_status()
        if status == ScanStatus.RUNNING:
            self._ai_device.scan_stop()

    def close(self):
        self.stop()
        if self._daq_device.is_connected():
            self._daq_device.disconnect()
        self._daq_device.release()
