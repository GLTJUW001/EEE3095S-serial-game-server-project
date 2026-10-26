"""Tests for the GUI's controller (pc/game_client.py).

Runs on the same three targets as the protocol tests: fake server by default,
FIRMWARE_HOST=... for the real firmware C logic, SERIAL_PORT=... for the board.
The Tk window itself is not tested here; it only draws what this object says.
"""

import pytest

from game_client import DISCONNECTED, IDLE, OVER, PLAYING, GameClient, parse_reply
from serial_link import SerialLink

EMPTY = "........."


@pytest.fixture
def client(link):
    c = GameClient(link)
    assert c.connect() is True
    return c


@pytest.fixture
def started(client):
    client.new_game()
    return client


def play_cells(c, cells):
    for cell in cells:
        c.move(cell)


# --- scripted transport for link-fault cases --------------------------------------
class ScriptedTransport:
    """Returns canned reply lines; can also simulate a dead port or silence."""

    def __init__(self, replies=(), write_error=None):
        self.replies = list(replies)
        self.write_error = write_error
        self.sent = []

    def write(self, data):
        if self.write_error:
            raise self.write_error
        self.sent.append(data)

    def readline(self):
        return self.replies.pop(0) if self.replies else b""

    def reset_input_buffer(self):
        pass

    def close(self):
        pass


# --- reply parsing -----------------------------------------------------------------
@pytest.mark.parametrize("text,kind", [
    ("OK", "ok"), ("OK:BOARD:.........", "board_ok"), ("WIN:X:XXXOO....", "win"),
    ("DRAW:XOXXOOOXX", "draw"), ("BOARD:....X....:O:PLAY", "state"),
    ("BOARD:XXXOO....:-:OVER", "state"), ("OK:GAMEOVER", "gameover"),
    ("NACK:OCCUPIED", "nack"),
])
def test_parse_valid_replies(text, kind):
    assert parse_reply(text)[0] == kind


@pytest.mark.parametrize("text", ["", "OK:BOARD:XXX", "OK:BOARD:.......Z.", "WIN:Z:.........",
                                  "hello", "BOARD:.........:X:LOL", "NACK:bad"])
def test_parse_invalid_replies(text):
    assert parse_reply(text)[0] == "invalid"


# --- normal play ---------------------------------------------------------------------
def test_connect_and_new_game(client):
    assert client.mode == IDLE
    client.new_game()
    assert client.mode == PLAYING and client.board == EMPTY and client.turn == "X"
    assert client.board_enabled


def test_client_sends_the_right_mark_and_tracks_turn(started):
    started.move(4)
    assert started.board == "....X...." and started.turn == "O"
    started.move(0)
    assert started.board == "O...X...." and started.turn == "X"
    assert started.headline == "X to move"


def test_occupied_cell_gives_specific_message_and_board_unchanged(started):
    started.move(4)
    started.move(4)
    assert started.level == "error" and "already taken" in started.message
    assert started.board == "....X...." and started.turn == "O" and started.mode == PLAYING


def test_out_of_range_gives_specific_message(started):
    started.move(9)
    assert "out of range" in started.message
    assert started.board == EMPTY and started.mode == PLAYING


def test_win_ends_game_and_disables_board(started):
    play_cells(started, [0, 3, 1, 4, 2])          # X top row
    assert started.mode == OVER and started.result == "WIN" and started.winner == "X"
    assert started.board == "XXXOO...." and started.win_line == (0, 1, 2)
    assert started.headline == "X wins!" and not started.board_enabled


def test_o_win_is_reported_for_o(started):
    play_cells(started, [0, 3, 1, 4, 8, 5])
    assert started.result == "WIN" and started.winner == "O" and started.win_line == (3, 4, 5)


def test_draw(started):
    play_cells(started, [0, 1, 2, 4, 3, 5, 7, 6, 8])
    assert started.mode == OVER and started.result == "DRAW"
    assert started.board == "XOXXOOOXX" and started.headline == "It's a draw"


def test_move_after_game_over_is_reported_not_crashed(started):
    play_cells(started, [0, 3, 1, 4, 2])
    started.move(8)
    assert started.level == "error" and "over" in started.message.lower()
    assert started.board == "XXXOO...." and started.mode == OVER


def test_new_game_while_playing_is_refused_by_server(started):
    started.move(0)
    started.new_game()
    assert "already in progress" in started.message
    assert started.mode == PLAYING and started.board == "X........"


