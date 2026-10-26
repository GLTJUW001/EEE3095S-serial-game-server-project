"""Python model of the STM32 server, mirroring the firmware (Protocol_Spec_v1).

Stands in for the board so the GUI and tests can be built and run without it.
It follows the same structure as the C code (parser.c / server.c / game.c):

  parser   - '\\r' ignored, '\\n' ends a frame, >32 bytes -> NACK:OVERFLOW once
             then discard to the next '\\n', 500 ms of silence mid-frame ->
             NACK:TIMEOUT, non-printable bytes / empty line -> NACK:BADCMD,
             optional '*HH' XOR checksum (present but wrong -> NACK:CHECKSUM)
  server   - IDLE / PLAY / OVER state machine and the reply strings
  game     - MOVE checks in order: NOTURN, RANGE, OCCUPIED; board written last

Replies carry no checksum. button_press() queues the unsolicited EVT:RESET.
"""

import time

from serial_link import MAX_FRAME

IDLE, PLAY, OVER = "IDLE", "PLAY", "OVER"
PARTIAL_TIMEOUT = 0.5   # seconds of silence before a partial frame is dropped
EMPTY_BOARD = "." * 9

WIN_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
             (0, 3, 6), (1, 4, 7), (2, 5, 8),
             (0, 4, 8), (2, 4, 6))


def _hex_value(ch):
    if len(ch) == 1 and ch in "0123456789abcdefABCDEF":
        return int(ch, 16)
    return -1


