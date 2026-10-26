"""Protocol tests for the Serial Game Server (Protocol_Spec_v1).

One suite for all three targets (see conftest.py): the Python fake server,
the firmware C logic on the PC, or the real board. No human interaction
needed, except that the button test is skipped on a real board.
"""

import time

import pytest

from conftest import play
from serial_link import frame

EMPTY = "........."


def state(link):
    """STATE reply: BOARD:<9>:<turn>:<status>."""
    return link.request("STATE")


# --- session and new game ---------------------------------------------------
def test_connect_returns_ok(link):
    assert link.request("CONNECT") == "OK"


def test_connect_again_while_idle_is_ok(link):
    assert link.request("CONNECT") == "OK"
    assert link.request("CONNECT") == "OK"


def test_new_returns_empty_board(link):
    link.request("CONNECT")
    assert link.request("NEW") == "OK:BOARD:" + EMPTY


def test_connect_during_game_is_busy(game):
    assert game.request("CONNECT") == "NACK:BUSY"
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"


def test_new_during_game_is_busy(game):
    game.request("MOVE:X:0")
    assert game.request("NEW") == "NACK:BUSY"
    assert state(game) == "BOARD:X........:O:PLAY"


# --- legal moves ------------------------------------------------------------
def test_legal_move_changes_board_exactly(game):
    assert game.request("MOVE:X:4") == "OK:BOARD:....X...."
    assert state(game) == "BOARD:....X....:O:PLAY"
    assert game.request("MOVE:O:0") == "OK:BOARD:O...X...."
    assert state(game) == "BOARD:O...X....:X:PLAY"


def test_bare_move_uses_current_turn(game):
    assert game.request("MOVE:4") == "OK:BOARD:....X...."
    assert game.request("MOVE:0") == "OK:BOARD:O...X...."


# --- rejections leave state unchanged ---------------------------------------
def test_occupied_cell_rejected_and_board_unchanged(game):
    game.request("MOVE:X:4")
    assert game.request("MOVE:O:4") == "NACK:OCCUPIED"
    assert state(game) == "BOARD:....X....:O:PLAY"
    # It is still O's turn, so a legal O move works afterwards.
    assert game.request("MOVE:O:0") == "OK:BOARD:O...X...."


@pytest.mark.parametrize("index", [9, 10, 99, -1])
def test_out_of_range_rejected(game, index):
    assert game.request("MOVE:X:%d" % index) == "NACK:RANGE"
    assert game.request("MOVE:%d" % index) == "NACK:RANGE"
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"


def test_out_of_turn_rejected(game):
    assert game.request("MOVE:O:0") == "NACK:NOTURN"      # X goes first
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"
    game.request("MOVE:X:0")
    assert game.request("MOVE:X:1") == "NACK:NOTURN"      # same player twice
    assert state(game) == "BOARD:X........:O:PLAY"


def test_turn_is_checked_before_range(game):
    # Spec section 4: mark/turn (step 4) comes before index range (step 5).
    assert game.request("MOVE:O:9") == "NACK:NOTURN"


def test_move_before_any_game_is_nogame(link):
    link.request("CONNECT")
    assert link.request("MOVE:X:0") == "NACK:NOGAME"
    assert link.request("STATE") == "NACK:NOGAME"


# --- terminal results -------------------------------------------------------
def test_x_wins_top_row(game):
    replies = play(game, [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)])
    assert replies[-1] == "WIN:X:XXXOO...."
    assert state(game) == "BOARD:XXXOO....:-:OVER"


def test_o_wins_middle_row(game):
    replies = play(game, [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 8), ("O", 5)])
    assert replies[-1] == "WIN:O:XX.OOO..X"


def test_x_wins_diagonal(game):
    replies = play(game, [("X", 2), ("O", 0), ("X", 4), ("O", 1), ("X", 6)])
    assert replies[-1] == "WIN:X:OOX.X.X.."


def test_draw(game):
    replies = play(game, [("X", 0), ("O", 1), ("X", 2), ("O", 4), ("X", 3),
                          ("O", 5), ("X", 7), ("O", 6), ("X", 8)])
    assert all(r.startswith("OK:BOARD:") for r in replies[:-1])
    assert replies[-1] == "DRAW:XOXXOOOXX"
    assert state(game) == "BOARD:XOXXOOOXX:-:OVER"


def test_move_after_game_over_rejected(game):
    play(game, [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)])
    assert game.request("MOVE:O:8") == "NACK:NOGAME"
    assert state(game) == "BOARD:XXXOO....:-:OVER"        # board frozen


def test_new_after_game_over_starts_fresh_game(game):
    play(game, [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)])
    assert game.request("NEW") == "OK:BOARD:" + EMPTY
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"


def test_resign_ends_game(game):
    game.request("MOVE:X:4")
    assert game.request("RESIGN") == "OK:GAMEOVER"
    assert state(game) == "BOARD:....X....:-:OVER"
    assert game.request("MOVE:O:0") == "NACK:NOGAME"
    assert game.request("RESIGN") == "NACK:NOGAME"


