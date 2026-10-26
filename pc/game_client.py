"""Game client logic for the Tic-Tac-Toe GUI (no GUI code in here).

The STM32 is the single source of truth. This class is the "thin client":

  * it never decides whether a move is legal, it only forwards the request;
  * the board it shows is replaced ONLY by a valid server reply
    (OK:BOARD / WIN / DRAW / BOARD), never by what the user clicked;
  * every server rejection is turned into a specific message;
  * anything odd (timeout, malformed reply, button reset, lost port) is
    handled without raising, and the board is never changed by a bad reply.

gui.py draws whatever this object says; tests drive it directly.
"""

import re

from serial_link import LinkError, LinkTimeout

DISCONNECTED, IDLE, PLAYING, OVER = "DISCONNECTED", "IDLE", "PLAYING", "OVER"
EMPTY_BOARD = "." * 9

NACK_TEXT = {
    "OCCUPIED": "That cell is already taken.",
    "NOTURN": "It is not that player's turn.",
    "RANGE": "That cell number is out of range (0-8).",
    "NOGAME": "There is no game in progress.",
    "BUSY": "The server is busy: a game is already in progress.",
    "BADCMD": "The server did not understand the command.",
    "CHECKSUM": "The command reached the server with a bad checksum.",
    "OVERFLOW": "The command was too long for the server.",
    "TIMEOUT": "The server timed out waiting for the rest of a command.",
}

_B = "([.XO]{9})"
_PATTERNS = [
    ("ok", re.compile(r"^OK$")),
    ("board_ok", re.compile(r"^OK:BOARD:" + _B + "$")),
    ("win", re.compile(r"^WIN:([XO]):" + _B + "$")),
    ("draw", re.compile(r"^DRAW:" + _B + "$")),
    ("state", re.compile(r"^BOARD:" + _B + r":([XO-]):(PLAY|OVER)$")),
    ("gameover", re.compile(r"^OK:GAMEOVER$")),
    ("nack", re.compile(r"^NACK:([A-Z]+)$")),
]

# Cosmetic only: used to highlight the line the SERVER already declared won.
_LINES = ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8),
          (0, 4, 8), (2, 4, 6))


def parse_reply(text):
    """Classify a server reply. Returns (kind, groups); kind 'invalid' if unknown."""
    for kind, pattern in _PATTERNS:
        m = pattern.match(text)
        if m:
            return kind, m.groups()
    return "invalid", ()


def nack_message(reason):
    return NACK_TEXT.get(reason, "The server rejected the request (NACK:%s)." % reason)


def _winning_line(board, mark):
    for line in _LINES:
        if all(board[i] == mark for i in line):
            return line
    return ()


