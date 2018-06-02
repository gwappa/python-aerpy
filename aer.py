import numpy as np
import struct
import traceback

end_of_header = "#End Of ASCII Header\r\n".encode()
matched = len(end_of_header)
TICKS_PER_SEC = 1000000
TICKS_PER_MSEC = 1000

def findstart(file):
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

def parse_epxy(bseq):
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

def parse_timestamp(bseq):
    return struct.unpack(fmt_int32_timestamp, bseq)[0]

def parse_event(bseq):
    e, p, x, y = parse_epxy(bseq[:4])
    t = parse_timestamp(bseq[4:])
    return e, p, x, y, t

def read_events_impl(file):
    while True:
        bseq = file.read(8)
        if (len(bseq) < 8):
            break
        yield parse_event(bseq)

def read_events(file):
    """read events from `file` and returns it as an numpy array.

    out[:,0] -- whether or not it is 'special' event.
    out[:,1] -- polarity.
    out[:,2] -- X position.
    out[:,3] -- Y position.
    out[:,4] -- timestamp.
    """
    if isinstance(file, str):
        with open(file, 'rb') as f:
            return read_events(f)
    try:
        file.seek(0)
    except:
        traceback.print_exc()
    findstart(file)
    return np.stack([epxyt for epxyt in read_events_impl(file)], axis=0)
