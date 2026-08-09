import os
import pty
import time

from marta.logging_setup import setup_stdout_logging
from marta.rfid import RFIDReader
from marta.events import TagPlaced, TagRemoved


def test_rfid_reader():
    setup_stdout_logging()

    master, slave = pty.openpty()
    slave_name = os.ttyname(slave)

    events = []
    reader = RFIDReader(post=events.append, port=slave_name)

    valid = b"\x02" + b"010203040501" + b"\x03"  # 01^02^03^04^05 == 0x01

    os.write(master, valid)
    time.sleep(0.3)
    assert events == [TagPlaced("010203040501")], events

    # garbled frame with non-hex data must be discarded and must not kill the thread
    os.write(master, b"\x02" + b"GGGGGGGGGGGG" + b"\x03")
    time.sleep(0.3)
    assert events == [TagPlaced("010203040501")], events
    assert reader._read_rfid_thread.is_alive(), "reader thread died on garbage"

    # frame with wrong tail must be discarded
    os.write(master, b"\x02" + b"010203040501" + b"\xff")
    time.sleep(0.3)

    # bad checksum must be discarded
    os.write(master, b"\x02" + b"0102030405FF" + b"\x03")
    time.sleep(0.3)
    assert events == [TagPlaced("010203040501")], events

    # silence -> tag removal
    time.sleep(0.8)
    assert events == [TagPlaced("010203040501"), TagRemoved()], events

    # tag placed again after all the garbage -> still detected
    os.write(master, valid)
    time.sleep(0.3)
    assert events == [TagPlaced("010203040501"), TagRemoved(), TagPlaced("010203040501")], events
    assert reader._read_rfid_thread.is_alive()

    reader.terminate()


if __name__ == "__main__":
    test_rfid_reader()
    print("ALL ASSERTIONS PASSED")
