"""Reference implementation of the Serial Game Server protocol in Python.

Stands in for the STM32 so the GUI and tests can be built before the board
works, and doubles as an executable version of PROTOCOL.md for comparing
against the firmware.

Check order for every incoming frame:
    1. oversize frame            -> NACK:BADCMD  (discard to next terminator)
    2. checksum missing / wrong  -> NACK:CHECKSUM
    3. command syntax            -> NACK:BADCMD
    4. state allows the command  -> NACK:NOGAME / NACK:INGAME
    5. MOVE rules: RANGE, then NOTURN, then OCCUPIED
Every NACK leaves all game state unchanged. Empty lines are ignored silently.
"""

import re
import time

from serial_link import MAX_FRAME, checksum, frame

IDLE, IN_PROGRESS, GAME_OVER = "IDLE", "IN_PROGRESS", "GAME_OVER"
PARTIAL_TIMEOUT = 0.5   # seconds of silence before a partial frame is dropped
EMPTY_BOARD = "." * 9

WIN_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
             (0, 3, 6), (1, 4, 7), (2, 5, 8),
             (0, 4, 8), (2, 4, 6))

_MOVE_RE = re.compile(r"^MOVE:([XO]):(-?\d+)$")


class FakeServer:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._out = []            # queued reply frames (bytes)
        self.reset()
        self._buf = bytearray()
        self._overflow = False
        self._last_rx = 0.0

    # -- game state --------------------------------------------------------
    def reset(self):
        """Back to the boot state (also what a button reset does)."""
        self.state = IDLE
        self.board = list(EMPTY_BOARD)
        self.turn = "X"

    button_press = reset

    def _board_str(self):
        return "".join(self.board)

    def _winner(self):
        for a, b, c in WIN_LINES:
            if self.board[a] != "." and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    # -- byte-level input (mirrors what the firmware RX path must do) -------
    def feed(self, data):
        now = self._clock()
        if self._buf and now - self._last_rx > PARTIAL_TIMEOUT:
            self._buf.clear()
            self._overflow = False
        self._last_rx = now
        for byte in data:
            if byte == 0x0D:                 # ignore '\r'
                continue
            if byte == 0x0A:                 # terminator
                self._end_of_frame()
                continue
            if self._overflow:
                continue
            # buffer limit leaves room for the terminator within MAX_FRAME
            if len(self._buf) >= MAX_FRAME - 1:
                self._overflow = True
                self._buf.clear()
                continue
            self._buf.append(byte)

    def _end_of_frame(self):
        if self._overflow:
            self._overflow = False
            self._buf.clear()
            self._reply("NACK:BADCMD")
            return
        raw = bytes(self._buf)
        self._buf.clear()
        if not raw:
            return
        self._reply(self._handle(raw))

    def _reply(self, payload):
        self._out.append(frame(payload))

    # -- frame / command handling --------------------------------------------
    def _handle(self, raw):
        try:
            text = raw.decode("ascii")
        except UnicodeDecodeError:
            return "NACK:CHECKSUM"
        payload, star, cs = text.rpartition("*")
        if not star or len(cs) != 2 or any(c not in "0123456789ABCDEF" for c in cs):
            return "NACK:CHECKSUM"
        if int(cs, 16) != checksum(payload):
            return "NACK:CHECKSUM"
        return self._dispatch(payload)

    def _dispatch(self, cmd):
        if cmd == "CONNECT":
            return "OK"
        if cmd == "NEW":
            if self.state == IN_PROGRESS:
                return "NACK:INGAME"
            self.board = list(EMPTY_BOARD)
            self.turn = "X"
            self.state = IN_PROGRESS
            return "OK:BOARD:" + EMPTY_BOARD
        if cmd == "STATE":
            if self.state == IDLE:
                return "NACK:NOGAME"
            return "BOARD:" + self._board_str()
        if cmd == "RESIGN":
            if self.state != IN_PROGRESS:
                return "NACK:NOGAME"
            self.state = GAME_OVER
            return "OK:GAMEOVER"
        if cmd == "DISCONNECT":
            self.reset()
            return "OK"
        if cmd.startswith("MOVE"):
            return self._move(cmd)
        return "NACK:BADCMD"

    def _move(self, cmd):
        m = _MOVE_RE.match(cmd)
        if not m:
            return "NACK:BADCMD"
        if self.state != IN_PROGRESS:
            return "NACK:NOGAME"
        mark, index = m.group(1), int(m.group(2))
        if not 0 <= index <= 8:
            return "NACK:RANGE"
        if mark != self.turn:
            return "NACK:NOTURN"
        if self.board[index] != ".":
            return "NACK:OCCUPIED"
        self.board[index] = mark
        winner = self._winner()
        if winner:
            self.state = GAME_OVER
            return "WIN:%s:%s" % (winner, self._board_str())
        if "." not in self.board:
            self.state = GAME_OVER
            return "DRAW:" + self._board_str()
        self.turn = "O" if self.turn == "X" else "X"
        return "OK:BOARD:" + self._board_str()

    # -- transport interface ------------------------------------------------
    def transport(self):
        return FakeTransport(self)


class FakeTransport:
    """Duck-types the parts of pyserial.Serial that SerialLink uses."""

    def __init__(self, server):
        self.server = server

    def write(self, data):
        self.server.feed(data)

    def readline(self):
        if self.server._out:
            return self.server._out.pop(0)
        return b""        # pyserial returns b"" when its timeout expires

    def reset_input_buffer(self):
        self.server._out.clear()

    def close(self):
        pass
