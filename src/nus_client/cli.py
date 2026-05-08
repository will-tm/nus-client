"""Command-line interface for nus-client."""

from __future__ import annotations

import argparse
import sys

from nus_client import __version__
from nus_client.client import NUSConnection, get_adapter, list_peripherals, pick_peripheral


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="nus-client",
        description="BLE Nordic UART Service (NUS) client — interactive terminal and PTY bridge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    ap.add_argument("--name", help="match peripheral by exact advertised name")
    ap.add_argument("--addr", help="match peripheral by Bluetooth address")
    ap.add_argument(
        "--prefix",
        default=None,
        help="match peripherals whose name starts with PREFIX",
    )
    ap.add_argument(
        "--scan",
        action="store_true",
        help="list visible peripherals and exit",
    )
    ap.add_argument(
        "--pty",
        action="store_true",
        help="expose the connection as a PTY instead of interactive mode",
    )
    ap.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="scan timeout in seconds (default: 12)",
    )
    args = ap.parse_args(argv)

    try:
        adapter = get_adapter()
    except RuntimeError as e:
        sys.stderr.write(f"error: {e}\n")
        return 1

    if args.scan:
        return list_peripherals(adapter, prefix=args.prefix)

    if not args.name and not args.addr and not args.prefix:
        sys.stderr.write("error: specify --name, --addr, or --prefix to identify a peripheral\n")
        sys.stderr.write("       use --scan to list visible devices first\n")
        return 1

    sys.stderr.write("scanning...\n")
    try:
        peripheral = pick_peripheral(
            adapter,
            name=args.name,
            addr=args.addr,
            prefix=args.prefix,
            timeout=args.timeout,
        )
    except TimeoutError as e:
        sys.stderr.write(f"error: {e}\n")
        return 1

    sys.stderr.write(f"connecting to {peripheral.identifier()!r} ({peripheral.address()})...\n")

    conn = NUSConnection(peripheral)
    try:
        conn.open()
    except Exception as e:
        sys.stderr.write(f"failed to connect: {e}\n")
        return 1

    try:
        if args.pty:
            from nus_client.pty_bridge import run_pty

            run_pty(conn)
        else:
            from nus_client.interactive import run_interactive

            run_interactive(conn)
    finally:
        sys.stderr.write("\ndisconnecting...\n")
        conn.close()

    return 0
