"""Tests for CLI argument parsing and helpers (no BLE hardware needed)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nus_client import __version__
from nus_client.client import NUS_MTU_FALLBACK, NUS_RX_UUID, NUS_SVC_UUID, NUS_TX_UUID


def test_version_string():
    assert __version__


def test_uuid_format():
    for uuid in (NUS_SVC_UUID, NUS_RX_UUID, NUS_TX_UUID):
        parts = uuid.split("-")
        assert len(parts) == 5


def test_mtu_is_positive():
    assert NUS_MTU_FALLBACK > 0


def test_cli_scan_no_adapter():
    with patch("nus_client.cli.get_adapter", side_effect=RuntimeError("no BLE adapter available")):
        from nus_client.cli import main

        rc = main(["--scan"])
        assert rc == 1


def test_cli_version(capsys):
    from nus_client.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out


class TestNUSConnection:
    def test_drain_tx_empty(self):
        from nus_client.client import NUSConnection

        peripheral = MagicMock()
        conn = NUSConnection(peripheral)
        assert conn.drain_tx() == b""

    def test_drain_tx_with_data(self):
        from nus_client.client import NUSConnection

        peripheral = MagicMock()
        conn = NUSConnection(peripheral)
        conn.tx_queue.put(b"hello")
        conn.tx_queue.put(b" world")
        assert conn.drain_tx() == b"hello world"

    def test_write_chunks_at_mtu(self):
        from nus_client.client import NUSConnection

        peripheral = MagicMock()
        conn = NUSConnection(peripheral)
        conn.use_write_command = True

        data = b"A" * 50
        conn.write(data)

        calls = peripheral.write_command.call_args_list
        assert len(calls) == 3  # 20 + 20 + 10
        assert calls[0].args == (NUS_SVC_UUID, NUS_RX_UUID, data[:20])
        assert calls[1].args == (NUS_SVC_UUID, NUS_RX_UUID, data[20:40])
        assert calls[2].args == (NUS_SVC_UUID, NUS_RX_UUID, data[40:])

    def test_write_uses_request_when_not_command(self):
        from nus_client.client import NUSConnection

        peripheral = MagicMock()
        conn = NUSConnection(peripheral)
        conn.use_write_command = False

        conn.write(b"hi")
        peripheral.write_request.assert_called_once()
        peripheral.write_command.assert_not_called()

    def test_is_connected_delegates(self):
        from nus_client.client import NUSConnection

        peripheral = MagicMock()
        peripheral.is_connected.return_value = True
        conn = NUSConnection(peripheral)
        assert conn.is_connected() is True

    def test_close_tolerates_errors(self):
        from nus_client.client import NUSConnection

        peripheral = MagicMock()
        peripheral.unsubscribe.side_effect = Exception("already unsubscribed")
        peripheral.disconnect.side_effect = Exception("already disconnected")
        conn = NUSConnection(peripheral)
        conn.close()
