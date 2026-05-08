"""PTY bridge — expose BLE NUS as a pseudo-terminal device.

Third-party tools (minicom, screen, picocom, or any serial library) can
open the printed PTY path and communicate with the BLE peripheral as if
it were a local serial port.
"""

from __future__ import annotations

import contextlib
import os
import select
import signal
import sys
import threading
import time

from nus_client.client import NUSConnection

_stop = threading.Event()


def _on_signal(signum: int, frame: object) -> None:
    _stop.set()


def run_pty(conn: NUSConnection) -> None:
    master_fd, slave_fd = os.openpty()
    slave_path = os.ttyname(slave_fd)

    sys.stderr.write(f"PTY ready: {slave_path}\n")
    sys.stderr.write("Ctrl-C to exit.\n")
    print(slave_path)
    sys.stdout.flush()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        while conn.is_connected() and not _stop.is_set():
            tx_data = conn.drain_tx()
            if tx_data:
                with contextlib.suppress(OSError):
                    os.write(master_fd, tx_data)

            r, _, _ = select.select([master_fd], [], [], 0.05)
            if not r:
                continue

            try:
                chunk = os.read(master_fd, 4096)
            except OSError:
                time.sleep(0.1)
                continue

            if not chunk:
                break

            conn.write(chunk)
    finally:
        os.close(master_fd)
        os.close(slave_fd)