def test_new_game_after_game_over_resets_everything(started):
    play_cells(started, [0, 3, 1, 4, 2])
    started.new_game()
    assert started.mode == PLAYING and started.board == EMPTY
    assert started.result is None and started.win_line == ()


def test_resign(started):
    started.move(4)
    started.resign()
    assert started.mode == OVER and started.result == "RESIGNED"
    assert started.board == "....X...." and not started.board_enabled
    started.resign()
    assert started.level == "error" and "no game" in started.message.lower()


def test_resign_with_no_game_is_reported(client):
    client.resign()
    assert client.level == "error" and "no game" in client.message.lower()
    assert client.mode == IDLE


def test_disconnect_returns_server_to_idle(link, started):
    started.move(4)
    real_close = link.close
    link.close = lambda: None                        # keep the port open for the check below
    started.disconnect()
    assert started.mode == DISCONNECTED and started.link is None
    fresh = GameClient(link)                         # same board, new client
    assert fresh.connect() is True and fresh.mode == IDLE   # IDLE, not "resumed": DISCONNECT reset it
    link.close = real_close


# --- recovery ----------------------------------------------------------------------------
def test_reconnect_resumes_game_in_progress(link, started):
    started.move(4)                                   # X plays centre, then the "GUI crashes"
    newer = GameClient(link)                          # fresh GUI, same board
    assert newer.connect() is True
    assert newer.mode == PLAYING and newer.board == "....X...." and newer.turn == "O"
    assert "resumed" in newer.message
    newer.move(0)                                     # and play carries on correctly
    assert newer.board == "O...X...."


def test_button_reset_event_returns_client_to_idle(started):
    if not hasattr(started.link.transport, "button_press"):
        pytest.skip("needs a simulated button; on the real board press SW0 by hand")
    started.move(4)
    started.link.transport.button_press()
    import time
    time.sleep(0.05)
    assert started.poll() is True
    assert started.mode == IDLE and started.board == EMPTY
    assert "reset" in started.message and not started.board_enabled
    started.new_game()                                # and a fresh game works
    assert started.mode == PLAYING


def test_move_after_silent_reset_resyncs(started):
    if not hasattr(started.link.transport, "button_press"):
        pytest.skip("needs a simulated button")
    started.move(4)
    started.link.transport.button_press()
    import time
    time.sleep(0.05)
    started.move(0)                                   # GUI has not polled yet; server is IDLE
    assert started.mode == IDLE
    assert started.level == "error" and started.board == EMPTY


# --- link faults (scripted, never touch the board) ----------------------------------------
def test_timeout_is_reported_and_changes_nothing():
    c = GameClient(SerialLink(ScriptedTransport(replies=[b"OK\n"])))
    assert c.connect() is True
    c.new_game()                                      # no reply scripted: silence
    assert c.mode == IDLE and c.board == EMPTY
    assert c.level == "error" and "no reply" in c.message.lower()


def test_malformed_server_reply_never_changes_the_board():
    t = ScriptedTransport(replies=[b"OK\n", b"OK:BOARD:.........\n", b"OK:BOARD:XXXXXXXXXXXX\n"])
    c = GameClient(SerialLink(t))
    c.connect()
    c.new_game()
    c.move(4)
    assert c.board == EMPTY and c.mode == PLAYING
    assert "unexpected reply" in c.message.lower()


def test_unknown_nack_is_shown_not_crashed():
    t = ScriptedTransport(replies=[b"OK\n", b"NACK:SOMETHINGNEW\n"])
    c = GameClient(SerialLink(t))
    c.connect()
    c.new_game()
    assert "NACK:SOMETHINGNEW" in c.message and c.level == "error"


def test_lost_port_drops_to_disconnected_without_raising():
    t = ScriptedTransport(replies=[b"OK\n"])
    c = GameClient(SerialLink(t))
    c.connect()
    t.write_error = OSError("device disconnected")
    c.new_game()
    assert c.mode == DISCONNECTED and c.link is None
    assert "connection lost" in c.message.lower()


def test_actions_when_not_connected_are_safe():
    c = GameClient()
    c.new_game()
    c.move(4)
    c.resign()
    c.disconnect()
    assert c.mode == DISCONNECTED and c.level in ("error", "info")


def test_connect_fails_cleanly_on_silence():
    c = GameClient(SerialLink(ScriptedTransport()))
    assert c.connect() is False
    assert c.mode == DISCONNECTED and "no reply" in c.message.lower()
