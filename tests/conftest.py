"""pytest setup. One suite, three targets:

    pytest                                   # Python fake server (default)
    FIRMWARE_HOST=hostsim/fw_host pytest     # real firmware C logic on the PC
    SERIAL_PORT=COM5 pytest                  # real STM32 (use /dev/ttyACM0 on Linux)
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pc"))
sys.path.insert(0, os.path.dirname(__file__))

from fake_server import FakeServer  # noqa: E402
from serial_link import LinkError, SerialLink  # noqa: E402


@pytest.fixture
def link():
    port = os.environ.get("SERIAL_PORT")
    host_fw = os.environ.get("FIRMWARE_HOST")
    if host_fw:
        from firmware_host import HostFirmwareTransport
        lk = SerialLink(HostFirmwareTransport(host_fw))
    elif port:
        lk = SerialLink.open_port(port)
        lk.flush_input()
        # Known state for every test: DISCONNECT returns the server to IDLE.
        lk.send("DISCONNECT")
        try:
            lk.read()
        except LinkError:
            pass
        lk.flush_input()
        lk.take_events()
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
