#
# MIT License
#
# Copyright (c) 2017-2019 Keisuke Sehara
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import numpy as np
from collections import namedtuple as _namedtuple
import struct as _struct

VERSION_STR = "0.4"

end_of_header = "#End Of ASCII Header\r\n".encode()
matched = len(end_of_header)
TICKS_PER_SEC = 1000000
TICKS_PER_MSEC = 1000

DEFAULT_BUFSIZ = 5000000

def find_aer_start(file):
    """finds the start of the event sequence for AER2.0 format."""
    offset = 0
    lines = 0
    while offset < matched:
        c = file.read(1)
        if len(c) == 0:
            raise EOFError()
        c = c[0]
        if c == end_of_header[-1]:
            lines += 1
        if c == end_of_header[offset]:
            offset += 1
        else:
            offset = 0
    return

class _BinaryDecoder:
    def __init__(self, fmt):
        self.fmt = fmt
        self.siz = _struct.calcsize(fmt)
        self.dec = _struct.Struct(fmt)

    def parse(self, file):
        buffer = file.read(self.siz)
        if len(buffer) < self.siz:
            raise EOFError("reached EOF while parsing")
        return self.dec.unpack(buffer)

class _AEDecoder:
    def __init__(self):
        self.dec = _BinaryDecoder('>LL')

    def parse(self, file):
        data, timestamp = self.dec.parse(file)
        isDVS = ((data >> 31) & 0x01 == 0)
        if isDVS == False:
            raise RuntimeError("non-DVS event detected")
        spec  = ((data >> 10) & 0x01 != 0)
        pol   = ((data >> 11) & 0x01 != 0)
        x     = (data >> 12) & 0x03FF
        y     = (data >> 22) & 0x01FF
        return AddressedEvent(timestamp, spec, pol, x, y)

DECODER = _AEDecoder()

class AEFileReader:
    src    = None

    def __init__(self, path, verbose=True):
        self.src     = open(path, 'rb')
        self.verbose = verbose
        try:
            header = self.rewind()
            if self.verbose == True:
                print(f"opened: {path}")
        except EOFError:
            raise RuntimeError(f"not in the AEData format: {path}")

    def rewind(self):
        self.src.seek(0)
        find_aer_start(self.src)

    def __iter__(self):
        try:
            while True:
                yield DECODER.parse(self.src)
        except EOFError:
            pass

    def close(self):
        self.src.close()

    def __enter__(self):
        return self

    def __exit__(self, exc, *args):
        self.close()
        if exc is not None:
            return False

AddressedEvent = _namedtuple('AddressedEvent', ['time','isspecial','polarity','xpos','ypos'])

def histogram(data, xdim=240, ydim=180, on=True, off=True):
    """generates a 2D histogram of event positions.

    parameters
    ----------

    xdim, ydim -- the dimension of the sensor.
    on, off    -- whether to include events with on/off polarity.

    returns
    -------

    histo      -- a 2D histogram.
    """
    histo = np.zeros((xdim,ydim), dtype=int)
    data  = data[~data.isspecial]
    for i in range(data.size()):
        if (bool(data.polarity[i]) == True) and (on == False):
            continue
        elif (bool(data.polarity[i]) == False) and (off == False):
            continue
        histo[int(data.xpos[i]), int(data.ypos[i])] += 1
    return histo


class AEData:
    def __init__(self, path, n=-1, initialsize=None, verbose=False, copy=None):
        """read events from `file` and returns it as an AEData named tuple.

        parameters
        ----------

        path        -- path to the .aedat file.
        n           -- the number of events to read from the file.
        initialsize -- the initial size of the buffer array.
        verbose     -- enables verbose output while reading.
        copy        -- a dictionary to copy arrays from (if set, other params are ignored)

        returns
        -------

        out.time      -- timestamp.
        out.isspecial -- whether or not it is 'special' event.
        out.polarity  -- polarity.
        out.xpos      -- X position.
        out.ypos      -- Y position.

        """
        if copy is not None:
            self.time      = copy['time']
            self.isspecial = copy['isspecial']
            self.polarity  = copy['polarity']
            self.xpos      = copy['xpos']
            self.ypos      = copy['ypos']

        else:
            if initialsize is None:
                initialsize = DEFAULT_BUFSIZ
            size    = initialsize

            time     = np.empty(size, dtype=np.int64)
            special  = np.empty(size, dtype=np.bool)
            polarity = np.empty(size, dtype=np.bool)
            xpos     = np.empty(size, dtype=np.int16)
            ypos     = np.empty(size, dtype=np.int16)
            offset   = 0
            with AEFileReader(path, verbose) as reader:
                for evt in reader:
                    time[offset], special[offset], polarity[offset], \
                        xpos[offset], ypos[offset] = evt
                    offset += 1
                    if (n > 0) and (offset == n):
                        break
                    elif offset == size:
                        # expand
                        size *= 2
                        if verbose == True:
                            print(f"resizing to: {size:>12d}")
                        time.resize(size)
                        special.resize(size)
                        polarity.resize(size)
                        xpos.resize(size)
                        ypos.resize(size)
            # fit
            size = offset
            if verbose == True:
                print(f" fitting to: {size:>12d}")
            time.resize(size)
            special.resize(size)
            polarity.resize(size)
            xpos.resize(size)
            ypos.resize(size)

            self.time      = time
            self.isspecial = special
            self.polarity  = polarity
            self.xpos      = xpos
            self.ypos      = ypos

    def size(self):
        return self.time.size

    def __getitem__(self, flag):
        if isinstance(flag, (str, int)):
            return super().__getitem__(flag)
        return AEData(None, copy=dict(time=self.time[flag],
                        isspecial=self.isspecial[flag],
                        polarity=self.polarity[flag],
                        xpos=self.xpos[flag],
                        ypos=self.ypos[flag]))

    def concatenate(self, other):
        if not isinstance(other, AEData):
            raise ValueError(f"cannot concatenate {other.__class__} to AEData")
        return AEData(None, copy=dict(time=np.concatenate([self.time, other.time]),
                        isspecial=np.concatenate([self.isspecial, other.isspecial]),
                        polarity=np.concatenate([self.polarity, other.polarity]),
                        xpos=np.concatenate([self.xpos, other.xpos]),
                        ypos=np.concatenate([self.ypos, other.ypos])))