class FakeServer:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._out = []               # queued reply lines (bytes, with '\n')
        self._buf = bytearray()
        self._discarding = False
        self._last_byte = clock()
        self.reset()

    # -- game ------------------------------------------------------------------
    def reset(self):
        """Boot state; also what the button and DISCONNECT do."""
        self.state = IDLE
        self._game_reset()

    def _game_reset(self):
        self.board = list(EMPTY_BOARD)
        self.turn = "X"
        self.winner = "-"
        self.moves = 0
        self.status = "PLAY"         # PLAY / WIN / DRAW

    def _game_move(self, mark, idx):
        """Return OK / OVER / NOTURN / RANGE / OCCUPIED; board written last."""
        if self.status != "PLAY":
            return "OVER"
        if mark and mark != self.turn:
            return "NOTURN"
        if idx < 0 or idx > 8:
            return "RANGE"
        if self.board[idx] != ".":
            return "OCCUPIED"
        self.board[idx] = self.turn
        self.moves += 1
        for a, b, c in WIN_LINES:
            if self.board[a] == self.board[b] == self.board[c] == self.turn:
                self.status = "WIN"
                self.winner = self.turn
                return "OK"
        if self.moves == 9:
            self.status = "DRAW"
            return "OK"
        self.turn = "O" if self.turn == "X" else "X"
        return "OK"

    def _board_str(self):
        return "".join(self.board)

    def button_press(self):
        """SW0: reset game, go to IDLE, send the unsolicited EVT:RESET."""
        self.reset()
        self._reply("EVT:RESET")

    # -- parser (mirrors parser.c) -----------------------------------------------
    def poll(self):
        """Stalled-frame timeout; the firmware calls this every main-loop pass."""
        if self._clock() - self._last_byte <= PARTIAL_TIMEOUT:
            return
        if self._discarding:
            self._discarding = False
            self._buf.clear()
        elif self._buf:
            self._buf.clear()
            self._reply("NACK:TIMEOUT")

    def feed(self, data):
        self.poll()
        self._last_byte = self._clock()
        for byte in data:
            if byte == 0x0D:                      # '\r' ignored
                continue
            if byte == 0x0A:                      # '\n' ends the frame
                if self._discarding:
                    self._discarding = False
                    self._buf.clear()
                    continue
                self._process_frame()
                self._buf.clear()
                continue
            if self._discarding:
                continue
            if len(self._buf) >= MAX_FRAME:
                self._discarding = True
                self._buf.clear()
                self._reply("NACK:OVERFLOW")      # once per oversized frame
                continue
            self._buf.append(byte)

    def _process_frame(self):
        if not self._buf:
            self._reply("NACK:BADCMD")
            return
        if any(c < 0x20 or c > 0x7E for c in self._buf):
            self._reply("NACK:BADCMD")
            return
        text = self._buf.decode("ascii")
        star = text.find("*")
        if star != -1:
            tail = text[star + 1:]
            hi = _hex_value(tail[0:1])
            lo = _hex_value(tail[1:2]) if hi >= 0 else -1
            if hi < 0 or lo < 0 or len(tail) != 2:
                self._reply("NACK:CHECKSUM")
                return
            x = 0
            for ch in text[:star]:
                x ^= ord(ch)
            if x != (hi << 4 | lo):
                self._reply("NACK:CHECKSUM")
                return
            text = text[:star]
        self._handle(text)

    # -- server (mirrors server.c) -------------------------------------------------
    def _reply(self, payload):
        self._out.append(payload.encode("ascii") + b"\n")

    def _nack(self, reason):
        self._reply("NACK:" + reason)

    def _handle(self, cmd):
        if cmd == "CONNECT":
            if self.state == IDLE:
                self._reply("OK")
            else:
                self._nack("BUSY")
        elif cmd == "NEW":
            if self.state == PLAY:
                self._nack("BUSY")
                return
            self._game_reset()
            self.state = PLAY
            self._reply("OK:BOARD:" + self._board_str())
        elif cmd.startswith("MOVE:"):
            self._handle_move(cmd[5:])
        elif cmd == "STATE":
            if self.state == IDLE:
                self._nack("NOGAME")
                return
            turn = self.turn if self.state == PLAY else "-"
            self._reply("BOARD:%s:%s:%s" % (self._board_str(), turn, self.state))
        elif cmd == "RESIGN":
            if self.state != PLAY:
                self._nack("NOGAME")
                return
            self.state = OVER
            self._reply("OK:GAMEOVER")
        elif cmd == "DISCONNECT":
            self.reset()
            self._reply("OK")
        else:
            self._nack("BADCMD")

    @staticmethod
    def _parse_index(s):
        digits = s[1:] if s.startswith("-") else s
        if not digits or not all(c in "0123456789" for c in digits):
            return None
        return int(s)

    def _handle_move(self, args):
        mark = ""
        # 1. syntax: "<i>" or "<X|O>:<i>"; nothing is touched here
        if len(args) >= 2 and args[1] == ":":
            if args[0] not in "XO":
                self._nack("BADCMD")
                return
            mark = args[0]
            args = args[2:]
        idx = self._parse_index(args)
        if idx is None:
            self._nack("BADCMD")
            return
        # 2. server state
        if self.state != PLAY:
            self._nack("NOGAME")
            return
        # 3. rules
        result = self._game_move(mark, idx)
        if result != "OK":
            self._nack({"NOTURN": "NOTURN", "RANGE": "RANGE",
                        "OCCUPIED": "OCCUPIED", "OVER": "NOGAME"}[result])
            return
        if self.status == "WIN":
            self.state = OVER
            self._reply("WIN:%s:%s" % (self.winner, self._board_str()))
        elif self.status == "DRAW":
            self.state = OVER
            self._reply("DRAW:" + self._board_str())
        else:
            self._reply("OK:BOARD:" + self._board_str())

    # -- transport interface ---------------------------------------------------------
    def transport(self):
        return FakeTransport(self)


class FakeTransport:
    """Duck-types the parts of pyserial.Serial that SerialLink uses."""

    def __init__(self, server):
        self.server = server

    def write(self, data):
        self.server.feed(data)

    def readline(self):
        self.server.poll()
        if self.server._out:
            return self.server._out.pop(0)
        return b""        # pyserial returns b"" when its timeout expires

    @property
    def in_waiting(self):
        """Bytes ready to read, like pyserial's Serial.in_waiting."""
        self.server.poll()
        return sum(len(line) for line in self.server._out)

    def button_press(self):
        self.server.button_press()

    def reset_input_buffer(self):
        self.server._out.clear()

    def close(self):
        pass
