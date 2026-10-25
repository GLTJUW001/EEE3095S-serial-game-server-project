"""Unit tests for the checksum/framing helpers (no server needed)."""

import pytest

from serial_link import ChecksumError, checksum, frame, unframe


def test_checksum_vectors_from_protocol():
    assert checksum("CONNECT") == 0x5E
    assert checksum("MOVE:X:4") == 0x7D


def test_frame_format():
    assert frame("CONNECT") == b"CONNECT*5E\n"
    assert frame("MOVE:X:4") == b"MOVE:X:4*7D\n"


def test_unframe_roundtrip():
    assert unframe(frame("OK:BOARD:........."))== "OK:BOARD:........."


@pytest.mark.parametrize("line", [b"CONNECT\n", b"CONNECT*5F\n", b"CONNECT*5\n",
                                  b"CONNECT*ZZ\n", b"\xff\xfe\n"])
def test_unframe_rejects_bad_frames(line):
    with pytest.raises(ChecksumError):
        unframe(line)
