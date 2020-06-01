import numpy as np
# import logging


# noinspection PyRedeclaration
class RollingBuffer:
    """
    a rolling buffer
    elements are added line-wise to the right of the matrix and shift previous elements to the left
    ex:
    0 1 2     5 5     2 5 5
    3 4 5  +  6 6  =  5 6 6
    6 7 8     7 7     8 7 7
    """
    def __init__(self, size=100, nLines=1, fill=0.0):
        self._size = size
        self._nLines = nLines
        self._buffer = np.full((nLines, size), fill, dtype=np.array(fill).dtype)

    def append(self, items):
        # logging.debug('in RollingBuffer.append(). Items received are %s: %s', np.shape(items), items)

        # let's make sure we're dealing with a numpy array
        items = np.array(items)

        if items.size == 0:
            return  # empty array, nothing to do

        # let's make sure items has the right dimensions
        shape = items.shape
        if len(shape) == 1:  # got a vector
            if self._nLines == 1:  # but that's OK since we have a 1 dimensional RollingBuffer
                items = np.reshape(items, (1, len(items)))
            else:
                raise ValueError("ERROR: the items to be added to the RollingBuffer have the wrong number of "
                                 "dimensions %s", self._buffer.shape)
        else:  # got a matrix
            nLinesItems = items.shape[0]
            if nLinesItems != self._nLines:
                raise ValueError("ERROR: the items to be added to the RollingBuffer have the wrong number of "
                                 "dimensions %s", self._buffer.shape)

        # do the thing
        _, n = np.shape(items)
        self._buffer = np.roll(self._buffer, -1 * n, 1)
        self._buffer[:, -1 * n:] = items[:, -1 * self._size:]

    def __repr__(self):
        return self._buffer.__repr__()

    def min(self, axis=None, out=None):
        return self._buffer.min(axis, out)

    def max(self, axis=None, out=None):
        return self._buffer.max(axis, out)

    def size(self):
        return self._buffer.size

    def shape(self):
        return self._buffer.shape

    def values(self):
        return self._buffer

    def __getitem__(self, item):
        return self._buffer.__getitem__(item)
