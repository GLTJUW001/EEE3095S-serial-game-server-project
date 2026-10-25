"""Unit tests for the framing helpers and SerialLink (no board needed)."""

import pytest

from fake_server import FakeServer
from serial_link import LinkTimeout, SerialLink, checksum, decode_reply, frame


def test_checksum_vectors():
    assert checksum("CONNECT") == 0x5E
    assert checksum("MOVE:X:4") == 0x7D


def test_frame_with_checksum():
    assert frame("CONNECT") == b"CONNECT*5E\n"
    assert frame("MOVE:X:4") == b"MOVE:X:4*7D\n"


def test_frame_without_checksum():
    assert frame("CONNECT", with_checksum=False) == b"CONNECT\n"


def test_decode_reply_strips_newline():
    assert decode_reply(b"OK:BOARD:.........\r\n") == "OK:BOARD:........."


def test_events_are_queued_not_returned_as_replies():
    server = FakeServer()
    link = SerialLink(server.transport())
    link.request("CONNECT")
    server.button_press()                     # EVT:RESET now waiting in the queue
    assert link.request("CONNECT") == "OK"    # reply is OK, not the event
    assert link.take_events() == ["EVT:RESET"]
    assert link.take_events() == []


def test_read_times_out_when_nothing_arrives():
    link = SerialLink(FakeServer().transport())
    with pytest.raises(LinkTimeout):
        link.read()
