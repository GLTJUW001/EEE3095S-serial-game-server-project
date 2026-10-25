"""Protocol tests for the Serial Game Server.

Runs against the Python fake server by default, or the real STM32 when
SERIAL_PORT is set (see conftest.py). No human interaction needed.
"""

import time

import pytest

from conftest import play
from serial_link import frame

EMPTY = "........."


# --- session and new game ---------------------------------------------------
def test_connect_returns_ok(link):
    assert link.request("CONNECT") == "OK"


def test_new_returns_empty_board(link):
    link.request("CONNECT")
    assert link.request("NEW") == "OK:BOARD:" + EMPTY


# --- legal moves ------------------------------------------------------------
def test_legal_move_changes_board_exactly(game):
    assert game.request("MOVE:X:4") == "OK:BOARD:....X...."
    assert game.request("STATE") == "BOARD:....X...."
    assert game.request("MOVE:O:0") == "OK:BOARD:O...X...."


# --- rejections leave state unchanged ---------------------------------------
def test_occupied_cell_rejected_and_board_unchanged(game):
    game.request("MOVE:X:4")
    assert game.request("MOVE:O:4") == "NACK:OCCUPIED"
    assert game.request("STATE") == "BOARD:....X...."
    # It is still O's turn, so a legal O move works afterwards.
    assert game.request("MOVE:O:0") == "OK:BOARD:O...X...."


@pytest.mark.parametrize("index", [9, 10, 99, -1])
def test_out_of_range_rejected(game, index):
    assert game.request("MOVE:X:%d" % index) == "NACK:RANGE"
    assert game.request("STATE") == "BOARD:" + EMPTY


def test_out_of_turn_rejected(game):
    assert game.request("MOVE:O:0") == "NACK:NOTURN"      # X goes first
    assert game.request("STATE") == "BOARD:" + EMPTY
    game.request("MOVE:X:0")
    assert game.request("MOVE:X:1") == "NACK:NOTURN"      # same player twice
    assert game.request("STATE") == "BOARD:X........"


def test_move_before_any_game_is_nogame(link):
    link.request("CONNECT")
    assert link.request("MOVE:X:0") == "NACK:NOGAME"
    assert link.request("STATE") == "NACK:NOGAME"


def test_new_during_game_rejected(game):
    game.request("MOVE:X:0")
    assert game.request("NEW") == "NACK:INGAME"
    assert game.request("STATE") == "BOARD:X........"


# --- terminal results -------------------------------------------------------
def test_x_wins_top_row(game):
    replies = play(game, [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)])
    assert replies[-1] == "WIN:X:XXXOO...."


def test_o_wins_middle_row(game):
    replies = play(game, [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 8), ("O", 5)])
    assert replies[-1] == "WIN:O:XX.OOO..X"


def test_draw(game):
    replies = play(game, [("X", 0), ("O", 1), ("X", 2), ("O", 4), ("X", 3),
                          ("O", 5), ("X", 7), ("O", 6), ("X", 8)])
    assert all(r.startswith("OK:BOARD:") for r in replies[:-1])
    assert replies[-1] == "DRAW:XOXXOOOXX"


def test_move_after_game_over_rejected(game):
    play(game, [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)])
    assert game.request("MOVE:O:8") == "NACK:NOGAME"
    assert game.request("STATE") == "BOARD:XXXOO...."     # board frozen


def test_new_after_game_over_starts_fresh_game(game):
    play(game, [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)])
    assert game.request("NEW") == "OK:BOARD:" + EMPTY


def test_resign_ends_game(game):
    game.request("MOVE:X:4")
    assert game.request("RESIGN") == "OK:GAMEOVER"
    assert game.request("MOVE:O:0") == "NACK:NOGAME"
    assert game.request("RESIGN") == "NACK:NOGAME"


def test_disconnect(game):
    assert game.request("DISCONNECT") == "OK"
    assert game.request("MOVE:X:0") == "NACK:NOGAME"


# --- protocol robustness ----------------------------------------------------
def test_unknown_command_is_badcmd(link):
    assert link.request("FOO") == "NACK:BADCMD"


@pytest.mark.parametrize("cmd", ["MOVE:4", "MOVE:Z:4", "MOVE:X:abc", "MOVE:X:",
                                 "MOVE", "CONNECT:1", "connect"])
def test_malformed_commands_are_badcmd(game, cmd):
    assert game.request(cmd) == "NACK:BADCMD"
    assert game.request("STATE") == "BOARD:" + EMPTY


def test_bad_checksum_rejected_and_state_unchanged(game):
    game.send_raw(b"MOVE:X:4*00\n")
    assert game.read() == "NACK:CHECKSUM"
    assert game.request("STATE") == "BOARD:" + EMPTY


def test_missing_checksum_rejected(game):
    game.send_raw(b"MOVE:X:4\n")
    assert game.read() == "NACK:CHECKSUM"
    assert game.request("STATE") == "BOARD:" + EMPTY


def test_oversized_frame_rejected_and_recovers(game):
    game.send_raw(b"A" * 100 + b"\n")
    assert game.read() == "NACK:BADCMD"
    assert game.request("STATE") == "BOARD:" + EMPTY


def test_garbage_bytes_rejected_and_recovers(game):
    game.send_raw(b"\xff\xfe\x00\x80\x01\x02\n")
    assert game.read().startswith("NACK:")
    assert game.request("STATE") == "BOARD:" + EMPTY


def test_partial_frame_dropped_after_timeout(game):
    game.send_raw(b"MOVE:X")          # incomplete, no terminator
    time.sleep(0.7)                   # longer than the 500 ms timeout
    assert game.request("STATE") == "BOARD:" + EMPTY   # stale bytes did not leak in


def test_frame_split_across_writes_still_works(game):
    data = frame("MOVE:X:4")
    game.send_raw(data[:4])
    game.send_raw(data[4:])
    assert game.read() == "OK:BOARD:....X...."


def test_crlf_terminator_tolerated(game):
    game.send_raw(frame("STATE")[:-1] + b"\r\n")
    assert game.read() == "BOARD:" + EMPTY
