"""Tkinter GUI for the STM32 Tic-Tac-Toe game server.

    python pc/gui.py                 # pick the port in the window
    python pc/gui.py --port COM3     # preselect a port
    python pc/gui.py --fake          # no board: talk to the built-in Python fake server

The window only DRAWS what game_client.GameClient says. All game rules live on
the STM32; the GUI forwards clicks and shows the server's replies and errors.
"""

import argparse
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_client import DISCONNECTED, GameClient  # noqa: E402
from serial_link import SerialLink  # noqa: E402

POLL_MS = 150                       # how often to look for an unsolicited EVT:RESET
MAX_LOG_LINES = 200
FONT = "Segoe UI"
LEVEL_COLOURS = {"info": "#333333", "ok": "#1b7f3b", "warn": "#a15c00", "error": "#b3261e"}
MARK_COLOURS = {"X": "#1f5fbf", "O": "#c0392b", ".": "#333333"}
WIN_BG = "#c8f0cf"
FAKE_PORT_LABEL = "(simulated board)"


def available_ports():
    """Serial port names, with the ST-LINK virtual COM port first if it can be spotted."""
    try:
        from serial.tools import list_ports
        found = list(list_ports.comports())
    except Exception:
        return []
    found.sort(key=lambda p: 0 if any(s in (p.description or "")
                                      for s in ("STLink", "STMicroelectronics", "ST-LINK")) else 1)
    return [p.device for p in found]


