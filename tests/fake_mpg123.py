#!/usr/bin/env python3
"""Minimal emulation of `mpg123 --remote` for offline protocol testing."""

import sys
import time
import threading

state = {"playing": 0, "pos": 0, "length": 441000}  # 0 stopped, 1 paused, 2 playing


def out(line):
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def banner():
    time.sleep(0.3)  # mpg123's startup is slow; banner arrives after SILENCE was sent
    out("@R MPG123 (ThOr) v10")


threading.Thread(target=banner, daemon=True).start()

for raw in sys.stdin:
    cmd = raw.strip()
    if not cmd:
        continue
    op = cmd.split(" ")[0]

    if op == "SILENCE":
        pass  # real mpg123 gives no matchable reply; the banner covers the wait
    elif op == "V":
        out("@V %f%%" % float(cmd.split(" ")[1]))
    elif op == "LP":
        out("@I ID3v2.title:Some Title")
        out("@I fake metadata line")
        state["playing"] = 1
        state["pos"] = 0
        out("@P 1")
    elif op == "SAMPLE":
        out("@SAMPLE %d %d" % (state["pos"], state["length"]))
    elif op == "P":
        if state["playing"] == 2:
            state["playing"] = 1
            out("@P 1")
        else:
            state["playing"] = 2
            out("@S 1.0 3 44100 0 0 0 0")
            out("@P 2")
    elif op == "K":
        state["pos"] = int(cmd.split(" ")[1])
        out("@K " + str(state["pos"]))
    elif op == "PITCH":
        out("@PITCH " + cmd.split(" ")[1])
    elif op == "S":
        state["playing"] = 0
        out("@P 0")
    elif op == "Q":
        break
    else:
        out("@E unknown command: " + cmd)