class GameClient:
    def __init__(self, link=None, log_cb=None):
        self.link = link
        self.log_cb = log_cb
        self.log = []                 # (direction, text) history
        self.mode = DISCONNECTED
        self.board = EMPTY_BOARD
        self.turn = None              # 'X' / 'O' while PLAYING, else None
        self.result = None            # None, 'WIN', 'DRAW', 'RESIGNED', 'OVER'
        self.winner = None
        self.win_line = ()
        self.message = "Not connected."
        self.level = "info"           # info / ok / warn / error

    # -- presentation helpers ----------------------------------------------------
    @property
    def headline(self):
        if self.mode == DISCONNECTED:
            return "Not connected"
        if self.mode == IDLE:
            return "Connected: press New Game"
        if self.mode == PLAYING:
            return "%s to move" % self.turn
        if self.result == "WIN":
            return "%s wins!" % self.winner
        if self.result == "DRAW":
            return "It's a draw"
        return "Game over"

    @property
    def board_enabled(self):
        """True while the server has a game in progress (grid clickable)."""
        return self.mode == PLAYING

    def _say(self, text, level="info"):
        self.message, self.level = text, level

    def notify(self, text, level="info"):
        """Let the GUI show its own message (e.g. 'could not open port')."""
        self._say(text, level)

    def _log(self, direction, text):
        self.log.append((direction, text))
        if self.log_cb:
            self.log_cb(direction, text)

    def _clear_game(self):
        self.board, self.turn = EMPTY_BOARD, None
        self.result = self.winner = None
        self.win_line = ()

    # -- state updates (only ever called with a validated server reply) ---------
    def _apply_board(self, board, turn=None):
        self.board = board
        if turn is None:
            turn = "X" if board.count("X") == board.count("O") else "O"
        self.turn = turn

    def _finish(self, board, result, winner=None):
        self.board, self.mode, self.turn = board, OVER, None
        self.result, self.winner = result, winner
        self.win_line = _winning_line(board, winner) if winner else ()

    def _lost(self, reason):
        """The port went away: drop to DISCONNECTED without raising."""
        try:
            if self.link:
                self.link.close()
        except Exception:
            pass
        self.link = None
        self.mode = DISCONNECTED
        self._clear_game()
        self._say("Connection lost: %s" % reason, "error")

    # -- one request/response -----------------------------------------------------
    def _ask(self, payload):
        """Send a request, log it, return the reply text or None on a link problem."""
        if self.link is None:
            self._say("Not connected.", "error")
            return None
        self._log("->", payload)
        try:
            reply = self.link.request(payload)
        except LinkTimeout:
            self._log("!!", "no reply (timeout)")
            self._say("No reply from the board (timed out). Nothing was changed; "
                      "check the cable and try again.", "error")
            self._drain_events()
            return None
        except (LinkError, OSError) as exc:
            self._lost(str(exc) or exc.__class__.__name__)
            return None
        self._log("<-", reply)
        self._drain_events()
        return reply

    def _drain_events(self):
        for event in self.link.take_events() if self.link else []:
            self._on_event(event)

    def _on_event(self, event):
        self._log("<-", event)
        if event == "EVT:RESET" and self.mode != DISCONNECTED:
            self.mode = IDLE
            self._clear_game()
            self._say("The board was reset with its button. Press New Game to start again.",
                      "warn")

    def poll(self):
        """Call from a timer: pick up unsolicited lines (button press). True if changed."""
        if self.link is None:
            return False
        try:
            events = self.link.poll_events()
        except (LinkError, OSError) as exc:
            self._lost(str(exc) or exc.__class__.__name__)
            return True
        for event in events:
            self._on_event(event)
        return bool(events)

    def _resync(self):
        """Ask the server where things really are (STATE) and adopt its answer."""
        reply = self._ask("STATE")
        if reply is None:
            return
        kind, g = parse_reply(reply)
        if kind == "state":
            board, turn, status = g
            if status == "PLAY":
                self.mode = PLAYING
                self.result = self.winner = None
                self.win_line = ()
                self._apply_board(board, turn)
            else:
                winner = next((m for m in "XO" if _winning_line(board, m)), None)
                result = "WIN" if winner else ("DRAW" if "." not in board else "OVER")
                self._finish(board, result, winner)
        elif kind == "nack" and g[0] == "NOGAME":
            self.mode = IDLE
            self._clear_game()
        else:
            self._say("Unexpected reply to STATE: %r" % reply, "error")

    # -- user actions -------------------------------------------------------------
    def connect(self, link=None):
        """CONNECT to the server. Resumes a game already running on the board."""
        if link is not None:
            self.link = link
        reply = self._ask("CONNECT")
        if reply is None:
            return False
        kind, g = parse_reply(reply)
        if kind == "ok":
            self.mode = IDLE
            self._clear_game()
            self._say("Connected. Press New Game to start.", "ok")
            return True
        if kind == "nack" and g[0] == "BUSY":
            self.mode = IDLE            # provisional; STATE below sets the real mode
            self._say("", "info")
            self._resync()
            if self.level == "error":   # could not learn the real state: do not pretend
                self.mode = DISCONNECTED
                return False
            if self.mode == PLAYING:
                self._say("Connected: resumed the game already in progress. "
                          "%s to move." % self.turn, "warn")
            elif self.mode == OVER:
                self._say("Connected: the previous game is over. Press New Game.", "warn")
            else:
                self._say("Connected. Press New Game to start.", "ok")
            return self.mode != DISCONNECTED
        if kind == "nack":
            self._say(nack_message(g[0]), "error")
        else:
            self._say("Unexpected reply to CONNECT: %r" % reply, "error")
        return False

    def new_game(self):
        reply = self._ask("NEW")
        if reply is None:
            return
        kind, g = parse_reply(reply)
        if kind == "board_ok":
            self.mode = PLAYING
            self.result = self.winner = None
            self.win_line = ()
            self._apply_board(g[0], "X")
            self._say("New game. %s to move." % self.turn, "ok")
        elif kind == "nack":
            if g[0] == "BUSY":
                self._resync()          # our picture may be stale; show the truth
            self._say(nack_message(g[0]) + (" Resign it first." if g[0] == "BUSY" else ""),
                      "error")
        else:
            self._say("Unexpected reply to NEW: %r" % reply, "error")

    def move(self, index):
        """Forward a move for the player whose turn the SERVER last told us it is."""
        mark = self.turn or "X"
        reply = self._ask("MOVE:%s:%s" % (mark, index))
        if reply is None:
            return
        kind, g = parse_reply(reply)
        if kind == "board_ok":
            self._apply_board(g[0])
            self._say("%s to move." % self.turn)
        elif kind == "win":
            self._finish(g[1], "WIN", g[0])
            self._say("%s wins! Press New Game to play again." % g[0], "ok")
        elif kind == "draw":
            self._finish(g[0], "DRAW")
            self._say("It's a draw. Press New Game to play again.", "ok")
        elif kind == "nack":
            reason = g[0]
            if reason in ("NOGAME", "NOTURN"):
                self._resync()          # we were out of step (reset / reconnect)
            text = nack_message(reason)
            if reason == "NOGAME":
                text = ("The game is over. Press New Game." if self.mode == OVER else
                        "No game in progress. The board may have been reset: press New Game.")
            self._say(text, "error")
        else:
            self._say("Unexpected reply to MOVE: %r (board left unchanged)." % reply, "error")

    def resign(self):
        reply = self._ask("RESIGN")
        if reply is None:
            return
        kind, g = parse_reply(reply)
        if kind == "gameover":
            self._finish(self.board, "RESIGNED")
            self._say("Game resigned. Press New Game to play again.", "warn")
        elif kind == "nack":
            if g[0] == "NOGAME":
                self._resync()
            self._say(nack_message(g[0]), "error")
        else:
            self._say("Unexpected reply to RESIGN: %r" % reply, "error")

    def disconnect(self):
        """Tell the server we are leaving (best effort), then close the port."""
        if self.link is not None and self.mode != DISCONNECTED:
            self._ask("DISCONNECT")
        try:
            if self.link:
                self.link.close()
        except Exception:
            pass
        self.link = None
        self.mode = DISCONNECTED
        self._clear_game()
        self._say("Disconnected.", "info")
