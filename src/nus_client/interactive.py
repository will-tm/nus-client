"""Interactive raw-terminal mode — stdin keystrokes over BLE, TX to stdout."""

from __future__ import annotations

import contextlib
import os
import signal
import sys
import time

from nus_client.client import NUSConnection

EXIT_KEY = 0x1D  # Ctrl-]

_IS_WINDOWS = sys.platform == "win32"


def _enable_raw_stdin() -> list | None:
    if _IS_WINDOWS or not sys.stdin.isatty():
        return None
    import termios
    import tty

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setraw(fd)
    return saved


def _restore_stdin(saved: list | None) -> None:
    if saved is None:
        return
    import termios

    with contextlib.suppress(Exception):
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, saved)


def _run_posix(conn: NUSConnection) -> None:
    import select

    saved_termios = _enable_raw_stdin()
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    try:
        while conn.is_connected():
            data = conn.drain_tx()
            if data:
                sys.stdout.buffer.write(data)
                sys.stdout.buffer.flush()

            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not r:
                continue

            chunk = os.read(sys.stdin.fileno(), 4096)
            if not chunk:
                break

            if EXIT_KEY in chunk:
                idx = chunk.index(bytes([EXIT_KEY]))
                if idx > 0:
                    conn.write(chunk[:idx])
                break

            conn.write(chunk)
    finally:
        _restore_stdin(saved_termios)


def _run_windows(conn: NUSConnection) -> None:
    import msvcrt  # type: ignore[import-not-found]

    kbhit = msvcrt.kbhit  # type: ignore[attr-defined]
    getch = msvcrt.getch  # type: ignore[attr-defined]

    while conn.is_connected():
        data = conn.drain_tx()
        if data:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

        if not kbhit():
            time.sleep(0.05)
            continue

        ch: bytes = getch()
        if ch == b"\xe0" or ch == b"\x00":
            ext: bytes = getch()
            conn.write(ch + ext)
            continue

        if ch[0] == EXIT_KEY:
            break

        conn.write(ch)


def run_interactive(conn: NUSConnection) -> None:
    sys.stderr.write("Ctrl-] to exit.\n")
    if _IS_WINDOWS:
        _run_windows(conn)
    else:
        _run_posix(conn)
