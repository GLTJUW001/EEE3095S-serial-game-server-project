"""Serial link layer for the Serial Game Server (Tic-Tac-Toe).

Shared by the GUI and the pytest harness. Follows Protocol_Spec_v1:

    client -> server   <payload>*<HH>\\n     HH = XOR of payload bytes, 2 hex digits
                                             (server also accepts no checksum)
    server -> client   <payload>\\n          replies carry NO checksum

The server can also send lines nobody asked for. Any line starting with
"EVT:" (currently only EVT:RESET, sent when the board button is pressed) is
asynchronous: it is queued in SerialLink.events and never returned as the
reply to a request.

The transport is anything with write(bytes), readline() -> bytes,
reset_input_buffer() and close(). That is what pyserial's Serial provides, and
fake_server.FakeTransport provides the same interface in-process, so the GUI
and tests run unchanged against either.
"""

SERIAL_BAUD = 115200
MAX_FRAME = 32          # max bytes of a request line, excluding the '\n'
REPLY_TIMEOUT = 1.0     # seconds the client waits for a reply (spec: server answers in 100 ms)
EVENT_PREFIX = "EVT:"


class LinkError(Exception):
    """Base class for link-level problems."""


class LinkTimeout(LinkError):
    """No complete reply line arrived in time."""


def checksum(payload):
    """XOR of all payload bytes. Accepts str (ASCII) or bytes."""
    if isinstance(payload, str):
        payload = payload.encode("ascii")
    value = 0
    for b in payload:
        value ^= b
    return value


def frame(payload, with_checksum=True):
    """Build a request line: payload [+ '*HH'] + newline."""
    if isinstance(payload, bytes):
        payload = payload.decode("ascii")
    if with_checksum:
        return "{}*{:02X}\n".format(payload, checksum(payload)).encode("ascii")
    return (payload + "\n").encode("ascii")


def decode_reply(line):
    """Turn a received line (bytes) into a str with the newline removed."""
    return line.decode("ascii", errors="replace").rstrip("\r\n")


class SerialLink:
    """Request/response wrapper around a transport."""

    def __init__(self, transport):
        self.transport = transport
        self.events = []          # unsolicited EVT: lines, oldest first

    @classmethod
    def open_port(cls, port, baud=SERIAL_BAUD, timeout=REPLY_TIMEOUT):
        """Open a real serial port (e.g. 'COM5' or '/dev/ttyACM0')."""
        import serial  # imported here so the fake server works without pyserial

        return cls(serial.Serial(port, baud, bytesize=8, parity="N",
                                 stopbits=1, timeout=timeout))

    # -- sending -----------------------------------------------------------
    def send(self, payload, with_checksum=True):
        """Send one request line (checksummed unless with_checksum=False)."""
        self.transport.write(frame(payload, with_checksum))

    def send_raw(self, data):
        """Send bytes exactly as given (for bad-checksum / garbage tests)."""
        self.transport.write(data)

    # -- receiving ---------------------------------------------------------
    def read_raw(self):
        """Read one line as raw bytes. Raises LinkTimeout if incomplete."""
        line = self.transport.readline()
        if not line.endswith(b"\n"):
            raise LinkTimeout("no complete reply line received")
        return line

    def read(self):
        """Read the next reply line. EVT: lines are queued, not returned."""
        while True:
            text = decode_reply(self.read_raw())
            if text.startswith(EVENT_PREFIX):
                self.events.append(text)
                continue
            return text

    def request(self, payload, with_checksum=True):
        """Send one command and return the server's reply."""
        self.send(payload, with_checksum)
        return self.read()

    def take_events(self):
        """Return and clear the queued unsolicited events."""
        events, self.events = self.events, []
        return events

    # -- housekeeping ------------------------------------------------------
    def flush_input(self):
        self.transport.reset_input_buffer()

    def close(self):
        self.transport.close()