class App:
    def __init__(self, root, fake=False, default_port=""):
        self.root = root
        self.fake = fake
        self.client = GameClient(log_cb=self._log_line)
        root.title("Tic-Tac-Toe  |  STM32 Game Server")
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._build(default_port)
        self.refresh()
        self.root.after(POLL_MS, self._tick)

    # -- layout ------------------------------------------------------------------------
    def _build(self, default_port):
        pad = {"padx": 12, "pady": 4}

        top = tk.Frame(self.root)
        top.pack(fill="x", **pad)
        tk.Label(top, text="Port:").pack(side="left")
        ports = available_ports()
        self.port_var = tk.StringVar(value=FAKE_PORT_LABEL if self.fake
                                     else (default_port or (ports[0] if ports else "")))
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, values=ports, width=16)
        self.port_box.pack(side="left", padx=6)
        self.refresh_btn = tk.Button(top, text="Refresh", command=self.on_refresh_ports)
        self.refresh_btn.pack(side="left")
        self.connect_btn = tk.Button(top, text="Connect", width=11, command=self.on_toggle_connection)
        self.connect_btn.pack(side="right")

        self.headline = tk.Label(self.root, text="", font=(FONT, 20, "bold"))
        self.headline.pack(**pad)
        self.message = tk.Label(self.root, text="", font=(FONT, 11), wraplength=340, height=3)
        self.message.pack(**pad)

        board = tk.Frame(self.root)
        board.pack(**pad)
        self.cells = []
        for i in range(9):
            cell = tk.Button(board, text="", width=3, height=1, font=(FONT, 34, "bold"),
                             command=lambda i=i: self.on_cell(i))
            cell.grid(row=i // 3, column=i % 3, padx=3, pady=3)
            self.cells.append(cell)
        self.default_bg = self.cells[0].cget("bg")

        actions = tk.Frame(self.root)
        actions.pack(**pad)
        tk.Label(actions, text="Mode:").pack(side="left", padx=(0, 4))
        self.game_mode_var = tk.StringVar(value="Two players")
        self.game_mode_box = ttk.Combobox(
            actions, textvariable=self.game_mode_var,
            values=("Two players", "Vs computer"), state="readonly", width=13)
        self.game_mode_box.pack(side="left", padx=4)
        self.new_btn = tk.Button(actions, text="New Game", width=12, command=self.on_new)
        self.new_btn.pack(side="left", padx=4)
        self.resign_btn = tk.Button(actions, text="Resign", width=12, command=self.on_resign)
        self.resign_btn.pack(side="left", padx=4)
        self.sim_btn = None
        if self.fake:
            self.sim_btn = tk.Button(actions, text="Press SW0 (sim)", command=self.on_sim_button)
            self.sim_btn.pack(side="left", padx=4)

        tk.Label(self.root, text="Move history:", anchor="w").pack(fill="x", padx=12)
        self.history_box = tk.Listbox(self.root, height=4, width=48, font=("Consolas", 10))
        self.history_box.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(self.root, text="Messages with the board:", anchor="w").pack(fill="x", padx=12)
        self.log = tk.Text(self.root, height=8, width=48, font=("Consolas", 9), state="disabled")
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 10))

    # -- drawing -------------------------------------------------------------------------
    def refresh(self):
        c = self.client
        connected = c.mode != DISCONNECTED

        win = c.result == "WIN"
        self.headline.config(text=c.headline, fg=LEVEL_COLOURS["ok"] if win else "#222222")
        self.message.config(text=c.message, fg=LEVEL_COLOURS.get(c.level, "#333333"))

        for i, cell in enumerate(self.cells):
            mark = c.board[i]
            cell.config(
                text="" if mark == "." else mark,
                state="normal" if (c.board_enabled and mark == ".") else "disabled",
                disabledforeground=MARK_COLOURS.get(mark, "#333333"),
                fg=MARK_COLOURS.get(mark, "#333333"),
                bg=WIN_BG if i in c.win_line else self.default_bg,
            )

        self.connect_btn.config(text="Disconnect" if connected else "Connect")
        self.port_box.config(state="disabled" if connected or self.fake else "normal")
        self.refresh_btn.config(state="disabled" if connected or self.fake else "normal")
        self.new_btn.config(state="normal" if connected else "disabled")
        self.game_mode_box.config(state="readonly" if connected and c.mode != "PLAYING" else "disabled")
        self.resign_btn.config(state="normal" if connected and c.mode == "PLAYING" else "disabled")
        self.history_box.delete(0, "end")
        for number, (mark, cell) in enumerate(c.history, start=1):
            player = "Computer" if c.vs_ai and mark == "O" else mark
            self.history_box.insert("end", "%d. %s -> cell %d" % (number, player, cell))
        if self.sim_btn is not None:
            self.sim_btn.config(state="normal" if connected else "disabled")

    def _log_line(self, direction, text):
        self.log.config(state="normal")
        self.log.insert("end", "%-2s %s\n" % (direction, text))
        lines = int(float(self.log.index("end")))
        if lines > MAX_LOG_LINES:
            self.log.delete("1.0", "%d.0" % (lines - MAX_LOG_LINES))
        self.log.see("end")
        self.log.config(state="disabled")

    # -- user actions ----------------------------------------------------------------------
    def on_refresh_ports(self):
        ports = available_ports()
        self.port_box.config(values=ports)
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def on_toggle_connection(self):
        if self.client.mode == DISCONNECTED:
            self._connect()
        else:
            self.client.disconnect()
        self.refresh()

    def _connect(self):
        try:
            if self.fake:
                from fake_server import FakeServer
                link = SerialLink(FakeServer().transport())
            else:
                port = self.port_var.get().strip()
                if not port:
                    self.client.notify("Choose a serial port first (Refresh to rescan).", "error")
                    return
                link = SerialLink.open_port(port)
                link.flush_input()
        except Exception as exc:          # port busy, not found, pyserial missing ...
            self.client.notify("Could not open the port: %s" % exc, "error")
            return
        if not self.client.connect(link):
            text, level = self.client.message, self.client.level
            try:
                link.close()
            except Exception:
                pass
            self.client.link = None
            self.client.notify(text, level)

    def on_cell(self, index):
        self.client.move(index)
        self.refresh()

    def on_new(self):
        vs_ai = self.game_mode_var.get() == "Vs computer"
        self.client.new_game(vs_ai=vs_ai)
        self.refresh()

    def on_resign(self):
        if messagebox.askyesno("Resign", "Resign the current game?"):
            self.client.resign()
            self.refresh()

    def on_sim_button(self):
        """Fake mode only: act like a press of the board's SW0 button."""
        transport = getattr(self.client.link, "transport", None)
        if transport is not None and hasattr(transport, "button_press"):
            transport.button_press()

    def on_close(self):
        try:
            self.client.disconnect()
        finally:
            self.root.destroy()

    # -- timer -------------------------------------------------------------------------------
    def _tick(self):
        try:
            if self.client.poll():
                self.refresh()
        finally:
            self.root.after(POLL_MS, self._tick)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tic-Tac-Toe GUI for the STM32 game server")
    parser.add_argument("--port", default=os.environ.get("SERIAL_PORT", ""),
                        help="serial port to preselect, e.g. COM3")
    parser.add_argument("--fake", action="store_true",
                        help="use the built-in Python fake server instead of a board")
    args = parser.parse_args(argv)
    root = tk.Tk()
    App(root, fake=args.fake, default_port=args.port)
    root.mainloop()


if __name__ == "__main__":
    main()
