# nus-client

BLE Nordic UART Service (NUS) client for interactive terminals and PTY bridging.

Connect to any BLE peripheral that exposes the standard Nordic UART Service and interact with it from your terminal — or expose the connection as a pseudo-terminal (PTY) device so third-party tools (minicom, screen, picocom, or any serial library) can talk to it like a local serial port.

## Installation

```bash
pip install nus-client
```

### From source

```bash
git clone https://github.com/will-tm/nus-client.git
cd nus-client
pip install -e ".[dev]"
```

## Quick start

### Scan for nearby BLE devices

```bash
nus-client --scan
```

Devices exposing NUS are marked with `*`.

### Interactive terminal

```bash
# Auto-connect to the first NUS peripheral found
nus-client

# Connect by name
nus-client --name "My Device"

# Connect by Bluetooth address
nus-client --addr E8:C1:C7:11:22:33

# Filter by name prefix
nus-client --prefix "Sensor"
```

Each keystroke is sent as a BLE write; the remote device's responses print to stdout. Press **Ctrl-]** to disconnect.

### PTY bridge

```bash
nus-client --pty
```

This creates a pseudo-terminal and prints its path (e.g. `/dev/ttys005`). Any tool that speaks serial can open that path:

```bash
# In another terminal
screen /dev/ttys005
# or
minicom -D /dev/ttys005
# or from Python
import serial
ser = serial.Serial("/dev/ttys005")
```

The PTY path is also printed to **stdout** (status messages go to stderr), so scripts can capture it:

```bash
PTY=$(nus-client --pty 2>/dev/null)
```

## CLI reference

```
usage: nus-client [-h] [--version] [--name NAME] [--addr ADDR]
                  [--prefix PREFIX] [--scan] [--pty] [--timeout TIMEOUT]

options:
  --name NAME        match peripheral by exact advertised name
  --addr ADDR        match peripheral by Bluetooth address
  --prefix PREFIX    match peripherals whose name starts with PREFIX
  --scan             list visible peripherals and exit
  --pty              expose the connection as a PTY instead of interactive mode
  --timeout TIMEOUT  scan timeout in seconds (default: 12)
```

## How it works

nus-client uses [SimpleBLE](https://github.com/simpleble/simpleble) to communicate over Bluetooth Low Energy. The Nordic UART Service is a de-facto standard (UUID `6e400001-b5a3-f393-e0a9-e50e24dcca9e`) implemented by Nordic nRF SDKs, Zephyr, and many custom firmware stacks.

- **RX characteristic** (`6e400002-...`): host writes data here (sent to the peripheral)
- **TX characteristic** (`6e400003-...`): peripheral sends notifications here (received by the host)

In **interactive mode**, the terminal is set to raw mode and keystrokes are forwarded over BLE. In **PTY mode**, a pseudo-terminal pair is created — the master side is bridged to BLE, and the slave path is exposed for external tools.

## Platform support

| Platform | Interactive | PTY |
|----------|-------------|-----|
| macOS    | Yes         | Yes |
| Linux    | Yes         | Yes |
| Windows  | Yes         | No  |

PTY mode is not available on Windows because it relies on POSIX pseudo-terminals (`openpty`). Interactive mode works on Windows using `msvcrt`.

## Development

```bash
pip install -e ".[dev]"

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Test
pytest
```

## License

MIT
