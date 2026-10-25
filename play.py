import sys, time
sys.path.insert(0, "pc")
from serial_link import SerialLink

link = SerialLink.open_port("COM3")
time.sleep(1)
link.request("CONNECT")
print(link.request("NEW"))
turn = "X"
while True:
    cell = input("%s move (0-8, q to quit): " % turn)
    if cell == "q":
        break
    reply = link.request("MOVE:%s:%s" % (turn, cell))
    print(reply)
    if reply.startswith("OK:BOARD"):
        turn = "O" if turn == "X" else "X"
    elif reply.startswith(("WIN", "DRAW")):
        break
link.request("DISCONNECT")
link.close()