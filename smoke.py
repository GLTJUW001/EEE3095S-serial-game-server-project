import sys, time
sys.path.insert(0, "pc")
from serial_link import SerialLink

link = SerialLink.open_port("COM3")
time.sleep(1)                      # some boards reset when the port opens
print(link.request("CONNECT"))     # expect: OK
print(link.request("NEW"))         # expect: OK:BOARD:.........
print(link.request("MOVE:X:4"))    # expect: OK:BOARD:....X....
print(link.request("STATE"))       # expect: BOARD:....X....:O:PLAY
print(link.request("DISCONNECT"))  # expect: OK
link.close()