def test_disconnect_from_any_state(game):
    assert game.request("DISCONNECT") == "OK"
    assert game.request("MOVE:X:0") == "NACK:NOGAME"
    assert game.request("DISCONNECT") == "OK"             # also fine when already IDLE


# --- protocol robustness ----------------------------------------------------
def test_unknown_command_is_badcmd(link):
    assert link.request("FOO") == "NACK:BADCMD"


@pytest.mark.parametrize("cmd", ["MOVE:Z:4", "MOVE:X:abc", "MOVE:X:", "MOVE:",
                                 "MOVE", "MOVE:4:5", "MOVE:abc", "CONNECT:1",
                                 "connect", "NEW:1"])
def test_malformed_commands_are_badcmd(game, cmd):
    assert game.request(cmd) == "NACK:BADCMD"
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"


def test_bad_checksum_rejected_and_state_unchanged(game):
    game.send_raw(b"MOVE:X:4*00\n")
    assert game.read() == "NACK:CHECKSUM"
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"


@pytest.mark.parametrize("line", [b"MOVE:X:4*Z1\n", b"MOVE:X:4*7\n", b"MOVE:X:4*7DD\n",
                                  b"MOVE:X:4*\n"])
def test_malformed_checksum_suffix_rejected(game, line):
    game.send_raw(line)
    assert game.read() == "NACK:CHECKSUM"
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"


def test_checksum_is_optional(game):
    assert game.request("MOVE:X:4", with_checksum=False) == "OK:BOARD:....X...."
    assert game.request("MOVE:O:0") == "OK:BOARD:O...X...."          # with checksum


def test_frame_of_exactly_32_bytes_is_not_an_overflow(link):
    link.send_raw(b"A" * 32 + b"\n")
    assert link.read() == "NACK:BADCMD"                   # at the limit: parsed normally, just not a command


def test_oversized_frame_gets_one_overflow_and_recovers(game):
    game.send_raw(b"A" * 100 + b"\n")
    assert game.read() == "NACK:OVERFLOW"
    # Exactly one reply: the next request must get its own reply, not a leftover.
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"


def test_frame_of_33_bytes_is_an_overflow(link):
    link.send_raw(b"A" * 33 + b"\n")
    assert link.read() == "NACK:OVERFLOW"


def test_garbage_bytes_are_badcmd_and_server_recovers(game):
    game.send_raw(b"\xff\xfe\x00\x80\x01\x02\n")
    assert game.read() == "NACK:BADCMD"
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"


def test_empty_line_is_badcmd(link):
    link.send_raw(b"\n")
    assert link.read() == "NACK:BADCMD"


def test_partial_frame_times_out_with_nack(game):
    game.send_raw(b"MOVE:X")          # incomplete, no terminator
    time.sleep(0.7)                   # longer than the 500 ms timeout
    assert game.read() == "NACK:TIMEOUT"
    assert state(game) == "BOARD:" + EMPTY + ":X:PLAY"    # stale bytes did not leak in


def test_frame_split_across_writes_still_works(game):
    data = frame("MOVE:X:4")
    game.send_raw(data[:4])
    game.send_raw(data[4:])
    assert game.read() == "OK:BOARD:....X...."


def test_crlf_terminator_tolerated(game):
    game.send_raw(frame("STATE")[:-1] + b"\r\n")
    assert game.read() == "BOARD:" + EMPTY + ":X:PLAY"


# --- button -----------------------------------------------------------------
def test_button_reset_sends_event_and_returns_to_idle(game):
    if not hasattr(game.transport, "button_press"):
        pytest.skip("needs a simulated button; on the real board press SW0 by hand")
    game.request("MOVE:X:4")
    game.transport.button_press()
    time.sleep(0.05)
    assert game.request("STATE") == "NACK:NOGAME"         # server is back in IDLE
    assert game.take_events() == ["EVT:RESET"]            # event queued, not mistaken for a reply
    assert game.request("CONNECT") == "OK"


def test_ai_mode_makes_a_valid_computer_move(link):
    assert link.request("CONNECT") == "OK"
    assert link.request("NEW:AI") == "OK:BOARD:" + EMPTY

    reply = link.request("MOVE:X:4")
    assert reply.startswith("OK:BOARD:")
    board_and_suffix = reply[len("OK:BOARD:"):]
    board, ai_suffix = board_and_suffix.split(":AI:")
    ai_cell = int(ai_suffix)
    assert len(board) == 9
    assert board[4] == "X"
    assert board[ai_cell] == "O"
    assert board.count("X") == 1 and board.count("O") == 1
    assert link.request("HIST") == "HIST:2:X4O%d" % ai_cell


def test_history_command_returns_successful_moves_only(game):
    assert game.request("MOVE:X:4") == "OK:BOARD:....X...."
    assert game.request("MOVE:O:4") == "NACK:OCCUPIED"
    assert game.request("MOVE:O:0") == "OK:BOARD:O...X...."
    assert game.request("HIST") == "HIST:2:X4O0"
