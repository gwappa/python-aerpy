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
from collections import namedtuple
import struct
import traceback

VERSION_STR = "0.3"

end_of_header = "#End Of ASCII Header\r\n".encode()
matched = len(end_of_header)
TICKS_PER_SEC = 1000000
TICKS_PER_MSEC = 1000

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

fmt_int32_raddr = '>I'
fmt_int16_waddr = '>H'
fmt_int16_raddr = '>H'
fmt_int32_timestamp = ">i"

class AEData(namedtuple('_AEData', ['time','isspecial','polarity','xpos','ypos'])):
    @classmethod
    def empty(cls, n=1):
        return cls(np.empty(n, dtype=int),
                    np.empty(n, dtype=bool),
                    np.empty(n, dtype=bool),
                    np.empty(n, dtype=int),
                    np.empty(n, dtype=int))
    def size(self):
        return self.time.size

    def set(self, idx, t, e, p, x, y):
        self.time[idx]      = t
        self.isspecial[idx] = e
        self.polarity[idx]  = p
        self.xpos[idx]      = x
        self.ypos[idx]      = y

    def __getitem__(self, flag):
        if isinstance(flag, (str, int)):
            return super().__getitem__(flag)
        return AEData(self.time[flag], self.isspecial[flag], self.polarity[flag], self.xpos[flag], self.ypos[flag])

    def concatenate(self, other):
        if not isinstance(other, AEData):
            raise ValueError(f"cannot concatenate {other.__class__} to AEData")
        return AEData(np.concatenate([self.time, other.time]),
                        np.concatenate([self.isspecial, other.isspecial]),
                        np.concatenate([self.polarity, other.polarity]),
                        np.concatenate([self.xpos, other.xpos]),
                        np.concatenate([self.ypos, other.ypos]))


def histogram(data, xdim=240, ydim=180, on=True, off=True):
    histo = np.zeros((xdim,ydim), dtype=int)
    data  = data[~data.isspecial]
    for i in range(data.size()):
        if (bool(data.polarity[i]) == True) and (on == False):
            continue
        elif (bool(data.polarity[i]) == False) and (off == False):
            continue
        histo[int(data.xpos[i]), int(data.ypos[i])] += 1
    return histo

def _impl_parse_epxy(bseq):
    """parses 32-bit `bseq` to return X pos, Y pos and polarity."""
    rawaddr = struct.unpack(fmt_int32_raddr, bseq)[0]
    bx = (rawaddr >> 12) & 0b1111111111
    by = (rawaddr >> 22) & 0b111111111
    be = (rawaddr >> 10) & 0b01
    bp = (rawaddr >> 11) & 0b01
    x = struct.unpack(fmt_int16_raddr, struct.pack(fmt_int16_waddr, bx))[0]
    y = struct.unpack(fmt_int16_raddr, struct.pack(fmt_int16_waddr, by))[0]
    e = (be == 1)
    p = (bp == 1)
    return e, p, x, y

def _impl_parse_timestamp(bseq):
    return struct.unpack(fmt_int32_timestamp, bseq)[0]

def parse_event(bseq):
    e, p, x, y = _impl_parse_epxy(bseq[:4])
    t = _impl_parse_timestamp(bseq[4:])
    return t, e, p, x, y

def _impl_read_events(file):
    data = AEData([],[],[],[],[])
    while True:
        bseq = file.read(8)
        if (len(bseq) < 8):
            break
        for arr, item in zip(data, parse_event(bseq)):
            arr.append(item)
    return AEData(*[np.array(buf) for buf in data])

def _impl_read_nevents(file, n=1):
    data = AEData.empty(n)
    i = 0
    while i < n:
        bseq = file.read(8)
        if (len(bseq) < 8):
            break
        data.set(i, *(parse_event(bseq)))
        i += 1
    return i, data

def _impl_filter_events(file, cond, min_interval_ticks):
    data = AEData([],[],[],[],[])
    status = "NA"
    min_timestamp = None
    while True:
        bseq = file.read(8)
        if (len(bseq) < 8):
            status = "EOF"
            break
        t, e, p, x, y = parse_event(bseq)
        data.time.append(t)
        data.isspecial.append(e)
        data.polarity.append(p)
        data.xpos.append(x)
        data.ypos.append(y)
        if min_timestamp is None:
            min_timestamp = t + min_interval_ticks
        if cond(t, e, p, x, y) == True:
            if t >= min_timestamp:
                status = "break"
                break
            else:
                min_timestamp = t + min_interval_ticks
    return status, AEData(*[np.array(buf) for buf in data])

class EventStatus:
    @staticmethod
    def is_special(t, e, p, x, y):
        return (e == True)

    @staticmethod
    def is_addressed(t, e, p, x, y):
        return (e == False)

    @staticmethod
    def is_on(t, e, p, x, y):
        return (p == True)

    @staticmethod
    def is_off(t, e, p, x, y):
        return (p == False)

def read(file, n=-1):
    """read events from `file` and returns it as an AEData named tuple.

    out.isspecial -- whether or not it is 'special' event.
    out.polarity  -- polarity.
    out.xpos      -- X position.
    out.ypos      -- Y position.
    out.time      -- timestamp.
    """
    if isinstance(file, str):
        with open(file, 'rb') as f:
            return read(f)
    try:
        file.seek(0)
    except:
        traceback.print_exc()
    find_aer_start(file)
    if isinstance(n, int) and n > 0:
        return _impl_read_nevents(file, n)
    else:
        return _impl_read_events(file)

class AEReader:
    """the reader interface for AER2.0 files."""
    def __init__(self, path):
        self._path = path
        try:
            self._file = open(str(path), 'rb')
            self._file.seek(0)
            find_aer_start(self._file)
            self._start = self._file.tell()
        except:
            traceback.print_exc()
            self._file.close()

    def close(self):
        self._file.close()

    def read(self, n=1):
        i, events   = _impl_read_nevents(self._file, n)
        self.status = i
        return events

    def read_all(self, rewind=False):
        events = _impl_read_events(self._file)
        if rewind == True:
            self._file.seek(self._start)
        return events

    def read_upto(self, cond=EventStatus.is_special, min_interval_ticks=TICKS_PER_SEC):
        status, events  = _impl_filter_events(self._file, cond, min_interval_ticks)
        self.status     = status
        return events

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
