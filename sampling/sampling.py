import logging
import numpy as np

logger = logging.getLogger(__name__)


# noinspection SpellCheckingInspection
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
    Otherwise, remainData is an _empty array

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
    """
    This is an object that represents a sampling system.
    Should initialize the sampling system, but not start the sampling itself
    Data is stored in an Numpy array of shape (number of channels, N)
    """

    _empty = np.empty(shape=(0, 0))

    def start(self):
        """
        starts the sampling system. starts collecting data
        """
        pass

    def read(self):
        """
        :return: a numpy array of shape (number of channels, N) containing the data sampled since the last call.
        """
        return self._empty

    def stop(self):
        """
        stops the sampling system
        """
        pass

    def close(self):
        """
        clean-up
        """
        pass
