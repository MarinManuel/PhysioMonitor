import logging
import numpy as np

from monitor.demostreamer import DemoStreamer
from monitor.nistreamer import NIStreamer

logger = logging.getLogger(__name__)


def deinterleave(inData, nChan, dtype=int):
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
        inData: numpy array
        nChan: number of channels
        dtype: dtype of the resulting array
    """
    n = len(inData)
    nToKeep = n - (n % nChan)
    outData = np.array(inData[:nToKeep], dtype=dtype).reshape((-1, nChan)).transpose()
    remainData = inData[nToKeep:]
    return outData, remainData


class Streamer(object):
    def read(self):
        return np.array([])

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        pass


AVAIL_ACQ_MODULES = {'demo': DemoStreamer,
                     'nidaqmx': NIStreamer}
