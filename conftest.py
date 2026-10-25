"""pytest setup: runs against the fake server by default, or a real board.

    pytest                              # fake server
    SERIAL_PORT=COM5 pytest             # real STM32 on COM5
    SERIAL_PORT=/dev/ttyACM0 pytest     # real STM32 on Linux
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pc"))

from fake_server import FakeServer  # noqa: E402
from serial_link import LinkError, SerialLink  # noqa: E402


@pytest.fixture
def link():
    port = os.environ.get("SERIAL_PORT")
    if port:
        lk = SerialLink.open_port(port)
        lk.flush_input()
        # Put the board in a known state: DISCONNECT returns the server to IDLE.
        lk.send("DISCONNECT")
        try:
            lk.read()
        except LinkError:
            pass
        lk.flush_input()
    else:
        lk = SerialLink(FakeServer().transport())
    yield lk
    lk.close()


@pytest.fixture
def game(link):
    """A link with CONNECT done and a fresh game started."""
    assert link.request("CONNECT") == "OK"
    assert link.request("NEW") == "OK:BOARD:........."
    return link


def play(link, moves):
    """Send a list of (mark, index) moves and return the list of replies."""
    return [link.request("MOVE:%s:%d" % (mark, idx)) for mark, idx in moves]
