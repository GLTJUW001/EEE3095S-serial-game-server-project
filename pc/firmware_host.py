"""Transport that talks to the firmware host simulator (hostsim/fw_host).

Duck-types the parts of pyserial.Serial that SerialLink uses, so the existing
tests and GUI run unchanged against the real firmware logic:

    FIRMWARE_HOST=hostsim/fw_host pytest
"""

import os
import select
import signal
import subprocess
import time


class HostFirmwareTransport:
    def __init__(self, binary, timeout=1.0):
        self.timeout = timeout
        self._buf = b""
        self.proc = subprocess.Popen([binary], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, bufsize=0)
        self._fd = self.proc.stdout.fileno()

    def write(self, data):
        self.proc.stdin.write(data)

    def _fill(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        ready, _, _ = select.select([self._fd], [], [], remaining)
        if not ready:
            return False
        chunk = os.read(self._fd, 4096)
        if not chunk:
            return False
        self._buf += chunk
        return True

    def readline(self):
        deadline = time.monotonic() + self.timeout
        while b"\n" not in self._buf:
            if not self._fill(deadline):
                line, self._buf = self._buf, b""
                return line               # incomplete / empty = timeout
        line, _, self._buf = self._buf.partition(b"\n")
        return line + b"\n"

    @property
    def in_waiting(self):
        """Bytes ready to read, like pyserial's Serial.in_waiting."""
        if select.select([self._fd], [], [], 0)[0]:
            chunk = os.read(self._fd, 4096)
            if chunk:
                self._buf += chunk
        return len(self._buf)

    def reset_input_buffer(self):
        time.sleep(0.05)
        while select.select([self._fd], [], [], 0)[0]:
            if not os.read(self._fd, 4096):
                break
        self._buf = b""

    def button_press(self):
        """Simulate SW0 (firmware sends EVT:RESET)."""
        self.proc.send_signal(signal.SIGUSR1)

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.wait(timeout=2)
