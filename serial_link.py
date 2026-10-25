"""Serial link layer for the Serial Game Server (Tic-Tac-Toe).

Shared by the GUI and the pytest harness. Handles the framing rules from
PROTOCOL.md:

    <payload>*<XX>\\n        XX = XOR of all payload bytes, 2 uppercase hex digits

The transport is anything with write(bytes), readline() -> bytes,
reset_input_buffer() and close(). That is exactly what pyserial's Serial
provides, and fake_server.FakeTransport provides the same interface in-process,
so the GUI and tests run unchanged against either.
"""

SERIAL_BAUD = 115200
MAX_FRAME = 32          # bytes on the wire including the terminator
REPLY_TIMEOUT = 1.0     # seconds the client waits for a reply


class LinkError(Exception):
    """Base class for link-level problems."""


class LinkTimeout(LinkError):
    """No complete reply line arrived in time."""


class ChecksumError(LinkError):
    """A reply arrived but its checksum was missing or wrong."""


def checksum(payload):
    """XOR of all payload bytes. Accepts str (ASCII) or bytes."""
    if isinstance(payload, str):
        payload = payload.encode("ascii")
    value = 0
    for b in payload:
        value ^= b
    return value


def frame(payload):
    """Build a wire frame: payload + '*' + 2 hex digits + newline."""
    if isinstance(payload, bytes):
        payload = payload.decode("ascii")
    return "{}*{:02X}\n".format(payload, checksum(payload)).encode("ascii")


def unframe(line):
    """Validate a received line and return its payload as str.

    Raises ChecksumError if the line is not a correctly checksummed frame.
    """
    try:
        text = line.decode("ascii").rstrip("\r\n")
    except UnicodeDecodeError:
        raise ChecksumError("non-ASCII data in reply: %r" % line)
    payload, star, cs = text.rpartition("*")
    if not star or len(cs) != 2:
        raise ChecksumError("missing checksum in reply: %r" % text)
    try:
        expected = int(cs, 16)
    except ValueError:
        raise ChecksumError("bad checksum digits in reply: %r" % text)
    if expected != checksum(payload):
        raise ChecksumError(
            "checksum mismatch in reply %r (computed %02X)" % (text, checksum(payload))
        )
    return payload


class SerialLink:
    """Request/response wrapper around a transport."""

    def __init__(self, transport):
        self.transport = transport

    @classmethod
    def open_port(cls, port, baud=SERIAL_BAUD, timeout=REPLY_TIMEOUT):
        """Open a real serial port (e.g. 'COM5' or '/dev/ttyACM0')."""
        import serial  # imported here so the fake server works without pyserial

        return cls(serial.Serial(port, baud, bytesize=8, parity="N",
                                 stopbits=1, timeout=timeout))

    # -- sending -----------------------------------------------------------
    def send(self, payload):
        """Send a payload with a correct checksum appended."""
        self.transport.write(frame(payload))

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
        """Read one reply and return its verified payload."""
        return unframe(self.read_raw())

    def request(self, payload):
        """Send one command and return the server's reply payload."""
        self.send(payload)
        return self.read()

    # -- housekeeping ------------------------------------------------------
    def flush_input(self):
        self.transport.reset_input_buffer()

    def close(self):
        self.transport.close()
