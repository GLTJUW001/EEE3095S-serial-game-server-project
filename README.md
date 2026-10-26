# Serial Game Server: Tic-Tac-Toe on an STM32

EEE3095S CS Project 2026. An STM32F051 board is the **authoritative game server**:
it owns the board, the turns and every rule. A Python GUI on the PC is a **thin
client**: it forwards clicks and draws whatever the server replies. The two talk
over UART (the board's ST-LINK virtual COM port) using a small ASCII,
line-based protocol.

```
 Python GUI (pc/gui.py)  <--- UART, 115200 8N1, ASCII lines --->  STM32 server (firmware/)
 pytest harness (tests/)  <------------ same link ------------->  (or the Python fake server)
```

Authors: **TODO: names**  |  Report: **TODO: link**  |  Demo video: **TODO: link**

## Repository layout

```
firmware/   STM32CubeIDE project (C): UART, parser, server FSM, game logic, LCD/LED/button
pc/         serial_link.py   framing, checksum, request/response wrapper
            game_client.py   GUI logic (no Tk): sync, resume, error handling
            gui.py           Tkinter window
            fake_server.py   Python model of the board, for development without hardware
tests/      pytest suite; runs on the fake server, the firmware logic, or the real board
hostsim/    fw_host.c: runs the real firmware parser/server/game on the PC (optional)
docs/       protocol specification, diagrams
evidence/   test output and screenshots
```

## Requirements

- Python 3.8 or newer. Tkinter ships with the Windows and macOS installers; on
  Debian/Ubuntu install it with `sudo apt install python3-tk`.
- `pip install -r requirements.txt` (pytest and pyserial)
- For the board: STM32CubeIDE (includes the Arm toolchain and STM32CubeProgrammer)
  and a USB cable to the UCT STM32 board.

If `pytest` is "not recognized" on Windows, run it as `python -m pytest`.

## Quick start (no board needed)

```
pip install -r requirements.txt
python -m pytest                 # protocol and GUI-logic tests against the Python fake server
python pc/gui.py --fake          # the GUI, talking to the fake server
```

`--fake` adds a "Press SW0 (sim)" button that mimics the board's reset button.

## Running with the board

1. **Build and flash.** Open STM32CubeIDE, import the `firmware/` folder
   (File, Import, Existing Projects into Workspace; do not tick "Copy projects
   into workspace"), build with Ctrl+B, and flash. The build produces
   `firmware/build/Debug/server/GameServer.elf`. If the run configuration looks
   for `Debug/Project.elf`, change its *C/C++ Application* field to that file, or
   flash it with STM32CubeProgrammer (ST-LINK, Open file, Download).
   Alternatively, with the Arm toolchain on your PATH: `cd firmware && make`.
2. **Check it booted.** The LCD shows `IDLE / Waiting for PC`.
3. **Find the COM port.** Windows: Device Manager, Ports (COM & LPT), "STLink
   Virtual COM Port (COMx)". Linux: `/dev/ttyACM0`. macOS: `/dev/cu.usbmodem*`.
   Close any other program using the port (serial terminals, debug sessions).
4. **Run the tests on the board:**
   - PowerShell: `$env:SERIAL_PORT="COM3"; python -m pytest -v`
   - bash: `SERIAL_PORT=/dev/ttyACM0 python -m pytest -v`

   Tests that need a simulated button are skipped on real hardware; press SW0
   by hand and check the LCD returns to IDLE.
5. **Run the GUI:** `python pc/gui.py --port COM3` (or pick the port in the window).

### Board behaviour

| Item | Behaviour |
|---|---|
| LCD | IDLE, whose turn it is with the board as `XOX|.O.|..X`, win/draw/resigned |
| Green LED | on = X to move, off = O to move or idle, 2 Hz blink = game over |
| SW0 button | debounced; resets the game to IDLE and sends the unsolicited line `EVT:RESET` |

## Protocol summary

Requests are single ASCII lines ending in `\n`, at most 32 bytes. An optional
checksum suffix `*HH` (XOR of the preceding bytes, two hex digits) is validated
if present. Replies carry no checksum. Board encoding is 9 characters, index 0-8
row-major, `.` empty, `X`, `O`. X always moves first.

| Request | Reply |
|---|---|
| `CONNECT` | `OK` (idle) or `NACK:BUSY` |
| `NEW` | `OK:BOARD:.........` or `NACK:BUSY` |
| `MOVE:<M>:<i>` or `MOVE:<i>` | `OK:BOARD:<9>`, `WIN:<M>:<9>`, `DRAW:<9>`, or a `NACK:` below |
| `STATE` | `BOARD:<9>:<turn>:<PLAY\|OVER>` or `NACK:NOGAME` |
| `RESIGN` | `OK:GAMEOVER` or `NACK:NOGAME` |
| `DISCONNECT` | `OK` (from any state) |

Errors: `NACK:OCCUPIED`, `RANGE`, `NOTURN`, `NOGAME`, `BUSY`, `BADCMD`, `CHECKSUM`,
`OVERFLOW` (over 32 bytes), `TIMEOUT` (partial frame abandoned after 500 ms).
Every rejected request leaves all game state unchanged. The full specification is
in `docs/Protocol_Spec_v1.pdf`.

## Tests

`tests/test_server.py` drives the communication interface only (no human
interaction) and covers: CONNECT/NEW, legal moves, occupied cells, out-of-range
and out-of-turn moves, moves after game over, scripted win and draw sequences,
resign, disconnect, bad checksums, oversized and garbage frames, partial frames,
and recovery after each. `tests/test_client.py` covers the GUI logic (resuming a
game, the button reset event, timeouts, malformed replies, a lost port).

One suite, three targets:

| Target | Command |
|---|---|
| Python fake server (default) | `python -m pytest` |
| Real firmware logic on the PC (Linux/macOS/WSL, needs a C compiler) | see below |
| Real board | `SERIAL_PORT=<port> python -m pytest` |

Firmware logic on the PC:

```
cc -std=c11 -O2 -Ifirmware/Core/Inc firmware/Core/Src/game.c firmware/Core/Src/server.c firmware/Core/Src/parser.c hostsim/fw_host.c -o hostsim/fw_host
FIRMWARE_HOST=hostsim/fw_host python -m pytest
```

The firmware also has its own C unit tests: `cd firmware && make test`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `pytest` not recognized | use `python -m pytest` (the Scripts folder is not on PATH) |
| `Debug/Project.elf not found` when flashing | the build writes `build/Debug/server/GameServer.elf`; point the run configuration at it |
| `LinkTimeout` / "No reply from the board" | wrong COM port, port held by another program, or firmware not running |
| `PermissionError` / access denied on the port | close other serial programs and debug sessions |
| COM number changed after replugging | check Device Manager again |
| GUI says "Connected: resumed the game already in progress" | the board still held a game from earlier; this is intended |
