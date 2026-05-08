"""Core BLE NUS transport — scan, connect, read/write."""

from __future__ import annotations

import contextlib
import queue
import sys
import time

import simplepyble

NUS_SVC_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # host -> peripheral
NUS_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # peripheral -> host

SCAN_DURATION_MS = 4000
ATT_HEADER_BYTES = 3
NUS_MTU_FALLBACK = 20
WRITE_CMD_DELAY_S = 0.01
WRITE_REQ_DELAY_S = 0.003


def get_adapter() -> simplepyble.Adapter:
    adapters = simplepyble.Adapter.get_adapters()
    if not adapters:
        raise RuntimeError("no BLE adapter available")
    return adapters[0]


def scan(adapter: simplepyble.Adapter, duration_ms: int = SCAN_DURATION_MS) -> list:
    adapter.scan_for(duration_ms)
    return adapter.scan_get_results()


def pick_peripheral(
    adapter: simplepyble.Adapter,
    *,
    name: str | None = None,
    addr: str | None = None,
    prefix: str | None = None,
    timeout: float = 12.0,
) -> simplepyble.Peripheral:
    if addr:
        addr_u = addr.upper()
    if name:
        name_l = name.lower()
    deadline = time.time() + timeout
    last_count = 0
    while time.time() < deadline:
        results = scan(adapter, 1500)
        for p in results:
            ident = p.identifier() or ""
            paddr = p.address().upper()
            if addr and paddr == addr_u:
                return p  # type: ignore[no-any-return]
            if name and ident.lower() == name_l:
                return p  # type: ignore[no-any-return]
            if not addr and not name and prefix and ident.startswith(prefix):
                return p  # type: ignore[no-any-return]
        if len(results) != last_count:
            last_count = len(results)
            sys.stderr.write(f"[scan] {len(results)} devices visible...\n")
    raise TimeoutError("no matching peripheral found within scan timeout")


def list_peripherals(adapter: simplepyble.Adapter, prefix: str | None = None) -> int:
    label = f"prefix={prefix!r}" if prefix else "all devices"
    sys.stderr.write(f"scanning for {SCAN_DURATION_MS} ms ({label})...\n")
    results = scan(adapter, SCAN_DURATION_MS)
    if not results:
        sys.stderr.write("none seen\n")
        return 1
    for p in results:
        ident = p.identifier() or "(no name)"
        connectable = "+" if p.is_connectable() else " "
        marker = connectable
        if prefix:
            marker = "*" if ident.startswith(prefix) else connectable
        rssi = p.rssi()
        print(f" {marker} {p.address()}  {rssi:4d} dBm  {ident}")
    return 0


def has_nus(peripheral: simplepyble.Peripheral) -> bool:
    """Check if a connected peripheral exposes NUS."""
    return any(svc.uuid().lower() == NUS_SVC_UUID.lower() for svc in peripheral.services())


def detect_write_command(peripheral: simplepyble.Peripheral) -> bool:
    """Check if RX supports write-without-response (must be connected)."""
    for svc in peripheral.services():
        if svc.uuid().lower() != NUS_SVC_UUID.lower():
            continue
        for ch in svc.characteristics():
            if ch.uuid().lower() != NUS_RX_UUID.lower():
                continue
            caps = {c.lower() for c in ch.capabilities()}
            return "write_without_response" in caps or "write_command" in caps
    return False


def send_rx(peripheral: simplepyble.Peripheral, data: bytes, use_write_command: bool) -> None:
    if use_write_command:
        peripheral.write_command(NUS_SVC_UUID, NUS_RX_UUID, data)
    else:
        peripheral.write_request(NUS_SVC_UUID, NUS_RX_UUID, data)


class NUSConnection:
    """Manages a BLE NUS connection with a TX notification queue."""

    def __init__(self, peripheral: simplepyble.Peripheral):
        self.peripheral = peripheral
        self.tx_queue: queue.SimpleQueue[bytes] = queue.SimpleQueue()
        self.use_write_command = False
        self.chunk_size = NUS_MTU_FALLBACK

    def open(self) -> None:
        self.peripheral.connect()

        if not has_nus(self.peripheral):
            self.peripheral.disconnect()
            raise RuntimeError("peripheral does not expose NUS")

        att_mtu = self.peripheral.mtu()
        if att_mtu > ATT_HEADER_BYTES:
            self.chunk_size = att_mtu - ATT_HEADER_BYTES
        else:
            self.chunk_size = NUS_MTU_FALLBACK

        self._subscribe_tx()
        self.use_write_command = detect_write_command(self.peripheral)
        mode = "write-no-response" if self.use_write_command else "write-with-response"
        sys.stderr.write(f"connected; MTU {att_mtu} (payload {self.chunk_size}), RX {mode}.\n")

    def _subscribe_tx(self) -> None:
        def on_tx(data: bytes) -> None:
            with contextlib.suppress(Exception):
                self.tx_queue.put_nowait(bytes(data))

        self.peripheral.notify(NUS_SVC_UUID, NUS_TX_UUID, on_tx)

    def write(self, data: bytes) -> None:
        sz = self.chunk_size
        chunks = [data[off : off + sz] for off in range(0, len(data), sz)]
        delay = WRITE_CMD_DELAY_S if self.use_write_command else WRITE_REQ_DELAY_S
        for i, chunk in enumerate(chunks):
            send_rx(self.peripheral, chunk, self.use_write_command)
            if i < len(chunks) - 1:
                time.sleep(delay)

    def drain_tx(self) -> bytes:
        chunks = []
        while True:
            try:
                chunks.append(self.tx_queue.get_nowait())
            except queue.Empty:
                break
        return b"".join(chunks)

    def is_connected(self) -> bool:
        return self.peripheral.is_connected()

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.peripheral.disconnect()
        time.sleep(0.3)
        self.drain_tx()
